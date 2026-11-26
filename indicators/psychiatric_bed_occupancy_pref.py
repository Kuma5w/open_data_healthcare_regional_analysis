"""都道府県ごとの精神病床の利用率（在院患者数÷許可精神病床数、630調査）

指標カード: indicators/psychiatric_bed_occupancy_pref.yaml
内訳は精神保健福祉法の区分（国立・都道府県立精神科病院等・指定病院・非指定病院）。
"""

from __future__ import annotations

import pandas as pd

from chiiki_od import seishin630 as s

KINDS = ["public", "designated", "nondesignated"]
PICK = {"beds_licensed": ("all", "beds_licensed"), "inpatients": ("all", "inpatients")}
for k in KINDS:
    PICK[f"beds_{k}"] = (k, "beds_licensed")
    PICK[f"inpatients_{k}"] = (k, "inpatients")


def load_inputs(sample: bool = False) -> dict[str, pd.DataFrame]:
    return {"facility": s.load_facility(sample=sample)}


def compute(facility: pd.DataFrame) -> tuple[pd.DataFrame, list[str]]:
    out, notes = s.prefecture_table(facility, None, PICK)
    out["occupancy_pct"] = s.rate(out["inpatients"], out["beds_licensed"], 100, 1)
    for k in KINDS:
        out[f"occupancy_{k}_pct"] = s.rate(out[f"inpatients_{k}"], out[f"beds_{k}"], 100, 1)
    if (n := int((out["occupancy_pct"] > 100).sum())):
        notes.append(f"利用率が100％を超える都道府県 {n}")
    return out, notes
