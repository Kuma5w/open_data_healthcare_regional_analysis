# 地域医療構想 オープンデータ共有基盤

地域医療構想の分析に携わる研究者どうしで、オープンデータを使った**基本的な分析の考え方と方法を共有する**ためのリポジトリです。

データや生成AIへの慣れは人によって違います。そこで、指標ごとに「作成者がどんな意図でその指標を作ったのか」を**指標カード**に書き残し、計算はスクリプトで再現できるようにしています。サイトに置く解説チャットボットは、この指標カードを根拠に質問に答えます。

サイト：https://kuma5w.github.io/open_data_healthcare_regional_analysis/

> 状態（2026年11月）：データセット28、指標32。指標はすべて草案（`status: draft`）で、意見をもらいながら直していく段階です。サイトの「結果を見る」から地域を選んで、表・グラフ・地図・CSV・印刷用の1枚を出せます。表示の切り替えは、質問窓口に「熊本県の結果を出して」と書いてもできます。

## はじめての方へ

インストールしなくても、サイトだけで使えます。

1. **サイトで指標を選ぶ**：[指標の一覧](https://kuma5w.github.io/open_data_healthcare_regional_analysis/)から、関心のある指標を開きます。
2. **指標カードを読む**：作成者の意図、分子と分母、なぜその分母を選んだか、注意点が書いてあります。数値より先に、ここを読んでください。
3. **結果を見る**：地域を選ぶと、表・グラフ・地図が出ます。CSV をダウンロードしたり、印刷用の1枚を出したりできます。
4. **質問窓口に聞く**：指標の意味を、カードを根拠にAIが答えます。AIの接続先は各自で設定します（[docs/site.md](docs/site.md) の「質問窓口の接続先」）。「熊本県の結果を出して」のような表示の切り替えは、AIを設定しなくても使えます。
5. **手元で再現する**：計算はすべてスクリプトで再現できます（下の「はじめかた」）。

### 感想・意見を送る

使ってみた感想、分かりにくかった点、指標の考え方への意見を歓迎します。[Issue の「使ってみた感想・意見」](https://github.com/Kuma5w/open_data_healthcare_regional_analysis/issues/new?template=feedback.md)から送ってください。Issue は公開されます。新しい指標の提案は「新しい指標の相談」のテンプレートを使ってください。

## 指標の一覧

| 分野 | 指標 | 単位 | 使うデータ |
|---|---|---|---|
| 病床 | [回復期病床の割合](indicators/recovery_bed_share_koso.yaml)、[75歳以上人口10万人あたり回復期病床数](indicators/recovery_beds_per_100k_75plus_koso.yaml) | 構想区域 | 病床機能報告（令和7年度）、住民基本台帳人口 |
| 在宅医療等連携機能（作成者 D.S.） | 類型（P・S・C）の判定：[病院別](indicators/zaitaku_renkei_psc_hospital.yaml)・[構想区域別](indicators/zaitaku_renkei_psc_koso.yaml)、該当項目数の推移（FY2020〜2024）：[病院別](indicators/zaitaku_renkei_trend_hospital.yaml)・[構想区域別](indicators/zaitaku_renkei_trend_koso.yaml) | 病院（名前は伏せる）、構想区域 | 病床機能報告（令和3〜7年度）、外来機能報告（令和7年度）、地方厚生局の届出受理医療機関名簿 |
| 医療施設 | 人口10万人あたりの[病院数](indicators/hospitals_per_100k.yaml)・[一般診療所数](indicators/general_clinics_per_100k.yaml)・[歯科診療所数](indicators/dental_clinics_per_100k.yaml)（市区町村）、同じく[病院数](indicators/hospitals_per_100k_koso.yaml)・[一般診療所数](indicators/general_clinics_per_100k_koso.yaml)・[歯科診療所数](indicators/dental_clinics_per_100k_koso.yaml)（構想区域） | 市区町村、構想区域 | 医療施設調査（令和7年）、住民基本台帳人口 |
| 介護サービス | 65歳以上人口1万人あたり事業所数：[訪問介護](indicators/homecare_offices_per_65plus.yaml)・[訪問看護](indicators/visiting_nursing_offices_per_65plus.yaml)・[訪問リハビリテーション](indicators/visiting_rehab_offices_per_65plus.yaml)・[通所介護](indicators/day_service_offices_per_65plus.yaml)・[通所リハビリテーション](indicators/day_rehab_offices_per_65plus.yaml)・[短期入所生活介護](indicators/short_stay_offices_per_65plus.yaml) | 市区町村 | 介護サービス情報公表システム、住民基本台帳人口 |
| 精神医療（病床・医師） | 人口10万人あたりの[精神病床数](indicators/psychiatric_beds_per_100k_pref.yaml)・[在院患者数](indicators/psychiatric_inpatients_per_100k_pref.yaml)・[精神科医師数](indicators/psychiatrists_per_100k_pref.yaml)、[精神病床の利用率](indicators/psychiatric_bed_occupancy_pref.yaml)、[措置入院受入可能病床の利用状況](indicators/involuntary_bed_use_pref.yaml) | 都道府県 | 精神保健福祉資料（630調査、令和7年度）、住民基本台帳人口 |
| 精神医療（構想区域） | [人口10万人あたり精神病床数](indicators/psychiatric_beds_per_100k_koso.yaml) | 構想区域 | 医療施設調査（令和7年）、住民基本台帳人口 |
| 精神医療（診療実績） | [精神科救急医療体制整備事業に参画する病院数](indicators/psy_emergency_hospitals_per_1m_pref.yaml)、専門外来を持つ病院数：[児童・思春期](indicators/child_adolescent_clinics_per_1m_pref.yaml)・[依存症](indicators/addiction_clinics_per_1m_pref.yaml)・[認知症](indicators/dementia_clinics_per_1m_pref.yaml)・[うつ病](indicators/depression_clinics_per_1m_pref.yaml)・[発達障害](indicators/developmental_clinics_per_1m_pref.yaml)・[摂食障害](indicators/eating_disorder_clinics_per_1m_pref.yaml)、[医療保護入院の1年時点の退院率](indicators/medical_protection_discharge_1y_pref.yaml) | 都道府県 | 精神保健福祉資料（630調査、令和7年度）、住民基本台帳人口 |

人口あたりの指標の分母（総人口・65歳以上・75歳以上・20歳未満など）と、その理由は各カードに書いてあります。`chiiki-od list` でも一覧できます。

## 3つの約束

1. **数値はスクリプトが作る。** AIや手作業で数値を作らない。チャットボットやボタン出力も、登録済みの指標スクリプトを呼ぶだけにする。
2. **指標には必ずカードを付ける。** 意図・分子と分母・なぜその分母か・注意点を書く。カードのない指標は共有しない。
3. **出典と加工を明記する。** 元データの取得元・時点・ハッシュ値を記録し、成果物には出典と「加工して作成」を書く。

## 構成

```
datasets/        データセット定義（取得元URL・時点・列名の対応・利用規約）
indicators/      指標カード（<id>.yaml）と計算スクリプト（<id>.py）を1対1で置く
reference/       共通対応表（政令市、構想区域、二次医療圏、市町村合併）
codebooks/       変換後の列名と元の見出し・必須区分・欠損の件数の対応表
src/chiiki_od/   共通部品（市区町村コード、変換、実行、検証）
schemas/         指標カードとデータセット定義の形式（JSON Schema）
manifests/       取得・変換の記録（どのURLのどのファイルから作ったか）
site/            指標カタログのサイトと質問窓口（index.html と、catalog・results コマンドで作る JSON・CSV、geo/ に地図の境界）
docs/            指標カードの書き方、出典表記、データセットごとの使い方（docs/datasets/）
scripts/         対応表を作り直すスクリプトなど
tests/           テストと合成サンプルデータ
data/            元データ・変換後データ・計算結果（Gitには入れない）
```

## はじめかた

Python 3.10以上が必要です。

```bash
git clone https://github.com/Kuma5w/open_data_healthcare_regional_analysis.git
cd open_data_healthcare_regional_analysis
pip install -e ".[dev]"          # uv を使う場合は uv sync --extra dev

chiiki-od check                  # データセット定義と指標カードの検証
chiiki-od list                   # 登録済みのデータセットと指標
chiiki-od run homecare_offices_per_65plus --sample   # 合成サンプルで見本指標を計算
```

### 実データで計算する

```bash
chiiki-od fetch kaigo_jigyosho_110      # 元データを data/raw/ に取得
chiiki-od convert kaigo_jigyosho_110    # data/processed/ に Parquet で保存
chiiki-od run homecare_offices_per_65plus
```

訪問介護の指標には、人口データ（`population_jumin_r8`）の取り込みも必要です。

サイトの「結果を見る」に載せる結果は、`chiiki-od results` で `site/results/` に作ります（[docs/site.md](docs/site.md)）。

### 手元に保存した公表ファイルから取り込む

公表元のファイル名のまま保存したフォルダを指定すると、ダウンロードせずに取り込めます（記録には公表元のURLとハッシュ値が残ります）。

```bash
chiiki-od fetch bed_function_report_r7_form2_monthly --from-dir ~/Downloads/R7_hosp
chiiki-od convert bed_function_report_r7_form2_monthly
```

データセットごとの使い方と注意点は docs/datasets/ にあります。

- [病床機能報告](docs/datasets/bed_function_report.md)（令和3〜7年度。過年度の注意点は末尾）
- [外来機能報告](docs/datasets/outpatient_function_report.md)
- [地方厚生局の届出受理医療機関名簿](docs/datasets/kouseikyoku_todokede.md)
- [介護サービス事業所](docs/datasets/kaigo_jigyosho.md)
- [医療施設調査](docs/datasets/medical_facility_survey.md)
- [精神保健福祉資料（630調査）](docs/datasets/mental_health_630.md)
- [住民基本台帳人口](docs/datasets/population_jumin.md)

### 変換後のデータを直接使う

Parquet は pandas・R・DuckDB のどれからでも読めます。

```python
import duckdb
duckdb.sql("""
  SELECT pref_name, count(*) AS n
  FROM 'data/processed/kaigo_jigyosho_110.parquet'
  GROUP BY 1 ORDER BY 2 DESC
""")
```

```r
library(arrow)
df <- read_parquet("data/processed/kaigo_jigyosho_110.parquet")
```

## 指標を追加する

[CONTRIBUTING.md](CONTRIBUTING.md) を見てください。流れは、Issueで相談 → `indicators/_template.yaml` からカードを書く → 計算スクリプトを書く → `chiiki-od check` と `pytest` → プルリクエスト → レビュー、です。カードの書き方は [docs/indicator_card_guide.md](docs/indicator_card_guide.md) にあります。

## 作業の進め方

1. 雛形：構成・指標カードの型・共通対応表（済）
2. データの変換と指標（済。データセット28・指標32）
3. 指標カタログのサイトと解説チャットボット（済。[docs/site.md](docs/site.md)）
4. ボタン出力：表・グラフ・CSV・印刷・再現の手順、塗り分け地図、質問窓口からの地域の指定、推移のグラフ（済）
5. 公開して、プルリクエストの受け付けを始める（公開済み。少数の研究者に試してもらい、感想をもとに直している ← いま）

## 出典とライセンス

- 元データの出典表記は [docs/attribution.md](docs/attribution.md) を参照。元データ自体はこのリポジトリに含めません。
- コード：MIT License（[LICENSE](LICENSE)）
- 指標カードと文書：CC BY 4.0（[LICENSE-docs.md](LICENSE-docs.md)）
- 引用：[CITATION.cff](CITATION.cff)
