"""都道府県ごとの措置入院受入可能病床の利用状況（措置入院患者数÷措置入院受入可能病床数、630調査）

指標カード: indicators/involuntary_bed_use_pref.yaml
"""

from __future__ import annotations

import pandas as pd

from chiiki_od import seishin630 as s

PICK = {
    "beds_involuntary_capable": ("all", "beds_involuntary_capable"),
    "inpatients_involuntary": ("all", "inpatients_involuntary"),
    "beds_involuntary_capable_public": ("public", "beds_involuntary_capable"),
    "inpatients_involuntary_public": ("public", "inpatients_involuntary"),
    "beds_designated": ("designated", "beds_designated"),
    "inpatients_involuntary_designated": ("designated", "inpatients_involuntary"),
    "inpatients_involuntary_nondesignated": ("nondesignated", "inpatients_involuntary"),
}


def load_inputs(sample: bool = False) -> dict[str, pd.DataFrame]:
    return {"facility": s.load_facility(sample=sample)}


def compute(facility: pd.DataFrame) -> tuple[pd.DataFrame, list[str]]:
    out, notes = s.prefecture_table(facility, None, PICK)
    out["involuntary_use_pct"] = s.rate(out["inpatients_involuntary"], out["beds_involuntary_capable"], 100, 1)
    out["involuntary_use_public_pct"] = s.rate(out["inpatients_involuntary_public"], out["beds_involuntary_capable_public"], 100, 1)
    out["involuntary_use_designated_pct"] = s.rate(out["inpatients_involuntary_designated"], out["beds_designated"], 100, 1)
    n = int(out["inpatients_involuntary_nondesignated"].fillna(0).sum())
    if n:
        notes.append(f"非指定病院（措置入院受入可能病床なし）の措置入院患者 {n}人（全体の値には含む）")
    return out, notes
