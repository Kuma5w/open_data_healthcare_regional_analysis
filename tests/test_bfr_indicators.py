"""病床機能報告を使う見本指標を、合成サンプルで手計算と照合する。"""

import pytest

from chiiki_od import runner


def _run(card_id):
    mod = runner.load_module(card_id)
    res, notes = mod.compute(**mod.load_inputs(sample=True))
    return res.set_index("koso_kuiki_code"), notes


def test_recovery_bed_share():
    d, notes = _run("recovery_bed_share_koso")
    # 札幌：高度急性期50・急性期100・回復期50（一般40＋療養10）・慢性期60、休棟30は分母に入れない
    assert d.loc["0104", ["beds_recovery", "beds_active", "beds_closed"]].tolist() == [50, 260, 30]
    assert d.loc["0104", "recovery_share_pct"] == pytest.approx(19.2)
    assert d.loc["4312", "recovery_share_pct"] == pytest.approx(23.1)
    assert d.loc["4308", "recovery_share_pct"] == pytest.approx(30.0)
    assert d.loc["4310", "recovery_share_pct"] == pytest.approx(0.0)  # 回復期0でも区域は残る
    assert any("全体の回復期の割合" in n for n in notes)


def test_recovery_beds_per_75plus():
    d, _ = _run("recovery_beds_per_100k_75plus_koso")
    # 人口は区の行を足す（政令市の合計行・郡の合計行・男女別の行は使わない）
    assert d.loc["0104", "pop_75plus"] == 1800 + 2200
    assert d.loc["0104", "recovery_beds_per_100k_75plus"] == pytest.approx(1250.0)
    assert d.loc["4312", "pop_75plus"] == 900 + 700
    assert d.loc["4312", "recovery_beds_per_100k_75plus"] == pytest.approx(1500.0)
    assert d.loc["4308", "recovery_beds_per_100k_75plus"] == pytest.approx(2500.0)
    assert d.loc["4310", "recovery_beds_per_100k_75plus"] == pytest.approx(0.0)
