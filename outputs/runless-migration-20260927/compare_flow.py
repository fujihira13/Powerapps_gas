"""Print semantic paths changed by the runless MQ flow candidate; no API calls."""

import json
from pathlib import Path


BASE = Path(__file__).resolve().parents[1]
BEFORE = Path(__file__).with_name("flow-before.json")
CANDIDATE = BASE / "flow-implementation" / "flow-definition.mq-local-candidate.json"


def changes(before, after, path=""):
    if isinstance(before, dict) and isinstance(after, dict):
        for key in sorted(before.keys() | after.keys()):
            next_path = f"{path}/{key}"
            if key not in before or key not in after:
                yield next_path
            else:
                yield from changes(before[key], after[key], next_path)
    elif isinstance(before, list) and isinstance(after, list):
        for i in range(max(len(before), len(after))):
            next_path = f"{path}/{i}"
            if i >= len(before) or i >= len(after):
                yield next_path
            else:
                yield from changes(before[i], after[i], next_path)
    elif before != after:
        yield path


live = json.loads(BEFORE.read_text(encoding="utf-8-sig"))
old = json.loads(live["clientdata"])
new = json.loads(CANDIDATE.read_text(encoding="utf-8-sig"))
paths = list(changes(old, new))
print(f"Semantic paths changed: {len(paths)}")
for path in paths:
    print(path)
    if path.endswith("/scriptId"):
        keys = [part for part in path.split("/") if part]
        old_value = old
        new_value = new
        for key in keys:
            old_value = old_value[key]
            new_value = new_value[key]
        print(f"  live={old_value} candidate={new_value}")
