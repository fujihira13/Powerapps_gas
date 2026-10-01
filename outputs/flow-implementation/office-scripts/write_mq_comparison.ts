/** Create the single-sheet MQ result workbook from the copied legacy template. */
type MqComparisonInput = {
  contract_version: string;
  status: string;
  comparison_available: boolean;
  end_marker_present: boolean;
  expected_ids: string[];
  logged_ids: string[];
  missing_ids: string[] | null;
  log_only_ids: string[] | null;
  counts: { expected: number; logged: number; missing: number | null; log_only: number | null };
  presentation: { status_label: string; human_decision_required: boolean };
  source_files: { batch_input: string; log: string };
};
type Cell = string | number | boolean;
type WriterResult = { ok: boolean; caseId: string; resultText: string; error?: string };
const TABLE_START_ROW_INDEX = 0;

function parseInput(validationJson: string): MqComparisonInput | undefined {
  try {
    const value = JSON.parse(validationJson) as MqComparisonInput;
    if (
      value.contract_version !== "mq-id-result.v1" ||
      value.status !== "comparison_ready" ||
      value.comparison_available !== true ||
      typeof value.end_marker_present !== "boolean" ||
      !Array.isArray(value.expected_ids) ||
      !Array.isArray(value.logged_ids) ||
      !Array.isArray(value.missing_ids) ||
      !Array.isArray(value.log_only_ids) ||
      typeof value.counts?.expected !== "number" ||
      typeof value.counts?.logged !== "number" ||
      typeof value.counts?.missing !== "number" ||
      typeof value.counts?.log_only !== "number" ||
      (value.presentation?.status_label !== "要確認" && value.presentation?.status_label !== "比較完了") ||
      value.presentation?.human_decision_required !== true ||
      typeof value.source_files?.batch_input !== "string" ||
      value.source_files.batch_input.length === 0 ||
      typeof value.source_files?.log !== "string" ||
      value.source_files.log.length === 0
    ) {
      return undefined;
    }
    return value;
  } catch {
    return undefined;
  }
}

function comparisonResult(input: MqComparisonInput, mqId: string): string {
  const isExpected = input.expected_ids.indexOf(mqId) >= 0;
  if (!isExpected) {
    return "一覧にないID・要確認";
  }
  return input.logged_ids.indexOf(mqId) >= 0
    ? "ログに記録あり"
    : "ログに記録なし・要確認";
}

function resultText(input: MqComparisonInput): string {
  const lines: string[] = [
  ];
  for (const mqId of input.expected_ids) {
    lines.push(`${mqId}\t${comparisonResult(input, mqId)}`);
  }
  for (const mqId of input.log_only_ids as string[]) {
    lines.push(`${mqId}\t${comparisonResult(input, mqId)}`);
  }
  return lines.join("\n");
}

function expectedRows(input: MqComparisonInput): Cell[][] {
  const rows: Cell[][] = [["MQ ID", "Excelの記載", "ログの記録", "照合結果"]];
  for (const mqId of input.expected_ids) {
    const inLog = input.logged_ids.indexOf(mqId) >= 0;
    rows.push([mqId, "あり", inLog ? "あり" : "なし", inLog ? "一致" : "ログに記録なし"]);
  }
  for (const mqId of input.log_only_ids as string[]) {
    rows.push([mqId, "なし", "あり", "Excelに記載なし"]);
  }
  return rows;
}

function main(workbook: ExcelScript.Workbook, validationJson: string, caseId: string): string {
  const fail = (reason: string): string => JSON.stringify({ ok: false, caseId, resultText: "", error: reason } as WriterResult);
  const input = parseInput(validationJson);
  if (!input) {
    return fail("mq-id-result.v1 is invalid or comparison is unavailable");
  }
  const worksheets = workbook.getWorksheets();
  const evidenceSheet = workbook.getWorksheet("証跡");
  if (
    !evidenceSheet ||
    worksheets.length !== 1 ||
    worksheets[0].getName() !== "証跡"
  ) {
    return fail("expected a workbook with only the 証跡 worksheet");
  }
  if (workbook.getWorksheet("MQ ID照合結果")) {
    return fail("MQ ID照合結果 already exists; refusing to overwrite");
  }

  const sheet = workbook.addWorksheet("MQ ID照合結果");
  const rows = expectedRows(input);
  const reportRange = sheet.getRangeByIndexes(TABLE_START_ROW_INDEX, 0, rows.length, rows[0].length);
  reportRange.setValues(rows);
  const table = sheet.addTable(reportRange, true);
  table.setName("MQ_ComparisonTable");
  table.getRange().getFormat().autofitColumns();
  sheet.getRange("A:A").getFormat().setColumnWidth(185);
  sheet.getRange("B:B").getFormat().setColumnWidth(180);
  sheet.getRange("C:C").getFormat().setColumnWidth(190);
  sheet.getRange("D:D").getFormat().setColumnWidth(230);
  for (let index = 1; index < rows.length; index++) {
    if (rows[index][3] !== "一致") {
      sheet.getRangeByIndexes(TABLE_START_ROW_INDEX + index, 0, 1, 4)
        .getFormat().getFill().setColor("#FFF2CC");
    }
  }
  evidenceSheet.delete();
  const remainingWorksheets = workbook.getWorksheets();
  if (
    remainingWorksheets.length !== 1 ||
    remainingWorksheets[0].getName() !== "MQ ID照合結果"
  ) {
    return fail("result workbook does not contain exactly one MQ ID照合結果 worksheet");
  }

  return JSON.stringify({ ok: true, caseId, resultText: resultText(input) } as WriterResult);
}
