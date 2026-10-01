/** Independently verify the one-sheet MQ result workbook and derive result text. */
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
type ReadbackResult = { ok: boolean; caseId: string; resultText: string; error?: string };
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

function sameRows(actual: (string | number | boolean)[][], expected: Cell[][]): boolean {
  if (actual.length !== expected.length) {
    return false;
  }
  for (let row = 0; row < expected.length; row++) {
    if (actual[row].length !== expected[row].length) {
      return false;
    }
    for (let column = 0; column < expected[row].length; column++) {
      if (actual[row][column] !== expected[row][column]) {
        return false;
      }
    }
  }
  return true;
}

function main(workbook: ExcelScript.Workbook, validationJson: string, caseId: string): string {
  const fail = (reason: string): string => JSON.stringify({ ok: false, caseId, resultText: "", error: reason } as ReadbackResult);
  const input = parseInput(validationJson);
  if (!input) {
    return fail("mq-id-result.v1 is invalid or comparison is unavailable");
  }
  const evidenceSheet = workbook.getWorksheet("証跡");
  const worksheets = workbook.getWorksheets();
  const reportSheet = workbook.getWorksheet("MQ ID照合結果");
  if (
    evidenceSheet ||
    worksheets.length !== 1 ||
    !reportSheet ||
    worksheets[0].getName() !== "MQ ID照合結果"
  ) {
    return fail("workbook must contain only the MQ ID照合結果 worksheet");
  }

  const tables = reportSheet.getTables();
  const matchingTable = reportSheet.getTable("MQ_ComparisonTable");
  if (!matchingTable || tables.length !== 1) {
    return fail("MQ_ComparisonTable is missing or duplicated");
  }
  const expected = expectedRows(input);
  const tableRange = matchingTable.getRange();
  const actual = tableRange.getValues();
  const usedRange = reportSheet.getUsedRange(true);
  const shapeMatches = usedRange !== undefined &&
    usedRange.getRowIndex() === 0 &&
    usedRange.getColumnIndex() === 0 &&
    usedRange.getRowCount() === TABLE_START_ROW_INDEX + expected.length &&
    usedRange.getColumnCount() === expected[0].length &&
    tableRange.getRowIndex() === TABLE_START_ROW_INDEX &&
    tableRange.getColumnIndex() === 0;
  const ok = shapeMatches && sameRows(actual, expected);
  return JSON.stringify({
    ok,
    caseId,
    resultText: ok ? resultText(input) : "",
    error: ok ? undefined : "MQ ID照合結果 rows or dimensions differ from the computed result",
  } as ReadbackResult);
}
