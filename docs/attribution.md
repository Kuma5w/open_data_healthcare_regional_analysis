# 出典表記

このリポジトリは元データを含みません。各データの取得元と利用規約は `datasets/<id>.yaml` の `source_page` と `license` に書いてあります。成果物（表・図・論文・スライド）には、そこに書いた出典表記を付けてください。`chiiki-od run` が出力する実行記録（`data/outputs/<指標>.json`）の `attribution` と、サイトの「結果を見る」の「計算の記録と出典」（印刷にも入ります）にも同じ文が入ります。

## 厚生労働省のデータ

厚生労働省ホームページの利用規約（https://www.mhlw.go.jp/chosakuken/index.html）に従います。

- 出典を記載する。
- 編集・加工して利用する場合は、出典とは別に、編集・加工したことを記載する。
- 加工した情報を、国が作成したかのような形で公表・利用しない。

記載例：

> 出典：厚生労働省「令和7年度病床機能報告公表データ」（https://www.mhlw.go.jp/stf/seisakunitsuite/bunya/open_data_00020.html）を加工して作成

### 介護サービス情報公表システムのオープンデータ

上に加えて、介護サービス情報公表システムから抽出したデータであることを表示します。また、厚生労働省は利用状況を把握するため、データを利用した場合にフォームから連絡するよう依頼しています（https://www.mhlw.go.jp/stf/kaigo-kouhyou_opendata.html）。

## 総務省のデータ

住民基本台帳に基づく人口などは、総務省の利用規約に従います（URLは `datasets/population_jumin_r7.yaml`・`population_jumin_r8.yaml` に記載。要確認）。
