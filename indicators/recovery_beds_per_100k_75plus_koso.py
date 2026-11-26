"""構想区域ごとの75歳以上人口10万人あたり回復期病床数（病床機能報告・令和7年度）

指標カード: indicators/recovery_beds_per_100k_75plus_koso.yaml
意図・分母を選んだ理由・注意点はカードに書く。このファイルには計算だけを書く。
"""

from __future__ import annotations

import pandas as pd

from chiiki_od import areas, inputs
from chiiki_od.bfr import beds_by_koso_function

POPULATION = "population_jumin_r7"  # 病床機能報告の時点（2025年7月1日）に近い令和7年1月1日
SCALE = 100_000


def load_inputs(sample: bool = False) -> dict[str, pd.DataFrame]:
    return {
        "wards": inputs.bfr_wards(sample=sample),
        "population": inputs.population(POPULATION, sample=sample),
    }


def compute(wards: pd.DataFrame, population: pd.DataFrame) -> tuple[pd.DataFrame, list[str]]:
    beds, notes = beds_by_koso_function(wards)
    pop, pop_notes = areas.to_koso(areas.population_units(population), ["pop_75plus"])
    notes += pop_notes

    res = beds[["pref_code", "koso_kuiki_code", "koso_kuiki_name", "beds_recovery"]].merge(
        pop[["koso_kuiki_code", "pop_75plus"]], on="koso_kuiki_code", how="outer"
    )
    if (n := int(res["pop_75plus"].isna().sum())):
        notes.append(f"人口が対応しない構想区域 {n} 件")
    no_beds = res["beds_recovery"].isna()
    if no_beds.any():
        notes.append(f"病棟票に病棟がない構想区域 {int(no_beds.sum())} 件は回復期病床0とした")
        res["koso_kuiki_name"] = res["koso_kuiki_name"].fillna(
            res["koso_kuiki_code"].map(areas.koso_reference().drop_duplicates("koso_kuiki_code")
                                       .set_index("koso_kuiki_code")["koso_kuiki_name"])
        )
    res["beds_recovery"] = res["beds_recovery"].fillna(0).astype("Int64")
    pop75 = res["pop_75plus"].astype("Float64")
    res["recovery_beds_per_100k_75plus"] = (res["beds_recovery"] / pop75.where(pop75 > 0) * SCALE).round(1)
    total = res[["beds_recovery", "pop_75plus"]].sum()
    notes.append(f"全体 {total['beds_recovery'] / total['pop_75plus'] * SCALE:.1f}（75歳以上人口10万人あたり）")
    res["pref_code"] = res["pref_code"].fillna(res["koso_kuiki_code"].str[:2])
    return res.sort_values("koso_kuiki_code").reset_index(drop=True), notes
