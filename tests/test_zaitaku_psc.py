"""在宅医療等連携機能のP・S・C判定（D.S.氏の方法）を、合成サンプルで手計算と照合する。

tests/fixtures/zaitaku_psc_*_sample.csv の病院
  イチ（熊本・上益城）：P の6項目をすべて基準ちょうどで満たす。P4は件数5（<30）でも退院100の5％で○
  ニ（同）           ：S1は件数300（<650）でも退院100件当たり37.5件で○、S3は16件でも2％で○。
                        S7は名簿の医療機関コードが違うが、法人名を除いた名称で照合して○
  サン（八代）       ：外来機能報告とつながらない→P1〜P3は「－」。C2は79人（<80）でも7.9％で○、C4は240ちょうど
  ヨン（八代）       ：1床当たり年200人の入棟・退棟→P4・C1〜C3は判定不能「－」
  ゴ（八代）         ：一般・療養病床がない→対象外
"""

import pytest

from chiiki_od import runner, zaitaku_psc


@pytest.fixture(scope="module")
def judged():
    r, notes = zaitaku_psc.evaluate(**zaitaku_psc.load_inputs(sample=True))
    return r.set_index("od_facility_code"), notes


def test_target_hospitals(judged):
    r, notes = judged
    assert sorted(r.index) == ["4300000001", "4300000002", "4300000003", "4300000004"]
    assert r.loc["4300000001", "beds"] == 50  # 2つの病棟を足す
    assert any("対象外" in n or "除く" in n for n in notes)


def test_type_p_at_thresholds(judged):
    r, _ = judged
    h = r.loc["4300000001"]
    assert [h[c] for c in ["P1", "P2", "P3", "P4", "P5", "P6"]] == ["○"] * 6
    assert h["P3_value"] == 120  # 在医総管60＋施医総管60
    assert h["type"] == "P" and h["P_count"] == 6


def test_type_s_with_ratio_and_name_match(judged):
    r, notes = judged
    h = r.loc["4300000002"]
    assert h["S1_value"] == 300 and h["S1"] == "○"  # 割合の条件
    assert h["S3"] == "○" and h["S4"] == "×" and h["S6"] == "×"
    assert h["S7"] == "○"  # 名称で照合した届出
    assert h["type"] == "S" and h["S_count"] == 5
    assert any("名称" in n for n in notes)


def test_type_c_and_missing_outpatient(judged):
    r, _ = judged
    h = r.loc["4300000003"]
    assert [h[c] for c in ["P1", "P2", "P3"]] == ["－"] * 3
    assert h["C1"] == "○" and h["C2"] == "○" and h["C3"] == "×" and h["C4"] == "○" and h["C5"] == "○"
    assert h["P5"] == "○" and h["type"] == "C"


def test_implausible_form1_values(judged):
    r, _ = judged
    h = r.loc["4300000004"]
    assert [h[c] for c in ["P4", "C1", "C2", "C3"]] == ["－"] * 4
    assert h["P1"] == "×"  # オープンデータ医療機関コードで外来機能報告とつながる
    assert h["type"] == "—" and h["items_met"] == 0


def test_sensitivity_scale():
    half, _ = zaitaku_psc.evaluate(**zaitaku_psc.load_inputs(sample=True), scale=0.5)
    half = half.set_index("od_facility_code")
    assert half.loc["4300000002", "S4"] == "○"  # 23件 ≥ 24×0.5


def test_hospital_indicator_hides_names():
    mod = runner.load_module("zaitaku_renkei_psc_hospital")
    res, notes = mod.compute(**mod.load_inputs(sample=True))
    assert "facility_name" not in res.columns and "od_facility_code" not in res.columns
    assert list(res["hospital_label"]) == ["八代・A病院", "八代・B病院", "熊本・上益城・A病院", "熊本・上益城・B病院"]
    assert res.set_index("hospital_id").loc["4312-A", "type"] == "P"  # 該当項目数の多い順
    assert any("感度分析" in n for n in notes)


def test_koso_indicator_counts():
    mod = runner.load_module("zaitaku_renkei_psc_koso")
    res, _ = mod.compute(**mod.load_inputs(sample=True))
    d = res.set_index("koso_kuiki_code")
    assert d.loc["4312", ["hospitals", "hospitals_p", "hospitals_s", "hospitals_c", "hospitals_any"]].tolist() == [2, 1, 1, 0, 2]
    assert d.loc["4308", ["hospitals", "hospitals_c", "hospitals_any", "hospitals_pc"]].tolist() == [2, 1, 1, 0]
    assert d.loc["0104", "hospitals"] == 0  # 対象の病院がない区域も0で残る
    assert len(res) == 339


def test_letters():
    assert [zaitaku_psc.letters(i) for i in (0, 25, 26, 701)] == ["A", "Z", "AA", "ZZ"]
