"""Audit and prepare a minimal Flow PATCH for Excel datetime normalization."""

import json
import re
from pathlib import Path


HERE = Path(__file__).resolve().parent
LIVE = HERE / "flow-before-readback-fix.json"
CANDIDATE = HERE.parent / "flow-implementation" / "flow-definition.mq-local-candidate.json"
PATCH = HERE / "flow-datetime-patch-body.json"


def changes(before, after, path=""):
    if isinstance(before, dict) and isinstance(after, dict):
        for key in sorted(before.keys() | after.keys()):
            next_path = f"{path}/{key}"
            if key not in before or key not in after:
                yield next_path
            else:
                yield from changes(before[key], after[key], next_path)
    elif isinstance(before, list) and isinstance(after, list):
        for index in range(max(len(before), len(after))):
            next_path = f"{path}/{index}"
            if index >= len(before) or index >= len(after):
                yield next_path
            else:
                yield from changes(before[index], after[index], next_path)
    elif before != after:
        yield path


live = json.loads(LIVE.read_text(encoding="utf-8-sig"))
candidate = json.loads(CANDIDATE.read_text(encoding="utf-8-sig"))
assert live["workflowid"] == "ef881fbc-dcb8-f111-b377-7ced8d3141aa"
assert live["resourceid"] == "ccbc5642-9cce-b1e9-07f5-8174f938bab4"
assert live["statecode"] == 1 and live["statuscode"] == 2
old = json.loads(live["clientdata"])
paths = list(changes(old, candidate))
print("Current ETag:", live["@odata.etag"])
print("Semantic paths changed:", len(paths))
for path in paths:
    print(path)
assert paths, "Candidate already deployed"
assert len(paths) == 3, paths
for path in paths:
    assert path.endswith("/expression/equals/0"), path
    assert "Condition_Readback_Matches" in path or "Condition_Readback_Retry_Matches" in path, path
    keys = [part for part in path.split("/") if part]
    old_value, new_value = old, candidate
    for key in keys:
        if key.isdigit():
            key = int(key)
        old_value, new_value = old_value[key], new_value[key]
    normalized, count = re.subn(
        r"equals\((first\(body\('[^']+'\)\?\['value'\]\)\?\['ReceivedAtJst'\]),convertTimeZone",
        r"equals(formatDateTime(\1,'yyyy-MM-dd HH:mm:ss'),convertTimeZone",
        old_value,
    )
    assert count in (1, 2) and normalized == new_value, path
serialized = json.dumps(candidate, ensure_ascii=False, separators=(",", ":"))
PATCH.write_text(json.dumps({"clientdata": serialized}, ensure_ascii=False), encoding="utf-8")
print("Prepared clientdata PATCH; no cloud update made")
