# 件別転記フロー定義

## 現在の状態

Developer環境のPower Apps (V2)からDataverseの対象1件を受け取り、添付ログと転記先を検査した後、OneDriveのExcelひな形へ転記して読戻し、結果をDataverseへ記録するWDL定義を作成・反映しました。事前検査の不合格は`停止`、コピー以降の失敗や読戻し不一致は`結果不明`にし、確認前に再実行しない旨を記録します。

2026-09-25にDataverse CLIで初版定義をDeveloper環境へPOSTし、既存フローを作成しました。初回架空件BはExcelの実内容が正しかった一方、直後の読戻しが0行となり件状態は`結果不明`です。Bは再実行していません。読戻し再照会と成功時のExcel直接URL記録を含む版を反映し、架空件F・A・D・Gの正常転記と、A／日付不一致Cの混在処理を確認しました。

2026-09-26、C02の理由具体化候補を既存フローへ条件付きPATCHし、HTTP 204と直後GETの完全一致、フローの有効状態を確認しました。反映定義は`flow-definition.excelurl-c02-local-candidate.json`（SHA-256 `917d7ec981b5490da494d8f5b3f14b58cf6b2ad723870360634d96ab60bbfe1b`）と一致します。反映後、無効暦日G・日付行なしD・サーバー行なしHの3件が、それぞれ具体的な理由付きで`停止`し、Excelが0冊であることを実機確認しました。さらに正常回帰A/A/run102（対象日2026-09-26、件ID `25ba005c-76b9-f111-b377-7ced8d3141aa`）で、添付1件・177B、件状態`転記済み`／`全文一致`とExcel URL、SharePoint上の結果Excel 1冊・8,265B、Evidence 9列・1行およびログ全文一致を確認しました。旧Bの`結果不明`は維持し、C02添付本文読取不能・異常と正常の混在、C03・C04・C08・C09の失敗・復旧条件は未完了です。詳細は`docs/TASKS.md`を参照してください。

## 生成物

- `workflow-create-body.json`: Dataverse Web API `POST /api/data/v9.2/workflows`に渡す純粋なworkflowオブジェクト。`clientdata`はJSON文字列です。
- `flow-definition.candidate.json`: 初版のWDL `clientdata`。Excel URL／読戻し版より前の旧定義で、現在の稼働版として使いません。
- `flow-definition.excelurl-c02-local-candidate.json`: Excel URL／読戻し経路にC02の具体的な入力異常理由・実在日付検査・添付本文読取失敗時の停止記録を加えた定義。条件付きPATCH後の稼働定義と直後GETで完全一致を確認済みです。
- `workflow-create-api-request.json`: 宛先と送信bodyを含むローカルプレビュー。送信機能はありません。
- `flow-candidate-status.json`: 実装範囲、確認済み事項、制限と未確認事項。
- `build_flow_definition.py`: 決定的な生成とローカル静的検査。
- `test_flow_definition.py`: WDL構造と安全条件のオフラインテスト。

## フロー経路

1. `caseId`をPower Apps (V2)トリガーから受け取り、Dataverseの案件行を取得します。
2. 状態が`開始受付済み`であること、添付メモが1件であること、ログ内の処理日・環境・サーバー・実行番号が案件と一致することを確認します。
3. 環境・サーバーに一致する有効な転記先が1件だけで、指定のT006フォルダーと一致することを確認します。
4. 同一caseIdの固定ファイル名を使い、実動作確認済みのT002と同じ`CopyDriveFileByPath`形式でT006ひな形をコピーします。`overwrite=false`です。
5. Excelの`Evidence`表にあるひな形行を置換し、値を読み戻して照合します。読戻しが0行だった場合だけ10秒後に1回、読取専用で再照会します。1行の9項目がすべて一致した場合だけ状態を`転記済み`、確認結果を`全文一致`にします。再照会でも確認できなければ`結果不明`です。

コピー前の検査不合格は理由とともに`停止`を記録します。無効暦日・日付行欠落・サーバー識別情報欠落の3ケースは、反映後の実機で具体的な停止理由とExcel未作成を確認しました。コピー以降の失敗・読戻し不一致は`結果不明`とし、OneDrive／Excelを確認するまで再実行しません。読戻し一致の成功分岐だけで既存ファイルの直接URLを`excelurl`へ記録し、共有リンクは作りません。反映後の正常回帰A/A/run102では添付1件・177Bから`転記済み`／`全文一致`、Excel URL、結果Excel 1冊・8,265B、Evidence 9列・1行とログ全文一致を実機確認しました。添付本文読取失敗・タイムアウト、異常と正常の混在、C03・C04・C08・C09の復旧条件は未確認または未実装です。

## 制限

- 1セル30,000文字までの単一行転記です。長いログの分割転記には対応していません。
- コピー・Excel書込の自動再試行、同時起動のロック、要求ID・試行ID、安全な再実行判定は未実装です。読戻し0行の場合は読取専用で1回だけ再照会します。同じcaseIdの出力がすでに存在する場合、上書きせずコピー操作が失敗し、`結果不明`になります。
- 明示したコピー・Excel書込・読戻しの失敗分岐以外の予期しない障害や、状態更新そのものの失敗からの復旧は未検証です。
- 受付保存の結果不明から同じ件IDで安全に再保存する処理（C08）と、保存済み件の取消・同じ件での添付差替え（C09）は未実装です。旧Bは`結果不明`のまま保全し、再実行していません。
- C02の異常3ケースと正常回帰A/A/run102は反映後に確認済みです。添付本文読取不能・タイムアウトと異常／正常混在、C03／C04の障害・再実行、C08／C09の保存・取消回復は未確認です。

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
- 既存フローへのC02条件付きPATCH（HTTP 204）、直後GETと反映定義の完全一致、フロー有効状態は確認済みです。反映後のC02異常3件は理由付き停止・Excel0冊を、正常回帰A/A/run102は添付1件・177B、`転記済み`／`全文一致`、Excel URL、結果Excel 1冊・8,265B、Evidence 9列・1行とログ全文一致を確認しました。添付本文読取失敗分岐、異常／正常混在、C03／C04／C08／C09の失敗と回復は未確認または未実装です。
- T006ひな形のExcel Online UIでの開封は未確認です。保存後のExcelファイル自体とEvidence表の内容は読戻しで確認済みです。

## 一次資料

- [コードを使ったクラウドフローの操作](https://learn.microsoft.com/en-us/power-automate/manage-flows-with-code)
- [Microsoft Dataverse コネクター](https://learn.microsoft.com/en-us/connectors/commondataserviceforapps/)
- [OneDrive for Business コネクター](https://learn.microsoft.com/en-us/connectors/onedriveforbusiness/)
- [Excel Online (Business) コネクター](https://learn.microsoft.com/en-us/connectors/excelonlinebusiness/)
