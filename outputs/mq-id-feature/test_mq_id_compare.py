import json
from pathlib import Path
import unittest

from mq_id_compare import compare_payload

FIXTURES_DIR = Path(__file__).resolve().parent / "fixtures"


def load_fixture(name):
    return json.loads((FIXTURES_DIR / name).read_text(encoding="utf-8"))


def make_payload(expected_ids, log_text, *, sheet_name="Batch_Input", extra_columns=None):
    rows = [["MQ Batch Input"], ["MQ_ID"]]
    for index, value in enumerate(expected_ids):
        row = [value]
        if extra_columns and index in extra_columns:
            row.extend(extra_columns[index])
        rows.append(row)
    return {
        "contract_version": "mq-id-input.v1",
        "batch_input": {"sheets": [{"name": sheet_name, "rows": rows}]},
        "log_text": log_text,
    }


class ComparePayloadTests(unittest.TestCase):
    def test_five_id_design_sample_reports_only_the_unrecorded_id(self):
        result = compare_payload(load_fixture("design-preview-5.json"))

        self.assertEqual(result["status"], "comparison_ready")
        self.assertTrue(result["end_marker_present"])
        self.assertEqual(result["expected_ids"], [f"MQ-{number:04d}" for number in range(1, 6)])
        self.assertEqual(result["logged_ids"], ["MQ-0001", "MQ-0002", "MQ-0004", "MQ-0005"])
        self.assertEqual(result["missing_ids"], ["MQ-0003"])
        self.assertEqual(result["log_only_ids"], [])
        self.assertEqual(result["presentation"]["status_label"], "要確認")
        self.assertTrue(result["presentation"]["human_decision_required"])
        json.dumps(result, ensure_ascii=False)

    def test_exact_match_is_comparison_only_and_still_requires_human_decision(self):
        result = compare_payload(
            make_payload(
                ["MQ-0010", "MQ-0011"],
                "MQ_BOX_ID=MQ-0010\nMQ_BOX_ID=MQ-0011\nALL SUCCESS\n",
            )
        )

        self.assertEqual(result["status"], "comparison_ready")
        self.assertEqual(result["missing_ids"], [])
        self.assertEqual(result["log_only_ids"], [])
        self.assertTrue(result["presentation"]["human_decision_required"])
        self.assertFalse(result["presentation"]["stop_processing"])

    def test_missing_end_marker_stops_with_confirmation_without_calling_ids_failed(self):
        result = compare_payload(
            make_payload(
                ["MQ-0001", "MQ-0002"],
                "MQ_BOX_ID=MQ-0001\nINFO batch output ended unexpectedly",
            )
        )

        self.assertEqual(result["status"], "log_incomplete")
        self.assertFalse(result["end_marker_present"])
        self.assertEqual(result["missing_ids"], ["MQ-0002"])
        self.assertTrue(result["presentation"]["stop_processing"])
        self.assertEqual(result["presentation"]["status_label"], "要確認")
        self.assertEqual(result["presentation"]["stop_reason"], "missing_end_marker")

    def test_end_marker_before_later_log_content_is_not_terminal(self):
        result = compare_payload(
            make_payload(
                ["MQ-0001"],
                "MQ_BOX_ID=MQ-0001\nALL SUCCESS\nINFO appended after the marker",
            )
        )

        self.assertEqual(result["status"], "log_incomplete")
        self.assertFalse(result["end_marker_present"])
        self.assertEqual(result["missing_ids"], [])
        self.assertTrue(result["presentation"]["stop_processing"])

    def test_end_marker_text_must_match_exactly(self):
        result = compare_payload(
            make_payload(["MQ-0001"], "MQ_BOX_ID=MQ-0001\nALL SUCCESS ")
        )

        self.assertEqual(result["status"], "log_incomplete")
        self.assertFalse(result["end_marker_present"])

    def test_duplicate_ids_in_both_inputs_stop_comparison(self):
        result = compare_payload(
            make_payload(
                ["MQ-0001", "MQ-0001"],
                "MQ_BOX_ID=MQ-0001\nMQ_BOX_ID=MQ-0001\nALL SUCCESS",
            )
        )

        self.assertEqual(result["status"], "input_error")
        self.assertIsNone(result["missing_ids"])
        self.assertIsNone(result["log_only_ids"])
        self.assertEqual(result["duplicate_ids"], {"expected": ["MQ-0001"], "logged": ["MQ-0001"]})
        self.assertTrue(result["presentation"]["stop_processing"])
        self.assertEqual(result["presentation"]["status_label"], "要確認")

    def test_invalid_ids_are_reported_with_source_locations_and_stop_comparison(self):
        result = compare_payload(
            make_payload(
                ["MQ-ABC1"],
                "MQ_BOX_ID=MQ-12345\nALL SUCCESS",
            )
        )

        self.assertEqual(result["status"], "input_error")
        self.assertIsNone(result["missing_ids"])
        self.assertEqual(result["invalid"]["expected_rows"], [{"row": 3, "value": "MQ-ABC1"}])
        self.assertEqual(result["invalid"]["log_lines"], [{"line": 1, "value": "MQ-12345"}])
        self.assertTrue(result["presentation"]["stop_processing"])

    def test_log_only_id_is_exposed_separately_for_review(self):
        result = compare_payload(
            make_payload(
                ["MQ-0001"],
                "MQ_BOX_ID=MQ-0001\nMQ_BOX_ID=MQ-0002\nALL SUCCESS",
            )
        )

        self.assertEqual(result["missing_ids"], [])
        self.assertEqual(result["log_only_ids"], ["MQ-0002"])
        self.assertTrue(result["presentation"]["human_decision_required"])

    def test_wrong_sheet_and_nonempty_extra_column_are_input_errors(self):
        wrong_sheet = compare_payload(
            make_payload(["MQ-0001"], "ALL SUCCESS", sheet_name="Input")
        )
        extra_column = compare_payload(
            make_payload(
                ["MQ-0001"],
                "ALL SUCCESS",
                extra_columns={0: ["unexpected"]},
            )
        )

        self.assertEqual(wrong_sheet["status"], "input_error")
        self.assertEqual(extra_column["status"], "input_error")
        self.assertTrue(any(error["code"] == "unexpected_sheet" for error in wrong_sheet["errors"]))
        self.assertTrue(any(error["code"] == "unexpected_column" for error in extra_column["errors"]))

    def test_header_must_be_in_cell_a2_with_the_exact_name(self):
        payload = make_payload(["MQ-0001"], "MQ_BOX_ID=MQ-0001\nALL SUCCESS")
        payload["batch_input"]["sheets"][0]["rows"][1][0] = "MQ ID"
        result = compare_payload(payload)

        self.assertEqual(result["status"], "input_error")
        self.assertTrue(any(error["code"] == "header_mismatch" for error in result["errors"]))
        self.assertIsNone(result["missing_ids"])

    def test_additional_worksheet_is_reported_and_stops_comparison(self):
        payload = make_payload(["MQ-0001"], "ALL SUCCESS")
        payload["batch_input"]["sheets"].append(
            {"name": "Notes", "rows": [["not part of the input"]]}
        )
        result = compare_payload(payload)

        self.assertEqual(result["status"], "input_error")
        self.assertIsNone(result["missing_ids"])
        self.assertTrue(any(error["code"] == "sheet_count" for error in result["errors"]))

    def test_missing_planned_ids_is_an_input_error(self):
        result = compare_payload(
            {
                "contract_version": "mq-id-input.v1",
                "batch_input": {
                    "sheets": [{"name": "Batch_Input", "rows": [["Title"], ["MQ_ID"]]}]
                },
                "log_text": "ALL SUCCESS",
            }
        )

        self.assertEqual(result["status"], "input_error")
        self.assertIsNone(result["missing_ids"])
        self.assertTrue(any(error["code"] == "no_expected_ids" for error in result["errors"]))

    def test_only_exact_start_of_line_id_records_are_parsed_and_ids_are_trimmed(self):
        result = compare_payload(
            make_payload(
                [" MQ-0001 "],
                "INFO MQ_BOX_ID=MQ-0002\nMQ_BOX_ID= MQ-0001 \nMQ_BOX_STATUS=READY\nALL SUCCESS\n",
            )
        )

        self.assertEqual(result["status"], "comparison_ready")
        self.assertEqual(result["logged_ids"], ["MQ-0001"])
        self.assertEqual(result["missing_ids"], [])

    def test_hundred_id_case_keeps_one_missing_and_one_log_only_id_distinct(self):
        result = compare_payload(load_fixture("synthetic-100.json"))

        self.assertEqual(result["status"], "comparison_ready")
        self.assertEqual(result["counts"], {"expected": 100, "logged": 100, "missing": 1, "log_only": 1})
        self.assertEqual(result["missing_ids"], ["MQ-0050"])
        self.assertEqual(result["log_only_ids"], ["MQ-9001"])


if __name__ == "__main__":
    unittest.main()
