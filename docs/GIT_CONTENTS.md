# Gitへ保存するもの・ローカルに残すもの

2026-10-02、ユーザーのコミット・push依頼に合わせて分類した。送信先は既存originの `https://github.com/fujihira13/Powerapps_gas.git`。アプリの公開とは別の操作。

## 2026-10-03 今回の分類

既存origin/mainへのコミット・通常pushはユーザーが明示依頼。保存済みCanvasはApp・5画面・編集状態の7定義。管理プラグインのソースとローカル契約検査、scriptsの生成・反映・読み戻しコード、承認済みHTML見本、今回の要件・計画・検査・画面資料を保守対象とする。

`outputs/再テスト用ファイル_2026-10-03`の人工入力8組16ファイルと手順書は再利用するテスト材料として保存する。再生成コードは`scripts/build_fresh_test_files.mjs`。結果記録CSVは利用者の記入用としてGit対象外とし、生成コードから再作成できる。

`outputs/environment-management-*`と`outputs/test-reset-*`は実環境の退避・登録一覧・API送信データ・署名済み生成物・検査・画像等を含むため全体を除外。署名鍵`*.snk`も場所によらず除外する。ファイル自体はローカルに残す。[今回の実施手順](plans/git-save-20261003.md)。

送信前確認：74ファイル、うち人工入力16と手順1。ステージした全ファイルの秘密値らしい文字列（xlsx内部XMLも対象）は検出0、除外対象の混入0、差分書式確認合格。管理契約16項目PASS、Python5ファイル・生成JavaScriptの構文確認合格。fetch時点のHEADとorigin/mainの差は0／0。push完了とハッシュは最終チャットに記録する。

## 2026-10-02 コミットしたもの

| 対象 | 内容・理由 |
|---|---|
| .gitignore、README.md | 除外規則と現在の操作案内 |
| docs の要件・画面仕様・確認記録・計画 | 合意と変更内容を引き継ぐための資料 |
| canvas/current の6定義＋来歴 | 保存済みの最新画面。途中のコピーと区別する |
| outputs/flow-implementation の変更済みソース・検査 | 既に依頼されたフロー構築コード、Office Script、必要な検査コード |
| outputs/flow-implementation/test-fixtures | 自動検査で参照する人工入力。旧操作用ファイルとは別 |
| outputs/date-independent-20261001/test_date_independent.py | 日付なし入力を確認する最小検査。隣の実環境バックアップは除外 |
| scripts/build_mq_acceptance.mjs | 新しい6組の入力を再生成するコード |
| samples/mq-acceptance | 環境A・Bの6組・12入力、期待値JSON、操作案内 |
| 承認済み旧ファイルの削除差分 | 削除済み入力をGitでも現在の状態へ合わせる |

## .gitignoreで除外し、ローカルに残すもの

| 対象 | 理由 |
|---|---|
| outputs/canvas-* | 同期・保存前後・診断の重複画面。最新はcanvas/current |
| outputs/ui-cleanup-*、cleanup-execution-* | Dataverseの記録・添付本文、削除対象一覧、復旧用コピー |
| outputs/sharepoint-teams-flow-definitions-*、ライブフローのpreflight JSON | 実環境の接続先・接続参照を含む退避用定義 |
| outputs/date-independent-20261001の検査以外 | 実環境の変更前後JSON、API送信用データ、再生成可能な記録 |
| outputs/review-ux-*、mq-group1-* | 実画面キャプチャー、試験途中の出力、実環境定義 |
| outputs/mq-20260930-ui-compare、mq-final-clarity-*、mq-readability-* | Office Scriptから生成されるラッパー等 |
| outputs/mq-user-test-*、mq-fresh-test-*、mq-acceptance-previews | 旧操作用入力・プレビュー。今回の確認用入力はsamplesへ保存 |
| *.inspect.ndjson、node_modules、キャッシュ・認証ファイル | 診断出力・依存物・ローカル秘密情報 |

除外はファイルの削除ではない。ローカルの復旧用コピーと旧出力は保持する。既に追跡されている過去の資料・画面コピーは、今回無断で追跡解除や履歴削除をしない。今後それらをまとめる場合は別途判断する。

## 最小確認と制限

入力は保存したExcelを読み直し、100 IDに対するログ記録100/99/50と差異0/1/50を全6組で確認。生成した6シートを表示確認。日付なし入力の既存4検査を実行。Gitのステージ一覧・差分・秘密値らしい値を確認してから通常pushする。クラウド照合、レビュー、通知、公開は今回実行しない。

ソース・資料にある環境URL、GUID、接続参照名は認証情報自体ではない。必要な既存設定を保持するが、アクセストークン、署名付きダウンロードURL、添付本文、記録のバックアップは送信対象にしない。一般的な文字列検査は秘密が存在しないことの完全な保証ではない。

## 今回の確認結果

- 変更・追加・承認済み削除を含む90ファイルをステージ。追加・変更63ファイルについて秘密値らしい文字列を検査し、検出0。バックアップ・途中の画面コピー・依存物の混入0。
- 最新6画面定義は保存済みの取得元とバイト単位で一致。
- .gitignoreで実データの退避・添付本文・ライブ定義・検査サイドカーが除外されることを確認。
- 日付なしの4検査、照合結果Excelの2検査が合格。6組の入力は保存後の再読込で100/100/0、100/99/1、100/50/50を確認。
- fetch後のHEADとorigin/mainの差は0。強制pushや履歴の書き換えをせず、現在のmainに1コミットとして保存する。
- 過去の資料は履歴として残す。Git対象外ファイルの追加削除はしていない。
