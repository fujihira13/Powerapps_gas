"""Build the approved workflow PATCH body without contacting Microsoft services.

The generated body contains tenant connection references and is gitignored.
"""

import json
from pathlib import Path


HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[1]
SOURCE = HERE / "flow-before.json"
CANDIDATE = ROOT / "outputs" / "flow-implementation" / "flow-definition.mq-local-candidate.json"
OUTPUT = HERE / "flow-patch-body.json"


def main() -> None:
    before = json.loads(SOURCE.read_text(encoding="utf-8-sig"))
    candidate = json.loads(CANDIDATE.read_text(encoding="utf-8-sig"))
    assert before["workflowid"] == "ef881fbc-dcb8-f111-b377-7ced8d3141aa"
    assert before["resourceid"] == "ccbc5642-9cce-b1e9-07f5-8174f938bab4"
    assert before["statecode"] == 1 and before["statuscode"] == 2
    assert before["@odata.etag"] == 'W/"3712193"'
    serialized = json.dumps(candidate, ensure_ascii=False, separators=(",", ":"))
    assert "__SELECT_MQ_" not in serialized
    assert "ReceivedAtJst" in serialized
    assert "evidence-template-received-at-jst.xlsx" in serialized
    body = {"clientdata": serialized}
    OUTPUT.write_text(json.dumps(body, ensure_ascii=False, separators=(",", ":")), encoding="utf-8")
    print("Prepared minimal clientdata PATCH body; no cloud update made")


if __name__ == "__main__":
    main()
