"""Pure JSON-in/JSON-out MQ ID comparison logic."""

from __future__ import annotations

import json
import re
import sys
from collections import Counter
from typing import Any


INPUT_CONTRACT_VERSION = "mq-id-input.v1"
RESULT_CONTRACT_VERSION = "mq-id-result.v1"
EXPECTED_SHEET = "Batch_Input"
EXPECTED_HEADER = "MQ_ID"
LOG_ID_PREFIX = "MQ_BOX_ID="
ID_PATTERN = re.compile(r"MQ-[0-9]{4}", re.ASCII)


def _has_value(value: Any) -> bool:
    """Return whether a cell contains a value, treating empty strings as blank."""
    return value is not None and not (isinstance(value, str) and not value.strip())


def _column_name(index: int) -> str:
    """Convert a zero-based column index to an Excel-style label."""
    label = ""
    number = index + 1
    while number:
        number, remainder = divmod(number - 1, 26)
        label = chr(65 + remainder) + label
    return label


def _unique_in_order(values: list[str]) -> list[str]:
    return list(dict.fromkeys(values))


def compare_payload(payload: Any) -> dict[str, Any]:
    """Validate the versioned flow payload and compare planned with logged IDs.

    The function has no file, network, or service access. ``batch_input`` is a
    worksheet-to-rows JSON projection supplied by the caller; Excel extraction
    and attachment handling belong to the flow adapter.
    """
    errors: list[dict[str, Any]] = []
    invalid_expected_rows: list[dict[str, Any]] = []
    invalid_log_lines: list[dict[str, Any]] = []
    expected_candidates: list[str] = []
    logged_candidates: list[str] = []

    if not isinstance(payload, dict):
        errors.append({"source": "contract", "code": "invalid_payload"})
        payload = {}
    if payload.get("contract_version") != INPUT_CONTRACT_VERSION:
        errors.append(
            {
                "source": "contract",
                "code": "unsupported_contract_version",
                "value": payload.get("contract_version"),
            }
        )

    batch_input = payload.get("batch_input")
    if not isinstance(batch_input, dict):
        errors.append({"source": "workbook", "code": "missing_batch_input"})
        batch_input = {}
    sheets = batch_input.get("sheets")
    if not isinstance(sheets, list) or not sheets:
        errors.append({"source": "workbook", "code": "missing_sheets"})
        sheets = []
    if len(sheets) != 1:
        errors.append(
            {
                "source": "workbook",
                "code": "sheet_count",
                "value": len(sheets),
            }
        )

    for sheet_index, candidate in enumerate(sheets, start=1):
        if not isinstance(candidate, dict):
            errors.append(
                {
                    "source": "workbook",
                    "code": "invalid_sheet",
                    "index": sheet_index,
                }
            )
        elif candidate.get("name") != EXPECTED_SHEET:
            errors.append(
                {
                    "source": "workbook",
                    "code": "unexpected_sheet",
                    "index": sheet_index,
                    "value": candidate.get("name"),
                }
            )

    sheet = sheets[0] if sheets and isinstance(sheets[0], dict) else None

    if sheet is not None:
        rows = sheet.get("rows")
        if not isinstance(rows, list):
            errors.append({"source": "workbook", "code": "invalid_rows"})
            rows = []

        normalized_rows: list[list[Any]] = []
        for row_number, row in enumerate(rows, start=1):
            if isinstance(row, list):
                normalized_rows.append(row)
            else:
                normalized_rows.append([])
                errors.append(
                    {
                        "source": "workbook",
                        "code": "invalid_row",
                        "row": row_number,
                        "value": row,
                    }
                )

        if len(normalized_rows) < 2:
            errors.append({"source": "workbook", "code": "missing_header"})
        else:
            header_row = normalized_rows[1]
            header = header_row[0] if header_row else None
            if header != EXPECTED_HEADER:
                errors.append(
                    {
                        "source": "workbook",
                        "code": "header_mismatch",
                        "row": 2,
                        "expected": EXPECTED_HEADER,
                        "value": header,
                    }
                )

            # No other populated columns are part of the approved workbook shape.
            for row_number, row in enumerate(normalized_rows, start=1):
                for column_index, value in enumerate(row[1:], start=1):
                    if _has_value(value):
                        errors.append(
                            {
                                "source": "workbook",
                                "code": "unexpected_column",
                                "row": row_number,
                                "column": _column_name(column_index),
                                "value": value,
                            }
                        )

            # Trailing empty rows are harmless; a blank row inside the data range
            # is an invalid record because every planned ID must occupy one row.
            last_populated_index = 1
            for index in range(2, len(normalized_rows)):
                if any(_has_value(value) for value in normalized_rows[index]):
                    last_populated_index = index

            for index in range(2, last_populated_index + 1):
                row = normalized_rows[index]
                value = row[0] if row else None
                row_number = index + 1
                if not _has_value(value):
                    invalid_expected_rows.append({"row": row_number, "value": value})
                    errors.append(
                        {
                            "source": "workbook",
                            "code": "blank_expected_id",
                            "row": row_number,
                        }
                    )
                    continue
                if not isinstance(value, str):
                    invalid_expected_rows.append({"row": row_number, "value": value})
                    errors.append(
                        {
                            "source": "workbook",
                            "code": "invalid_expected_id",
                            "row": row_number,
                            "value": value,
                        }
                    )
                    continue

                normalized = value.strip()
                if ID_PATTERN.fullmatch(normalized) is None:
                    invalid_expected_rows.append({"row": row_number, "value": normalized})
                    errors.append(
                        {
                            "source": "workbook",
                            "code": "invalid_expected_id",
                            "row": row_number,
                            "value": normalized,
                        }
                    )
                    continue
                expected_candidates.append(normalized)

            if not expected_candidates:
                errors.append({"source": "workbook", "code": "no_expected_ids"})

    log_text = payload.get("log_text")
    if not isinstance(log_text, str):
        errors.append({"source": "log", "code": "invalid_log_text"})
        log_text = ""

    log_lines = log_text.splitlines()
    for line_number, line in enumerate(log_lines, start=1):
        if not line.startswith(LOG_ID_PREFIX):
            continue
        value = line[len(LOG_ID_PREFIX) :].strip()
        if ID_PATTERN.fullmatch(value) is None:
            invalid_log_lines.append({"line": line_number, "value": value})
            errors.append(
                {
                    "source": "log",
                    "code": "invalid_log_id",
                    "line": line_number,
                    "value": value,
                }
            )
            continue
        logged_candidates.append(value)

    duplicate_expected = [
        value for value, count in Counter(expected_candidates).items() if count > 1
    ]
    duplicate_logged = [
        value for value, count in Counter(logged_candidates).items() if count > 1
    ]
    for value in duplicate_expected:
        errors.append({"source": "workbook", "code": "duplicate_expected_id", "value": value})
    for value in duplicate_logged:
        errors.append({"source": "log", "code": "duplicate_logged_id", "value": value})

    nonempty_lines = [line for line in log_lines if line.strip()]
    end_marker_present = bool(nonempty_lines and nonempty_lines[-1] == "ALL SUCCESS")

    expected_ids = _unique_in_order(expected_candidates)
    logged_ids = _unique_in_order(logged_candidates)
    comparison_available = not errors
    if comparison_available:
        expected_set = set(expected_ids)
        logged_set = set(logged_ids)
        missing_ids: list[str] | None = [
            value for value in expected_ids if value not in logged_set
        ]
        log_only_ids: list[str] | None = [
            value for value in logged_ids if value not in expected_set
        ]
        counts = {
            "expected": len(expected_ids),
            "logged": len(logged_ids),
            "missing": len(missing_ids),
            "log_only": len(log_only_ids),
        }
    else:
        missing_ids = None
        log_only_ids = None
        counts = {
            "expected": len(expected_ids),
            "logged": len(logged_ids),
            "missing": None,
            "log_only": None,
        }

    if errors:
        status = "input_error"
        stop_reason: str | None = "input_error"
        stop_processing = True
        status_label = "要確認"
    elif not end_marker_present:
        status = "log_incomplete"
        stop_reason = "missing_end_marker"
        stop_processing = True
        status_label = "要確認"
    else:
        status = "comparison_ready"
        stop_reason = None
        stop_processing = False
        status_label = "要確認" if missing_ids or log_only_ids else "比較完了"

    return {
        "contract_version": RESULT_CONTRACT_VERSION,
        "status": status,
        "comparison_available": comparison_available,
        "end_marker_present": end_marker_present,
        "expected_ids": expected_ids,
        "logged_ids": logged_ids,
        "missing_ids": missing_ids,
        "log_only_ids": log_only_ids,
        "counts": counts,
        "duplicate_ids": {
            "expected": duplicate_expected,
            "logged": duplicate_logged,
        },
        "invalid": {
            "expected_rows": invalid_expected_rows,
            "log_lines": invalid_log_lines,
        },
        "errors": errors,
        "presentation": {
            "status_label": status_label,
            "stop_processing": stop_processing,
            "stop_reason": stop_reason,
            "human_decision_required": True,
        },
    }


def main() -> None:
    """Read one input contract from stdin and write one result contract to stdout."""
    try:
        payload = json.load(sys.stdin)
    except (json.JSONDecodeError, UnicodeDecodeError) as error:
        result = {
            "contract_version": RESULT_CONTRACT_VERSION,
            "status": "input_error",
            "comparison_available": False,
            "end_marker_present": False,
            "expected_ids": [],
            "logged_ids": [],
            "missing_ids": None,
            "log_only_ids": None,
            "counts": {"expected": 0, "logged": 0, "missing": None, "log_only": None},
            "duplicate_ids": {"expected": [], "logged": []},
            "invalid": {"expected_rows": [], "log_lines": []},
            "errors": [{"source": "contract", "code": "invalid_json", "detail": str(error)}],
            "presentation": {
                "status_label": "要確認",
                "stop_processing": True,
                "stop_reason": "input_error",
                "human_decision_required": True,
            },
        }
    else:
        result = compare_payload(payload)
    json.dump(result, sys.stdout, ensure_ascii=False, indent=2)
    sys.stdout.write("\n")


if __name__ == "__main__":
    main()
