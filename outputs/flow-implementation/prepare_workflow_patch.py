"""Offline preflight for a conditional Dataverse workflow clientdata update.

This helper never makes network requests. It consumes a saved Dataverse GET
response, compares it with the reviewed C02 candidate, and writes a minimal
PATCH body plus the ETag to a new local directory only when all checks pass.
"""

from __future__ import annotations

import argparse
import hashlib
import importlib.util
import json
import re
import sys
from pathlib import Path
from typing import Any


HERE = Path(__file__).resolve().parent
EXPECTED_WORKFLOW_ID = "ef881fbc-dcb8-f111-b377-7ced8d3141aa"
EXPECTED_WORKFLOW_NAME = "架空ログ証跡_件別Excel転記"
EXPECTED_CANDIDATE_SHA256 = (
    "917d7ec981b5490da494d8f5b3f14b58cf6b2ad723870360634d96ab60bbfe1b"
)
DEFAULT_CANDIDATE = HERE / "flow-definition.excelurl-c02-local-candidate.json"

LOG_ACTION_ROOT = (
    "/properties/definition/actions/Condition_Start_Ready/actions/"
    "Condition_One_Note/actions"
)
ALLOWED_EXACT_PATHS = {
    f"{LOG_ACTION_ROOT}/Compose_IsValidLog/inputs",
    f"{LOG_ACTION_ROOT}/Condition_Log_Matches/else/actions/"
    "Update_case_stop_log_invalid/inputs/parameters/item",
}
ALLOWED_PREFIXES = (
    f"{LOG_ACTION_ROOT}/Compose_LogValidationReason",
    f"{LOG_ACTION_ROOT}/Compose_IsValidLog/runAfter",
    f"{LOG_ACTION_ROOT}/Update_case_stop_log_unreadable",
)


class PreflightError(ValueError):
    """A fail-closed validation error suitable for a short console report."""


def _load_candidate(path: Path) -> tuple[dict[str, Any], str, str]:
    try:
        raw_bytes = path.read_bytes()
        candidate = json.loads(raw_bytes.decode("utf-8-sig"))
    except (OSError, UnicodeError, json.JSONDecodeError) as exc:
        raise PreflightError("candidate file cannot be read as JSON") from exc
    digest = hashlib.sha256(raw_bytes).hexdigest()
    if digest != EXPECTED_CANDIDATE_SHA256:
        raise PreflightError("candidate SHA-256 differs from the reviewed C02 candidate")
    if not isinstance(candidate, dict) or not isinstance(candidate.get("properties"), dict):
        raise PreflightError("candidate has an unsupported root shape")
    if not isinstance(candidate["properties"].get("definition"), dict):
        raise PreflightError("candidate definition is missing")
    compact = json.dumps(candidate, ensure_ascii=False, separators=(",", ":"))
    _validate_with_builder(candidate)
    return candidate, compact, digest


def _validate_with_builder(candidate: dict[str, Any]) -> None:
    builder_path = HERE / "build_flow_definition.py"
    spec = importlib.util.spec_from_file_location("flow_definition_builder", builder_path)
    if spec is None or spec.loader is None:
        raise PreflightError("local flow validator cannot be loaded")
    module = importlib.util.module_from_spec(spec)
    try:
        spec.loader.exec_module(module)
        errors = module.validate_excelurl_candidate(candidate)
    except Exception as exc:  # keep candidate contents out of diagnostics
        raise PreflightError("local flow validator failed") from exc
    if errors:
        raise PreflightError(f"candidate fails local validation ({len(errors)} issue(s))")


def _read_entity(path: Path) -> tuple[dict[str, Any], str, str]:
    try:
        response = json.loads(path.read_text(encoding="utf-8-sig"))
    except (OSError, UnicodeError, json.JSONDecodeError) as exc:
        raise PreflightError("saved Dataverse response cannot be read as JSON") from exc
    return _parse_entity(response)


def _parse_entity(response: Any) -> tuple[dict[str, Any], str, str]:
    if not isinstance(response, dict):
        raise PreflightError("saved Dataverse response is not a single entity object")
    row = response
    if "value" in response:
        values = response.get("value")
        if not isinstance(values, list) or len(values) != 1 or not isinstance(values[0], dict):
            raise PreflightError("GET response must identify exactly one workflow")
        row = values[0]
    workflow_id = row.get("workflowid")
    if not isinstance(workflow_id, str) or workflow_id.strip("{} ").lower() != EXPECTED_WORKFLOW_ID:
        raise PreflightError("GET response workflow ID does not match the approved target")
    if row.get("name") != EXPECTED_WORKFLOW_NAME:
        raise PreflightError("GET response workflow name does not match the approved target")
    if row.get("statecode") != 1 or row.get("statuscode") != 2:
        raise PreflightError("workflow is not in the expected active state")
    etag = row.get("@odata.etag")
    if not isinstance(etag, str) or not re.fullmatch(r'(?:W/)?"[^"\r\n]+"', etag):
        raise PreflightError("GET response has no usable row ETag")
    raw_clientdata = row.get("clientdata")
    if not isinstance(raw_clientdata, str):
        raise PreflightError("GET response clientdata is missing or not a string")
    try:
        clientdata = json.loads(raw_clientdata)
    except json.JSONDecodeError as exc:
        raise PreflightError("GET response clientdata is not valid JSON") from exc
    if not isinstance(clientdata, dict):
        raise PreflightError("GET response clientdata has an unsupported shape")
    return clientdata, etag, raw_clientdata


def _flatten(value: Any, path: str = "") -> dict[str, Any]:
    if isinstance(value, dict) and value:
        flattened: dict[str, Any] = {}
        for key, child in value.items():
            flattened.update(_flatten(child, f"{path}/{key}"))
        return flattened
    return {path or "/": value}


def changed_paths(live: dict[str, Any], candidate: dict[str, Any]) -> list[str]:
    old = _flatten(live)
    new = _flatten(candidate)
    return sorted(
        path for path in set(old) | set(new)
        if old.get(path, _MISSING) != new.get(path, _MISSING)
    )


_MISSING = object()


def _is_allowed(path: str) -> bool:
    if path in ALLOWED_EXACT_PATHS:
        return True
    return any(path == prefix or path.startswith(prefix + "/") for prefix in ALLOWED_PREFIXES)


def _check_only_c02_differences(live: dict[str, Any], candidate: dict[str, Any]) -> list[str]:
    paths = changed_paths(live, candidate)
    unexpected = [path for path in paths if not _is_allowed(path)]
    if unexpected:
        # Paths contain action/property names only; never print field contents.
        summary = ", ".join(unexpected[:8])
        suffix = " …" if len(unexpected) > 8 else ""
        raise PreflightError(f"live/candidate differences exceed C02 allowlist: {summary}{suffix}")
    if not paths:
        raise PreflightError("live workflow already equals the candidate; no PATCH is needed")
    return paths


def _write_new_file(path: Path, text: str) -> None:
    try:
        with path.open("x", encoding="utf-8", newline="\n") as handle:
            handle.write(text)
    except FileExistsError as exc:
        raise PreflightError(f"output already exists: {path.name}") from exc
    except OSError as exc:
        raise PreflightError(f"cannot create output: {path.name}") from exc


def prepare(live_path: Path, candidate_path: Path, output_dir: Path) -> None:
    candidate, candidate_compact, candidate_hash = _load_candidate(candidate_path)
    live, etag, _ = _read_entity(live_path)
    paths = _check_only_c02_differences(live, candidate)
    if output_dir.exists():
        raise PreflightError("output directory already exists; choose a new empty path")
    output_dir.mkdir(parents=True)
    body = json.dumps({"clientdata": candidate_compact}, ensure_ascii=False, separators=(",", ":"))
    _write_new_file(output_dir / "patch-body.json", body + "\n")
    _write_new_file(output_dir / "etag.txt", etag + "\n")
    manifest = {
        "workflowId": EXPECTED_WORKFLOW_ID,
        "candidateSha256": candidate_hash,
        "liveClientdataSha256": hashlib.sha256(
            json.dumps(live, ensure_ascii=False, separators=(",", ":")).encode("utf-8")
        ).hexdigest(),
        "candidateClientdataSha256": hashlib.sha256(candidate_compact.encode("utf-8")).hexdigest(),
        "allowedDifferenceCount": len(paths),
        "allowedDifferencePaths": paths,
        "networkRequestsMade": False,
    }
    _write_new_file(
        output_dir / "preflight-manifest.json",
        json.dumps(manifest, ensure_ascii=False, indent=2) + "\n",
    )
    print(f"Preflight passed. C02-allowlisted semantic differences: {len(paths)}.")
    print(f"Candidate SHA-256: {candidate_hash}")
    print("No network request was made. ETag and PATCH body are saved locally.")


def verify_readback(readback_path: Path, candidate_path: Path) -> None:
    candidate, candidate_compact, candidate_hash = _load_candidate(candidate_path)
    _, _, returned_raw = _read_entity(readback_path)
    if returned_raw != candidate_compact:
        raise PreflightError("readback clientdata string is not identical to the candidate")
    print(f"Readback passed. Candidate SHA-256: {candidate_hash}")
    print("Workflow remains active. No network request was made by this helper.")


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    modes = parser.add_mutually_exclusive_group(required=True)
    modes.add_argument("--prepare", action="store_true", help="compare saved pre-update GET and write local PATCH artifacts")
    modes.add_argument("--verify-readback", action="store_true", help="compare saved post-update GET with the candidate")
    parser.add_argument("--live-response", type=Path, help="saved GET response before update")
    parser.add_argument("--readback-response", type=Path, help="saved GET response after update")
    parser.add_argument("--candidate", type=Path, default=DEFAULT_CANDIDATE)
    parser.add_argument("--output-dir", type=Path, help="new directory for minimal PATCH body and ETag")
    args = parser.parse_args(argv)
    try:
        if args.prepare:
            if args.live_response is None or args.output_dir is None:
                raise PreflightError("--prepare requires --live-response and --output-dir")
            prepare(args.live_response, args.candidate, args.output_dir)
        else:
            if args.readback_response is None:
                raise PreflightError("--verify-readback requires --readback-response")
            verify_readback(args.readback_response, args.candidate)
        return 0
    except PreflightError as exc:
        print(f"Preflight stopped: {exc}", file=sys.stderr)
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
