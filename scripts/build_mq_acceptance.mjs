import fs from 'node:fs/promises';
import path from 'node:path';
import { fileURLToPath } from 'node:url';
import { Workbook, SpreadsheetFile, FileBlob } from '@oai/artifact-tool';

const root = path.resolve(path.dirname(fileURLToPath(import.meta.url)), '..');
const output = path.join(root, 'samples', 'mq-acceptance');
const previews = path.join(root, 'outputs', 'mq-acceptance-previews');
await fs.mkdir(previews, { recursive: true });
const results = [];
for (const environment of ['a', 'b']) {
  const label = environment.toUpperCase();
  const folder = path.join(output, `environment-${environment}`);
  await fs.mkdir(folder, { recursive: true });
  const start = environment === 'a' ? 3001 : 4001;
  const ids = Array.from({ length: 100 }, (_, i) => `MQ-${start + i}`);
  for (const differences of [0, 1, 50]) {
    const stem = `mq-env-${environment}-diff-${differences}`;
    const wb = Workbook.create();
    const sheet = wb.worksheets.add('Batch_Input');
    sheet.showGridLines = false;
    sheet.getRange('A1:A102').values = [[`更新対象一覧／環境${label}`], ['MQ_ID'], ...ids.map(id => [id])];
    sheet.getRange('A1:A102').format.font = { name: 'Arial', size: 11, color: '#172B4D' };
    sheet.getRange('A1:A102').format.columnWidth = 36;
    sheet.getRange('A1:A102').format.rowHeight = 24;
    sheet.getRange('A1').format.font = { name: 'Arial', size: 15, bold: true, color: '#172B4D' };
    sheet.getRange('A1').format.rowHeight = 32;
    sheet.getRange('A2').format = { fill: '#163A5F', font: { name: 'Arial', size: 11, bold: true, color: '#FFFFFF' } };
    wb.recalculate();
    await wb.inspect({ kind: 'table', range: 'Batch_Input!A1:A6', include: 'values', tableMaxRows: 6, tableMaxCols: 1 });
    if (JSON.stringify(sheet.getRange('A3:A102').values.flat()) !== JSON.stringify(ids)) throw Error('Excel IDs mismatch');
    const png = await wb.render({ sheetName: 'Batch_Input', range: 'A1:A12', scale: 1.5, format: 'png' });
    await fs.writeFile(path.join(previews, `${stem}.png`), new Uint8Array(await png.arrayBuffer()));
    const workbookPath = path.join(folder, `${stem}.xlsx`);
    await (await SpreadsheetFile.exportXlsx(wb)).save(workbookPath);
    const logged = ids.slice(0, 100 - differences);
    const log = [`環境: 架空環境${label}`, `サーバー: 架空サーバー${label}`, 'INFO MQ refresh started.', ...logged.map(id => `MQ_BOX_ID=${id}`), 'INFO MQ refresh finished.', 'ALL SUCCESS'].join('\r\n') + '\r\n';
    const logPath = path.join(folder, `${stem}.txt`);
    await fs.writeFile(logPath, log, 'utf8');
    const reloaded = await SpreadsheetFile.importXlsx(await FileBlob.load(workbookPath));
    const savedIds = reloaded.worksheets.getItem('Batch_Input').getRange('A3:A102').values.flat();
    const savedLogged = [...(await fs.readFile(logPath, 'utf8')).matchAll(/^MQ_BOX_ID=(MQ-\d+)\r?$/gm)].map(match => match[1]);
    const missing = savedIds.filter(id => !savedLogged.includes(id));
    if (savedIds.length !== 100 || new Set(savedIds).size !== 100 || savedLogged.length !== 100 - differences || new Set(savedLogged).size !== savedLogged.length || missing.length !== differences || savedLogged.some(id => !savedIds.includes(id))) throw Error('Saved pair verification failed');
    results.push({ environment: `環境${label}`, server: `サーバー${label}`, stem, excel: path.relative(root, workbookPath).replaceAll('\\', '/'), log: path.relative(root, logPath).replaceAll('\\', '/'), expectedIds: 100, loggedIds: savedLogged.length, differences, missingIds: missing });
    console.log(`${stem}: Excel=100 log=${savedLogged.length} differences=${missing.length}`);
  }
}
await fs.writeFile(path.join(output, 'expected-results.json'), JSON.stringify(results, null, 2) + '\n');
const rows = results.map(r => `| ${r.environment}／${r.server} | ${r.differences}件 | ${r.stem}.xlsx | ${r.stem}.txt | 100／${r.loggedIds}／${r.differences} |`).join('\n');
await fs.writeFile(path.join(output, 'README.md'), `# 環境A・Bの照合確認用ファイル\n\n6組・12ファイルです。操作確認用に作ったデータで、実務のログではありません。日付・実行回の指定は不要です。\n\n## 保存場所（絶対パス）\n\n- 環境A：\`${path.join(output, 'environment-a')}\`\n- 環境B：\`${path.join(output, 'environment-b')}\`\n\n| 選択する環境／サーバー | 差異 | 更新対象一覧 | サーバーログ | Excel／ログ／差異 |\n|---|---:|---|---|---|\n${rows}\n\n## 確認手順\n\n1. アプリの受付画面で表の環境とサーバーを選びます。環境BではサーバーBを選びます。\n2. 更新対象一覧欄へExcel、サーバーログ欄へ同じ名前のtxtを1つずつ添付します。\n3. 「照合を開始」を1回押し、完了したら「ログと結果を見る」を開きます。\n4. 表の件数と、次の不足IDを確認してください。\n\n- 環境A・1件：MQ-3100。50件：MQ-3051～MQ-3100。\n- 環境B・1件：MQ-4100。50件：MQ-4051～MQ-4100。\n- 差異なし：不足IDはありません。\n\n差異50件の確認では、一覧の最初と最後のID、件数、スクロール、および確認・依頼操作に届くかを見てください。同じ組で再確認してもかまいません。\n\nログの先頭の「架空環境A/B・架空サーバーA/B」は現行のデータベース保存値に合わせています。画面には「環境A/B・サーバーA/B」と表示されます。ALL SUCCESSは末尾表示であり、差異0件やMQ更新成功の証明ではありません。\n\n作成・保存後のID件数と差分はローカルで確認済みです。クラウド照合はユーザーが行います。\n`, 'utf8');
