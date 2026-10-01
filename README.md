# MQ ID照合アプリ

更新対象一覧のExcelとサーバーログ1つを照合し、ログに記録されていないMQ IDや一覧にないIDを確認するPower Apps／Power Automateの作品です。`ALL SUCCESS`はログ末尾の表示であり、ID一致やMQ更新成功の証明ではありません。

現在はDeveloper環境の非公開アプリです。作者アカウントでStudioのプレビューを操作できます。一般公開・別人アカウントの権限・実務データ利用の受入は未実施です。

## 操作を確認する

1. [Power Apps編集画面](https://make.powerapps.com/e/c1719a14-6cac-eb5b-b598-2254af1c64b7/canvas/?action=edit&app-id=%2Fproviders%2FMicrosoft.PowerApps%2Fapps%2F3186a908-ac5b-48cc-90f5-d50e07282ee7)を作者アカウントで開き、▶でプレビューします。
2. 受付で環境とサーバーを選びます。環境AはサーバーA、環境BはサーバーBを使います。
3. 「更新対象一覧（Excel）」へxlsxを1つ、「サーバーログ（txt）」へ同じ組のtxtを1つ添付します。
4. 「照合を開始」を1回押します。内部で件と2ファイルを保存・確認してから照合します。日付・実行回の入力は不要です。同じファイルでも新しい照合を何度でも行えます。
5. 完了したら「ログと結果を見る」で差異IDと結果を確認します。
6. 担当者の確認を入力し、「レビューを依頼」で確認ダイアログの内容を確認してから依頼します。レビュー画面で確認・差し戻しを記録できます。

この操作はDataverseの新規記録・添付、OneDriveの照合結果Excelを作ります。設定済みのSharePoint保管とTeams通知も処理・レビューの状態に応じて動きます。ローカルファイル作成とGit保存だけでは、これらのクラウド操作は行われません。

## 環境A・Bの6組

各Excelは100 ID。ログは100、99、50 IDです。

| 選択する環境／サーバー | フォルダー | 差異0件 | 差異1件 | 差異50件 |
|---|---|---|---|---|
| 環境A／サーバーA | [environment-a](samples/mq-acceptance/environment-a) | mq-env-a-diff-0.xlsx/txt | mq-env-a-diff-1.xlsx/txt | mq-env-a-diff-50.xlsx/txt |
| 環境B／サーバーB | [environment-b](samples/mq-acceptance/environment-b) | mq-env-b-diff-0.xlsx/txt | mq-env-b-diff-1.xlsx/txt | mq-env-b-diff-50.xlsx/txt |

不足ID：環境Aの1件はMQ-3100、50件はMQ-3051～MQ-3100。環境Bの1件はMQ-4100、50件はMQ-4051～MQ-4100。絶対パスと操作は[確認用ファイルの説明](samples/mq-acceptance/README.md)にあります。日付なしで翌日以降も使用できます。

Excelの契約は `Batch_Input` シート1枚、A2に `MQ_ID`、A3以降にIDです。ログの `MQ_BOX_ID=` 行を読みます。ログの環境・サーバー識別行は現行の保存値に合わせています。画面表示の「環境A/B・サーバーA/B」は保存値の「架空環境A/B・架空サーバーA/B」から表示上の「架空」を取り除いたものです。

## ソースと資料

- [canvas/current](canvas/current)：最新の保存済みApp・4画面・編集状態と取得元。
- [フロー構築とOffice Script](outputs/flow-implementation)：既存照合処理のソース。
- [入力生成コード](scripts/build_mq_acceptance.mjs)：今回の6組の生成コード。`@oai/artifact-tool` を使用。
- [要件](docs/REQUIREMENTS.md)、[確認方法](docs/CHECKS.md)、[作業履歴](docs/TASKS.md)、[引き継ぎ](docs/HANDOFF.md)。
- [Git保存対象の分類](docs/GIT_CONTENTS.md)：コミット対象・ローカル保全・除外理由。

## 確認済みと未確認

今回の6組は保存したExcelとログを読み直し、差異0/1/50、余分なID0、重複0をローカルで確認済みです。入力シートの表示も確認しました。この6組の実機照合はユーザー確認待ちです。直近の画面変更はStudio非公開保存・コード読戻し・表示確認を実施しましたが、MCP接続が422で失敗したため、この版をcompile_canvasで検査したとは扱いません。

2026-10-02に承認済みの過去テスト記録と入力・結果を削除しました。以前の結果URLを現在の確認先には使いません。復旧用コピーはローカル／専用クラウドフォルダーに保持し、Gitに送信しません。履歴と未確認事項は作業記録を参照してください。
