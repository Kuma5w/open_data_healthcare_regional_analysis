"""地図の境界（国土数値情報 行政区域 N03）から、サイトの地図に使う TopoJSON を作る。

1つの TopoJSON に、境界線を共有する4つの層を入れる。

| 層 | 地域 | コード |
|---|---|---|
| municipality_ward | 市区町村（政令市は区） | 5桁の市区町村コード |
| municipality | 市区町村（政令市は市にまとめる） | 5桁（政令市は市のコード） |
| koso_kuiki | 構想区域（reference/koso_kuiki.csv で市区町村をまとめる） | 4桁の構想区域コード |
| prefecture | 都道府県 | 2桁 |

各地物の属性は code・name・pref（都道府県コード2桁）。

簡略化と変換には mapshaper（Node.js のツール）を使う。PATH にあればそれを、なければ
npx で決まった版を使う。元データ・道具の版・設定・元ファイルの SHA-256 を、
TopoJSON と同じ場所の <名前>.meta.json に書く。
"""

from __future__ import annotations

import csv
import json
import re
import shutil
import subprocess
import tempfile
import zipfile
from pathlib import Path

from . import codes, manifest, paths

MAPSHAPER = "mapshaper@0.6.121"
SOURCE = {
    "title": "国土数値情報（行政区域データ）",
    "publisher": "国土交通省",
    "source_page": "https://nlftp.mlit.go.jp/ksj/gml/datalist/KsjTmplt-N03-2026.html",
    "file": "N03-20260101_GML.zip（全国、世界測地系、765.94MB）",
    # 公表ページではダウンロード欄がアイコンだけで、リンク先を本文から確かめられなかった。メタデータの置き場所と同じ規則で書いたもの
    "url": "https://nlftp.mlit.go.jp/ksj/gml/data/N03/N03-2026/N03-20260101_GML.zip",
    "as_of": "令和8年1月1日",
    "license": "CC BY 4.0（使用許諾条件「オープンデータ（CC_BY_4.0）」）",
    "original": "原典：国土地理院「数値地図（国土基本情報）」「地理院タイル」、総務省「全国地方公共団体コード一覧」（測量法に基づく国土地理院長承認（複製）R 7JHf 351）",
    "checked": "2026-11-26 に公表ページでファイル名・容量・使用許諾条件を確認",
}
ATTRIBUTION = "出典：国土交通省「国土数値情報（行政区域データ）」（令和8年1月1日時点）を加工して作成"
DEFAULTS = {"interval_m": 200, "min_island_km2": 2, "quantization": 100000}
LAYERS = ("municipality_ward", "municipality", "koso_kuiki", "prefecture")


def mapshaper_cmd() -> list[str]:
    exe = shutil.which("mapshaper")
    if exe:
        return [exe]
    npx = shutil.which("npx")
    if not npx:
        raise RuntimeError("mapshaper も npx も見つかりません。Node.js を入れてから `npm install -g mapshaper` してください")
    return [npx, "--yes", MAPSHAPER]


def find_shapefile(src: Path, workdir: Path) -> tuple[Path, list[Path]]:
    """src（N03 の zip か .shp）から市区町村界のシェープファイルを探す。zip なら必要な部分だけ展開する。

    返す値：(.shp のパス, SHA-256 を記録するファイルの一覧)
    """
    src = Path(src)
    pat = re.compile(r"N03-\d{8}\.(shp|dbf|shx|prj|cpg)$")
    if src.suffix.lower() == ".zip":
        with zipfile.ZipFile(src) as z:
            members = [m for m in z.namelist() if pat.search(Path(m).name)]
            if not any(m.endswith(".shp") for m in members):
                raise FileNotFoundError(f"{src.name} に N03-YYYYMMDD.shp がありません")
            for m in members:
                dest = workdir / Path(m).name
                with z.open(m) as r, open(dest, "wb") as w:
                    shutil.copyfileobj(r, w)
        shp = next(workdir.glob("*.shp"))
        return shp, [src]
    if src.suffix.lower() != ".shp":
        raise ValueError(f"N03 の zip か .shp を指定してください: {src}")
    parts = [p for p in sorted(src.parent.glob(src.stem + ".*")) if pat.search(p.name)]
    if not any(p.suffix == ".dbf" for p in parts):
        raise FileNotFoundError(f"{src.with_suffix('.dbf').name} がありません")
    return src, parts


def build_lookup(attrs: list[dict], koso: list[dict], designated: list[dict]) -> tuple[list[dict], dict]:
    """N03 の属性（N03_001 都道府県名・N03_004 市区町村名・N03_005 政令市の区名・N03_007 コード）から、
    コードごとの対応（政令市の市・構想区域）を作る。所属未定地（末尾000）は除く。

    返す値：(対応表の行, 照合の記録)
    """
    city_of = {(r["pref_name"], r["city_name"]): r["code5"] for r in designated}
    koso_of = {r["municipality_code5"]: r for r in koso}
    rows, seen = [], set()
    unknown_cities = set()
    for a in attrs:
        code = a["N03_007"]
        if not code or code in seen or code.endswith("000"):
            continue
        seen.add(code)
        ward = a.get("N03_005") or ""
        city = code
        if ward:
            city = city_of.get((a["N03_001"], a["N03_004"]), "")
            if not city:
                unknown_cities.add(f"{a['N03_001']}{a['N03_004']}")
        k = koso_of.get(code, {})
        rows.append({
            "code": code,
            "name": a["N03_004"] + ward,
            "pref": code[:2],
            "city": city,
            "city_name": a["N03_004"],
            "koso": k.get("koso_kuiki_code", ""),
            "koso_name": k.get("koso_kuiki_name", ""),
        })
    in_n03 = {r["code"] for r in rows}
    check = {
        "n03_codes": len(rows),
        "n03_without_koso": sorted(r["code"] + " " + r["name"] for r in rows if not r["koso"]),
        "koso_without_n03": sorted(c for c in koso_of if c not in in_n03),
        "unknown_designated_cities": sorted(unknown_cities),
    }
    return rows, check


def _read_csv(path: Path) -> list[dict]:
    with open(path, encoding="utf-8", newline="") as f:
        return list(csv.DictReader(f))


def _write_csv(path: Path, rows: list[dict]) -> None:
    with open(path, "w", encoding="utf-8", newline="") as f:
        w = csv.DictWriter(f, fieldnames=list(rows[0]))
        w.writeheader()
        w.writerows(rows)


def summarize(topo: dict) -> dict:
    """TopoJSON の層ごとの地物の数と、形のない地物（簡略化で消えたもの）を数える。"""
    out = {}
    for name in LAYERS:
        geoms = topo["objects"][name]["geometries"]
        empty = [g["properties"]["code"] for g in geoms if not g.get("arcs")]
        out[name] = {"features": len(geoms), "empty": empty}
    return out


def build(src: str | Path, out_dir: Path | None = None, name: str | None = None, **options) -> dict:
    """N03 から TopoJSON と記録（meta.json）を作る。返す値は記録の内容。"""
    opts = {**DEFAULTS, **{k: v for k, v in options.items() if v is not None}}
    out_dir = Path(out_dir or paths.SITE / "geo")
    out_dir.mkdir(parents=True, exist_ok=True)
    ms = mapshaper_cmd()
    with tempfile.TemporaryDirectory() as td:
        tmp = Path(td)
        shp, inputs = find_shapefile(Path(src), tmp)
        name = name or shp.stem.lower().replace("-", "_")  # 例：n03_20260101
        attrs_csv = tmp / "attrs.csv"
        subprocess.run([*ms, "-i", str(shp), "encoding=utf8", "-o", str(attrs_csv), "format=csv"],
                       check=True, capture_output=True)
        lookup, check = build_lookup(
            _read_csv(attrs_csv),
            _read_csv(paths.REFERENCE / "koso_kuiki.csv"),
            _read_csv(paths.REFERENCE / "designated_cities.csv"),
        )
        lookup_csv = tmp / "lookup.csv"
        _write_csv(lookup_csv, lookup)
        topo_path = out_dir / f"{name}.topo.json"
        pref_names = json.dumps(codes.PREFECTURES, ensure_ascii=False)
        cmd = [
            *ms, "-i", str(shp), "encoding=utf8",
            "-filter", "!/000$/.test(N03_007)",  # 所属未定地を除く
            "-join", str(lookup_csv), "keys=N03_007,code", "string-fields=code,pref,city,koso",
            "-dissolve", "N03_007", "copy-fields=name,pref,city,city_name,koso,koso_name",
            "-rename-fields", "code=N03_007",
            "-filter-islands", f"min-area={opts['min_island_km2']}km2",
            "-simplify", "weighted", "keep-shapes", f"interval={opts['interval_m']}",
            "-rename-layers", "municipality_ward",
            "-dissolve", "city", "copy-fields=city_name,pref", "+", "name=municipality",
            "-dissolve", "koso", "target=municipality_ward", "copy-fields=koso_name,pref", "+", "name=koso_kuiki",
            "-filter", 'koso != ""', "target=koso_kuiki",  # 北方領土の村は構想区域がない
            "-dissolve", "pref", "target=municipality_ward", "+", "name=prefecture",
            "-each", "code=city, name=city_name", "target=municipality",
            "-each", "code=koso, name=koso_name", "target=koso_kuiki",
            "-each", f"code=pref, name=({pref_names})[pref]", "target=prefecture",
            "-filter-fields", "code,name,pref", "target=municipality,koso_kuiki,prefecture",
            "-filter-fields", "code,name,pref,city,koso", "target=municipality_ward",
            "-o", str(topo_path), "format=topojson", "target=*", f"quantization={opts['quantization']}",
        ]
        r = subprocess.run(cmd, check=True, capture_output=True, text=True)
        version = subprocess.run([*ms, "-v"], check=True, capture_output=True, text=True).stdout.strip()
        files = [{"name": p.name, "bytes": p.stat().st_size, "sha256": manifest.sha256(p)} for p in inputs]

    topo = json.loads(topo_path.read_text(encoding="utf-8"))
    meta = {
        "format": "chiiki-od-geo/1",
        "name": name,
        "path": f"geo/{topo_path.name}",
        "generated_at": manifest.now(),
        "source": SOURCE,
        "attribution": ATTRIBUTION,
        "input_files": files,
        "tool": f"mapshaper {version}",
        "options": opts,
        "layers": summarize(topo),
        "bytes": topo_path.stat().st_size,
        "reference": {"koso_kuiki": "reference/koso_kuiki.csv", "designated_cities": "reference/designated_cities.csv"},
        "check": check,
        "notes": [
            "所属未定地（コードの末尾が000）は除いた。",
            f"面積{opts['min_island_km2']}km²未満の島は省略した。境界は約{opts['interval_m']}mより細かい凹凸を省いて簡略化した（地図の表示用。面積や距離の計算には使わない）。",
            "北方領土の6村は市区町村の層にはあるが、構想区域がないため構想区域の層にはない。",
            "構想区域は reference/koso_kuiki.csv（令和7年度病床機能報告の構想区域マスタ）で市区町村（政令市は区）をまとめた。",
        ],
        # 手元のパスは公開リポジトリに残さない（ファイル名だけにする）
        "mapshaper_log": [re.sub(r"(?:[A-Za-z]:)?[\\/][^\s]*[\\/]", "", ln) for ln in (r.stderr or "").splitlines() if ln.strip()][-12:],
    }
    (out_dir / f"{name}.meta.json").write_text(json.dumps(meta, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    return meta


def load_index(site_dir: Path | None = None) -> list[dict]:
    """site/geo/*.meta.json の一覧（新しい時点が先）。catalog.json の geo 欄に入れる。"""
    d = Path(site_dir or paths.SITE) / "geo"
    out = []
    for p in sorted(d.glob("*.meta.json"), reverse=True):
        m = json.loads(p.read_text(encoding="utf-8"))
        out.append({k: m[k] for k in ("name", "path", "source", "attribution", "layers", "notes", "generated_at") if k in m})
    return out
