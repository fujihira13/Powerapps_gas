# MQ ID照合ロジック

このフォルダーには、フローが抽出した架空の入力をJSONで受け取り、予定MQ IDとログ記録IDを比較するPythonの純粋ロジックを置いています。Power Platform、Dataverse、OneDrive、Excel Onlineへ接続しません。元のExcelファイルを開く処理も含みません。

## 入出力契約

- 入力契約は[`input-contract.schema.json`](input-contract.schema.json)（`mq-id-input.v1`）です。フロー側のアダプターがExcelからシート名と行・セル値をJSONへ変換し、ログ本文を`log_text`へ渡します。
- 出力契約は[`result-contract.schema.json`](result-contract.schema.json)（`mq-id-result.v1`）です。`compare_payload()`が返す辞書はJSONへそのまま変換できます。
- `case_name`はfixtureを見分ける任意の補助欄で、照合結果には影響しません。フローは省略できます。
- Excelはシート`Batch_Input`が1枚だけ、`A2`が厳密に`MQ_ID`、`A3`以降はA列に1件ずつIDを置きます。`A1`はタイトル可。B列以降に値がある行、追加シート、空のID行、ヘッダー違いは入力エラーです。末尾の空行は無視します。
- IDは前後空白を除き、ASCII数字4桁の`MQ-0001`形式で比較します。予定側・ログ側それぞれの重複、形式不正をエラーとして出し、比較を止めます。
- ログIDは行頭が`MQ_BOX_ID=`で始まる行だけを見ます。値は1つのID全体である必要があります。文中のIDや`MQ_BOX_STATUS=READY`は数えません。
- ログの最後の非空行が`ALL SUCCESS`のときだけ終了マーカーありです。これはログ出力の終端を示し、MQ更新成功を証明しません。

主な出力フィールドは次のとおりです。

| フィールド | 意味 |
| --- | --- |
| `status` | `input_error`、`log_incomplete`、`comparison_ready`のいずれか |
| `expected_ids` / `logged_ids` | 検証できたIDの重複なし一覧。出現順を維持 |
| `missing_ids` | 予定にはあるがログにないID。入力エラーの場合は`null` |
| `log_only_ids` | ログにだけあるID。入力エラーの場合は`null` |
| `duplicate_ids` / `invalid` / `errors` | 入力エラーの種別と行・値。`input_error`ならフローは後続処理を止める |
| `presentation.status_label` | エラー・ログ終端なし・差異ありは`要確認`。差異がない場合は`比較完了` |
| `presentation.stop_processing` | `input_error`または`log_incomplete`なら`true`。フローは要確認で停止する |
| `presentation.human_decision_required` | 常に`true`。比較結果から更新の成否を自動確定しない |

`log_incomplete`でも比較配列は計算しますが、`stop_processing`を`true`にして`要確認`を返します。欠落IDは「ログ未記録」であり、個別の更新失敗とは断定しません。入力エラーでは`missing_ids`・`log_only_ids`と対応する件数が`null`です。`counts.expected`・`counts.logged`は、形式を確認できた重複なし候補数を示します。`comparison_ready`は比較処理が成立した意味だけで、バッチやサーバー上の反映成功を意味しません。

入力エラー時に`expected_ids`・`logged_ids`へ値があっても、これは診断用に形式を確認できた一部候補です。`comparison_available: false`なら差分計算には使わず、フローは停止してください。

## 実行と確認

プロジェクトルートから実行します。

```powershell
python outputs/mq-id-feature/generate_fixtures.py
python -m unittest discover -s outputs/mq-id-feature -p test_mq_id_compare.py
Get-Content -Raw -Encoding utf8 outputs/mq-id-feature/fixtures/design-preview-5.json | python outputs/mq-id-feature/mq_id_compare.py
```

`fixtures/design-preview-5.json`は見本の`Batch_Input` A1:A7と`mock-log.txt`をJSON化したものです。期待値は5件、ログ記録は4件、欠落は`MQ-0003`、終端マーカーありです。`fixtures/synthetic-100.json`は約100件の架空例で、`MQ-0050`の未記録とログのみの`MQ-9001`を含みます。

実装は標準ライブラリのみです。Python関数のテストはローカルで完結し、サービスへの通信を行いません。
