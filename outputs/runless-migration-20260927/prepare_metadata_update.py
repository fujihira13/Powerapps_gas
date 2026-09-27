"""Prepare the reviewed Dataverse metadata update from live read-only snapshots.

This script writes a request body only. It does not contact Dataverse.
"""

import json
from pathlib import Path


HERE = Path(__file__).resolve().parent
KEY_ID = "8818f513-9eb8-f111-b377-7ced8d3141aa"
COLUMN_ID = "c37d9ebe-9db8-f111-b377-7ced8d3141aa"
KEY_COLUMNS = {
    "cr6cb_environment",
    "cr6cb_server",
    "cr6cb_runnumber",
    "cr6cb_targetdate",
}


def read_json(name: str) -> dict:
    return json.loads((HERE / name).read_text(encoding="utf-8-sig"))


def main() -> None:
    keys = read_json("key-before.json")["value"]
    assert len(keys) == 1, "Unexpected key count; inspect before changing schema"
    key = keys[0]
    assert key["MetadataId"] == KEY_ID
    assert key["SchemaName"] == "cr6cb_EvidenceCaseBusinessKey"
    assert set(key["KeyAttributes"]) == KEY_COLUMNS
    assert key["EntityKeyIndexStatus"] == "Active"
    assert key["IsManaged"] is False

    column = read_json("runnumber-before.json")
    assert column["MetadataId"] == COLUMN_ID
    assert column["LogicalName"] == "cr6cb_runnumber"
    assert column["RequiredLevel"]["Value"] == "ApplicationRequired"
    assert column["RequiredLevel"]["CanBeChanged"] is True
    assert column["IsManaged"] is False

    column.pop("@odata.context", None)
    column["@odata.type"] = "Microsoft.Dynamics.CRM.IntegerAttributeMetadata"
    column["RequiredLevel"]["Value"] = "None"
    output = HERE / "runnumber-optional.put.json"
    output.write_text(
        json.dumps(column, ensure_ascii=False, indent=2) + "\n", encoding="utf-8"
    )
    print(f"Prepared {output.name}; no Dataverse changes made")


if __name__ == "__main__":
    main()
