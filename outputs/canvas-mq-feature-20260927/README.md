# MQ Canvas ローカル候補

2026-09-27にCanvas Authoring MCPで読み戻し、前回スナップショットともSHA-256一致を確認した6 YAMLを起点に作ったローカル候補です。同期元 `outputs/canvas-mq-live-sync-20260927/` は編集していません。候補workspaceは6 YAMLのみです。**現行アプリのMQ対応Canvas定義はStudioへ保存済み**で、このフォルダーは現行クラウド定義を読み戻した正本ではありません。Developer環境の実機結果と未確認範囲は[docs/TASKS.md T-013](../../docs/TASKS.md)を参照してください。

## 画面候補の変更

- **Screen1（受付）**: `.txt`を複数受付し、1ファイルごとに既存の件キューを作る経路を維持します。選択中の件に「ログのみ／MQ照合」を表示し、添付された`.xlsx`でMQ照合モードへ切り替えます。ログのみは`.txt` 1件のみ、MQ照合は`.txt` 1件と`.xlsx` 1件のみで保存できます。拡張子違い・同種重複・片方欠落は保存を止めます。キュー内の添付をQueueIdで保持する候補式を追加し、保存後は件ID・件数・拡張子別件数・状態列を読み戻した場合に限り「保存済み」にします。結果不明の件は既存ガードどおり停止し、キューの未保存件が残る間は処理開始を無効にします。
- **Screen2（進捗一覧）**: MQ比較状態、終了表示、予定・ログ記録・欠落件数を表示します。未書込みの列は「未確定」と表示し、ログ終端`ALL SUCCESS`を全ID成功とは扱わない説明を加えています。
- **Screen3（件ごとの確認）**: 同じ件の添付にある`.txt`と`Batch_Input .xlsx`の件数、結果Excelリンク、7つのMQ列、予定ID別TSV結果を表示します。TSVギャラリーは行単位でスクロールできます。既存の担当者判断とレビュー操作は残しています。
- **Screen4、App、EditorState**: 現行読み戻し版からバイト単位で変更していません。

Dataverse列はフロー担当と合意した名前を使います: `cr6cb_mqterminalstatus`, `cr6cb_mqexpectedcount`, `cr6cb_mqloggedcount`, `cr6cb_mqmissingcount`, `cr6cb_mqmissingids`, `cr6cb_mqcomparisonstatus`, `cr6cb_mqresulttext`。Developer環境の件表にはこの7列を追加して読み戻し済みです。列payloadを別環境に適用する場合は、その環境のSchemaNameと既存列を確認してください。

終端表示がない場合は、7列が記録する診断情報を画面で「ログ不完全・要確認」と表示する想定です。この診断情報は転記処理の成功を表しません。結果Excelのリンクは既存の`cr6cb_excelurl`だけを使い、両シートの読戻し確認を通ったリンクがない場合は無効のままです。

## 添付制御の未確認事項

Classic Attachmentsコントロールに `OnAddFile` / `OnRemoveFile` / `OnUndoRemoveFile`、`Items` Table、`Attachments` Tableがあることは読み取り専用の制御説明で確認済みです。候補はコントロールの`Items`をQueueId別コレクションに結び、編集結果の`Attachments`をフォームの添付列に渡します。ただし、複数キューの添付Blobをコレクションに保持して選択を切り替える挙動、`Items.Name` / `Items.Value`の型、`Self.Attachments`のイベント時点、読戻し行のファイル名列がPower Fx/Dataverseで想定どおり動くかは**未検証**です。拡張子での役割分けは受付ガードであり、ファイル本文の`Batch_Input`シートやログ形式の検証はフロー側の責任です。

このローカル候補workspace自体はCanvasでコンパイル・保存していません。現行4画面のMQ対応版はStudioで保存済みで、run92704の進捗一覧と件ごとの確認画面では予定5／記録4／欠落`MQ-0003`・「要確認」の表示を確認しました。別サイズでのレイアウト、アクセシビリティ、レビュー操作、ログだけの既存経路は未確認です。

## ローカル検査

```powershell
python outputs/canvas-mq-feature-20260927/test_canvas_mq_static.py -q
```

この検査は候補YAMLの静的文字列条件と6ファイル構成、変更しない3ファイルのSHA-256のみを確認します。このローカル候補を対象にした検査はCanvas構文検査やクラウド保存を行いません。別途、現行MQ対応Canvas 6ファイルはMCP構文検査後にStudio保存され、run92704の画面表示も確認済みです。ログ本文の実機検査結果と残る画面条件は`docs/TASKS.md` T-013に記録します。
