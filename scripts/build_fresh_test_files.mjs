import fs from 'node:fs/promises';
import path from 'node:path';
import { fileURLToPath } from 'node:url';
import { Workbook, SpreadsheetFile, FileBlob } from '@oai/artifact-tool';

const here = path.dirname(fileURLToPath(import.meta.url));
const root = path.resolve(here, '..');
const output = process.argv[2] ? path.resolve(process.argv[2]) : path.join(root, 'outputs', '再テスト用ファイル_2026-10-03');
const previews = path.join(root, 'outputs', 'test-reset-20261003', 'file-previews');
try { await fs.access(output); throw new Error('Output folder already exists; preserve it.'); }
catch (e) { if (e.code !== 'ENOENT') throw e; }
await fs.mkdir(previews, { recursive: true });
const server1 = '再テスト用サーバー1';
const server2 = '再テスト用サーバー2';
const envA = '再テスト環境A';
const envB = '再テスト環境B';
const definitions = [];
for (const [label, environment, start] of [['A', envA, 8001], ['B', envB, 8201]]) {
  for (const differences of [0, 1, 50]) {
    const n = definitions.length + 1;
    const name = `環境${label}_${differences === 0 ? '差異なし' : `差異${differences}件`}`;
    definitions.push({ number: n, name, folder: `${String(n).padStart(2, '0')}_${name}`, environment, server: server1, logEnvironment: environment, logServer: server1, start, differences, stop: null });
  }
}
definitions.push({ number: 7, name: '環境不一致で停止', folder: '07_環境不一致で停止', environment: envA, server: server1, logEnvironment: envB, logServer: server1, start: 8001, differences: 0, stop: '環境不一致' });
definitions.push({ number: 8, name: 'サーバー不一致で停止', folder: '08_サーバー不一致で停止', environment: envA, server: server1, logEnvironment: envA, logServer: server2, start: 8001, differences: 0, stop: 'サーバー不一致' });
const results = [];
for (const d of definitions) {
  const folder = path.join(output, d.folder);
  await fs.mkdir(folder, { recursive: true });
  const ids = Array.from({ length: 100 }, (_, i) => `MQ-${d.start + i}`);
  const logged = ids.slice(0, 100 - d.differences);
  const workbook = Workbook.create();
  const sheet = workbook.worksheets.add('Batch_Input');
  sheet.showGridLines = false;
  sheet.getRange('A1:A102').values = [[`${d.name.replaceAll('_', ' ')} 更新対象一覧`], ['MQ_ID'], ...ids.map(id => [id])];
  sheet.getRange('A1:A102').format.font = { name: 'Arial', size: 11, color: '#17365D' };
  sheet.getRange('A1:A102').format.columnWidth = 68;
  sheet.getRange('A1:A102').format.rowHeight = 23;
  sheet.getRange('A1:A102').format.verticalAlignment = 'center';
  sheet.getRange('A1').format.font = { name: 'Arial', size: 15, bold: true, color: '#17365D' };
  sheet.getRange('A1').format.rowHeight = 34;
  sheet.getRange('A2').format = { fill: '#17365D', font: { name: 'Arial', size: 11, bold: true, color: '#FFFFFF' } };
  sheet.freezePanes.freezeRows(2);
  workbook.recalculate();
  const inspected = await workbook.inspect({ kind: 'table', range: 'Batch_Input!A1:A6', include: 'values', tableMaxRows: 6, tableMaxCols: 1, maxChars: 1300 });
  await fs.writeFile(path.join(previews, `${d.number}-inspect.ndjson`), inspected.ndjson, 'utf8');
  const png = await workbook.render({ sheetName: 'Batch_Input', range: 'A1:A12', scale: 1, format: 'png' });
  await fs.writeFile(path.join(previews, `${d.number}.png`), new Uint8Array(await png.arrayBuffer()));
  const excelName = `${d.name}_更新対象一覧.xlsx`;
  const logName = `${d.name}_サーバーログ.txt`;
  const excelPath = path.join(folder, excelName);
  const logPath = path.join(folder, logName);
  await (await SpreadsheetFile.exportXlsx(workbook)).save(excelPath);
  const log = [`環境: ${d.logEnvironment}`, `サーバー: ${d.logServer}`, 'INFO MQ refresh started.', ...logged.map(id => `MQ_BOX_ID=${id}`), 'INFO MQ refresh finished.', 'ALL SUCCESS', ''].join('\r\n');
  await fs.writeFile(logPath, log, 'utf8');

  const saved = await SpreadsheetFile.importXlsx(await FileBlob.load(excelPath));
  const savedSheet = saved.worksheets.getItem('Batch_Input');
  const savedIds = savedSheet.getRange('A3:A102').values.flat();
  const savedLog = await fs.readFile(logPath, 'utf8');
  const savedLogged = [...savedLog.matchAll(/^MQ_BOX_ID=(MQ-\d{4})\r?$/gm)].map(x => x[1]);
  const missing = savedIds.filter(id => !savedLogged.includes(id));
  const extra = savedLogged.filter(id => !savedIds.includes(id));
  if (savedSheet.getRange('A2').values[0][0] !== 'MQ_ID' || JSON.stringify(savedIds) !== JSON.stringify(ids) || new Set(savedIds).size !== 100 || new Set(savedLogged).size !== savedLogged.length || savedLogged.length !== 100 - d.differences || missing.length !== d.differences || extra.length !== 0 || !savedLog.startsWith(`環境: ${d.logEnvironment}\r\nサーバー: ${d.logServer}\r\n`) || !savedLog.endsWith('\r\nALL SUCCESS\r\n')) throw new Error(`Saved files do not match expectation: ${d.folder}`);
  if ((d.environment !== d.logEnvironment) !== (d.stop === '環境不一致') || (d.server !== d.logServer) !== (d.stop === 'サーバー不一致')) throw new Error(`Wrong mismatch headers: ${d.folder}`);
  results.push({ ...d, excelName, logName, excelPath, logPath, expectedIds: 100, loggedIds: savedLogged.length, missingIds: missing, extraIds: extra, expectedResult: d.stop ? `${d.stop}による停止。結果Excelは作成されない。` : d.differences === 0 ? '差異なし' : `差異あり ${d.differences}件`, localVerification: 'PASS', cloudTest: '未実施' });
  await fs.rename(`${excelPath}.inspect.ndjson`, path.join(previews, `${excelName}.inspect.ndjson`));
  console.log(`${d.folder}: Excel=100, Log=${savedLogged.length}, Missing=${missing.length}, Expected=${d.stop || 'comparison'}`);
}
await fs.writeFile(path.join(root, 'outputs', 'test-reset-20261003', 'file-verification.json'), JSON.stringify(results, null, 2) + '\n', 'utf8');

const rows = results.map(r => `| ${String(r.number).padStart(2, '0')} | ${r.name.replaceAll('_', ' ')} | ${r.server} | ${r.environment} | ${r.expectedResult} |`).join('\n');
const folders = results.map(r => `- ${r.folder}\n  - ${r.excelName}\n  - ${r.logName}`).join('\n');
const guide = `# 再テストの手順\n\n同じ番号のフォルダーにあるExcelとログを1つずつ添付します。\n\n## 最初に確認すること\n\n過去のテスト記録の削除は、削除対象・復元方法を確認して承認後に行います。この一式を作成した時点では削除していません。実機の再テストも未実施です。\n\n新しいテスト用の登録名は以下です。登録がまだない場合は、管理画面で同じ文字の名前を登録してから照合します。既存の設定をこの名前に変更する必要はありません。\n\n| サーバー名 | 対象の環境名 |\n|---|---|\n| ${server1} | ${envA} |\n| ${server1} | ${envB} |\n| ${server2} | ${envA} |\n\n${server1}を追加するときに${envA}を入力します。そのサーバーの「環境を見る」から${envB}を追加します。${server2}は${envA}と一緒に追加します。サーバー1には2環境、サーバー2には1環境がある構成です。\n\n## 役割\n\n- 私：入力ファイルと期待結果の準備、保存結果の読み取り、問題が出た場合の調査。\n- あなた：PCの実アプリでの操作、見やすさ・使いやすさの確認。「テスト結果記録.csv」に結果を記録できます。\n\n## 1. 管理操作を確認する\n\n1. 上記の3組を追加します。名前の空欄・100文字超過・重複は保存できないこと、入力をキャンセルすると登録が増えないことを確認します。\n2. サーバー1の名前を一時的に「再テスト用サーバー1_名称変更確認」に変更します。その配下の2環境が同じサーバーにまとまっていることを確認し、元の${server1}に戻します。\n3. 環境Bの名前を一時的に「再テスト環境B_名称変更確認」に変更します。環境Aとサーバー2側の環境Aは変わらないことを確認し、元の${envB}に戻します。\n4. サーバー1の環境Bを使用終了にします。次にサーバー1を使用終了にして再使用します。環境Bは使用終了のまま、環境Aだけ使用できることを確認します。最後に環境Bを再使用します。\n5. 受付へ戻り、上記の3組が選べることを確認します。環境を変更したときに別の環境のサーバーが残っていないことも確認します。\n\n名称と使用状態を元に戻してから、以下の照合へ進んでください。管理操作の保存を何度も連打しないでください。\n\n## 2. Excelとログを照合する\n\n1. 受付で下表の環境・サーバーを選びます。\n2. 対応する番号のフォルダーから「更新対象一覧.xlsx」と「サーバーログ.txt」を添付します。\n3. 「照合を開始」を1回押します。処理が終わったら「ログと結果を見る」を開きます。\n4. 期待結果、入力ファイル、結果Excel、SharePointの保存内容を確認します。停止用07・08では停止理由を確認します。\n\n| 番号 | フォルダーの内容 | 選ぶサーバー | 選ぶ環境 | 期待結果 |\n|---|---|---|---|---|\n${rows}\n\n### 差異件数とID\n\n- 環境AのExcel：MQ-8001〜MQ-8100の100件。01のログは100件、02は99件、03は50件です。\n- 02でログにないID：MQ-8100。03でログにないID：MQ-8051〜MQ-8100の50件。\n- 環境BのExcel：MQ-8201〜MQ-8300の100件。04のログは100件、05は99件、06は50件です。\n- 05でログにないID：MQ-8300。06でログにないID：MQ-8251〜MQ-8300の50件。\n- 03・06では「前へ」「次へ」で最初と最後のページを確認します。10件ずつ5ページ、最初は「前へ」、最後は「次へ」が無効になることを確認します。\n\n### 停止用ファイルの意味\n\n- 07：選ぶのは${envA}、ログに書かれているのは${envB}。サーバー名とMQ IDは一致させています。環境が違う理由で停止することを確認します。\n- 08：選ぶのは${server1}、ログに書かれているのは${server2}。環境名とMQ IDは一致させています。サーバーが違う理由で停止することを確認します。\n- 停止した同じ件を再実行する操作はありません。再確認したい場合は新しい照合として始めます。\n\nログ内のALL SUCCESSはログの終了表示です。差異0件や実際のサーバー更新成功を保証する文言ではありません。成功した照合01〜06の各SharePointフォルダーには入力Excel・入力ログ・結果Excelの3ファイルがそろうことを確認します。\n\n## 3. 判断・レビュー・完了履歴を確認する\n\n追加の照合を作らず、01〜06の結果を使います。\n\n1. 01：担当者の判断を「問題なし」にし、コメントを入力して下書きを保存します。開き直して入力が残ることを確認します。\n2. 01：レビュー依頼の確認でキャンセルし、依頼前の状態を保つことを確認します。再度依頼し、同じ確認画面で担当者の判断・コメントを読み、承認してレビューを完了します。\n3. 02：「要対応」でコメントを空欄にした場合の入力案内を確認します。コメントを入れて依頼します。レビューの差し戻し理由も空欄では完了できないことを確認し、理由を記入して差し戻します。担当者側で修正、再依頼、承認する流れを確認します。\n4. 03：「判断保留」ではコメントが必要なことを確認し、コメントを入れて下書きを保存します。\n5. 完了した01を完了履歴へ移します。一覧が切り替わっても元の判断・コメント・添付・結果が同じ件に残っていることを確認します。\n6. 戻るボタン、青いホバー表示、画面の欠け・重なり、環境を見るボタンで対象一覧が変わることをPC幅で確認します。\n\n現行アプリは同じ利用者で担当者操作とレビュー操作を確認する構成です。別アカウントへの権限分離を試験したことにはなりません。照合停止やレビュー操作で、既存の個人向けTeams通知が届く場合があります。\n\n## ファイルの場所\n\n${folders}\n\n## 作成時の確認\n\n8組のファイルを保存後に読み直し、Excelの100 ID、ログのID数、欠落数、名前の不一致箇所、終了行をローカルで確認しました。クラウドでの8件照合・管理操作・レビュー・履歴移動の結果は「未実施」です。\n`;
await fs.writeFile(path.join(output, '最初に読む_テスト手順.md'), guide, 'utf8');
const checklist = [
  ['M01', '管理', 'サーバー1＋環境A/B、サーバー2＋環境Aの3組を追加', '追加した3組が使用できる'],
  ['M02', '管理', '空欄・100文字超過・重複・キャンセル', '保存されず入力理由が表示される。キャンセルは無変更'],
  ['M03', '管理', 'サーバー名変更して元に戻す', '配下2環境が一緒に変更される'],
  ['M04', '管理', '環境B名称変更して元に戻す', '環境Aや他サーバーの環境Aは変わらない'],
  ['M05', '管理', '子環境終了→親サーバー終了→親再使用', '子の終了状態が保持される'],
  ['M06', '受付', '子再使用・受付へ戻る・環境候補変更', '3組が選択可能。別環境のサーバーが残らない'],
  ...results.map(r => [`C${String(r.number).padStart(2, '0')}`, '照合', r.folder, r.expectedResult]),
  ['U01', '一覧表示', '03・06のページ送り', '10件ずつ5ページ。先頭と末尾でボタンが無効'],
  ['R01', '判断', '01 下書き保存・開き直し', '判断とコメントが残る'],
  ['R02', 'レビュー', '01 依頼キャンセル→依頼→承認', 'キャンセルは未依頼。依頼後の判断とコメントを確認して完了'],
  ['R03', 'レビュー', '02 コメント必須・差し戻し理由必須・修正再依頼', '空欄では案内。差し戻し後に修正し承認できる'],
  ['R04', '判断', '03 判断保留・コメント入力・下書き', 'コメント必須。保存後に残る'],
  ['H01', '履歴', '01 完了履歴へ移動', '同じ件の判断・コメント・ファイルが残る'],
  ['F01', '保存内容', '01〜06の結果ExcelとSharePoint', '各フォルダーに入力Excel・ログ・結果Excelの3ファイル'],
  ['U02', '画面', 'PC幅で戻る・ホバー・環境を見る・画面表示', '操作に反応し欠けや重なりがない'],
];
const quote = v => `"${String(v).replaceAll('"', '""')}"`;
const csvRows = [['番号', '分類', '操作', '期待結果', '結果', '気づいたこと'], ...checklist.map(r => [...r, '未実施', ''])];
await fs.writeFile(path.join(output, 'テスト結果記録.csv'), '\uFEFF' + csvRows.map(r => r.map(quote).join(',')).join('\r\n') + '\r\n', 'utf8');
console.log(`Created ${results.length} pairs; cloud tests not executed. Folder: ${output}`);
