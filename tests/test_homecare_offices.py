"""見本指標を合成サンプルで計算し、手計算の値と一致するか確かめる。"""

import pandas as pd
import pytest

from chiiki_od import runner


@pytest.fixture(scope="module")
def mod():
    return runner.load_module("homecare_offices_per_65plus")


def _as_dict(df):
    return df.set_index("municipality_code5")[["offices", "pop_65plus", "offices_per_10k_65plus"]]


def test_city_level(mod):
    res, notes = mod.compute(**mod.load_inputs(sample=True))
    d = _as_dict(res)
    assert list(d.index) == ["01100", "43100", "43202", "43203"]
    # 札幌市：市の合計行（10000）を使い、区の行（3000+4000）は足さない
    assert d.loc["01100"].tolist() == [2, 10000, 2.0]
    # 熊本市：合計行がないので区を足し上げる（1500+1200）
    assert d.loc["43100", "offices"] == 2
    assert d.loc["43100", "pop_65plus"] == 2700
    assert d.loc["43100", "offices_per_10k_65plus"] == pytest.approx(7.407)
    # 八代市：重複行と検査数字の誤った行は数えない
    assert d.loc["43202"].tolist() == [1, 2000, 5.0]
    # 人吉市：事業所0でも結果に残り、0になる
    assert d.loc["43203"].tolist() == [0, 1000, 0.0]
    joined = " ".join(notes)
    assert "都道府県コード" in joined and "重複" in joined and "読めない" in joined


def test_ward_level(mod):
    res, _ = mod.compute(**mod.load_inputs(sample=True), ward_level=True)
    d = _as_dict(res)
    assert "01100" not in d.index  # 市の合計行は使わない
    assert d.loc["01101", "offices_per_10k_65plus"] == pytest.approx(3.333)
    assert d.loc["43103", "offices_per_10k_65plus"] == pytest.approx(8.333)


def test_runner_writes_output(tmp_path, monkeypatch):
    from chiiki_od import paths

    monkeypatch.setattr(paths, "OUTPUTS", tmp_path)
    res, notes, out = runner.run("homecare_offices_per_65plus", sample=True)
    assert out.exists() and out.with_suffix(".json").exists()
    assert len(pd.read_csv(out, dtype={"municipality_code5": str})) == len(res)
