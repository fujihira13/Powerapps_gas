# MQフロー候補（ローカル生成物。現行クラウド状態を含む）

この資料と生成手順はローカル候補を説明し、実行しても現行フローを更新しません。候補生成物そのものはCanvas、Dataverse、Power Automate、OneDriveへ送信しません。一方、2026-09-27時点では、別途、Developer環境の件表7列・OneDrive上のOffice Script 3件・既存フロー更新が反映・読戻し済みです。Studio保存済みCanvasとrun92704の1件実機結果も確認しました。これらの実物の証拠と残る未確認範囲は[docs/TASKS.md T-013](../../docs/TASKS.md)を参照してください。

## 生成と静的検証

プロジェクトルートで実行します。

```powershell
python outputs/flow-implementation/build_flow_definition.py --mq-candidate --mq-script-id-source outputs/runless-migration-20260927/flow-before.json
python outputs/flow-implementation/build_mq_column_payloads.py
python outputs/flow-implementation/build_osts_wrappers.py
python -m unittest discover -s outputs/flow-implementation -p "test_*.py"
```

生成物は`flow-definition.mq-local-candidate.json`、`dataverse-column-payloads/`内の7列JSON、`office-scripts/osts-candidates/`内の3つの`.osts`候補です。今回のMQフロー候補は保存済みの現行フローGETからOffice Script ID 3つを継承し、元フローの値と一致することをローカルで確認しました。候補は未反映であり、新しい結果Excelひな形のOneDrive配置とフロー更新・読戻しを終えるまで実行対象ではありません。別環境で生成する場合は、その環境の現行フローとScript IDを別途確認してください。

## 現行候補からの差分

- Power Appsの入力は従来どおり`caseId` 1つです。
- 添付1件は従来のログ検査・Evidence表への転記・全件読戻しへ進みます。MQ比較スクリプトは呼びません。
- MQ経路は添付2件だけを受け付け、拡張子が`.txt` 1件と`.xlsx` 1件であることを検査します。欠落、重複、別形式は出力ブック作成前に停止します。
- `.xlsx`添付は変更せず、T006検証フォルダーに件ID名の一時コピーとして保持します。元ファイルや一時コピーは自動削除しません。
- `read_validate_batch_input.ts`は`Batch_Input`を読み、`mq-id-feature`の`mq-id-input.v1` / `mq-id-result.v1`規則に沿ってID・重複・余分なシート/列・`MQ_BOX_ID=`行・末尾の`ALL SUCCESS`を検査します。
- 入力形式エラーでは結果Excelを作らず、MQ診断7列も更新しません。
- 末尾`ALL SUCCESS`がない場合も結果Excelを作らず、比較・Evidence転記・結果リンク表示へ進みません。一方、形式が有効な入力から算出した予定/記録/暫定欠落件数、欠落ID、ID別TSVは診断情報として7列に記録し、終端「なし」・比較状態「要確認」を示します。この更新は処理成功やMQ結果の確定を意味しません。診断更新に失敗して結果が不明な場合は再実行前に状態確認が必要です。
- 結果ExcelはEvidence表付きひな形の件ID名コピーです。既存のEvidence表を残し、別の`MQ_Comparison`シートと`MQ_ComparisonTable`を作ります。
- 末尾マーカーのあるログは差異があっても「要確認」を表示します。これはログ上の記録差であり、サーバーの更新成否を意味しません。
- MQ結果シートを別のOffice Scriptで読戻し、さらに既存Evidence表も件ID・本文を照合してからだけ、7つのMQ列と成功状態・結果リンクを書きます。
- コピー、スクリプト書込み、読戻しの失敗・タイムアウトは「結果不明」とし、自動再試行しません。部分結果を成功扱いにしたり、結果リンクを表示したりしません。

`cr6cb_mqresulttext`はCanvas詳細画面で行単位表示できるよう、1 ID / 1行のTSVです（LF改行、ヘッダーなし）。例：`MQ-0001<TAB>記録あり`。終端なしでは記録有無の行に「ログ不完全・要確認」を付け、予定外ログIDも末尾に`予定外ID・要確認`として含みます。`ALL SUCCESS`はログ終端表示で、MQ更新成功を示しません。

7列のpayloadはローカルJSON候補で、API送信しません。全列を任意入力にし、整数列は0以上、短文列は16/20文字、欠落ID本文は16,384文字、結果TSVは30,000文字を上限として指定しています。Developer環境の現行件表では7列を作成し読み戻し済みです。このpayload候補を別環境へ適用する前には、既存テーブル・SchemaNameの衝突、コネクター上限、対象ユーザーの表示要件を確認してください。上限超過時の切り捨てはこの候補では行いません。

## 未確認事項と実行前提

2026-09-27時点のMicrosoft公式資料では、Power AutomateはExcel Online (Business)のRun scriptアクションを通じてOffice Scriptsを呼べます。`main`の引数・返り値の型がアクションのパラメーターに反映され、変更時にはRun scriptアクションを作り直す必要があります。Power AutomateからのOffice Scripts利用にはMicrosoft 365のBusinessライセンス要件があります。組織管理者によるOffice Scriptsやコネクターの制限もあり得ます。

Developer環境ではOneDrive上のScript 3件（Writer／readbackはversion 3.0）とFlow guardの更新・読戻しを確認し、run92704で1件のフロー実行、出力2シート、case状態、画面を照合しました。これは当該の架空入力1件の実機確認です。ローカル生成物は現行クラウドフローの正本ではなく、未試験の異常系・ログのみ経路・他環境のライセンスや権限、別環境への移植性は未確認です。ローカル`.osts`候補全体の独立コンパイルも行っていません。

このローカル生成物を今後別環境へ反映する場合は、その環境用に3つのScript IDを割り当て、Run scriptアクションのスキーマと列・権限を確認し、出力シートとEvidence表を独立読戻ししてください。Developer環境の既存実装はrun92704を完了済みのため再実行せず、今回の新仕様の統合試験では実行回を入力しない新件を使用します。実機試験の詳細と未完了条件は`docs/TASKS.md` T-013・T-014を参照してください。

Microsoft Learnで確認したOffice Scriptsの新規作成経路はExcelの`Automate > New Script > Create in Code Editor` UIです。Office ScriptsはOneDriveの`Documents/Office Scripts`に`.osts`ファイルとして保存されます。Microsoft Learnは拡張子と保存先を説明していますが、今回参照した公式資料に`.osts`本文のJSONスキーマや`version`/`body`フィールドの定義はありません。ローカル候補は公開されている`.osts`実例の`version: "0.2.0"`に合わせ、TypeScript本文をそのまま`body`に入れたJSON包装にしています。この値と包装形式は公式仕様として保証されず、Office Scriptsで解釈できるか未検証です。静的テストで本文一致とJSON可読性は確かめますが、Excel UIへの読込、Office Scriptsコンパイル、OneDrive保存・読戻しは未検証です。これらの`.osts`候補はローカルに作るだけで、API送信や登録は行いません。

## 確認したMicrosoft公式資料

- [Run Office Scripts with Power Automate](https://learn.microsoft.com/en-us/office/dev/scripts/develop/power-automate-integration)
- [Pass data to and from scripts in Power Automate](https://learn.microsoft.com/en-us/office/dev/scripts/develop/power-automate-parameters-returns)
- [Office Scripts platform limits and requirements](https://learn.microsoft.com/en-us/office/dev/scripts/testing/platform-limits)
- [Excel Online (Business) connector](https://learn.microsoft.com/en-us/connectors/excelonlinebusiness/)
- [Office Scripts file storage and ownership](https://learn.microsoft.com/en-us/office/dev/scripts/overview/script-storage)
- [Tutorial: Update a spreadsheet from a Power Automate flow](https://learn.microsoft.com/en-us/office/dev/scripts/tutorials/excel-power-automate-manual)
