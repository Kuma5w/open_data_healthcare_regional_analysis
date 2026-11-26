# 指標カタログのサイトと質問窓口

`site/` は、指標カードとデータセット定義を読んで表示する1ページのサイトです。指標のページの「結果を見る」では、計算結果を表・グラフ・CSV・印刷用の1枚で出せます。右側の質問窓口（チャット）は、このサイトの中の資料だけを根拠にAIが答えます。

## しくみ

```
indicators/*.yaml ─┐
datasets/*.yaml  ──┤  chiiki-od catalog   ┌─ site/catalog.json       指標カード・データセット定義・結果の一覧
docs/*.md        ──┼────────────────────→ │
codebooks/*.csv  ──┘                      └─ site/search_index.json  docs の節・列の見出し

data/processed/*.parquet ── chiiki-od results ──→ site/results/<指標>.json / .csv  計算結果・要約・入力のハッシュ
（手元だけ。Gitに入れない）    （指標スクリプトを実行）     （Gitに入れる）
                                                       │
                                     site/index.html が読み込んで表示・検索
                                                       │
                       質問 → 近い資料を検索（2文字組の一致）→ 資料だけを渡してAIが回答 → 根拠の資料を表示
```

- AIに渡すのは、質問に近い指標カード（最大3、表示中の指標は必ず含める）、データセット定義（最大2）、docs の節（最大3）、列の見出し（最大6）です。
- AIへの指示：資料にないことは「作成者の説明はありません」と答える、数値は資料にあるものしか書かない、根拠のIDを最後に書く。
- 回答の下に、根拠にした資料へのリンクが出ます。

## 結果を見る（ボタン出力）

指標のページで地域（全国または都道府県）と並べ方を選ぶと、次のものが出ます。

- 全国計・都道府県計・中央値・地域の数
- 値の棒グラフ（全国を選ぶと都道府県ごとの計、都道府県を選ぶと構想区域・市区町村ごとの値）。縦線は全国計。60件を超えるときは上下25件ずつを描き、残りは表に出す
- 表と、CSVのダウンロード（見出しは日本語、UTF-8 BOM付き）。スクリプトの列名のままのCSVは `site/results/<指標>.csv`
- 印刷・PDF（チャットや操作部品を除いた1枚。計算の記録と出典を含む）
- 再現の手順（取得・変換・計算のコマンド、元データのSHA-256、公開CSVを pandas・R で読むコード）

選んだ地域と並べ方はURLに残ります（例：`#ind-homecare-offices-per-65plus?pref=43&sort=asc`）。そのURLを共有すれば、同じ表示を開けます。

### 数値はどこで作るか

サイトの中では新しい数値を計算しません。表の値は指標スクリプトの `compute` が、全国計・都道府県計・中央値・四分位は `src/chiiki_od/results.py` が作り、JSONに入れています。

- **計**：値のある行の分子と分母をそれぞれ合計し、`output.scale` を掛けた値（例：都道府県の事業所数の合計 ÷ 65歳以上人口の合計 × 10,000）
- **中央値・四分位**：地域ごとの値の分位点（pandas の `quantile`、線形補間）

質問窓口には、表示中の結果（全国計・要約と、表示中の表。60件を超えるときは並べ方の先頭30件と末尾30件）も根拠として渡します。AIには、表の値を引用してよいが、差や比などの新しい数値は計算しないよう指示しています。

### 結果を作り直す

元データはリポジトリに入れないため、CIでは結果を作れません。指標カードか計算スクリプトを変えたら、手元で作り直してコミットします。

```bash
chiiki-od results                      # output のある全指標
chiiki-od results recovery_bed_share_koso
```

`chiiki-od check`（CIでも実行）は、結果のファイルが指標カードの版・計算スクリプトのハッシュ値・列と食い違っていると注意を出します。サイトでも、その指標の結果の上に注意が出ます。合成サンプルの結果を `site/results/` に置くとエラーになります。

結果を出すには、指標カードに `output` 欄が必要です（[指標カードの書き方](indicator_card_guide.md)）。

## 手元で見る

```bash
chiiki-od catalog
python -m http.server 8000 -d site
# ブラウザで http://localhost:8000 を開く
```

## 公開（GitHub Pages）

`.github/workflows/pages.yml` が、main に変更が入るたびにサイトを作り直して公開します。使う前に一度だけ、リポジトリの Settings → Pages → Source を「GitHub Actions」にしてください。公開先は `https://kuma5w.github.io/open_data_healthcare_regional_analysis/` になります。

## 質問窓口の接続先

「接続の設定」で選びます。設定（APIキーを含む）は、そのブラウザの localStorage にだけ保存されます。

| 接続先 | 使える場所 | 設定 |
|---|---|---|
| Claude | claude.ai 上で開いたとき | 設定不要 |
| OpenAI互換API | どこでも | ベースURL・モデル名・APIキー（ローカルなら空欄） |

### ローカルのQwen（Ollama）を使う

1. Ollama でモデルを用意する（例：`ollama pull qwen3.8:27b`）。
2. Ollama に、サイトのアドレスからの接続を許可する（CORS）。Ollama を起動する前に環境変数を設定する。
   - Windows（PowerShell）：`setx OLLAMA_ORIGINS "https://kuma5w.github.io,http://localhost:8000"` を実行してから Ollama を再起動
   - macOS・Linux：`OLLAMA_ORIGINS="https://kuma5w.github.io,http://localhost:8000" ollama serve`
3. サイトの「接続の設定」で「OpenAI互換API」を選び、ベースURL `http://localhost:11434/v1`、モデル名（例：`qwen3.8:27b`）を入れて保存する。

この方法では、AIは各自のPCで動きます。公開サイトを見ている他の人のブラウザからは、その人自身のPCのOllamaに接続します（あなたのPCには接続しません）。全員で1つのAIを共有するには、APIキーを隠す中継（Cloudflare Workers など）が必要です。

### 注意

- OpenAI互換APIのキーをブラウザに入れると、そのブラウザを使う人は誰でもキーを使えます。共用のPCでは入れないでください。
- 無料枠のAPIでは、送った質問がサービスの改善に使われる場合があります。質問に個人情報を書かないでください。
