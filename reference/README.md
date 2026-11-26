# 共通対応表

各自がばらばらに処理すると結果を比べられなくなる部分を、ここで1つに揃えます。

| ファイル | 内容 | 状態 |
|---|---|---|
| `designated_cities.csv` | 政令指定都市20市の5桁コード。区→市の置き換え（`chiiki_od.codes.ward_to_city`）に使う | 記入済み |
| `koso_kuiki.csv` | 市区町村（政令市は区）→ 構想区域・二次医療圏の対応。令和7年度病床機能報告の構想区域マスタ（別紙２）から作成 | 記入済み（1,892行、構想区域339、二次医療圏330） |
| `municipality_mergers.csv` | 市町村合併の旧コード→新コード | 列だけ。要作成 |

## 決まりごと

- コードは**5桁の文字列**で書く（6桁の検査数字付きは `codes.to_code5` で変換）。
- 1行ごとに根拠の資料（`source_url`）を書く。
- 構想区域は都道府県の地域医療構想で決まり、見直されることがある。どの時点の区域かを `valid_for` に書く。

## koso_kuiki.csv

`pref_code, municipality_code5, municipality_name, koso_kuiki_code, koso_kuiki_name, secondary_area_code, secondary_area_name, valid_for, source_url`

- 作り方：`python scripts/make_koso_kuiki_reference.py`（留意事項ZIPから作り直す）
- 構想区域コードと二次医療圏コードは4桁（都道府県2桁＋2桁）。構想区域と二次医療圏が一致しない市区町村が51ある（秋田県など）。
- 政令指定都市は区ごとの行になっている。市単位で使うときは `ward_to_city` で市にまとめる。
- 出典：厚生労働省「令和7年度病床機能報告 別紙２ 構想区域マスタ」を加工して作成

## municipality_mergers.csv の列

`old_code5, old_name, new_code5, new_name, effective_date, source_url`
