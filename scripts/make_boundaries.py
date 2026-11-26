"""国土数値情報 行政区域（N03）から、サイトの地図に使う境界（site/geo/*.topo.json）を作る。

使い方:
    # 国土数値情報のページから「全国」の zip（例: N03-20260101_GML.zip）を保存して
    python scripts/make_boundaries.py --src ~/Downloads/N03-20260101_GML.zip
    # 展開済みなら .shp を指定してもよい（同じフォルダに .dbf .shx .prj が必要）
    python scripts/make_boundaries.py --src ~/Downloads/N03-20260101/N03-20260101.shp

Node.js が必要（mapshaper を使う。PATH になければ npx で取得する）。
"""

import argparse
import json

from chiiki_od import boundaries, catalog


def main() -> None:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--src", required=True, help="N03 の zip か .shp")
    ap.add_argument("--interval", type=int, help=f"簡略化の細かさ（m）。既定 {boundaries.DEFAULTS['interval_m']}")
    ap.add_argument("--min-island", type=float, help=f"省略する島の面積（km²）。既定 {boundaries.DEFAULTS['min_island_km2']}")
    a = ap.parse_args()
    meta = boundaries.build(a.src, interval_m=a.interval, min_island_km2=a.min_island)
    print(f"{meta['path']}: {meta['bytes']:,} バイト")
    for k, v in meta["layers"].items():
        print(f"  {k}: {v['features']} 地物" + (f"（形のないもの {len(v['empty'])}）" if v["empty"] else ""))
    c = meta["check"]
    if c["koso_without_n03"] or c["unknown_designated_cities"]:
        print("注意：", json.dumps({k: c[k] for k in ("koso_without_n03", "unknown_designated_cities")}, ensure_ascii=False))
    print(f"構想区域のない市区町村：{', '.join(c['n03_without_koso']) or 'なし'}")
    catalog.build()
    print("site/catalog.json も更新しました")


if __name__ == "__main__":
    main()
