"""精神保健福祉資料（630調査）医療機関票 施設概要の専用パーサー。

国立精神・神経医療研究センター 精神保健研究所が公表している Excel（令和7年度 r7_630_shisetu.zip で確認）。
1つのブックに、都道府県と政令指定都市ごとの集計表が11枚ある（医療機関ごとの値はない）。

  施設概要1〜8  精神病床を有する病院（1 全病院、2〜5 医療法の区分、6〜8 精神保健福祉法の区分）
  施設概要9〜11 精神病床を有しない医療機関（9 全施設、10 病院、11 クリニック・診療所）

どの表も列の並びは同じ（表頭は4〜6行目の3段）。精神病床を有しない医療機関の表では、病床・入院の列は空欄。
行は、都道府県（1〜47）、全国、政令指定都市（6桁の団体コード）の順。都道府県の値には政令指定都市の分が含まれる。
記号「-」は、値を計算できない欄（相談員1人当たりの患者数で相談員が0など）。欠損にする。

変換後は1行＝表×地域（都道府県・政令指定都市・全国）。列名は COLUMNS。
「精神病床を有しない医療機関_回答率」のシートは extras の response_rate に入れる。
"""

from __future__ import annotations

import re
import unicodedata
import zipfile
from pathlib import Path

import pandas as pd

from . import codes

# 表頭の列位置（0始まり）→ 列名と、表頭に含まれるはずの語（並びが変わったら止めるため）
COLUMNS: list[tuple[int, str, str]] = [
    (2, "facilities", "数"),  # 病院数（精神病床なしの表は施設数・医療機関数）
    (3, "emergency_admission_hospitals", "応急入院指定"),
    (4, "wards_active", "稼働中"),
    (5, "wards_closed", "休床中"),
    (6, "beds_notified", "届出病床数"),
    (7, "beds_licensed", "許可精神病床数"),
    (8, "beds_involuntary_capable", "措置入院受入可能病床数"),
    (9, "beds_designated", "指定病床数"),
    (10, "inpatients", "在院患者数"),
    (11, "wards_with_payphone", "公衆電話"),
    (12, "seclusion_rooms", "保護室"),
    (13, "seclusion_rooms_with_toilet", "トイレ"),
    (14, "seclusion_rooms_with_camera", "カメラ"),
    (15, "psychiatrists_ft", "精神科医師数"),
    (16, "psychiatrists_pt", "精神科医師数"),
    (17, "designated_physicians_ft", "精神保健指定医"),
    (18, "designated_physicians_pt", "精神保健指定医"),
    (19, "specified_physicians_ft", "特定医師"),
    (20, "specified_physicians_pt", "特定医師"),
    (21, "nurses_ft", "看護師"),
    (22, "nurses_pt", "看護師"),
    (23, "nurses_cns_ft", "専門看護師"),
    (24, "nurses_cns_pt", "専門看護師"),
    (25, "nurses_certified_ft", "認定看護師"),
    (26, "nurses_certified_pt", "認定看護師"),
    (27, "nurses_specified_act_psy_ft", "薬剤投与」に関連"),
    (28, "nurses_specified_act_psy_pt", "薬剤投与」に関連"),
    (29, "nurses_specified_act_other_ft", "薬剤投与」以外"),
    (30, "nurses_specified_act_other_pt", "薬剤投与」以外"),
    (31, "assistant_nurses_ft", "准看護師"),
    (32, "assistant_nurses_pt", "准看護師"),
    (33, "nursing_aides_ft", "看護補助者"),
    (34, "nursing_aides_pt", "看護補助者"),
    (35, "physical_therapists_ft", "理学療法士"),
    (36, "physical_therapists_pt", "理学療法士"),
    (37, "physical_therapists_ft_facilities", "理学療法士"),
    (38, "physical_therapists_pt_facilities", "理学療法士"),
    (39, "occupational_therapists_ft", "作業療法士"),
    (40, "occupational_therapists_pt", "作業療法士"),
    (41, "occupational_therapists_ft_facilities", "作業療法士"),
    (42, "occupational_therapists_pt_facilities", "作業療法士"),
    (43, "psychiatric_social_workers_ft", "精神保健福祉士"),
    (44, "psychiatric_social_workers_pt", "精神保健福祉士"),
    (45, "psychiatric_social_workers_ft_facilities", "精神保健福祉士"),
    (46, "psychiatric_social_workers_pt_facilities", "精神保健福祉士"),
    (47, "psychologists_ft", "臨床心理技術者"),
    (48, "psychologists_pt", "臨床心理技術者"),
    (49, "psychologists_ft_facilities", "臨床心理技術者"),
    (50, "psychologists_pt_facilities", "臨床心理技術者"),
    (51, "certified_psychologists_ft", "公認心理師有資格者"),
    (52, "certified_psychologists_pt", "公認心理師有資格者"),
    (53, "certified_psychologists_ft_facilities", "公認心理師有資格者"),
    (54, "certified_psychologists_pt_facilities", "公認心理師有資格者"),
    (55, "discharge_counselors", "退院後生活環境相談員配置数"),
    (56, "discharge_counselors_psw", "精神保健福祉士の人数"),
    (57, "discharge_counselors_nurses", "看護職員の人数"),
    (58, "discharge_counselors_ot", "作業療法士の人数"),
    (59, "discharge_counselors_sw", "社会福祉士の人数"),
    (60, "discharge_counselors_psychologists", "公認心理師の人数"),
    (61, "discharge_counselors_trained", "研修を修了"),
    (62, "inpatients_medical_protection", "医療保護入院患者数"),
    (63, "inpatients_involuntary", "措置入院患者数"),
    (64, "patients_per_discharge_counselor", "1人当たり"),
]
VALUE_COLUMNS = [name for _, name, _ in COLUMNS]
KEY_COLUMNS = ["table_no", "table_name", "level", "area_code", "area_name"]

_TITLE = re.compile(r"施設概要(\d+)\((.+?)\)\((都道府県|政令指定都市)\)")  # NFKC 後の半角括弧


def _norm(s) -> str:
    return re.sub(r"\s+", "", unicodedata.normalize("NFKC", "" if s is None else str(s)))


def _header_labels(rows: list[tuple], top: int) -> list[str]:
    """3段の表頭（top〜top+2 行目）を「段1 > 段2 > 段3」の見出しにする。

    段1は次の見出しまで右へ続く（結合セル）。段2は段1が変わるか次の段2が出るまで続く。段3は列ごと。
    """
    width = max(len(rows[top + k]) for k in range(3))

    def get(k: int, i: int):
        r = rows[top + k]
        return r[i] if i < len(r) else None

    labels, h1, h2 = [], "", ""
    for i in range(width):
        if get(0, i) is not None:
            h1, h2 = _norm(get(0, i)), ""
        if get(1, i) is not None:
            h2 = _norm(get(1, i))
        h3 = _norm(get(2, i)) if get(2, i) is not None else ""
        labels.append(" > ".join(p for p in (h1, h2, h3) if p))
    return labels


def _check_label(label: str, name: str, word: str) -> bool:
    if _norm(word) not in label:
        return False
    last = label.split(" > ")[-1]
    if name.endswith("_ft_facilities"):
        return last.startswith("常勤配置")
    if name.endswith("_pt_facilities"):
        return last.startswith("非常勤配置")
    if name.endswith("_ft"):
        return last.startswith("常勤") and "配置" not in last
    if name.endswith("_pt"):
        return last.startswith("非常勤") and "配置" not in last
    return True


def _value(v):
    if v is None:
        return None
    if isinstance(v, str):
        s = v.strip()
        if s in ("-", "－", "―", ""):
            return None
        return float(s.replace(",", ""))
    return v


def _area_code(v, level: str) -> str:
    if level == "prefecture":
        return f"{int(v):02d}"
    return codes.to_code5(str(v).strip().zfill(6))


def parse_sheet(rows: list[tuple], title_hint: str = "") -> tuple[pd.DataFrame, dict]:
    """施設概要の1枚を、地域ごとの行にする。表頭の位置は「施設概要n（…）（都道府県）」の行から探す。"""
    out, report = [], {"sheet": title_hint, "blocks": []}
    i = 0
    labels = None
    while i < len(rows):
        first = rows[i][0] if rows[i] else None
        m = _TITLE.search(_norm(first)) if isinstance(first, str) else None
        if not m:
            i += 1
            continue
        table_no, table_name, kind = int(m.group(1)), m.group(2), m.group(3)
        level = "prefecture" if kind == "都道府県" else "designated_city"
        if level == "prefecture":
            labels = _header_labels(rows, i + 1)
            for pos, name, word in COLUMNS:
                if not _check_label(labels[pos], name, word):
                    raise ValueError(f"{title_hint}：{pos + 1}列目の見出し「{labels[pos]}」が {name}（{word}）と合いません")
        j = i + 4  # 表頭3段の次の行
        n = 0
        while j < len(rows):
            row = rows[j]
            key, name = (row[0], row[1]) if len(row) > 1 else (row[0] if row else None, None)
            if isinstance(key, str) and (key.startswith("※") or _TITLE.search(_norm(key))):
                break
            if name is None and key is None:
                if n:
                    break
                j += 1
                continue
            vals = {nm: _value(row[pos]) if pos < len(row) else None for pos, nm, _ in COLUMNS}
            if key is None and _norm(name) == "全国":
                out.append({"table_no": table_no, "table_name": table_name, "level": "national",
                            "area_code": "00", "area_name": "全国", **vals})
            else:
                out.append({"table_no": table_no, "table_name": table_name, "level": level,
                            "area_code": _area_code(key, level), "area_name": _norm(name), **vals})
            n += 1
            j += 1
        report["blocks"].append({"table_no": table_no, "level": level, "rows": n})
        i = j
    df = pd.DataFrame(out)
    report["labels"] = {name: labels[pos] for pos, name, _ in COLUMNS} if labels else {}
    return df, report


def parse_response_rate(rows: list[tuple]) -> pd.DataFrame:
    """「精神病床を有しない医療機関_回答率」のシート（都道府県・政令指定都市・全国）。"""
    out, level = [], "prefecture"
    for row in rows:
        if not row or len(row) < 5:
            continue
        key, name, a, b, rate = row[:5]
        if isinstance(key, str) and "政令指定" in key:
            level = "designated_city"
            continue
        if not isinstance(a, (int, float)) or not isinstance(b, (int, float)):
            continue
        if key is None and _norm(name) == "全国":
            out.append({"level": "national", "area_code": "00", "area_name": "全国",
                        "respondents": a, "distributed": b, "response_rate": rate})
        else:
            out.append({"level": level, "area_code": _area_code(key, level), "area_name": _norm(name),
                        "respondents": a, "distributed": b, "response_rate": rate})
    return pd.DataFrame(out)


def _workbook_rows(path: Path) -> dict[str, list[tuple]]:
    import io

    import openpyxl

    if path.suffix.lower() == ".zip":
        with zipfile.ZipFile(path) as z:
            members = [m for m in z.namelist() if m.lower().endswith(".xlsx")]
            if len(members) != 1:
                raise ValueError(f"{path.name} の中に Excel が1つではありません：{members}")
            data = io.BytesIO(z.read(members[0]))
    else:
        data = path
    wb = openpyxl.load_workbook(data, read_only=True, data_only=True)
    try:
        return {ws.title: list(ws.iter_rows(values_only=True)) for ws in wb.worksheets}
    finally:
        wb.close()


def check_totals(df: pd.DataFrame) -> list[str]:
    """都道府県の合計と全国の行、表どうしの内訳（医療法の区分・精神保健福祉法の区分・病院と診療所）を比べる。"""
    msgs = []
    cols = [c for c in VALUE_COLUMNS if c in df.columns and c != "patients_per_discharge_counselor"]
    pref = df[df.level == "prefecture"]
    nat = df[df.level == "national"].set_index("table_no")
    sums = pref.groupby("table_no")[cols].sum(min_count=1)
    for t in sums.index:
        if t not in nat.index:
            continue
        for c in cols:
            a, b = sums.at[t, c], nat.at[t, c]
            if pd.notna(b) and pd.notna(a) and abs(a - b) > 1e-6:
                msgs.append(f"表{t} {c}：都道府県の合計 {a:g} ≠ 全国 {b:g}")
    tab = pref.set_index(["table_no", "area_code"])[cols]
    for whole, parts in ((1, [2, 3, 4, 5]), (1, [6, 7, 8]), (9, [10, 11])):
        present = set(tab.index.get_level_values(0))
        if whole not in present or not set(parts) <= present:
            continue
        w = tab.loc[whole]
        p = sum(tab.loc[k] for k in parts)
        for c in ["facilities", "beds_licensed", "inpatients"] if whole == 1 else ["facilities"]:
            if (bad := (w[c] - p[c]).abs().gt(1e-6)).any():
                msgs.append(f"表{whole}≠表{'+'.join(map(str, parts))} {c}：{int(bad.sum())}都道府県")
    return msgs


def parse_file(path: Path) -> tuple[pd.DataFrame, pd.DataFrame, dict]:
    sheets = _workbook_rows(path)
    frames, report = [], {"sheets": {}}
    for title, rows in sheets.items():
        if title.startswith("医療機能・施設概要"):
            df, rep = parse_sheet(rows, title)
            frames.append(df)
            report["sheets"][title] = rep["blocks"]
            report.setdefault("labels", rep["labels"])
    rr_title = next((t for t in sheets if "回答率" in t), None)
    rr = parse_response_rate(sheets[rr_title]) if rr_title else pd.DataFrame()
    df = pd.concat(frames, ignore_index=True)
    as_of = next((_norm(r[0]) for rows in sheets.values() for r in rows[:2] if r and isinstance(r[0], str) and "時点" in r[0]), None)
    df["as_of"] = as_of
    report["as_of"] = as_of
    report["total_mismatches"] = check_totals(df)
    return df, rr, report


def parse_dataset(ds: dict):
    from .fetch import raw_path

    (fs,) = ds["files"]
    df, rr, report = parse_file(raw_path(ds["id"], fs))
    labels = report.pop("labels")
    codebook = pd.DataFrame([{"column": name, "position": pos + 1, "label": labels.get(name, "")}
                             for pos, name, _ in COLUMNS])
    nat = df[(df.level == "national") & (df.table_no == 1)].iloc[0]
    print(f"  {report['as_of']}：表 {df['table_no'].nunique()}、行 {len(df):,}。全病院（精神病床あり）"
          f" {int(nat['facilities']):,}、許可精神病床 {int(nat['beds_licensed']):,}、在院患者 {int(nat['inpatients']):,}")
    for m in report["total_mismatches"][:10]:
        print(f"  注意: {m}")
    df = df.sort_values(["table_no", "level", "area_code"]).reset_index(drop=True)
    return df, report, {"response_rate": rr, "__codebook__": codebook}


# ---- 指標スクリプトが使う共通処理 ------------------------------------------------

DATASET = "mental_health_630_facility_r7"
POPULATION = "population_jumin_r8"  # 調査の時点（令和7年6月30日）から半年後。ほかの人口あたりの指標とそろえる
TABLES = {"all": 1, "public": 6, "designated": 7, "nondesignated": 8}  # 精神病床を有する病院：全体と精神保健福祉法の区分
TABLE_LABELS = {"public": "国立・都道府県立精神科病院等", "designated": "指定病院", "nondesignated": "非指定病院"}


def load_facility(sample: bool = False) -> pd.DataFrame:
    """変換後の表（表×地域）。"""
    from . import paths

    if sample:
        df = pd.read_csv(paths.FIXTURES / "mental_health_630_sample.csv", dtype=str, encoding="utf-8-sig")
        for c in df.columns:
            if c in VALUE_COLUMNS or c == "table_no":
                df[c] = pd.to_numeric(df[c])
        return df
    return pd.read_parquet(paths.PROCESSED / f"{DATASET}.parquet")


def load_population(sample: bool = False) -> pd.DataFrame:
    from . import inputs

    return inputs.population(POPULATION, sample=sample)


def prefecture_table(facility: pd.DataFrame, population: pd.DataFrame | None,
                     pick: dict[str, tuple[str, str]]) -> tuple[pd.DataFrame, list[str]]:
    """都道府県ごとの1行の表。pick は {出力の列名: (表の区分 TABLES のキー, 元の列名)}。

    population を渡すと、住民基本台帳の都道府県の総人口（列 population）を付ける。
    """
    notes = []
    pref = facility[facility["level"] == "prefecture"]
    out = pd.DataFrame({"pref_code": sorted(pref["area_code"].unique())})
    out["pref_name"] = out["pref_code"].map(codes.PREFECTURES)
    for name, (kind, col) in pick.items():
        t = pref[pref["table_no"] == TABLES[kind]].set_index("area_code")[col]
        out[name] = out["pref_code"].map(t).astype("Int64")  # 人数・病床数・施設数（整数）
    if population is not None:
        p = population[population["level"] == "prefecture"]
        p = p.assign(pref_code=p["municipality_code"].str[:2]).set_index("pref_code")["pop_total"]
        out["population"] = out["pref_code"].map(p).astype("Int64")
        if (n := int(out["population"].isna().sum())):
            notes.append(f"人口の表に行がない都道府県 {n}（値は欠損）")
    return out, notes


def rate(num: pd.Series, den: pd.Series, scale: float, digits: int) -> pd.Series:
    """num ÷ den × scale（den が0か欠損なら欠損）。"""
    den = den.astype("Float64")
    return (num.astype("Float64") / den.where(den > 0) * scale).round(digits)
