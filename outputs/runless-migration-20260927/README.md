# 1件受付・実行回なし化のクラウド変更記録

対象はDeveloper環境の既存 `cr6cb_evidencecase` 表、既存フロー `ef881fbc-dcb8-f111-b377-7ced8d3141aa`、非公開Canvasアプリ `3186a908-ac5b-48cc-90f5-d50e07282ee7` です。ここにあるファイルは準備と読取り結果です。実際の反映・実機結果は`docs/TASKS.md`のT-014に記録します。

## 変更前の読取り

- `key-before.json`: 有効な4項目代替キーは1件だけです。名前は `cr6cb_EvidenceCaseBusinessKey`、IDは `8818f513-9eb8-f111-b377-7ced8d3141aa` です。
- `runnumber-before.json`: `cr6cb_runnumber` は `ApplicationRequired` で、必須設定の変更が可能です。
- `flow-before.json`: 現在有効なフロー定義のバックアップです。テナント固有の接続参照を含むためGit管理から除外します。
- `key-delete-dependencies.json`: Microsoftの `RetrieveDependenciesForDelete` をキーID・構成要素種別14で読んだ結果は空です。
- 既存件は21件（読取り時点）。既存行・添付・結果Excelは変更しません。

## 反映候補

1. `batchfilename.create.json` で任意の `cr6cb_Batchfilename` テキスト列を追加します。これはユーザーが追加承認した、ログ名と独立した同名Excel警告用の列です。既存行は空のままとし、受付画面では旧21件の添付名も移行境界内で調べます。
2. キーID `8818f513-9eb8-f111-b377-7ced8d3141aa` の定義だけを削除します。件データや列は削除しません。実行前に名前・4列・有効状態・依存が変わっていないことを再確認します。
3. `prepare_metadata_update.py` で現行列メタデータから生成した `runnumber-optional.put.json` を使用し、`cr6cb_runnumber` の `RequiredLevel` だけを `None` にします。生成結果を差分確認したところ、元定義との相違はその値とPUTに必要な型注記のみです。
4. `publish-evidencecase.json` を使って件表のカスタマイズだけを有効化します。これはDataverseのメタデータ反映で、Canvasアプリの一般公開ではありません。
5. 各操作の直後にキー一覧・列定義を読み戻し、対象以外のキーと列を変更していないことを確認します。

上記のメタデータ変更、ひな形追加、フローと非公開Canvasの更新はユーザー承認後に反映しました。新規の架空件を2件保存し、1件目はExcel本文が正しく生成された一方で日時の読戻し比較が偽不一致となり、件状態は`結果不明`です。この件は再実行しません。比較式を修正・読戻し後、ユーザーが追加承認した2件目を1回だけ処理し、件状態`転記済み`／`全文一致`、結果Excelの`ReceivedAtJst`と件ID・ログ全文・MQ予定5／記録4／欠落1を確認しました。旧キーは同じ4項目の新件を作ったため単純に再作成できません。既存データは削除せず保全します。

Microsoft公式資料: [代替キー](https://learn.microsoft.com/en-us/power-apps/developer/data-platform/define-alternate-keys-entity)、[列メタデータの更新](https://learn.microsoft.com/en-us/power-apps/developer/data-platform/webapi/create-update-column-definitions-using-web-api)、[PublishXml](https://learn.microsoft.com/en-us/power-apps/developer/data-platform/webapi/reference/publishxml?view=dataverse-latest)。
