"""在宅医療等連携機能：P・S・Cの類型に該当する病院の数（構想区域別）

指標カード: indicators/zaitaku_renkei_psc_koso.yaml
判定の方法は chiiki_od.zaitaku_psc（病院別の指標 zaitaku_renkei_psc_hospital と同じ）。
"""

from __future__ import annotations

import pandas as pd

from chiiki_od import areas, zaitaku_psc


def load_inputs(sample: bool = False) -> dict[str, pd.DataFrame]:
    return zaitaku_psc.load_inputs(sample=sample)


def compute(facility, wards, form2, outpatient, filings) -> tuple[pd.DataFrame, list[str]]:
    r, notes = zaitaku_psc.evaluate(facility, wards, form2, outpatient, filings)
    notes += zaitaku_psc.summary_notes(r)
    out = zaitaku_psc.koso_table(r, areas.koso_reference())
    if (n := int((out["hospitals"] == 0).sum())):
        notes.append(f"対象の病院がない構想区域 {n}（0として表に残す）")
    return out, notes
