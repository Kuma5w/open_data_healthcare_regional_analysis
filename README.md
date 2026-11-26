# 地域医療構想 オープンデータ共有基盤

地域医療構想の分析に携わる研究者どうしで、オープンデータを使った**基本的な分析の考え方と方法を共有する**ためのリポジトリです。

データや生成AIへの慣れは人によって違います。そこで、指標ごとに「作成者がどんな意図でその指標を作ったのか」を**指標カード**に書き残し、計算はスクリプトで再現できるようにしています。サイトに置く解説チャットボットは、この指標カードを根拠に質問に答えます。

> 状態：v0.2。病床機能報告（令和7年度）の施設票・診療所票・様式2（月別）を変換できます。見本の指標は1つです。

## 3つの約束

1. **数値はスクリプトが作る。** AIや手作業で数値を作らない。チャットボットやボタン出力も、登録済みの指標スクリプトを呼ぶだけにする。
2. **指標には必ずカードを付ける。** 意図・分子と分母・なぜその分母か・注意点を書く。カードのない指標は共有しない。
3. **出典と加工を明記する。** 元データの取得元・時点・ハッシュ値を記録し、成果物には出典と「加工して作成」を書く。

## 構成

```
datasets/        データセット定義（取得元URL・時点・列名の対応・利用規約）
indicators/      指標カード（<id>.yaml）と計算スクリプト（<id>.py）を1対1で置く
reference/       共通対応表（政令市、構想区域、市町村合併）
codebooks/       変換後の列名と元の見出し・必須区分・欠損の件数の対応表
src/chiiki_od/   共通部品（市区町村コード、変換、実行、検証）
schemas/         指標カードとデータセット定義の形式（JSON Schema）
manifests/       取得・変換の記録（どのURLのどのファイルから作ったか）
site/            サイトとチャットボットが読む catalog.json
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

現時点では、人口データ（`population_65plus`）の専用パーサーが未実装のため、見本指標は実データでは最後まで動きません。人口データは作業手順の2番目で対応します。

### 手元に保存した公表ファイルから取り込む

公表元のファイル名のまま保存したフォルダを指定すると、ダウンロードせずに取り込めます（記録には公表元のURLとハッシュ値が残ります）。

```bash
chiiki-od fetch bed_function_report_r7_form2_monthly --from-dir ~/Downloads/R7_hosp
chiiki-od convert bed_function_report_r7_form2_monthly
```

病床機能報告の使い方と注意点（記号の扱い、秘匿、0の意味など）は [docs/datasets/bed_function_report.md](docs/datasets/bed_function_report.md) にあります。

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
2. データ3種（病床機能報告・介護事業所・人口）の変換と、見本の指標を3つ ← いまここ（病床機能報告は病棟票と様式2年間合計が未）
3. 指標カタログのサイトと解説チャットボット
4. ボタン出力（登録済み指標×地域×年度を選んで、表・地図・CSV・再現コードを出す）
5. 公開して、プルリクエストの受け付けを始める

## 出典とライセンス

- 元データの出典表記は [docs/attribution.md](docs/attribution.md) を参照。元データ自体はこのリポジトリに含めません。
- コード：MIT License（[LICENSE](LICENSE)）
- 指標カードと文書：CC BY 4.0（[LICENSE-docs.md](LICENSE-docs.md)）
- 引用：[CITATION.cff](CITATION.cff)
