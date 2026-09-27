"""Build local Dataverse column metadata payloads for the MQ diagnostics.

This script only writes JSON files. It never calls Dataverse or any other API.
"""

from __future__ import annotations

import json
from pathlib import Path


BASE = Path(__file__).parent / "dataverse-column-payloads"


def label(value: str) -> dict:
    return {
        "@odata.type": "Microsoft.Dynamics.CRM.Label",
        "LocalizedLabels": [{"Label": value, "LanguageCode": 1041}],
    }


def column(
    schema_name: str,
    display_name: str,
    kind: str,
    *,
    max_length: int | None = None,
    min_value: int | None = None,
    max_value: int | None = None,
) -> dict:
    metadata = {
        "@odata.type": f"Microsoft.Dynamics.CRM.{kind}AttributeMetadata",
        "AttributeType": kind,
        "AttributeTypeName": {"Value": f"{kind}Type"},
        "SchemaName": schema_name,
        "DisplayName": label(display_name),
        "RequiredLevel": {"Value": "None"},
    }
    if kind == "String":
        if max_length is None:
            raise ValueError("String columns require an explicit max_length")
        metadata.update({"FormatName": {"Value": "Text"}, "MaxLength": max_length})
    elif kind == "Memo":
        if max_length is None:
            raise ValueError("Memo columns require an explicit max_length")
        metadata.update({"Format": "Text", "MaxLength": max_length})
    elif kind == "Integer":
        if min_value is None or max_value is None:
            raise ValueError("Integer columns require explicit min_value and max_value")
        metadata.update({"Format": "None", "MinValue": min_value, "MaxValue": max_value})
    else:
        raise ValueError(f"Unsupported MQ column type: {kind}")
    return metadata


COLUMNS = {
    "mqterminalstatus": column(
        "cr6cb_Mqterminalstatus", "MQ終端状態", "String", max_length=16
    ),
    "mqexpectedcount": column(
        "cr6cb_Mqexpectedcount", "MQ予定件数", "Integer", min_value=0, max_value=2147483647
    ),
    "mqloggedcount": column(
        "cr6cb_Mqloggedcount", "MQ記録件数", "Integer", min_value=0, max_value=2147483647
    ),
    "mqmissingcount": column(
        "cr6cb_Mqmissingcount", "MQ欠落件数", "Integer", min_value=0, max_value=2147483647
    ),
    "mqmissingids": column(
        "cr6cb_Mqmissingids", "MQ欠落ID", "Memo", max_length=16384
    ),
    "mqcomparisonstatus": column(
        "cr6cb_Mqcomparisonstatus", "MQ比較状態", "String", max_length=20
    ),
    "mqresulttext": column(
        "cr6cb_Mqresulttext", "MQ結果テキスト", "Memo", max_length=30000
    ),
}


def build_payloads() -> dict[str, dict]:
    """Return fresh optional-column metadata payloads keyed by logical name."""
    return {logical_name: dict(payload) for logical_name, payload in COLUMNS.items()}


def write_payloads(base: Path = BASE) -> list[Path]:
    base.mkdir(parents=True, exist_ok=True)
    written = []
    for logical_name, payload in build_payloads().items():
        path = base / f"{logical_name}.json"
        path.write_text(json.dumps(payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
        written.append(path)
    return written


if __name__ == "__main__":
    for output in write_payloads():
        print(output)
