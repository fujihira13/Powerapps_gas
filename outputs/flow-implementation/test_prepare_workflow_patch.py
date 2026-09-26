import copy
import importlib.util
import json
import unittest
from pathlib import Path


MODULE_PATH = Path(__file__).with_name("prepare_workflow_patch.py")
SPEC = importlib.util.spec_from_file_location("prepare_workflow_patch", MODULE_PATH)
MODULE = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(MODULE)


class WorkflowPatchPreflightTests(unittest.TestCase):
    def setUp(self):
        candidate, _, _ = MODULE._load_candidate(MODULE.DEFAULT_CANDIDATE)
        self.candidate = candidate
        self.synthetic_live = copy.deepcopy(candidate)
        note = (
            self.synthetic_live["properties"]["definition"]["actions"]
            ["Condition_Start_Ready"]["actions"]["Condition_One_Note"]["actions"]
        )
        note.pop("Compose_LogValidationReason")
        note.pop("Update_case_stop_log_unreadable")
        note["Compose_IsValidLog"]["inputs"] = "@equals(length(outputs('Compose_LogLines')),4)"
        note["Compose_IsValidLog"]["runAfter"] = {"Compose_LogLines": ["Succeeded"]}
        invalid_item = note["Condition_Log_Matches"]["else"]["actions"]
        invalid_item["Update_case_stop_log_invalid"]["inputs"]["parameters"]["item"] = (
            "@addProperty(json('{}'),'cr6cb_processingstatus','停止')"
        )

    def test_only_c02_validation_changes_are_allowed(self):
        changed = MODULE._check_only_c02_differences(self.synthetic_live, self.candidate)
        self.assertGreaterEqual(len(changed), 4)
        self.assertTrue(all(MODULE._is_allowed(path) for path in changed))

    def test_excel_url_change_is_rejected(self):
        live = copy.deepcopy(self.synthetic_live)
        actions = live["properties"]["definition"]["actions"]
        actions["Condition_Start_Ready"]["actions"]["Condition_One_Note"]["actions"][
            "Condition_Log_Matches"]["actions"]["Condition_One_Destination"]["actions"][
            "Scope_Write_And_Verify"]["actions"]["Condition_Readback_Is_Empty"]["else"][
            "actions"]["Condition_Readback_Matches"]["actions"]["Compose_ExcelUrl"]["inputs"] += "-changed"
        with self.assertRaises(MODULE.PreflightError):
            MODULE._check_only_c02_differences(live, self.candidate)

    def test_workflow_record_requires_etag_and_active_state(self):
        record = {
            "workflowid": MODULE.EXPECTED_WORKFLOW_ID,
            "name": MODULE.EXPECTED_WORKFLOW_NAME,
            "statecode": 1,
            "statuscode": 2,
            "clientdata": json.dumps(self.candidate, ensure_ascii=False),
        }
        with self.assertRaises(MODULE.PreflightError):
            MODULE._parse_entity(record)
        record["@odata.etag"] = 'W/"123"'
        _, etag, _ = MODULE._parse_entity(record)
        self.assertEqual(etag, 'W/"123"')
        record["statecode"] = 0
        with self.assertRaises(MODULE.PreflightError):
            MODULE._parse_entity(record)


if __name__ == "__main__":
    unittest.main()
