"""65歳以上人口1万人あたり短期入所生活介護事業所数（市区町村別）

指標カード: indicators/short_stay_offices_per_65plus.yaml
意図・分母を選んだ理由・注意点はカードに書く。このファイルには計算だけを書く。
数え方（重複の除き方、政令市のまとめ方、人口の扱い）は chiiki_od.kaigo と chiiki_od.areas の共通処理による。
"""

from __future__ import annotations

import pandas as pd

from chiiki_od import kaigo

SERVICES = ["210"]
BREAKDOWN = None


def load_inputs(sample: bool = False) -> dict[str, pd.DataFrame]:
    return {
        "offices": kaigo.load_offices(SERVICES, sample=sample),
        "population": kaigo.load_population(sample=sample),
    }


def compute(
    offices: pd.DataFrame, population: pd.DataFrame, ward_level: bool = False
) -> tuple[pd.DataFrame, list[str]]:
    return kaigo.offices_per_population(
        offices, population, "offices_per_10k_65plus", breakdown=BREAKDOWN, ward_level=ward_level
    )
