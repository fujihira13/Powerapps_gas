# Screen1 受付・対象確認 — Screen Brief

Action: Modify
Screen: Screen1 受付・対象確認
Target File: `C:\dev\Powerapps_gas\outputs\canvas-mq-one-action-20260928\Screen1.pa.yaml`
YAML screen key: `Screen1`
Control name prefix: `s01One`
Shared plan: `C:\dev\Powerapps_gas\outputs\canvas-mq-one-action-20260928\canvas-app-shared.md`

## Required Actions

### ACT-01 — 環境・サーバー・日付と2ファイルを選ぶ

- **Precondition / entry point:** 新規受付で未保存の状態。対象処理日は `Today()` を初期値とする編集可能な日付。既存候補値から環境・サーバーを選択。
- **Source / stable identity:** 親 `架空ログ証跡件` の新規フォームと、子データソース `'件別ファイル'` に対するログ・Excelの標準Attachmentフォームを分離。ログ `.txt` 1件とExcel `.xlsx` 1冊を必須とする。実行回入力は置かない。
- **Transition / write set:** この段階ではDataverse書込なし。拡張子・添付数・必須選択・二重押下を検証し、形式不一致ならCTAを無効化/停止。
- **Postcondition observer / proof:** CTA有効時、同一画面に環境/サーバー/日付・ログ名・Excel名の選択状態が表示される。
- **Visible evidence:** 「サーバーログ（txt）」と「更新対象一覧（Excel）」の別欄、日付、環境、サーバー、「照合を開始」ボタン。

### ACT-02 — 同名候補を確認し明示続行する

- **Precondition / entry point:** ACT-01が有効で「照合を開始」を押す。
- **Source / stable identity:** 親の `cr6cb_caselabel`、新方式の `'件別ファイル'.cr6cb_filename`、旧方式のNotes filename。候補は親GUIDで重複排除。
- **Transition / write set:** 読取のみ。該当候補がある時は新規保存を止め、全候補を表示して利用者の「続けて新しい件を作成」か「戻って見直す」を求める。照会/委任/完全性確認の失敗は一致なしとみなさず保存停止。明示続行後だけ同じ入力で保存チェーンへ進む。
- **Postcondition observer / proof:** 候補ごとに一致ファイル名、役割、過去受付日時(JST)、完全な親GUIDを表示。空候補も検索完了を確認してから続行。
- **Visible evidence:** ファイル名による注意喚起でありファイル内容一致ではないと説明。複数候補は全件表示。継続/取消の別ボタン。

### ACT-03〜06 — 親・role別子行を保存し全件読戻す

- **Precondition / entry point:** ACT-02で一致なし、または警告候補を表示後に明示続行。処理中/結果不明/保存不明の再送ではない。
- **Source / stable identity:** 既存親表 `架空ログ証跡件`、親GUID `cr6cb_evidencecaseid`。子表 `'件別ファイル'`、親Lookup `cr6cb_evidencecase`、role `cr6cb_filerole` (`log`/`excel`)、filename `cr6cb_filename`、添付 `{Attachments}`、一意キー `cr6cb_case_filerole`。
- **Transition / write set:** 単一CTA内で親新規作成→親GUID読戻し→log child form SubmitForm/OnSuccess→excel child form SubmitForm/OnSuccess→親・各role子行・各添付/Notes読戻し→一致時に開始前状態を設定。各フォームは独立した標準Attachments欄を使い、同じ添付コレクションを共有しない。各段階は前段成功イベントの後だけ開始する。
- **Postcondition observer / proof:** 親のGUID/createdon/環境/サーバー/日付/ログ名を読戻す。子行は親GUID＋roleで各ちょうど1行、role・`cr6cb_filename`・Notesの添付件数/filenameが選択値と一致。親子どちらかの保存・読戻しが不確かなら親の状態を既存`停止`/`結果不明`に保全しflowを呼ばない。
- **Visible evidence:** 「保存を確認しています」を経て、完全な親GUIDと受付日時(JST)、両ファイル名、環境/サーバー/日付を読戻した後だけ保存確認表示。

### ACT-07 — 既存フローを親GUIDで一度だけ開始する

- **Precondition / entry point:** ACT-03〜06の全読戻し成功、重複確認済み、処理中フラグなし。
- **Source / stable identity:** 親GUID `cr6cb_evidencecaseid`、既存フロー `架空ログ証跡_件別Excel転記` のcaseId入力。
- **Transition / write set:** 親状態を既存`開始受付済み`に更新し、同GUIDで再読込できた時だけ既存フローを一度呼ぶ。flow `Run`をBoolean結果として判定しない。呼出結果不明時に再呼出しない。
- **Postcondition observer / proof:** 同GUIDの親状態をRefresh/LookUpし、Screen2へ渡す。フロー実行結果が不確かなら`結果不明`を保ち再開始を無効化。
- **Visible evidence:** 「照合を開始しています」からScreen2へ進み、同じ受付日時・GUID・ファイル名を一覧で確認。保存/開始多重押下を無効化。

## Functional Test Scenarios

| ID | Given | When | Then: source postcondition | Evidence |
|---|---|---|---|---|
| S1-T01 | 新規フォーム、対象日は今日、環境/サーバー候補あり | .txt 1件と.xlsx 1冊を選択 | 2欄が独立しCTA有効、Dataverse書込はまだ0件 | Screen1入力確認 |
| S1-T02 | 片側未選択、拡張子不一致、または同役割複数 | CTAを押す | 親/子/flowは0、開始しない | 入力エラーと無効CTA |
| S1-T03 | 過去親名/子名/旧Notes名が一致し、日時/GUIDが読める | CTAを押す | 保存0件。全候補を警告表示し、明示続行後のみ新GUIDで開始処理へ進む | JST・完全GUID・role・filename |
| S1-T04 | 重複検索が失敗/不完全/委任上限 | 有効入力でCTAを押す | 親/子/flowは0、同名なし扱いにしない | 読取失敗理由 |
| S1-T05 | 重複なしで親作成成功、log child作成失敗/結果不明 | CTAを一度実行 | 親は残り、Excel子とflowは作らない。親は停止/結果不明、再送不可 | 親GUIDと失敗段階 |
| S1-T06 | 親とlog child成功、Excel child失敗/添付読戻し不一致 | CTAを一度実行 | 既存行保持、flowは0、成功表示なし | 親GUID、該当role/name/count |
| S1-T07 | 親・両子・Notes添付の読戻し完全一致 | 「照合を開始」を一度押す | 親GUID配下に各role1行/各添付1件、開始受付後flow呼出1回 | 受付日時・完全GUID・両file名のreceipt、Screen2行 |
| S1-T08 | 送信中/flow呼出中または応答不明 | CTAを連打/再起動 | 追加親/子・flow再呼出しなし | ロック中表示/結果不明 |

## Implementation Notes

- 既存の環境/サーバー/日付の選択と4画面ナビの見た目を保つ。既存の1つの親Attachments欄、保存ボタン、別処理開始ボタン、ログのみの新規分岐を新規受付UIから外す。
- 既存のフォーム・カード・Attachmentsのサポートされたプロパティだけを使う。子Attachment欄は子テーブル標準フォーム内に置き、非標準Itemsコレクションは使わない。
- App共通差分なし。Screen2/3との式やコントロール名が重ならないよう `s01One` prefixを使う。
