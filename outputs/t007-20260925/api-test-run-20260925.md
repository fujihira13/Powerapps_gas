# T-007 Dataverse API試験結果

日付: 2026-09-25 (JST)
対象環境: Developer `c1719a14-6cac-eb5b-b598-2254af1c64b7`
対象表: `cr6cb_evidencecase` / EntitySetName `cr6cb_evidencecases`
CLI: `@microsoft/dataverse` 1.0.80 (`dataverse.js`)
実行方式: PowerShellからDataverse CLI。ネットワーク接続を許可した昇格実行。認証情報、Set-Cookie等の応答ヘッダーはこの記録に含めない。

## 試験手順と結果

### 事前GET

T007表示ラベルの既存行確認。GETはHTTP 200、`value=[]`。試験前に同じラベル接頭辞の行がないことを確認した。

```powershell
node '<Dataverse CLI path>' api request --target dataverse --environment 'https://org3d6ad684.crm7.dynamics.com/' --path "/api/data/v9.2/cr6cb_evidencecases?`$select=cr6cb_evidencecaseid,cr6cb_caselabel,cr6cb_environment,cr6cb_server,cr6cb_runnumber,cr6cb_targetdate&`$filter=startswith(cr6cb_caselabel,'T007')&`$orderby=cr6cb_caselabel" --include
```

### 作成要求

1. `case-create-requests/01-valid.json` — HTTP 201 Created、CLI終了コード0。作成ID `fed4e447-b1b8-f111-b377-7ced8d3141aa`、ラベル `T007正常01`、ETag `W/"3092086"`、対象処理日 `2026-09-25`。
2. `case-create-requests/02-duplicate.json` — 同じ4項目の値を使った重複要求。HTTP 412 Precondition Failed、エラーコード `0x80060892`、CLI終了コード1。作成IDなし。
3. `case-create-requests/03-missing-environment.json` — 環境列を省いた要求。**予想外にHTTP 201 Created**、CLI終了コード0。作成ID `3086ba97-b1b8-f111-b377-7ced8d3141aa`、ラベル `T007環境欠落03`、ETag `W/"3092090"`。

各POSTは次の共通形式で、ペイロードだけ上記JSONへ変更した。`Prefer:return=representation`で作成行のIDとETagを取得した。

```powershell
node '<Dataverse CLI path>' api request --target dataverse --environment 'https://org3d6ad684.crm7.dynamics.com/' --path '/api/data/v9.2/cr6cb_evidencecases' --method POST --body-file '<case-create-requests JSON path>' --header 'Prefer:return=representation' --include
```

### 読戻し

- 01-validの後: GET HTTP 200、1行。ID `fed4e447-b1b8-f111-b377-7ced8d3141aa`、ラベル `T007正常01`、環境 `架空環境T007検証`、サーバー `架空サーバーT007-A`、実行回 `1`、対象処理日 `2026-09-25`、ETag `W/"3092086"`。
- 02-duplicateの後: GET HTTP 200、1行のまま。上記正常行のみで、重複要求による追加行はなかった。
- 03-missing-environmentの後: GET HTTP 200、2行。
  - ID `3086ba97-b1b8-f111-b377-7ced8d3141aa`、ラベル `T007環境欠落03`、環境は空、サーバー `架空サーバーT007-C`、実行回 `3`、対象処理日 `2026-09-25`、ETag `W/"3092090"`。
  - ID `fed4e447-b1b8-f111-b377-7ced8d3141aa`、ラベル `T007正常01`、環境 `架空環境T007検証`、サーバー `架空サーバーT007-A`、実行回 `1`、対象処理日 `2026-09-25`、ETag `W/"3092086"`。

読戻しGETは同じラベル接頭辞と列選択で実行した。`--include`の生出力にはSet-Cookieヘッダーがあるため、ツール出力と証拠にはHTTP状態と必要なJSON項目だけを抽出した。

## 停止・未実施

- 環境必須列が空の行をAPIが受け入れたため、停止条件に従い以降の作成要求を送っていない。未送信: `04-missing-server.json`、`05-missing-run.json`、`06-missing-date.json`、`07-concurrent-a.json`、`08-concurrent-b.json`。
- 実際の作成POSTは3回。うち2件が保存され、重複要求1件はHTTP 412で拒否された。現存行は読戻しGETで2件と確認した。削除はしていない。
- 条件付き更新（現在版の更新と古いETagでの拒否確認）は**未実施**。予想外の保存を受けた時点で以後の書込みを止めたため。
- フローの作成・起動、Excel操作、公開、購入・課金設定変更、既存T001-T003資産の変更は行っていない。

## 判定

重複の4項目キーはこの重複要求をHTTP 412で拒否した。一方、環境列を欠く要求をHTTP 201で保存したため、API経由での必須項目拒否条件は失敗。条件付き更新を含む残りの項目が未実施のため、T-007実API試験全体の合否は未判定。原因調査や仕様変更は別担当の判断へ戻す。
