"""Package Office Script TypeScript as unverified local .osts candidates.

Microsoft documents the relationship between ``main`` parameters/returns and
Power Automate inputs/outputs, but does not publish the .osts wrapper schema.
The parameterInfo/apiInfo shape here follows community examples and still needs
validation through Excel/Power Automate import and readback. This builder only
writes local files; it does not register, upload, or send files anywhere.
"""

from __future__ import annotations

import json
from pathlib import Path
from tempfile import NamedTemporaryFile


ROOT = Path(__file__).parent
SOURCE_DIR = ROOT / "office-scripts"
OUTPUT_DIR = ROOT.parent / "mq-cloud-20260927" / "osts-candidates-metadata-v2"
WRAPPER_VERSION = "0.2.0"
SCRIPT_NAMES = (
    "read_validate_batch_input",
    "write_mq_comparison",
    "readback_mq_comparison",
)
SCRIPT_PARAMETERS = {
    "read_validate_batch_input": ("logText",),
    "write_mq_comparison": ("validationJson", "caseId"),
    "readback_mq_comparison": ("validationJson", "caseId"),
}


def make_parameter_info(script_name: str) -> str:
    """Return community-example parameter metadata for one main signature."""
    parameter_names = SCRIPT_PARAMETERS[script_name]
    parameter_info = {
        "originalParameterOrder": [
            {"name": name, "index": index}
            for index, name in enumerate(parameter_names)
        ],
        "parameterSchema": {
            "type": "object",
            "required": list(parameter_names),
            "properties": {
                name: {"type": "string"} for name in parameter_names
            },
        },
        "returnSchema": {
            "type": "object",
            "properties": {"result": {"type": "string"}},
        },
    }
    return json.dumps(parameter_info, ensure_ascii=False, separators=(",", ":"))


def build_wrappers() -> dict[str, dict[str, str]]:
    """Build wrapper documents with source TypeScript kept verbatim."""
    wrappers = {}
    for name in SCRIPT_NAMES:
        source = SOURCE_DIR / f"{name}.ts"
        wrappers[f"{name}.osts"] = {
            "version": WRAPPER_VERSION,
            "body": source.read_text(encoding="utf-8"),
            "description": "",
            "parameterInfo": make_parameter_info(name),
            "apiInfo": json.dumps(
                {"variant": "synchronous", "variantVersion": 2},
                separators=(",", ":"),
            ),
        }
    return wrappers


def write_wrappers() -> list[Path]:
    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
    staged: list[tuple[Path, Path]] = []
    try:
        for name, document in build_wrappers().items():
            target = OUTPUT_DIR / name
            with NamedTemporaryFile(
                mode="w",
                encoding="utf-8",
                newline="\n",
                prefix=f".{name}.",
                suffix=".tmp",
                dir=OUTPUT_DIR,
                delete=False,
            ) as temporary:
                temporary.write(json.dumps(document, ensure_ascii=False, indent=2) + "\n")
                temporary.flush()
                staged.append((Path(temporary.name), target))

        for temporary, target in staged:
            temporary.replace(target)
        return [target for _, target in staged]
    finally:
        for temporary, _ in staged:
            temporary.unlink(missing_ok=True)


if __name__ == "__main__":
    for output in write_wrappers():
        print(output)
