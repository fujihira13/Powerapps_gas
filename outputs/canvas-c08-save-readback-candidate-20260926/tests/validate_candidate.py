from pathlib import Path
from collections import Counter
import re

import yaml


ROOT = Path(__file__).resolve().parents[1]
BASE = ROOT.parent / "canvas-live-readback-20260926-demo-audit"
APP = ROOT / "workspace"


def parse_app(directory):
    paths = sorted(directory.glob("*.pa.yaml"))
    assert len(paths) == 6, f"expected 6 YAML files, found {len(paths)} in {directory}"
    return {path.name: yaml.safe_load(path.read_text(encoding="utf-8-sig")) for path in paths}


def changed_paths(before, after, path=""):
    if isinstance(before, dict) and isinstance(after, dict):
        result = []
        for key in before.keys() | after.keys():
            child = f"{path}.{key}" if path else str(key)
            if key not in before or key not in after:
                result.append(child)
            else:
                result.extend(changed_paths(before[key], after[key], child))
        return result
    if isinstance(before, list) and isinstance(after, list):
        if len(before) != len(after):
            return [path]
        result = []
        for index, (left, right) in enumerate(zip(before, after)):
            result.extend(changed_paths(left, right, f"{path}[{index}]"))
        return result
    return [] if before == after else [path]


def assert_balanced_powerfx(formula):
    pairs = {")": "(", "}": "{", "]": "["}
    opening = set(pairs.values())
    stack = []
    in_string = False
    index = 0
    while index < len(formula):
        char = formula[index]
        if in_string:
            if char == '"':
                if index + 1 < len(formula) and formula[index + 1] == '"':
                    index += 2
                    continue
                in_string = False
        elif char == '"':
            in_string = True
        elif char in opening:
            stack.append(char)
        elif char in pairs:
            assert stack and stack.pop() == pairs[char], f"mismatched {char} at offset {index}"
        index += 1
    assert not in_string, "unterminated Power Fx string"
    assert not stack, f"unclosed Power Fx delimiters: {stack}"


def call_arguments(formula, start):
    open_paren = formula.find("(", start)
    assert open_paren >= 0
    depth = 1
    in_string = False
    index = open_paren + 1
    arg_start = index
    args = []
    while index < len(formula):
        char = formula[index]
        if in_string:
            if char == '"':
                if index + 1 < len(formula) and formula[index + 1] == '"':
                    index += 2
                    continue
                in_string = False
        elif char == '"':
            in_string = True
        elif char in "({[":
            depth += 1
        elif char in ")}]":
            depth -= 1
            if depth == 0:
                args.append(formula[arg_start:index].strip())
                return args
        elif char == "," and depth == 1:
            args.append(formula[arg_start:index].strip())
            arg_start = index + 1
        index += 1
    raise AssertionError("unterminated function call")


def if_calls(formula):
    return [call_arguments(formula, match.start()) for match in re.finditer(r"\bIf\s*\(", formula)]


def find_control(tree, name):
    if isinstance(tree, dict):
        if name in tree:
            return tree[name]
        for value in tree.values():
            found = find_control(value, name)
            if found is not None:
                return found
    elif isinstance(tree, list):
        for value in tree:
            found = find_control(value, name)
            if found is not None:
                return found
    return None


baseline = parse_app(BASE)
candidate = parse_app(APP)
assert baseline.keys() == candidate.keys()

diffs = changed_paths(baseline["Screen1.pa.yaml"], candidate["Screen1.pa.yaml"])
expected_changes = {
    "Form1.Properties.OnFailure",
    "Form1.Properties.OnSuccess",
    "btnT001Save.Properties.DisplayMode",
    "btnT001Save.Properties.OnSelect",
    "実行回数_DataCard1.Properties.Update",
    "ErrorMessage4.Properties.Text",
    "ErrorMessage4.Properties.Visible",
    "btnT001Stage.Properties.OnSelect",
    "btnT001Select.Properties.AccessibleLabel",
    "btnT001Select.Properties.Text",
    "btnT001Select.Properties.OnSelect",
    "btnT001CancelItem.Properties.DisplayMode",
    "btnT001CancelItem.Properties.OnSelect",
}
normalized_diffs = set()
for path in diffs:
    matches = [expected for expected in expected_changes if expected in path]
    assert len(matches) == 1, path
    normalized_diffs.add(matches[0])
assert normalized_diffs == expected_changes and len(diffs) == len(expected_changes), diffs
for name in candidate.keys() - {"Screen1.pa.yaml"}:
    assert baseline[name] == candidate[name], f"unexpected change in {name}"

screen = candidate["Screen1.pa.yaml"]["Screens"]["Screen1"]
base_screen = baseline["Screen1.pa.yaml"]["Screens"]["Screen1"]
form_props = find_control(screen, "Form1")["Properties"]
save_button = find_control(screen, "btnT001Save")["Properties"]
cancel_button = find_control(screen, "btnT001CancelItem")["Properties"]
intake_button = find_control(screen, "btnT001Stage")["Properties"]
queue_select = find_control(screen, "btnT001Select")["Properties"]
start_button = find_control(screen, "btnS01StartFlow")["Properties"]
run_number_error = find_control(screen, "ErrorMessage4")["Properties"]
run_number_card = find_control(screen, "実行回数_DataCard1")["Properties"]
save_if = next(args for args in if_calls(save_button["OnSelect"]) if any("SubmitForm(Form1)" in arg for arg in args))
assert len(save_if) == 3
assert "IsBlank(varT001UnknownQueueId)" in save_if[0]
assert 'SaveStatus <> "保存結果不明"' in save_if[0]
assert "Form1.Valid" in save_if[0]
assert 'SaveStatus <> "保存済み"' in save_if[0]
assert "IfError(!IsBlank(runNumber) && runNumber >= 1 && runNumber <= 2147483647 && Mod(runNumber, 1) = 0, false)" in save_if[0]
assert "IfError(Value(DataCardValue4.Text), Blank())" in save_button["OnSelect"]
assert run_number_card["Update"] == "=IfError(Value(DataCardValue4.Text), Blank())"
assert "runNumberValid:IfError(!IsBlank(runNumber) && runNumber >= 1 && runNumber <= 2147483647 && Mod(runNumber, 1) = 0, false)" in save_button["DisplayMode"]
assert "2,147,483,647" in run_number_error["Text"]
assert "標準上限" in run_number_error["Text"]
assert "数値で入力" in run_number_error["Text"]
assert "整数で入力" in run_number_error["Text"]
assert "1以上" in run_number_error["Text"]
assert "Mod(runNumber, 1) <> 0" in run_number_error["Text"]
assert "IfError(runNumber > 2147483647, true)" in run_number_error["Text"]
assert "IfError(runNumber < 1, true)" in run_number_error["Text"]
assert "IfError(Mod(runNumber, 1) <> 0, true)" in run_number_error["Visible"]
assert "runNumberValid" in save_button["DisplayMode"]
assert "SubmitForm(Form1)" in save_if[1]
assert "SubmitForm(Form1)" not in save_if[2]
assert 'SaveStatus: "保存結果不明"' not in save_if[2]
assert "Notify(Coalesce(Form1.Error" in save_if[2]
assert "Set(varT001UnknownQueueId, Blank())" not in save_if[1]
assert "!Form1.Valid" in save_button["DisplayMode"]
assert 'SaveStatus = "保存結果不明"' in save_button["DisplayMode"]
assert "!IsBlank(varT001UnknownQueueId)" in save_button["DisplayMode"]
assert "Filter(colT001Metadata, SaveStatus = \"保存結果不明\")" not in save_if[0]

cancel_if = next(args for args in if_calls(cancel_button["OnSelect"]) if "RemoveIf(colT001Metadata" in args[-1])
assert 'SaveStatus <> "保存結果不明"' in cancel_if[0]
assert 'SaveStatus = "保存結果不明"' in cancel_button["DisplayMode"]
assert 'ThisItem.SaveStatus = "保存結果不明"' in queue_select["Text"]
assert 'ThisItem.SaveStatus = "保存結果不明"' in queue_select["AccessibleLabel"]
assert "IfError(Value(DataCardValue4.Text), Blank())" in queue_select["OnSelect"]
assert "Set(varT001UnknownQueueId, Blank())" not in intake_button["OnSelect"]

start_if = next(args for args in if_calls(start_button["OnSelect"]) if "IsBlank(varT001UnknownQueueId)" in args[0])
assert 'SaveStatus = "保存済み"' in start_if[0]
assert 'SaveStatus = "保存済み"' in start_if[1]
assert "!IsBlank(varT001UnknownQueueId)" in start_button["DisplayMode"]

failure_if = next(args for args in if_calls(form_props["OnFailure"]) if args[0] == "!Form1.Valid")
assert len(failure_if) == 3
validation_branch, ambiguous_branch = failure_if[1], failure_if[2]
assert "Set(varT001Saving, false)" in validation_branch
assert "Set(varT001SavingQueueId, Blank())" in validation_branch
assert "Notify(Coalesce(Form1.Error" in validation_branch
assert 'SaveStatus: "保存結果不明"' not in validation_branch
assert "Set(varT001UnknownQueueId" not in validation_branch
assert "ResetForm(Form1)" not in validation_branch and "NewForm(Form1)" not in validation_branch
assert 'varT001FailureMetadataPatch.SaveStatus = "保存結果不明"' in ambiguous_branch
assert 'Set(varT001UnknownQueueId, varT001SavingQueueId)' in ambiguous_branch
assert 'SaveStatus: "保存結果不明"' in ambiguous_branch
assert ambiguous_branch.index('SaveStatus: "保存結果不明"') < ambiguous_branch.index("Set(varT001Saving, false)")

unknown_mark_call = re.search(r"Patch\s*\(\s*colT001Metadata\s*,\s*LookUp\(colT001Metadata, QueueId = varT001SavingQueueId\)", form_props["OnFailure"])
assert unknown_mark_call, "OnFailure must mark the saving queue, not a global/selected queue"
formula = form_props["OnSuccess"]
final_if = next(args for args in if_calls(formula) if args[0] == "varT001SaveVerified")
assert len(final_if) == 3
assert "ResetForm(Form1)" in final_if[1] and "NewForm(Form1)" in final_if[1]
assert "Set(varT001UnknownQueueId, Blank())" in final_if[1]
clear_fallback_if = next(args for args in if_calls(final_if[1]) if "Set(varT001UnknownQueueId, Blank())" in args[-1])
assert clear_fallback_if[0] == "varT001UnknownQueueId = varT001SavingQueueId"
assert 'SaveStatus: "保存結果不明"' in final_if[2]
assert "Set(varT001UnknownQueueId, varT001SavingQueueId)" in final_if[2]
assert "ResetForm(Form1)" not in final_if[2] and "NewForm(Form1)" not in final_if[2]
assert re.search(r"Patch\s*\(\s*colT001Metadata\s*,\s*LookUp\(colT001Metadata, QueueId = varT001SavingQueueId\)", final_if[2])

verify_if = next(args for args in if_calls(formula) if "varT001ReadbackCase.cr6cb_reviewstatus = \"未依頼\"" in args[0])
assert len(verify_if) == 2
assert re.search(r"Patch\s*\(\s*colT001Metadata", verify_if[1])
assert re.search(r"LookUp\(colT001Metadata, QueueId = varT001SavingQueueId\)", verify_if[1])
assert "Set(varT001SaveVerified, true)" in verify_if[1]
assert re.search(r"Patch\s*\(\s*colT001Metadata", formula).start() < formula.index("Set(varT001SaveVerified, true)")
assert formula.index("Set(varT001SaveVerified, true)") < re.search(r"If\s*\(\s*varT001SaveVerified", formula).start()

for changed_formula in (form_props["OnFailure"], formula, save_button["DisplayMode"], save_button["OnSelect"], run_number_card["Update"], run_number_error["Text"], run_number_error["Visible"], cancel_button["OnSelect"], intake_button["OnSelect"], queue_select["Text"], queue_select["AccessibleLabel"], queue_select["OnSelect"]):
    assert_balanced_powerfx(changed_formula)

print("PASS: six-file YAML parse; expected properties only differ; saved-state and whole-number input boundaries (blank/non-numeric, fractional, below 1, and above platform max) are structurally guarded in DisplayMode/OnSelect/error evidence; local-invalid inputs never call SubmitForm or mark Unknown; an OnFailure with Form.Valid false preserves the queue/form without Unknown; ambiguous attempted-submit failures mark only that item Unknown; A Unknown remains isolated when B succeeds; reset ordering and formula delimiters hold.")
print("Note: structural Power Fx checks do not compile/evaluate the formulas or prove connector/runtime behavior.")
