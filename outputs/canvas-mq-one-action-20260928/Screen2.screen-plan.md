# Screen2 進捗一覧 — Screen Brief

Action: Modify
Screen: Screen2 進捗一覧
Target File: `C:\dev\Powerapps_gas\outputs\canvas-mq-one-action-20260928\Screen2.pa.yaml`
YAML screen key: `Screen2`
Control name prefix: `s02One`
Shared plan: `C:\dev\Powerapps_gas\outputs\canvas-mq-one-action-20260928\canvas-app-shared.md`

## Required Actions

### ACT-08 — 件の進捗を読み、同じ件へ移動する

- **Precondition / entry point:** Screen2へ通常遷移。各親行の「ログと結果を見る」、条件を満たす「レビューを確認」、上部の「新しい受付」から到達。
- **Source / stable identity:** `架空ログ証跡件` を `modifiedon` 降順で読み、親 `cr6cb_evidencecaseid` を各行の安定識別子とする。受付日時は `createdon` をJSTで表示する。
- **Transition / write set:** 読取専用。MQ状態は `'件別ファイル'` を親Lookup＋`cr6cb_filerole`で照会し、`log`と`excel`が各ちょうど1行である時だけ新方式として表示する。旧ログのみ、片側欠落、重複role、照会失敗はMQ件数を成功扱いしない。行の詳細は `Set(varEvidenceCase, ThisItem); Navigate(Screen3, ...)`、レビューは既存役割導線、受付はScreen1へ。
- **Postcondition observer / proof:** 親GUIDを持つ同一行で受付日時(JST)、完全GUID、ログ名、環境、サーバー、対象日、保存/処理/Excel反映/担当者/レビュー状態が表示される。新方式のMQ表示は親GUIDの両role子行の数・role・filenameを読んだ結果のみ。
- **Visible evidence:** `createdon`と完全GUIDを含むカード。新方式だけ予定/記録/欠落件数・終端を表示。旧件はMQ集計なし。保存済み件の再開始・Screen1へ戻る開始ボタンを外し、同じ件の再実行導線を設けない。

## Functional Test Scenarios

| ID | Given | When | Then: source postcondition | Evidence |
|---|---|---|---|---|
| S2-T01 | `P-OK`にはlog/excel子行が各1件、読戻し一致 | Screen2を開く | 親行と新方式MQサマリーだけ表示。日時JST・完全GUIDが同じ`P-OK` | `galS02Cases`行 |
| S2-T02 | `P-OLD`は親Notesに旧ログだけで子行なし | Screen2を開く | 親履歴は表示、MQサマリーなし、再実行ボタンなし | `P-OLD`行 |
| S2-T03 | 親に子行が欠落、role重複、または読取エラー | 一覧を再表示 | MQ一致/完了を出さず要確認または空欄。別roleや旧添付へ推測でフォールバックしない | 該当行 |
| S2-T04 | 有効な親`P-OK`が一覧表示 | 詳細・レビュー・新規受付をそれぞれ選択 | 詳細=Screen3へ同じ親GUID、レビュー=既存適格条件の時Screen4へ、新規=Screen1へ。親レコードは変更なし | 遷移先の件ID |

## Implementation Notes

- 既存 `galS02Cases`, identity/status/MQ labels, open/review/new-intake controlsを対象にする。独自の新しいデータモデルや状態語彙は導入しない。
- 既存 `btnS02Resume` /「処理開始へ戻る」の再開始経路を削除または非表示にし、同一ケースの開始操作を再提供しない。
- `ThisItem.Attachments`で新方式のMQ判定をしない。role別子表は親GUIDとroleで読む。
- 4画面ナビ、既存レビュー条件、既存の他フィールド表示は維持する。Screen4はこのbriefの編集対象外。
