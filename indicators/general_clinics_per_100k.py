"""人口10万人あたり一般診療所数（市区町村別）

指標カード: indicators/general_clinics_per_100k.yaml
意図・分母を選んだ理由・注意点はカードに書く。このファイルには計算だけを書く。
市区町村・構想区域へのまとめ方と人口の扱いは chiiki_od.iryo_shisetsu と chiiki_od.areas の共通処理による。
"""

from __future__ import annotations

import pandas as pd

from chiiki_od import iryo_shisetsu

COUNTS = ["general_clinics", "clinics_with_beds"]  # 先頭が分子。残りは内訳（再掲）の列


def load_inputs(sample: bool = False) -> dict[str, pd.DataFrame]:
    return {
        "facilities": iryo_shisetsu.load_facilities(sample=sample),
        "population": iryo_shisetsu.load_population(sample=sample),
    }


def compute(
    facilities: pd.DataFrame, population: pd.DataFrame, ward_level: bool = False
) -> tuple[pd.DataFrame, list[str]]:
    return iryo_shisetsu.per_population(
        facilities, population, COUNTS, "general_clinics_per_100k", "municipality", 1, ward_level=ward_level
    )
