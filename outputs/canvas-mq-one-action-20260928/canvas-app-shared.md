# Canvas App Shared Plan — MQ 2ファイル受付

Mode: EDIT
Working directory: `C:\dev\Powerapps_gas\outputs\canvas-mq-one-action-20260928\`
承認済み計画: `C:\dev\Powerapps_gas\docs\plans\mq-two-files-one-action-20260928.md`

## Shared invariants

- 既存の4画面・親テーブル `架空ログ証跡件`・主キー `cr6cb_evidencecaseid` を維持する。新しい1件は常に新しい親GUIDで作り、既存件を上書き・移行しない。
- 確認済みの新規データソース名は `'件別ファイル'`。子主キーは `cr6cb_evidencefileid`。親Lookup `cr6cb_evidencecase` は `架空ログ証跡件.cr6cb_evidencecaseid` を参照し、role `cr6cb_filerole` は必須String (`log` / `excel`)、filename `cr6cb_filename` は必須String (255文字)、添付列は標準 `{Attachments}`。子表の一意キー `cr6cb_case_filerole` はStudioでアクティブ確認済み。新しい添付は親GUID＋roleで検索し、各roleがちょうど1行でなければ未完了として扱う。
- 新方式では子行のroleとファイル名を元ファイルの識別元とする。親の `{Attachments}`、`cr6cb_batchfilename`、旧親Notesは旧件履歴のために保ち、新方式の分類に使わない。
- Screen1の通常導線は「照合を開始」1回。内部は親→ログ子→Excel子→各行と添付の読み戻し→親を開始受付状態へ更新・再読込→既存フローを親GUIDで1回呼出。フォーム送信は非同期であり、後続段階は各 `OnSuccess` からのみ進む。失敗・不明結果でフローを呼ばず、自動削除・同じ保存の再送・再開始をしない。
- 重複は親ログ名、子 `cr6cb_filename`、旧親Notesの `filename` から検索し、親GUIDで候補を重複排除する。過去の受付日時はJSTに変換し、全一致候補の完全GUID・ファイル名・roleを出す。ファイル名注意であり内容一致ではない。検索失敗、委任制限、部分読取、親特定不能は「一致なし」にせず保存停止。
- 受付日時は親 `createdon` を使用し、Screen1/2/3でJSTの同じ書式と完全な親GUIDを表示する。日時の式は既存Screen2/3の `DateAdd(DateAdd(createdon, TimeZoneOffset(createdon), TimeUnit.Minutes), 9, TimeUnit.Hours)` 変換を踏襲し、StudioプレビューでJSTを確認する。
- 旧ログのみ親件は一覧・元添付・記録を閲覧できるが、子行を作らず、MQ照合済みに見せず、再実行しない。
- 担当者の転記照合・結果判断・コメント・レビュー依頼、Screen4のレビュアー確認/差し戻しは既存親GUIDに対して保つ。書込後は同じGUIDを読戻して証拠表示する。
- `App.pa.yaml` の `OnStart`（`varDemoRole`）と `StartScreen` の既存ルーティング、画面順 `Screen1, Screen2, Screen3, Screen4` は変更しない。App共通差分はNone。

## Data / state contracts

| Data | Stable identity | Required readback |
|---|---|---|
| 親件 | `cr6cb_evidencecaseid` | `createdon`, log名, environment, server, target date, processing/review states |
| ログファイル子行 | `cr6cb_evidencefileid`; guard: 親Lookup＋role=`log` | ちょうど1行、親GUID、role、`cr6cb_filename`, その行のNotes添付1件のファイル名 |
| Excelファイル子行 | `cr6cb_evidencefileid`; guard: 親Lookup＋role=`excel` | ちょうど1行、親GUID、role、`cr6cb_filename`, その行のNotes添付1件のファイル名 |
| MQ照合結果 | 親GUID | 期待数、記録数、欠落数、欠落ID、予定外ID、終端状態、入力/結果ブック読戻し状態、結果URL |
| 担当者/レビュー | 親GUID | 書込後の同GUID行にある各判断・コメント・状態 |

作成・更新は `cr6cb_evidencefileid`、role件数の検証は親GUID＋roleの有効な一意キーで行う。重複検索で曖昧/失敗なら続行しない。

## Result display rules

- Screen2は親件を `createdon` 降順で表示し、受付日時(JST)、完全GUID、環境/サーバー/対象日、親状態、レビュー状態を表示する。
- 新方式のMQ表示条件は、親GUIDに一致する子行が各roleちょうど1件あり、roleと添付の読戻しが一致すること。子行なしの旧件・片側だけの部分保存・重複roleはMQ値を空欄/要確認として表示する。
- Screen3は添付元をroleで示す。`cr6cb_mqresulttext` の正常ID行を全列挙しない。欠落IDは「ログに記録されていないID」、予定外IDは「一覧にないIDがログにあります」と区別する。
- 「予定したIDはすべてログに記録されています」は差異0、終端行あり、入力・結果ブックと結果レコードの必要な読戻し全件一致の時だけ。終端なしでは「ログが最後まで出力されたことを確認できません」。これらの表示はサーバー反映成功を断定しない。
- 結果ExcelリンクはURL・ブック読戻しが確認できた時だけ有効。Screen4のレビュー状態表示も同じ親GUIDの読戻し値。

## Visual and interaction rules

- 既存の白/淡い青灰背景、濃紺の見出し、Segoe UI、4画面の情報階層とボタンスタイルを継続する。
- Screen1は2つの役割欄を明確に別表示。短い項目は同じ列に詰め込まず、モバイル幅では縦積み・スクロールを優先する。状態・次に必要な操作・エラー理由を見える位置に置く。
- Screen2/3の日時とGUIDは表示ラベルを付けて省略せず、狭い幅でも折返し可能にする。識別アイコンだけでは代替しない。
- 添付欄はフォーム内の標準Attachmentsコントロールを使う。親レコード外へ直接置かず、`Items` へ任意コレクションを割り当てない。実際のフォーム/カード/コントロールのプロパティはStudioで該当型を確認し、未知の列・プロパティを推測しない。

## Test seed and boundaries

ローカル式検証専用: 親 `P-OK=11111111-1111-4111-8111-111111111111`、旧件 `P-OLD=44444444-4444-4444-8444-444444444444`、ログ子 `CH-LOG=22222222-2222-4222-8222-222222222222`、Excel子 `CH-EXCEL=33333333-3333-4333-8333-333333333333`。架空ファイル名 `mq-id-5-items-runless.txt` / `mq-id-5-items-20260928.xlsx`。これらはmock値であり、Dataverseへ書き込まない。

クラウド側のスキーマ確認・保存・テスト記録作成はこのローカル計画の作成とは別操作であり、ここでは実施しない。許可済みの最小範囲を超える環境・レコード数・添付数・Excel数へ広げない。
