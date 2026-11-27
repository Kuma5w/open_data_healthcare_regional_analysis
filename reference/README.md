# 共通対応表

各自がばらばらに処理すると結果を比べられなくなる部分を、ここで1つに揃えます。

| ファイル | 内容 | 状態 |
|---|---|---|
| `designated_cities.csv` | 政令指定都市20市の5桁コード。区→市の置き換え（`chiiki_od.codes.ward_to_city`）に使う | 記入済み |
| `koso_kuiki.csv` | 市区町村（政令市は区）→ 構想区域・二次医療圏の対応。令和7年度病床機能報告の構想区域マスタ（別紙２）から作成 | 記入済み（1,892行、構想区域339、二次医療圏330） |
| `secondary_medical_area_2023.csv` | 市区町村（政令市は区）→ 二次医療圏。厚生労働省「二次医療圏－市区町村対応表（令和5年12月31日）」から作成 | 記入済み（1,896行、二次医療圏335） |
| `bfr_item_map.csv` | 病床機能報告の列の、年度をまたぐ対応（令和7年度の列 → 令和3〜6年度の列）。23列（見出しで照合して作った。ほかの項目は、使う指標のスクリプトで同じように対応づける） | 作成済み |
| `municipality_mergers.csv` | 市町村合併の旧コード→新コード | 列だけ。要作成 |
| `../site/geo/n03_20260101.topo.json` | 地図の境界（市区町村・政令市の区・構想区域・都道府県）。国土数値情報（行政区域、令和8年1月1日）から作成 | 作成済み（下の「地図の境界」） |

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

## secondary_medical_area_2023.csv

`pref_code, pref_name, secondary_area_code, secondary_area_name, municipality_code5, municipality_name, valid_for, source_url`

- 作り方：`python scripts/make_secondary_area_reference.py --file <二次医療圏.xlsx>`
- 元ファイル（e-Govデータポータル、公開日2024-03-15）は**令和5年12月31日時点**、つまり第7次医療計画の二次医療圏。
- `koso_kuiki.csv`（令和7年度病床機能報告の構想区域マスタ）の二次医療圏と比べると、違いは次の2点だけ。
  - 秋田県：8医療圏 → 3医療圏（県北・県央・県南）に再編（第8次医療計画）。25市町村の二次医療圏が変わる
  - 浜松市：2024年1月の行政区の再編で、7区（22131〜22137）→ 3区（22138 中央区、22139 浜名区、22140 天竜区）
- 令和6年度以降のデータには `koso_kuiki.csv` の二次医療圏を、令和5年度以前のデータにはこの表を使う。
- 政令市の区の `municipality_name` は区名だけ（例：中央区）。
- 出典：厚生労働省「二次医療圏－市区町村対応表（令和5年12月31日）」（e-Govデータポータル）を加工して作成

## municipality_mergers.csv の列

`old_code5, old_name, new_code5, new_name, effective_date, source_url`

## 地図の境界（site/geo/）

サイトの地図は、国土数値情報（行政区域データ N03、令和8年1月1日時点）から作った TopoJSON を使います。1つのファイルに、境界線を共有する4つの層が入っています。

| 層 | 地域 | コード（`code`） |
|---|---|---|
| `municipality` | 市区町村（政令市は市にまとめる） | 5桁。1,741市区町村＋北方領土の6村 |
| `municipality_ward` | 市区町村（政令市は区） | 5桁 |
| `koso_kuiki` | 構想区域（この表の `koso_kuiki.csv` で市区町村をまとめる） | 4桁。339区域 |
| `prefecture` | 都道府県 | 2桁 |

- 作り方：国土数値情報のページから「全国」の zip（`N03-20260101_GML.zip`、約766MB）を保存し、`python scripts/make_boundaries.py --src <zip か 展開した N03-20260101.shp>`。Node.js が必要（mapshaper を使う）。
- 所属未定地は除き、面積2km²未満の島は省略し、約200mより細かい凹凸を省いて簡略化しています（表示用。面積や距離の計算には使わない）。
- N03 の市区町村コードと `koso_kuiki.csv` は過不足なく一致しました（N03 にだけあるのは北方領土の6村。構想区域の層には入りません）。浜松市の区の再編（2024年1月）も両方に反映されています。
- 元ファイルの SHA-256、mapshaper の版と設定、照合の結果は `site/geo/n03_20260101.meta.json` にあります。
- 出典：国土交通省「国土数値情報（行政区域データ）」（令和8年1月1日時点）を加工して作成（CC BY 4.0）
