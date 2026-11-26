# 住民基本台帳に基づく人口（総務省）の使い方

総務省「住民基本台帳に基づく人口、人口動態及び世帯数」の【総計】年齢階級別人口（市区町村別）を Parquet にしたものです。

| データセットid | 時点 | 公表ファイル | 入手方法 |
|---|---|---|---|
| `population_jumin_r8` | 令和8年1月1日 | 000892953.xlsx | 総務省のページから直接取得できる |
| `population_jumin_r7` | 令和7年1月1日 | 2504ssnen.xlsx | e-Stat から手動でダウンロードし、`--from-dir` で取り込む |

```bash
chiiki-od fetch population_jumin_r8
chiiki-od fetch population_jumin_r7 --from-dir ~/Downloads/population   # 2504ssnen.xlsx を置いたフォルダ
chiiki-od convert population_jumin_r7
```

## 列

| 列 | 内容 |
|---|---|
| `municipality_code` | 5桁（6桁の団体コードから検査数字を除いたもの）。全国は `00000` |
| `pref_name`・`municipality_name` | 都道府県名・市区町村名 |
| `sex` | `total`（男女計）・`male`・`female` |
| `level` | 行の種類（下表） |
| `pop_total` | 総数 |
| `age_00_04` 〜 `age_95_99`・`age_100plus` | 5歳階級 |
| `pop_0_14`・`pop_15_64`・`pop_65plus`・`pop_75plus` | 5歳階級を足したもの |
| `age_sum_gap` | 総数と5歳階級の合計の差（下の注意を参照） |
| `as_of` | 時点 |

## 行の種類（level）と二重計上

1つの表に、市区町村の行と集計行が混ざっています。

| level | 内容 | 足し上げに使うか |
|---|---|---|
| `municipality` | 市町村（東京都の特別区を含む） | 使う |
| `ward` | 政令指定都市の区 | 使う |
| `designated_city` | 政令指定都市の合計 | 使わない（区と二重） |
| `county` | 郡の合計 | 使わない（町村と二重） |
| `islands` | 東京都の島しょの合計 | 使わない（町村と二重） |
| `prefecture`・`national` | 都道府県・全国 | 使わない |

`municipality` と `ward` の行を足すと、全国の総数と一致します（令和7年・令和8年で確認）。構想区域にまとめるときは `chiiki_od.areas.population_units` と `to_koso` を使います（`reference/koso_kuiki.csv` は政令市を区単位で持っています）。

## 注意

- 外国人住民が少ない市区町村では、外国人住民の5歳階級の内訳が非公表です。そのため総数と5歳階級の合計が合わない行があり、`pop_65plus` などはわずかに少なく数えられます（差は `age_sum_gap`）。
- 外国人住民のうち性別欄が空欄の人は男女に計上されず、総数にのみ計上されます。`male`＋`female` は `total` と一致しない場合があります。
- 北方領土の6村は人口0で、構想区域の対応表にはありません。

確認用の全国の値：

| 時点 | 総数 | 65歳以上 | 75歳以上 |
|---|---:|---:|---:|
| 令和7年1月1日 | 124,330,690 | 35,916,427 | 20,664,082 |

出典表記の例：出典：総務省「住民基本台帳に基づく人口、人口動態及び世帯数」（令和7年1月1日現在）を加工して作成
