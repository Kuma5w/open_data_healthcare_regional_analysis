"""サイトの「結果を見る」が読むファイル（site/results/）の書き出しと検証。"""

import json

import pytest

from chiiki_od import paths, results, specs


def _export(tmp_path, card_id):
    p = results.export(card_id, sample=True, out_dir=tmp_path)
    return json.loads(p.read_text(encoding="utf-8"))


def test_export_matches_card_output(tmp_path):
    doc = _export(tmp_path, "recovery_bed_share_koso")
    card = specs.load_card("recovery_bed_share_koso")
    assert [c["name"] for c in doc["columns"]] == [c["name"] for c in card["output"]["columns"]]
    assert {c["name"]: c["type"] for c in doc["columns"]}["koso_kuiki_code"] == "string"
    assert all(len(r) == len(doc["columns"]) for r in doc["rows"])
    assert doc["sample"] is True and doc["card_version"] == card["version"]
    assert (tmp_path / "recovery_bed_share_koso.csv").read_bytes().startswith(b"\xef\xbb\xbf")


def test_pooled_values_are_sums_of_numerator_and_denominator(tmp_path):
    doc = _export(tmp_path, "recovery_bed_share_koso")
    names = [c["name"] for c in doc["columns"]]
    rows = [dict(zip(names, r, strict=True)) for r in doc["rows"]]
    hk = [r for r in rows if r["koso_kuiki_code"].startswith("01")]
    num = sum(r["beds_recovery"] for r in hk)
    den = sum(r["beds_active"] for r in hk)
    assert doc["by_pref"]["01"]["name"] == "北海道"
    assert doc["by_pref"]["01"]["numerator_sum"] == num
    assert doc["by_pref"]["01"]["pooled"] == pytest.approx(num / den * 100, abs=1e-3)
    assert doc["national"]["numerator_sum"] == sum(r["beds_recovery"] for r in rows)
    assert doc["summary"]["n"] == len(rows)


def test_sample_results_cannot_go_to_site(tmp_path, monkeypatch):
    with pytest.raises(ValueError, match="合成サンプル"):
        results.export("recovery_bed_share_koso", sample=True)
    _export(tmp_path, "recovery_bed_share_koso")
    res = results.check(tmp_path)
    assert any("合成サンプル" in e for e in res.errors)


def test_check_reports_stale_results(tmp_path):
    _export(tmp_path, "homecare_offices_per_65plus")
    p = tmp_path / "homecare_offices_per_65plus.json"
    doc = json.loads(p.read_text(encoding="utf-8"))
    doc["card_version"] = "0.0.1"
    doc["script_sha256"] = "0" * 64
    p.write_text(json.dumps(doc, ensure_ascii=False), encoding="utf-8")
    warnings = results.check(tmp_path).warnings
    assert any("v0.0.1" in w for w in warnings)
    assert any("計算スクリプトが" in w for w in warnings)


def test_card_must_list_every_result_column(tmp_path, monkeypatch):
    card = specs.load_card("recovery_bed_share_koso")
    card["output"]["columns"] = card["output"]["columns"][:-1]
    monkeypatch.setattr(specs, "load_card", lambda cid: card)
    with pytest.raises(ValueError, match="output.columns"):
        results.build("recovery_bed_share_koso", sample=True)


def test_published_results_pass_check():
    """リポジトリに入っている site/results/ はエラーなし（CIで毎回確かめる）。"""
    if not (paths.SITE / "results").exists():
        pytest.skip("site/results がまだありません")
    assert results.check().errors == []


def test_time_series_for_trend_indicators(tmp_path):
    # 推移を持つ指標：表は最新の年度、series は年度ごとの全国・都道府県・地域の値、CSV はすべての年度
    doc = _export(tmp_path, "zaitaku_renkei_trend_koso")
    names = [c["name"] for c in doc["columns"]]
    rows = [dict(zip(names, r, strict=True)) for r in doc["rows"]]
    assert {r["fiscal_year"] for r in rows} == {"FY2024"}
    s = doc["series"]
    assert s["time_column"] == "fiscal_year" and s["times"] == ["FY2022", "FY2023", "FY2024"]
    assert s["kind"] == "pooled"
    assert s["national"] == [2.5, 1.0, 2.0]  # (1+4)/2、(0+0+3)/3、(1+4+3+0)/4
    assert s["by_pref"]["43"] == s["national"]
    assert s["areas"]["4312"] == [1.0, 0.0, 2.5] and s["areas"]["4302"] == [None, None, None]
    import pandas as pd

    csv = pd.read_csv(tmp_path / "zaitaku_renkei_trend_koso.csv", dtype=str)
    assert sorted(csv["fiscal_year"].unique()) == s["times"]


def test_time_series_mean_for_hospitals(tmp_path):
    doc = _export(tmp_path, "zaitaku_renkei_trend_hospital")
    s = doc["series"]
    assert s["kind"] == "mean"
    assert s["national"][-1] == pytest.approx(2.0)  # 4病院の該当項目数 1・4・3・0 の平均
    assert len(doc["rows"]) == 4


def _hide(monkeypatch, card_id):
    """card_id のカードだけ、hidden_from_site が付いているものとして読む。"""
    real = specs.load_card
    monkeypatch.setattr(
        specs, "load_card", lambda cid: {**real(cid), "hidden_from_site": {"reason": "テスト"}} if cid == card_id else real(cid)
    )


def test_hidden_cards_stay_off_the_site(tmp_path, monkeypatch):
    _export(tmp_path, "homecare_offices_per_65plus")
    _hide(monkeypatch, "homecare_offices_per_65plus")
    res = results.check(tmp_path)
    # 結果を site/results に置いたままだと公開されるので、エラーにする
    assert any("hidden_from_site" in e for e in res.errors)
    # 引数なしの chiiki-od results でも作らず、結果がないことも注意しない
    assert "homecare_offices_per_65plus" not in results.exportable()
    assert not any(w.startswith("indicators/homecare_offices_per_65plus.yaml") for w in res.warnings)
