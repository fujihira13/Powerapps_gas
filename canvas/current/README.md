# 保存済みCanvas定義

現在の非公開Studio保存内容を追跡する場所です。途中の同期コピーは outputs 内でローカルだけに保持します。

| ファイル | 保存内容の取得元 |
|---|---|
| Screen1.pa.yaml、Screen3.pa.yaml | outputs/ui-cleanup-20261001/canvas-saved（2026-10-02の余白・未保存表示修正） |
| App.pa.yaml、Screen2.pa.yaml、Screen4.pa.yaml、_EditorState.pa.yaml | outputs/canvas-20261001-clipping-verified-save（今回の2画面修正では変更なし） |

Studioの保存とコード読戻しは実施済み。MCP接続が422で失敗したため、この版をcompile_canvasで検査したとは扱いません。画面のユーザー受入は別途必要です。このフォルダーの追加によってクラウドの画面を再送信・公開したものではありません。

環境・サーバーの選択肢は有効なDataverse転記先を参照し、「架空」の文字を表示から除いています。ログ本文の照合には実際の保存値を使います。
