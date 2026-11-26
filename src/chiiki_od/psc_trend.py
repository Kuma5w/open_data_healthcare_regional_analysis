"""在宅医療等連携機能（P・S・C）の年次推移（D.S.氏の方法、FY2020〜2024）。

病床機能報告で毎年追える11項目（P4、S1〜S6、C1〜C4）を、令和7年度（R7）と同じ基準で年度ごとに判定し、
病院ごとの該当項目数（0〜11）を出す。届出（P5・S7）、外来機能報告の件数（P1〜P3）、看取り（P6・C5）は含めない。

年度の読み方：Rn 報告＝その年の7月1日時点の病床＋前年度の実績。R3報告＝FY2020 … R7報告＝FY2024。

様式2の件数（S1〜S6・C4）は、すべての年度で月別票から推計する（推移の物差しをそろえるため。R7も同じ）。
  推計値＝月別の公表値の合計＋非公表（*）の月数×補完値
  補完値＝R7の（年間合計票の実数−月別の公表値の合計）÷ 非公表の月数を、都道府県ごと・項目ごとに求めた値
          （下限1・上限9。その都道府県に非公表の月がない項目は全国の値）
そのため、R7の推移上の判定は、星取り表（年間合計票の実数による判定）と一部ずれる。
病棟票の年間の値（P4・C1〜C3）は、各年度の病棟票をそのまま使う。

年度によって列の位置と見出しが変わるため、令和7年度の列（w137 など）を、見出しで各年度の列に対応づける（item_map）。
"""

from __future__ import annotations

import re
import unicodedata

import numpy as np
import pandas as pd
import pyarrow.parquet as pq

from . import paths
from .areas import safe_code5
from .zaitaku_psc import IMPLAUSIBLE_PER_BED, ITEM_BY_CODE, core_name, judge

TREND_ITEMS = ["P4", "S1", "S2", "S3", "S4", "S5", "S6", "C1", "C2", "C3", "C4"]
REPORTS = {2020: "r3", 2021: "r4", 2022: "r5", 2023: "r6", 2024: "r7"}  # 実績年度 → 報告年度
WARD_COLS = ["w019", "w023", "w137", "w189", "w202", "w241", "w293", "w306", "w319", "w332", "w371", "w397"]
FORM2_COLS = ["m161", "m172", "m173", "m175", "m176", "m177", "m178", "m179", "m181", "m182", "m184"]
ID_COLS = ["od_facility_code", "facility_name", "pref_code", "koso_kuiki_code", "koso_kuiki_name",
           "municipality_code", "medical_code_ika"]
IMPUTE_MIN, IMPUTE_MAX = 1.0, 9.0
FORM2_LABELS = {  # 注記に使う短い名前
    "m161": "在宅患者緊急入院診療加算", "m172": "入退院支援加算1", "m173": "入退院支援加算2", "m175": "入退院支援加算3",
    "m176": "入院時支援加算1", "m177": "入院時支援加算2", "m178": "救急・在宅等支援病床初期加算ほか",
    "m179": "急性期患者支援・在宅患者支援（療養）病床初期加算", "m181": "退院時共同指導料2",
    "m182": "介護支援連携指導料", "m184": "退院前訪問指導料",
}


# ---- 年度をまたぐ列の対応 ----------------------------------------------------------

def _norm(s) -> str:
    s = unicodedata.normalize("NFKC", "" if s is None or (isinstance(s, float) and np.isnan(s)) else str(s))
    s = re.sub(r"【[^】]*】", "", s)
    s = re.sub(r"\s+", "", s)
    s = re.sub(r"\(年間\)", "", s)
    return re.sub(r"[、,・]", "", s)  # 「うち、介護施設」と「うち介護施設」のような表記の揺れ


# 診療報酬改定で名前が変わった項目（その年度の項目名 → 令和7年度の項目名）
RENAMED = {
    "救急・在宅等支援（療養）病床初期加算及び有床診療所一般病床初期加算":
        "救急・在宅等支援病床初期加算、在宅患者支援療養病床初期加算、有床診療所急性期患者支援（療養）病床初期加算、"
        "有床診療所在宅患者支援（療養）病床初期加算",  # 令和4年度改定で再編（R3・R4報告は旧名）
}


def _codebook(dataset_id: str) -> pd.DataFrame:
    return pd.read_csv(paths.CODEBOOKS / f"{dataset_id}.csv", dtype=str)


def match_columns(r7: pd.DataFrame, other: pd.DataFrame, columns: list[str]) -> dict[str, tuple[str | None, str]]:
    """令和7年度の列を、別の年度のコードブックの列に見出しで対応づける。

    1. 見出し（全階層）をならした文字列が一致する列（1つだけのとき）
    2. 項目名をならした文字列と、表頭の1段目（節）が一致する列（1つだけのとき）
    3. 項目名だけが一致する列、または改定で名前が変わった項目（RENAMED）の列（1つだけのとき）
    戻り値：{R7の列: (その年度の列 または None, 対応のしかた)}
    """
    r7 = r7.set_index("column")
    renamed = set(other.loc[other["item"].isin(RENAMED), "column"])
    lab = other["label"].map(_norm)
    item = other["item"].map(lambda s: _norm(RENAMED.get(s, s)))
    h1 = other["h1"].map(_norm)
    out = {}
    for c in columns:
        row = r7.loc[c]
        hit = other.loc[lab == _norm(row["label"]), "column"]
        if len(hit) == 1:
            out[c] = (hit.iat[0], "見出し")
            continue
        hit = other.loc[(item == _norm(row["item"])) & (h1 == _norm(row["h1"])), "column"]
        if len(hit) == 1:
            out[c] = (hit.iat[0], "項目名と節")
            continue
        hit = other.loc[item == _norm(row["item"]), "column"]
        out[c] = (hit.iat[0], "項目名") if len(hit) == 1 else (None, f"対応なし（候補{len(hit)}）")
    return {c: (col, "改定で名前が変わった項目" if col in renamed else how) for c, (col, how) in out.items()}


def item_map() -> pd.DataFrame:
    """11項目の判定に使う列の、年度ごとの対応表（reference/bfr_item_map.csv と同じ形）。"""
    rows = []
    for kind, cols in (("ward", WARD_COLS), ("form2_monthly", FORM2_COLS)):
        base = "ward" if kind == "ward" else "form2_annual"
        r7 = _codebook(f"bed_function_report_r7_{base}")
        labels = r7.set_index("column")["label"]
        for fy, rep in REPORTS.items():
            if rep == "r7":
                m = {c: (c, "令和7年度") for c in cols}
            else:
                m = match_columns(r7, _codebook(f"bed_function_report_{rep}_{kind}"), cols)
            for c, (col, how) in m.items():
                rows.append({"table": kind, "r7_column": c, "r7_label": labels[c], "fiscal_year": fy,
                             "report": rep, "column": col, "how": how})
    return pd.DataFrame(rows)


# ---- 入力（年度ごとの表を、令和7年度の列名にそろえて縦につなぐ） --------------------------

SAMPLE_FILES = {"trend_wards": "psc_trend_wards_sample.csv", "trend_form2": "psc_trend_form2_sample.csv",
                "trend_secret": "psc_trend_secret_sample.csv", "trend_annual": "psc_trend_annual_sample.csv"}
_TEXT = {"od_facility_code", "facility_name", "pref_code", "koso_kuiki_code", "koso_kuiki_name",
         "municipality_code", "medical_code_ika", "column"}


def _read_sample(name: str) -> pd.DataFrame:
    df = pd.read_csv(paths.FIXTURES / name, dtype=str, encoding="utf-8-sig")
    for c in df.columns:
        if c not in _TEXT:
            df[c] = pd.to_numeric(df[c]).astype("Float64" if c in WARD_COLS + FORM2_COLS else "Int64")
    return df


def load_inputs(sample: bool = False) -> dict[str, pd.DataFrame]:
    """推移の判定に使う4つの表と、列の対応表。

    trend_wards  ：病棟票（年度×病棟。列は令和7年度の列名、その年度にない列は欠損）
    trend_form2  ：様式2 月別票（年度×病棟×月。報告月0の行は除く）
    trend_secret ：様式2 月別票で「*」（1〜9件の非公表）だった欄（年度・row_id・令和7年度の列名）
    trend_annual ：令和7年度 様式2 年間合計票（補完値を求めるため）
    item_map     ：列の対応表（reference/bfr_item_map.csv と同じ）
    """
    cmap = item_map()
    if sample:
        out = {k: _read_sample(v) for k, v in SAMPLE_FILES.items()}
        out["item_map"] = cmap
        return out
    P = paths.PROCESSED
    wards, form2, secret = [], [], []
    for fy, rep in REPORTS.items():
        wm = _year_map(cmap, "ward", fy)
        mm = _year_map(cmap, "form2_monthly", fy)
        wpath = P / f"bed_function_report_{rep}_ward.parquet"
        present = set(pq.read_schema(wpath).names)
        w = pd.read_parquet(wpath, columns=[c for c in ID_COLS if c in present] + list(wm.values()))
        wards.append(w.rename(columns={v: k for k, v in wm.items()}).assign(fiscal_year=fy))
        m = pd.read_parquet(P / f"bed_function_report_{rep}_form2_monthly.parquet",
                            columns=["row_id", "od_facility_code", "pref_code", "report_month", *mm.values()])
        m = m[m["report_month"] != 0]
        form2.append(m.rename(columns={v: k for k, v in mm.items()}).assign(fiscal_year=fy))
        f = pd.read_parquet(P / f"bed_function_report_{rep}_form2_monthly__flags.parquet",
                            filters=[("token", "==", "*"), ("column", "in", list(mm.values()))])
        f = f[f["row_id"].isin(m["row_id"])]
        secret.append(f.assign(column=f["column"].map({v: k for k, v in mm.items()}), fiscal_year=fy)[
            ["fiscal_year", "row_id", "column"]])
    annual = pd.read_parquet(P / "bed_function_report_r7_form2_annual.parquet", columns=["od_facility_code", *FORM2_COLS])
    return {
        "trend_wards": pd.concat(wards, ignore_index=True).reindex(columns=["fiscal_year", *ID_COLS, *WARD_COLS]),
        "trend_form2": pd.concat(form2, ignore_index=True).reindex(
            columns=["fiscal_year", "row_id", "od_facility_code", "pref_code", "report_month", *FORM2_COLS]),
        "trend_secret": pd.concat(secret, ignore_index=True),
        "trend_annual": annual,
        "item_map": cmap,
    }


def _year_map(cmap: pd.DataFrame, table: str, fy: int) -> dict[str, str]:
    """その年度にある列だけの {令和7年度の列: その年度の列}。"""
    m = cmap[(cmap["table"] == table) & (cmap["fiscal_year"] == fy)]
    return {r: c for r, c in zip(m["r7_column"], m["column"], strict=True) if isinstance(c, str)}


# ---- 補完値（R7の年間合計票に合わせる） ----------------------------------------------

def calibrate(annual: pd.DataFrame, monthly: pd.DataFrame, secret: pd.DataFrame, pref: pd.Series) -> pd.DataFrame:
    """都道府県×項目の補完値。列 pref_code・column・n_secret・k_raw・k（全国は pref_code="00"）。

    annual：令和7年度の年間合計票、monthly・secret：令和7年度の月別票と「*」の欄、
    pref：令和7年度の病院（オープンデータ医療機関コード）→ 都道府県コード。対象はこの病院だけ。
    """
    a = annual[annual["od_facility_code"].isin(pref.index)].assign(pref_code=lambda d: d["od_facility_code"].map(pref))
    m = monthly[monthly["od_facility_code"].isin(pref.index)].assign(pref_code=lambda d: d["od_facility_code"].map(pref))
    f = secret[secret["row_id"].isin(m["row_id"])].merge(m[["row_id", "pref_code"]], on="row_id")
    groups = [("00", a, m, f)] + [(p, a[a.pref_code == p], m[m.pref_code == p], f[f.pref_code == p])
                                  for p in sorted(pref.dropna().unique())]
    rows = []
    for code, A, M, F in groups:
        n = F["column"].value_counts()
        for c in FORM2_COLS:
            k = (float(A[c].sum()) - float(M[c].sum())) / n[c] if n.get(c, 0) else np.nan
            rows.append({"pref_code": code, "column": c, "n_secret": int(n.get(c, 0)), "k_raw": k,
                         "k": np.nan if np.isnan(k) else float(np.clip(k, IMPUTE_MIN, IMPUTE_MAX))})
    cal = pd.DataFrame(rows)
    nat = cal[cal.pref_code == "00"].set_index("column")["k"]
    cal["k"] = cal["k"].fillna(cal["column"].map(nat))
    # 全国でも非公表の月がない項目（実データにはない）は、1〜9の中央の値にする
    cal["k"] = cal["k"].fillna((IMPUTE_MIN + IMPUTE_MAX) / 2)
    return cal


def estimate_form2(monthly: pd.DataFrame, secret: pd.DataFrame, cal: pd.DataFrame, cols: list[str]) -> pd.DataFrame:
    """1年度分の月別票から、病院ごとの年間の件数を推計する（公表値の合計＋非公表の月数×補完値）。"""
    pub = monthly.groupby("od_facility_code")[cols].sum(min_count=1)
    f = secret[secret["row_id"].isin(monthly["row_id"]) & secret["column"].isin(cols)]
    f = f.merge(monthly[["row_id", "od_facility_code"]], on="row_id")
    nsec = f.pivot_table(index="od_facility_code", columns="column", values="row_id", aggfunc="size", fill_value=0)
    nsec = nsec.reindex(index=pub.index, columns=cols, fill_value=0)
    pref = monthly.drop_duplicates("od_facility_code").set_index("od_facility_code")["pref_code"].reindex(pub.index)
    kk = cal.pivot_table(index="pref_code", columns="column", values="k")
    k = kk.reindex(pref.to_numpy()).fillna(kk.loc["00"]).set_axis(pub.index)
    return pub.astype(float).fillna(0) + nsec * k[cols]


# ---- 年度ごとの判定 ------------------------------------------------------------------

def _short(cmap: pd.DataFrame, c: str) -> str:
    lab = cmap.loc[cmap["r7_column"] == c, "r7_label"]
    return lab.iat[0].split(" > ")[-1] if len(lab) else c


def evaluate(trend_wards: pd.DataFrame, trend_form2: pd.DataFrame, trend_secret: pd.DataFrame,
             trend_annual: pd.DataFrame, item_map: pd.DataFrame) -> tuple[pd.DataFrame, pd.DataFrame, list[str]]:
    """年度ごとに、病院ごとの11項目を判定する。戻り値は（年度×病院の表, 補完値の表, 注記）。"""
    notes: list[str] = []
    years = sorted(int(y) for y in trend_wards["fiscal_year"].unique())
    latest = max(years)
    w7 = trend_wards[trend_wards.fiscal_year == latest]
    pref7 = w7.drop_duplicates("od_facility_code").set_index("od_facility_code")["pref_code"]
    m7 = trend_form2[trend_form2.fiscal_year == latest]
    cal = calibrate(trend_annual, m7, trend_secret[trend_secret.fiscal_year == latest], pref7)

    frames = []
    for fy in years:
        w = trend_wards[trend_wards.fiscal_year == fy]
        idc = [c for c in ID_COLS if c != "od_facility_code"]
        ids = w.groupby("od_facility_code")[idc].first()
        h = ids.join(w.groupby("od_facility_code")[WARD_COLS].sum(min_count=1))
        h["beds"] = h["w019"].fillna(0) + h["w023"].fillna(0)
        n_all = len(h)
        h = h[h["beds"] > 0].copy()
        have_w = set(_year_map(item_map, "ward", fy)) if fy in set(item_map["fiscal_year"]) else set(WARD_COLS)
        for c in (c for c in WARD_COLS if c not in have_w):
            h[c] = 0.0
            notes.append(f"FY{fy}：病棟票に「{_short(item_map, c)}」の列がないため0とした")
        have_m = [c for c in FORM2_COLS if c in set(_year_map(item_map, "form2_monthly", fy))]
        est = estimate_form2(trend_form2[trend_form2.fiscal_year == fy], trend_secret[trend_secret.fiscal_year == fy],
                             cal, have_m)
        h = h.join(est, how="left")
        for c in FORM2_COLS:
            h[c] = h[c].astype(float).fillna(0) if c in h else 0.0
        if missing := [c for c in FORM2_COLS if c not in have_m]:
            notes.append(f"FY{fy}：様式2に「{'」「'.join(_short(item_map, c) for c in missing)}」の項目がないため0とした")
        per_bed = pd.concat([h["w137"], h["w241"]], axis=1).max(axis=1) / h["beds"]
        h["implausible_form1"] = per_bed > IMPLAUSIBLE_PER_BED
        h["has_outpatient"] = True  # 推移には外来機能報告の項目を使わない
        h = h.reset_index()
        j = judge(h, [ITEM_BY_CODE[c] for c in TREND_ITEMS])
        j = j.drop(columns=[c for c in j.columns if c.startswith("is_") or c in ("type", "P_count")])
        out = pd.concat([h, j], axis=1).assign(fiscal_year=fy)
        notes.append(f"FY{fy}（{REPORTS.get(fy, '').upper()}報告）：対象 {len(out):,} 病院"
                     f"（病棟票の {n_all:,} 病院のうち、一般・療養病床がない {n_all - len(out):,} 病院を除く）")
        frames.append(out)
    return pd.concat(frames, ignore_index=True), cal, notes


# ---- 年度をまたぐ病院の照合 ----------------------------------------------------------

def link_to_r7(years: pd.DataFrame) -> pd.DataFrame:
    """各年度の病院を、令和7年度の病院（オープンデータ医療機関コード）に対応づける。

    オープンデータ医療機関コード → 医療機関コード（医科） → 同じ都道府県で法人名を除いた名称（1対1）の順。
    同じ年度に、同じ令和7年度の病院へつながる病院が2つ以上あるときは、先の方法でつながった病院だけを残す。
    戻り値：years と同じ行の順で、列 r7_code（つながらなければ欠損）と link（つないだ方法）。
    """
    r7 = years[years.fiscal_year == years["fiscal_year"].max()][["od_facility_code", "medical_code_ika", "pref_code", "facility_name"]]
    by_od = set(r7["od_facility_code"])
    by_med = (r7.dropna(subset=["medical_code_ika"]).drop_duplicates("medical_code_ika", keep=False)
              .set_index("medical_code_ika")["od_facility_code"])
    r7n = r7.assign(core=r7["facility_name"].map(core_name)).dropna(subset=["core"])
    r7n = r7n[~r7n.duplicated(["pref_code", "core"], keep=False)].set_index(["pref_code", "core"])["od_facility_code"]

    out = pd.DataFrame({"r7_code": years["od_facility_code"].where(years["od_facility_code"].isin(by_od)),
                        "link": None}, index=years.index).astype(object)
    out.loc[out["r7_code"].notna(), "link"] = "1_od"
    miss = out["r7_code"].isna()
    if "medical_code_ika" in years:
        out.loc[miss, "r7_code"] = years.loc[miss, "medical_code_ika"].map(by_med)
        out.loc[miss & out["r7_code"].notna(), "link"] = "2_medical_code"
    miss = out["r7_code"].isna()
    keys = list(zip(years.loc[miss, "pref_code"], years.loc[miss, "facility_name"].map(core_name), strict=True))
    out.loc[miss, "r7_code"] = [r7n.get(k) for k in keys]
    out.loc[miss & out["r7_code"].notna(), "link"] = "3_name"

    rank = out.assign(fy=years["fiscal_year"]).dropna(subset=["r7_code"]).sort_values("link")
    dup = rank.index[rank.duplicated(["fy", "r7_code"], keep="first")]
    out.loc[dup, ["r7_code", "link"]] = None
    return out


# ---- 結果の表（構想区域別・病院別） --------------------------------------------------

ITEM_COLS = [f"n_{c}" for c in TREND_ITEMS]


def fy_label(fy: int) -> str:
    return f"FY{fy}"


def assign_koso(years: pd.DataFrame, link: pd.DataFrame, ref: pd.DataFrame) -> tuple[pd.DataFrame, list[str]]:
    """各年度の病院を、令和7年度の構想区域に割り当てる（列 koso_kuiki_code・koso_kuiki_name を置き換える）。

    令和7年度の病院につながる病院：令和7年度の構想区域（病院別の表と同じ区域にするため）
    つながらない病院（令和7年度までに廃止など）：所在地の市区町村コード→令和7年度の構想区域マスタ。
      マスタにない市区町村（区の再編など）は、その年度に報告された構想区域コードがマスタにあればそれを使う。
    """
    notes = []
    latest = years["fiscal_year"].max()
    r7 = years[years.fiscal_year == latest].set_index("od_facility_code")
    names = ref.drop_duplicates("koso_kuiki_code").set_index("koso_kuiki_code")["koso_kuiki_name"]
    by_mun = ref.drop_duplicates("municipality_code5").set_index("municipality_code5")["koso_kuiki_code"]
    code = link["r7_code"].map(r7["koso_kuiki_code"])
    miss = code.isna()
    code[miss] = years.loc[miss, "municipality_code"].map(safe_code5).map(by_mun)
    miss2 = code.isna()
    code[miss2] = years.loc[miss2, "koso_kuiki_code"].where(years.loc[miss2, "koso_kuiki_code"].isin(names.index))
    if (n := int(miss2.sum())):
        notes.append(f"市区町村コードが構想区域マスタにない病院 {n} 件は、報告された構想区域コードで割り当てた"
                     f"（割り当てられなかった {int(code.isna().sum())} 件は除外）")
    out = years.assign(koso_kuiki_code=code, koso_kuiki_name=code.map(names), pref_code=code.str[:2])
    return out[out["koso_kuiki_code"].notna()], notes


def koso_trend(years: pd.DataFrame, ref: pd.DataFrame) -> pd.DataFrame:
    """構想区域×年度：対象の病院数、該当項目数の合計、1病院あたりの該当項目数、項目ごとの○の病院数。"""
    ok = years.assign(**{f"n_{c}": years[c].eq("○") for c in TREND_ITEMS})
    g = ok.groupby(["koso_kuiki_code", "fiscal_year"]).agg(
        hospitals=("od_facility_code", "size"), items_met_sum=("items_met", "sum"),
        **{c: (c, "sum") for c in ITEM_COLS})
    areas_ = ref.drop_duplicates("koso_kuiki_code")[["pref_code", "koso_kuiki_code", "koso_kuiki_name"]]
    grid = areas_.merge(pd.DataFrame({"fiscal_year": sorted(years["fiscal_year"].unique())}), how="cross")
    out = grid.merge(g, left_on=["koso_kuiki_code", "fiscal_year"], right_index=True, how="left")
    for c in ["hospitals", "items_met_sum", *ITEM_COLS]:
        out[c] = out[c].fillna(0).astype("Int64")
    out["items_per_hospital"] = (out["items_met_sum"] / out["hospitals"].where(out["hospitals"] > 0)).astype("Float64").round(2)
    out["fiscal_year"] = out["fiscal_year"].map(fy_label)
    cols = ["pref_code", "koso_kuiki_code", "koso_kuiki_name", "fiscal_year", "hospitals", "items_met_sum",
            "items_per_hospital", *ITEM_COLS]
    return out[cols].sort_values(["koso_kuiki_code", "fiscal_year"]).reset_index(drop=True)


def hospital_trend(years: pd.DataFrame, link: pd.DataFrame, ids: pd.DataFrame) -> pd.DataFrame:
    """病院×年度（令和7年度の病院につながる病院だけ）。番号と伏せた名前は ids（od_facility_code → hospital_id・hospital_label）。"""
    y = years.assign(r7_code=link["r7_code"]).dropna(subset=["r7_code"])
    y = y.merge(ids, left_on="r7_code", right_on="od_facility_code", suffixes=("", "_r7"))
    r7 = y[y.fiscal_year == y.fiscal_year.max()].set_index("hospital_id")
    y["pref_code"] = y["hospital_id"].map(r7["pref_code"])
    y["koso_kuiki_code"] = y["hospital_id"].map(r7["koso_kuiki_code"])
    y["koso_kuiki_name"] = y["hospital_id"].map(r7["koso_kuiki_name"])
    for c in TREND_ITEMS:
        y[f"{c}_value"] = y[f"{c}_value"].astype("Float64").round(0).astype("Int64")
    y["beds"] = y["beds"].round(0).astype("Int64")
    y["fiscal_year"] = y["fiscal_year"].map(fy_label)
    cols = ["hospital_id", "hospital_label", "pref_code", "koso_kuiki_code", "koso_kuiki_name", "fiscal_year", "beds",
            "items_met", "S_count", "C_count", *TREND_ITEMS, *[f"{c}_value" for c in TREND_ITEMS]]
    return y[cols].sort_values(["hospital_id", "fiscal_year"]).reset_index(drop=True)


def trend_notes(years: pd.DataFrame, link: pd.DataFrame, cal: pd.DataFrame) -> list[str]:
    """リンクのしかたと補完値の要約。"""
    notes = []
    fy = years["fiscal_year"]
    for y in sorted(fy.unique())[:-1]:
        lk = link.loc[fy == y, "link"]
        notes.append(f"FY{y}：令和7年度の病院につながった {int(lk.notna().sum()):,}（医療機関コード（医科）で "
                     f"{int((lk == '2_medical_code').sum())}、名称で {int((lk == '3_name').sum())}）、"
                     f"つながらない {int(lk.isna().sum()):,}（構想区域別の表には含め、病院別の表には含めない）")
    nat = cal[cal.pref_code == "00"].set_index("column")["k"].round(2)
    notes.append("「*」の補完値（全国）：" + "、".join(f"{FORM2_LABELS[c]} {v:g}" for c, v in nat.items()))
    return notes
