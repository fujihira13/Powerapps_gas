# Canvas App Complex Edit Plan — MQ照合を2ファイル受付・1操作化

Mode: EDIT
Working directory: `C:\dev\Powerapps_gas\outputs\canvas-mq-one-action-20260928\`
対象承認計画: `C:\dev\Powerapps_gas\docs\plans\mq-two-files-one-action-20260928.md`
これはユーザー承認済み実装計画のCanvas作業分解です。計画で対象化したDeveloper環境・非公開アプリ・既存フロー・架空データの範囲で実装を進めます。一般公開・購入・実務データ利用は含まず、クラウド操作は承認計画に書かれた件数上限と直前の対象確認に従います。

## Requirement Coverage

| 要件・承認事項 | 現行の根拠と不足 | 変更後の見える操作・表示 | 完成の証拠 |
| --- | --- | --- | --- |
| REQ-01 / C08: 新規受付 | Screen1は親件の1つのAttachments集合に.txtと.xlsxを入れ、「保存」と「処理開始」を別々に行う | Excelとログを別々の役割別欄で選択し、通常は「照合を開始」1回で親・子行・添付の保存読戻し後にフローを1回開始 | 同じ親GUID配下にExcel役割とログ役割の子行が各1件あり、各添付名・数・役割を読み戻す。開始前に読み戻し不一致なし |
| REQ-01 / REQ-02 / C09 / C10: 操作中・復元 | 現行Screen1は保存と開始が別。保存後の開始途中やアプリ再起動の部分受付は新方式未定義 | 入力・重複確認・保存・読戻し・開始の状態を明示。部分作成・結果不明では開始も同じ操作の再送も禁止し、進捗一覧で確認 | 保存/開始の多重押下、各段階失敗、再起動後の停止状態を安定GUIDで確認 |
| REQ-02 / C01: 進捗一覧 | Screen2は親件と1つの親Attachmentsを前提にMQ有無を判定する | 受付日時(JST)・完全な件GUID・環境・サーバー・対象処理日・各処理状態を維持し、子行が揃った新方式の差異件数を示す。旧ログのみ件にはMQ集計を出さない | 新方式・旧履歴・部分失敗の行が同じ親件一覧で誤認なく区別される |
| REQ-03 / REQ-04 / C03 / C12: 件別内容確認 | Screen3は親Attachmentsから元ログとExcelを探し、`cr6cb_mqresulttext`の全行を表示する | 新方式は役割別子行から元ログと入力ブックを参照。MQ結果は欠落・予定外IDのみ表示し、終端・読戻し条件を満たす時だけ所定の一致文を出す | 元2ファイル・親GUID・両結果シートの読戻し状態が一件に結び付く。正常ID行は画面に出ない |
| REQ-05 / C05 / C06: 担当者確認・レビュー | Screen3の担当者記録、依頼、Screen4のレビュアー確認・差し戻しは既存経路 | 既存の入力選択肢、コメント条件、依頼・再依頼、確認済み・差し戻しの動作を維持 | 同一件GUIDに対する担当者記録・依頼・確認/差し戻しと一覧表示の一致 |
| REQ-06: 失敗・結果不明 | 既存画面は件別失敗を示す。新方式では親・子の部分作成が加わる | どの段階の失敗・不一致・読取不能でもフローを開始しない。部分行を自動削除せず、成功や再送可能と誤表示しない | 親・子・Notesの作成と読戻しを各段階で失敗させ、親GUIDと理由を進捗に残す |
| REQ-07 / C11 / C13 / C14: MQ照合と結果Excel | 現行フローは親件GUIDから親Notes添付を読む。結果画面は全IDを表示 | 新方式の親GUIDから子役割を名前で検索し、役割別Notesを1件ずつ検証して既存ID比較・結果Excel作成へ渡す。元ブックは変更しない | 正しい2役割、件別比較、`証跡`/`MQ_Comparison`両シート、件GUID、`ReceivedAtJst`、URLを読戻して状態と一致 |
| A1: 独立した2欄 | 現行のAttachmentsは単一集合で役割別欄ではない | 子テーブル上の独立したExcelフォームとログフォーム。新規受付は.xlsx 1冊と.txt 1件を必須とする | 片側に選んだファイルが他方の欄へ混在せず、各欄の形式・件数が別々に検査される |
| A2: 1回の開始操作 | 現行は「保存」「処理開始」の2操作 | 保存、2子行作成、添付読戻し、親状態更新、フロー起動を一つの通常操作に直列接続。重複確認だけは明示続行を追加 | 一連の成功でフロー1回。不足・失敗・不明ではフロー0回 |
| A3: 同名注意 | 現行の同名確認は親行・親添付に依存 | 新旧どちらの保存方式もファイル名を検索し、過去件の受付日時・GUIDと照合種別を表示。内容同一とは言わない | 一致候補を全て表示し、検索失敗・上限・曖昧な関連付けでは保存停止 |
| A4: 差異のみの表示 | 現行Screen3は全行を見せる | 正常ID行を隠し、欠落・予定外IDだけを表示。終端表示なしは差異0件でも未完了の文言を出す | 成功表示・失敗表示・リンク有効化の条件分岐を確認 |
| A5: 既存履歴・レビュー保持 | 既存は親Notes添付、既存結果Excel、Screen4レビューを使用 | 既存行・Notes・結果Excelを変更せず、旧ログのみ件は履歴閲覧用とする。Screen4は変更しない | 旧件を再実行せずに閲覧し、既存レビュー経路を1件で回帰確認 |

## Current App State

同期済みの6 YAMLは `App.pa.yaml`、`Screen1.pa.yaml`～`Screen4.pa.yaml`、`_EditorState.pa.yaml`。既存画面は4画面で、Studio順序はScreen1→Screen2→Screen3→Screen4。

- `App.pa.yaml`: `varDemoRole` を担当者役に初期化し、処理中・停止・結果不明・依頼中の親件があればScreen2、なければScreen1を開始画面とする。
- Screen1: 親件`Form1`、1つの標準Attachmentsコントロール、環境・サーバー・対象日、保存ボタン、別の処理開始ボタン、同名確認がある。日時DataCardのDefaultは新規時Today()を返すが、DatePickerの`DefaultDate`は同期YAMLに明示されていない。新計画で当日初期値を再確認する。
- Screen2: 親件を更新日時順に表示。親Attachments内の.xlsx有無でMQ集計を出す。保存済み件からScreen1へ戻す「開始再開」導線がある。
- Screen3: 親Attachmentsから元ファイルを参照し、MQ結果文字列を全行表示。担当者照合・判断・コメント、確認記録、レビュー依頼を行う。
- Screen4: 同一件のレビュアー役切替、確認済みまたは理由付き差し戻しを記録する。今回変更しない。
- 既存パレットはScreen1の白背景・青い操作色、Screen2～4の淡い青灰背景とSegoe UI系を維持する。新しいテーマ、未承認の見出し、画面は追加しない。

## Screens to Modify

| Action | Screen | File | Summary |
| --- | --- | --- | --- |
| Modify | Screen1 受付・対象確認 | `Screen1.pa.yaml` | 親フォームと役割別の独立した子フォーム2つ、単一開始操作、重複確認、非同期保存連鎖、読み戻しゲート、フロー1回起動を実装 |
| Modify | Screen2 進捗一覧 | `Screen2.pa.yaml` | 子行に基づくMQ対象判定・差異件数、新方式の進捗、結果不明/部分受付の表示、別の開始再開操作を廃止 |
| Modify | Screen3 件ごとの確認 | `Screen3.pa.yaml` | 子行から2元ファイルを役割別表示し、MQの例外IDだけを表示。終端/読戻し条件、既存担当者確認・依頼を維持 |

## Screens to Add

None。4画面構成を保つ。Screen4、画面順序、レビュー役割は変更しない。

## App Changes

### Before builders

- `App.pa.yaml`の変更は**None**。既存の`OnStart`と`StartScreen`を保持する。部分受付・保存不明の親件には、既存StartScreenがScreen2へ振り分ける`停止`または`結果不明`を用いる。新しい未確認状態文字列を導入してScreen1へ取り残さない。
- Studio接続済みCanvasデータソースは `'件別ファイル'`。確認済み列は親Lookup `cr6cb_evidencecase`、role `cr6cb_filerole`（`log` / `excel`）、filename `cr6cb_filename`、標準添付 `{Attachments}`。親Lookup＋roleの一意キー `cr6cb_case_filerole` はアクティブ確認済み。画面式はこれらの実名を使う。
- `cr6cb_evidencecase`の既存列・`cr6cb_batchfilename`・旧親Notes・過去値は削除/移行/一括更新しない。新方式の役割名は子行を正とし、親の既存ファイル名列を新方式のソースとして使わない。

### After builders

None。子データソースはStudioに接続済み。App起動処理や画面順序は変更しない。部分保存は既存の`停止`/`結果不明`で扱い、新しい状態語彙を導入しない。

## Functional Changes

| Capability | Existing behavior | Required transition | Visible success |
| --- | --- | --- | --- |
| 2ファイルの役割別受付 | 親件の1つのAttachments集合にログ・ブックを混在 | 各ファイルを子行に独立保存。親GUID＋役割名で1行ずつ | 画面上でExcel名とログ名が別欄・別役割で表示され、親件IDと対応 |
| 通常の照合開始 | 親保存と処理開始を別操作 | 1ボタン→親作成→ログ子作成→Excel子作成→親/子/Notes読戻し→親を開始受付済みに更新→既存フローへ親GUIDを1回渡す | 進捗画面で同じGUID・受付日時・開始状態を確認。フロー実行の戻り値はBoolean扱いしない |
| 重複ファイル名 | 既存ファイル名検索が保存方式に依存 | 親ログ名、過去の子ファイル名、新方式以前の親Notes filenameを検索。該当親をGUIDで重複排除 | 全候補のファイル名・役割・受付日時(JST)・完全な親GUIDを警告表示し、明示続行後のみ新しい親GUIDを作成 |
| MQ内容判定の表示 | 全ID行を画面に表示 | 入力・結果Excelの読戻し後、欠落・予定外IDの行だけ抽出 | 適切な差異名と終端表示条件が画面に示され、実サーバー反映を断定しない |
| 担当者・レビュアー記録 | 既存4画面の記録操作 | 操作条件・各列・役割切替を維持 | 同一親GUIDの担当者結果、依頼状態、レビュアー結果が各画面で一致 |

## Action Contracts

以下の契約はStudioで確認済みの `'件別ファイル'` スキーマに基づく。添付のNotes読戻しは各子レコードに関連付いたfilenameを確認する。

| ID / action | Precondition & entry point | Source / stable identity | Exact transition and write set | Postcondition observer & proof set | Visible evidence |
| --- | --- | --- | --- | --- | --- |
| ACT-01 入力を選び開始条件を整える | Screen1新規受付。環境・サーバー候補から選択し、今日を初期値とする編集可能日を確認。1つのExcel欄に.xlsxを1冊、別のログ欄に.txtを1件 | Screen1の親フォーム値と2つの別子フォームの添付欄。未作成データはまだ書かない | UI選択のみ。実行回入力を設けない。片側欠落、重複添付、拡張子違い、候補外の環境/サーバーならCTA無効または開始イベントでブロック | 各欄のファイル名・拡張子・件数が1/1。環境/サーバー/日付を開始前に同画面で確認 | 2つの役割ラベル、各ファイル名、環境、サーバー、日付、開始操作の有効/無効状態 |
| ACT-02 同名照合と続行確認 | ACT-01が有効で通常CTAを押す | 親ケース表、子ケース表、旧方式Notesのfilename/親関連。親GUIDで候補を重複排除 | 読取のみ。名前だけの一致は内容一致と断定しない。照会失敗/部分読取/結果上限/親GUID特定不能なら保存・フローを止める。候補がある場合だけ確認後の続行を求める | 警告集合の全候補が名前・役割・createdon・親GUIDを持つ。空候補なら照会完了を示す | 過去受付日時(JST)、完全な件GUID、ファイル名と役割、名前による注意喚起であること、続行/修正の明確な選択 |
| ACT-03 親件を作成 | 重複なし、または候補表示後に明示続行。多重押下・保存不明では不可 | `cr6cb_evidencecase`、生成された`cr6cb_evidencecaseid` GUID | 既存親行を更新せず、新GUIDで環境・サーバー・対象日・ケースラベルを作成し`保存済み`を初期値にする。部分失敗は既存の`停止`または`結果不明`に保全し、新規status語彙を追加しない | Fresh Lookup by parent GUIDでGUID、createdon、cr6cb_caselabel、環境、サーバー、対象日、状態を一致確認 | 受付日時、完全な件GUID、ログ/Excel両ファイル名、環境、サーバー、対象日を表示する読戻しレシート |
| ACT-04 ログ役割の子行・添付を保存 | ACT-03で親GUID読戻し済み。ログ欄は.txt 1件 | `'件別ファイル'`、親Lookup `cr6cb_evidencecase`＋一意role `cr6cb_filerole="log"` | 新規子行1件を作成し、親Lookup、role=`log`、`cr6cb_filename`、標準Attachmentsに.txt 1件を保存 | 親GUID＋roleで1行を読戻し、親GUID/role/filenameとその子行関連Notesのdocument/filename/添付数=1を確認 | ログrole、親GUID、.txt名、添付1件の読戻し値 |
| ACT-05 Excel役割の子行・添付を保存 | ACT-04のログ子行保存が完了し、Excel欄は.xlsx 1冊 | `'件別ファイル'`、同じ親GUID、role=`excel`（アクティブ一意キーで別行） | Excel役割の子行を独立作成。ログ子行の添付集合を共有/流用しない | 親GUID＋roleで1行を読戻し、親GUID/role/filenameとその子行関連Notesでdocument/filename/添付数=1を確認 | Excel role、親GUID、.xlsx名、添付1件の読戻し値 |
| ACT-06 親・子・添付全体を検証 | ACT-04/05完了。処理未開始 | 親GUID、`'件別ファイル'`のrole別2行、各関連Notes | 読取のみ。親値一致、子行が各roleちょうど1件、各Notesがちょうど1ファイル、filename/拡張子/role一致を確かめる。問題があれば親を停止/結果不明として記録しフロー呼び出しなし | 親・子・Notes各ソースを親GUID＋roleで再読込。proof setは親GUID/日時/環境/サーバー/日付、各role/filename/添付数 | すべて一致なら開始へ遷移。不一致/失敗では理由と親GUIDを示して進捗確認へ。自動削除・再送なし |
| ACT-07 開始受付と既存フロー1回呼出 | ACT-06全件合格、重複確認済み、CTA処理中フラグなし | 親件テーブル、親GUID。既存フロー `架空ログ証跡_件別Excel転記` のcaseId入力 | 親状態を`開始受付済み`へ更新・読戻し後に親GUIDを1回だけRunへ渡す。Runが応答値なしの場合に戻り値をBoolean判定しない。呼出後に親行をRefresh/LookUp | 安定親GUIDの状態読戻し。許可された開始状態を確認し、実行フラグを解除または結果不明に保持 | 「照合を開始しています」→進捗一覧。開始結果を読めなければ状態不明表示、再起動禁止 |
| ACT-08 進捗行を確認/詳細・レビューへ移動 | Screen2に親行が表示 | 親GUID | 読取のみ。対象行からScreen3、レビュー依頼済み行からScreen4へ遷移。新規受付ナビはScreen1へ | Screen2/3/4が同じ親GUIDとcreatedonを使う | 完全なGUID・日時(JST)・環境/サーバー/対象日・保存/処理/実反映/担当者/レビュー状態・該当MQ件数 |
| ACT-09 MQ例外を確認 | Screen2から新方式の対象親をScreen3に開く | 親GUID→子表のExcel/Log role→各Notes。比較結果は親GUIDに記録された`cr6cb_mq*` fields | 読取のみ。全成功IDは画面に列挙しない。差異0でも終端欠如・読戻し不完了なら成功文を出さない。出力Excel linkは両シートとID/件数を読戻した時のみ有効 | 親GUIDで比較状態・counts・terminal status・missing/extra result lines・`excelcheckstatus`・URLをFresh Lookup | 「予定したIDはすべてログに記録されています」は差異0＋終端あり＋必要な読戻し済みだけ。例外ID行だけ表示。終端なしは「ログが最後まで出力されたことを確認できません」 |
| ACT-10 担当者確認を記録 | 新規または既存完了件を開く。Excel実反映確認済み。担当者役 | 親GUID。既存`cr6cb_evidencecase` row | 既存write set: `cr6cb_transfercheck`、`cr6cb_outcomejudgment`、`cr6cb_reviewcomment`。異常/判断保留ではコメント必須。異なる欄の意味を統合しない | same GUID Fresh LookupをScreen3の変数に再設定。proof: 上記3つの値 | 読戻し成功時だけ「確認を記録」成功状態。失敗は保存済みと表示せず画面に留まる |
| ACT-11 レビュー依頼/再依頼 | Excel実反映を確認し、担当者照合・判断・必要コメントを保存済み。未依頼または差し戻し後の再依頼可能状態 | 親GUID | 既存`cr6cb_reviewstatus`を`依頼中`または`再依頼`へ更新 | Fresh Lookupで同一GUIDのreviewstatus確認。Screen2の依頼状態が同じ値を読む | Screen3の依頼ボタン状態とScreen2のレビュー状態が一致 |
| ACT-12 レビュー確認 | Screen4のレビュアー役で、依頼中の親を開き、確認を選択 | 親GUID | `cr6cb_reviewstatus="確認済み"`へ更新 | Fresh Lookup by GUID; Screen4とScreen2双方が同じ値を読む | 確認済みの状態と完全な件識別表示 |
| ACT-13 レビュー差し戻し | Screen4のレビュアー役で、依頼中の親を開き、理由を添えて差し戻し | 親GUID | `cr6cb_reviewstatus="差し戻し"`、`cr6cb_reviewreason`を保存 | Fresh Lookup by GUID; Screen4/Screen2がstatusと理由を読む | 差し戻し状態と理由。Screen3再依頼は担当者3項目のみ変更可能 |

## Functional Test Matrix

以下はまずローカル式追跡・静的検査で実施し、Studio/Dataverseの保存・フロー起動実演は承認済み計画の範囲と個別の実行前確認後に行う。Mock IDは実Dataverse GUIDとして送信しない。

固定mock値: `P-OK=11111111-1111-4111-8111-111111111111`、`CH-LOG=22222222-2222-4222-8222-222222222222`、`CH-EXCEL=33333333-3333-4333-8333-333333333333`、`P-OLD=44444444-4444-4444-8444-444444444444`。正常入力は `samples/mq-id/mq-id-5-items-runless.txt` と対応する5 IDの架空xlsx。環境A/サーバーA、対象処理日`2026-09-28`。旧件は履歴専用でフローを呼ばない。

| Test | Given | When | Then: source postcondition | Evidence surface / contract |
| --- | --- | --- | --- | --- |
| T01 2役割別選択 | 新規画面、Excel欄空、ログ欄空、P-OKなし | xlsxをExcel欄、txtをログ欄に選びA/A/2026-09-28を指定 | 各欄は独立し、開始前は親・子レコード0件。CTAは両方揃った時だけ有効 | Screen1で2役割/名前/環境/サーバー/日付。ACT-01 |
| T02 欠落・不正添付 | 片方の欄欠落、またはPDF/2つの.xlsx/2つの.txt | CTAを押す | 親0・子0、flow call 0 | Screen1に形式/数エラー。ACT-01, ACT-06 |
| T03 同名警告 | P-OLDの旧親Notesに`mq-id-5-items-20260928.xlsx`、別caseに同じlog filename、両方のGUID/createdonあり | 同名の2ファイルでCTA→明示続行 | 初回はparent/child/flow未作成。警告に両caseをGUIDごと1回表示。続行後はP-OKが新GUIDで作成 | 過去日時(JST)、親GUID、ファイル名/役割、内容同一とは断定しない表示。ACT-02, ACT-03 |
| T04 重複検索不能 | Notesまたは子表の読み取りが失敗/partial/limit reached | 有効な2ファイルでCTA | 親0・子0・flow0、operation remains blocked | 失敗/要確認理由。空結果と扱わない。ACT-02 |
| T05 親フォーム失敗 | T01入力、parent createが確定失敗 | 1 CTA | 親なし、子なし、flow0。再押下同一actionは禁止または失敗を確実に判定できる状態 | Screen1で保存失敗/結果不明、操作状態と進捗誘導。ACT-03 |
| T06 child log失敗 | 親P-OKが作成され、log child service fails | 同じaction chainを進める | P-OKは残る。child Excel未作成または未確定。親statusは停止/結果不明、flow0、削除/再送なし | Screen2にP-OKと理由、Screen1に子段階を表示。ACT-04/06 |
| T07 child Excel失敗 | 親P-OKとCH-LOG成功、Excel child creation fails | action chainを進める | 親とCH-LOGを保持。CH-EXCEL未作成または不明、flow0、追加重複送信なし | 親GUIDと不足役割、Excel名、状態。ACT-05/06 |
| T08 添付readback mismatch | Parent and both child rows exist, but Notes has zero/two files, wrong filename or wrong parent/role | child readback | parent must not enter `開始受付済み`; flow0; no successful receipt | mismatch role/name/count, P-OK and reason. ACT-06 |
| T09 valid one-button start | P-OK and CH-LOG/CH-EXCEL are absent, valid input; no duplicate; parent and child/notes readbacks match | Normal `照合を開始` once | Parent GUID stable, exactly one child per role, each one attachment; parent starts flow-ready then flow invoked exactly once with P-OK; no Run return Boolean branch | Screen2 receipt has receiptDate, full GUID, both filenames, env/server/date and current status. ACT-03..08 |
| T10 double press / unknown response | T09 is in parent/child submit or flow call; connector response can be lost | Press CTA twice or simulate lost response | At most one parent and one child per role; no second flow call while result unknown; no duplicate report as success | Locked control and Screen2 unknown status. ACT-03..07 |
| T11 count/role validation in flow | P-OK has duplicate child for one role, missing role, wrong role name, non-document note or wrong extension/content | Flow is called for test invocation only in local unit harness | Child branch stops before result workbook creation; parent status/failure reason records validation outcome | Flow outputs and no link in Screen3. ACT-07/09 |
| T12 normal five IDs | Valid child pair for P-OK; input expected5; log records all5 and terminal marker; both workbook sheets and parent values read back | Local flow test then Screen3 observes P-OK | expected=5/logged=5/missing=0/unexpected=0; terminal present; input/output readbacks match; link URL present only after all verification | Screen3 shows exact approved success sentence, no normal ID lines; Screen2 counts. ACT-09 |
| T13 missing plus unexpected | Expected `MQ-0001..MQ-0005`, log lacks `MQ-0003`, includes `MQ-9001`, terminal present | Open P-OK in Screen3 | comparison is attention-required, not reflected-failure claim; result workbook retains all details | Screen3 shows `MQ-0003` as log missing and `MQ-9001` as unexpected only; Screen2 counts. ACT-09 |
| T14 no terminal marker | Expected and logged IDs otherwise equal, but no `ALL SUCCESS` ending | Open result | No all-logged success sentence even with zero differences | Screen3 exact terminal-missing caution. ACT-09 |
| T15 incomplete readback | Comparison rows may look complete, but input workbook, one result sheet, case GUID/count or workbook URL readback is absent/mismatched | Open result | Success sentence suppressed; output link disabled; parent is attention-required | Screen3 error/result unknown status and no valid URL. ACT-09 |
| T16 old log-only history | P-OLD has only old parent Notes and no child pair/MQ output | Open P-OLD from Screen2 | Existing log/history visible; MQ summary absent; no flow/child migration; no re-run control | Screen2/Screen3 show ID/date and legacy file only. ACT-08/09 |
| T17担当者記録・依頼 | New P-OK has verified workbook reflection; demo role is担当者; comments obey rule | Select transfer match/judgment/comment and record; then request review | Existing 3 parent fields update by P-OK GUID; request status transitions only after record succeeds | Screen3 receipt and Screen2 status. ACT-10/11 |
| T18 reviewer confirm/return | P-OK review status is依頼中; reviewer switches role. Return test includes reason | Confirm in one seeded case; return with reason in another | Confirm case status is確認済み. Returned case status is差し戻し with reason. IDs remain stable | Screen4 and Screen2 read same state; Screen3 permits only required resubmission fields. ACT-12/13 |

## Approach

Preserve the existing four-screen shell, typography, color, status semantics, parent case GUID, result workbook contract, human confirmation and review. Replace only the intake's combined attachment relationship with role-specific child rows and update each consumer that currently infers MQ mode from parent Attachments. The one-action sequence is asynchronous: each `SubmitForm` must continue from its success event, not immediately after the call. No later stage may assume earlier submission succeeded from a button press or notification. Use a new parent GUID for every new case; existing parent and child rows are never repurposed.

The child datasource, lookup, role values, filename column, attachment field, and active parent+role key are confirmed. The remaining local implementation gate is Canvas compile plus UI readback proving both standard attachment forms preserve their selected files. If this fails, stop before any real-data test; do not revert to one collection. Cloud changes and fictional test rows are performed separately by the root owner under the approved scope.

## Dispatch

The rows below define file ownership and briefs; no builder tool is being invoked. No two rows share a target or control-name prefix.

| Action | Screen | Target File | YAML Key | Name Prefix | Screen Brief |
| --- | --- | --- | --- | --- | --- |
| Modify | Screen1 受付・対象確認 | `C:\dev\Powerapps_gas\outputs\canvas-mq-one-action-20260928\Screen1.pa.yaml` | Screen1 | s01One | `C:\dev\Powerapps_gas\outputs\canvas-mq-one-action-20260928\Screen1.screen-plan.md` |
| Modify | Screen2 進捗一覧 | `C:\dev\Powerapps_gas\outputs\canvas-mq-one-action-20260928\Screen2.pa.yaml` | Screen2 | s02One | `C:\dev\Powerapps_gas\outputs\canvas-mq-one-action-20260928\Screen2.screen-plan.md` |
| Modify | Screen3 件ごとの確認 | `C:\dev\Powerapps_gas\outputs\canvas-mq-one-action-20260928\Screen3.pa.yaml` | Screen3 | s03One | `C:\dev\Powerapps_gas\outputs\canvas-mq-one-action-20260928\Screen3.screen-plan.md` |

Screen2/3 are assigned to the root owner; Screen1 is assigned to this implementation branch. Verify each Required Action against its brief and compile the local screen after the edits. Do not change `App.pa.yaml` or call cloud APIs from this subtask.

## Editor State Changes

None. Preserve exact order: `Screen1`, `Screen2`, `Screen3`, `Screen4`. No screen is added or renamed.

## Blockers and Non-Goals

- Confirmed child table/source and fields are listed in `canvas-app-shared.md`; the Canvas YAML still needs compile and Studio preview verification for two independent attachment forms and chained form submissions.
- Exact lookup for duplicate filename on legacy parent Notes must map `filename` to the parent GUID and return all matches; a generic “legacy might match” warning is not accepted as completion.
- This local Screen1 YAML and plan-file work does not create cloud rows or files. Root coordinates cloud edits and the approved fictional-data test ceiling. No purchase, destructive cleanup, public release, practical data use, or old-case rerun is included.
