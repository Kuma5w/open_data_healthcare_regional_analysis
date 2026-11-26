"""在宅医療等連携機能：毎年追える11項目の該当数の推移（病院別、FY2020〜2024）

指標カード: indicators/zaitaku_renkei_trend_hospital.yaml
判定の方法は chiiki_od.psc_trend。病院の番号と伏せた名前は、P・S・C判定の病院別の指標
（zaitaku_renkei_psc_hospital）と同じ（令和7年度の18項目の判定から作る）。病院名と医療機関コードは載せない。
"""

from __future__ import annotations

import pandas as pd

from chiiki_od import psc_trend, zaitaku_psc


def load_inputs(sample: bool = False) -> dict[str, pd.DataFrame]:
    return psc_trend.load_inputs(sample=sample) | zaitaku_psc.load_inputs(sample=sample)


def compute(trend_wards, trend_form2, trend_secret, trend_annual, item_map,
            facility, wards, form2, outpatient, filings) -> tuple[pd.DataFrame, list[str]]:
    years, cal, notes = psc_trend.evaluate(trend_wards, trend_form2, trend_secret, trend_annual, item_map)
    link = psc_trend.link_to_r7(years)
    notes += psc_trend.trend_notes(years, link, cal)
    r, _ = zaitaku_psc.evaluate(facility, wards, form2, outpatient, filings)
    ids = pd.concat([r[["od_facility_code"]], zaitaku_psc.mask_ids(r)], axis=1)
    if (n := int((~link["r7_code"].dropna().isin(ids["od_facility_code"])).sum())):
        notes.append(f"令和7年度のP・S・C判定の対象にない病院につながった {n} 行は除外")
    return psc_trend.hospital_trend(years, link, ids), notes
