"""地図の境界（chiiki_od.boundaries と site/geo/）のテスト。"""

from __future__ import annotations

import json
import zipfile

import pytest

from chiiki_od import boundaries, paths, results, specs

DESIGNATED = [{"code5": "43100", "pref_name": "熊本県", "city_name": "熊本市"}]
KOSO = [
    {"municipality_code5": "43101", "koso_kuiki_code": "4301", "koso_kuiki_name": "熊本・上益城"},
    {"municipality_code5": "43202", "koso_kuiki_code": "4305", "koso_kuiki_name": "八代"},
    {"municipality_code5": "43999", "koso_kuiki_code": "4309", "koso_kuiki_name": "（N03にない）"},
]


def attr(pref, city, ward, code):
    return {"N03_001": pref, "N03_004": city, "N03_005": ward, "N03_007": code}


def test_対応表_政令市の区は市に_構想区域を付ける():
    rows, check = boundaries.build_lookup(
        [
            attr("熊本県", "熊本市", "中央区", "43101"),
            attr("熊本県", "熊本市", "中央区", "43101"),  # 島ごとの行は1つにまとめる
            attr("熊本県", "八代市", "", "43202"),
            attr("熊本県", "所属未定地", "", "43000"),
            attr("北海道", "色丹村", "", "01695"),
        ],
        KOSO,
        DESIGNATED,
    )
    by = {r["code"]: r for r in rows}
    assert set(by) == {"43101", "43202", "01695"}
    assert by["43101"] | {} == {
        "code": "43101", "name": "熊本市中央区", "pref": "43", "city": "43100",
        "city_name": "熊本市", "koso": "4301", "koso_name": "熊本・上益城",
    }
    assert by["43202"]["city"] == "43202" and by["43202"]["koso"] == "4305"
    assert check["n03_without_koso"] == ["01695 色丹村"]
    assert check["koso_without_n03"] == ["43999"]
    assert check["unknown_designated_cities"] == []


def test_対応表_政令市の一覧にない市は記録する():
    _, check = boundaries.build_lookup([attr("静岡県", "浜松市", "中央区", "22138")], [], DESIGNATED)
    assert check["unknown_designated_cities"] == ["静岡県浜松市"]


def test_zipから市区町村界だけを取り出す(tmp_path):
    z = tmp_path / "N03-20260101_GML.zip"
    with zipfile.ZipFile(z, "w") as f:
        for ext in ("shp", "dbf", "shx", "prj", "cpg", "geojson"):
            f.writestr(f"N03-20260101_GML/N03-20260101.{ext}", b"x")
        f.writestr("N03-20260101_GML/N03-20260101_prefecture.shp", b"x")
    work = tmp_path / "w"
    work.mkdir()
    shp, inputs = boundaries.find_shapefile(z, work)
    assert shp.name == "N03-20260101.shp"
    assert sorted(p.name for p in work.iterdir()) == [f"N03-20260101.{e}" for e in ("cpg", "dbf", "prj", "shp", "shx")]
    assert inputs == [z]


def test_展開済みのshpも使える(tmp_path):
    for ext in ("shp", "dbf", "shx", "prj"):
        (tmp_path / f"N03-20260101.{ext}").write_bytes(b"x")
    shp, inputs = boundaries.find_shapefile(tmp_path / "N03-20260101.shp", tmp_path)
    assert shp.name == "N03-20260101.shp"
    assert [p.suffix for p in inputs] == [".dbf", ".prj", ".shp", ".shx"]


GEO = sorted((paths.SITE / "geo").glob("*.topo.json"))


@pytest.mark.skipif(not GEO, reason="site/geo に境界がない")
def test_境界の層と属性():
    topo = json.loads(GEO[-1].read_text(encoding="utf-8"))
    assert set(topo["objects"]) == set(boundaries.LAYERS)
    for name, s in boundaries.summarize(topo).items():
        assert s["empty"] == [], f"{name} に形のない地物があります"
    for name in boundaries.LAYERS:
        for g in topo["objects"][name]["geometries"]:
            p = g["properties"]
            assert p["code"] and p["name"] and len(p["pref"]) == 2
            assert p["code"].startswith(p["pref"])
    assert len(topo["objects"]["prefecture"]["geometries"]) == 47


@pytest.mark.skipif(not GEO, reason="site/geo に境界がない")
def test_結果の地域はすべて地図にある():
    layers = boundaries.layer_codes()
    for p in sorted((paths.SITE / "results").glob("*.json")):
        doc = json.loads(p.read_text(encoding="utf-8"))
        card = specs.load_card(doc["indicator"])
        ix = [c["name"] for c in doc["columns"]].index(doc["output"]["area_code"])
        cov = boundaries.map_coverage(card["unit_of_analysis"], [r[ix] for r in doc["rows"]], layers)
        assert cov["shown"] and cov["missing"] == [], f"{p.name}: {cov}"


LAYERS = {
    "municipality": {"43100", "43202"},
    "municipality_ward": {"43101", "43202"},
    "koso_kuiki": {"4301", "4305", "0503"},
    "prefecture": {"43"},
}


def test_地図の層は集計単位で決める():
    # 二次医療圏は構想区域とコードが同じでも、構想区域の境界では塗らない
    cov = boundaries.map_coverage("secondary_medical_area", ["4301", "4305"], LAYERS)
    assert cov["layer"] is None and not cov["shown"] and "二次医療圏" in cov["reason"]
    assert boundaries.map_coverage("koso_kuiki", ["4301", "4305"], LAYERS)["layer"] == "koso_kuiki"
    # 市区町村は、政令市を市にまとめた層と区の層のうち、よく一致するほう
    assert boundaries.map_coverage("municipality", ["43100", "43202"], LAYERS)["layer"] == "municipality"
    assert boundaries.map_coverage("municipality", ["43101", "43202"], LAYERS)["layer"] == "municipality_ward"


def test_境界にないコードは数え_9割未満なら地図を出さない():
    codes10 = [f"43{i:03d}" for i in range(10)]
    layers = {"municipality": set(codes10[:9])}
    cov = boundaries.map_coverage("municipality", codes10, layers)
    assert cov["shown"] and cov["missing"] == ["43009"]
    layers = {"municipality": set(codes10[:8])}
    assert not boundaries.map_coverage("municipality", codes10, layers)["shown"]


def test_checkの注意():
    card = {"unit_of_analysis": "municipality"}
    doc = {"output": {"area_code": "code"}, "columns": [{"name": "code"}], "rows": [["43100"], ["43202"], ["43999"]]}
    # 3件中1件が境界にない（9割未満）→ 地図は出ない
    assert "地図は出ません" in results.map_warnings(card, doc, LAYERS)[0]
    doc["rows"] = [[c] for c in [f"43{i:03d}" for i in range(9)] + ["43100"]]
    layers = {"municipality": {f"43{i:03d}" for i in range(9)}}
    w = results.map_warnings(card, doc, layers)
    assert "1件" in w[0] and "43100" in w[0]


@pytest.mark.skipif(not GEO, reason="site/geo に境界がない")
def test_カタログに境界の出典が入る():
    geo = boundaries.load_index()
    assert geo and geo[0]["path"].startswith("geo/") and "国土数値情報" in geo[0]["attribution"]
    assert (paths.SITE / geo[0]["path"]).exists()
