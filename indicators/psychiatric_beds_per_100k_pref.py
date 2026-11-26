"""都道府県ごとの人口10万人あたり精神病床数（630調査）

指標カード: indicators/psychiatric_beds_per_100k_pref.yaml
意図・分母を選んだ理由・注意点はカードに書く。このファイルには計算だけを書く。
"""

from __future__ import annotations

import pandas as pd

from chiiki_od import seishin630 as s

PICK = {
    "hospitals": ("all", "facilities"),
    "beds_licensed": ("all", "beds_licensed"),
    "beds_public": ("public", "beds_licensed"),
    "beds_designated_hosp": ("designated", "beds_licensed"),
    "beds_nondesignated_hosp": ("nondesignated", "beds_licensed"),
}


def load_inputs(sample: bool = False) -> dict[str, pd.DataFrame]:
    return {"facility": s.load_facility(sample=sample), "population": s.load_population(sample=sample)}


def compute(facility: pd.DataFrame, population: pd.DataFrame) -> tuple[pd.DataFrame, list[str]]:
    out, notes = s.prefecture_table(facility, population, PICK)
    out["beds_per_100k"] = s.rate(out["beds_licensed"], out["population"], 100_000, 1)
    return out, notes
