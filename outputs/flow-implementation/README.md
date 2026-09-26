# 件別転記フロー定義

## 現在の状態

Developer環境のPower Apps (V2)からDataverseの対象1件を受け取り、添付ログと転記先を検査した後、OneDriveのExcelひな形へ転記して読戻し、結果をDataverseへ記録するWDL候補を作成しました。事前検査の不合格は`停止`、コピー以降の失敗や読戻し不一致は`結果不明`にし、確認前に再実行しない旨を記録します。

2026-09-25にDataverse CLIで初版定義をDeveloper環境へPOSTし、フロー `ef881fbc-dcb8-f111-b377-7ced8d3141aa` を1件作成しました。Power Automate画面のresource IDは`ccbc5642-9cce-b1e9-07f5-8174f938bab4`です。初回架空件BはExcelの実内容が正しかった一方、フロー直後の読戻しが0行となり、件状態は`結果不明`です。Bは再実行していません。読戻し再照会と成功時のExcel直接URL記録を含む定義をCLIで反映し、クラウドから定義の一致と有効状態を再確認しました。このURL記録版で架空件F・A・D・Gの正常転記を確認し、Aと日付不一致Cの同時処理ではAだけが成功、CはExcelを作らず停止しました。各成功Excelの内容・件状態・画面リンクも確認済みです。現行フローの停止理由はまだ複数の原因をまとめた文言です。具体的な理由、日付の実在性検査、ログ本文の読取失敗時の停止を加えた`flow-definition.excelurl-c02-local-candidate.json`はローカル候補のみで、クラウド未反映です。詳細は`docs/TASKS.md`を参照してください。

## 生成物

- `workflow-create-body.json`: Dataverse Web API `POST /api/data/v9.2/workflows`に渡す純粋なworkflowオブジェクト。`clientdata`はJSON文字列です。
- `flow-definition.candidate.json`: WDLの`clientdata`オブジェクト。
- `flow-definition.excelurl-c02-local-candidate.json`: 現在のExcel URL／読戻し経路に、具体的な入力異常理由・実在日付検査・ログ読取失敗時の停止記録を組み合わせた最新ローカル候補。クラウドへは未反映です。
- `workflow-create-api-request.json`: 宛先と送信bodyを含むローカルプレビュー。送信機能はありません。
- `flow-candidate-status.json`: 実装範囲、確認済み事項、制限と未確認事項。
- `build_flow_definition.py`: 決定的な生成とローカル静的検査。
- `test_flow_definition.py`: WDL構造と安全条件のオフラインテスト。

## フロー経路

1. `caseId`をPower Apps (V2)トリガーから受け取り、Dataverseの案件行を取得します。
2. 状態が`開始受付済み`であること、添付メモが1件であること、ログ内の処理日・環境・サーバー・実行番号が案件と一致することを確認します。
3. 環境・サーバーに一致する有効な転記先が1件だけで、指定のT006フォルダーと一致することを確認します。
4. 同一caseIdの固定ファイル名を使い、実動作確認済みのT002と同じ`CopyDriveFileByPath`形式でT006ひな形をコピーします。`overwrite=false`です。
5. Excelの`Evidence`表にあるひな形行を置換し、値を読み戻して照合します。ローカル修正候補では、読戻しが0行だった場合だけ10秒後に1回再照会します。1行の9項目がすべて一致した場合だけ状態を`転記済み`、確認結果を`全文一致`にします。再照会でも確認できなければ`結果不明`です。

コピー前の検査不合格は、理由とともに`停止`を記録します。コピー以降の失敗・読戻し不一致は`結果不明`を記録します。結果不明時はOneDrive/Excelを確認するまで再実行しない設計です。URL記録版では読戻し一致の成功分岐だけで既存ファイルの直接URLを`excelurl`へ記録し、共有リンクは作りません。このURL経路は架空件F・A・D・Gの実機実行で確認済みです。具体的な停止理由と読取失敗分岐は別のローカル候補であり、クラウド実行は未確認です。

## 制限

- 1セル30,000文字までの単一行転記です。長いログの分割転記には対応していません。
- コピー・Excel書込の自動再試行、同時起動のロック、要求ID・試行IDは未実装です。現行版の読戻しが0行の場合は、読取り専用で1回だけ再照会します。同じcaseIdの出力がすでに存在する場合、上書きせずコピー操作が失敗し、結果不明になります。
- 明示したコピー・Excel書込・読戻しの失敗分岐以外の予期しない障害や、状態更新そのものの失敗からの復旧は未検証です。
- Canvas画面で成功・停止の状態とExcelリンクを表示する経路は、架空件F・A・D・Gおよび日付不一致Cで確認済みです。新しい個別の停止理由を画面へ表示する経路は、その候補をクラウドに反映した後の確認が必要です。

## 確認方法

```powershell
python -m unittest discover -s outputs/flow-implementation -p test_flow_definition.py
python outputs/flow-implementation/build_flow_definition.py
python outputs/flow-implementation/case_transfer.py --self-test
```

テストと生成スクリプトはローカルのWDL構造、接続参照、操作名、条件分岐、JSON参照の循環、`runAfter`参照範囲を検査します。これはPower AutomateのDesigner/APIスキーマ検証ではなく、コネクター接続や実行成功を保証しません。利用可能な`validate_flow` MCPがないため、Microsoft公式コネクター資料と既存T002保存済み定義を根拠に構成しています。

## 確認済みと未確認

- Developer環境のDataverse、OneDrive、Excel接続参照は読み取りで存在を確認し、架空件の転記・Excel読戻しを実行しました。
- Dataverseの案件・転記先列、T006ひな形パス、既存T002の`CopyDriveFileByPath`とExcel `PatchItem`の保存形式を確認しました。
- Dataverse APIによるWDLの作成・有効化・定義読戻し、Power Apps (V2)経由の起動、架空ログの転記、Excel内容の読戻しと画面リンクは確認済みです。Designerで保存したJSONとの比較、および個別理由を持つ新候補のDesigner/APIスキーマ検証とクラウド実行は未確認です。
- T006ひな形のExcel Online UIでの開封は未確認です。保存後のExcelファイル自体とEvidence表の内容は読戻しで確認済みです。

## 一次資料

- [コードを使ったクラウドフローの操作](https://learn.microsoft.com/en-us/power-automate/manage-flows-with-code)
- [Microsoft Dataverse コネクター](https://learn.microsoft.com/en-us/connectors/commondataserviceforapps/)
- [OneDrive for Business コネクター](https://learn.microsoft.com/en-us/connectors/onedriveforbusiness/)
- [Excel Online (Business) コネクター](https://learn.microsoft.com/en-us/connectors/excelonlinebusiness/)
