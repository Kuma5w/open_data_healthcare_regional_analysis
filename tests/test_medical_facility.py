"""医療施設調査のパーサーと、人口10万人あたりの施設数の指標（構想区域・市区町村）を、合成サンプルで確かめる。

人口（総数、tests/fixtures/population_jumin_sample.csv）
  市区町村版：札幌市は市の合計行 50000、熊本市は区の足し上げ 6000+5000=11000、八代市 10000、人吉市 5000
  構想区域版：区と市町村の行を足す。札幌 0104＝15000+20000、熊本・上益城 4312＝6000+5000、八代 4308、球磨 4310
"""

import pytest

from chiiki_od import paths, runner
from chiiki_od.iryo_shisetsu import TABLE_COLUMNS, parse_table


def test_parse_table_levels_and_symbols():
    df, report = parse_table(paths.FIXTURES / "medical_facility_survey_table2_raw_sample.csv", TABLE_COLUMNS["table2"])
    assert report["levels"] == {"municipality": 3, "secondary_area": 2, "prefecture": 1}
    assert report["as_of"] == "令和7(2025)年10月1日"
    assert report["subtotal_mismatches"] == []  # 都道府県・二次医療圏の行＝市区町村の合計
    muni = df[df.level == "municipality"].set_index("code")
    assert list(muni.index) == ["43101", "43103", "43202"]  # 5桁のコードを2桁や4桁と取り違えない
    assert muni.loc["43103", "clinics_with_beds"] == 0  # 「-」は0
    assert muni.loc["43202", "secondary_area_code"] == "4304"  # 直前の二次医療圏の行
    assert muni.loc["43101", "name"] == "中央区"


def test_parse_table_detects_subtotal_mismatch(tmp_path):
    raw = (paths.FIXTURES / "medical_facility_survey_table2_raw_sample.csv").read_bytes().decode("cp932")
    broken = tmp_path / "broken.csv"
    broken.write_bytes(raw.replace("43202 八代市　　　　,7,", "43202 八代市　　　　,6,").encode("cp932"))
    _, report = parse_table(broken, TABLE_COLUMNS["table2"])
    assert "prefecture 43" in report["subtotal_mismatches"]
    assert "secondary_area 4304" in report["subtotal_mismatches"]


def _run(card_id, key, **options):
    mod = runner.load_module(card_id)
    res, notes = mod.compute(**mod.load_inputs(sample=True), **options)
    return res.set_index(key), notes


def test_hospitals_municipality():
    d, notes = _run("hospitals_per_100k", "municipality_code5")
    assert list(d.index) == ["01100", "43100", "43202", "43203"]
    assert d.loc["01100", ["hospitals", "general_hospitals", "psychiatric_hospitals", "pop_total"]].tolist() == [4, 3, 1, 50000]
    assert d.loc["01100", "hospitals_per_100k"] == pytest.approx(8.0)
    assert d.loc["43100", "hospitals_per_100k"] == pytest.approx(18.18)
    assert d.loc["43203", "hospitals_per_100k"] == pytest.approx(0.0)
    assert any("施設が0の市区町村 1 件" in n for n in notes)


def test_hospitals_ward_level():
    d, _ = _run("hospitals_per_100k", "municipality_code5", ward_level=True)
    assert d.loc["01101", "hospitals_per_100k"] == pytest.approx(20.0)  # 3 ÷ 15000
    assert d.loc["43103", "hospitals"] == 0


def test_hospitals_koso():
    d, _ = _run("hospitals_per_100k_koso", "koso_kuiki_code")
    assert d.loc["0104", ["hospitals", "pop_total"]].tolist() == [4, 35000]
    assert d.loc["0104", "hospitals_per_100k"] == pytest.approx(11.43)
    assert d.loc["4312", "hospitals_per_100k"] == pytest.approx(18.18)
    assert d.loc["4308", "hospitals_per_100k"] == pytest.approx(10.0)
    assert d.loc["4310", "hospitals_per_100k"] == pytest.approx(0.0)  # 病院0でも区域は残る
    assert d.loc["4312", "koso_kuiki_name"] == "熊本・上益城"


def test_clinics_and_dental():
    d, _ = _run("general_clinics_per_100k_koso", "koso_kuiki_code")
    assert d.loc["0104", ["general_clinics", "clinics_with_beds"]].tolist() == [30, 2]
    assert d.loc["0104", "general_clinics_per_100k"] == pytest.approx(85.7)
    d, _ = _run("general_clinics_per_100k", "municipality_code5")
    assert d.loc["43100", "general_clinics_per_100k"] == pytest.approx(100.0)  # 11 ÷ 11000
    d, _ = _run("dental_clinics_per_100k", "municipality_code5")
    assert d.loc["43203", "dental_clinics_per_100k"] == pytest.approx(0.0)
    d, _ = _run("dental_clinics_per_100k_koso", "koso_kuiki_code")
    assert d.loc["4308", "dental_clinics_per_100k"] == pytest.approx(40.0)


def test_psychiatric_beds_koso():
    # 精神病床（合成）：札幌 中央区100、熊本 中央区50、八代市60。人口は上の説明のとおり
    d, notes = _run("psychiatric_beds_per_100k_koso", "koso_kuiki_code")
    assert d.loc["0104", "beds_psychiatric"] == 100 and d.loc["0104", "beds_psychiatric_per_100k"] == pytest.approx(285.7)
    assert d.loc["4312", "beds_psychiatric_per_100k"] == pytest.approx(454.5)  # 50 ÷ 11,000
    assert d.loc["4308", "beds_psychiatric_per_100k"] == pytest.approx(600.0)
    assert d.loc["4310", "beds_psychiatric"] == 0
    assert any("精神病床が0の構想区域 1 件" in n for n in notes)
