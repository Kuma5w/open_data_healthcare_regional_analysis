"""都道府県ごとの人口10万人あたり精神科医師数（常勤、精神病床を有する病院、630調査）

指標カード: indicators/psychiatrists_per_100k_pref.yaml
"""

from __future__ import annotations

import pandas as pd

from chiiki_od import seishin630 as s

PICK = {
    "hospitals": ("all", "facilities"),
    "psychiatrists_ft": ("all", "psychiatrists_ft"),
    "psychiatrists_pt": ("all", "psychiatrists_pt"),
    "designated_physicians_ft": ("all", "designated_physicians_ft"),
    "designated_physicians_pt": ("all", "designated_physicians_pt"),
}


def load_inputs(sample: bool = False) -> dict[str, pd.DataFrame]:
    return {"facility": s.load_facility(sample=sample), "population": s.load_population(sample=sample)}


def compute(facility: pd.DataFrame, population: pd.DataFrame) -> tuple[pd.DataFrame, list[str]]:
    out, notes = s.prefecture_table(facility, population, PICK)
    out["psychiatrists_ft_per_100k"] = s.rate(out["psychiatrists_ft"], out["population"], 100_000, 2)
    out["designated_physicians_ft_per_100k"] = s.rate(out["designated_physicians_ft"], out["population"], 100_000, 2)
    return out, notes
