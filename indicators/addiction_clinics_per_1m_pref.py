"""都道府県ごとの人口100万人あたり依存症の専門外来を設置している病院数（精神病床を有する病院、630調査）

指標カード: indicators/addiction_clinics_per_1m_pref.yaml
計算は chiiki_od.seishin630.specialty_clinics（6種類の専門外来で共通）。
"""

from __future__ import annotations

import pandas as pd

from chiiki_od import seishin630 as s


def load_inputs(sample: bool = False) -> dict[str, pd.DataFrame]:
    return {"clinical": s.load_clinical(sample=sample), "population": s.load_population(sample=sample)}


def compute(clinical: pd.DataFrame, population: pd.DataFrame) -> tuple[pd.DataFrame, list[str]]:
    return s.specialty_clinics(clinical, population, "addiction")
