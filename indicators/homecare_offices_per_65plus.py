"""65歳以上人口1万人あたり訪問介護事業所数（市区町村別）

指標カード: indicators/homecare_offices_per_65plus.yaml
意図・分母を選んだ理由・注意点はカードに書く。このファイルには計算だけを書く。
"""

from __future__ import annotations

import pandas as pd

from chiiki_od import codes, inputs, paths
from chiiki_od.convert import read_with_spec

SCALE = 10_000


def _safe_code5(value) -> str | None:
    try:
        return codes.to_code5(value)
    except (TypeError, ValueError):
        return None


POPULATION = "population_jumin_r8"  # 事業所の時点（2026年6月末）に近い令和8年1月1日


def load_inputs(sample: bool = False) -> dict[str, pd.DataFrame]:
    pop = inputs.population(POPULATION, sample=sample)
    # 郡・島しょの合計行と全国は除く（政令市の合計と区の扱いは compute で決める）
    pop = pop[~pop["level"].isin(["county", "islands", "national"])]
    if sample:
        offices = read_with_spec("kaigo_jigyosho_110", paths.FIXTURES / "kaigo_jigyosho_110_sample.csv")
    else:
        offices = pd.read_parquet(paths.PROCESSED / "kaigo_jigyosho_110.parquet")
    return {"offices": offices, "population": pop}


def compute(
    offices: pd.DataFrame, population: pd.DataFrame, ward_level: bool = False
) -> tuple[pd.DataFrame, list[str]]:
    notes: list[str] = []

    # 1. 分子：事業所を市区町村ごとに数える -----------------------------------
    o = offices[["municipality_code", "office_number"]].copy()
    o["code5"] = o["municipality_code"].map(_safe_code5)
    if (n := int(o["code5"].isna().sum())):
        notes.append(f"コードが読めない事業所 {n} 件を除外")
    o = o.dropna(subset=["code5"])

    pref_level = o["code5"].map(codes.is_prefecture_level)
    if (n := int(pref_level.sum())):
        notes.append(f"都道府県コード（下3桁000）の事業所 {n} 件は市区町村に割り当てられないため除外")
    o = o[~pref_level]

    if (n := int(o.duplicated("office_number").sum())):
        notes.append(f"事業所番号が重複する {n} 行を除外")
    o = o.drop_duplicates("office_number")

    if not ward_level:
        o["code5"] = o["code5"].map(codes.ward_to_city)
    counts = o.groupby("code5").size().rename("offices")

    # 2. 分母：65歳以上人口（政令市の二重計上を防ぐ） ---------------------------
    p = population[["municipality_code", "municipality_name", "pop_65plus"]].copy()
    p["code5"] = p["municipality_code"].map(_safe_code5)
    p = p.dropna(subset=["code5"])
    p = p[~p["code5"].map(codes.is_prefecture_level)]
    is_ward = p["code5"].map(codes.is_designated_ward)
    is_city = p["code5"].isin(list(codes.designated_cities()))

    if ward_level:
        p = p[~is_city]  # 市の合計行を捨て、区の行を使う
    else:
        # 市の合計行があればそれを使い、区の行は捨てる。合計行がない市だけ区を足し上げる
        cities_present = set(p.loc[is_city, "code5"])
        wards = p[is_ward].assign(city=lambda d: d["code5"].map(codes.ward_to_city))
        to_sum = wards[~wards["city"].isin(cities_present)]
        if len(to_sum):
            summed = (
                to_sum.groupby("city", as_index=False)["pop_65plus"].sum()
                .rename(columns={"city": "code5"})
                .assign(municipality_name=lambda d: d["code5"].map(codes.designated_cities()))
            )
            notes.append(f"市の合計行がない政令市 {len(summed)} 市は区の人口を足し上げた")
            p = pd.concat([p[~is_ward], summed], ignore_index=True)
        else:
            p = p[~is_ward]

    # 3. 結合：人口の表を基準にする（事業所が0の市区町村を落とさない） ------------
    res = p.merge(counts, left_on="code5", right_index=True, how="left")
    res["offices"] = res["offices"].fillna(0).astype("Int64")
    if (unmatched := sorted(set(counts.index) - set(p["code5"]))):
        n_off = int(counts.loc[unmatched].sum())
        notes.append(
            f"人口の表にない市区町村コード {len(unmatched)} 件（事業所 {n_off} 件）は結果に含まれない"
            "（市町村合併や時点のずれの可能性）"
        )

    pop = res["pop_65plus"].astype("Float64")
    res["offices_per_10k_65plus"] = (res["offices"] / pop.where(pop > 0) * SCALE).round(3)
    out = res.rename(columns={"code5": "municipality_code5"})[
        ["municipality_code5", "municipality_name", "offices", "pop_65plus", "offices_per_10k_65plus"]
    ]
    return out.sort_values("municipality_code5").reset_index(drop=True), notes
