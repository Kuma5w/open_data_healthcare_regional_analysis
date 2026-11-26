# 共通対応表

各自がばらばらに処理すると結果を比べられなくなる部分を、ここで1つに揃えます。

| ファイル | 内容 | 状態 |
|---|---|---|
| `designated_cities.csv` | 政令指定都市20市の5桁コード。区→市の置き換え（`chiiki_od.codes.ward_to_city`）に使う | 記入済み |
| `koso_kuiki.csv` | 構想区域（原則は二次医療圏）と市区町村の対応 | 列だけ。要作成 |
| `municipality_mergers.csv` | 市町村合併の旧コード→新コード | 列だけ。要作成 |

## 決まりごと

- コードは**5桁の文字列**で書く（6桁の検査数字付きは `codes.to_code5` で変換）。
- 1行ごとに `source_url`（根拠にした資料）を書く。
- 構想区域は都道府県の地域医療構想で決まり、見直されることがあるため、`valid_from`（適用開始日）を書く。

## koso_kuiki.csv の列

`pref_code, koso_kuiki_code, koso_kuiki_name, municipality_code5, municipality_name, valid_from, source_url`

`koso_kuiki_code` は全国で一意になるよう、都道府県コード2桁＋連番2桁（例：4301）を仮に使います。正式なコード体系があれば置き換えます。

## municipality_mergers.csv の列

`old_code5, old_name, new_code5, new_name, effective_date, source_url`
