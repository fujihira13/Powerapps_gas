import assert from "node:assert/strict";
import { execFileSync } from "node:child_process";
import { readFileSync } from "node:fs";
import path from "node:path";
import vm from "node:vm";
import { stripTypeScriptTypes } from "node:module";

function loadMain(scriptName) {
  const file = path.join("outputs", "flow-implementation", "office-scripts", `${scriptName}.ts`);
  const source = readFileSync(file, "utf8");
  const javascript = stripTypeScriptTypes(source, { mode: "strip" });
  const context = {};
  vm.runInNewContext(`${javascript}\nglobalThis.__main = main;`, context, { filename: file });
  return context.__main;
}

class MockRange {
  constructor(sheet, row, column, rowCount, columnCount) {
    Object.assign(this, { sheet, row, column, rowCount, columnCount });
  }
  setValues(values) {
    assert.equal(values.length, this.rowCount);
    for (let row = 0; row < this.rowCount; row++) {
      assert.equal(values[row].length, this.columnCount);
      for (let column = 0; column < this.columnCount; column++) {
        this.sheet.cells.set(`${this.row + row},${this.column + column}`, values[row][column]);
      }
    }
  }
  getValues() {
    return Array.from({ length: this.rowCount }, (_, row) =>
      Array.from({ length: this.columnCount }, (_, column) =>
        this.sheet.cells.get(`${this.row + row},${this.column + column}`) ?? null));
  }
  getFormat() {
    return { setWrapText() {}, autofitRows() {}, autofitColumns() {}, setColumnWidth() {}, getFill() { return { setColor() {} }; } };
  }
  getRowIndex() { return this.row; }
  getColumnIndex() { return this.column; }
  getRowCount() { return this.rowCount; }
  getColumnCount() { return this.columnCount; }
}

class MockTable {
  constructor(range) { this.range = range; this.name = ""; }
  setName(name) { this.name = name; }
  getRange() { return this.range; }
}

class MockWorksheet {
  constructor(name, workbook) {
    this.name = name;
    this.workbook = workbook;
    this.cells = new Map();
    this.tables = [];
  }
  getName() { return this.name; }
  getRangeByIndexes(row, column, rowCount, columnCount) {
    return new MockRange(this, row, column, rowCount, columnCount);
  }
  getRange() { return new MockRange(this, 0, 0, 0, 0); }
  addTable(range) {
    const table = new MockTable(range);
    this.tables.push(table);
    return table;
  }
  getTables() { return this.tables.slice(); }
  getTable(name) { return this.tables.find((table) => table.name === name); }
  getUsedRange() {
    const used = Array.from(this.cells.entries()).filter(([, value]) =>
      value !== null && value !== undefined && value !== "");
    if (used.length === 0) return undefined;
    const positions = used.map(([key]) => key.split(",").map(Number));
    const maxRow = Math.max(...positions.map(([row]) => row));
    const maxColumn = Math.max(...positions.map(([, column]) => column));
    return new MockRange(this, 0, 0, maxRow + 1, maxColumn + 1);
  }
  delete() { this.workbook.sheets = this.workbook.sheets.filter((sheet) => sheet !== this); }
}

class MockWorkbook {
  constructor() { this.sheets = []; }
  addWorksheet(name) {
    const sheet = new MockWorksheet(name, this);
    this.sheets.push(sheet);
    return sheet;
  }
  getWorksheet(name) { return this.sheets.find((sheet) => sheet.name === name); }
  getWorksheets() { return this.sheets.slice(); }
}

function workbookWithRows(name, rows) {
  const workbook = new MockWorkbook();
  const sheet = workbook.addWorksheet(name);
  const width = Math.max(...rows.map((row) => row.length));
  rows.forEach((row, rowIndex) => {
    for (let column = 0; column < width; column++) {
      sheet.cells.set(`${rowIndex},${column}`, row[column] ?? null);
    }
  });
  return workbook;
}

const readInput = loadMain("read_validate_batch_input");
const writeReport = loadMain("write_mq_comparison");
const readReport = loadMain("readback_mq_comparison");
const python = [
  "import json, sys",
  "from openpyxl import load_workbook",
  "workbook = load_workbook(sys.argv[1], read_only=True, data_only=True)",
  "sheet = workbook['Batch_Input']",
  "print(json.dumps([list(row) for row in sheet.iter_rows(values_only=True)], ensure_ascii=False))",
].join("\n");
const cases = [
  { key: "diff-found", expected: 6, logged: 5, missing: "MQ-0304", label: "要確認" },
  { key: "pass", expected: 6, logged: 6, missing: null, label: "比較完了" },
];

for (const sample of cases) {
  const prefix = `outputs/flow-implementation/test-fixtures/mq-demo-${sample.key}-20260929`;
  const xlsxPath = `${prefix}.xlsx`;
  const logPath = `${prefix}.txt`;
  const rows = JSON.parse(execFileSync("python", ["-c", python, xlsxPath], { encoding: "utf8" }));
  const logText = readFileSync(logPath, "utf8");
  const result = JSON.parse(readInput(workbookWithRows("Batch_Input", rows), logText));
  assert.equal(result.status, "comparison_ready", sample.key);
  assert.equal(result.counts.expected, sample.expected, sample.key);
  assert.equal(result.counts.logged, sample.logged, sample.key);
  result.source_files = { batch_input: path.basename(xlsxPath), log: path.basename(logPath) };

  const caseId = `case-${sample.key}`;
  const output = new MockWorkbook();
  output.addWorksheet("証跡");
  const written = JSON.parse(writeReport(output, JSON.stringify(result), caseId));
  assert.equal(written.ok, true, written.error || sample.key);
  const worksheets = output.getWorksheets();
  assert.equal(worksheets.length, 1, sample.key);
  assert.equal(worksheets[0].getName(), "MQ ID照合結果", sample.key);

  const tableRows = worksheets[0].getTable("MQ_ComparisonTable").getRange().getValues();
  assert.deepEqual(tableRows[0], ["MQ ID", "Excelの記載", "ログの記録", "照合結果"], sample.key);
  assert.ok(tableRows.every((row) => row.length === 4), sample.key);
  assert.equal(tableRows.length, sample.expected + 1, sample.key);
  const resultById = Object.fromEntries(tableRows.slice(1).map((row) => [row[0], row[3]]));
  if (sample.missing) {
    assert.equal(resultById[sample.missing], "ログに記録なし", sample.key);
  }
  assert.ok(Object.values(resultById).every((value) =>
    value === "一致" || (sample.missing && value === "ログに記録なし")), sample.key);
  assert.equal(worksheets[0].getRangeByIndexes(0, 0, 1, 4).getValues()[0][0], "MQ ID", sample.key);
  assert.equal(worksheets[0].getUsedRange().getRowCount(), sample.expected + 1, sample.key);
  assert.equal(JSON.stringify(Array.from(worksheets[0].cells.values())).includes(logText), false, sample.key);

  const readback = JSON.parse(readReport(output, JSON.stringify(result), caseId));
  assert.equal(readback.ok, true, readback.error || sample.key);
  assert.equal(readback.resultText, written.resultText, sample.key);
  process.stdout.write(`${sample.key}: PASS (${sample.expected} planned, ${sample.logged} logged, 1 worksheet, 4 columns)\n`);
}
