"""都道府県ごとの医療保護入院の1年時点の退院率（2024年6月に入院した患者、630調査）

指標カード: indicators/medical_protection_discharge_1y_pref.yaml
退院した人数は、公表されている退院率×入院した患者数（どの都道府県でも整数になる）。
"""

from __future__ import annotations

import pandas as pd

from chiiki_od import codes
from chiiki_od import seishin630 as s

PERIODS = ["3m", "6m", "1y"]


def load_inputs(sample: bool = False) -> dict[str, pd.DataFrame]:
    return {"outcome": s.load_outcome(sample=sample)}


def compute(outcome: pd.DataFrame) -> tuple[pd.DataFrame, list[str]]:
    notes = []
    o = outcome[outcome["level"] == "prefecture"].sort_values("area_code")
    out = pd.DataFrame({"pref_code": o["area_code"].to_numpy()})
    out["pref_name"] = out["pref_code"].map(codes.PREFECTURES)
    out["admitted"] = o["admitted"].round().astype("Int64").to_numpy()
    for p in PERIODS:
        x = o[f"discharge_rate_{p}"].to_numpy() * o["admitted"].to_numpy()
        if (abs(x - x.round()) > 1e-6).any():
            notes.append(f"退院率×患者数が整数にならない都道府県がある（{p}。四捨五入した）")
        out[f"discharged_{p}"] = pd.array(x.round(), dtype="Int64")
    for p in PERIODS:
        out[f"discharge_rate_{p}_pct"] = s.rate(out[f"discharged_{p}"], out["admitted"], 100, 1)
    out["support_referral_pct"] = (o["support_referral_rate"].astype("Float64") * 100).round(1).to_numpy()
    if (n := int((out["admitted"] < 50).sum())):
        notes.append(f"入院した患者が50人未満の都道府県 {n}（率が大きく動きやすい）")
    return out, notes
