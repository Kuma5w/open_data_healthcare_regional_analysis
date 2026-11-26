"""都道府県ごとの人口100万人あたり精神科救急医療体制整備事業に参画する病院数（精神病床を有する病院、630調査）

指標カード: indicators/psy_emergency_hospitals_per_1m_pref.yaml
参画＝常時対応型・病院群輪番型・身体合併症対応施設・外来対応施設のいずれか（1病院1つの役割）。
"""

from __future__ import annotations

import pandas as pd

from chiiki_od import seishin630 as s

ROLES = ["psy_emergency_full_time", "psy_emergency_rotation", "psy_emergency_comorbidity", "psy_emergency_outpatient"]
OTHERS = ["psy_emergency_nonparticipant_responding", "psy_emergency_nonparticipant_not_responding"]


def load_inputs(sample: bool = False) -> dict[str, pd.DataFrame]:
    return {"clinical": s.load_clinical(sample=sample), "population": s.load_population(sample=sample)}


def compute(clinical: pd.DataFrame, population: pd.DataFrame) -> tuple[pd.DataFrame, list[str]]:
    pick = {"hospitals": ("all", "facilities")} | {c: ("all", c) for c in ROLES + OTHERS}
    out, notes = s.prefecture_table(clinical, population, pick)
    out["participating_hospitals"] = out[ROLES].sum(axis=1).astype("Int64")
    out["full_time_or_rotation"] = out[ROLES[:2]].sum(axis=1).astype("Int64")
    if (bad := out["hospitals"] - out[ROLES + OTHERS].sum(axis=1)).ne(0).any():
        notes.append(f"役割の内訳の合計が病院数と一致しない都道府県 {int(bad.ne(0).sum())}")
    out["participating_per_1m"] = s.rate(out["participating_hospitals"], out["population"], 1_000_000, 2)
    order = ["pref_code", "pref_name", "hospitals", *ROLES, *OTHERS, "participating_hospitals", "full_time_or_rotation",
             "population", "participating_per_1m"]
    return out[order], notes
