/**
 * Local candidate adapter for the approved mq-id-input.v1 / mq-id-result.v1
 * contract. It reads worksheet values and returns JSON as a string so the
 * Power Automate action has a stable scalar return type.
 */
type CellValue = string | number | boolean | null;
type JsonObject = { [key: string]: unknown };

function hasValue(value: CellValue): boolean {
  return value !== null && !(typeof value === "string" && value.trim() === "");
}

function columnName(zeroBasedIndex: number): string {
  let number = zeroBasedIndex + 1;
  let label = "";
  while (number > 0) {
    const remainder = (number - 1) % 26;
    label = String.fromCharCode(65 + remainder) + label;
    number = Math.floor((number - 1) / 26);
  }
  return label;
}

function uniqueInOrder(values: string[]): string[] {
  const seen = new Set<string>();
  const result: string[] = [];
  for (const value of values) {
    if (!seen.has(value)) {
      seen.add(value);
      result.push(value);
    }
  }
  return result;
}

function comparisonResult(workbook: ExcelScript.Workbook, logText: string): JsonObject {
  const errors: JsonObject[] = [];
  const invalidExpectedRows: JsonObject[] = [];
  const invalidLogLines: JsonObject[] = [];
  const expectedCandidates: string[] = [];
  const loggedCandidates: string[] = [];
  const worksheets = workbook.getWorksheets();

  if (worksheets.length === 0) {
    errors.push({ source: "workbook", code: "missing_sheets" });
    errors.push({ source: "workbook", code: "sheet_count", value: 0 });
  }
  if (worksheets.length !== 1) {
    errors.push({ source: "workbook", code: "sheet_count", value: worksheets.length });
  }
  for (let index = 0; index < worksheets.length; index++) {
    const name = worksheets[index].getName();
    if (name !== "Batch_Input") {
      errors.push({ source: "workbook", code: "unexpected_sheet", index: index + 1, value: name });
    }
  }

  // The Python comparator inspects the first sheet after recording sheet-name
  // and count errors. Keep that diagnostic order and behavior here.
  const firstSheet = worksheets.length > 0 ? worksheets[0] : undefined;
  let rows: CellValue[][] = [];
  if (firstSheet) {
    const usedRange = firstSheet.getUsedRange(true);
    if (usedRange) {
      const lastRowExclusive = usedRange.getRowIndex() + usedRange.getRowCount();
      const lastColumnExclusive = usedRange.getColumnIndex() + usedRange.getColumnCount();
      const values = firstSheet
        .getRangeByIndexes(0, 0, lastRowExclusive, lastColumnExclusive)
        .getValues();
      rows = values.map((row) => row.map((value) => value as CellValue));
    }

    if (rows.length < 2) {
      errors.push({ source: "workbook", code: "missing_header" });
    } else {
      const headerRow = rows[1];
      const header: CellValue = headerRow.length > 0 ? headerRow[0] : null;
      if (header !== "MQ_ID") {
        errors.push({ source: "workbook", code: "header_mismatch", row: 2, expected: "MQ_ID", value: header });
      }

      for (let rowIndex = 0; rowIndex < rows.length; rowIndex++) {
        const row = rows[rowIndex];
        for (let columnIndex = 1; columnIndex < row.length; columnIndex++) {
          const value = row[columnIndex];
          if (hasValue(value)) {
            errors.push({
              source: "workbook",
              code: "unexpected_column",
              row: rowIndex + 1,
              column: columnName(columnIndex),
              value,
            });
          }
        }
      }

      let lastPopulatedIndex = 1;
      for (let index = 2; index < rows.length; index++) {
        if (rows[index].some((value) => hasValue(value))) {
          lastPopulatedIndex = index;
        }
      }
      for (let index = 2; index <= lastPopulatedIndex; index++) {
        const row = rows[index];
        const value: CellValue = row.length > 0 ? row[0] : null;
        const rowNumber = index + 1;
        if (!hasValue(value)) {
          invalidExpectedRows.push({ row: rowNumber, value });
          errors.push({ source: "workbook", code: "blank_expected_id", row: rowNumber });
          continue;
        }
        if (typeof value !== "string") {
          invalidExpectedRows.push({ row: rowNumber, value });
          errors.push({ source: "workbook", code: "invalid_expected_id", row: rowNumber, value });
          continue;
        }
        const normalized = value.trim();
        if (!/^MQ-[0-9]{4}$/.test(normalized)) {
          invalidExpectedRows.push({ row: rowNumber, value: normalized });
          errors.push({ source: "workbook", code: "invalid_expected_id", row: rowNumber, value: normalized });
          continue;
        }
        expectedCandidates.push(normalized);
      }
      if (expectedCandidates.length === 0) {
        errors.push({ source: "workbook", code: "no_expected_ids" });
      }
    }
  }

  // Python str.splitlines() recognizes Unicode separators in addition to CR/LF.
  const logLines = logText.split(/\r\n|[\n\r\v\f\u001c-\u001e\u0085\u2028\u2029]/);
  for (let index = 0; index < logLines.length; index++) {
    const line = logLines[index];
    if (!line.startsWith("MQ_BOX_ID=")) {
      continue;
    }
    const value = line.substring("MQ_BOX_ID=".length).trim();
    if (!/^MQ-[0-9]{4}$/.test(value)) {
      invalidLogLines.push({ line: index + 1, value });
      errors.push({ source: "log", code: "invalid_log_id", line: index + 1, value });
      continue;
    }
    loggedCandidates.push(value);
  }

  const duplicateValues = (values: string[]): string[] => {
    const counts = new Map<string, number>();
    for (const value of values) {
      counts.set(value, (counts.get(value) || 0) + 1);
    }
    return Array.from(counts.entries())
      .filter((entry) => entry[1] > 1)
      .map((entry) => entry[0]);
  };
  const duplicateExpected = duplicateValues(expectedCandidates);
  const duplicateLogged = duplicateValues(loggedCandidates);
  for (const value of duplicateExpected) {
    errors.push({ source: "workbook", code: "duplicate_expected_id", value });
  }
  for (const value of duplicateLogged) {
    errors.push({ source: "log", code: "duplicate_logged_id", value });
  }

  const nonemptyLines = logLines.filter((line) => line.trim() !== "");
  const endMarkerPresent = nonemptyLines.length > 0 && nonemptyLines[nonemptyLines.length - 1] === "ALL SUCCESS";
  const expectedIds = uniqueInOrder(expectedCandidates);
  const loggedIds = uniqueInOrder(loggedCandidates);
  const comparisonAvailable = errors.length === 0;
  let missingIds: string[] | null = null;
  let logOnlyIds: string[] | null = null;
  let missingCount: number | null = null;
  let logOnlyCount: number | null = null;
  if (comparisonAvailable) {
    const loggedSet = new Set(loggedIds);
    const expectedSet = new Set(expectedIds);
    missingIds = expectedIds.filter((value) => !loggedSet.has(value));
    logOnlyIds = loggedIds.filter((value) => !expectedSet.has(value));
    missingCount = missingIds.length;
    logOnlyCount = logOnlyIds.length;
  }

  let status: string;
  let stopReason: string | null;
  let stopProcessing: boolean;
  let statusLabel: string;
  if (errors.length > 0) {
    status = "input_error";
    stopReason = "input_error";
    stopProcessing = true;
    statusLabel = "要確認";
  } else if (!endMarkerPresent) {
    status = "log_incomplete";
    stopReason = "missing_end_marker";
    stopProcessing = true;
    statusLabel = "要確認";
  } else {
    status = "comparison_ready";
    stopReason = null;
    stopProcessing = false;
    statusLabel = (missingIds && missingIds.length > 0) || (logOnlyIds && logOnlyIds.length > 0)
      ? "要確認"
      : "比較完了";
  }

  const diagnosticResultText = comparisonAvailable
    ? [
        ...expectedIds.map((mqId) => {
          const isMissing = (missingIds as string[]).indexOf(mqId) >= 0;
          const result = endMarkerPresent
            ? (isMissing ? "ログ未記録・要確認" : "記録あり")
            : (isMissing ? "ログ未記録（ログ不完全）・要確認" : "記録あり（ログ不完全・要確認）");
          return `${mqId}\t${result}`;
        }),
        ...(logOnlyIds as string[]).map((mqId) => `${mqId}\t予定外ID・要確認`),
      ].join("\n")
    : "";

  return {
    contract_version: "mq-id-result.v1",
    status,
    comparison_available: comparisonAvailable,
    end_marker_present: endMarkerPresent,
    expected_ids: expectedIds,
    logged_ids: loggedIds,
    missing_ids: missingIds,
    log_only_ids: logOnlyIds,
    counts: { expected: expectedIds.length, logged: loggedIds.length, missing: missingCount, log_only: logOnlyCount },
    result_text: diagnosticResultText,
    duplicate_ids: { expected: duplicateExpected, logged: duplicateLogged },
    invalid: { expected_rows: invalidExpectedRows, log_lines: invalidLogLines },
    errors,
    presentation: {
      status_label: statusLabel,
      stop_processing: stopProcessing,
      stop_reason: stopReason,
      human_decision_required: true,
    },
  };
}

function main(workbook: ExcelScript.Workbook, logText: string): string {
  return JSON.stringify(comparisonResult(workbook, logText));
}
