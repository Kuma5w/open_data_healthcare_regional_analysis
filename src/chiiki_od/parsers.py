"""汎用の読み込み（1行見出しの表）で足りないデータの専用パーサー。

datasets/<id>.yaml に `parser: <名前>` と書くと、変換時にここの関数が呼ばれる。
関数は (DataFrame, report) を返す。DataFrame の列は datasets/<id>.yaml の columns の name に合わせる。
"""

from __future__ import annotations

import pandas as pd


def parse_population_jumin_age(ds: dict) -> tuple[pd.DataFrame, dict]:
    """住民基本台帳 年齢階級別人口（市区町村別）→ 1行＝1市区町村の表。

    未実装。実ファイルの表構成（見出しが何行目か、年齢階級の列、政令市の合計行の扱い）を
    確認してから実装する。返す列: municipality_code（5桁）, municipality_name,
    pop_total, pop_65plus, as_of
    """
    raise NotImplementedError(
        "population_65plus の専用パーサーは未実装です。"
        "総務省のExcelの表構成を確認して src/chiiki_od/parsers.py に実装してください。"
        "それまでは `chiiki-od run <指標> --sample` でサンプルデータを使って試せます。"
    )


PARSERS = {
    "population_jumin_age": parse_population_jumin_age,
}
