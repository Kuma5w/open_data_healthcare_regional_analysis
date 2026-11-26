"""在宅医療等連携機能：毎年追える11項目の該当数の推移（構想区域別、FY2020〜2024）

指標カード: indicators/zaitaku_renkei_trend_koso.yaml
判定の方法は chiiki_od.psc_trend（D.S.氏の方法。P・S・C判定の11項目を各年度の病床機能報告で判定する）。
"""

from __future__ import annotations

import pandas as pd

from chiiki_od import areas, psc_trend


def load_inputs(sample: bool = False) -> dict[str, pd.DataFrame]:
    return psc_trend.load_inputs(sample=sample)


def compute(trend_wards, trend_form2, trend_secret, trend_annual, item_map) -> tuple[pd.DataFrame, list[str]]:
    years, cal, notes = psc_trend.evaluate(trend_wards, trend_form2, trend_secret, trend_annual, item_map)
    link = psc_trend.link_to_r7(years)
    notes += psc_trend.trend_notes(years, link, cal)
    ref = areas.koso_reference()
    years, n = psc_trend.assign_koso(years, link, ref)
    return psc_trend.koso_trend(years, ref), notes + n
