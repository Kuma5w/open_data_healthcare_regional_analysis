"""地図の境界（chiiki_od.boundaries と site/geo/）のテスト。"""

from __future__ import annotations

import json
import zipfile

import pytest

from chiiki_od import boundaries, paths

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
    topo = json.loads(GEO[-1].read_text(encoding="utf-8"))
    layers = {k: {g["properties"]["code"] for g in o["geometries"]} for k, o in topo["objects"].items()}
    for p in sorted((paths.SITE / "results").glob("*.json")):
        doc = json.loads(p.read_text(encoding="utf-8"))
        ix = [c["name"] for c in doc["columns"]].index(doc["output"]["area_code"])
        area = {r[ix] for r in doc["rows"]}
        best = max(layers.values(), key=lambda s: len(area & s))
        assert area <= best, f"{p.name}: 地図にない地域 {sorted(area - best)[:5]}"


@pytest.mark.skipif(not GEO, reason="site/geo に境界がない")
def test_カタログに境界の出典が入る():
    geo = boundaries.load_index()
    assert geo and geo[0]["path"].startswith("geo/") and "国土数値情報" in geo[0]["attribution"]
    assert (paths.SITE / geo[0]["path"]).exists()
