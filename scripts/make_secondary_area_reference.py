"""厚生労働省「二次医療圏－市区町村対応表」（e-Govデータポータル）から reference/secondary_medical_area_2023.csv を作る。

使い方:
    python scripts/make_secondary_area_reference.py --file <二次医療圏.xlsx のパス>

元ファイル: https://data.e-gov.go.jp/data/uploads/resource/%E4%BA%8C%E6%AC%A1%E5%8C%BB%E7%99%82%E5%9C%8F.xlsx
（2026年11月時点の掲載ファイルは「令和5年12月31日」時点の対応表。公開日 2024-03-15）
"""

import argparse
import re

import pandas as pd
import python_calamine as pc

from chiiki_od import paths

SOURCE_URL = "https://data.e-gov.go.jp/data/uploads/resource/%E4%BA%8C%E6%AC%A1%E5%8C%BB%E7%99%82%E5%9C%8F.xlsx"


def _clean(v) -> str:
    return re.sub(r"[\s　]+", "", str(v))


def _code(v, width: int) -> str:
    t = _clean(v)
    return str(int(float(t))).zfill(width) if re.fullmatch(r"\d+(\.0)?", t) else t


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--file", required=True)
    args = ap.parse_args()
    rows = pc.CalamineWorkbook.from_path(args.file).get_sheet_by_index(0).to_python()
    title = _clean(rows[1][1])
    as_of = re.search(r"（(.+?)）", title)[1]
    if [_clean(rows[3][i]) for i in (1, 2, 4)] != ["都道府県", "二次医療圏", "市区町村"]:
        raise ValueError(f"見出しが想定と違います: {rows[3]}")
    recs = [
        (_clean(r[1]), _code(r[2], 4), _clean(r[3]), _code(r[4], 5), _clean(r[5]))
        for r in rows[4:]
        if _clean(r[4])
    ]
    d = pd.DataFrame(recs, columns=["pref_name", "secondary_area_code", "secondary_area_name",
                                    "municipality_code5", "municipality_name"])
    d.insert(0, "pref_code", d["municipality_code5"].str[:2])
    d["valid_for"] = as_of
    d["source_url"] = SOURCE_URL
    out = paths.REFERENCE / "secondary_medical_area_2023.csv"
    d.to_csv(out, index=False, encoding="utf-8")
    print(f"{out.relative_to(paths.ROOT)}: {as_of}、{len(d)}行、二次医療圏 {d['secondary_area_code'].nunique()}")


if __name__ == "__main__":
    main()
