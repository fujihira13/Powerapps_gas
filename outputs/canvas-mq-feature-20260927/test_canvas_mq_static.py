"""Offline source checks for the MQ Canvas candidate.

These checks inspect authored YAML text only. They do not compile Power Fx,
connect to Power Platform, or prove that attachment upload/readback works at runtime.
"""

from __future__ import annotations

import hashlib
import unittest
from pathlib import Path


ROOT = Path(__file__).parent
WORKSPACE = ROOT / "workspace"
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


class CanvasMqStaticChecks(unittest.TestCase):
    def test_workspace_contains_only_the_six_canvas_yaml_files(self) -> None:
        self.assertEqual(
            EXPECTED_FILES,
            {path.name for path in WORKSPACE.glob("*.pa.yaml")},
        )

    def test_app_screen4_and_editor_state_are_preserved(self) -> None:
        for file_name in ("App.pa.yaml", "Screen4.pa.yaml", "_EditorState.pa.yaml"):
            candidate_hash = hashlib.sha256((WORKSPACE / file_name).read_bytes()).hexdigest()
            baseline_hash = hashlib.sha256((BASELINE / file_name).read_bytes()).hexdigest()
            self.assertEqual(baseline_hash, candidate_hash, file_name)

    def test_intake_has_explicit_per_case_mode_and_attachment_guards(self) -> None:
        screen = contents("Screen1.pa.yaml")
        required_fragments = (
            'Items: = ["ログのみ", "MQ照合"]',
            "OnAddFile:",
            "OnRemoveFile:",
            'EndsWith(Lower(candidate.Name), ".xlsx")',
            'FileRole = "Batch_Input"',
            "varT001SelectedQueueId",
            "MqRequested",
            "varT001SavingMqRequested",
            "CountRows(varT001ReadbackCase.Attachments)",
            "varT001ReadbackLogCount = 1",
            "varT001ReadbackWorkbookCount",
            "varT001SaveVerified",
            '"保存状況を確認しています"',
        )
        for fragment in required_fragments:
            with self.subTest(fragment=fragment):
                self.assertIn(fragment, screen)

    def test_attachment_event_handlers_have_balanced_parentheses(self) -> None:
        screen = contents("Screen1.pa.yaml")
        for name, next_name in (
            ("OnAddFile", "OnRemoveFile"),
            ("OnRemoveFile", "OnUndoRemoveFile"),
            ("OnUndoRemoveFile", "NoAttachmentsColor"),
        ):
            handler = attachment_handler(screen, name, next_name)
            with self.subTest(handler=name):
                self.assertEqual(handler.count("("), handler.count(")"))

    def test_intake_mode_guidance_and_empty_queue_fit_without_overlapping(self) -> None:
        screen = contents("Screen1.pa.yaml")
        gallery = screen.split("      - galT001Queue:", 1)[1].split(
            "      - btnT001CancelItem:", 1
        )[0]
        mode_label = screen.split("      - lblT001MqMode:", 1)[1].split(
            "      - radT001MqMode:", 1
        )[0]
        radio = screen.split("      - radT001MqMode:", 1)[1].split(
            "      - btnS01Progress:", 1
        )[0]

        self.assertIn("Height: =Parent.Height - 310", gallery)
        self.assertIn("Y: =100", gallery)
        self.assertIn("Height: =50", mode_label)
        self.assertIn("AutoHeight: =false", mode_label)
        self.assertIn("Y: =Parent.Height - 205", mode_label)
        self.assertIn("ログを選ぶと受付対象が一覧に表示されます。", mode_label)
        self.assertIn(".xlsx不可", mode_label)
        self.assertIn("Y: =Parent.Height - 145", radio)

    def test_start_flow_is_blocked_for_empty_queue_in_both_button_and_handler(self) -> None:
        screen = contents("Screen1.pa.yaml")
        start_button = screen.split("      - btnS01StartFlow:", 1)[1]
        display_mode = start_button.split("            DisplayMode:", 1)[1].split(
            "            Height:", 1
        )[0]
        on_select = start_button.split("            OnSelect:", 1)[1].split(
            "            Text:", 1
        )[0]

        self.assertIn("IsEmpty(colT001Metadata)", display_mode)
        self.assertIn("!IsEmpty(colT001Metadata)", on_select)

    def test_initial_attachment_can_be_added_before_a_queue_item_exists(self) -> None:
        screen = contents("Screen1.pa.yaml")
        attachment = screen.split("                  - DataCardValue5:", 1)[1].split(
            "                  - ErrorMessage6:", 1
        )[0]
        display_mode = next(
            line.split("=", 1)[1]
            for line in attachment.splitlines()
            if line.strip().startswith("DisplayMode:")
        )
        stage_button = screen.split("      - btnT001Stage:", 1)[1].split(
            "      - galT001Queue:", 1
        )[0]
        stage_display_mode = next(
            line.split("=", 1)[1]
            for line in stage_button.splitlines()
            if line.strip().startswith("DisplayMode:")
        )
        stage_on_select = stage_button.split("            OnSelect:", 1)[1].split(
            "            Text:", 1
        )[0]

        # With no queue selected, none of the disabled conditions should match;
        # an existing queue only adds the saved/unknown-state lock.
        for fragment in (
            "Coalesce(varS01Starting, false)",
            "Coalesce(varS01StartUnknown, false)",
            "Coalesce(varT001Saving, false)",
            "!IsBlank(varT001SelectedQueueId) && (",
            "varT001UnknownQueueId = varT001SelectedQueueId",
            'SaveStatus = "保存済み"',
            'SaveStatus = "保存結果不明"',
        ):
            with self.subTest(fragment=fragment):
                self.assertIn(fragment, display_mode)
        self.assertNotIn("|| IsBlank(varT001SelectedQueueId)", display_mode)

        self.assertIn("!IsEmpty(colT001Metadata)", stage_display_mode)
        self.assertIn("IsEmpty(colT001Metadata)", stage_on_select)
        self.assertIn("!IsEmpty(DataCardValue5.Attachments)", stage_on_select)
        self.assertIn("ClearCollect(colT001AttachmentSource, DataCardValue5.Attachments)", stage_on_select)

    def test_add_file_handler_leaves_initial_attachments_in_the_control(self) -> None:
        screen = contents("Screen1.pa.yaml")
        on_add_file = attachment_handler(screen, "OnAddFile", "OnRemoveFile")

        self.assertIn("!IsBlank(selectedCase) && !selectedCase.MqRequested", on_add_file)
        self.assertNotIn("Reset(DataCardValue5)", on_add_file)
        self.assertNotIn("ResetForm(Form1)", on_add_file)
        self.assertNotIn("Clear(DataCardValue5)", on_add_file)
        self.assertNotIn("ClearCollect(colT001AttachmentSource", on_add_file)

    def test_attachment_items_use_native_source_for_initial_and_mq_rows(self) -> None:
        screen = contents("Screen1.pa.yaml")
        attachment = screen.split("                  - DataCardValue5:", 1)[1].split(
            "                  - ErrorMessage6:", 1
        )[0]
        items_formula = next(
            line.split("=", 1)[1].strip()
            for line in attachment.splitlines()
            if line.strip().startswith("Items:")
        )

        self.assertEqual(
            items_formula,
            "If(IsBlank(varT001SelectedQueueId) || LookUp(colT001Metadata, QueueId = varT001SelectedQueueId).MqRequested, Parent.Default, Filter(colT001QueueAttachments, QueueId = varT001SelectedQueueId))",
        )
        self.assertIn("Parent.Default", items_formula)
        self.assertIn("Filter(colT001QueueAttachments, QueueId = varT001SelectedQueueId)", items_formula)

    def test_mq_pair_staging_keeps_both_original_attachments_for_save(self) -> None:
        screen = contents("Screen1.pa.yaml")
        stage_button = screen.split("      - btnT001Stage:", 1)[1].split(
            "      - galT001Queue:", 1
        )[0]
        stage_on_select = stage_button.split("            OnSelect:", 1)[1].split(
            "            Text:", 1
        )[0]
        mq_branch = stage_on_select.split(
            "If(\n                      bookCount = 1,", 1
        )[1].split(",\n                      Set(varT001Saved, Blank());", 1)[0]

        self.assertIn("bookCount <> 1 || logCount <> 1 || attachmentCount <> 2", stage_on_select)
        self.assertIn("ClearCollect(colT001AttachmentSource, DataCardValue5.Attachments)", mq_branch)
        self.assertIn('FileName:LookUp(colT001AttachmentSource As candidate, EndsWith(Lower(candidate.Name), ".txt")).Name', mq_branch)
        self.assertIn("MqRequested:true", mq_branch)
        self.assertIn("ForAll(\n                          colT001AttachmentSource As candidate", mq_branch)
        self.assertIn("Name:candidate.Name, Value:candidate.Value", mq_branch)
        self.assertNotIn("ResetForm(Form1)", mq_branch)
        self.assertNotIn("NewForm(Form1)", mq_branch)

        # The multi-log-only queue still uses its original separate-per-log staging path.
        self.assertIn("Sequence(CountRows(colT001AttachmentSource)) As seq", stage_on_select)
        self.assertIn("ResetForm(Form1);\n                      NewForm(Form1)", stage_on_select)

    def test_pre_staged_mq_pair_file_events_do_not_rebuild_its_attachment_set(self) -> None:
        screen = contents("Screen1.pa.yaml")
        for name, next_name in (
            ("OnAddFile", "OnRemoveFile"),
            ("OnRemoveFile", "OnUndoRemoveFile"),
            ("OnUndoRemoveFile", "NoAttachmentsColor"),
        ):
            handler = attachment_handler(screen, name, next_name)
            with self.subTest(handler=name):
                self.assertIn("!IsBlank(selectedCase) && !selectedCase.MqRequested", handler)
                self.assertIn("RemoveIf(colT001QueueAttachments", handler)
                self.assertLess(
                    handler.index("!IsBlank(selectedCase) && !selectedCase.MqRequested"),
                    handler.index("RemoveIf(colT001QueueAttachments"),
                )

    def test_reselecting_the_current_mq_queue_does_not_reset_its_form(self) -> None:
        screen = contents("Screen1.pa.yaml")
        select_button = screen.split("            - btnT001Select:", 1)[1].split(
            "      - btnT001CancelItem:", 1
        )[0]
        on_select = select_button.split("                  OnSelect: |-")
        self.assertEqual(len(on_select), 2)
        on_select = on_select[1].split("                  Text:", 1)[0]

        guard = "ThisItem.QueueId <> varT001SelectedQueueId || !LookUp(colT001Metadata, QueueId = ThisItem.QueueId).MqRequested"
        self.assertIn(guard, on_select)
        self.assertLess(on_select.index(guard), on_select.index("ResetForm(Form1)"))

    def test_save_keeps_the_explicit_attachment_pair_guard(self) -> None:
        screen = contents("Screen1.pa.yaml")
        attachment_card = screen.split("            - Attachments_DataCard1:", 1)[1].split(
            "      - btnT001Save:", 1
        )[0]
        save_button = screen.split("      - btnT001Save:", 1)[1].split(
            "      - btnT001Stage:", 1
        )[0]
        display_mode = save_button.split("            DisplayMode: |-", 1)[1].split(
            "            Height:", 1
        )[0]
        on_select = save_button.split("            OnSelect: |-", 1)[1].split(
            "            Text:", 1
        )[0]

        self.assertIn("Required: =false", attachment_card)
        self.assertIn("!Form1.Valid", display_mode)
        self.assertIn("!pairValid", display_mode)
        self.assertIn("Form1.Valid && pairValid", on_select)

    def test_save_disabled_status_reports_the_blocking_checks(self) -> None:
        screen = contents("Screen1.pa.yaml")
        status_label = screen.split("      - lblS01FlowStatus:", 1)[1]

        for fragment in (
            "btnT001Save.DisplayMode = DisplayMode.Disabled",
            "Form1.Valid=NG",
            "pairValid:",
            'If(runNumberValid, "OK", "NG")',
            'If(IsBlank(DataCardValue2.Selected.Value), "NG", "OK")',
            'If(IsBlank(DataCardValue3.Selected.Value), "NG", "OK")',
            'If(IsBlank(DateValue1.SelectedDate), "NG", "OK")',
            "varT001UnknownQueueId = varT001SelectedQueueId",
            "!IsBlank(varT001UnknownQueueId)",
        ):
            with self.subTest(fragment=fragment):
                self.assertIn(fragment, status_label)

        card_names = (
            "'ログ名_DataCard1'",
            "'環境名_DataCard1'",
            "'サーバー名_DataCard1'",
            "'実行回数_DataCard1'",
            "'対象処理日_DataCard1'",
            "Attachments_DataCard1",
        )
        for card_name in card_names:
            with self.subTest(card=card_name):
                self.assertIn(f"{card_name}.Valid", status_label)
                self.assertIn(f"{card_name}.Update", status_label)
                self.assertIn(f"{card_name}.Required", status_label)
                self.assertIn(f"{card_name}.Error", status_label)

        self.assertIn("Filter(formCards, !CardValid)", status_label)
        self.assertIn("CountRows(Attachments_DataCard1.Update)", status_label)
        self.assertNotIn("file.Value", status_label)
        self.assertNotIn("candidate.Value", status_label)

    def test_progress_shows_verified_mq_summary_without_claiming_success(self) -> None:
        screen = contents("Screen2.pa.yaml")
        for column in (
            "cr6cb_mqterminalstatus",
            "cr6cb_mqexpectedcount",
            "cr6cb_mqloggedcount",
            "cr6cb_mqmissingcount",
            "cr6cb_mqcomparisonstatus",
        ):
            with self.subTest(column=column):
                self.assertIn(column, screen)
        self.assertIn("ALL SUCCESS", screen)
        self.assertIn("全ID成功を意味しません", screen)
        self.assertIn("未記録・要確認", screen)
        self.assertIn('ThisItem.cr6cb_mqterminalstatus = "なし"', screen)
        self.assertIn("ログ不完全・要確認", screen)

    def test_case_detail_separates_the_two_inputs_and_exposes_comparison_evidence(self) -> None:
        screen = contents("Screen3.pa.yaml")
        for fragment in (
            'EndsWith(Lower(DisplayName), ".txt")',
            'EndsWith(Lower(DisplayName), ".xlsx")',
            "cr6cb_mqmissingids",
            "cr6cb_mqterminalstatus",
            "cr6cb_mqexpectedcount",
            "cr6cb_mqloggedcount",
            "cr6cb_mqmissingcount",
            "cr6cb_mqresulttext",
            "cr6cb_mqcomparisonstatus",
            "varEvidenceCase.cr6cb_excelurl",
            "ALL SUCCESS",
            "全ID成功を意味しません",
            "未記録・要確認",
            "ログ不完全・要確認",
            "radCaseCompare:",
            "radCaseJudgment:",
            "btnCaseRequestReview:",
        ):
            with self.subTest(fragment=fragment):
                self.assertIn(fragment, screen)

    def test_canvas_label_controls_do_not_use_unsupported_accessiblelabel(self) -> None:
        screen1 = contents("Screen1.pa.yaml")
        mode_label = screen1.split("      - lblT001MqMode:", 1)[1].split(
            "      - radT001MqMode:", 1
        )[0]
        self.assertNotIn("AccessibleLabel:", mode_label)

        screen3 = contents("Screen3.pa.yaml")
        result_label = screen3.split("            - lblCaseMqResultRow:", 1)[1].split(
            "      - lblCaseFailure:", 1
        )[0]
        self.assertNotIn("AccessibleLabel:", result_label)


if __name__ == "__main__":
    unittest.main(verbosity=2)
