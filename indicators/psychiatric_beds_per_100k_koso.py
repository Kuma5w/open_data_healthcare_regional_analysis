"""構想区域ごとの人口10万人あたり精神病床数（医療施設調査）

指標カード: indicators/psychiatric_beds_per_100k_koso.yaml
意図・分母を選んだ理由・注意点はカードに書く。このファイルには計算だけを書く。
市区町村の値を構想区域にまとめる方法と人口の扱いは chiiki_od.iryo_shisetsu と chiiki_od.areas の共通処理による。
"""

from __future__ import annotations

import pandas as pd

from chiiki_od import iryo_shisetsu

COUNTS = ["beds_psychiatric", "psychiatric_hospitals"]  # 先頭が分子。精神科病院数は目安の列


def load_inputs(sample: bool = False) -> dict[str, pd.DataFrame]:
    return {
        "facilities": iryo_shisetsu.load_facilities(sample=sample),
        "population": iryo_shisetsu.load_population(sample=sample),
    }


def compute(facilities: pd.DataFrame, population: pd.DataFrame) -> tuple[pd.DataFrame, list[str]]:
    return iryo_shisetsu.per_population(facilities, population, COUNTS, "beds_psychiatric_per_100k", "koso_kuiki", 1,
                                        zero_word="精神病床")
