"""Build Dataverse column metadata for the T-006 preparation tables."""

import json
from pathlib import Path


BASE = Path(__file__).parent / "column-payloads"
BASE.mkdir(exist_ok=True)


def label(value):
    return {
        "@odata.type": "Microsoft.Dynamics.CRM.Label",
        "LocalizedLabels": [{"Label": value, "LanguageCode": 1041}],
    }


def column(schema, display, kind, *, required=True, length=None):
    item = {
        "@odata.type": f"Microsoft.Dynamics.CRM.{kind}AttributeMetadata",
        "AttributeType": kind,
        "AttributeTypeName": {"Value": f"{kind}Type"},
        "SchemaName": schema,
        "DisplayName": label(display),
        "RequiredLevel": {"Value": "ApplicationRequired" if required else "None"},
    }
    if kind == "String":
        item.update({"FormatName": {"Value": "Text"}, "MaxLength": length})
    elif kind == "Integer":
        item.update({"Format": "None", "MinValue": 1, "MaxValue": 2147483647})
    elif kind == "DateTime":
        item.update({"Format": "DateOnly", "DateTimeBehavior": {"Value": "DateOnly"}})
    elif kind == "Boolean":
        item.update({
            "DefaultValue": True,
            "OptionSet": {
                "TrueOption": {"Value": 1, "Label": label("有効")},
                "FalseOption": {"Value": 0, "Label": label("無効")},
                "OptionSetType": "Boolean",
            },
        })
    return item


COLUMNS = {
    "case-environment": column("cr6cb_Environment", "環境", "String", length=100),
    "case-server": column("cr6cb_Server", "サーバー", "String", length=100),
    "case-run-number": column("cr6cb_RunNumber", "実行回", "Integer"),
    "case-target-date": column("cr6cb_TargetDate", "対象処理日", "DateTime"),
    "destination-environment": column("cr6cb_Environment", "環境", "String", length=100),
    "destination-server": column("cr6cb_Server", "サーバー", "String", length=100),
    "destination-drive-id": column("cr6cb_DriveId", "ドライブID", "String", length=255),
    "destination-folder-id": column("cr6cb_FolderId", "フォルダーID", "String", length=100),
    "destination-active": column("cr6cb_IsActive", "有効", "Boolean", required=False),
}

for name, payload in COLUMNS.items():
    (BASE / f"{name}.json").write_text(
        json.dumps(payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8"
    )
