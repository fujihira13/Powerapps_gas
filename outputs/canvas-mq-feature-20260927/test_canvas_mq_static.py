"""Offline checks for the runless single-case Canvas candidate.

These checks inspect authored YAML text only. They do not compile Power Fx,
connect to Power Platform, or prove that attachment upload/readback works at runtime.
"""

from __future__ import annotations

import unittest
from pathlib import Path

import yaml


ROOT = Path(__file__).parent
WORKSPACE = ROOT.parent / "canvas-runless-live-sync-20260927"
BASELINE = ROOT.parent / "canvas-mq-live-sync-20260927"
EXPECTED_FILES = {
    "App.pa.yaml",
    "Screen1.pa.yaml",
    "Screen2.pa.yaml",
    "Screen3.pa.yaml",
    "Screen4.pa.yaml",
    "_EditorState.pa.yaml",
}


def contents(file_name: str) -> str:
    return (WORKSPACE / file_name).read_text(encoding="utf-8")


def attachment_handler(screen: str, name: str, next_name: str) -> str:
    attachment = screen.split("                  - DataCardValue5:", 1)[1].split(
        "                  - ErrorMessage6:", 1
    )[0]
    return attachment.split(f"{name}: |-\n", 1)[1].split(
        f"\n                        {next_name}:", 1
    )[0]


def parse_yaml(file_name: str) -> dict:
    return yaml.safe_load((WORKSPACE / file_name).read_text(encoding="utf-8-sig"))


def canvas_screen(name: str) -> dict:
    return parse_yaml(f"{name}.pa.yaml")["Screens"][name]


def find_control(node, name: str) -> dict:
    if isinstance(node, dict):
        if name in node and isinstance(node[name], dict):
            return node[name]
        for value in node.values():
            try:
                return find_control(value, name)
            except KeyError:
                pass
    elif isinstance(node, list):
        for value in node:
            try:
                return find_control(value, name)
            except KeyError:
                pass
    raise KeyError(name)


def control_props(screen_name: str, control_name: str) -> dict:
    return find_control(canvas_screen(screen_name), control_name)["Properties"]


def has_balanced_parentheses(expression: str) -> bool:
    depth = 0
    in_string = False
    index = 0
    while index < len(expression):
        char = expression[index]
        if char == '"':
            if in_string and index + 1 < len(expression) and expression[index + 1] == '"':
                index += 2
                continue
            in_string = not in_string
        elif not in_string and char == "(":
            depth += 1
        elif not in_string and char == ")":
            depth -= 1
            if depth < 0:
                return False
        index += 1
    return depth == 0 and not in_string


class RunlessCanvasStaticChecks(unittest.TestCase):
    def test_synced_workspace_contains_six_valid_canvas_yaml_files(self) -> None:
        self.assertEqual(EXPECTED_FILES, {path.name for path in WORKSPACE.glob("*.pa.yaml")})
        for file_name in EXPECTED_FILES:
            with self.subTest(file=file_name):
                self.assertIsInstance(parse_yaml(file_name), dict)

    def test_screen1_is_single_case_without_run_number_or_staging_queue(self) -> None:
        source = (WORKSPACE / "Screen1.pa.yaml").read_text(encoding="utf-8-sig")
        top_level = {next(iter(control)) for control in canvas_screen("Screen1")["Children"]}
        self.assertNotIn("btnT001Stage", top_level)
        self.assertNotIn("galT001Queue", top_level)
        self.assertNotIn("radT001MqMode", top_level)
        for obsolete in ("colT001Metadata", "varT001SelectedQueueId", "実行回", "RunNumber", "cr6cb_runnumber"):
            with self.subTest(obsolete=obsolete):
                self.assertNotIn(obsolete, source)
        self.assertEqual(control_props("Screen1", "Form1")["DefaultMode"], "=FormMode.New")
        self.assertEqual(control_props("Screen1", "DataCardValue5")["Items"], "=Parent.Default")
        self.assertEqual(
            control_props("Screen1", "対象処理日_DataCard1")["Default"],
            "=If(Form1.Mode = FormMode.New, Today(), ThisItem.対象処理日)",
        )
        self.assertEqual(control_props("Screen1", "DateValue1")["IsEditable"], "=true")
        self.assertNotIn("バッチExcel名_DataCard1", source)
        self.assertIn(
            "cr6cb_batchfilename:If(IsBlank(varT001SavingWorkbookName), Blank(), varT001SavingWorkbookName)",
            control_props("Screen1", "Form1")["OnSuccess"],
        )

    def test_attachment_count_and_type_guards_allow_log_only_or_one_pair(self) -> None:
        save_formula = control_props("Screen1", "btnT001Save")["OnSelect"]
        for fragment in (
            "logCount = 1 && bookCount <= 1",
            "unsupportedCount = 0",
            "attachmentCount = logCount + bookCount",
            'EndsWith(Lower(file.Name), ".txt")',
            'EndsWith(Lower(file.Name), ".xlsx")',
        ):
            with self.subTest(fragment=fragment):
                self.assertIn(fragment, save_formula)
        attachment_props = control_props("Screen1", "DataCardValue5")
        self.assertEqual(attachment_props["Items"], "=Parent.Default")
        for event_name in ("OnAddFile", "OnRemoveFile", "OnUndoRemoveFile"):
            self.assertIn(event_name, attachment_props)

    def test_duplicate_check_covers_log_new_batch_column_and_legacy_note(self) -> None:
        save_formula = control_props("Screen1", "btnT001Save")["OnSelect"]
        warning_text = control_props("Screen1", "lblT001MqMode")["Text"]
        confirm = control_props("Screen1", "btnT001CancelItem")
        for fragment in (
            "cr6cb_caselabel = varT001SavingLogName",
            "cr6cb_batchfilename = varT001SavingWorkbookName",
            "Set(varS01LegacyExcelUnverified, false)",
            "LookUp('メモ ', 'ファイル名' = varT001SavingWorkbookName)",
            "AsType(varS01LegacyNote.'関連', [@'架空ログ証跡件']).cr6cb_evidencecaseid",
            'MatchType:"Excel添付名"',
            "!IsEmpty(colS01DuplicateCases) || varS01LegacyExcelUnverified",
            "Set(varS01DuplicateReadOk, false)",
            "!varS01DuplicateReadOk",
        ):
            with self.subTest(fragment=fragment):
                self.assertIn(fragment, save_formula)
        self.assertNotIn("cr6cb_evidencecase_Annotations", save_formula)
        for fragment in (
            "内容が同一という判定ではありません",
            "旧受付のExcel添付名を個別照合できない",
            "TimeZoneOffset(duplicateCase.CreatedOn) + 540",
            "Text(duplicateCase.EvidenceCaseId)",
        ):
            with self.subTest(fragment=fragment):
                self.assertIn(fragment, warning_text)
        self.assertEqual(confirm["Visible"], "=varS01DuplicateWarning")
        self.assertIn("varS01LegacyExcelUnverified", confirm["OnSelect"])
        self.assertIn("SubmitForm(Form1)", confirm["OnSelect"])
        self.assertIn("未照合を確認して新しい件として保存", confirm["Text"])
        self.assertIn("修正する", control_props("Screen1", "btnS01Progress")["Text"])

    def test_saved_state_requires_case_metadata_status_and_attachment_readback(self) -> None:
        on_success = control_props("Screen1", "Form1")["OnSuccess"]
        on_failure = control_props("Screen1", "Form1")["OnFailure"]
        for fragment in (
            "Form1.LastSubmit.cr6cb_evidencecaseid",
            "!IsBlank(varT001ReadbackCase.createdon)",
            "Refresh('架空ログ証跡件')",
            "cr6cb_batchfilename",
            "CountRows(varT001ReadbackCase.Attachments)",
            "savedFile.DisplayName = varT001SavingLogName",
            "savedFile.DisplayName = varT001SavingWorkbookName",
            'cr6cb_processingstatus = "保存済み"',
            "Set(varT001SaveVerified, true)",
            "Set(varT001Saved, varT001ReadbackCase)",
        ):
            with self.subTest(fragment=fragment):
                self.assertIn(fragment, on_success)
        status = control_props("Screen1", "lblS01FlowStatus")["Text"]
        self.assertIn("varT001Saved.createdon", status)
        self.assertIn("TimeZoneOffset(varT001Saved.createdon) + 540", status)
        self.assertIn("Text(varT001Saved.cr6cb_evidencecaseid)", status)
        self.assertIn("Set(varT001SaveUnknown, true)", on_failure)
        self.assertIn("再保存せず進捗一覧で状態を確認", on_failure)

    def test_authored_intake_formulas_have_balanced_parentheses_and_strings(self) -> None:
        formulas = (
            control_props("Screen1", "Form1")["OnSuccess"],
            control_props("Screen1", "btnT001Save")["OnSelect"],
            control_props("Screen1", "btnT001CancelItem")["OnSelect"],
            control_props("Screen1", "btnS01StartFlow")["OnSelect"],
            control_props("Screen1", "lblT001MqMode")["Text"],
        )
        for index, formula in enumerate(formulas):
            with self.subTest(formula=index):
                self.assertTrue(has_balanced_parentheses(formula))

    def test_save_and_start_are_separate_and_start_targets_one_verified_case(self) -> None:
        save = control_props("Screen1", "btnT001Save")["OnSelect"]
        start = control_props("Screen1", "btnS01StartFlow")
        self.assertIn("SubmitForm(Form1)", save)
        self.assertNotIn(".Run(", save)
        self.assertIn(".Run(Text(varT001Saved.cr6cb_evidencecaseid))", start["OnSelect"])
        self.assertNotIn("SubmitForm(Form1)", start["OnSelect"])
        self.assertIn("Refresh('架空ログ証跡件')", start["OnSelect"])
        self.assertIn("varS01StartReadback.cr6cb_processingstatus", start["OnSelect"])
        self.assertIn('varT001Saved.cr6cb_processingstatus = "保存済み"', start["OnSelect"])
        self.assertIn('cr6cb_processingstatus:"開始受付済み"', start["OnSelect"])
        self.assertIn("varS01StartUnknown", start["DisplayMode"])

    def test_screens_2_to_4_show_receipt_datetime_and_case_id_without_run_number(self) -> None:
        for name in ("Screen2", "Screen3", "Screen4"):
            source = (WORKSPACE / f"{name}.pa.yaml").read_text(encoding="utf-8-sig")
            with self.subTest(screen=name):
                self.assertNotIn("実行回", source)
                self.assertNotIn("cr6cb_runnumber", source)
                self.assertIn("createdon", source)
                self.assertIn("cr6cb_evidencecaseid", source)
                self.assertIn("TimeZoneOffset", source)
                self.assertIn("TimeUnit.Hours", source)

    def test_four_screens_and_review_actions_remain(self) -> None:
        for name in ("Screen1", "Screen2", "Screen3", "Screen4"):
            self.assertTrue((WORKSPACE / f"{name}.pa.yaml").exists())
        self.assertIn("btnCaseRequestReview", (WORKSPACE / "Screen3.pa.yaml").read_text(encoding="utf-8-sig"))
        self.assertIn("varDemoRole", (WORKSPACE / "Screen4.pa.yaml").read_text(encoding="utf-8-sig"))


if __name__ == "__main__":
    unittest.main(verbosity=2)
