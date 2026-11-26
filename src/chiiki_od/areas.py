"""市区町村の値を構想区域にまとめる共通処理。"""

from __future__ import annotations

import pandas as pd

from . import codes, paths
from .jumin import UNITS


def koso_reference() -> pd.DataFrame:
    """reference/koso_kuiki.csv（市区町村・政令市の区 → 構想区域・二次医療圏）。"""
    return pd.read_csv(paths.REFERENCE / "koso_kuiki.csv", dtype=str)


def population_units(population: pd.DataFrame, sex: str = "total") -> pd.DataFrame:
    """人口表から、重複なく足し上げられる行（市区町村と政令市の区）だけを取り出す。"""
    p = population
    if "sex" in p.columns:
        p = p[p["sex"] == sex]
    if "level" in p.columns:
        p = p[p["level"].isin(UNITS)]
    return p


def to_koso(units: pd.DataFrame, value_cols: list[str], ref: pd.DataFrame | None = None) -> tuple[pd.DataFrame, list[str]]:
    """市区町村（政令市は区）単位の値を構想区域ごとに合計する。注記（対応しなかった行）も返す。"""
    ref = koso_reference() if ref is None else ref
    notes = []
    m = units.merge(
        ref[["municipality_code5", "pref_code", "koso_kuiki_code", "koso_kuiki_name"]],
        left_on="municipality_code", right_on="municipality_code5", how="left",
    )
    unmatched = m[m["koso_kuiki_code"].isna()]
    if len(unmatched):
        nonzero = unmatched[unmatched[value_cols].fillna(0).sum(axis=1) > 0]
        notes.append(
            f"構想区域の対応表にない市区町村 {len(unmatched)} 件（うち値が0でないもの {len(nonzero)} 件）は除外"
            + (f"：{', '.join(nonzero['municipality_code'].head(5))}" if len(nonzero) else "")
        )
    out = (
        m.dropna(subset=["koso_kuiki_code"])
        .groupby(["pref_code", "koso_kuiki_code", "koso_kuiki_name"], as_index=False)[value_cols]
        .sum()
    )
    return out, notes


# ---- 人口あたりの値（市区町村・構想区域） --------------------------------------
# 分子は「市区町村（政令市は区）ごとの件数」の表（列 code5 と件数の列）で受け取る。
# 政令市の区を市にまとめるか、構想区域にまとめるかは、ここで揃えて行う。

MUNICIPAL_LEVELS = ("municipality", "ward", "designated_city")


def safe_code5(value) -> str | None:
    """5桁・6桁のコードを5桁にする。読めないものは None。"""
    try:
        return codes.to_code5(value)
    except (TypeError, ValueError):
        return None


def municipality_population(
    population: pd.DataFrame, pop_col: str, ward_level: bool = False
) -> tuple[pd.DataFrame, list[str]]:
    """人口表から、市区町村ごとの人口を1行ずつ取り出す（列 code5・municipality_name・pop_col）。

    政令市は市単位にまとめる。市の合計行があればそれを使い、合計行がない市だけ区を足し上げる
    （homecare_offices_per_65plus と同じ扱い）。ward_level=True なら市の合計行を使わず区の行を使う。
    人口が0の行（北方領土の村など）は除く。
    """
    notes: list[str] = []
    p = population
    if "sex" in p.columns:
        p = p[p["sex"] == "total"]
    if "level" in p.columns:
        p = p[p["level"].isin(MUNICIPAL_LEVELS)]
    p = p[["municipality_code", "municipality_name", pop_col]].copy()
    p["code5"] = p["municipality_code"].map(safe_code5)
    p = p.dropna(subset=["code5"])
    p = p[~p["code5"].map(codes.is_prefecture_level)]
    is_ward = p["code5"].map(codes.is_designated_ward)
    is_city = p["code5"].isin(list(codes.designated_cities()))

    if ward_level:
        p = p[~is_city]
    else:
        cities_present = set(p.loc[is_city, "code5"])
        wards = p[is_ward].assign(city=lambda d: d["code5"].map(codes.ward_to_city))
        to_sum = wards[~wards["city"].isin(cities_present)]
        if len(to_sum):
            summed = (
                to_sum.groupby("city", as_index=False)[pop_col].sum()
                .rename(columns={"city": "code5"})
                .assign(municipality_name=lambda d: d["code5"].map(codes.designated_cities()))
            )
            notes.append(f"市の合計行がない政令市 {len(summed)} 市は区の人口を足し上げた")
            p = pd.concat([p[~is_ward], summed], ignore_index=True)
        else:
            p = p[~is_ward]

    zero = p[pop_col].fillna(0) == 0
    if zero.any():
        notes.append(f"{pop_col} が0の市区町村 {int(zero.sum())} 件（北方領土の村など）は除外")
        p = p[~zero]
    return p[["code5", "municipality_name", pop_col]].reset_index(drop=True), notes


def _rate(df: pd.DataFrame, num: str, den: str, scale: float, digits: int) -> pd.Series:
    d = df[den].astype("Float64")
    return (df[num].astype("Float64") / d.where(d > 0) * scale).round(digits)


def rate_by_municipality(
    counts: pd.DataFrame,
    population: pd.DataFrame,
    count_cols: list[str],
    pop_col: str,
    value_col: str,
    scale: float,
    digits: int,
    ward_level: bool = False,
) -> tuple[pd.DataFrame, list[str]]:
    """市区町村（政令市は区）ごとの件数を、市区町村（政令市は市）ごとの人口あたりの値にする。

    人口の表を基準に結合するので、件数が0の市区町村も0として残る。
    値は count_cols の先頭の列 ÷ pop_col × scale。
    """
    c = counts[["code5", *count_cols]].copy()
    if not ward_level:
        c["code5"] = c["code5"].map(codes.ward_to_city)
    c = c.groupby("code5")[count_cols].sum()

    pop, notes = municipality_population(population, pop_col, ward_level=ward_level)
    res = pop.merge(c, left_on="code5", right_index=True, how="left")
    for col in count_cols:
        res[col] = res[col].fillna(0).astype("Int64")
    if unmatched := sorted(set(c.index) - set(pop["code5"])):
        n = int(c.loc[unmatched, count_cols[0]].sum())
        notes.append(
            f"人口の表にない市区町村コード {len(unmatched)} 件（件数 {n}）は結果に含まれない"
            "（市町村合併や時点のずれの可能性）"
        )
    res[value_col] = _rate(res, count_cols[0], pop_col, scale, digits)
    total = res[[count_cols[0], pop_col]].sum()
    notes.append(f"全国計 {total[count_cols[0]] / total[pop_col] * scale:.{digits}f}（{len(res)} 市区町村）")
    out = res.rename(columns={"code5": "municipality_code5"})[
        ["municipality_code5", "municipality_name", *count_cols, pop_col, value_col]
    ]
    return out.sort_values("municipality_code5").reset_index(drop=True), notes


def rate_by_koso(
    counts: pd.DataFrame,
    population: pd.DataFrame,
    count_cols: list[str],
    pop_col: str,
    value_col: str,
    scale: float,
    digits: int,
    ref: pd.DataFrame | None = None,
) -> tuple[pd.DataFrame, list[str]]:
    """市区町村（政令市は区）ごとの件数を、構想区域ごとの人口あたりの値にする。

    件数も人口も reference/koso_kuiki.csv で構想区域に合計する。件数が0の区域も0として残る。
    """
    ref = koso_reference() if ref is None else ref
    c = counts[["code5", *count_cols]].rename(columns={"code5": "municipality_code"})
    c = c.groupby("municipality_code", as_index=False)[count_cols].sum()
    num, notes = to_koso(c, count_cols, ref)
    pop, pop_notes = to_koso(population_units(population), [pop_col], ref)
    notes += [f"人口：{n}" for n in pop_notes]

    names = ref.drop_duplicates("koso_kuiki_code").set_index("koso_kuiki_code")
    res = pop.merge(num[["koso_kuiki_code", *count_cols]], on="koso_kuiki_code", how="outer")
    if (n := int(res[pop_col].isna().sum())):
        notes.append(f"人口が対応しない構想区域 {n} 件")
    res["koso_kuiki_name"] = res["koso_kuiki_name"].fillna(res["koso_kuiki_code"].map(names["koso_kuiki_name"]))
    res["pref_code"] = res["pref_code"].fillna(res["koso_kuiki_code"].str[:2])
    for col in count_cols:
        res[col] = res[col].fillna(0).astype("Int64")
    res[value_col] = _rate(res, count_cols[0], pop_col, scale, digits)
    total = res[[count_cols[0], pop_col]].sum()
    notes.append(f"全国計 {total[count_cols[0]] / total[pop_col] * scale:.{digits}f}（{len(res)} 構想区域）")
    out = res[["pref_code", "koso_kuiki_code", "koso_kuiki_name", *count_cols, pop_col, value_col]]
    return out.sort_values("koso_kuiki_code").reset_index(drop=True), notes
