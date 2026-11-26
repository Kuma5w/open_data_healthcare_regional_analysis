# 地域医療構想 オープンデータ共有基盤

地域医療構想の分析に携わる研究者どうしで、オープンデータを使った**基本的な分析の考え方と方法を共有する**ためのリポジトリです。

データや生成AIへの慣れは人によって違います。そこで、指標ごとに「作成者がどんな意図でその指標を作ったのか」を**指標カード**に書き残し、計算はスクリプトで再現できるようにしています。サイトに置く解説チャットボットは、この指標カードを根拠に質問に答えます。

サイト：https://kuma5w.github.io/open_data_healthcare_regional_analysis/

> 状態：v0.5。病床機能報告（令和7年度）の全5表と、住民基本台帳の年齢階級別人口（令和7年・令和8年）を変換できます。見本の指標は3つで、サイトの「結果を見る」から地域を選んで表・グラフ・CSVを出せます。

## 見本の指標

| 指標 | 単位 | 使うデータ |
|---|---|---|
| [65歳以上人口1万人あたり訪問介護事業所数](indicators/homecare_offices_per_65plus.yaml) | 市区町村 | 介護サービス事業所（訪問介護）、住民基本台帳人口（令和8年） |
| [構想区域ごとの回復期病床の割合](indicators/recovery_bed_share_koso.yaml) | 構想区域 | 病床機能報告 病棟票（令和7年度） |
| [構想区域ごとの75歳以上人口10万人あたり回復期病床数](indicators/recovery_beds_per_100k_75plus_koso.yaml) | 構想区域 | 病床機能報告 病棟票、住民基本台帳人口（令和7年） |

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
site/            指標カタログのサイトと質問窓口（index.html と、catalog・results コマンドで作る JSON・CSV）
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

データセットごとの使い方と注意点は docs/datasets/ にあります（[病床機能報告](docs/datasets/bed_function_report.md)、[住民基本台帳人口](docs/datasets/population_jumin.md)）。

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
2. データ3種（病床機能報告・介護事業所・人口）の変換と、見本の指標を3つ （済）
3. 指標カタログのサイトと解説チャットボット（済。[docs/site.md](docs/site.md)）
4. ボタン出力：段階1（指標×地域を選んで、表・グラフ・CSV・印刷・再現の手順を出す）は済。段階2で地図と、質問窓口からの地域の指定 ← いまここ
5. 公開して、プルリクエストの受け付けを始める

## 出典とライセンス

- 元データの出典表記は [docs/attribution.md](docs/attribution.md) を参照。元データ自体はこのリポジトリに含めません。
- コード：MIT License（[LICENSE](LICENSE)）
- 指標カードと文書：CC BY 4.0（[LICENSE-docs.md](LICENSE-docs.md)）
- 引用：[CITATION.cff](CITATION.cff)
