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
