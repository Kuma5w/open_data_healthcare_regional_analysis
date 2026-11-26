"""630調査（精神保健福祉資料）医療機関票 施設概要のパーサーと、精神科の5指標を合成サンプルで確かめる。

tests/fixtures/mental_health_630_sample.csv
  熊本県：全病院 4（国立・都道府県立 1、指定 2、非指定 1）、許可病床 1,000、在院 850、措置 6（3・2・1）、
          措置入院受入可能病床 120（国公立 100＋指定病床 20）、常勤精神科医 30、常勤指定医 20。人口（合成）100,000
  北海道：許可病床 200 に在院 210（利用率 105％）、措置入院受入可能病床 0。人口の合成サンプルに行がない
"""

import pandas as pd
import pytest

from chiiki_od import runner, seishin630


def _header_rows():
    """施設概要の表頭3段（見出しの語を段2に、常勤・非常勤を段3に置く）。"""
    width = 65
    r1, r2, r3 = [None] * width, [None] * width, [None] * width
    r1[0], r1[1] = "都道府県\n番号", "都道府県名"
    for pos, name, word in seishin630.COLUMNS:
        r2[pos] = word
        if name.endswith("_ft_facilities"):
            r3[pos] = "常勤配置\n医療機関数"
        elif name.endswith("_pt_facilities"):
            r3[pos] = "非常勤配置\n医療機関数"
        elif name.endswith("_ft"):
            r3[pos] = "常勤"
        elif name.endswith("_pt"):
            r3[pos] = "非常勤\n（※3）"
    return [tuple(r1), tuple(r2), tuple(r3)]


def _row(key, name, base):
    vals = [base + i for i in range(63)]
    vals[62] = "-"  # 相談員1人当たり：計算できない
    return (key, name, *vals)


def test_parse_sheet_blocks_and_codes():
    rows = [("令和7年6月30日時点の医療機関の実態",), (), ("施設概要1（精神病床有_全病院）（都道府県）",), *_header_rows(),
            _row(1, "北海道", 10), _row(43, "熊本県", 20), (None, "全国", *[30 + i for i in range(62)], 1.5), (),
            ("施設概要1（精神病床有_全病院）（政令指定都市）",), *_header_rows(), _row("011002", "札幌市", 5),
            _row(431001, "熊本市", 6), ("※1", "休床中の精神科病棟を含む。")]
    df, rep = seishin630.parse_sheet(rows, "施設概要1")
    assert df["level"].tolist() == ["prefecture", "prefecture", "national", "designated_city", "designated_city"]
    assert df["area_code"].tolist() == ["01", "43", "00", "01100", "43100"]
    assert df.loc[0, "facilities"] == 10 and df.loc[0, "beds_licensed"] == 15
    assert pd.isna(df.loc[0, "patients_per_discharge_counselor"])  # 「-」は欠損
    assert df.loc[2, "patients_per_discharge_counselor"] == 1.5
    assert rep["blocks"] == [{"table_no": 1, "level": "prefecture", "rows": 3}, {"table_no": 1, "level": "designated_city", "rows": 2}]


def test_parse_sheet_stops_when_columns_move():
    head = _header_rows()
    r2 = list(head[1])
    r2[7], r2[8] = r2[8], r2[7]  # 許可病床と措置入院受入可能病床の列が入れ替わった
    rows = [("施設概要1（精神病床有_全病院）（都道府県）",), head[0], tuple(r2), head[2], _row(1, "北海道", 10)]
    with pytest.raises(ValueError, match="見出し"):
        seishin630.parse_sheet(rows, "施設概要1")


def test_check_totals_reports_mismatch():
    df = seishin630.load_facility(sample=True)
    assert seishin630.check_totals(df) == []
    bad = df.copy()
    bad.loc[(bad.table_no == 1) & (bad.area_code == "43"), "beds_licensed"] = 999
    msgs = seishin630.check_totals(bad)
    assert any("表1 beds_licensed" in m for m in msgs) and any("表1≠表6+7+8 beds_licensed" in m for m in msgs)


def _run(card_id):
    res, notes = runner.execute(card_id, sample=True)[:2]
    return res.set_index("pref_code"), notes


def test_beds_and_inpatients_per_100k():
    r, notes = _run("psychiatric_beds_per_100k_pref")
    assert r.loc["43", "beds_per_100k"] == 1000.0 and r.loc["43", "beds_designated_hosp"] == 600
    assert pd.isna(r.loc["01", "beds_per_100k"]) and any("人口の表に行がない" in n for n in notes)
    r, _ = _run("psychiatric_inpatients_per_100k_pref")
    assert r.loc["43", "inpatients_per_100k"] == 850.0 and r.loc["43", "inpatients_involuntary"] == 6
    assert set(r.index) == {"01", "43"}  # 政令指定都市と全国の行は使わない


def test_occupancy_by_category():
    r, notes = _run("psychiatric_bed_occupancy_pref")
    assert r.loc["43", "occupancy_pct"] == 85.0
    assert r.loc["43", ["occupancy_public_pct", "occupancy_designated_pct", "occupancy_nondesignated_pct"]].tolist() == [60.0, 90.0, 83.3]
    assert r.loc["01", "occupancy_pct"] == 105.0 and pd.isna(r.loc["01", "occupancy_public_pct"])  # 病床0は欠損
    assert any("100％を超える" in n for n in notes)


def test_involuntary_bed_use():
    r, notes = _run("involuntary_bed_use_pref")
    assert r.loc["43", "involuntary_use_pct"] == 5.0  # 6 ÷ 120
    assert r.loc["43", "involuntary_use_public_pct"] == 3.0 and r.loc["43", "involuntary_use_designated_pct"] == 10.0
    assert pd.isna(r.loc["01", "involuntary_use_pct"])  # 受入可能病床0
    assert any("非指定病院" in n and "1人" in n for n in notes)


def test_psychiatrists_per_100k():
    r, _ = _run("psychiatrists_per_100k_pref")
    assert r.loc["43", "psychiatrists_ft_per_100k"] == 30.0 and r.loc["43", "designated_physicians_ft_per_100k"] == 20.0
    assert r.loc["43", "pref_name"] == "熊本県"


# ---- 診療実績（r7_630_shinryou）-------------------------------------------------
# tests/fixtures/mental_health_630_clinical_sample.csv・mental_health_630_outcome_sample.csv
#   熊本県：精神病床を有する病院 4。児童・思春期の専門外来 2、認知症 2、依存症 1。精神科救急は常時対応型 1・輪番型 2・不参加 1。
#           人口（合成）総数 100,000、20歳未満 17,000、65歳以上 30,000
#           医療保護入院 40人（3か月 50％・6か月 75％・1年 90％）
#   北海道：病院 2 に対し救急の役割の内訳が 1（内訳の不一致の注記）。医療保護入院 200人


def test_clinical_header_labels_match_columns():
    rows = [("診療実績_専門外来_届出状況1（精神病床有_全病院）（都道府県）",)]
    width = 81
    hdr = [[None] * width for _ in range(5)]
    hdr[0][0], hdr[0][1] = "都道府県\n番号", "都道府県名"
    for pos, name, word in seishin630.CLINICAL_COLUMNS:
        parts = word.split(" > ")
        for k, p in enumerate(parts[:4]):
            hdr[k][pos] = p
        if name.endswith(("_yes", "_no")):
            hdr[len(parts)][pos] = "有り" if name.endswith("_yes") else "無し"
    rows += [tuple(r) for r in hdr] + [(1, "北海道", *range(79))]
    df, _ = seishin630.parse_sheet(rows, "診療実績1", seishin630.CLINICAL_COLUMNS, depth=5)
    assert df.loc[0, "facilities"] == 0 and df.loc[0, "notif_psy_emergency_no"] == 78


def _run_clin(card_id):
    res, notes = runner.execute(card_id, sample=True)[:2]
    return res.set_index("pref_code"), notes


def test_specialty_clinics_use_age_specific_population():
    r, _ = _run_clin("child_adolescent_clinics_per_1m_pref")
    assert r.loc["43", "population"] == 17000 and r.loc["43", "clinic_hospitals_per_1m"] == 117.65  # 2 ÷ 17,000 × 100万
    assert r.loc["43", "clinic_share_pct"] == 50.0
    r, _ = _run_clin("dementia_clinics_per_1m_pref")
    assert r.loc["43", "population"] == 30000 and r.loc["43", "clinic_hospitals_per_1m"] == 66.67
    assert r.loc["43", "dementia_center"] == 1
    r, notes = _run_clin("addiction_clinics_per_1m_pref")
    assert r.loc["43", "clinic_hospitals_per_1m"] == 10.0 and r.loc["43", "hub_addiction_specialized"] == 1
    assert any("0の都道府県 1" in n for n in notes)  # 北海道


def test_psy_emergency_participation():
    r, notes = _run_clin("psy_emergency_hospitals_per_1m_pref")
    assert r.loc["43", "participating_hospitals"] == 3 and r.loc["43", "participating_per_1m"] == 30.0
    assert r.loc["43", "full_time_or_rotation"] == 3
    assert any("内訳の合計が病院数と一致しない都道府県 1" in n for n in notes)


def test_medical_protection_discharge():
    r, notes = _run_clin("medical_protection_discharge_1y_pref")
    assert r.loc["43", ["discharged_3m", "discharged_6m", "discharged_1y"]].tolist() == [20, 30, 36]
    assert r.loc["43", "discharge_rate_1y_pct"] == 90.0 and r.loc["43", "support_referral_pct"] == 25.0
    assert set(r.index) == {"01", "43"}
    assert any("50人未満の都道府県 1" in n for n in notes)
