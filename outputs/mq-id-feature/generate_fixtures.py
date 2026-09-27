"""Generate deterministic JSON inputs for the MQ ID comparison examples."""

from __future__ import annotations

import json
from pathlib import Path


FEATURE_DIR = Path(__file__).resolve().parent
REPOSITORY_ROOT = FEATURE_DIR.parents[1]
PREVIEW_DIR = REPOSITORY_ROOT / "outputs" / "mq-id-design-preview-20260926"
FIXTURES_DIR = FEATURE_DIR / "fixtures"


def _payload(rows: list[list[str]], log_text: str, case_name: str) -> dict[str, object]:
    return {
        "contract_version": "mq-id-input.v1",
        "case_name": case_name,
        "batch_input": {
            "sheets": [
                {
                    "name": "Batch_Input",
                    "rows": rows,
                }
            ]
        },
        "log_text": log_text,
    }


def generate_fixtures() -> None:
    FIXTURES_DIR.mkdir(parents=True, exist_ok=True)

    # This is the inspected cell projection of batch-input.xlsx:
    # A1 is the title, A2 is the contract header, and A3:A7 contain five IDs.
    sample_rows = [["MQ Batch Input"], ["MQ_ID"]]
    sample_rows.extend([[f"MQ-{number:04d}"] for number in range(1, 6)])
    sample_log = (PREVIEW_DIR / "mock-log.txt").read_text(encoding="utf-8")
    sample = _payload(sample_rows, sample_log, "design-preview-5")

    planned_ids = [f"MQ-{number:04d}" for number in range(1, 101)]
    logged_ids = [value for value in planned_ids if value != "MQ-0050"]
    logged_ids.append("MQ-9001")
    synthetic_rows = [["Synthetic MQ Batch Input"], ["MQ_ID"]]
    synthetic_rows.extend([[value] for value in planned_ids])
    synthetic_log = "\n".join(
        [
            "Synthetic log; fictional data only.",
            *(f"MQ_BOX_ID={value}" for value in logged_ids),
            "ALL SUCCESS",
            "",
        ]
    )
    synthetic = _payload(synthetic_rows, synthetic_log, "synthetic-100")

    for filename, payload in (
        ("design-preview-5.json", sample),
        ("synthetic-100.json", synthetic),
    ):
        (FIXTURES_DIR / filename).write_text(
            json.dumps(payload, ensure_ascii=False, indent=2) + "\n",
            encoding="utf-8",
        )


if __name__ == "__main__":
    generate_fixtures()
