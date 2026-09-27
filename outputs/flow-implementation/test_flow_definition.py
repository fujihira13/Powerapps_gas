import copy
import json
import unittest
from pathlib import Path

from build_flow_definition import (
    build_api_request,
    build_clientdata,
    build_excelurl_candidate,
    build_workflow_body,
    validate_clientdata,
    validate_excelurl_candidate,
)


def find_action(actions, expected_name):
    for name, action in actions.items():
        if name == expected_name:
            return action
        nested = action.get("actions", {})
        if isinstance(nested, dict):
            found = find_action(nested, expected_name)
            if found is not None:
                return found
        else_actions = action.get("else", {}).get("actions", {})
        if isinstance(else_actions, dict):
            found = find_action(else_actions, expected_name)
            if found is not None:
                return found
    return None


def walk_actions(actions):
    for name, action in actions.items():
        yield name, action
        nested = action.get("actions", {})
        if isinstance(nested, dict):
            yield from walk_actions(nested)
        else_actions = action.get("else", {}).get("actions", {})
        if isinstance(else_actions, dict):
            yield from walk_actions(else_actions)


def walk_action_paths(actions, path=()):
    for name, action in actions.items():
        current = path + (name,)
        yield current, action
        nested = action.get("actions", {})
        if isinstance(nested, dict):
            yield from walk_action_paths(nested, current)
        else_actions = action.get("else", {}).get("actions", {})
        if isinstance(else_actions, dict):
            yield from walk_action_paths(else_actions, current)


class FlowDefinitionTests(unittest.TestCase):
    def test_mq_candidate_keeps_legacy_case_id_single_note_and_evidence_flow(self):
        from build_flow_definition import build_mq_candidate, validate_mq_candidate

        candidate = build_mq_candidate()
        actions = candidate["properties"]["definition"]["actions"]
        trigger = candidate["properties"]["definition"]["triggers"]["manual"]
        self.assertEqual(trigger["inputs"]["schema"]["required"], ["text"])
        self.assertEqual(trigger["inputs"]["schema"]["properties"]["text"]["title"], "caseId")
        self.assertIn("Condition_Two_Attachments", json.dumps(actions))
        self.assertNotIn("Condition_MQ_Mode", json.dumps(actions))
        legacy_candidate = build_excelurl_candidate()
        self.assertIn("Condition_One_Note", json.dumps(legacy_candidate))
        self.assertIn("table\": \"Evidence\"", json.dumps(actions))
        legacy_branch = find_action(actions, "Condition_One_Note")["actions"]
        legacy_branch_before_mq = find_action(
            legacy_candidate["properties"]["definition"]["actions"], "Condition_One_Note"
        )["actions"]
        self.assertEqual(legacy_branch, legacy_branch_before_mq)
        self.assertNotIn("Run_MQ_Input_Validation", json.dumps(legacy_branch))
        self.assertIn("Replace_template_row", json.dumps(legacy_branch))
        self.assertEqual(validate_mq_candidate(candidate), [])

    def test_every_mq_branch_expression_resolves_to_mq_or_shared_ancestor_actions(self):
        from build_flow_definition import build_mq_candidate, validate_mq_candidate

        candidate = build_mq_candidate()
        actions = candidate["properties"]["definition"]["actions"]
        destination = find_action(actions, "Condition_One_Destination_MQ")
        destination_expression = json.dumps(destination["expression"])
        self.assertIn("Filter_active_destinations_MQ", destination_expression)
        self.assertNotIn("Filter_active_destinations'", destination_expression)
        condition_name = "Condition_Readback_Matches_MQ"
        expression = json.dumps(find_action(actions, condition_name)["expression"])
        with self.subTest(condition=condition_name):
            self.assertIn("Compose_LogFileName_MQ", expression)
            self.assertIn("Compose_LogText_MQ", expression)
            self.assertNotIn("Compose_LogFileName'", expression)
            self.assertNotIn("Compose_LogText'", expression)
        self.assertEqual(validate_mq_candidate(candidate), [])

        # The validator scans nested MQ expressions, not just destination gates.
        writer = find_action(actions, "Run_MQ_Result_Write_MQ")
        writer["inputs"]["parameters"]["drive"] = "@outputs('Missing_MQ_Drive_Action')"
        errors = validate_mq_candidate(candidate)
        self.assertTrue(
            any(
                "unavailable or non-MQ actions" in error
                and "Missing_MQ_Drive_Action" in error
                for error in errors
            ),
            errors,
        )

    def test_mq_candidate_validates_one_txt_and_one_xlsx_then_reads_batch_workbook(self):
        from build_flow_definition import build_mq_candidate

        actions = build_mq_candidate()["properties"]["definition"]["actions"]
        role_gate = find_action(actions, "Condition_MQ_Attachment_Roles")
        log_filter = find_action(actions, "Filter_MQ_Logs")
        book_filter = find_action(actions, "Filter_MQ_Books")
        stage = find_action(actions, "Stage_MQ_Input")
        reader = find_action(actions, "Run_MQ_Input_Validation")
        self.assertIsNotNone(role_gate)
        serialized = json.dumps(actions)
        self.assertIn("equals(length(body('Filter_MQ_Logs')),1)", json.dumps(role_gate))
        self.assertIn("equals(length(body('Filter_MQ_Books')),1)", json.dumps(role_gate))
        self.assertNotIn("body('Filter_MQ_Logs')?['value']", serialized)
        self.assertNotIn("body('Filter_MQ_Books')?['value']", serialized)
        self.assertIn(".txt", log_filter["inputs"]["where"])
        self.assertIn(".xlsx", book_filter["inputs"]["where"])
        self.assertIn("first(body('Filter_MQ_Logs'))?['documentbody']", serialized)
        self.assertIn("first(body('Filter_MQ_Logs'))?['filename']", serialized)
        self.assertEqual(stage["inputs"]["host"]["operationId"], "CreateFile")
        self.assertIn("first(body('Filter_MQ_Books'))?['documentbody']", json.dumps(stage))
        self.assertEqual(stage["inputs"]["retryPolicy"], {"type": "none"})
        self.assertEqual(reader["inputs"]["host"]["operationId"], "RunScriptProd")
        self.assertIn("__SELECT_MQ_BATCH_READER_SCRIPT__", reader["inputs"]["parameters"]["scriptId"])
        validation_gate = find_action(actions, "Condition_MQ_Batch_Valid")
        gate_expression = json.dumps(validation_gate["expression"])
        self.assertIn("mq-id-result.v1", gate_expression)
        self.assertIn("comparison_available", gate_expression)
        self.assertIn("comparison_ready", gate_expression)
        self.assertNotIn("stop_processing", gate_expression)
        incomplete_gate = find_action(actions, "Condition_MQ_Log_Incomplete")
        self.assertIn("log_incomplete", json.dumps(incomplete_gate["expression"]))
        self.assertIn("comparison_available", json.dumps(incomplete_gate["expression"]))
        self.assertIn("Update_case_mq_incomplete_diagnostic", incomplete_gate["actions"])
        self.assertIn("Update_case_stop_mq_input_invalid", incomplete_gate["else"]["actions"])
        self.assertIn("result_text", find_action(actions, "Update_case_mq_incomplete_diagnostic")["inputs"]["parameters"]["item"])

    def test_mq_candidate_inherits_exact_three_script_ids_from_saved_flow_get(self):
        from build_flow_definition import (
            MQ_SCRIPT_ACTION_NAMES,
            build_mq_candidate,
            load_mq_script_ids,
            validate_mq_candidate,
        )

        source_path = (
            Path(__file__).resolve().parents[2]
            / "outputs"
            / "runless-migration-20260927"
            / "flow-before.json"
        )
        source = json.loads(source_path.read_text(encoding="utf-8-sig"))
        live_clientdata = json.loads(source["clientdata"])
        live_actions = live_clientdata["properties"]["definition"]["actions"]
        expected_ids = {
            role: find_action(live_actions, action_name)["inputs"]["parameters"]["scriptId"]
            for role, action_name in MQ_SCRIPT_ACTION_NAMES.items()
        }
        selected_ids = load_mq_script_ids(source_path)
        self.assertEqual(selected_ids, expected_ids)

        candidate = build_mq_candidate(script_ids=selected_ids)
        candidate_actions = candidate["properties"]["definition"]["actions"]
        actual_ids = {
            role: find_action(candidate_actions, action_name)["inputs"]["parameters"]["scriptId"]
            for role, action_name in MQ_SCRIPT_ACTION_NAMES.items()
        }
        serialized = json.dumps(candidate, ensure_ascii=False)
        self.assertEqual(actual_ids, expected_ids)
        self.assertEqual(len(actual_ids), 3)
        self.assertNotIn("__SELECT_MQ_", serialized)
        self.assertEqual(
            validate_mq_candidate(candidate, expected_script_ids=selected_ids), []
        )

    def test_mq_result_write_and_independent_readback_gate_success(self):
        from build_flow_definition import build_mq_candidate

        actions = build_mq_candidate()["properties"]["definition"]["actions"]
        scope = find_action(actions, "Scope_Write_And_Verify_MQ")
        self.assertEqual(scope["type"], "Scope")
        scope_actions = scope["actions"]
        self.assertIn("Replace_template_row_MQ", scope_actions)
        self.assertIn("Run_MQ_Result_Write_MQ", scope_actions)
        self.assertIn("Run_MQ_Result_Readback_MQ", scope_actions)
        self.assertIn("Read_back_evidence_MQ", scope_actions)
        self.assertEqual(
            scope_actions["Run_MQ_Result_Write_MQ"]["runAfter"],
            {"Replace_template_row_MQ": ["Succeeded"]},
        )
        self.assertEqual(
            scope_actions["Run_MQ_Result_Readback_MQ"]["runAfter"],
            {"Compose_MQ_Result_Write_Gate_MQ": ["Succeeded"]},
        )
        self.assertEqual(
            find_action(actions, "Update_case_postcopy_unknown_MQ")["runAfter"],
            {"Scope_Write_And_Verify_MQ": ["Failed", "TimedOut"]},
        )
        readback_match = find_action(actions, "Condition_Readback_Matches_MQ")
        self.assertIn("Compose_MQ_Result_Readback_MQ", json.dumps(readback_match))

        expected_fields = (
            "cr6cb_mqterminalstatus",
            "cr6cb_mqexpectedcount",
            "cr6cb_mqloggedcount",
            "cr6cb_mqmissingcount",
            "cr6cb_mqmissingids",
            "cr6cb_mqcomparisonstatus",
            "cr6cb_mqresulttext",
        )
        success_name = "Update_case_success_MQ"
        item = find_action(actions, success_name)["inputs"]["parameters"]["item"]
        for field in expected_fields:
            self.assertIn(field, item)
        field_writers = []
        for action_name, action in walk_actions(actions):
            action_inputs = action.get("inputs", {})
            if not isinstance(action_inputs, dict) or action_inputs.get("host", {}).get("operationId") != "UpdateOnlyRecord":
                continue
            item = action_inputs.get("parameters", {}).get("item", "")
            if any(field in item for field in expected_fields):
                field_writers.append(action_name)
        self.assertEqual(
            set(field_writers),
            {"Update_case_success_MQ", "Update_case_mq_incomplete_diagnostic"},
        )
        self.assertIn("ScriptParameters/caseId", scope_actions["Run_MQ_Result_Write_MQ"]["inputs"]["parameters"])
        self.assertIn("ScriptParameters/caseId", scope_actions["Run_MQ_Result_Readback_MQ"]["inputs"]["parameters"])

    def test_mq_writer_result_must_be_ok_before_readback_and_generic_unknown_preserves_reason(self):
        from build_flow_definition import build_mq_candidate, validate_mq_candidate

        candidate = build_mq_candidate()
        actions = candidate["properties"]["definition"]["actions"]
        scope_actions = find_action(actions, "Scope_Write_And_Verify_MQ")["actions"]
        writer_result = scope_actions["Compose_MQ_Result_Write_MQ"]
        writer_gate = scope_actions["Compose_MQ_Result_Write_Gate_MQ"]
        result_readback = scope_actions["Run_MQ_Result_Readback_MQ"]
        self.assertEqual(
            writer_result["runAfter"],
            {"Run_MQ_Result_Write_MQ": ["Succeeded"]},
        )
        self.assertIn("body('Run_MQ_Result_Write_MQ')?['result']", writer_result["inputs"])
        self.assertIn("outputs('Compose_MQ_Result_Write_MQ')?['ok']", writer_gate["inputs"])
        self.assertIn("div(1,if(", writer_gate["inputs"])
        self.assertNotIn("div(1,0)", writer_gate["inputs"])
        self.assertEqual(
            writer_gate["runAfter"],
            {"Compose_MQ_Result_Write_MQ": ["Succeeded"]},
        )
        self.assertEqual(
            result_readback["runAfter"],
            {"Compose_MQ_Result_Write_Gate_MQ": ["Succeeded"]},
        )

        postcopy_unknown = find_action(actions, "Update_case_postcopy_unknown_MQ")
        postcopy_item = postcopy_unknown["inputs"]["parameters"]["item"]
        self.assertIn("outputs('Compose_MQ_Result_Write_MQ')?['error']", postcopy_item)
        self.assertIn("actions('Compose_MQ_Result_Write_MQ')?['status']", postcopy_item)
        validation_unknown = find_action(actions, "Update_case_mq_validation_condition_unknown")
        validation_item = validation_unknown["inputs"]["parameters"]["item"]
        self.assertNotIn("cr6cb_failurereason", validation_item)
        self.assertIn("cr6cb_processingstatus','結果不明'", validation_item)
        self.assertNotIn("cr6cb_excelcheckstatus", validation_item)
        self.assertEqual(validate_mq_candidate(candidate), [])

        writer_gate["inputs"] = "@true"
        self.assertTrue(
            any("writer result must gate readback" in error for error in validate_mq_candidate(candidate))
        )

        candidate = build_mq_candidate()
        validation_unknown = find_action(
            candidate["properties"]["definition"]["actions"],
            "Update_case_mq_validation_condition_unknown",
        )
        validation_unknown["inputs"]["parameters"]["item"] += "cr6cb_failurereason"
        self.assertTrue(
            any("broad MQ unknown fallback must preserve an existing failure reason" in error
                for error in validate_mq_candidate(candidate))
        )

        candidate = build_mq_candidate()
        validation_unknown = find_action(
            candidate["properties"]["definition"]["actions"],
            "Update_case_mq_validation_condition_unknown",
        )
        validation_unknown["inputs"]["parameters"]["item"] += "cr6cb_excelcheckstatus"
        self.assertTrue(
            any("broad MQ unknown fallback must update processing status only" in error
                for error in validate_mq_candidate(candidate))
        )

    def test_mq_readback_retry_is_flattened_without_losing_unknown_handlers(self):
        from build_flow_definition import build_mq_candidate, validate_mq_candidate

        candidate = build_mq_candidate()
        actions = candidate["properties"]["definition"]["actions"]
        scope = find_action(actions, "Scope_Write_And_Verify_MQ")
        scope_actions = scope["actions"]
        self.assertNotIn("Condition_Readback_Is_Empty_MQ", scope_actions)
        self.assertNotIn("Condition_Readback_Matches_MQ", scope_actions)
        self.assertNotIn("Condition_Readback_Retry_Matches_MQ", scope_actions)
        self.assertEqual(
            scope_actions["Read_back_evidence_MQ"]["runAfter"],
            {"Delay_before_readback_MQ": ["Succeeded"]},
        )
        self.assertEqual(
            scope_actions["Delay_before_readback_retry_MQ"]["runAfter"],
            {"Read_back_evidence_MQ": ["Succeeded"]},
        )
        self.assertEqual(
            scope_actions["Read_back_evidence_retry_MQ"]["runAfter"],
            {"Delay_before_readback_retry_MQ": ["Succeeded"]},
        )
        readback_gate = find_action(actions, "Condition_Readback_Matches_MQ")
        self.assertEqual(
            readback_gate["runAfter"],
            {"Scope_Write_And_Verify_MQ": ["Succeeded"]},
        )
        match_expression = readback_gate["expression"]["equals"][0]
        self.assertIn(
            "or(equals(length(body('Read_back_evidence_MQ')?['value']),0),and(",
            match_expression,
        )
        self.assertIn(
            "length(body('Read_back_evidence_retry_MQ')?['value']),1",
            match_expression,
        )
        self.assertIn("Compose_MQ_Result_Readback_MQ", match_expression)
        self.assertIn("Compose_LogFileName_MQ", match_expression)
        self.assertIn("Compose_LogText_MQ", match_expression)
        self.assertIn("Update_case_success_MQ", readback_gate["actions"])
        self.assertIn(
            "Update_case_readback_unknown_MQ",
            readback_gate["else"]["actions"],
        )

        validation_gate = find_action(actions, "Condition_MQ_Batch_Valid")
        self.assertEqual(
            validation_gate["actions"]["Update_case_readback_condition_unknown_MQ"]["runAfter"],
            {"Condition_Readback_Matches_MQ": ["Failed", "TimedOut"]},
        )
        self.assertEqual(
            find_action(actions, "Update_case_postcopy_unknown_MQ")["runAfter"],
            {"Scope_Write_And_Verify_MQ": ["Failed", "TimedOut"]},
        )

        mq_paths = [
            path
            for path, _ in walk_action_paths(actions)
            if "Condition_Two_Attachments" in path
        ]
        self.assertLessEqual(max(len(path) - 1 for path in mq_paths), 8)
        for target in (
            "Delay_before_readback_retry_MQ",
            "Read_back_evidence_retry_MQ",
            "Condition_Readback_Matches_MQ",
        ):
            path = next(path for path in mq_paths if path[-1] == target)
            with self.subTest(action=target):
                expected_depth = 7 if target == "Condition_Readback_Matches_MQ" else 8
                self.assertEqual(len(path) - 1, expected_depth)
        self.assertEqual(validate_mq_candidate(candidate), [])

    def test_log_incomplete_saves_only_guarded_provisional_columns_without_report_or_link(self):
        from build_flow_definition import build_mq_candidate, validate_mq_candidate

        actions = build_mq_candidate()["properties"]["definition"]["actions"]
        batch_gate = find_action(actions, "Condition_MQ_Batch_Valid")
        incomplete_gate = find_action(actions, "Condition_MQ_Log_Incomplete")
        diagnostic = find_action(actions, "Update_case_mq_incomplete_diagnostic")
        item = diagnostic["inputs"]["parameters"]["item"]
        expected_fields = (
            "cr6cb_mqterminalstatus",
            "cr6cb_mqexpectedcount",
            "cr6cb_mqloggedcount",
            "cr6cb_mqmissingcount",
            "cr6cb_mqmissingids",
            "cr6cb_mqcomparisonstatus",
            "cr6cb_mqresulttext",
        )

        self.assertIn("Condition_MQ_Log_Incomplete", batch_gate["else"]["actions"])
        self.assertIn("end_marker_present", json.dumps(incomplete_gate["expression"]))
        self.assertIn("'なし'", item)
        self.assertIn("'要確認'", item)
        self.assertIn("cr6cb_processingstatus','停止'", item)
        for field in expected_fields:
            with self.subTest(field=field):
                self.assertIn(field, item)
        branch = json.dumps(incomplete_gate["actions"], ensure_ascii=False)
        self.assertNotIn("Copy_template_MQ", branch)
        self.assertNotIn("Run_MQ_Result_Write_MQ", branch)
        self.assertNotIn("cr6cb_excelurl", branch)
        self.assertEqual(diagnostic["inputs"]["retryPolicy"], {"type": "none"})
        self.assertEqual(validate_mq_candidate(build_mq_candidate()), [])

    def test_mq_scripts_enforce_contract_and_preserve_result_workbook_evidence(self):
        scripts = Path(__file__).parent / "office-scripts"
        reader = (scripts / "read_validate_batch_input.ts").read_text(encoding="utf-8")
        writer = (scripts / "write_mq_comparison.ts").read_text(encoding="utf-8")
        readback = (scripts / "readback_mq_comparison.ts").read_text(encoding="utf-8")
        for expected in ("Batch_Input", "MQ_ID", "MQ_BOX_ID=", "ALL SUCCESS", "MQ-[0-9]{4}"):
            self.assertIn(expected, reader)
        self.assertIn("MQ_Comparison", writer)
        self.assertIn("MQ_Comparison", readback)
        self.assertIn('workbook.getWorksheet("証跡")', writer)
        self.assertIn('workbook.getWorksheet("証跡")', readback)
        self.assertIn('workbook.getWorksheet("MQ_Comparison")', writer)
        self.assertIn('workbook.getWorksheet("MQ_Comparison")', readback)
        self.assertNotIn('getName() === "Evidence"', writer)
        self.assertNotIn('getName() === "Evidence"', readback)
        self.assertNotIn("worksheets.find(", readback)
        self.assertNotIn("worksheets.some(", writer)
        self.assertNotIn("worksheets.some(", readback)
        self.assertNotIn("getTables().filter(", readback)
        self.assertIn('reportSheet.getTable("MQ_ComparisonTable")', readback)
        self.assertIn("証跡 worksheet is missing", writer)
        self.assertIn("証跡 or MQ_Comparison worksheet is missing", readback)
        self.assertIn('table.setName("MQ_ComparisonTable")', writer)
        self.assertIn("`${mqId}\\t${rowResult(input, mqId)}`", writer)
        self.assertIn("`${mqId}\\t${rowResult(input, mqId)}`", readback)
        self.assertIn('value.status !== "comparison_ready"', writer)
        self.assertIn('value.status !== "comparison_ready"', readback)
        self.assertIn("ALL SUCCESSはログ終端表示であり、MQ更新成功を証明しません。", writer)
        self.assertIn("ALL SUCCESSはログ終端表示であり、MQ更新成功を証明しません。", readback)
        self.assertIn("予定外ID・要確認", writer)
        self.assertIn("予定外ID・要確認", readback)
        for script in (writer, readback):
            self.assertIn('"記録あり（ログ不完全・要確認）"', script)
            self.assertIn('"ログ未記録（ログ不完全）・要確認"', script)
        self.assertIn('"記録あり"', reader)
        self.assertIn('"ログ未記録（ログ不完全）・要確認"', reader)

    def test_mq_validator_rejects_missing_role_gate_or_result_readback_gate(self):
        from build_flow_definition import build_mq_candidate, validate_mq_candidate

        candidate = build_mq_candidate()
        actions = candidate["properties"]["definition"]["actions"]
        role_gate = find_action(actions, "Condition_MQ_Attachment_Roles")
        role_gate["expression"] = {"equals": ["@equals(length(body('Filter_MQ_Logs')?['value']),1)", True]}
        self.assertTrue(any("attachment roles" in error.lower() for error in validate_mq_candidate(candidate)))

        candidate = build_mq_candidate()
        actions = candidate["properties"]["definition"]["actions"]
        readback = find_action(actions, "Condition_Readback_Matches_MQ")
        readback["expression"] = {"equals": ["@true", True]}
        self.assertTrue(
            any("MQ success must require" in error for error in validate_mq_candidate(candidate))
        )

        candidate = build_mq_candidate()
        actions = candidate["properties"]["definition"]["actions"]
        batch_gate = find_action(actions, "Condition_MQ_Batch_Valid")
        batch_gate["expression"] = {"equals": ["@outputs('Compose_MQ_Input_Result')?['comparison_available']", True]}
        self.assertTrue(any("comparison_ready" in error for error in validate_mq_candidate(candidate)))

        candidate = build_mq_candidate()
        actions = candidate["properties"]["definition"]["actions"]
        success = find_action(actions, "Update_case_success_MQ")
        success["inputs"]["parameters"]["item"] = success["inputs"]["parameters"]["item"].replace(
            "cr6cb_mqmissingcount", "cr6cb_missingcount"
        )
        self.assertTrue(any("seven MQ summary fields" in error for error in validate_mq_candidate(candidate)))

    def test_minimal_vertical_slice_has_power_apps_compose_and_dataverse_get(self):
        clientdata = build_clientdata()
        definition = clientdata["properties"]["definition"]
        trigger = definition["triggers"]["manual"]
        self.assertEqual(trigger["type"], "Request")
        self.assertEqual(trigger["kind"], "PowerAppV2")
        self.assertEqual(trigger["inputs"]["schema"]["required"], ["text"])
        self.assertEqual(
            trigger["inputs"]["schema"]["properties"]["text"]["title"], "caseId"
        )

        actions = definition["actions"]
        self.assertIn("Compose_CaseId", actions)
        self.assertIn("Get_case", actions)
        self.assertEqual(actions["Get_case"]["runAfter"], {"Compose_CaseId": ["Succeeded"]})
        self.assertEqual(
            actions["Get_case"]["inputs"]["host"]["operationId"], "GetItem"
        )
        self.assertEqual(
            actions["Get_case"]["inputs"]["parameters"]["entityName"],
            "cr6cb_evidencecases",
        )

    def test_connector_reference_is_linked_to_current_dataverse_reference(self):
        clientdata = build_clientdata()
        refs = clientdata["properties"]["connectionReferences"]
        dataverse = refs["shared_commondataserviceforapps"]
        self.assertEqual(
            dataverse["connection"]["connectionReferenceLogicalName"],
            "new_sharedcommondataserviceforapps_88a5f",
        )
        self.assertEqual(
            dataverse["connection"]["name"],
            "shared-commondataser-6fdd83a9-6111-4889-bd4d-0d03929e9d5c",
        )

    def test_transfer_actions_use_confirmed_connector_operations(self):
        clientdata = build_clientdata()
        refs = clientdata["properties"]["connectionReferences"]
        self.assertIn("shared_onedriveforbusiness", refs)
        self.assertIn("shared_excelonlinebusiness", refs)
        self.assertEqual(
            refs["shared_onedriveforbusiness"]["connection"]["connectionReferenceLogicalName"],
            "new_sharedonedriveforbusiness_84ffc",
        )
        self.assertEqual(
            refs["shared_excelonlinebusiness"]["connection"]["connectionReferenceLogicalName"],
            "new_sharedexcelonlinebusiness_1723f",
        )
        actions = clientdata["properties"]["definition"]["actions"]
        all_actions = json.dumps(actions, ensure_ascii=False)
        for operation_id in (
            "ListRecords",
            "UpdateOnlyRecord",
            "CopyDriveFileByPath",
            "PatchItem",
            "GetItems",
        ):
            self.assertIn(operation_id, all_actions)
        self.assertIn('"overwrite": false', all_actions)
        self.assertIn("/架空ログ証跡アプリ完成版検証-T006-20260925/evidence-template-received-at-jst.xlsx", all_actions)

    def test_excelurl_candidate_writes_encoded_url_only_after_verified_readback(self):
        browser_root = (
            "https://tenant-my.sharepoint.com/personal/"
            "sample_tenant_onmicrosoft_com/Documents"
        )
        candidate = build_excelurl_candidate(browser_documents_root=browser_root)
        self.assertEqual(validate_excelurl_candidate(candidate), [])

        original = build_clientdata()
        self.assertNotIn("cr6cb_excelurl", json.dumps(original, ensure_ascii=False))

        actions = candidate["properties"]["definition"]["actions"]
        expression = (
            "@concat('"
            + browser_root
            + "/',uriComponent('架空ログ証跡アプリ完成版検証-T006-20260925'),"
            + "'/',outputs('Compose_CaseId'),'.xlsx')"
        )

        for condition_name, compose_name, update_name in (
            (
                "Condition_Readback_Matches",
                "Compose_ExcelUrl",
                "Update_case_success",
            ),
            (
                "Condition_Readback_Retry_Matches",
                "Compose_ExcelUrl_Retry",
                "Update_case_success_retry",
            ),
        ):
            condition = find_action(actions, condition_name)
            self.assertIsNotNone(condition)
            success_actions = condition["actions"]
            compose = success_actions[compose_name]
            self.assertEqual(compose["inputs"], expression)
            update = success_actions[update_name]
            self.assertEqual(update["runAfter"], {compose_name: ["Succeeded"]})
            self.assertIn("'cr6cb_excelurl',outputs(", update["inputs"]["parameters"]["item"])

        update_items = {
            name: action["inputs"]["parameters"].get("item", "")
            for name, action in walk_actions(actions)
            if action.get("type") == "OpenApiConnection"
            and action.get("inputs", {}).get("host", {}).get("operationId")
            == "UpdateOnlyRecord"
        }
        url_writes = {
            name for name, item in update_items.items() if "cr6cb_excelurl" in item
        }
        self.assertEqual(
            url_writes,
            {"Update_case_success", "Update_case_success_retry"},
        )
        self.assertNotIn("CreateShareLinkV2", json.dumps(actions))
        self.assertNotIn("CreateShareLinkByPathV2", json.dumps(actions))

    def test_excelurl_candidate_accepts_a_different_https_site_root(self):
        candidate = build_excelurl_candidate(
            browser_documents_root="https://other-my.sharepoint.com/personal/other/Documents/"
        )
        expression = find_action(
            candidate["properties"]["definition"]["actions"], "Compose_ExcelUrl"
        )["inputs"]
        self.assertTrue(expression.startswith("@concat('https://other-my.sharepoint.com/personal/other/Documents/"))
        self.assertEqual(validate_excelurl_candidate(candidate), [])

    def test_excelurl_candidate_rejects_unusable_site_root(self):
        for bad_root in (
            "http://tenant-my.sharepoint.com/personal/sample/Documents",
            "https://tenant-my.sharepoint.com/personal/sample/Documents?download=1",
            "https://tenant-my.sharepoint.com/sites/team/Documents",
            "https://tenant-my.sharepoint.com.attacker.example/personal/sample/Documents",
            "https://tenant-my.sharepoint.com/personal/sample'site/Documents",
        ):
            with self.subTest(root=bad_root):
                with self.assertRaises(ValueError):
                    build_excelurl_candidate(browser_documents_root=bad_root)

    def test_excelurl_candidate_rejects_a_copy_destination_outside_t006_folder(self):
        clientdata = build_clientdata()
        actions = clientdata["properties"]["definition"]["actions"]
        find_action(actions, "Compose_DestinationPath")["inputs"] = (
            "@concat('/another-folder/',outputs('Compose_CaseId'),'.xlsx')"
        )

        with self.assertRaisesRegex(ValueError, "destination.*T006"):
            build_excelurl_candidate(clientdata=clientdata)

        candidate = build_excelurl_candidate()
        find_action(
            candidate["properties"]["definition"]["actions"], "Compose_DestinationPath"
        )["inputs"] = "@concat('/another-folder/',outputs('Compose_CaseId'),'.xlsx')"
        self.assertTrue(
            any("T006 output path" in error for error in validate_excelurl_candidate(candidate))
        )

    def test_excelurl_validator_rejects_mutated_readback_gates_and_ordering(self):
        mutations = (
            (
                "initial condition expression",
                "Condition_Readback_Matches",
                lambda condition: condition.update(
                    expression={"equals": ["@true", True]}
                ),
            ),
            (
                "retry condition expression",
                "Condition_Readback_Retry_Matches",
                lambda condition: condition.update(
                    expression={"equals": ["@true", True]}
                ),
            ),
            (
                "initial read ordering",
                "Condition_Readback_Is_Empty",
                lambda condition: condition.update(runAfter={}),
            ),
            (
                "retry read ordering",
                "Condition_Readback_Retry_Matches",
                lambda condition: condition.update(runAfter={}),
            ),
            (
                "initial read ordering",
                "Read_back_evidence",
                lambda action: action.update(runAfter={}),
            ),
            (
                "write/read order",
                "Replace_template_row",
                lambda action: action.update(runAfter={}),
            ),
            (
                "readback file binding",
                "Read_back_evidence",
                lambda action: action["inputs"]["parameters"].update(
                    file="@outputs('Unrelated_copy')?['body/Id']"
                ),
            ),
            (
                "compose/update cycle",
                "Condition_Readback_Matches",
                lambda condition: condition["actions"]["Compose_ExcelUrl"].update(
                    runAfter={"Update_case_success": ["Succeeded"]}
                ),
            ),
        )

        for label, action_name, mutate in mutations:
            with self.subTest(mutation=label):
                candidate = build_excelurl_candidate()
                condition = find_action(
                    candidate["properties"]["definition"]["actions"], action_name
                )
                mutate(condition)

                self.assertTrue(validate_excelurl_candidate(candidate))

    def test_normal_path_checks_inputs_and_reads_back_before_success(self):
        clientdata = build_clientdata()
        actions = clientdata["properties"]["definition"]["actions"]
        self.assertIn("Condition_Start_Ready", actions)
        self.assertIn("Condition_One_Note", json.dumps(actions, ensure_ascii=False))
        self.assertIn("Condition_Log_Matches", json.dumps(actions, ensure_ascii=False))
        self.assertIn("Condition_One_Destination", json.dumps(actions, ensure_ascii=False))
        self.assertIn("Condition_Readback_Matches", json.dumps(actions, ensure_ascii=False))
        self.assertIn("Update_case_success", json.dumps(actions, ensure_ascii=False))
        self.assertIn("開始受付済み", json.dumps(actions, ensure_ascii=False))
        self.assertIn("全文一致", json.dumps(actions, ensure_ascii=False))
        self.assertIn("__TEMPLATE__", json.dumps(actions, ensure_ascii=False))
        self.assertIn("30", json.dumps(actions, ensure_ascii=False))
        get_case = actions["Get_case"]["inputs"]["parameters"]
        self.assertIn("createdon", get_case["$select"])
        self.assertNotIn("cr6cb_runnumber", get_case["$select"])

    def test_log_validation_records_a_specific_pre_copy_failure_reason(self):
        actions = build_clientdata()["properties"]["definition"]["actions"]
        reason_action = find_action(actions, "Compose_LogValidationReason")
        valid_action = find_action(actions, "Compose_IsValidLog")
        condition = find_action(actions, "Condition_Log_Matches")
        stop_action = find_action(actions, "Update_case_stop_log_invalid")

        self.assertIsNotNone(reason_action)
        self.assertIsNotNone(valid_action)
        self.assertIsNotNone(condition)
        self.assertIsNotNone(stop_action)
        reason = reason_action["inputs"]
        for message in (
            "ログの冒頭に処理日行（処理日: YYYY-MM-DD）がありません。",
            "ログの処理日がYYYY-MM-DD形式ではありません。",
            "ログの処理日は暦上存在しない日付です。",
            "本文日付（",
            "ログに環境の識別情報がありません。",
            "ログの環境が件の環境と一致しません。",
            "ログにサーバーの識別情報がありません。",
            "ログのサーバーが件のサーバーと一致しません。",
            "ログ本文が処理上限の30,000文字を超えています。",
        ):
            with self.subTest(message=message):
                self.assertIn(message, reason)
        self.assertNotIn("実行回", reason)
        self.assertNotIn("cr6cb_runnumber", reason)
        self.assertNotIn("Compose_LogLines')?[3]", reason)

        # Guard every indexed/substring date check before evaluating it and
        # make the same reason expression authoritative for acceptance.
        self.assertLess(
            reason.index("greater(length(outputs('Compose_LogText')),30000)"),
            reason.index("empty(outputs('Compose_LogFileName'))"),
        )
        self.assertLess(
            reason.index("startsWith(string(coalesce(outputs('Compose_LogLines')?[0],'')),'処理日: ')") ,
            reason.index("substring(string(coalesce(outputs('Compose_LogLines')?[0],'')),9,1)"),
        )
        self.assertIn("contains('0123456789'", reason)
        self.assertIn("mod(int(substring(", reason)
        self.assertIn("equals(mod(int(substring(", reason)
        self.assertIn(",400),0)", reason)
        self.assertIn(",100),0)", reason)
        self.assertIn(",4),0)", reason)
        self.assertIn("lessOrEquals(int(substring(", reason)
        self.assertLess(
            reason.index("ログの処理日は暦上存在しない日付です。"),
            reason.index("本文日付（"),
        )
        self.assertNotIn("1行上限", reason)
        self.assertEqual(
            reason_action["runAfter"], {"Compose_LogLines": ["Succeeded"]}
        )
        self.assertEqual(
            valid_action["inputs"], "@equals(outputs('Compose_LogValidationReason'),'')"
        )
        self.assertEqual(
            valid_action["runAfter"], {"Compose_LogValidationReason": ["Succeeded"]}
        )

        stop_item = stop_action["inputs"]["parameters"]["item"]
        self.assertIn("outputs('Compose_LogValidationReason')", stop_item)
        self.assertEqual(
            list(condition["else"]["actions"]), ["Update_case_stop_log_invalid"]
        )
        self.assertNotIn("Copy_template", json.dumps(condition["else"]["actions"]))

    def test_log_decode_failure_and_timeout_record_a_stop_without_copying(self):
        actions = build_clientdata()["properties"]["definition"]["actions"]
        decode = find_action(actions, "Compose_LogText")
        filename = find_action(actions, "Compose_LogFileName")
        failure_stop = find_action(actions, "Update_case_stop_log_unreadable")

        self.assertEqual(
            decode["inputs"],
            "@base64ToString(first(body('List_attached_notes')?['value'])?['documentbody'])",
        )
        self.assertEqual(filename["runAfter"], {"Compose_LogText": ["Succeeded"]})
        self.assertEqual(
            failure_stop["runAfter"],
            {"Compose_LogText": ["Failed", "TimedOut"]},
        )
        failure_item = failure_stop["inputs"]["parameters"]["item"]
        self.assertIn("cr6cb_processingstatus','停止'", failure_item)
        self.assertIn("添付ログ本文を読み取れませんでした", failure_item)
        self.assertIn("欠落または不正", failure_item)
        self.assertEqual(failure_stop["inputs"]["host"]["operationId"], "UpdateOnlyRecord")
        self.assertNotIn("Copy_template", json.dumps(failure_stop, ensure_ascii=False))

    def test_static_validator_requires_failed_and_timed_out_log_decode_handler(self):
        clientdata = copy.deepcopy(build_clientdata())
        handler = find_action(
            clientdata["properties"]["definition"]["actions"],
            "Update_case_stop_log_unreadable",
        )
        handler["runAfter"] = {"Compose_LogText": ["Failed"]}

        self.assertTrue(
            any(
                "decode failure and timeout" in error
                for error in validate_clientdata(clientdata)
            )
        )

    def test_empty_readback_gets_one_read_only_refresh_before_unknown(self):
        definition = build_clientdata()["properties"]["definition"]
        actions = definition["actions"]
        scope = find_action(actions, "Scope_Write_And_Verify")
        self.assertIsNotNone(scope)
        scope_actions = scope["actions"]

        empty_check = scope_actions["Condition_Readback_Is_Empty"]
        self.assertEqual(
            empty_check["runAfter"], {"Read_back_evidence": ["Succeeded"]}
        )
        self.assertEqual(
            empty_check["expression"],
            {"equals": ["@length(body('Read_back_evidence')?['value'])", 0]},
        )

        retry_actions = empty_check["actions"]
        self.assertEqual(
            retry_actions["Delay_before_readback_retry"]["inputs"]["interval"],
            {"count": 10, "unit": "Second"},
        )
        retry_read = retry_actions["Read_back_evidence_retry"]
        retry_parameters = retry_read["inputs"]["parameters"]
        initial_parameters = scope_actions["Read_back_evidence"]["inputs"]["parameters"]
        self.assertEqual(retry_read["inputs"]["host"]["operationId"], "GetItems")
        expected_retry_parameters = copy.deepcopy(initial_parameters)
        expected_retry_parameters["$top"] = 3
        self.assertEqual(retry_parameters, expected_retry_parameters)
        self.assertEqual(retry_parameters["$top"], 3)
        self.assertEqual(retry_read["inputs"]["retryPolicy"], {"type": "none"})
        self.assertEqual(
            scope_actions["Read_back_evidence"]["inputs"]["retryPolicy"],
            {"type": "none"},
        )
        self.assertEqual(
            retry_read["runAfter"], {"Delay_before_readback_retry": ["Succeeded"]}
        )

        retry_match = retry_actions["Condition_Readback_Retry_Matches"]
        initial_match = empty_check["else"]["actions"]["Condition_Readback_Matches"]
        for action_name, readback_match in (
            ("Read_back_evidence", initial_match),
            ("Read_back_evidence_retry", retry_match),
        ):
            expression = readback_match["expression"]["equals"][0]
            self.assertIn(f"length(body('{action_name}')?['value']),1", expression)
            row = f"first(body('{action_name}')?['value'])?"
            expected_comparisons = (
                f"equals({row}['CaseId'],outputs('Compose_CaseId'))",
                f"equals({row}['LogFileName'],outputs('Compose_LogFileName'))",
                f"equals({row}['Environment'],outputs('Get_case')?['body/cr6cb_environment'])",
                f"equals({row}['Server'],outputs('Get_case')?['body/cr6cb_server'])",
                f"equals(formatDateTime({row}['ReceivedAtJst'],'yyyy-MM-dd HH:mm:ss'),convertTimeZone(outputs('Get_case')?['body/createdon'],'UTC','Tokyo Standard Time','yyyy-MM-dd HH:mm:ss'))",
                f"startsWith(string({row}['TargetDate']),formatDateTime(outputs('Get_case')?['body/cr6cb_targetdate'],'yyyy-MM-dd'))",
                f"equals(string({row}['ChunkIndex']),'1')",
                f"equals(string({row}['ChunkCount']),'1')",
                f"equals({row}['LogTextPart'],outputs('Compose_LogText'))",
            )
            for comparison in expected_comparisons:
                with self.subTest(action=action_name, comparison=comparison):
                    self.assertIn(comparison, expression)

        # Any non-empty initial result bypasses the extra read. Exactly one
        # matching row succeeds; multiple rows or any mismatched field go unknown.
        self.assertEqual(
            list(empty_check["else"]["actions"]), ["Condition_Readback_Matches"]
        )
        self.assertIn("Update_case_success", initial_match["actions"])
        self.assertIn(
            "Update_case_readback_unknown", initial_match["else"]["actions"]
        )
        self.assertIn("Update_case_success_retry", retry_match["actions"])
        self.assertIn("Update_case_readback_unknown_retry", retry_match["else"]["actions"])
        self.assertIn(
            "結果不明",
            json.dumps(retry_match["else"]["actions"], ensure_ascii=False),
        )

        self.assertEqual(
            initial_match["runAfter"], {}
        )

        retry_openapi_actions = [
            action
            for _, action in walk_actions(retry_actions)
            if action.get("type") == "OpenApiConnection"
        ]
        retry_operations = [
            action["inputs"]["host"]["operationId"]
            for action in retry_openapi_actions
        ]
        self.assertEqual(retry_operations.count("GetItems"), 1)
        self.assertNotIn("PatchItem", retry_operations)
        self.assertNotIn("CopyDriveFileByPath", retry_operations)
        self.assertNotIn("CopyDriveFile", retry_operations)
        excel_operations = [
            action["inputs"]["host"]["operationId"]
            for action in retry_openapi_actions
            if action["inputs"]["host"]["apiId"].endswith(
                "/shared_excelonlinebusiness"
            )
        ]
        self.assertEqual(excel_operations, ["GetItems"])
        self.assertFalse(
            any(
                action["inputs"]["host"]["apiId"].endswith(
                    "/shared_onedriveforbusiness"
                )
                for action in retry_openapi_actions
            )
        )

    def test_pre_copy_rejections_record_stop_and_post_copy_failure_records_unknown(self):
        clientdata = build_clientdata()
        actions = json.dumps(clientdata["properties"]["definition"]["actions"], ensure_ascii=False)
        self.assertIn("Update_case_stop_no_note", actions)
        self.assertIn("Update_case_stop_log_invalid", actions)
        self.assertIn("Update_case_stop_destination", actions)
        self.assertIn("Scope_Write_And_Verify", actions)
        self.assertIn("Update_case_copy_unknown", actions)
        self.assertIn("Update_case_postcopy_unknown", actions)
        self.assertIn("結果不明", actions)
        self.assertIn("停止", actions)
        self.assertIn("再実行", actions)

    def test_validator_rejects_unsafe_copy_and_write_failure_mutations(self):
        mutations = (
            (
                "copy automatic retry",
                lambda actions: find_action(actions, "Copy_template")["inputs"].update(
                    retryPolicy={"type": "exponential"}
                ),
            ),
            (
                "Excel write automatic retry",
                lambda actions: find_action(actions, "Replace_template_row")["inputs"].pop(
                    "retryPolicy"
                ),
            ),
            (
                "copy timeout bypasses unknown handler",
                lambda actions: find_action(actions, "Update_case_copy_unknown").update(
                    runAfter={"Copy_template": ["Failed"]}
                ),
            ),
            (
                "post-copy failure can mark success",
                lambda actions: find_action(actions, "Update_case_postcopy_unknown")[
                    "inputs"
                ]["parameters"].update(
                    item="@addProperty(json('{}'),'cr6cb_processingstatus','転記済み')"
                ),
            ),
            (
                "duplicate copy can create a second workbook",
                lambda actions: find_action(actions, "Condition_One_Destination")[
                    "actions"
                ].update(
                    Copy_template_duplicate=copy.deepcopy(find_action(actions, "Copy_template"))
                    )
            ),
        )
        for label, mutate in mutations:
            with self.subTest(mutation=label):
                candidate = build_excelurl_candidate()
                actions = candidate["properties"]["definition"]["actions"]
                mutate(actions)
                self.assertTrue(
                    validate_excelurl_candidate(candidate),
                    f"validator accepted unsafe mutation: {label}",
                )

    def test_excelurl_validator_rejects_transaction_chain_in_no_destination_branch(self):
        candidate = build_excelurl_candidate()
        actions = candidate["properties"]["definition"]["actions"]
        condition = find_action(actions, "Condition_One_Destination")
        condition["else"]["actions"].update(condition["actions"])
        condition["actions"] = {}

        errors = validate_excelurl_candidate(candidate)

        for action_name in (
            "Copy_template",
            "Scope_Write_And_Verify",
            "Update_case_copy_unknown",
            "Update_case_postcopy_unknown",
        ):
            self.assertIn(
                f"{action_name} must remain under Condition_One_Destination success branch",
                errors,
            )

    def test_c02_snapshot_is_preserved_and_new_excelurl_candidate_uses_received_at(self):
        candidate_path = Path(__file__).with_name(
            "flow-definition.excelurl-c02-local-candidate.json"
        )
        historical_candidate = json.loads(candidate_path.read_text(encoding="utf-8"))
        historical_readback = find_action(
            historical_candidate["properties"]["definition"]["actions"],
            "Read_back_evidence",
        )
        self.assertIn("RunNumber", historical_readback["inputs"]["parameters"]["$select"])
        self.assertEqual(validate_excelurl_candidate(historical_candidate), [])

        new_candidate = build_excelurl_candidate()
        self.assertEqual(validate_excelurl_candidate(new_candidate), [])
        new_actions = new_candidate["properties"]["definition"]["actions"]
        new_readback = find_action(new_actions, "Read_back_evidence")
        new_write = find_action(new_actions, "Replace_template_row")
        self.assertIn("ReceivedAtJst", new_readback["inputs"]["parameters"]["$select"])
        self.assertNotIn("RunNumber", new_readback["inputs"]["parameters"]["$select"])
        self.assertIn("ReceivedAtJst", new_write["inputs"]["parameters"]["item"])

    def test_validator_rejects_cycles_and_out_of_scope_run_after(self):
        import copy

        cycle_candidate = copy.deepcopy(build_clientdata())
        compose = cycle_candidate["properties"]["definition"]["actions"]["Compose_CaseId"]
        compose["self"] = compose
        self.assertTrue(any("cycle" in item.lower() for item in validate_clientdata(cycle_candidate)))

        bad_run_after = copy.deepcopy(build_clientdata())
        bad_run_after["properties"]["definition"]["actions"]["Compose_CaseId"]["runAfter"] = {
            "missing": ["Succeeded"]
        }
        self.assertTrue(
            any("runAfter" in item for item in validate_clientdata(bad_run_after))
        )

    def test_candidate_states_initial_happy_path_limits_without_claiming_retry(self):
        from build_flow_definition import build_status

        status = build_status()
        self.assertEqual(status["status"], "local definition artifact; deployment and runtime status are tracked in docs/TASKS.md")
        self.assertTrue(any("date, environment, and server" in item for item in status["scope"]))
        self.assertFalse(any("run number" in item.lower() for item in status["scope"]))
        self.assertTrue(
            any(
                "concurrent-start locking" in item.lower()
                for item in status["not_implemented"]
            )
        )
        self.assertTrue(
            any(
                "Copy and Excel write actions use retryPolicy=none" in item
                and "read-only GetItems requery" in item
                and "not a copy/write retry" in item
                for item in status["known_behavior"]
            )
        )
        self.assertTrue(any("failure" in item.lower() for item in status["not_implemented"]))

    def test_api_preview_serializes_clientdata_and_stays_draft(self):
        clientdata = build_clientdata()
        request = build_api_request(clientdata)
        body = request["body"]
        self.assertEqual(body["category"], 5)
        self.assertEqual(body["type"], 1)
        self.assertNotIn("statecode", body)
        self.assertNotIn("statuscode", body)
        self.assertEqual(json.loads(body["clientdata"]), clientdata)

    def test_pure_workflow_body_is_directly_serializable_for_body_file(self):
        body = build_workflow_body(build_clientdata())
        self.assertEqual(
            set(body), {"category", "name", "type", "description", "primaryentity", "clientdata"}
        )
        self.assertEqual(json.loads(body["clientdata"]), build_clientdata())

    def test_static_validation_rejects_unresolved_placeholders(self):
        clientdata = build_clientdata()
        clientdata["properties"]["definition"]["actions"]["Get_case"]["inputs"]["parameters"][
            "organization"
        ] = "<organization-url>"
        self.assertTrue(
            any("placeholder" in error.lower() for error in validate_clientdata(clientdata))
        )

    def test_static_validation_rejects_broken_connection_reference(self):
        clientdata = copy.deepcopy(build_clientdata())
        clientdata["properties"]["connectionReferences"]["shared_commondataserviceforapps"][
            "connection"]["connectionReferenceLogicalName"] = "wrong_reference"
        self.assertTrue(
            any("connection reference" in error.lower() for error in validate_clientdata(clientdata))
        )

    def test_static_validation_accepts_current_candidate(self):
        self.assertEqual(validate_clientdata(build_clientdata()), [])


if __name__ == "__main__":
    unittest.main()
