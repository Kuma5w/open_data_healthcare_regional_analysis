"""市区町村の値を構想区域にまとめる共通処理。"""

from __future__ import annotations

import pandas as pd

from . import paths
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
