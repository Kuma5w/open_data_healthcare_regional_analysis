"""介護サービス情報公表システムの事業所一覧（kaigo_jigyosho_<サービスコード>）の共通処理。

サービスごとに別のファイル・別のデータセットになっている（列は同じ24列）。
指標スクリプトはここで事業所を読み、市区町村（政令市は区）ごとに数えてから、
chiiki_od.areas で人口あたりの値にする。
"""

from __future__ import annotations

from collections.abc import Callable

import pandas as pd

from . import areas, codes, inputs, paths
from .convert import read_with_spec

# サービスコード → 「サービスの種類」列の値
SERVICES = {
    "110": "訪問介護",
    "130": "訪問看護",
    "140": "訪問リハビリテーション",
    "150": "通所介護",
    "160": "通所リハビリテーション",
    "210": "短期入所生活介護",
    "780": "地域密着型通所介護",
}

# 事業所番号の3桁目（付番の区分）。病院・診療所・老健がみなし指定を受けると、
# 医療機関等のコードがそのまま事業所番号になる（datasets/kaigo_jigyosho_*.yaml の notes）
MEDICAL = ("1", "3")  # 医療機関（医科・歯科）
ROKEN = ("5", "B")  # 介護老人保健施設・介護医療院（Bは事業所名との照合による）

POPULATION = "population_jumin_r8"  # 事業所の時点（2026年6月末）に近い令和8年1月1日
SAMPLE = paths.FIXTURES / "kaigo_jigyosho_services_sample.csv"


def dataset_id(service_code: str) -> str:
    return f"kaigo_jigyosho_{service_code}"


def load_offices(service_codes: list[str], sample: bool = False) -> pd.DataFrame:
    """事業所一覧を読み、列 service_code（サービスコード）を足して縦につなぐ。"""
    frames = []
    for code in service_codes:
        if sample:
            df = read_with_spec(dataset_id(code), SAMPLE)
            df = df[df["service_type"] == SERVICES[code]]
        else:
            df = pd.read_parquet(paths.PROCESSED / f"{dataset_id(code)}.parquet")
        frames.append(df.assign(service_code=code))
    return pd.concat(frames, ignore_index=True)


def load_population(sample: bool = False) -> pd.DataFrame:
    return inputs.population(POPULATION, sample=sample)


def numbering(offices: pd.DataFrame) -> pd.Series:
    """事業所番号の3桁目（付番の区分）。"""
    return offices["office_number"].fillna("").str[2]


Breakdown = dict[str, Callable[[pd.DataFrame], pd.Series]]

BY_PROVIDER: Breakdown = {
    "offices_medical": lambda d: numbering(d).isin(MEDICAL),
    "offices_roken": lambda d: numbering(d).isin(ROKEN),
}


def count_offices(offices: pd.DataFrame, breakdown: Breakdown | None = None) -> tuple[pd.DataFrame, list[str]]:
    """事業所を市区町村（政令市は区）ごとに数える。列 code5・offices と内訳の列を返す。

    - コードが読めない行、都道府県コード（下3桁000）の行は除く
    - 同じサービスで事業所番号が重複する行は1件にする（本体とサテライトの例）。
      別のサービスで同じ事業所番号の行は、別々の指定なので両方数える
    """
    notes: list[str] = []
    o = offices.copy()
    o["code5"] = o["municipality_code"].map(areas.safe_code5)
    if (n := int(o["code5"].isna().sum())):
        notes.append(f"コードが読めない事業所 {n} 件を除外")
    o = o.dropna(subset=["code5"])

    pref_level = o["code5"].map(codes.is_prefecture_level)
    if (n := int(pref_level.sum())):
        notes.append(f"都道府県コード（下3桁000）の事業所 {n} 件は市区町村に割り当てられないため除外")
    o = o[~pref_level]

    dup = o.duplicated(["service_code", "office_number"])
    if dup.any():
        notes.append(f"同じサービスで事業所番号が重複する {int(dup.sum())} 行を除外")
    o = o[~dup]
    shared = o[o.duplicated("office_number", keep=False)]
    if len(shared):
        notes.append(
            f"別のサービスで同じ事業所番号の事業所 {shared['office_number'].nunique()} 件は、それぞれのサービスで数えた"
        )

    o["offices"] = 1
    cols = ["offices"]
    for name, rule in (breakdown or {}).items():
        o[name] = rule(o).astype(int)
        cols.append(name)
    counts = o.groupby("code5", as_index=False)[cols].sum()
    by_service = o["service_code"].value_counts().sort_index()
    notes.append("数えた事業所：" + "、".join(f"{SERVICES[k]} {v:,}" for k, v in by_service.items()))
    return counts, notes


def offices_per_population(
    offices: pd.DataFrame,
    population: pd.DataFrame,
    value_col: str,
    pop_col: str = "pop_65plus",
    scale: int = 10_000,
    digits: int = 3,
    breakdown: Breakdown | None = None,
    ward_level: bool = False,
) -> tuple[pd.DataFrame, list[str]]:
    """市区町村（政令市は市。ward_level=True なら区）ごとの、人口あたり事業所数。"""
    counts, notes = count_offices(offices, breakdown)
    count_cols = [c for c in counts.columns if c != "code5"]
    res, rate_notes = areas.rate_by_municipality(
        counts, population, count_cols, pop_col, value_col, scale, digits, ward_level=ward_level
    )
    zero = int((res["offices"] == 0).sum())
    return res, notes + rate_notes + [f"事業所が0の市区町村 {zero} 件"]
