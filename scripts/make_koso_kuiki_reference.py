"""病床機能報告の留意事項ZIP（別紙２ 構想区域マスタ）から reference/koso_kuiki.csv を作る。

使い方:
    chiiki-od fetch bed_function_report_r7_facility   # 留意事項ZIPも取得される
    python scripts/make_koso_kuiki_reference.py
"""

from chiiki_od import paths, specs
from chiiki_od.bfr import koso_kuiki_reference
from chiiki_od.fetch import raw_path

DATASET = "bed_function_report_r7_facility"
MEMBER = "別紙２_令和７年度病床機能報告構想区域マスタ.xlsx"


def main() -> None:
    ds = specs.load_dataset(DATASET)
    notes = next(f for f in ds["files"] if f["key"] == "notes")
    m = koso_kuiki_reference(raw_path(DATASET, notes), MEMBER)
    m["valid_for"] = "令和7年度病床機能報告"
    m["source_url"] = notes["url"]
    out = paths.REFERENCE / "koso_kuiki.csv"
    m.to_csv(out, index=False, encoding="utf-8")
    print(f"{out.relative_to(paths.ROOT)}: {len(m)}行、構想区域 {m['koso_kuiki_code'].nunique()}、二次医療圏 {m['secondary_area_code'].nunique()}")


if __name__ == "__main__":
    main()
