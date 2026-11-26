"""病床機能報告 公表データ（厚生労働省）の専用パーサー。

公表Excelの形（令和7年度で確認）
  1〜4行目 : 表頭（4階層。結合セルのため、空欄は左の見出しの続き）
  5行目    : 項目名
  6行目    : 必須区分（必須項目・月別必須など）
  7行目〜  : データ（1行＝1医療機関、1病棟、または1病棟×1か月）
列の並びは、留意事項ZIP内「別紙１ データ定義」の該当シートの行の並びと一致する。

数値列の記号（留意事項より）
  "*"                     月別の件数が1〜9件のため秘匿
  "-"（"－"）             任意項目の未報告、条件付き項目の非該当、データ不備
  "未報告又はデータ不備"  必須項目の未報告、データ不備
これらは数値列では欠損にし、元の記号は別表（flags）に「何行目のどの列か」として残す。
なお、定義書で「未回答時にゼロを入力する項目」とされた列では、空欄の回答が0として入っている。
"""

from __future__ import annotations

import io
import re
import unicodedata
import zipfile
from pathlib import Path

import pandas as pd
import python_calamine as pc

HEADER_ROWS = 6
ITEM_ROW = 4

TOKEN_KIND = {
    "*": "secret_1_9",
    "-": "dash",
    "－": "dash",
    "未報告又はデータ不備": "unreported",
}

# 先頭の識別列は英字の列名にする（表頭1段目を正規化した文字列で判定）
KEY_COLUMNS = {
    "病診区分": "hospital_clinic_type",
    "オープンデータ医療機関コード": "od_facility_code",
    "医療機関名": "facility_name",
    "都道府県コード": "pref_code",
    "二次医療圏コード": "secondary_area_code",
    "二次医療圏名": "secondary_area_name",
    "構想区域コード": "koso_kuiki_code",
    "構想区域名": "koso_kuiki_name",
    "市区町村コード": "municipality_code",
    "市区町村名称": "municipality_name",
    "医療機関コード(医科)": "medical_code_ika",
    "医療機関コード(歯科)": "medical_code_shika",
    "医療機関名コード(医科)": "medical_code_ika",  # 令和4・5年度の表記
    "医療機関名コード(歯科)": "medical_code_shika",
    "市町村コード": "municipality_code",  # 令和3年度の表記
    "市町村名称": "municipality_name",
    "オープンデータ病棟コード": "od_ward_code",
    "病棟名": "ward_name",
    "報告月": "report_month",
}
KEY_SCAN = 20  # 識別列は先頭20列の中にある

_NUM = re.compile(r"^-?\d+(\.\d+)?$")


def norm(s) -> str:
    """全角・半角と改行の揺れをならした比較用の文字列。"""
    if s is None or (isinstance(s, float) and pd.isna(s)):
        return ""
    return re.sub(r"\s+", "", unicodedata.normalize("NFKC", str(s)))


def _present(x) -> bool:
    return x is not None and not (isinstance(x, float) and pd.isna(x)) and str(x) != ""


def _clean(s) -> str | None:
    if s is None or (isinstance(s, float) and pd.isna(s)):
        return None
    t = str(s).replace("\r", "").replace("\n", "").strip()
    return t or None


# ---- データ定義（コードブック） --------------------------------------------

def zip_member(z: zipfile.ZipFile, name: str) -> str:
    """ZIPの中のファイル名を探す。令和3〜5年度のZIPはファイル名がShift_JISで、そのままでは文字化けするため、
    読み直した名前と比べる。フォルダの部分は無視して、ファイル名の末尾で一致するものを選ぶ。"""
    for info in z.infolist():
        decoded = info.filename
        if not info.flag_bits & 0x800:  # UTF-8 の印がない名前は cp437 として読まれている
            try:
                decoded = info.filename.encode("cp437").decode("cp932")
            except (UnicodeEncodeError, UnicodeDecodeError):
                pass
        if decoded == name or decoded.rsplit("/", 1)[-1] == name:
            return info.filename
    raise KeyError(f"ZIPの中に {name} がありません")


def load_definition(zip_path: Path, member: str | None, sheet: str, prefix: str) -> pd.DataFrame:
    """データ定義の1シートを、列ごとのコードブックにする。

    病床機能報告は留意事項ZIPの中の xlsx（member で指定）、外来機能報告はデータ定義の xlsx そのもの
    （member は None）を読む。
    """
    if member is None:
        raw = Path(zip_path).read_bytes()
    else:
        with zipfile.ZipFile(zip_path) as z:
            raw = z.read(zip_member(z, member))
    d = pd.read_excel(io.BytesIO(raw), sheet_name=sheet, header=0, dtype=str, engine="calamine")
    d = d.iloc[:, :10]
    d.columns = ["h1", "h2", "h3", "h4", "item", "required", "dtype", "secret", "zero_if_blank", "note"]

    # 表頭の空欄を埋める：上位の段が空欄（＝前の行の続き）なら前の行の値を引き継ぐ
    filled, prev = [], [None] * 4
    for row in d[["h1", "h2", "h3", "h4"]].itertuples(index=False):
        cur, new_branch = [], False
        for k, v in enumerate(row):
            v = _clean(v)
            if v is not None:
                cur.append(v)
                new_branch = True
            else:
                cur.append(None if new_branch else prev[k])
        filled.append(cur)
        prev = cur
    for k, col in enumerate(("h1", "h2", "h3", "h4")):
        d[col] = pd.Series([f[k] for f in filled], index=d.index, dtype="object")

    for c in ("item", "required", "dtype", "note"):
        d[c] = d[c].map(_clean)
    d["secret"] = d["secret"].map(_clean).eq("※")
    d["zero_if_blank"] = d["zero_if_blank"].map(_clean).isin(["○", "〇"])  # 外来機能報告の定義は「〇」も使う
    d.insert(0, "position", range(1, len(d) + 1))

    names = []
    for i, r in d.iterrows():
        is_simple = not (_present(r["h2"]) or _present(r["h3"]))
        key = KEY_COLUMNS.get(norm(r["h1"])) if i < KEY_SCAN and is_simple else None
        names.append(key or f"{prefix}{r['position']:03d}")
    if len(set(names)) != len(names):
        raise ValueError(f"{sheet}: 列名が重複しました（識別列の判定を確認してください）")
    d.insert(1, "column", names)
    d["label"] = [
        " > ".join(dict.fromkeys(str(x) for x in (r.h1, r.h2, r.h3, r.h4, r.item) if _present(x)))
        for r in d.itertuples()
    ]
    d["numeric"] = d["dtype"].eq("数値")
    return d


# ---- 1ファイルの読み込み -----------------------------------------------------

def parse_file(path: Path, codebook: pd.DataFrame, max_mismatch: int | None = None) -> tuple[pd.DataFrame, pd.DataFrame, dict]:
    sheet = pc.CalamineWorkbook.from_path(str(path)).get_sheet_by_index(0)
    rows = sheet.to_python(skip_empty_area=False)
    width = len(codebook)

    items = list(rows[ITEM_ROW]) + [""] * width
    mismatch = [
        (i + 1, _clean(items[i]), codebook["item"].iat[i])
        for i in range(width)
        if norm(items[i]) != norm(codebook["item"].iat[i])
    ]
    # 項目名の言い回しだけが定義書と違う年度がある（令和4年度の病棟票「うち、」の有無など）。
    # その場合はデータセット定義の parser_options.max_item_mismatch で許す数を決める
    if len(mismatch) > (max_mismatch if max_mismatch is not None else max(3, width * 0.05)):
        raise ValueError(
            f"{path.name}: 項目名がデータ定義と {len(mismatch)} 列で一致しません。"
            f"シートや年度の取り違えがないか確認してください。例: {mismatch[:3]}"
        )

    data = [list(r) + [""] * (width - len(r)) for r in rows[HEADER_ROWS:] if any(v not in ("", None) for v in r)]
    cols = list(zip(*data, strict=False)) if data else [()] * width

    out, flag_rows, flag_cols, flag_tokens = {}, [], [], []
    stats = []
    for j, cb in enumerate(codebook.itertuples()):
        values = cols[j] if j < len(cols) else ()
        n_blank = n_zero = 0
        counts = {"secret_1_9": 0, "dash": 0, "unreported": 0, "other": 0}
        if cb.numeric:
            parsed = []
            for i, v in enumerate(values):
                if isinstance(v, (int, float)) and not isinstance(v, bool):
                    parsed.append(float(v))
                    n_zero += v == 0
                elif v is None or (isinstance(v, str) and v.strip() == ""):
                    parsed.append(None)
                    n_blank += 1
                elif isinstance(v, str) and _NUM.match(v.strip()):
                    f = float(v)
                    parsed.append(f)
                    n_zero += f == 0
                else:
                    t = str(v).strip()
                    kind = TOKEN_KIND.get(t, "other")
                    counts[kind] += 1
                    parsed.append(None)
                    flag_rows.append(i)
                    flag_cols.append(cb.column)
                    flag_tokens.append(t)
            s = pd.array(parsed, dtype="Float64")
            nonnull = s[~s.isna()]
            if len(nonnull) == 0 or (nonnull == nonnull.round()).all():
                s = s.astype("Int64")
            out[cb.column] = s
        else:
            texts = []
            for i, v in enumerate(values):
                if isinstance(v, float) and v.is_integer():
                    v = str(int(v))
                t = _clean(v)
                if t in TOKEN_KIND:  # 文字列の列でも記号は欠損にし、記号は flags に残す
                    counts[TOKEN_KIND[t]] += 1
                    flag_rows.append(i)
                    flag_cols.append(cb.column)
                    flag_tokens.append(t)
                    t = None
                else:
                    n_blank += t is None
                texts.append(t)
            out[cb.column] = pd.array(texts, dtype="string")
        stats.append({"column": cb.column, "n_value": len(values) - n_blank - sum(counts.values()),
                      "n_zero": n_zero, "n_blank": n_blank, **{f"n_{k}": v for k, v in counts.items()}})

    df = pd.DataFrame(out)
    flags = pd.DataFrame({"row": pd.array(flag_rows, dtype="int32"),
                          "column": pd.array(flag_cols, dtype="string"),
                          "token": pd.array(flag_tokens, dtype="string")})
    report = {"rows": len(df), "item_name_mismatches": mismatch}
    return df, flags, {"report": report, "stats": pd.DataFrame(stats)}


# ---- データセット全体 --------------------------------------------------------

def parse_dataset(ds: dict) -> tuple[pd.DataFrame, dict, dict]:
    """datasets/<id>.yaml の parser_options に従って、地域別ファイルなどを1つの表にまとめる。"""
    from .fetch import raw_path

    opt = ds["parser_options"]
    files = {f["key"]: f for f in ds["files"]}
    notes = raw_path(ds["id"], files[opt["definition_file"]])
    if not notes.exists():
        raise FileNotFoundError(f"{notes} がありません。留意事項ZIPを取得してください（chiiki-od fetch {ds['id']}）")
    codebook = load_definition(notes, opt.get("definition_member"), opt["definition_sheet"], opt["column_prefix"])

    frames, flag_frames, stats_frames, report = [], [], [], {"files": {}}
    offset = 0
    data_files = [f for f in ds["files"] if f["key"] != opt["definition_file"]]
    for fs in data_files:
        src = raw_path(ds["id"], fs)
        if not src.exists():
            raise FileNotFoundError(f"{src} がありません（chiiki-od fetch {ds['id']} または --from-dir で取り込む）")
        df, flags, info = parse_file(src, codebook, opt.get("max_item_mismatch"))
        if len(data_files) > 1:
            df.insert(0, "source_file", fs["key"])
        flags["row"] = flags["row"] + offset
        offset += len(df)
        frames.append(df)
        flag_frames.append(flags)
        stats_frames.append(info["stats"])
        report["files"][fs["key"]] = info["report"]
        print(f"  読み込み: {fs['key']}（{len(df):,}行）")

    df = pd.concat(frames, ignore_index=True)
    if "report_month" in df.columns:  # 報告月は数値で扱う（0は年間値）
        df["report_month"] = pd.to_numeric(df["report_month"], errors="coerce").astype("Int64")
    df.insert(0, "row_id", pd.array(range(len(df)), dtype="int32"))
    flags = pd.concat(flag_frames, ignore_index=True).rename(columns={"row": "row_id"})

    stats = pd.concat(stats_frames).groupby("column", sort=False).sum().reset_index()
    codebook = codebook.merge(stats, on="column", how="left")

    report["rows"] = len(df)
    report["tokens"] = flags["token"].value_counts().to_dict()
    for key in (["od_ward_code", "report_month"], ["od_ward_code"], ["od_facility_code", "report_month"], ["od_facility_code"]):
        if all(k in df.columns for k in key):
            dup = df.duplicated(key, keep=False)
            report["duplicate_keys"] = {
                "key": key,
                "rows": int(dup.sum()),
                "codes": int(df.loc[dup, key[0]].nunique()),
            }
            if dup.any():
                print(f"  注意: {'+'.join(key)} が重複する行が {int(dup.sum())} 行あります（{report['duplicate_keys']['codes']} コード）")
            break
    extras = {"flags": flags, "__codebook__": codebook}
    return df, report, extras


def koso_kuiki_reference(zip_path: Path, member: str) -> pd.DataFrame:
    """別紙２ 構想区域マスタ → reference/koso_kuiki.csv の形。"""
    with zipfile.ZipFile(zip_path) as z:
        raw = z.read(member)
    m = pd.read_excel(io.BytesIO(raw), header=0, dtype=str, engine="calamine")
    m.columns = ["pref_code", "municipality_code5", "municipality_name", "koso_kuiki_code",
                 "koso_kuiki_name", "secondary_area_code", "secondary_area_name"]
    return m.map(_clean)


# ---- 病棟票の集計 ------------------------------------------------------------

FUNCTIONS = {"高度急性期": "high_acute", "急性期": "acute", "回復期": "recovery", "慢性期": "chronic"}
CLOSED_PREFIX = "休棟中"


def beds_by_koso_function(wards: pd.DataFrame, function_col: str = "w016") -> tuple[pd.DataFrame, list[str]]:
    """病棟票から、構想区域ごと・医療機能ごとの許可病床数（一般 w019 ＋ 療養 w023）を出す。

    休棟中の病棟は beds_closed にまとめ、稼働中の4機能の合計（beds_active）には含めない。
    """
    notes = []
    w = wards.copy()
    na = w["w019"].isna() | w["w023"].isna()
    if na.any():
        notes.append(f"許可病床数が欠損の病棟 {int(na.sum())} 件は、欠損を0として数えた")
    w["beds"] = w["w019"].fillna(0) + w["w023"].fillna(0)
    func = w[function_col].astype("string")
    w["fn"] = func.map(FUNCTIONS)
    w.loc[func.str.startswith(CLOSED_PREFIX, na=False), "fn"] = "closed"
    other = w["fn"].isna()
    if other.any():
        notes.append(f"医療機能が4機能・休棟中以外の病棟 {int(other.sum())} 件（{', '.join(func[other].dropna().unique()[:3])}）は除外")
    w = w[~other]
    keys = ["pref_code", "koso_kuiki_code", "koso_kuiki_name"]
    t = w.pivot_table(index=keys, columns="fn", values="beds", aggfunc="sum", fill_value=0).reset_index()
    for f in [*FUNCTIONS.values(), "closed"]:
        if f not in t.columns:
            t[f] = 0
    t = t.rename(columns={f: f"beds_{f}" for f in [*FUNCTIONS.values(), "closed"]})
    t["beds_active"] = t[[f"beds_{f}" for f in FUNCTIONS.values()]].sum(axis=1)
    t.columns.name = None
    return t, notes
