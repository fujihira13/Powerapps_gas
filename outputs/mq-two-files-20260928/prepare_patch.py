"""Prepare a guarded, minimal update for the approved MQ child-file flow."""

import hashlib
import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
HERE = Path(__file__).resolve().parent
LIVE = HERE / "flow-before.json"
CANDIDATE = ROOT / "outputs/flow-implementation/flow-definition.mq-local-candidate.json"
EXPECTED_ID = "ef881fbc-dcb8-f111-b377-7ced8d3141aa"
EXPECTED_NAME = "架空ログ証跡_件別Excel転記"
ALLOWED_PREFIX = "/properties/definition/actions/Condition_Start_Ready/actions/Condition_One_Note/else/actions/"


def flatten(value, prefix=""):
    if isinstance(value, dict):
        result = {}
        for key, child in value.items():
            result.update(flatten(child, f"{prefix}/{key}"))
        return result
    return {prefix: value}


row = json.loads(LIVE.read_text(encoding="utf-8-sig"))
assert row["workflowid"] == EXPECTED_ID
assert row["name"] == EXPECTED_NAME
assert row["statecode"] == 1 and row["statuscode"] == 2
etag = row["@odata.etag"]
assert etag.startswith('W/"') and etag.endswith('"')
live = json.loads(row["clientdata"])
candidate = json.loads(CANDIDATE.read_text(encoding="utf-8"))
old, new = flatten(live), flatten(candidate)
missing = object()
changed = sorted(path for path in old.keys() | new.keys() if old.get(path, missing) != new.get(path, missing))
assert changed and all(path.startswith(ALLOWED_PREFIX) for path in changed), "unexpected flow diff"
body = {"clientdata": json.dumps(candidate, ensure_ascii=False, separators=(",", ":"))}
(HERE / "patch-body.json").write_text(json.dumps(body, ensure_ascii=False, separators=(",", ":")) + "\n", encoding="utf-8")
(HERE / "etag.txt").write_text(etag + "\n", encoding="utf-8")
(HERE / "diff-paths.txt").write_text("\n".join(changed) + "\n", encoding="utf-8")
print(json.dumps({"flow_id": EXPECTED_ID, "changed_paths": len(changed), "candidate_sha256": hashlib.sha256(CANDIDATE.read_bytes()).hexdigest(), "etag": etag}, ensure_ascii=False))
