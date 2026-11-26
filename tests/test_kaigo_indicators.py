"""介護サービスの指標（訪問看護・訪問リハ・通所介護・通所リハ・短期入所生活介護）を、
合成サンプル（tests/fixtures/kaigo_jigyosho_services_sample.csv）で手計算と照合する。

人口（65歳以上）：札幌市は市の合計行 10000、熊本市は区の足し上げ 1500+1200=2700、八代市 2000、人吉市 1000。
"""

import pytest

from chiiki_od import kaigo, runner


def _run(card_id, **options):
    mod = runner.load_module(card_id)
    res, notes = mod.compute(**mod.load_inputs(sample=True), **options)
    return res.set_index("municipality_code5"), notes


def test_visiting_nursing():
    d, notes = _run("visiting_nursing_offices_per_65plus")
    assert list(d.index) == ["01100", "43100", "43202", "43203"]  # 人口0の色丹村は除く
    assert d.loc["01100", ["offices", "offices_medical"]].tolist() == [2, 1]
    assert d.loc["01100", "offices_per_10k_65plus"] == pytest.approx(2.0)
    # 熊本市：同じ事業所番号の本体とサテライト（中央区・西区）は1件
    assert d.loc["43100", "offices"] == 1
    assert d.loc["43100", "offices_per_10k_65plus"] == pytest.approx(3.704)
    assert d.loc["43202", ["offices", "offices_medical"]].tolist() == [1, 1]
    assert d.loc["43203", "offices_per_10k_65plus"] == pytest.approx(0.0)  # 事業所0でも残る
    assert any("重複" in n for n in notes)


def test_visiting_nursing_ward_level():
    d, _ = _run("visiting_nursing_offices_per_65plus", ward_level=True)
    assert "01100" not in d.index
    assert d.loc["01101", "offices_per_10k_65plus"] == pytest.approx(3.333)
    assert d.loc["43101", "offices"] == 1  # 重複は先に出た行（中央区）で数える
    assert d.loc["43103", "offices"] == 0


def test_visiting_rehab_breakdown():
    d, _ = _run("visiting_rehab_offices_per_65plus")
    assert d.loc["43202", ["offices", "offices_medical", "offices_roken"]].tolist() == [2, 1, 1]
    assert d.loc["43202", "offices_per_10k_65plus"] == pytest.approx(10.0)
    assert d.loc["43100", ["offices", "offices_medical", "offices_roken"]].tolist() == [1, 0, 0]
    assert d.loc["01100", "offices"] == 0


def test_day_service_includes_community_type():
    d, notes = _run("day_service_offices_per_65plus")
    # 札幌市：通所介護1（中央区）＋地域密着型1（北区）
    assert d.loc["01100", ["offices", "offices_regular", "offices_community"]].tolist() == [2, 1, 1]
    # 八代市：同じ事業所番号が通所介護と地域密着型の両方にあり、それぞれ数える
    assert d.loc["43202", ["offices", "offices_regular", "offices_community"]].tolist() == [2, 1, 1]
    assert d.loc["43202", "offices_per_10k_65plus"] == pytest.approx(10.0)
    assert d.loc["43203", "offices_per_10k_65plus"] == pytest.approx(10.0)
    assert d.loc["43100", "offices"] == 0
    joined = " ".join(notes)
    assert "都道府県コード" in joined and "別のサービスで同じ事業所番号" in joined


def test_day_rehab():
    d, notes = _run("day_rehab_offices_per_65plus")
    assert d.loc["43202", ["offices", "offices_medical", "offices_roken"]].tolist() == [1, 0, 1]
    assert d.loc["43100", ["offices", "offices_medical"]].tolist() == [1, 1]
    assert d.loc["43100", "offices_per_10k_65plus"] == pytest.approx(3.704)
    assert any("読めない" in n for n in notes)


def test_short_stay():
    d, _ = _run("short_stay_offices_per_65plus")
    assert d.loc["01100", "offices_per_10k_65plus"] == pytest.approx(1.0)
    assert d.loc["43203", "offices_per_10k_65plus"] == pytest.approx(10.0)
    assert d["offices"].sum() == 2


def test_helper_matches_homecare_indicator():
    """共通処理で訪問介護を数えると、既存の homecare_offices_per_65plus と同じ結果になる。"""
    from chiiki_od import paths
    from chiiki_od.convert import read_with_spec

    mod = runner.load_module("homecare_offices_per_65plus")
    inputs = mod.load_inputs(sample=True)
    expected, _ = mod.compute(**inputs)

    offices = read_with_spec("kaigo_jigyosho_110", paths.FIXTURES / "kaigo_jigyosho_110_sample.csv")
    got, _ = kaigo.offices_per_population(
        offices.assign(service_code="110"), kaigo.load_population(sample=True), "offices_per_10k_65plus"
    )
    cols = list(expected.columns)
    assert got[cols].astype(str).equals(expected[cols].astype(str))
