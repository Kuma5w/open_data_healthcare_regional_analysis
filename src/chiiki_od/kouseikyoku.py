"""地方厚生局「届出受理医療機関名簿」（施設基準の届出受理状況）の専用パーサー。

厚生局ごとにファイル名やファイルの分け方は違うが、令和8年10・11月時点の名簿は列の並びが同じだった。
  2行目    : 「[令和８年１１月１日 現在」の形の時点
  4行目    : 見出し（項番・都道府県コード・…・種別 の24列）
  5行目〜  : 1行＝1医療機関×1つの届出
  東北厚生局は県ごとのシート、中国四国厚生局（中国5県）は医科・歯科・薬局が1つのファイル。
見出しの行は「項番」で始まる行を探す。区分（医科・歯科・薬局）は parser_options の category で絞る。
"""

from __future__ import annotations

import re
import unicodedata
from pathlib import Path

import pandas as pd
import python_calamine as pc

COLUMNS = {
    "項番": "item_no",
    "都道府県コード": "pref_code",
    "都道府県名": "pref_name",
    "区分": "category",
    "医療機関番号": "facility_number",
    "併設医療機関番号": "attached_facility_number",
    "医療機関記号番号": "facility_symbol",
    "医療機関名称": "facility_name",
    "医療機関所在地（郵便番号）": "postal_code",
    "医療機関所在地（住所）": "address",
    "電話番号": "tel",
    "FAX番号": "fax",
    "病床数": "beds_text",
    "受理届出名称": "filing_name",
    "受理記号": "filing_symbol",
    "受理番号": "filing_number",
    "算定開始年月日": "start_date",
    "個別有効開始年月日": "individual_start_date",
    "備考（見出し）": "remarks_heading",
    "備考（データ）": "remarks_data",
    "市町村コード": "municipality_code",
    "市町村名": "municipality_name",
    "種別コード": "type_code",
    "種別": "type_name",
}
POINT_TABLE = {"医科": "1", "歯科": "3", "薬局": "4"}  # 医療機関コード10桁の3桁目（点数表区分）


def _norm(v) -> str:
    if v is None:
        return ""
    if isinstance(v, float) and v.is_integer():
        v = int(v)
    return unicodedata.normalize("NFKC", str(v)).strip()


def _cell(v) -> str | None:
    if v is None:
        return None
    if isinstance(v, float) and v.is_integer():
        v = int(v)
    s = str(v).replace("\r", "").replace("\n", " ").strip()
    return s or None


def parse_file(path: Path) -> tuple[pd.DataFrame, dict]:
    """1ファイル（全シート）を読む。"""
    wb = pc.CalamineWorkbook.from_path(str(path))
    frames, report = [], {"sheets": {}}
    for sheet in wb.sheet_names:
        rows = wb.get_sheet_by_name(sheet).to_python(skip_empty_area=False)
        head = next((i for i, r in enumerate(rows[:20]) if r and _norm(r[0]) == "項番"), None)
        if head is None:
            report["sheets"][sheet] = "見出しの行（項番）がないため読まない"
            continue
        header = [_norm(x) for x in rows[head]]
        expected = [unicodedata.normalize("NFKC", k) for k in COLUMNS]
        if header[: len(expected)] != expected:
            raise ValueError(f"{path.name}［{sheet}］: 見出しが想定と違います: {header[:24]}")
        as_of = next(
            (m.group(0) for r in rows[:head] for x in r if (m := re.search(r"令和\s*\S+?年\S+?月\S+?日", _norm(x)))),
            None,
        )
        data = [r for r in rows[head + 1 :] if any(_cell(x) for x in r[:14])]
        df = pd.DataFrame(
            [[_cell(x) for x in (list(r) + [None] * 24)[:24]] for r in data],
            columns=list(COLUMNS.values()),
            dtype="string",
        )
        df["sheet"] = sheet
        df["as_of"] = as_of
        frames.append(df)
        report["sheets"][sheet] = {"rows": len(df), "as_of": as_of}
    return pd.concat(frames, ignore_index=True), report


def parse_dataset(ds: dict):
    from .fetch import raw_path

    category = ds.get("parser_options", {}).get("category")
    frames, report = [], {"files": {}}
    for fs in ds["files"]:
        df, rep = parse_file(raw_path(ds["id"], fs))
        n_all = len(df)
        if category:
            df = df[df["category"] == category]
        df.insert(0, "source_file", fs["key"])
        rep["rows_kept"] = len(df)
        rep["rows_other_category"] = n_all - len(df)
        report["files"][fs["key"]] = rep
        frames.append(df)
    df = pd.concat(frames, ignore_index=True)

    # 医療機関コード（10桁）＝都道府県コード＋点数表区分＋医療機関番号（7桁）
    num = df["facility_number"].str.replace(r"\D", "", regex=True)
    bad = num.str.len() != 7
    df["medical_code"] = (df["pref_code"].str.zfill(2) + df["category"].map(POINT_TABLE) + num).where(~bad)
    report["rows"] = len(df)
    report["facilities"] = int(df["medical_code"].nunique())
    report["facility_number_not_7_digits"] = int(bad.sum())
    report["prefectures"] = df["pref_code"].value_counts().sort_index().to_dict()
    report["as_of"] = df["as_of"].value_counts().to_dict()
    missing = sorted(set(f"{i:02d}" for i in range(1, 48)) - set(df["pref_code"].dropna()))
    report["missing_prefectures"] = missing
    print(f"  {len(df):,}行、医療機関 {report['facilities']:,}、都道府県 {len(report['prefectures'])}（時点 {report['as_of']}）")
    if missing:
        print(f"  注意: 名簿のない都道府県 {missing}")
    if bad.any():
        print(f"  注意: 医療機関番号が7桁でない行 {int(bad.sum())}")
    return df, report
