"""在宅医療等連携機能：実数基準のP・S・C判定（D.S.氏の方法、千葉県R7で確定した基準）。

病院ごとに在宅医療に関わる18項目を実数の基準と比べ、3つの「在宅医療機能の類型」を判定する。
  P：自院で在宅医療を実施（6項目中3以上）
  S：在宅療養の後方支援（7項目中4以上）
  C：介護施設等との連携（5項目中3以上）
基準は件数が主で、割合は「または」の条件。県内順位や総合スコアは使わない（実数で説明できるようにするため）。

使うデータ（いずれも令和7年度の報告。実績は令和6年度）
  病床機能報告 施設票（看取り）・病棟票 様式1（退院・入棟・退棟）・様式2 年間合計票（算定件数）
  外来機能報告 様式2 の年間値（報告月0。訪問診療・往診・在医総管・施医総管）
  地方厚生局 届出受理医療機関名簿（医科。在宅療養支援病院・在宅療養後方支援病院の受理記号）
"""

from __future__ import annotations

import re
import unicodedata
from dataclasses import dataclass

import pandas as pd

TYPES = {"P": 3, "S": 4, "C": 3}  # 類型ごとの、該当とみなす項目数（過半）


@dataclass(frozen=True)
class Item:
    code: str
    label: str
    count_cols: tuple[str, ...]  # 合計して件数にする列（届出の項目は空）
    count_min: float | None  # 件数の基準（以上）
    ratio_den: str | None = None  # 割合の分母の列
    ratio_min: float | None = None  # 割合の基準（以上。0.05＝5％、退院100件当たり35件＝0.35）
    ward_form1: bool = False  # 病棟票 様式1 の値を使う（患者数が桁違いの病院では判定不能にする）
    filing: str | None = None  # 届出で判定する項目（受理記号の先頭）
    source: str = ""
    basis: str = ""


# 千葉県R7の基準値（D.S.氏のMD「3類型と18項目」）
ITEMS = [
    Item("P1", "訪問診療の実施", ("out_home_visit",), 120, source="外来機能報告 様式2 在宅患者訪問診療料（Ⅰ）",
         basis="地域包括ケア病棟の実績（3か月30回）の年換算"),
    Item("P2", "往診の実施", ("out_ojin",), 10, source="外来機能報告 様式2 往診料",
         basis="機能強化型在支病（緊急往診 年10件）。往診料全体で代用"),
    Item("P3", "在医総管・施医総管", ("out_zaiisoukan", "out_shiisoukan"), 120, source="外来機能報告 様式2",
         basis="月10人の継続管理（目安）"),
    Item("P4", "退院患者への自院在宅医療の提供", ("w397",), 30, "w371", 0.05, ward_form1=True,
         source="病棟票「退院後1か月以内に自院が在宅医療を提供する予定の患者」", basis="実績のある病院の中央値"),
    Item("P5", "在宅療養支援病院の届出", (), None, filing="支援病", source="厚生局 届出受理医療機関名簿"),
    Item("P6", "医療機関以外での看取り", ("f022",), 4, source="施設票", basis="機能強化型在支病（看取り 年4件）"),
    Item("S1", "入退院支援加算1〜3", ("m172", "m173", "m175"), 650, "w371", 0.35, source="様式2 年間合計",
         basis="中央値"),
    Item("S2", "入院時支援加算1・2", ("m176", "m177"), 200, source="様式2 年間合計", basis="中央値"),
    Item("S3", "介護支援連携指導料", ("m182",), 50, "w371", 0.02, source="様式2 年間合計", basis="中央値"),
    Item("S4", "退院時共同指導料2", ("m181",), 24, source="様式2 年間合計",
         basis="地域包括ケア病棟の実績（3か月6回）の年換算"),
    Item("S5", "退院前訪問指導料", ("m184",), 3, source="様式2 年間合計", basis="中央値"),
    Item("S6", "在宅患者の緊急入院の受入", ("m161",), 31, source="様式2 年間合計 在宅患者緊急入院診療加算",
         basis="機能強化型在支病（緊急受入 年31件）"),
    Item("S7", "在宅療養後方支援病院の届出", (), None, filing="在後病", source="厚生局 届出受理医療機関名簿"),
    Item("C1", "介護施設等からの入院", ("w189", "w202"), 100, "w137", 0.10, ward_form1=True,
         source="病棟票 入棟前の場所（介護施設・福祉施設＋介護医療院）", basis="中央値"),
    Item("C2", "介護保険施設（老健・特養・介護医療院）への退院", ("w293", "w306", "w319"), 80, "w241", 0.07,
         ward_form1=True, source="病棟票 退棟先", basis="中央値"),
    Item("C3", "有料老人ホーム等への退院", ("w332",), 50, "w241", 0.04, ward_form1=True,
         source="病棟票 退棟先（社会福祉施設・有料老人ホーム等）", basis="中央値"),
    Item("C4", "在宅患者支援・急性期患者支援の病床初期加算", ("m178", "m179"), 240, source="様式2 年間合計（病床初期加算の2項目の合計）",
         basis="中央値"),
    Item("C5", "医療機関での看取り（在宅療養を担当した患者）", ("f061",), 4, source="施設票",
         basis="機能強化型在支病の看取り要件を準用"),
]
ITEM_BY_CODE = {i.code: i for i in ITEMS}

WARD_COLS = ["w019", "w023", "w137", "w189", "w202", "w241", "w293", "w306", "w319", "w332", "w371", "w397", "w059", "w124"]
FORM2_COLS = ["m161", "m172", "m173", "m175", "m176", "m177", "m178", "m179", "m181", "m182", "m184"]
OUTPATIENT = {"gb057": "out_ojin", "gb058": "out_home_visit", "gb059": "out_zaiisoukan", "gb060": "out_shiisoukan"}
FACILITY_KEYS = ["od_facility_code", "facility_name", "pref_code", "koso_kuiki_code", "koso_kuiki_name",
                 "secondary_area_code", "secondary_area_name", "medical_code_ika"]
IMPLAUSIBLE_PER_BED = 100  # 1床当たりの新規入棟または退棟が年100人を超える病院は、様式1由来の項目を判定不能にする


def build_hospital_table(facility: pd.DataFrame, wards: pd.DataFrame, form2: pd.DataFrame,
                         outpatient: pd.DataFrame, filings: pd.DataFrame) -> tuple[pd.DataFrame, list[str]]:
    """病院ごとの1行の表（18項目の元の値と、届出の有無）を作る。対象は一般・療養病床を持つ病院。"""
    notes: list[str] = []
    w = wards.groupby("od_facility_code")[WARD_COLS].sum(min_count=1)
    w["beds"] = w["w019"].fillna(0) + w["w023"].fillna(0)
    h = facility[FACILITY_KEYS + ["f022", "f061"]].merge(w, left_on="od_facility_code", right_index=True, how="left")
    n_all = len(h)
    h = h[h["beds"].fillna(0) > 0].copy()
    notes.append(f"対象：一般・療養病床を持つ病院 {len(h):,}（施設票 {n_all:,} 病院のうち、病棟票の許可病床（一般＋療養）が0または病棟票にない {n_all - len(h):,} 病院を除く）")

    m = form2.groupby("od_facility_code")[FORM2_COLS].sum(min_count=1)
    h = h.merge(m, left_on="od_facility_code", right_index=True, how="left")
    if (n := int(h[FORM2_COLS].isna().all(axis=1).sum())):
        notes.append(f"様式2 年間合計票に行がない病院 {n}（様式2の項目は0とみなす）")
    h[FORM2_COLS] = h[FORM2_COLS].fillna(0)

    # 外来機能報告とは医療機関コード（医科）でつなぎ、つながらない病院はオープンデータ医療機関コードでつなぐ
    o = outpatient.rename(columns=OUTPATIENT)
    vals = list(OUTPATIENT.values())
    by_med = o.dropna(subset=["medical_code_ika"]).drop_duplicates("medical_code_ika").set_index("medical_code_ika")[vals]
    h = h.merge(by_med, left_on="medical_code_ika", right_index=True, how="left")
    if "od_facility_code" in o.columns:
        by_od = o.dropna(subset=["od_facility_code"]).drop_duplicates("od_facility_code").set_index("od_facility_code")[vals]
        miss = h[vals].isna().all(axis=1)
        filled = h.loc[miss, ["od_facility_code"]].join(by_od, on="od_facility_code")[vals]
        h.loc[miss, vals] = filled.to_numpy()
        if (n := int((miss & h[vals].notna().any(axis=1)).sum())):
            notes.append(f"外来機能報告と医療機関コード（医科）でつながらず、オープンデータ医療機関コードでつないだ病院 {n}")
    no_out = h[vals].isna().all(axis=1)
    if no_out.any():
        notes.append(f"外来機能報告 様式2 とつながらない病院 {int(no_out.sum())}（P1〜P3は判定不能「－」）")
    h["has_outpatient"] = ~no_out

    f = filings.dropna(subset=["medical_code"])
    # 名簿の医療機関コードと一致しない病院は、同じ都道府県で法人名を除いた名称が1対1で一致すれば、その名簿の行を使う
    h["filing_code"] = h["medical_code_ika"].where(h["medical_code_ika"].isin(set(f["medical_code"])))
    by_name = name_matches(h[h["filing_code"].isna()], f)
    h["filing_code"] = h["filing_code"].fillna(h["od_facility_code"].map(by_name))
    if len(by_name):
        notes.append(f"厚生局の名簿と医療機関コードが一致せず、名称（法人名を除く）で照合した病院 {len(by_name)}")
    if (n := int(h["filing_code"].isna().sum())):
        notes.append(f"厚生局の名簿と照合できなかった病院 {n}（届出なしとして扱う）")
    for item in (i for i in ITEMS if i.filing):
        codes_ = set(f.loc[f["filing_symbol"].fillna("").str.startswith(item.filing), "medical_code"])
        h[f"filing_{item.code}"] = h["filing_code"].isin(codes_)
    shien = f[f["filing_symbol"].isin(["支援病１", "支援病２", "支援病３"])]
    kind = shien.sort_values("filing_symbol").drop_duplicates("medical_code").set_index("medical_code")["filing_symbol"]
    h["shien_kind"] = h["filing_code"].map(kind.map({"支援病１": "機能強化型（単独）", "支援病２": "機能強化型（連携）", "支援病３": "従来型"}))

    per_bed = pd.concat([h["w137"], h["w241"]], axis=1).max(axis=1) / h["beds"]
    h["implausible_form1"] = per_bed > IMPLAUSIBLE_PER_BED
    if h["implausible_form1"].any():
        notes.append(f"様式1の患者数が桁違いの病院（1床当たり新規入棟または退棟が年{IMPLAUSIBLE_PER_BED}人超） {int(h['implausible_form1'].sum())}：P4・C1〜C3は判定不能")
    return h.reset_index(drop=True), notes


def judge(h: pd.DataFrame, items: list[Item] = ITEMS, scale: float = 1.0) -> pd.DataFrame:
    """18項目の○×－と、類型を判定する。scale は件数の基準に掛ける倍率（感度分析用）。"""
    out = pd.DataFrame(index=h.index)
    for item in items:
        if item.filing:
            ok = h[f"filing_{item.code}"].astype(bool)
            value = ok.astype(int)
            unknown = pd.Series(False, index=h.index)
        else:
            value = h[list(item.count_cols)].sum(axis=1, min_count=1)
            ok = value >= item.count_min * scale
            if item.ratio_den:
                den = h[item.ratio_den]
                ratio = value / den.where(den > 0)
                ok = ok | (ratio >= item.ratio_min * scale).fillna(False)
            unknown = value.isna()
            if item.ward_form1:
                unknown = unknown | h["implausible_form1"]
            if item.code in ("P1", "P2", "P3"):
                unknown = unknown | ~h["has_outpatient"]
        out[f"{item.code}_value"] = value.where(~unknown)
        out[item.code] = pd.Series("×", index=h.index).mask(ok, "○").mask(unknown, "－")
    for t, need in TYPES.items():
        cols = [i.code for i in items if i.code.startswith(t)]
        out[f"{t}_count"] = (out[cols] == "○").sum(axis=1).astype("Int64")
        out[f"is_{t}"] = out[f"{t}_count"] >= need
    out["type"] = out.apply(lambda r: "・".join(t for t in TYPES if r[f"is_{t}"]) or "—", axis=1)
    out["items_met"] = sum(out[f"{t}_count"] for t in TYPES).astype("Int64")
    return out


_CORP = re.compile(
    r"^(?:(?:社会|特定|特別)?医療法人(?:社団|財団)?|(?:一般|公益)(?:社団|財団)法人|社会福祉法人|(?:地方)?独立行政法人|"
    r"国立大学法人|公立大学法人|学校法人|宗教法人|医療生活協同組合|生活協同組合|社会福祉法人恩賜財団|日本赤十字社)"
)


def core_name(name: str | None) -> str | None:
    """名称から法人名の部分を除いた、比較用の名前（例「医療法人社団 北札幌病院」→「北札幌病院」）。"""
    if not isinstance(name, str):
        return None
    s = unicodedata.normalize("NFKC", name).strip()
    parts = s.split()
    if len(parts) > 1 and _CORP.match(parts[0]):
        s = parts[-1]
    return re.sub(r"\s+", "", s) or None


def name_matches(hospitals: pd.DataFrame, filings: pd.DataFrame) -> dict[str, str]:
    """医療機関コードで照合できなかった病院を、都道府県＋法人名を除いた名称で照合する（1対1のものだけ）。"""
    if hospitals.empty:
        return {}
    f = filings[["pref_code", "facility_name", "medical_code"]].drop_duplicates("medical_code").copy()
    f["core"] = f["facility_name"].map(core_name)
    f = f.dropna(subset=["core"])
    f = f[~f.duplicated(["pref_code", "core"], keep=False)]
    h = hospitals[["od_facility_code", "pref_code", "facility_name"]].copy()
    h["core"] = h["facility_name"].map(core_name)
    h = h[~h.duplicated(["pref_code", "core"], keep=False)]
    m = h.merge(f, on=["pref_code", "core"], how="inner")
    return dict(zip(m["od_facility_code"], m["medical_code"], strict=True))


def letters(n: int) -> str:
    """0→A、25→Z、26→AA …（病院名を伏せた表示用）。"""
    s = ""
    n += 1
    while n:
        n, r = divmod(n - 1, 26)
        s = chr(65 + r) + s
    return s


# ---- 指標スクリプトが使う入口 ------------------------------------------------------

DATASETS = {
    "facility": "bed_function_report_r7_facility",
    "wards": "bed_function_report_r7_ward",
    "form2": "bed_function_report_r7_form2_annual",
    "outpatient": "outpatient_function_report_r7_form2",
    "filings": "kouseikyoku_todokede_ika_r8",
}
SAMPLE_FILES = {k: f"zaitaku_psc_{k}_sample.csv" for k in DATASETS}
_TEXT = set(FACILITY_KEYS) | {"medical_code", "filing_symbol", "hospital_clinic_type", "w016"}


def load_inputs(sample: bool = False) -> dict[str, pd.DataFrame]:
    """判定に使う5つの表。sample=True なら tests/fixtures の合成サンプル。"""
    from . import paths

    cols = {
        "facility": [*FACILITY_KEYS, "f022", "f061"],
        "wards": ["od_facility_code", *WARD_COLS],
        "form2": ["od_facility_code", *FORM2_COLS],
        "outpatient": ["medical_code_ika", "od_facility_code", "report_month", *OUTPATIENT],
        "filings": ["pref_code", "facility_name", "medical_code", "filing_symbol"],
    }
    out = {}
    for key, ds in DATASETS.items():
        if sample:
            df = pd.read_csv(paths.FIXTURES / SAMPLE_FILES[key], dtype=str, encoding="utf-8-sig")
            for c in df.columns:
                if c not in _TEXT:
                    df[c] = pd.to_numeric(df[c]).astype("Int64")
        else:
            df = pd.read_parquet(paths.PROCESSED / f"{ds}.parquet", columns=cols[key])
        df = df[[c for c in cols[key] if c in df.columns]]
        if key == "outpatient":
            df = df[df["report_month"] == 0]  # 報告月0＝年間値
        out[key] = df.reset_index(drop=True)
    return out


def evaluate(facility, wards, form2, outpatient, filings, scale: float = 1.0) -> tuple[pd.DataFrame, list[str]]:
    """病院の表と判定をまとめて返す（病院別・構想区域別の指標の共通の入口）。"""
    h, notes = build_hospital_table(facility, wards, form2, outpatient, filings)
    return pd.concat([h, judge(h, scale=scale)], axis=1), notes


def _id_order(s: pd.Series) -> pd.Series:
    """「4312-B」「4312-AA」を、構想区域の中で A, B, …, Z, AA の順に並べるためのキー。"""
    parts = s.str.split("-", n=1, expand=True)
    return parts[0] + "-" + parts[1].str.len().astype(str).str.zfill(2) + parts[1]


def _anon_order(code: str) -> str:
    import hashlib

    return hashlib.sha1(code.encode()).hexdigest()


def mask_ids(r: pd.DataFrame) -> pd.DataFrame:
    """病院名と医療機関コードの代わりに使う番号（構想区域ごとに A病院・B病院…）。

    伏せた名前の順は、該当項目数の多い順、同じ数の中は医療機関コードから作った乱数の順（公表ファイルの並びと関係しない）。
    r は evaluate の結果（令和7年度・18項目）。年次推移の病院別の表も、この番号を使う。
    戻り値：r と同じ行の順で、列 hospital_id・hospital_label。
    """
    order = r["od_facility_code"].map(_anon_order)
    s = r.assign(_order=order).sort_values(["koso_kuiki_code", "items_met", "_order"], ascending=[True, False, True])
    seq = s.groupby("koso_kuiki_code").cumcount().map(letters)
    ids = pd.DataFrame({"hospital_id": s["koso_kuiki_code"] + "-" + seq,
                        "hospital_label": s["koso_kuiki_name"] + "・" + seq + "病院"}, index=s.index)
    return ids.reindex(r.index)


def hospital_table(r: pd.DataFrame) -> pd.DataFrame:
    """病院別の結果（病院名と医療機関コードは載せず、構想区域ごとに A病院・B病院… と伏せる。mask_ids）。"""
    r = pd.concat([r, mask_ids(r)], axis=1).sort_values("hospital_id", key=_id_order)
    cols = ["hospital_id", "hospital_label", "pref_code", "koso_kuiki_code", "koso_kuiki_name", "type",
            "items_met", "P_count", "S_count", "C_count"]
    cols += [i.code for i in ITEMS] + [f"{i.code}_value" for i in ITEMS] + ["shien_kind"]
    out = r[cols].reset_index(drop=True)
    for i in ITEMS:
        out[f"{i.code}_value"] = out[f"{i.code}_value"].astype("Float64").round(0).astype("Int64")
    return out


def koso_table(r: pd.DataFrame, ref: pd.DataFrame) -> pd.DataFrame:
    """構想区域ごとの、類型に該当する病院の数。対象病院のない区域も0で残す。"""
    g = r.assign(
        any_=r["is_P"] | r["is_S"] | r["is_C"], pc=r["is_P"] & r["is_C"]
    ).groupby("koso_kuiki_code").agg(
        hospitals=("od_facility_code", "size"),
        hospitals_p=("is_P", "sum"),
        hospitals_s=("is_S", "sum"),
        hospitals_c=("is_C", "sum"),
        hospitals_any=("any_", "sum"),
        hospitals_pc=("pc", "sum"),
    )
    areas = ref.drop_duplicates("koso_kuiki_code")[["pref_code", "koso_kuiki_code", "koso_kuiki_name"]]
    out = areas.merge(g, left_on="koso_kuiki_code", right_index=True, how="left")
    for c in g.columns:
        out[c] = out[c].fillna(0).astype("Int64")
    return out.sort_values("koso_kuiki_code").reset_index(drop=True)


def summary_notes(r: pd.DataFrame) -> list[str]:
    n = {t: int(r[f"is_{t}"].sum()) for t in TYPES}
    any_ = int((r["is_P"] | r["is_S"] | r["is_C"]).sum())
    pc = int((r["is_P"] & r["is_C"]).sum())
    return [f"判定した病院 {len(r):,}：P {n['P']:,}、S {n['S']:,}、C {n['C']:,}、いずれか {any_:,}、PかつC {pc:,}"]
