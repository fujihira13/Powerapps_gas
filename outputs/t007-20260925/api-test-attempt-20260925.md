# T-007 API試験の接続確認記録

日付: 2026-09-25 (JST)
対象環境: Developer `c1719a14-6cac-eb5b-b598-2254af1c64b7`
対象表: `cr6cb_evidencecase`

## 実行した確認

1. `pac auth list` は終了コード0。有効プロファイル `Codex-Dev-20260925`、環境URL `https://org3d6ad684.crm7.dynamics.com/` を表示した。アカウント識別子は証拠に含めない。`docs/TASKS.md`の同名プロファイル作成記録は、指定環境IDでのプロファイル作成を記録している。
2. `pac org who --environment c1719a14-6cac-eb5b-b598-2254af1c64b7` は `Connected as [redacted]` の後に対象環境情報を返さず、30秒を超えて停止した。Ctrl+Cで中断した。終了状態・環境情報は取得できず。
3. 実験行の事前GETに先立ち、表のEntitySetName特定用の読取り専用メタデータ要求をDataverse CLIで起動した。

```powershell
node 'C:\Users\misum\AppData\Local\npm-cache\_npx\a64cee6843b5ff58\node_modules\@microsoft\dataverse\bin\dataverse.js' api request --target dataverse --environment 'https://org3d6ad684.crm7.dynamics.com/' --path "/api/data/v9.2/EntityDefinitions(LogicalName='cr6cb_evidencecase')?`$select=EntitySetName,LogicalName,PrimaryIdAttribute" --include
```

コマンドは30秒超応答がなく、HTTP状態・本文を受け取れなかったためCtrl+Cで中断（終了コード1）。HTTP要求がサーバーに到達したかは確認できない。

## 結果と停止点

- 認証プロファイルの一覧は取得できたが、指定環境へのAPI応答は確立できなかった。接続不能、応答遅延、認証問題のいずれかは未判定。
- 実験ラベルが既存でないことを確かめる事前GETは**未実施**。作成要求8件、読戻し、条件付き更新は**未実施**。
- HTTP状態・行ID・作成行数: 取得なし。Dataverseへの変更を確認できる結果はない。
- 条件を満たせないため、ここで停止した。再認証、UI操作、別経路、再試行は行っていない。
