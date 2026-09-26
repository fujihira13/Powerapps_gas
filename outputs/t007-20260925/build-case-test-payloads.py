"""Prepare fictional Dataverse create requests for the proposed T-007 gate.

This script only writes local JSON. Sending the requests requires the separate
real-API-test authorization recorded in docs/TASKS.md.
"""

import json
from pathlib import Path


OUTPUT = Path(__file__).parent / "case-create-requests"
OUTPUT.mkdir(exist_ok=True)

DATE = "2026-09-25"


def case(label: str, server: str, run: int, *, missing: str | None = None) -> dict:
    value = {
        "cr6cb_caselabel": label,
        "cr6cb_environment": "架空環境T007検証",
        "cr6cb_server": server,
        "cr6cb_runnumber": run,
        "cr6cb_targetdate": DATE,
    }
    if missing:
        del value[missing]
    return value


REQUESTS = {
    "01-valid": case("T007正常01", "架空サーバーT007-A", 1),
    "02-duplicate": case("T007重複02", "架空サーバーT007-A", 1),
    "03-missing-environment": case(
        "T007環境欠落03", "架空サーバーT007-C", 3,
        missing="cr6cb_environment",
    ),
    "04-missing-server": case(
        "T007サーバー欠落04", "架空サーバーT007-D", 4,
        missing="cr6cb_server",
    ),
    "05-missing-run": case(
        "T007実行回欠落05", "架空サーバーT007-E", 5,
        missing="cr6cb_runnumber",
    ),
    "06-missing-date": case(
        "T007日付欠落06", "架空サーバーT007-F", 6,
        missing="cr6cb_targetdate",
    ),
    "07-concurrent-a": case("T007同時07", "架空サーバーT007-G", 7),
    "08-concurrent-b": case("T007同時08", "架空サーバーT007-G", 7),
}

for name, value in REQUESTS.items():
    (OUTPUT / f"{name}.json").write_text(
        json.dumps(value, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )
