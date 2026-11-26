# data/（Gitには入れない）

| フォルダ | 中身 | 作るコマンド |
|---|---|---|
| `raw/<dataset>/` | 公表元から取得した元データ | `chiiki-od fetch <dataset>` |
| `processed/` | Parquet に変換したデータ | `chiiki-od convert <dataset>` |
| `outputs/` | 指標の計算結果（CSV）と実行記録（JSON） | `chiiki-od run <indicator>` |

変換後の Parquet は、リポジトリの Releases に添付して配布する予定です（GitHubは100MiBを超えるファイルをリポジトリに置けないため）。取得・変換の記録は `manifests/` に残り、こちらはGitに入れます。
