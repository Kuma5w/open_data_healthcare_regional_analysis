"""サイトとチャットボットが読むファイルの中身。"""

import json

from chiiki_od import catalog, paths


def test_catalog_and_search_index(tmp_path, monkeypatch):
    monkeypatch.setattr(paths, "SITE", tmp_path)
    cat = catalog.build()
    ids = {c["id"] for c in cat["indicators"]}
    assert {"homecare_offices_per_65plus", "recovery_bed_share_koso"} <= ids
    idx = json.loads((tmp_path / "search_index.json").read_text(encoding="utf-8"))["items"]
    docs = [x for x in idx if x["type"] == "doc"]
    cols = [x for x in idx if x["type"] == "col"]
    assert any(d["source"] == "docs/datasets/bed_function_report.md" for d in docs)
    assert any(d["source"] == "docs/site.md" for d in docs)
    # 列は項目名（見出しの最後の段）で検索できる
    m088 = next(c for c in cols if c["id"] == "col:bed_function_report_r7_form2_annual.m088")
    assert m088["item"] == "手術総数"
    # 都道府県名と、site/results にある結果の一覧
    assert cat["prefectures"]["43"] == "熊本県" and len(cat["prefectures"]) == 47
    for cid, r in cat["results"].items():
        assert cid in ids and r["path"] == f"results/{cid}.json"
