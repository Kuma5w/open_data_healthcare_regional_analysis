"""指標スクリプトが共通で使う入力の読み込み（実データと合成サンプルを同じ形で返す）。"""

from __future__ import annotations

import pandas as pd

from . import paths

POP_INT = ["pop_total", "pop_65plus", "pop_75plus", "pop_0_14", "age_15_19"]


def population(dataset_id: str, sample: bool = False, sex: str = "total") -> pd.DataFrame:
    """住民基本台帳の人口（変換後）。sex で男女計・男・女を選ぶ。level 列で集計行を区別できる。"""
    if sample:
        df = pd.read_csv(paths.FIXTURES / "population_jumin_sample.csv", dtype=str, encoding="utf-8-sig")
        for c in POP_INT:
            df[c] = pd.to_numeric(df[c]).astype("Int64")
    else:
        df = pd.read_parquet(paths.PROCESSED / f"{dataset_id}.parquet")
    return df[df["sex"] == sex].reset_index(drop=True)


WARD_COLS = ["od_ward_code", "pref_code", "koso_kuiki_code", "koso_kuiki_name", "w016", "w017", "w019", "w023"]


def bfr_wards(dataset_id: str = "bed_function_report_r7_ward", sample: bool = False) -> pd.DataFrame:
    """病床機能報告の病棟票（変換後）のうち、病床数の集計に使う列。"""
    if sample:
        df = pd.read_csv(paths.FIXTURES / "bfr_ward_sample.csv", dtype=str, encoding="utf-8-sig")
        for c in ("w019", "w023"):
            df[c] = pd.to_numeric(df[c]).astype("Int64")
        return df
    df = pd.read_parquet(paths.PROCESSED / f"{dataset_id}.parquet")
    return df[[c for c in WARD_COLS if c in df.columns]]
