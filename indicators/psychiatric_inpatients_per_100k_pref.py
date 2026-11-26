"""都道府県ごとの人口10万人あたり精神病床の在院患者数（630調査）

指標カード: indicators/psychiatric_inpatients_per_100k_pref.yaml
"""

from __future__ import annotations

import pandas as pd

from chiiki_od import seishin630 as s

PICK = {
    "inpatients": ("all", "inpatients"),
    "inpatients_medical_protection": ("all", "inpatients_medical_protection"),
    "inpatients_involuntary": ("all", "inpatients_involuntary"),
}


def load_inputs(sample: bool = False) -> dict[str, pd.DataFrame]:
    return {"facility": s.load_facility(sample=sample), "population": s.load_population(sample=sample)}


def compute(facility: pd.DataFrame, population: pd.DataFrame) -> tuple[pd.DataFrame, list[str]]:
    out, notes = s.prefecture_table(facility, population, PICK)
    out["inpatients_per_100k"] = s.rate(out["inpatients"], out["population"], 100_000, 1)
    return out, notes
