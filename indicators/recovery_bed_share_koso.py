"""構想区域ごとの回復期病床の割合（病床機能報告・令和7年度）

指標カード: indicators/recovery_bed_share_koso.yaml
意図・分母を選んだ理由・注意点はカードに書く。このファイルには計算だけを書く。
"""

from __future__ import annotations

import pandas as pd

from chiiki_od import inputs
from chiiki_od.bfr import beds_by_koso_function


def load_inputs(sample: bool = False) -> dict[str, pd.DataFrame]:
    return {"wards": inputs.bfr_wards(sample=sample)}


def compute(wards: pd.DataFrame) -> tuple[pd.DataFrame, list[str]]:
    t, notes = beds_by_koso_function(wards)
    active = t["beds_active"].astype("Float64")
    t["recovery_share_pct"] = (t["beds_recovery"] / active.where(active > 0) * 100).round(1)
    total = t[["beds_recovery", "beds_active"]].sum()
    notes.append(
        f"全体の回復期の割合 {total['beds_recovery'] / total['beds_active'] * 100:.1f}%"
        f"（回復期 {int(total['beds_recovery']):,}床／休棟を除く {int(total['beds_active']):,}床）"
    )
    cols = ["pref_code", "koso_kuiki_code", "koso_kuiki_name", "beds_high_acute", "beds_acute",
            "beds_recovery", "beds_chronic", "beds_active", "beds_closed", "recovery_share_pct"]
    return t[cols].sort_values("koso_kuiki_code").reset_index(drop=True), notes
