"""医療施設調査（厚生労働省）二次医療圏・市区町村編の表の専用パーサー。

e-Stat で公表されている CSV（Shift_JIS）の形（令和7年で確認）
  1〜2行目 : 調査名・時点・表題
  3行目〜  : 表頭（複数行。結合セルの名残で空欄が多い）
  データ行 : 1列目が「コード＋全角空白＋名前」。コードの桁数で行の種類が分かる
               2桁 都道府県 / 4桁 二次医療圏 / 5桁 市区町村（政令市は区。市の合計行はない）
  記号     : "-" は計数がない（0）

市区町村の行だけを残し、どの二次医療圏の下にあったかを列に入れる。
都道府県・二次医療圏の行は、市区町村の合計と一致するかの検算に使う。
"""

from __future__ import annotations

import re
import unicodedata
from pathlib import Path

import pandas as pd

# 表ごとの値の列（左から順に）
TABLE_COLUMNS = {
    "table1": [
        "hospitals",  # 病院 施設数 総数
        "psychiatric_hospitals",  # 精神科病院
        "general_hospitals",  # 一般病院 総数
        "general_hospitals_with_ltc_beds",  # 一般病院のうち療養病床を有する病院（再掲）
        "regional_support_hospitals",  # 地域医療支援病院（再掲）
        "emergency_hospitals",  # 救急告示病院（再掲）
        "hospital_beds",  # 病院 病床数 総数
        "beds_psychiatric",  # 精神病床
        "beds_infectious",  # 感染症病床
        "beds_tuberculosis",  # 結核病床
        "beds_ltc",  # 療養病床
        "beds_general",  # 一般病床
        "beds_regional_support_hospitals",  # 地域医療支援病院の病床（再掲）
    ],
    "table2": [
        "general_clinics",  # 一般診療所数 総数
        "clinics_with_beds",  # 有床
        "clinics_with_ltc_beds",  # 療養病床を有する一般診療所（再掲）
        "clinics_without_beds",  # 無床
        "dental_clinics",  # 歯科診療所数 総数
        "dental_clinics_with_beds",  # 有床
        "dental_clinics_without_beds",  # 無床
        "clinic_beds",  # 一般診療所の病床数
        "clinic_ltc_beds",  # うち療養病床（再掲）
    ],
}

# 内訳の合計が総数と一致するはずの組
IDENTITIES = {
    "table1": [("hospitals", ["psychiatric_hospitals", "general_hospitals"]),
               ("hospital_beds", ["beds_psychiatric", "beds_infectious", "beds_tuberculosis", "beds_ltc", "beds_general"])],
    "table2": [("general_clinics", ["clinics_with_beds", "clinics_without_beds"]),
               ("dental_clinics", ["dental_clinics_with_beds", "dental_clinics_without_beds"])],
}

_KEY = re.compile(r"^(\d{5}|\d{4}|\d{2})(?!\d)\s*(.*)$")
LEVEL = {2: "prefecture", 4: "secondary_area", 5: "municipality"}


def _value(s: str) -> int:
    s = unicodedata.normalize("NFKC", s).strip().replace(",", "")
    if s in ("-", "−", "―", ""):
        return 0
    if not s.isdigit():
        raise ValueError(f"数値ではない値があります: {s!r}")
    return int(s)


def parse_table(path: Path, value_cols: list[str], encoding: str = "cp932") -> tuple[pd.DataFrame, dict]:
    """1つの表を、都道府県・二次医療圏・市区町村の行を持つ表にする（列 level で区別）。"""
    text = Path(path).read_bytes().decode(encoding)
    lines = text.splitlines()
    title = " ".join(x for x in lines[1].split(",") if x).strip() if len(lines) > 1 else ""
    as_of = next((unicodedata.normalize("NFKC", x).strip() for x in lines[0].split(",") if "月" in x and "日" in x), "")

    rows, area = [], (None, None)
    for line in lines:
        cells = line.split(",")
        key = unicodedata.normalize("NFKC", cells[0]).strip()
        m = _KEY.match(key)
        if not m:
            continue
        code, name = m.group(1), m.group(2).strip()
        values = cells[1 : 1 + len(value_cols)]
        if len(values) != len(value_cols):
            raise ValueError(f"{Path(path).name}: 列の数が合いません（{len(values)}列、期待 {len(value_cols)}列）: {line[:60]}")
        level = LEVEL[len(code)]
        if level == "secondary_area":
            area = (code, name)
        elif level == "prefecture":
            area = (None, None)
        rows.append({
            "code": code,
            "name": name,
            "level": level,
            "secondary_area_code": area[0] if level == "municipality" else (code if level == "secondary_area" else None),
            "secondary_area_name": area[1] if level == "municipality" else (name if level == "secondary_area" else None),
            **{c: _value(v) for c, v in zip(value_cols, values, strict=True)},
        })
    df = pd.DataFrame(rows)
    for c in value_cols:
        df[c] = df[c].astype("Int64")

    # 検算：都道府県・二次医療圏の行は、その下の市区町村の合計と一致するか
    muni = df[df.level == "municipality"]
    mismatches = []
    for lvl, key in (("prefecture", muni["code"].str[:2]), ("secondary_area", muni["secondary_area_code"])):
        sums = muni.groupby(key)[value_cols].sum()
        top = df[df.level == lvl].set_index("code")[value_cols]
        diff = (top - sums.reindex(top.index).fillna(0)).abs().sum(axis=1)
        mismatches += [f"{lvl} {c}" for c in diff[diff > 0].index]
    report = {
        "title": title,
        "as_of": as_of,
        "levels": df["level"].value_counts().to_dict(),
        "national": {c: int(df.loc[df.level == "prefecture", c].sum()) for c in value_cols},
        "subtotal_mismatches": mismatches,
    }
    return df, report


def parse_dataset(ds: dict):
    from .fetch import raw_path

    merged, report = None, {}
    for fs in ds["files"]:
        cols = TABLE_COLUMNS[fs["key"]]
        df, rep = parse_table(raw_path(ds["id"], fs), cols, fs.get("encoding", "cp932"))
        broken = [
            f"{total}≠{'+'.join(parts)}（{int(n)}行）"
            for total, parts in IDENTITIES[fs["key"]]
            if (n := (df[total] != df[parts].sum(axis=1)).sum())
        ]
        rep["identity_mismatches"] = broken
        report[fs["key"]] = rep
        if rep["subtotal_mismatches"]:
            print(f"  注意: {fs['key']} の小計が市区町村の合計と一致しません: {rep['subtotal_mismatches'][:5]}")
        if broken:
            print(f"  注意: {fs['key']} の内訳の合計が総数と一致しません: {broken}")
        muni = df[df.level == "municipality"].drop(columns="level")
        if merged is None:
            merged = muni
        else:
            keys = ["code", "name", "secondary_area_code", "secondary_area_name"]
            n_before = len(merged)
            merged = merged.merge(muni, on=keys, how="outer", indicator=True)
            if (merged["_merge"] != "both").any() or len(merged) != n_before:
                raise ValueError("表どうしで市区町村の行が一致しません")
            merged = merged.drop(columns="_merge")

    out = merged.rename(columns={"code": "municipality_code", "name": "municipality_name"})
    out.insert(2, "pref_code", out["municipality_code"].str[:2])
    out["as_of"] = report[ds["files"][0]["key"]]["as_of"]
    nat = {k: v for r in report.values() for k, v in r["national"].items()}
    print(f"  {out['as_of'].iat[0]}：市区町村 {len(out):,}、病院 {nat.get('hospitals', 0):,}、一般診療所 {nat.get('general_clinics', 0):,}、歯科診療所 {nat.get('dental_clinics', 0):,}")
    return out.sort_values("municipality_code").reset_index(drop=True), report


# ---- 指標スクリプトが使う共通処理 ------------------------------------------------

DATASET = "medical_facility_survey_r7"
POPULATION = "population_jumin_r8"  # 調査の時点（2025年10月1日）に近い令和8年1月1日


def load_facilities(sample: bool = False) -> pd.DataFrame:
    """変換後の表（市区町村・政令市の区ごとの施設数）。"""
    from . import paths

    if sample:
        df = pd.read_csv(paths.FIXTURES / "medical_facility_survey_sample.csv", dtype=str, encoding="utf-8-sig")
        for c in df.columns:
            if c in TABLE_COLUMNS["table1"] + TABLE_COLUMNS["table2"]:
                df[c] = pd.to_numeric(df[c]).astype("Int64")
        return df
    return pd.read_parquet(paths.PROCESSED / f"{DATASET}.parquet")


def load_population(sample: bool = False) -> pd.DataFrame:
    from . import inputs

    return inputs.population(POPULATION, sample=sample)


def per_population(
    facilities: pd.DataFrame,
    population: pd.DataFrame,
    count_cols: list[str],
    value_col: str,
    unit: str,
    digits: int,
    ward_level: bool = False,
) -> tuple[pd.DataFrame, list[str]]:
    """人口10万人あたりの施設数（unit は "municipality" か "koso_kuiki"）。分母は総人口。"""
    from . import areas

    counts = facilities[["municipality_code", *count_cols]].rename(columns={"municipality_code": "code5"})
    if unit == "koso_kuiki":
        res, notes = areas.rate_by_koso(counts, population, count_cols, "pop_total", value_col, 100_000, digits)
        zero_label = "構想区域"
    else:
        res, notes = areas.rate_by_municipality(
            counts, population, count_cols, "pop_total", value_col, 100_000, digits, ward_level=ward_level
        )
        zero_label = "市区町村"
    zero = int((res[count_cols[0]] == 0).sum())
    return res, notes + [f"施設が0の{zero_label} {zero} 件"]
