/** Write a separate MQ report sheet without modifying the 証跡 worksheet. */
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
};
type Cell = string | number | boolean;
type WriterResult = { ok: boolean; caseId: string; resultText: string; error?: string };

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
      value.presentation?.human_decision_required !== true
    ) {
      return undefined;
    }
    return value;
  } catch {
    return undefined;
  }
}

function rowResult(input: MqComparisonInput, mqId: string): string {
  const isMissing = (input.missing_ids as string[]).indexOf(mqId) >= 0;
  if (isMissing) {
    return input.end_marker_present
      ? "ログ未記録・要確認"
      : "ログ未記録（ログ不完全）・要確認";
  }
  return input.end_marker_present
    ? "記録あり"
    : "記録あり（ログ不完全・要確認）";
}

function resultText(input: MqComparisonInput): string {
  const lines: string[] = [
  ];
  for (const mqId of input.expected_ids) {
    lines.push(`${mqId}\t${rowResult(input, mqId)}`);
  }
  for (const mqId of input.log_only_ids as string[]) {
    lines.push(`${mqId}\t予定外ID・要確認`);
  }
  return lines.join("\n");
}

function expectedRows(input: MqComparisonInput, caseId: string): Cell[][] {
  const headers = [
    "RowType",
    "CaseId",
    "MQ_ID",
    "Result",
    "EndMarkerPresent",
    "ExpectedCount",
    "LoggedCount",
    "MissingCount",
    "LogOnlyCount",
    "HumanDecisionRequired",
  ];
  const marker = input.end_marker_present ? "あり" : "なし";
  const rows: Cell[][] = [
    headers,
    [
      "summary",
      caseId,
      "",
      input.presentation.status_label,
      marker,
      input.counts.expected,
      input.counts.logged,
      input.counts.missing as number,
      input.counts.log_only as number,
      true,
    ],
    [
      "note",
      caseId,
      "",
      "ALL SUCCESSはログ終端表示であり、MQ更新成功を証明しません。",
      marker,
      "",
      "",
      "",
      "",
      true,
    ],
  ];
  for (const mqId of input.expected_ids) {
    rows.push(["planned", caseId, mqId, rowResult(input, mqId), marker, "", "", "", "", true]);
  }
  for (const mqId of input.log_only_ids as string[]) {
    rows.push(["log_only", caseId, mqId, "予定外ID・要確認", marker, "", "", "", "", true]);
  }
  return rows;
}

function main(workbook: ExcelScript.Workbook, validationJson: string, caseId: string): string {
  const fail = (reason: string): string => JSON.stringify({ ok: false, caseId, resultText: "", error: reason } as WriterResult);
  const input = parseInput(validationJson);
  if (!input) {
    return fail("mq-id-result.v1 is invalid or comparison is unavailable");
  }
  if (!workbook.getWorksheet("証跡")) {
    return fail("証跡 worksheet is missing");
  }
  if (workbook.getWorksheet("MQ_Comparison")) {
    return fail("MQ_Comparison already exists; refusing to overwrite");
  }

  const sheet = workbook.addWorksheet("MQ_Comparison");
  const rows = expectedRows(input, caseId);
  const reportRange = sheet.getRangeByIndexes(0, 0, rows.length, rows[0].length);
  reportRange.setValues(rows);
  const table = sheet.addTable(reportRange, true);
  table.setName("MQ_ComparisonTable");
  table.getRange().getFormat().autofitColumns();

  return JSON.stringify({ ok: true, caseId, resultText: resultText(input) } as WriterResult);
}
