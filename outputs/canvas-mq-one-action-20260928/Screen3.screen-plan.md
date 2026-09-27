# Screen3 件ごとの確認 — Screen Brief

Action: Modify
Screen: Screen3 件ごとの確認
Target File: `C:\dev\Powerapps_gas\outputs\canvas-mq-one-action-20260928\Screen3.pa.yaml`
YAML screen key: `Screen3`
Control name prefix: `s03One`
Shared plan: `C:\dev\Powerapps_gas\outputs\canvas-mq-one-action-20260928\canvas-app-shared.md`

## Required Actions

### ACT-09 — 元ファイル・MQ差異・処理結果を確認する

- **Precondition / entry point:** Screen2の対象親行から遷移。`varEvidenceCase`に選択した親行を保持。
- **Source / stable identity:** 親 `cr6cb_evidencecaseid` から `'件別ファイル'` を親Lookup＋role (`log`/`excel`) で読む。旧親Notesは閲覧のみ。MQ状態・差異は同GUIDの親 `cr6cb_mq*` fields、結果リンクは読戻し済みURL。
- **Transition / write set:** 読取専用。正常IDを全列挙せず、欠落IDと予定外IDのみを別表示。新方式に必須の2子行がない/複数/不一致ならMQ比較を完了扱いしない。終端なしなら一致文を出さない。結果URLは読戻し成功後のみ開く。
- **Postcondition observer / proof:** Refresh後に同じ親GUIDと2つのrole別子行/添付が一致し、親結果値の予定数・記録数・欠落数・欠落ID・予定外ID・終端・結果URLを読み取る。
- **Visible evidence:** 件名、受付日時(JST)、完全GUID、環境/サーバー/対象日、role別ファイル名、差異IDのみ、読戻し/終端状態。欠落は「ログに記録されていないID」、予定外は「一覧にないIDがログにあります」。差異0＋終端あり＋全読戻し一致時だけ「予定したIDはすべてログに記録されています」。終端なしは「ログが最後まで出力されたことを確認できません」。サーバー反映成功とは表示しない。

### ACT-10 — 担当者の照合結果を記録する

- **Precondition / entry point:** `varDemoRole="担当者役"`、既存の転記完了かつ `cr6cb_excelcheckstatus="全文一致"`、有効な転記照合と判断が選択済み。異常/保留時はコメント必須。
- **Source / stable identity:** 親 `cr6cb_evidencecaseid`。
- **Transition / write set:** 既存の3列 `cr6cb_transfercheck`, `cr6cb_outcomejudgment`, `cr6cb_reviewcomment` だけを同じ親GUIDへPatchする。
- **Postcondition observer / proof:** 同GUIDでRefresh/LookUpし、3値を読み戻す。読戻し不成立なら保存成功を表示しない。
- **Visible evidence:** 照合・判断・コメントが現在値として表示され、保存失敗/不明は未確認のまま理由を示す。

### ACT-11 — レビューを依頼/再依頼する

- **Precondition / entry point:** 担当者役、転記済み/全文一致、3つの担当者記録が読み戻し済み、未依頼または差し戻し。
- **Source / stable identity:** 親GUID。
- **Transition / write set:** `cr6cb_reviewstatus`を既存語彙の`依頼中`または`再依頼`へ更新する。
- **Postcondition observer / proof:** 同じ親GUIDで状態を再読込し、Screen2とScreen3で一致させる。
- **Visible evidence:** 読戻し成功後のみ依頼済み表示またはScreen2へ遷移。差し戻し理由など他の欄は消さない。

## Functional Test Scenarios

| ID | Given | When | Then: source postcondition | Evidence |
|---|---|---|---|---|
| S3-T01 | `P-OK`の子行がlog/excel各1件。expected=5, logged=5, missing=0, unexpected=0、終端あり、入力/結果ブックとURL読戻し一致 | `P-OK`を開く | 全成功ID行は表示しない。一致文を出す。URL有効 | Screen3の結果・link |
| S3-T02 | `P-OK`で欠落`MQ-0003`・予定外`MQ-9001`、終端あり | `P-OK`を開く | 2差異を別ラベルで表示し、サーバー反映失敗とは断定しない | 例外だけのGallery |
| S3-T03 | 差異0でも終端なし、または子行/ブック/URL読戻し不完全 | `P-OK`を開く | 一致文/linkを抑止し要確認状態を表示 | 終端/不足の警告 |
| S3-T04 | `P-OLD`は旧親Notesだけで子行なし | `P-OLD`を開く | 旧ログ閲覧は可能、MQ照合済みと見せず、再実行なし | 元ログ欄と旧件identity |
| S3-T05 | 完了・全文一致の親、担当者役、異常判断でコメント済み | 確認を記録 | 同じ親GUIDで3列をPatchして再読戻し。成功表示は読戻し値と一致 | 担当者各値と確認状態 |
| S3-T06 | S3-T05の3記録読戻し済み、reviewstatus未依頼または差し戻し | レビュー依頼/再依頼 | 同GUIDのstatusが依頼中/再依頼へ変化し、Screen2と一致 | Screen3/2のreview status |

## Implementation Notes

- 既存 `varEvidenceCase`, `frmCaseSourceLog`, `galCaseMqResults`, 担当者ラジオ/コメント/記録/レビュー依頼、一覧戻りを維持し、添付表示とMQ表示式を新データソースに対応させる。
- `varEvidenceCase.Attachments`で新規MQ件を判定しない。旧件についてのみ親Notes添付を表示する。
- Screen4のreviewer actionsはここでは編集しない。完全なGUIDと受付日時(JST)は詳細ヘッダーに残す。
