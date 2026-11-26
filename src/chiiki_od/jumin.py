"""住民基本台帳に基づく人口（総務省）年齢階級別人口（市区町村別）の専用パーサー。

公表Excelの形（令和7年・令和8年で確認）
  1行目 : 「令和8年1月1日住民基本台帳」（時点）
  2行目 : 総数、0歳～4歳、…、95歳～99歳、100歳以上
  3行目 : 団体コード（6桁）、都道府県名、市区町村名、性別、人…
  4行目〜: 1団体につき 計・男・女 の3行。全国（団体コード "-"）、都道府県、市区町村のほか、
          政令市の合計と区、郡の合計、東京都の「島しょ」の合計を含む
  末尾  : 注記（外国人住民の内訳の非公表など）

集計行（郡・島しょ・政令市の合計・都道府県・全国）と市区町村の行が同じ表にあるため、
level 列で区別する。市区町村単位で合計するときは level が municipality と ward の行だけを使う。
"""

from __future__ import annotations

import re

import pandas as pd
import python_calamine as pc

from . import codes

SEX = {"計": "total", "男": "male", "女": "female"}
EXPECTED_KEYS = ["団体コード", "都道府県名", "市区町村名", "性別"]
UNITS = ("municipality", "ward")  # 重複なく足し上げられる単位


def _age_col(label: str) -> str:
    t = re.sub(r"\s+", "", str(label))
    if t == "総数":
        return "pop_total"
    if m := re.fullmatch(r"(\d+)歳～(\d+)歳", t):
        return f"age_{int(m[1]):02d}_{int(m[2]):02d}"
    if m := re.fullmatch(r"(\d+)歳以上", t):
        return f"age_{int(m[1])}plus"
    raise ValueError(f"年齢階級の見出しを読めません: {label!r}")


def _level(code5: str, name: str) -> str:
    if code5 == "00000":
        return "national"
    if codes.is_prefecture_level(code5):
        return "prefecture"
    if code5 in codes.designated_cities():
        return "designated_city"
    if codes.is_designated_ward(code5):
        return "ward"
    if name.endswith("郡"):
        return "county"
    if name == "島しょ":
        return "islands"
    return "municipality"


def parse_file(path) -> tuple[pd.DataFrame, dict]:
    rows = pc.CalamineWorkbook.from_path(str(path)).get_sheet_by_index(0).to_python(skip_empty_area=False)
    title = str(rows[0][0])
    m = re.search(r"((?:令和|平成)\s*\d+年\d+月\d+日)", title)
    as_of = m[1] if m else title
    keys = [str(v).strip() for v in rows[2][:4]]
    if keys != EXPECTED_KEYS:
        raise ValueError(f"{path}: 3行目の見出しが想定と違います: {keys}")
    age_cols = [_age_col(v) for v in rows[1][4:] if str(v).strip()]
    width = 4 + len(age_cols)

    records, footnotes = [], []
    for r in rows[3:]:
        r = list(r) + [""] * (width - len(r))
        sex = str(r[3]).strip()
        if sex not in SEX:
            if str(r[0]).strip():
                footnotes.append(str(r[0]).strip())
            continue
        code = str(r[0]).strip()
        code5 = "00000" if code == "-" else codes.to_code5(code)
        name = str(r[2]).strip()
        name = "" if name == "-" else name
        rec = {
            "municipality_code": code5,
            "pref_name": str(r[1]).strip(),
            "municipality_name": name or str(r[1]).strip(),
            "sex": SEX[sex],
            "level": _level(code5, name),
        }
        for col, v in zip(age_cols, r[4:width], strict=True):
            rec[col] = int(float(v)) if str(v).strip() not in ("", "-") else None
        records.append(rec)

    df = pd.DataFrame(records)
    ages = [c for c in age_cols if c.startswith("age_")]
    for c in ["pop_total", *ages]:
        df[c] = df[c].astype("Int64")

    def span(lo: int, hi: int | None = None) -> list[str]:
        out = []
        for c in ages:
            start = int(re.match(r"age_(\d+)", c)[1])
            if start >= lo and (hi is None or start < hi):
                out.append(c)
        return out

    df["pop_0_14"] = df[span(0, 15)].sum(axis=1).astype("Int64")
    df["pop_15_64"] = df[span(15, 65)].sum(axis=1).astype("Int64")
    df["pop_65plus"] = df[span(65)].sum(axis=1).astype("Int64")
    df["pop_75plus"] = df[span(75)].sum(axis=1).astype("Int64")
    df["age_sum_gap"] = (df["pop_total"] - df[ages].sum(axis=1)).astype("Int64")
    df["as_of"] = as_of

    total = df[(df.level == "national") & (df.sex == "total")]
    units = df[df.level.isin(UNITS) & (df.sex == "total")]
    report = {
        "as_of": as_of,
        "rows": len(df),
        "levels": df[df.sex == "total"]["level"].value_counts().to_dict(),
        "national_total": int(total["pop_total"].iat[0]) if len(total) else None,
        "sum_of_units": int(units["pop_total"].sum()),
        "rows_with_age_sum_gap": int((df["age_sum_gap"] != 0).sum()),
        "max_age_sum_gap": int(df["age_sum_gap"].abs().max()),
        "footnotes": footnotes,
    }
    return df, report


def parse_dataset(ds: dict):
    from .fetch import raw_path

    fs = next(f for f in ds["files"] if f["key"] == "main")
    df, report = parse_file(raw_path(ds["id"], fs))
    if report["national_total"] != report["sum_of_units"]:
        print(f"  注意: 市区町村の合計（{report['sum_of_units']:,}）が全国計（{report['national_total']:,}）と一致しません")
    print(f"  {report['as_of']}：全国 {report['national_total']:,}人、市区町村と区 {report['levels'].get('municipality', 0) + report['levels'].get('ward', 0)}")
    return df, report
