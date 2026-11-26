# 指標カタログのサイトと質問窓口

`site/` は、指標カードとデータセット定義を読んで表示する1ページのサイトです。右側の質問窓口（チャット）は、このサイトの中の資料だけを根拠にAIが答えます。

## しくみ

```
indicators/*.yaml ─┐
datasets/*.yaml  ──┤  chiiki-od catalog   ┌─ site/catalog.json       指標カード・データセット定義
docs/*.md        ──┼────────────────────→ │
codebooks/*.csv  ──┘                      └─ site/search_index.json  docs の節・列の見出し
                                                       │
                                     site/index.html が読み込んで表示・検索
                                                       │
                       質問 → 近い資料を検索（2文字組の一致）→ 資料だけを渡してAIが回答 → 根拠の資料を表示
```

- AIに渡すのは、質問に近い指標カード（最大3、表示中の指標は必ず含める）、データセット定義（最大2）、docs の節（最大3）、列の見出し（最大6）です。
- AIへの指示：資料にないことは「作成者の説明はありません」と答える、数値は資料にあるものしか書かない、根拠のIDを最後に書く。
- 回答の下に、根拠にした資料へのリンクが出ます。

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
