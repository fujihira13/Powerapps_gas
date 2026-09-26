"""Build fictional environment/server mappings for the approved T-006 folder."""

import json
from pathlib import Path


ROOT = Path(__file__).parents[2]
SAMPLES = ROOT / "samples" / "t006"
OUT = Path(__file__).parent / "destination-rows"
OUT.mkdir(exist_ok=True)

DRIVE_ID = "b!sJQ6Cjnu_0-V2PVDfBquhZ3w-BDqyatNkcUB825NHJR8Ir9o1-n1Qa3iOm8G0eik"
FOLDER_ID = "01VTXCECE5BP476QXS7RFIAAAMC5QNGY6X"

for sample in sorted(SAMPLES.glob("*.txt")):
    values = {}
    for line in sample.read_text(encoding="utf-8").splitlines()[:5]:
        if ": " in line:
            key, value = line.split(": ", 1)
            values[key] = value
    # The screen must resolve a destination before parsing the log body.
    # This fictional case deliberately omits the server line in the log;
    # the screen selects the registered H pair so the parser can catch it.
    if sample.stem == "missing-identifier":
        values["サーバー"] = "架空サーバーH"
    if not values.get("環境") or not values.get("サーバー"):
        continue
    payload = {
        "cr6cb_destinationlabel": f"{values['環境']} / {values['サーバー']}",
        "cr6cb_environment": values["環境"],
        "cr6cb_server": values["サーバー"],
        "cr6cb_driveid": DRIVE_ID,
        "cr6cb_folderid": FOLDER_ID,
        "cr6cb_isactive": True,
    }
    (OUT / f"{sample.stem}.json").write_text(
        json.dumps(payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8"
    )
