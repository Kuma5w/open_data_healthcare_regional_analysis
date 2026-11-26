# 医療施設調査（厚生労働省）二次医療圏・市区町村編の使い方

厚生労働省「医療施設調査」の二次医療圏・市区町村編のうち、次の2つの表を1つの Parquet にしたものです。

| データセットid | 時点 | 表 | ファイル |
|---|---|---|---|
| `medical_facility_survey_r7` | 令和7年10月1日 | 第1表 病院数・病床数（病床の種類別） | n0001.csv |
| 〃 | 〃 | 第2表 一般診療所数・歯科診療所数・病床数（病床の有無別） | n0002.csv |

e-Stat（https://www.e-stat.go.jp/stat-search/files?toukei=00450021）の「医療施設調査」から、令和7年の二次医療圏・市区町村編の表を CSV でダウンロードします。
直接ダウンロードするURLを決めていないので、ファイルを置いたフォルダを `--from-dir` で指定して取り込みます。

```bash
chiiki-od fetch medical_facility_survey_r7 --from-dir ~/Downloads/R7_iryoshisetu   # n0001.csv と n0002.csv を置いたフォルダ
chiiki-od convert medical_facility_survey_r7
```

## 元の表の形と変換

- 文字コードは Shift_JIS（cp932）。1行目に調査名と時点、2行目に表題、そのあと複数行の表頭が続きます。
- データの行は、1列目が「コード＋全角空白＋名前」です。コードの桁数で行の種類が分かります。
  - 2桁：都道府県
  - 4桁：二次医療圏（令和7年10月1日時点で330圏）
  - 5桁：市区町村。政令市は区の行だけで、市の合計行はありません
- 記号「-」は計数がない（0）です。
- 変換では市区町村の行（1,892行）だけを残し、直前の二次医療圏の行を `secondary_area_code`・`secondary_area_name` の列にしました。
- 変換のときに、都道府県と二次医療圏の行が市区町村の合計と一致するか、内訳の合計（精神科病院＋一般病院、有床＋無床など）が総数と一致するかを確かめます。令和7年の表では、すべて一致しました。

市区町村コードは `reference/koso_kuiki.csv` と過不足なく一致するため、構想区域にそのまままとめられます。

## 列

| 列 | 内容 |
|---|---|
| `municipality_code` | 5桁（検査数字なし）。政令市は区のコード |
| `municipality_name` | 名前。政令市の区は区名だけ（例「中央区」） |
| `hospitals`・`general_hospitals`・`psychiatric_hospitals` | 病院数（総数・一般病院・精神科病院） |
| `general_hospitals_with_ltc_beds`・`regional_support_hospitals`・`emergency_hospitals` | 療養病床を有する一般病院・地域医療支援病院・救急告示病院（いずれも再掲） |
| `hospital_beds`・`beds_psychiatric`・`beds_infectious`・`beds_tuberculosis`・`beds_ltc`・`beds_general` | 病院の病床数（総数と種類別） |
| `general_clinics`・`clinics_with_beds`・`clinics_without_beds`・`clinics_with_ltc_beds` | 一般診療所数（総数・有床・無床・療養病床を有する（再掲）） |
| `dental_clinics`・`dental_clinics_with_beds`・`dental_clinics_without_beds` | 歯科診療所数 |
| `clinic_beds`・`clinic_ltc_beds` | 一般診療所の病床数・うち療養病床 |

## 注意

- **医師数・歯科医師数・薬剤師数はこの表にありません。** 医師・歯科医師・薬剤師統計（2年ごと、12月31日現在）にあります。病院の従事者数は、3年ごとの静態調査にあります。
- 医療施設調査の公表値の「人口10万対」は推計人口（10月1日）によります。このリポジトリの指標は住民基本台帳の人口を使うので、値は一致しません。
- 動態調査は、開設・廃止などの届出をもとにしています。

## 共通処理

指標スクリプトは `chiiki_od.iryo_shisetsu` を使います。

- `load_facilities()`：変換後の表を読む
- `per_population(facilities, population, count_cols, value_col, unit, digits)`：人口10万人あたりの値にする。`unit` は `"koso_kuiki"`（構想区域）か `"municipality"`（市区町村。政令市は市にまとめる）

## 出典の書き方

> 出典：厚生労働省「医療施設調査」（令和7年10月1日現在）を加工して作成
