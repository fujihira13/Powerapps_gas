# MQ 2ファイル受付に伴うフロー更新

2026-09-28、Developer環境の既存フロー `ef881fbc-dcb8-f111-b377-7ced8d3141aa` を条件付きで更新した。更新前の行ETagは `W/"3805607"`。ローカル候補 `outputs/flow-implementation/flow-definition.mq-local-candidate.json` と現行定義との差分128か所は、すべて既存MQ添付読取分岐 `Condition_One_Note/else/actions` 内に収まった。

Dataverse APIのPATCHは HTTP 204。直後のGETではフローが有効 (`statecode=1`, `statuscode=2`) で、`clientdata` のJSON値は候補と完全一致した。反映後ETagは `W/"4257750"`。この読戻しは定義の一致であり、実行成功の証明ではない。

`flow-before.json`、`flow-after.json`、`patch-body.json`、`etag.txt` は環境固有の接続参照を含むため `.gitignore` で除外する。`prepare_patch.py` は対象フローのID・名前・有効状態・ETagと差分範囲を確認して最小PATCH本文を作る。変更パスの一覧は `diff-paths.txt` に記録した。

その後、架空の新規件`ed89fb2c-bfba-f111-b377-7ced8d3141aa`で子テーブルの役割別添付2件を実際に読み、フローが転記済み／Excel全文一致まで進むことを確認した。SharePointから生成結果Excelを直接読み、`証跡`の元ログと`MQ_Comparison`の予定5・記録4・欠落`MQ-0003`を確認した。この1件は代表経路の確認であり、添付欠落・通信失敗等の全分岐は未確認。既存件は再実行していない。
