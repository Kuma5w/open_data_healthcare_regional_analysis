"""在宅医療等連携機能：実数基準のP・S・C判定と星取り表（病院別）

指標カード: indicators/zaitaku_renkei_psc_hospital.yaml
判定の方法（18項目・基準値・類型の決め方）は chiiki_od.zaitaku_psc にまとめてある。
このファイルは病院別の表を作るだけ。病院名と医療機関コードは載せない。
"""

from __future__ import annotations

import pandas as pd

from chiiki_od import zaitaku_psc


def load_inputs(sample: bool = False) -> dict[str, pd.DataFrame]:
    return zaitaku_psc.load_inputs(sample=sample)


def compute(facility, wards, form2, outpatient, filings) -> tuple[pd.DataFrame, list[str]]:
    r, notes = zaitaku_psc.evaluate(facility, wards, form2, outpatient, filings)
    notes += zaitaku_psc.summary_notes(r)
    for scale in (0.5, 2.0):  # 感度分析：基準（件数・割合）を半分・2倍にしたとき
        s, _ = zaitaku_psc.evaluate(facility, wards, form2, outpatient, filings, scale=scale)
        notes += [f"感度分析（基準×{scale:g}）" + zaitaku_psc.summary_notes(s)[0].removeprefix("判定した病院")]
    return zaitaku_psc.hospital_table(r), notes
