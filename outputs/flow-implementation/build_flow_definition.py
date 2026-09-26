"""Build a local Power Automate WDL candidate and static-check its wiring.

The script only writes local JSON files. It never calls Power Platform.
"""

from __future__ import annotations

import argparse
import copy
import json
import re
import uuid
from pathlib import Path
from typing import Any
from urllib.parse import urlsplit, urlunsplit


HERE = Path(__file__).resolve().parent
ORGANIZATION_URL = "https://org3d6ad684.crm7.dynamics.com/"
DATAVERSE_CONNECTION_NAME = "shared-commondataser-6fdd83a9-6111-4889-bd4d-0d03929e9d5c"
DATAVERSE_REFERENCE_NAME = "new_sharedcommondataserviceforapps_88a5f"
ONEDRIVE_CONNECTION_NAME = "shared-onedriveforbu-063fb695-4425-4257-8eec-e4cd4203d105"
ONEDRIVE_REFERENCE_NAME = "new_sharedonedriveforbusiness_84ffc"
EXCEL_CONNECTION_NAME = "shared-excelonlinebu-85d16041-9b32-40ce-952f-c75a0c6b9435"
EXCEL_REFERENCE_NAME = "new_sharedexcelonlinebusiness_1723f"
DATAVERSE_API = "shared_commondataserviceforapps"
ONEDRIVE_API = "shared_onedriveforbusiness"
EXCEL_API = "shared_excelonlinebusiness"
T006_FOLDER_ID = "01VTXCECE5BP476QXS7RFIAAAMC5QNGY6X"
T006_TEMPLATE_ID = "01VTXCECFCHLCOP5KJYFG3SOSB36BFWFWD"
T006_FOLDER_PATH = "/架空ログ証跡アプリ完成版検証-T006-20260925"
T006_TEMPLATE_PATH = f"{T006_FOLDER_PATH}/evidence-template.xlsx"
T006_BROWSER_DOCUMENTS_ROOT = (
    "https://fujimasa13-my.sharepoint.com/personal/"
    "fujimasa_fujimasa13_onmicrosoft_com/Documents"
)
MAX_SINGLE_CELL_LENGTH = 30_000


def _metadata_id(name: str) -> str:
    return str(uuid.uuid5(uuid.NAMESPACE_URL, f"powerapps-gas-flow:{name}"))


def _reference(api_name: str, connection_name: str, logical_name: str, runtime_source: str) -> dict[str, Any]:
    return {
        "runtimeSource": runtime_source,
        "connection": {
            "name": connection_name,
            "connectionReferenceLogicalName": logical_name,
        },
        "api": {"name": api_name},
    }


def _compose(name: str, inputs: str, run_after: dict[str, list[str]]) -> dict[str, Any]:
    return {
        "runAfter": run_after,
        "metadata": {"operationMetadataId": _metadata_id(name)},
        "type": "Compose",
        "inputs": inputs,
    }


def _openapi(
    name: str,
    api_name: str,
    connection_key: str,
    operation_id: str,
    parameters: dict[str, Any],
    run_after: dict[str, list[str]],
    *,
    retry_none: bool = False,
) -> dict[str, Any]:
    action: dict[str, Any] = {
        "runAfter": run_after,
        "metadata": {"operationMetadataId": _metadata_id(name)},
        "type": "OpenApiConnection",
        "inputs": {
            "host": {
                "apiId": f"/providers/Microsoft.PowerApps/apis/{api_name}",
                "connectionName": connection_key,
                "operationId": operation_id,
            },
            "parameters": parameters,
            "authentication": "@parameters('$authentication')",
        },
    }
    if retry_none:
        action["inputs"]["retryPolicy"] = {"type": "none"}
    return action


def _condition(
    name: str,
    expression: dict[str, Any],
    true_actions: dict[str, Any],
    run_after: dict[str, list[str]],
    false_actions: dict[str, Any] | None = None,
) -> dict[str, Any]:
    return {
        "runAfter": run_after,
        "metadata": {"operationMetadataId": _metadata_id(name)},
        "type": "If",
        "expression": expression,
        "actions": true_actions,
        "else": {"actions": false_actions or {}},
    }


def _list_rows(
    name: str, entity_name: str, parameters: dict[str, Any], run_after: dict[str, list[str]]
) -> dict[str, Any]:
    all_parameters = {"entityName": entity_name}
    all_parameters.update(parameters)
    return _openapi(
        name,
        DATAVERSE_API,
        DATAVERSE_API,
        "ListRecords",
        all_parameters,
        run_after,
        retry_none=True,
    )


def _update_case(name: str, item_expression: str, run_after: dict[str, list[str]]) -> dict[str, Any]:
    return _openapi(
        name,
        DATAVERSE_API,
        DATAVERSE_API,
        "UpdateOnlyRecord",
        {
            "entityName": "cr6cb_evidencecases",
            "recordId": "@outputs('Compose_CaseId')",
            "item": item_expression,
        },
        run_after,
        retry_none=True,
    )


def _failure_item(status: str, reason: str, excel_status: str | None = None) -> str:
    expression = "json('{}')"
    for field, value in (
        ("cr6cb_processingstatus", status),
        ("cr6cb_failurereason", reason),
        ("cr6cb_excelcheckstatus", excel_status),
    ):
        if value is not None:
            expression = f"addProperty({expression},'{field}','{value}')"
    return "@" + expression


def _excel_item_expression() -> str:
    properties = [
        ("CaseId", "outputs('Compose_CaseId')"),
        ("LogFileName", "outputs('Compose_LogFileName')"),
        ("Environment", "outputs('Get_case')?['body/cr6cb_environment']"),
        ("Server", "outputs('Get_case')?['body/cr6cb_server']"),
        ("RunNumber", "outputs('Get_case')?['body/cr6cb_runnumber']"),
        (
            "TargetDate",
            "formatDateTime(outputs('Get_case')?['body/cr6cb_targetdate'],'yyyy-MM-dd')",
        ),
        ("ChunkIndex", "1"),
        ("ChunkCount", "1"),
        ("LogTextPart", "outputs('Compose_LogText')"),
    ]
    expression = "json('{}')"
    for property_name, value_expression in properties:
        expression = (
            f"addProperty({expression},'{property_name}',{value_expression})"
        )
    return "@" + expression


def _log_validation_reason_expression() -> str:
    """Return a specific pre-copy rejection reason, or an empty string if valid."""
    lines = "outputs('Compose_LogLines')"
    line0 = f"string(coalesce({lines}?[0],''))"
    line1 = f"string(coalesce({lines}?[1],''))"
    line2 = f"string(coalesce({lines}?[2],''))"
    line3 = f"string(coalesce({lines}?[3],''))"
    run_number = "outputs('Get_case')?['body/cr6cb_runnumber']"
    server = "outputs('Get_case')?['body/cr6cb_server']"
    environment = "outputs('Get_case')?['body/cr6cb_environment']"
    target_date = "outputs('Get_case')?['body/cr6cb_targetdate']"
    run_expected = f"concat('実行回: ',string({run_number}))"
    server_expected = f"concat('サーバー: ',{server})"
    environment_expected = f"concat('環境: ',{environment})"
    date_expected = f"concat('処理日: ',formatDateTime({target_date},'yyyy-MM-dd'))"

    reason = "''"
    reason = (
        f"if(not(equals({line3},{run_expected})),"
        "'ログの実行回が件の実行回と一致しません。',"
        f"{reason})"
    )
    reason = (
        f"if(not(startsWith({line3},'実行回: ')),"
        "'ログに実行回の識別情報がありません。',"
        f"{reason})"
    )
    reason = (
        f"if(not(equals({line2},{server_expected})),"
        "'ログのサーバーが件のサーバーと一致しません。',"
        f"{reason})"
    )
    reason = (
        f"if(not(startsWith({line2},'サーバー: ')),"
        "'ログにサーバーの識別情報がありません。',"
        f"{reason})"
    )
    reason = (
        f"if(not(equals({line1},{environment_expected})),"
        "'ログの環境が件の環境と一致しません。',"
        f"{reason})"
    )
    reason = (
        f"if(not(startsWith({line1},'環境: ')),"
        "'ログに環境の識別情報がありません。',"
        f"{reason})"
    )
    reason = (
        f"if(not(equals({line0},{date_expected})),"
        f"concat('本文日付（',substring({line0},5,10),'）と対象処理日（',"
        f"formatDateTime({target_date},'yyyy-MM-dd'),'）が一致しません。'),"
        f"{reason})"
    )
    date_digits = (5, 6, 7, 8, 10, 11, 13, 14)
    invalid_date_digit = "or(" + ",".join(
        f"not(contains('0123456789',substring({line0},{position},1)))"
        for position in date_digits
    ) + ")"
    year = f"int(substring({line0},5,4))"
    month = f"int(substring({line0},10,2))"
    day = f"int(substring({line0},13,2))"
    leap_year = (
        f"or(equals(mod({year},400),0),"
        f"and(equals(mod({year},4),0),not(equals(mod({year},100),0))))"
    )
    days_in_month = (
        f"if(or({','.join(f'equals({month},{value})' for value in (1, 3, 5, 7, 8, 10, 12))}),31,"
        f"if(equals({month},2),if({leap_year},29,28),30))"
    )
    valid_calendar_date = (
        f"and(greaterOrEquals({year},1),lessOrEquals({year},9999),"
        f"greaterOrEquals({month},1),lessOrEquals({month},12),"
        f"greaterOrEquals({day},1),lessOrEquals({day},{days_in_month}))"
    )
    reason = (
        f"if(not({valid_calendar_date}),"
        "'ログの処理日は暦上存在しない日付です。',"
        f"{reason})"
    )
    reason = (
        f"if({invalid_date_digit},"
        "'ログの処理日がYYYY-MM-DD形式ではありません。',"
        f"{reason})"
    )
    reason = (
        f"if(not(equals(substring({line0},12,1),'-')),"
        "'ログの処理日がYYYY-MM-DD形式ではありません。',"
        f"{reason})"
    )
    reason = (
        f"if(not(equals(substring({line0},9,1),'-')),"
        "'ログの処理日がYYYY-MM-DD形式ではありません。',"
        f"{reason})"
    )
    reason = (
        f"if(not(equals(length({line0}),15)),"
        "'ログの処理日がYYYY-MM-DD形式ではありません。',"
        f"{reason})"
    )
    reason = (
        f"if(not(startsWith({line0},'処理日: ')),"
        "'ログの冒頭に処理日行（処理日: YYYY-MM-DD）がありません。',"
        f"{reason})"
    )
    reason = (
        "if(empty(outputs('Compose_LogFileName')),'ログのファイル名を読み取れません。',"
        f"{reason})"
    )
    reason = (
        "if(greater(length(outputs('Compose_LogText')),30000),"
        "'ログ本文が処理上限の30,000文字を超えています。',"
        f"{reason})"
    )
    return "@" + reason


def _readback_expression(readback_action: str) -> str:
    row = f"first(body('{readback_action}')?['value'])?"
    conditions = [
        f"equals(length(body('{readback_action}')?['value']),1)",
        f"equals({row}['CaseId'],outputs('Compose_CaseId'))",
        f"equals({row}['LogFileName'],outputs('Compose_LogFileName'))",
        f"equals({row}['Environment'],outputs('Get_case')?['body/cr6cb_environment'])",
        f"equals({row}['Server'],outputs('Get_case')?['body/cr6cb_server'])",
        f"equals(string({row}['RunNumber']),string(outputs('Get_case')?['body/cr6cb_runnumber']))",
        f"startsWith(string({row}['TargetDate']),formatDateTime(outputs('Get_case')?['body/cr6cb_targetdate'],'yyyy-MM-dd'))",
        f"equals(string({row}['ChunkIndex']),'1')",
        f"equals(string({row}['ChunkCount']),'1')",
        f"equals({row}['LogTextPart'],outputs('Compose_LogText'))",
    ]
    return "@and(" + ",".join(conditions) + ")"


def _excel_action(
    name: str,
    operation_id: str,
    parameters: dict[str, Any],
    run_after: dict[str, list[str]],
    *,
    retry_none: bool = False,
) -> dict[str, Any]:
    return _openapi(
        name,
        EXCEL_API,
        EXCEL_API,
        operation_id,
        parameters,
        run_after,
        retry_none=retry_none,
    )


def _delay(name: str, seconds: int, run_after: dict[str, list[str]]) -> dict[str, Any]:
    return {
        "runAfter": run_after,
        "metadata": {"operationMetadataId": _metadata_id(name)},
        "type": "Wait",
        "inputs": {"interval": {"count": seconds, "unit": "Second"}},
    }


def _normal_path_actions() -> dict[str, Any]:
    actions: dict[str, Any] = {}

    actions["List_attached_notes"] = _list_rows(
        "List_attached_notes",
        "annotations",
        {
            "$select": "annotationid,filename,documentbody,isdocument,_objectid_value",
            "$filter": "@concat('isdocument eq true and _objectid_value eq ',outputs('Compose_CaseId'))",
            "$top": 2,
        },
        {},
    )

    log_actions: dict[str, Any] = {}
    log_actions["Compose_LogText"] = _compose(
        "Compose_LogText",
        "@base64ToString(first(body('List_attached_notes')?['value'])?['documentbody'])",
        {},
    )
    log_actions["Update_case_stop_log_unreadable"] = _update_case(
        "Update_case_stop_log_unreadable",
        _failure_item(
            "停止",
            "添付ログ本文を読み取れませんでした。本文データが欠落または不正です。",
        ),
        {"Compose_LogText": ["Failed", "TimedOut"]},
    )
    log_actions["Compose_LogFileName"] = _compose(
        "Compose_LogFileName",
        "@first(body('List_attached_notes')?['value'])?['filename']",
        {"Compose_LogText": ["Succeeded"]},
    )
    log_actions["Compose_LogLines"] = _compose(
        "Compose_LogLines",
        "@split(replace(outputs('Compose_LogText'),decodeUriComponent('%0D'),''),decodeUriComponent('%0A'))",
        {"Compose_LogFileName": ["Succeeded"]},
    )
    log_actions["Compose_LogValidationReason"] = _compose(
        "Compose_LogValidationReason",
        _log_validation_reason_expression(),
        {"Compose_LogLines": ["Succeeded"]},
    )
    log_actions["Compose_IsValidLog"] = _compose(
        "Compose_IsValidLog",
        "@equals(outputs('Compose_LogValidationReason'),'')",
        {"Compose_LogValidationReason": ["Succeeded"]},
    )

    validation_actions: dict[str, Any] = {}
    validation_actions["List_active_destinations"] = _list_rows(
        "List_active_destinations",
        "cr6cb_evidencedestinations",
        {
            "$select": "cr6cb_destinationlabel,cr6cb_environment,cr6cb_server,cr6cb_driveid,cr6cb_folderid,cr6cb_isactive",
            "$filter": "cr6cb_isactive eq true",
            "$top": 100,
        },
        {},
    )
    validation_actions["Filter_active_destinations"] = {
        "runAfter": {"List_active_destinations": ["Succeeded"]},
        "metadata": {"operationMetadataId": _metadata_id("Filter_active_destinations")},
        "type": "Query",
        "inputs": {
            "from": "@body('List_active_destinations')?['value']",
            "where": "@and(equals(item()?['cr6cb_environment'],outputs('Get_case')?['body/cr6cb_environment']),equals(item()?['cr6cb_server'],outputs('Get_case')?['body/cr6cb_server']))",
        },
    }

    destination_actions: dict[str, Any] = {}
    destination_actions["Compose_DestinationPath"] = _compose(
        "Compose_DestinationPath",
        f"@concat('{T006_FOLDER_PATH}/',outputs('Compose_CaseId'),'.xlsx')",
        {},
    )
    destination_actions["Update_processing"] = _update_case(
        "Update_processing",
        "@addProperty(json('{}'),'cr6cb_processingstatus','処理中')",
        {"Compose_DestinationPath": ["Succeeded"]},
    )
    destination_actions["Copy_template"] = _openapi(
        "Copy_template",
        ONEDRIVE_API,
        ONEDRIVE_API,
        "CopyDriveFileByPath",
        {
            "source": T006_TEMPLATE_PATH,
            "destination": "@outputs('Compose_DestinationPath')",
            "overwrite": False,
        },
        {"Update_processing": ["Succeeded"]},
        retry_none=True,
    )
    write_verify_actions: dict[str, Any] = {}
    write_verify_actions["Delay_for_workbook"] = _delay(
        "Delay_for_workbook", 10, {}
    )
    write_verify_actions["Replace_template_row"] = _excel_action(
        "Replace_template_row",
        "PatchItem",
        {
            "source": "me",
            "drive": "@first(body('Filter_active_destinations'))?['cr6cb_driveid']",
            "file": "@outputs('Copy_template')?['body/Id']",
            "table": "Evidence",
            "idColumn": "CaseId",
            "id": "__TEMPLATE__",
            "item": _excel_item_expression(),
            "dateTimeFormat": "ISO 8601",
        },
        {"Delay_for_workbook": ["Succeeded"]},
        retry_none=True,
    )
    write_verify_actions["Delay_before_readback"] = _delay(
        "Delay_before_readback", 30, {"Replace_template_row": ["Succeeded"]}
    )
    write_verify_actions["Read_back_evidence"] = _excel_action(
        "Read_back_evidence",
        "GetItems",
        {
            "source": "me",
            "drive": "@first(body('Filter_active_destinations'))?['cr6cb_driveid']",
            "file": "@outputs('Copy_template')?['body/Id']",
            "table": "Evidence",
            "$filter": "@concat('CaseId eq ''',outputs('Compose_CaseId'),'''')",
            "$top": 2,
            "$select": "CaseId,LogFileName,Environment,Server,RunNumber,TargetDate,ChunkIndex,ChunkCount,LogTextPart",
            "dateTimeFormat": "ISO 8601",
        },
        {"Delay_before_readback": ["Succeeded"]},
        retry_none=True,
    )

    success_fields = "@addProperty(addProperty(json('{}'),'cr6cb_processingstatus','転記済み'),'cr6cb_excelcheckstatus','全文一致')"
    unknown_fields = _failure_item(
        "結果不明",
        "Excelの反映内容を全文照合できませんでした。出力ファイルを確認し、確認が終わるまで再実行しないでください。",
        "読出不能",
    )

    retry_actions: dict[str, Any] = {}
    retry_actions["Delay_before_readback_retry"] = _delay(
        "Delay_before_readback_retry", 10, {}
    )
    retry_actions["Read_back_evidence_retry"] = _excel_action(
        "Read_back_evidence_retry",
        "GetItems",
        {
            "source": "me",
            "drive": "@first(body('Filter_active_destinations'))?['cr6cb_driveid']",
            "file": "@outputs('Copy_template')?['body/Id']",
            "table": "Evidence",
            "$filter": "@concat('CaseId eq ''',outputs('Compose_CaseId'),'''')",
            # Use a distinct page size to make a distinct read request. This is
            # a best-effort cache-key variation, not proof that a cache is bypassed.
            # A retry result is still accepted only after full row verification.
            "$top": 3,
            "$select": "CaseId,LogFileName,Environment,Server,RunNumber,TargetDate,ChunkIndex,ChunkCount,LogTextPart",
            "dateTimeFormat": "ISO 8601",
        },
        {"Delay_before_readback_retry": ["Succeeded"]},
        retry_none=True,
    )
    retry_actions["Condition_Readback_Retry_Matches"] = _condition(
        "Condition_Readback_Retry_Matches",
        {"equals": [_readback_expression("Read_back_evidence_retry"), True]},
        {
            "Update_case_success_retry": _update_case(
                "Update_case_success_retry", success_fields, {}
            )
        },
        {"Read_back_evidence_retry": ["Succeeded"]},
        {
            "Update_case_readback_unknown_retry": _update_case(
                "Update_case_readback_unknown_retry", unknown_fields, {}
            )
        },
    )
    write_verify_actions["Condition_Readback_Is_Empty"] = _condition(
        "Condition_Readback_Is_Empty",
        {"equals": ["@length(body('Read_back_evidence')?['value'])", 0]},
        retry_actions,
        {"Read_back_evidence": ["Succeeded"]},
        {
            "Condition_Readback_Matches": _condition(
                "Condition_Readback_Matches",
                {"equals": [_readback_expression("Read_back_evidence"), True]},
                {
                    "Update_case_success": _update_case(
                        "Update_case_success", success_fields, {}
                    )
                },
                {},
                {
                    "Update_case_readback_unknown": _update_case(
                        "Update_case_readback_unknown", unknown_fields, {}
                    )
                },
            )
        },
    )

    destination_actions["Scope_Write_And_Verify"] = {
        "runAfter": {"Copy_template": ["Succeeded"]},
        "metadata": {"operationMetadataId": _metadata_id("Scope_Write_And_Verify")},
        "type": "Scope",
        "actions": write_verify_actions,
    }
    destination_actions["Update_case_copy_unknown"] = _update_case(
        "Update_case_copy_unknown",
        _failure_item(
            "結果不明",
            "コピー処理の結果を確認できません。出力ファイルを確認し、状態が判明するまで再実行しないでください。",
            "未確認",
        ),
        {"Copy_template": ["Failed", "TimedOut"]},
    )
    destination_actions["Update_case_postcopy_unknown"] = _update_case(
        "Update_case_postcopy_unknown",
        _failure_item(
            "結果不明",
            "コピー後のExcel書込・読戻しを確認できません。出力ファイルを確認し、状態が判明するまで再実行しないでください。",
            "読出不能",
        ),
        {"Scope_Write_And_Verify": ["Failed", "TimedOut"]},
    )

    destination_condition = _condition(
        "Condition_One_Destination",
        {
            "equals": [
                "@and(equals(length(body('Filter_active_destinations')),1),equals(first(body('Filter_active_destinations'))?['cr6cb_folderid'],'01VTXCECE5BP476QXS7RFIAAAMC5QNGY6X'),not(empty(first(body('Filter_active_destinations'))?['cr6cb_driveid'])))",
                True,
            ]
        },
        dict(destination_actions),
        {"Filter_active_destinations": ["Succeeded"]},
        {
            "Update_case_stop_destination": _update_case(
                "Update_case_stop_destination",
                _failure_item("停止", "有効な転記先が一意に確認できません。"),
                {},
            )
        },
    )
    validation_actions["Condition_One_Destination"] = destination_condition
    log_condition = _condition(
        "Condition_Log_Matches",
        {"equals": ["@outputs('Compose_IsValidLog')", True]},
        dict(validation_actions),
        {"Compose_IsValidLog": ["Succeeded"]},
        {
            "Update_case_stop_log_invalid": _update_case(
                "Update_case_stop_log_invalid",
                "@addProperty(addProperty(json('{}'),'cr6cb_processingstatus','停止'),'cr6cb_failurereason',outputs('Compose_LogValidationReason'))",
                {},
            )
        },
    )
    note_branch = dict(log_actions)
    note_branch["Condition_Log_Matches"] = log_condition
    note_condition = _condition(
        "Condition_One_Note",
        {"equals": ["@length(body('List_attached_notes')?['value'])", 1]},
        note_branch,
        {"List_attached_notes": ["Succeeded"]},
        {
            "Update_case_stop_no_note": _update_case(
                "Update_case_stop_no_note",
                _failure_item("停止", "添付ログが1件ではありません。"),
                {},
            )
        },
    )
    actions["Condition_One_Note"] = note_condition
    return actions


def build_clientdata() -> dict[str, Any]:
    dataverse_key = DATAVERSE_API
    definition = {
        "$schema": "https://schema.management.azure.com/providers/Microsoft.Logic/schemas/2016-06-01/workflowdefinition.json#",
        "contentVersion": "1.0.0.0",
        "parameters": {
            "$connections": {"defaultValue": {}, "type": "Object"},
            "$authentication": {"defaultValue": {}, "type": "SecureObject"},
        },
        "triggers": {
            "manual": {
                "metadata": {"operationMetadataId": _metadata_id("PowerAppsV2_trigger")},
                "type": "Request",
                "kind": "PowerAppV2",
                "inputs": {
                    "schema": {
                        "type": "object",
                        "properties": {
                            "text": {
                                "title": "caseId",
                                "type": "string",
                                "x-ms-content-hint": "TEXT",
                                "x-ms-dynamically-added": True,
                            }
                        },
                        "required": ["text"],
                    }
                },
            }
        },
        "actions": {
            "Compose_CaseId": _compose(
                "Compose_CaseId", "@toLower(triggerBody()?['text'])", {}
            ),
            "Get_case": _openapi(
                "Get_case",
                DATAVERSE_API,
                DATAVERSE_API,
                "GetItem",
                {
                    "entityName": "cr6cb_evidencecases",
                    "recordId": "@outputs('Compose_CaseId')",
                    "$select": "cr6cb_evidencecaseid,cr6cb_caselabel,cr6cb_environment,cr6cb_server,cr6cb_runnumber,cr6cb_targetdate,cr6cb_processingstatus",
                },
                {"Compose_CaseId": ["Succeeded"]},
                retry_none=True,
            ),
            "Condition_Start_Ready": _condition(
                "Condition_Start_Ready",
                {
                    "equals": [
                        "@outputs('Get_case')?['body/cr6cb_processingstatus']",
                        "開始受付済み",
                    ]
                },
                _normal_path_actions(),
                {"Get_case": ["Succeeded"]},
            ),
        },
    }
    return {
        "properties": {
            "connectionReferences": {
                dataverse_key: _reference(
                    DATAVERSE_API,
                    DATAVERSE_CONNECTION_NAME,
                    DATAVERSE_REFERENCE_NAME,
                    "embedded",
                ),
                ONEDRIVE_API: _reference(
                    ONEDRIVE_API,
                    ONEDRIVE_CONNECTION_NAME,
                    ONEDRIVE_REFERENCE_NAME,
                    "invoker",
                ),
                EXCEL_API: _reference(
                    EXCEL_API,
                    EXCEL_CONNECTION_NAME,
                    EXCEL_REFERENCE_NAME,
                    "invoker",
                ),
            },
            "definition": definition,
        },
        "schemaVersion": "1.0.0.0",
    }


def _normalize_browser_documents_root(value: str) -> str:
    if not isinstance(value, str) or not value.strip():
        raise ValueError("OneDrive browser Documents root must be a non-empty HTTPS URL")
    try:
        parsed = urlsplit(value.strip())
        hostname = parsed.hostname or ""
        port = parsed.port
    except ValueError as exc:
        raise ValueError("OneDrive browser Documents root is not a valid URL") from exc

    path = parsed.path.rstrip("/")
    segments = path.split("/")
    if (
        parsed.scheme.lower() != "https"
        or not hostname
        or not re.fullmatch(
            r"[a-z0-9](?:[a-z0-9-]*[a-z0-9])?-my\.sharepoint\.com",
            hostname.lower(),
        )
        or port is not None
        or parsed.username is not None
        or parsed.password is not None
        or parsed.query
        or parsed.fragment
        or "'" in parsed.netloc
        or "'" in path
        or len(segments) != 4
        or segments[0] != ""
        or segments[1] != "personal"
        or not segments[2]
        or segments[3] != "Documents"
    ):
        raise ValueError(
            "OneDrive browser root must be an HTTPS personal SharePoint Documents path"
        )
    return urlunsplit(("https", parsed.netloc, path, "", ""))


def _find_action(actions: dict[str, Any], expected_name: str) -> dict[str, Any] | None:
    for name, action in actions.items():
        if name == expected_name:
            return action
        nested = action.get("actions", {})
        if isinstance(nested, dict):
            found = _find_action(nested, expected_name)
            if found is not None:
                return found
        else_actions = action.get("else", {}).get("actions", {})
        if isinstance(else_actions, dict):
            found = _find_action(else_actions, expected_name)
            if found is not None:
                return found
    return None


def _excelurl_copy_destination_errors(actions: dict[str, Any]) -> list[str]:
    errors: list[str] = []
    expected_path = f"@concat('{T006_FOLDER_PATH}/',outputs('Compose_CaseId'),'.xlsx')"

    destination = _find_action(actions, "Compose_DestinationPath")
    if (
        not isinstance(destination, dict)
        or destination.get("type") != "Compose"
        or destination.get("inputs") != expected_path
    ):
        errors.append("Compose_DestinationPath must match the fixed T006 output path")

    copy = _find_action(actions, "Copy_template")
    copy_inputs = copy.get("inputs", {}) if isinstance(copy, dict) else {}
    if (
        not isinstance(copy, dict)
        or copy.get("type") != "OpenApiConnection"
        or copy_inputs.get("host", {}).get("operationId") != "CopyDriveFileByPath"
        or copy_inputs.get("parameters", {}).get("destination")
        != "@outputs('Compose_DestinationPath')"
    ):
        errors.append("Copy_template must use the validated T006 output path")
    return errors


def _excelurl_destination_branch_errors(actions: dict[str, Any]) -> list[str]:
    """Keep the side-effect transaction under the one-destination true branch."""
    errors: list[str] = []
    condition = _find_action(actions, "Condition_One_Destination")
    if not isinstance(condition, dict) or condition.get("type") != "If":
        return ["Condition_One_Destination must guard the copy/write transaction"]

    success_actions = condition.get("actions", {})
    if not isinstance(success_actions, dict):
        return ["Condition_One_Destination success branch must contain the transaction actions"]

    required_actions = (
        "Copy_template",
        "Scope_Write_And_Verify",
        "Update_case_copy_unknown",
        "Update_case_postcopy_unknown",
    )
    for action_name in required_actions:
        if _find_action(success_actions, action_name) is None:
            errors.append(
                f"{action_name} must remain under Condition_One_Destination success branch"
            )
    return errors


def _excelurl_readback_gate_errors(actions: dict[str, Any]) -> list[str]:
    errors: list[str] = []
    expected_dependencies = {
        "Scope_Write_And_Verify": {"Copy_template": ["Succeeded"]},
        "Delay_for_workbook": {},
        "Replace_template_row": {"Delay_for_workbook": ["Succeeded"]},
        "Delay_before_readback": {"Replace_template_row": ["Succeeded"]},
        "Read_back_evidence": {"Delay_before_readback": ["Succeeded"]},
    }
    expected_types = {
        "Scope_Write_And_Verify": "Scope",
        "Delay_for_workbook": "Wait",
        "Replace_template_row": "OpenApiConnection",
        "Delay_before_readback": "Wait",
        "Read_back_evidence": "OpenApiConnection",
    }
    expected_operations = {
        "Replace_template_row": "PatchItem",
        "Read_back_evidence": "GetItems",
    }
    for action_name, expected_run_after in expected_dependencies.items():
        action = _find_action(actions, action_name)
        if (
            not isinstance(action, dict)
            or action.get("type") != expected_types[action_name]
            or action.get("runAfter") != expected_run_after
        ):
            errors.append(f"{action_name} must preserve the workbook write/read order")
    for action_name, expected_operation in expected_operations.items():
        action = _find_action(actions, action_name)
        operation = (
            action.get("inputs", {}).get("host", {}).get("operationId")
            if isinstance(action, dict)
            else None
        )
        if not isinstance(action, dict) or action.get("type") != "OpenApiConnection" or operation != expected_operation:
            errors.append(f"{action_name} must use the expected Excel read/write operation")

    empty_check = _find_action(actions, "Condition_Readback_Is_Empty")
    if not isinstance(empty_check, dict) or empty_check.get("type") != "If":
        return ["Excel URL candidate is missing Condition_Readback_Is_Empty"]
    scope = _find_action(actions, "Scope_Write_And_Verify")
    scope_actions = scope.get("actions", {}) if isinstance(scope, dict) else {}
    if (
        not isinstance(scope, dict)
        or scope.get("type") != "Scope"
        or not isinstance(scope_actions, dict)
        or scope_actions.get("Condition_Readback_Is_Empty") is not empty_check
    ):
        errors.append("Condition_Readback_Is_Empty must remain inside the write/verify scope")

    if empty_check.get("runAfter") != {"Read_back_evidence": ["Succeeded"]}:
        errors.append("Condition_Readback_Is_Empty must wait for the initial readback")
    if empty_check.get("expression") != {
        "equals": ["@length(body('Read_back_evidence')?['value'])", 0]
    }:
        errors.append("Condition_Readback_Is_Empty must branch on the initial readback count")

    else_branch = empty_check.get("else", {})
    else_actions = else_branch.get("actions", {}) if isinstance(else_branch, dict) else {}
    initial_match = else_actions.get("Condition_Readback_Matches")
    retry_actions = empty_check.get("actions", {})
    if not isinstance(retry_actions, dict):
        retry_actions = {}
    retry_match = retry_actions.get("Condition_Readback_Retry_Matches")
    expected_readback_parameters = {
        "source": "me",
        "drive": "@first(body('Filter_active_destinations'))?['cr6cb_driveid']",
        "file": "@outputs('Copy_template')?['body/Id']",
        "table": "Evidence",
        "$filter": "@concat('CaseId eq ''',outputs('Compose_CaseId'),'''')",
        "$select": "CaseId,LogFileName,Environment,Server,RunNumber,TargetDate,ChunkIndex,ChunkCount,LogTextPart",
        "dateTimeFormat": "ISO 8601",
    }
    for readback_name, page_size in (
        ("Read_back_evidence", 2),
        ("Read_back_evidence_retry", 3),
    ):
        readback = _find_action(actions, readback_name)
        expected_parameters = {
            **expected_readback_parameters,
            "$top": page_size,
        }
        actual_parameters = (
            readback.get("inputs", {}).get("parameters")
            if isinstance(readback, dict)
            else None
        )
        if actual_parameters != expected_parameters:
            errors.append(f"{readback_name} must read back the copied Evidence row")

    for condition_name, condition, readback_name, expected_run_after in (
        (
            "Condition_Readback_Matches",
            initial_match,
            "Read_back_evidence",
            {},
        ),
        (
            "Condition_Readback_Retry_Matches",
            retry_match,
            "Read_back_evidence_retry",
            {"Read_back_evidence_retry": ["Succeeded"]},
        ),
    ):
        if not isinstance(condition, dict) or condition.get("type") != "If":
            errors.append(f"Excel URL candidate is missing {condition_name} in its readback branch")
            continue
        if condition.get("expression") != {
            "equals": [_readback_expression(readback_name), True]
        }:
            errors.append(f"{condition_name} must require the complete matching readback")
        if condition.get("runAfter") != expected_run_after:
            errors.append(f"{condition_name} must run after its verified readback branch")

    delay = retry_actions.get("Delay_before_readback_retry")
    retry_read = retry_actions.get("Read_back_evidence_retry")
    if not isinstance(delay, dict) or delay.get("type") != "Wait" or delay.get("runAfter") != {}:
        errors.append("retry readback delay must start within the empty-result branch")
    if (
        not isinstance(retry_read, dict)
        or retry_read.get("type") != "OpenApiConnection"
        or retry_read.get("inputs", {}).get("host", {}).get("operationId") != "GetItems"
        or retry_read.get("runAfter")
        != {"Delay_before_readback_retry": ["Succeeded"]}
    ):
        errors.append("Read_back_evidence_retry must run after its delay")

    for condition_name, condition in (
        ("Condition_Readback_Matches", initial_match),
        ("Condition_Readback_Retry_Matches", retry_match),
    ):
        if _find_action(actions, condition_name) is not condition:
            errors.append(f"{condition_name} must remain in its expected readback branch")
    return errors


def _add_success_excel_url(
    actions: dict[str, Any],
    condition_name: str,
    compose_name: str,
    update_name: str,
    url_expression: str,
) -> None:
    condition = _find_action(actions, condition_name)
    if condition is None or condition.get("type") != "If":
        raise ValueError(f"required matching condition is missing: {condition_name}")
    success_actions = condition.get("actions")
    if not isinstance(success_actions, dict):
        raise ValueError(f"success branch is missing for {condition_name}")
    if compose_name in success_actions:
        raise ValueError(f"duplicate Excel URL action: {compose_name}")

    update = success_actions.get(update_name)
    if update is None or update.get("type") != "OpenApiConnection":
        raise ValueError(f"success update is missing: {update_name}")
    item_expression = update.get("inputs", {}).get("parameters", {}).get("item", "")
    if not item_expression.startswith("@"):
        raise ValueError(f"success update item is not a workflow expression: {update_name}")

    updated_actions: dict[str, Any] = {}
    for name, action in success_actions.items():
        if name == update_name:
            updated_actions[compose_name] = _compose(compose_name, url_expression, {})
            action["runAfter"] = {compose_name: ["Succeeded"]}
            action["inputs"]["parameters"]["item"] = (
                f"@addProperty({item_expression[1:]},'cr6cb_excelurl',"
                f"outputs('{compose_name}'))"
            )
        updated_actions[name] = action
    condition["actions"] = updated_actions


def build_excelurl_candidate(
    clientdata: dict[str, Any] | None = None,
    *,
    browser_documents_root: str = T006_BROWSER_DOCUMENTS_ROOT,
) -> dict[str, Any]:
    """Build a separate local WDL candidate that records the verified file URL."""
    root = _normalize_browser_documents_root(browser_documents_root)
    candidate = copy.deepcopy(build_clientdata() if clientdata is None else clientdata)
    actions = candidate["properties"]["definition"]["actions"]
    destination_errors = _excelurl_copy_destination_errors(actions)
    if destination_errors:
        raise ValueError("Excel URL candidate has an invalid destination: " + "; ".join(destination_errors))
    gate_errors = _excelurl_readback_gate_errors(actions)
    if gate_errors:
        raise ValueError("Excel URL candidate has an invalid readback gate: " + "; ".join(gate_errors))

    folder_name = T006_FOLDER_PATH.strip("/")
    if "/" in folder_name:
        raise ValueError("T006 output folder must be one URL path segment")
    folder_literal = folder_name.replace("'", "''")
    url_expression = (
        f"@concat('{root}/',uriComponent('{folder_literal}'),"
        "'/',outputs('Compose_CaseId'),'.xlsx')"
    )

    _add_success_excel_url(
        actions,
        "Condition_Readback_Matches",
        "Compose_ExcelUrl",
        "Update_case_success",
        url_expression,
    )
    _add_success_excel_url(
        actions,
        "Condition_Readback_Retry_Matches",
        "Compose_ExcelUrl_Retry",
        "Update_case_success_retry",
        url_expression,
    )
    return candidate


def _side_effect_failure_path_errors(actions: dict[str, Any]) -> list[str]:
    """Keep uncertain copy/write outcomes fail-closed in the local WDL candidate."""
    errors: list[str] = []
    side_effects = (
        ("CopyDriveFileByPath", "Copy_template"),
        ("PatchItem", "Replace_template_row"),
    )
    for operation, expected_action in side_effects:
        matching_actions = []
        for action_name, action in _all_actions(actions):
            inputs = action.get("inputs", {}) if isinstance(action, dict) else {}
            host = inputs.get("host", {}) if isinstance(inputs, dict) else {}
            if isinstance(host, dict) and host.get("operationId") == operation:
                matching_actions.append(action_name)
        if matching_actions != [expected_action]:
            errors.append(
                f"{operation} must have exactly one side-effect action ({expected_action})"
            )
        action = _find_action(actions, expected_action)
        inputs = action.get("inputs", {}) if isinstance(action, dict) else {}
        if (
            not isinstance(action, dict)
            or not isinstance(inputs, dict)
            or inputs.get("retryPolicy") != {"type": "none"}
        ):
            errors.append(f"{expected_action} must disable automatic side-effect retries")

    handlers = (
        (
            "Update_case_copy_unknown",
            {"Copy_template": ["Failed", "TimedOut"]},
            "コピー処理の結果を確認できません。出力ファイルを確認し、状態が判明するまで再実行しないでください。",
            "未確認",
        ),
        (
            "Update_case_postcopy_unknown",
            {"Scope_Write_And_Verify": ["Failed", "TimedOut"]},
            "コピー後のExcel書込・読戻しを確認できません。出力ファイルを確認し、状態が判明するまで再実行しないでください。",
            "読出不能",
        ),
    )
    for action_name, expected_run_after, reason, excel_status in handlers:
        action = _find_action(actions, action_name)
        if not isinstance(action, dict):
            errors.append(f"{action_name} must handle both failure and timeout")
            continue
        inputs = action.get("inputs", {}) if isinstance(action, dict) else {}
        host = inputs.get("host", {}) if isinstance(inputs, dict) else {}
        parameters = inputs.get("parameters", {}) if isinstance(inputs, dict) else {}
        item = parameters.get("item", "") if isinstance(parameters, dict) else ""
        if action.get("runAfter") != expected_run_after:
            errors.append(f"{action_name} must handle both failure and timeout")
        if not isinstance(host, dict) or host.get("operationId") != "UpdateOnlyRecord":
            errors.append(f"{action_name} must use a non-upsert case update")
        if item != _failure_item("結果不明", reason, excel_status):
            errors.append(f"{action_name} must record an unknown outcome and prohibit rerun")
    return errors


def validate_excelurl_candidate(clientdata: dict[str, Any]) -> list[str]:
    errors = validate_clientdata(clientdata)
    if errors:
        return errors

    actions = clientdata["properties"]["definition"]["actions"]
    errors.extend(_excelurl_copy_destination_errors(actions))
    errors.extend(_excelurl_destination_branch_errors(actions))
    errors.extend(_excelurl_readback_gate_errors(actions))
    errors.extend(_side_effect_failure_path_errors(actions))
    expected_successes = (
        ("Condition_Readback_Matches", "Compose_ExcelUrl", "Update_case_success"),
        (
            "Condition_Readback_Retry_Matches",
            "Compose_ExcelUrl_Retry",
            "Update_case_success_retry",
        ),
    )
    success_update_names = {update for _, _, update in expected_successes}
    for condition_name, compose_name, update_name in expected_successes:
        condition = _find_action(actions, condition_name)
        if condition is None or condition.get("type") != "If":
            errors.append(f"Excel URL candidate is missing {condition_name}")
            continue
        success_actions = condition.get("actions", {})
        compose = success_actions.get(compose_name)
        update = success_actions.get(update_name)
        if not isinstance(compose, dict) or compose.get("type") != "Compose":
            errors.append(f"Excel URL must be composed only in {condition_name} success branch")
            continue
        if compose.get("runAfter") != {}:
            errors.append(f"{compose_name} must start only after its readback condition succeeds")
        expression = compose.get("inputs", "")
        expected_folder = T006_FOLDER_PATH.strip("/")
        prefix = "@concat('"
        root_literal = ""
        if isinstance(expression, str) and expression.startswith(prefix):
            root_literal = expression[len(prefix) :].split("/',uriComponent(", 1)[0]
        try:
            normalized_root = _normalize_browser_documents_root(root_literal)
            expected_expression = (
                f"@concat('{normalized_root}/',uriComponent('{expected_folder}'),"
                "'/',outputs('Compose_CaseId'),'.xlsx')"
            )
            if normalized_root != root_literal or expression != expected_expression:
                errors.append(f"{compose_name} must use the exact T006 folder and caseId.xlsx path")
        except ValueError:
            errors.append(f"{compose_name} browser root is invalid")

        if not isinstance(update, dict):
            errors.append(f"Excel URL success update is missing: {update_name}")
            continue
        if update.get("runAfter") != {compose_name: ["Succeeded"]}:
            errors.append(f"{update_name} must wait for {compose_name}")
        item = update.get("inputs", {}).get("parameters", {}).get("item", "")
        if f"'cr6cb_excelurl',outputs('{compose_name}')" not in item:
            errors.append(f"{update_name} must store its composed Excel URL")

    url_updates: set[str] = set()
    for action_name, action in _all_actions(actions):
        if action.get("type") != "OpenApiConnection":
            continue
        if action.get("inputs", {}).get("host", {}).get("operationId") != "UpdateOnlyRecord":
            continue
        item = action.get("inputs", {}).get("parameters", {}).get("item", "")
        if "cr6cb_excelurl" in item:
            url_updates.add(action_name)
    if url_updates != success_update_names:
        errors.append("cr6cb_excelurl may be written only by the two verified success updates")

    if any(
        operation in {"CreateShareLinkV2", "CreateShareLinkByPathV2"}
        for operation in (action.get("inputs", {}).get("host", {}).get("operationId")
                          for _, action in _all_actions(actions)
                          if action.get("type") == "OpenApiConnection")
    ):
        errors.append("Excel URL candidate must not create sharing links")
    return errors


def build_workflow_body(clientdata: dict[str, Any] | None = None) -> dict[str, Any]:
    candidate = build_clientdata() if clientdata is None else clientdata
    return {
        "category": 5,
        "name": "架空ログ証跡_件別Excel転記",
        "type": 1,
        "description": "One accepted case per run: validate its attached log, copy the T006 workbook, write one Evidence row, read it back, then update the case status.",
        "primaryentity": "none",
        "clientdata": json.dumps(candidate, ensure_ascii=False, separators=(",", ":")),
    }


def build_api_request(clientdata: dict[str, Any] | None = None) -> dict[str, Any]:
    return {
        "status": "local preview; not posted",
        "method": "POST",
        "target": f"{ORGANIZATION_URL.rstrip('/')}/api/data/v9.2/workflows",
        "body": build_workflow_body(clientdata),
        "initial_state": "Draft/Off by platform default; no statecode/statuscode is sent",
    }


def build_status() -> dict[str, Any]:
    return {
        "status": "local definition artifact; deployment and runtime status are tracked in docs/TASKS.md",
        "scope": [
            "Power Apps (V2) caseId input",
            "Read one case and require processingstatus=開始受付済み",
            "Require exactly one attached document note",
            "Compare log date, environment, server, and run number with the case",
            "Require exactly one active destination mapping matching environment/server and the T006 folder",
            "Copy the T006 workbook to a fixed caseId filename with overwrite=false",
            "Replace the template Evidence row, read it back, then mark 転記済み / 全文一致",
        ],
        "static_validation": "passed",
        "verified_from_current_environment": [
            "All three connection references and connections are present in the Developer environment list; connection health was not tested",
            "Case and destination entity names/fields and T006 OneDrive item identifiers were supplied by read-only environment checks",
            "Current connector operation IDs and parameter names are documented by Microsoft Learn",
            "The stored T002 flow confirms the CopyDriveFileByPath and Excel PatchItem action host/input structure; source uses the read-checked T006 template path",
        ],
        "not_implemented": [
            "Recovery from failures outside the explicit copy/write/readback scopes; failure to update Dataverse status can leave a stale state",
            "Concurrent-start locking and attempt/request identifiers",
            "Long-log chunking or logs longer than 30000 characters",
            "Writing excelurl; a share link is intentionally not created, and Copy output WebUrl is unconfirmed",
            "Runtime verification of the Power Apps (V2) trigger serialization and connector operation execution",
            "Power Automate Designer save/readback and execution of either approved fictitious log",
        ],
        "known_behavior": [
            "Copy and Excel write actions use retryPolicy=none. An empty initial readback triggers one explicit delayed, read-only GetItems requery; this is not a copy/write retry, and unresolved results remain 結果不明.",
            "Case ID is the fixed output filename; Copy uses overwrite=false. If a prior copy exists, the action fails and the flow does not retry.",
            "Pre-copy validation failures are marked 停止 with a reason. Copy/write/readback failures are marked 結果不明 with a reason that says not to rerun until checked.",
            "Review fields transfercheck, outcomejudgment, reviewcomment, reviewstatus, and reviewreason are never written.",
            "A successful transfer stores processingstatus and excelcheckstatus only; excelurl remains unchanged.",
        ],
        "sources": [
            "https://learn.microsoft.com/en-us/power-automate/manage-flows-with-code",
            "https://learn.microsoft.com/en-us/connectors/commondataserviceforapps/",
            "https://learn.microsoft.com/en-us/connectors/onedriveforbusiness/",
            "https://learn.microsoft.com/en-us/connectors/excelonlinebusiness/",
        ],
    }


def _all_actions(actions: dict[str, Any]):
    for name, action in actions.items():
        yield name, action
        if isinstance(action, dict):
            nested = action.get("actions", {})
            if isinstance(nested, dict):
                yield from _all_actions(nested)
            else_actions = action.get("else", {}).get("actions", {})
            if isinstance(else_actions, dict):
                yield from _all_actions(else_actions)


def _has_cycle(value: Any, active: set[int] | None = None, done: set[int] | None = None) -> bool:
    if not isinstance(value, (dict, list)):
        return False
    active = set() if active is None else active
    done = set() if done is None else done
    identity = id(value)
    if identity in active:
        return True
    if identity in done:
        return False
    active.add(identity)
    children = value.values() if isinstance(value, dict) else value
    if any(_has_cycle(child, active, done) for child in children):
        return True
    active.remove(identity)
    done.add(identity)
    return False


def _check_run_after_scopes(
    actions: dict[str, Any], errors: list[str], parent_path: str = "actions"
) -> None:
    names = set(actions)
    for name, action in actions.items():
        if not isinstance(action, dict):
            continue
        run_after = action.get("runAfter", {})
        if not isinstance(run_after, dict):
            errors.append(f"{parent_path}.{name} runAfter must be an object")
        else:
            for dependency in run_after:
                if dependency not in names:
                    errors.append(
                        f"{parent_path}.{name} runAfter references out-of-scope action {dependency}"
                    )
        nested = action.get("actions", {})
        if isinstance(nested, dict):
            _check_run_after_scopes(nested, errors, f"{parent_path}.{name}.actions")
        else_actions = action.get("else", {}).get("actions", {})
        if isinstance(else_actions, dict):
            _check_run_after_scopes(else_actions, errors, f"{parent_path}.{name}.else.actions")


def validate_clientdata(clientdata: dict[str, Any]) -> list[str]:
    errors: list[str] = []
    try:
        props = clientdata["properties"]
        refs = props["connectionReferences"]
        definition = props["definition"]
        trigger = definition["triggers"]["manual"]
        actions = definition["actions"]
    except (KeyError, TypeError) as exc:
        return [f"required WDL structure missing: {exc}"]

    if _has_cycle(clientdata):
        return ["WDL object graph contains a cycle"]
    _check_run_after_scopes(actions, errors)

    if clientdata.get("schemaVersion") != "1.0.0.0":
        errors.append("unsupported or missing clientdata schemaVersion")
    schema = trigger.get("inputs", {}).get("schema", {})
    if trigger.get("type") != "Request" or trigger.get("kind") != "PowerAppV2":
        errors.append("trigger must be Request / PowerAppV2")
    if schema.get("required") != ["text"]:
        errors.append("Power Apps trigger must require exactly one text input")
    if schema.get("properties", {}).get("text", {}).get("title") != "caseId":
        errors.append("Power Apps trigger text input must be named caseId")

    if actions.get("Compose_CaseId", {}).get("inputs") != "@toLower(triggerBody()?['text'])":
        errors.append("Compose_CaseId must normalize the trigger text input")
    get_case = actions.get("Get_case", {})
    get_host = get_case.get("inputs", {}).get("host", {})
    get_parameters = get_case.get("inputs", {}).get("parameters", {})
    if get_host.get("operationId") != "GetItem":
        errors.append("Get_case must use Dataverse GetItem")
    if get_parameters.get("entityName") != "cr6cb_evidencecases":
        errors.append("Get_case must target the case entity set")
    if get_parameters.get("recordId") != "@outputs('Compose_CaseId')":
        errors.append("Get_case must use the composed caseId")
    start_condition = actions.get("Condition_Start_Ready", {})
    if start_condition.get("type") != "If" or "開始受付済み" not in json.dumps(start_condition, ensure_ascii=False):
        errors.append("flow must guard the initial transfer on 開始受付済み")

    validation_reason = _find_action(actions, "Compose_LogValidationReason")
    if (
        validation_reason is None
        or validation_reason.get("inputs") != _log_validation_reason_expression()
        or validation_reason.get("runAfter") != {"Compose_LogLines": ["Succeeded"]}
    ):
        errors.append("log validation must compute a specific reason after splitting the log")
    is_valid_log = _find_action(actions, "Compose_IsValidLog")
    if (
        is_valid_log is None
        or is_valid_log.get("inputs") != "@equals(outputs('Compose_LogValidationReason'),'')"
        or is_valid_log.get("runAfter") != {"Compose_LogValidationReason": ["Succeeded"]}
    ):
        errors.append("log acceptance must depend on the specific validation reason")
    stop_log = _find_action(actions, "Update_case_stop_log_invalid")
    stop_log_item = (
        stop_log.get("inputs", {}).get("parameters", {}).get("item", "")
        if isinstance(stop_log, dict)
        else ""
    )
    if "outputs('Compose_LogValidationReason')" not in stop_log_item:
        errors.append("invalid-log stop must persist its specific validation reason")
    log_text = _find_action(actions, "Compose_LogText")
    unreadable_log_stop = _find_action(actions, "Update_case_stop_log_unreadable")
    if (
        log_text is None
        or log_text.get("inputs")
        != "@base64ToString(first(body('List_attached_notes')?['value'])?['documentbody'])"
    ):
        errors.append("attached log text must be decoded from its documentbody")
    unreadable_item = (
        unreadable_log_stop.get("inputs", {}).get("parameters", {}).get("item", "")
        if isinstance(unreadable_log_stop, dict)
        else ""
    )
    if (
        unreadable_log_stop is None
        or unreadable_log_stop.get("runAfter")
        != {"Compose_LogText": ["Failed", "TimedOut"]}
        or "cr6cb_processingstatus','停止'" not in unreadable_item
        or "本文データが欠落または不正" not in unreadable_item
    ):
        errors.append("decode failure and timeout must record a stopped unreadable-log reason")

    expected_references = {
        DATAVERSE_API: (DATAVERSE_CONNECTION_NAME, DATAVERSE_REFERENCE_NAME, "embedded"),
        ONEDRIVE_API: (ONEDRIVE_CONNECTION_NAME, ONEDRIVE_REFERENCE_NAME, "invoker"),
        EXCEL_API: (EXCEL_CONNECTION_NAME, EXCEL_REFERENCE_NAME, "invoker"),
    }
    for api_name, (connection_name, logical_name, runtime_source) in expected_references.items():
        reference = refs.get(api_name, {})
        connection = reference.get("connection", {})
        if (
            reference.get("api", {}).get("name") != api_name
            or connection.get("name") != connection_name
            or connection.get("connectionReferenceLogicalName") != logical_name
            or reference.get("runtimeSource") != runtime_source
        ):
            errors.append(f"connection reference mismatch for {api_name}")

    operations: dict[str, list[str]] = {}
    for action_name, action in _all_actions(actions):
        if action.get("type") != "OpenApiConnection":
            continue
        host = action.get("inputs", {}).get("host", {})
        api_id = host.get("apiId", "")
        api_name = api_id.rsplit("/", 1)[-1]
        connection_key = host.get("connectionName")
        operation = host.get("operationId")
        operations.setdefault(operation, []).append(action_name)
        if api_name not in refs or connection_key not in refs:
            errors.append(f"action {action_name} references an unknown connector connection")
        elif refs[api_name].get("api", {}).get("name") != api_name:
            errors.append(f"action {action_name} connector API does not match its reference")
        elif connection_key != api_name:
            errors.append(f"action {action_name} host connection key does not match its API reference")
        elif refs[api_name].get("connection", {}).get("name") in (None, ""):
            errors.append(f"action {action_name} connection ID is missing")
        if operation in {"CopyDriveFile", "CopyDriveFileByPath"}:
            params = action.get("inputs", {}).get("parameters", {})
            if params.get("overwrite") is not False:
                errors.append("template copy must explicitly set overwrite=false")
        if operation == "UpdateRecord":
            errors.append(f"action {action_name} must use UpdateOnlyRecord, not upsert UpdateRecord")

    required_operations = {"GetItem", "ListRecords", "UpdateOnlyRecord", "CopyDriveFileByPath", "PatchItem", "GetItems"}
    missing = sorted(required_operations - operations.keys())
    if missing:
        errors.append("normal path is missing connector operations: " + ", ".join(missing))
    if not operations.get("UpdateOnlyRecord") or len(operations["UpdateOnlyRecord"]) < 2:
        errors.append("normal path must update processing and successful case states")
    if operations.get("CreateShareLinkV2") or operations.get("CreateShareLinkByPathV2"):
        errors.append("candidate must not create or broaden sharing links")
    serialized = json.dumps(clientdata, ensure_ascii=False)
    if re.search(r"<[A-Za-z0-9 _-]+>", serialized):
        errors.append("unresolved placeholder found")
    return errors


def write_artifacts() -> None:
    candidate = build_clientdata()
    errors = validate_clientdata(candidate)
    if errors:
        raise ValueError("Candidate failed static validation: " + "; ".join(errors))
    (HERE / "flow-definition.candidate.json").write_text(
        json.dumps(candidate, ensure_ascii=False, indent=2) + "\n", encoding="utf-8"
    )
    workflow_body = build_workflow_body(candidate)
    (HERE / "workflow-create-body.json").write_text(
        json.dumps(workflow_body, ensure_ascii=False, indent=2) + "\n", encoding="utf-8"
    )
    (HERE / "workflow-create-api-request.json").write_text(
        json.dumps(build_api_request(candidate), ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )
    (HERE / "flow-candidate-status.json").write_text(
        json.dumps(build_status(), ensure_ascii=False, indent=2) + "\n", encoding="utf-8"
    )


def write_excelurl_candidate(
    browser_documents_root: str = T006_BROWSER_DOCUMENTS_ROOT,
) -> Path:
    candidate = build_excelurl_candidate(
        browser_documents_root=browser_documents_root
    )
    errors = validate_excelurl_candidate(candidate)
    if errors:
        raise ValueError("Excel URL candidate failed static validation: " + "; ".join(errors))
    output = HERE / "flow-definition.excelurl-candidate.json"
    output.write_text(
        json.dumps(candidate, ensure_ascii=False, indent=2) + "\n", encoding="utf-8"
    )
    return output


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Build local Flow definition candidates.")
    parser.add_argument(
        "--excelurl-candidate",
        action="store_true",
        help="write a separate candidate that records a verified Excel browser URL",
    )
    parser.add_argument(
        "--browser-documents-root",
        help="HTTPS OneDrive personal-site Documents root; defaults to the T006 site",
    )
    args = parser.parse_args()
    if args.excelurl_candidate:
        output = write_excelurl_candidate(
            args.browser_documents_root or T006_BROWSER_DOCUMENTS_ROOT
        )
        print(
            "Generated and statically validated local Excel URL candidate "
            f"{output.name}; no cloud calls made."
        )
    else:
        if args.browser_documents_root:
            parser.error("--browser-documents-root requires --excelurl-candidate")
        write_artifacts()
        print("Generated and statically validated local WDL candidate; no cloud calls made.")
