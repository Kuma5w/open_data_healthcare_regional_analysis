"""精神保健福祉資料（630調査）医療機関票（施設概要・診療実績）の専用パーサー。

国立精神・神経医療研究センター 精神保健研究所が公表している Excel（令和7年度 r7_630_shisetu.zip で確認）。
1つのブックに、都道府県と政令指定都市ごとの集計表が11枚ある（医療機関ごとの値はない）。

  施設概要1〜8  精神病床を有する病院（1 全病院、2〜5 医療法の区分、6〜8 精神保健福祉法の区分）
  施設概要9〜11 精神病床を有しない医療機関（9 全施設、10 病院、11 クリニック・診療所）

どの表も列の並びは同じ（表頭は4〜6行目の3段）。精神病床を有しない医療機関の表では、病床・入院の列は空欄。
行は、都道府県（1〜47）、全国、政令指定都市（6桁の団体コード）の順。都道府県の値には政令指定都市の分が含まれる。
記号「-」は、値を計算できない欄（相談員1人当たりの患者数で相談員が0など）。欠損にする。

変換後は1行＝表×地域（都道府県・政令指定都市・全国）。列名は COLUMNS。
「精神病床を有しない医療機関_回答率」のシートは extras の response_rate に入れる。

診療実績（r7_630_shinryou.zip）も同じ形の表が11枚（表頭は5段、列は CLINICAL_COLUMNS）。
加えて「医療保護入院の1年間転帰（都道府県別）」のシートを extras の outcome_1y に入れる（OUTCOME_COLUMNS）。
parser_options.kind が facility（施設概要）か clinical（診療実績）かで読み分ける。
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

# 診療実績（専門外来・届出状況）の表。表頭は5段。人数・件数は6月の1か月、医療機関の数は6月30日時点
_BANDS = ["1_5", "6_10", "11_50", "51_100", "101plus"]
_BAND_WORDS = ["1~5件", "6~10件", "11~50件", "51~100件", "101件~"]


def _claims(start: int, prefix: str, word: str) -> list[tuple[int, str, str]]:
    """「総算定件数・医療機関数（算定有り・件数の階級5つ・算定無し）」の8列。"""
    cols = [(start, f"{prefix}_claims", f"{word} > 総算定件数"), (start + 1, f"{prefix}_facilities_any", f"{word} > 医療機関数 > 算定有り")]
    cols += [(start + 2 + k, f"{prefix}_facilities_{b}", f"算定有り > {w}") for k, (b, w) in enumerate(zip(_BANDS, _BAND_WORDS, strict=True))]
    return cols + [(start + 7, f"{prefix}_facilities_none", f"{word} > 医療機関数 > 算定無し")]


def _yes_no(start: int, prefix: str, word: str) -> list[tuple[int, str, str]]:
    return [(start, f"{prefix}_yes", word), (start + 1, f"{prefix}_no", word)]


CLINICAL_COLUMNS: list[tuple[int, str, str]] = [
    (2, "facilities", "数"),
    (3, "new_admissions_june", "6月の精神病床への新規入院患者の総数"),
    (4, "outpatients_june", "6月の外来受診患者数"),
    (5, "outpatients_june_jiritsu", "自立支援医療"),
    (6, "outpatients_june_welfare", "生活保護"),
    (7, "outpatients_june_psychotherapy", "通院・在宅精神療法"),
    (8, "outpatients_june_continuing_support", "療養生活継続支援加算"),
    (9, "outpatients_june_first_visit", "初診患者数"),
    (10, "home_visits_june", "訪問診療"),
    (11, "house_calls_june", "往診"),
    (12, "home_nursing_june", "訪問看護"),
    (13, "liaison_june_other_dept", "院内他科(延べ件数)"),
    (14, "liaison_june_emergency_center", "救命救急センター(延べ件数)"),
    *_yes_no(15, "clinic_child", "専門外来の設置状況 > 児童・思春期"),
    *_yes_no(17, "clinic_addiction", "専門外来の設置状況 > 依存症"),
    *_yes_no(19, "clinic_dementia", "専門外来の設置状況 > 認知症"),
    *_yes_no(21, "clinic_depression", "専門外来の設置状況 > うつ病"),
    *_yes_no(23, "clinic_developmental", "専門外来の設置状況 > 発達障害"),
    *_yes_no(25, "clinic_eating", "専門外来の設置状況 > 摂食障害"),
    *_yes_no(27, "emergency_center", "救命救急センターの有無"),
    *_yes_no(29, "dementia_center", "認知症疾患医療センターの有無"),
    (31, "psy_emergency_full_time", "常時対応型精神科救急医療施設"),
    (32, "psy_emergency_rotation", "病院群輪番型精神科救急医療施設"),
    (33, "psy_emergency_comorbidity", "身体合併症対応施設"),
    (34, "psy_emergency_outpatient", "外来対応施設"),
    (35, "psy_emergency_nonparticipant_responding", "参加していないが、救急対応を行っている"),
    (36, "psy_emergency_nonparticipant_not_responding", "参加していない上、救急対応を行っていない"),
    *_yes_no(37, "hub_addiction_specialized", "依存症専門医療拠点の有無"),
    *_yes_no(39, "hub_addiction_treatment", "依存症治療拠点の有無"),
    *_yes_no(41, "hub_brain_injury", "高次脳機能障害支援拠点の有無"),
    *_yes_no(43, "hub_eating", "摂食障害治療支援センターの有無"),
    *_yes_no(45, "hub_epilepsy", "てんかん診療拠点の有無"),
    *_yes_no(47, "dpat", "DPAT先遣隊登録の有無"),
    *_claims(49, "cbt_doctor", "認知療法・認知行動療法(医師による場合)"),
    *_claims(57, "cbt_joint", "認知療法・認知行動療法(医師及び看護師が共同して行う場合)"),
    (65, "cbt_facilities_doctor_only", "(医師による場合)のみを算定"),
    (66, "cbt_facilities_joint_only", "(医師及び看護師が共同して行う場合)のみを算定"),
    (67, "cbt_facilities_both", "両方を算定"),
    (68, "cbt_facilities_neither", "いずれも算定していない"),
    *_claims(69, "comorbidity", "精神科身体合併症管理加算"),
    *_yes_no(77, "notif_psy_enhanced", "精神科充実体制加算"),
    *_yes_no(79, "notif_psy_emergency", "精神科救急医療体制加算"),
]
CLINICAL_VALUE_COLUMNS = [name for _, name, _ in CLINICAL_COLUMNS]

# 医療保護入院の1年間転帰（2024年6月に医療保護入院した患者のその後）。表頭は3段。人数のほかは割合（0〜1）
OUTCOME_COLUMNS: list[tuple[int, str, str]] = [
    (2, "admitted", "2024年6月に医療保護入院で入院した合計患者数"),
    (3, "discharge_rate_3m", "3か月時点での退院率"),
    (4, "discharge_rate_6m", "6か月時点での退院率"),
    (5, "discharge_rate_1y", "1年時点での退院率"),
    *[(6 + k, f"planned_stay_{s}", w) for k, (s, w) in enumerate(zip(
        ["lt_2w", "2w_1m", "1m_2m", "2m_3m", "3m", "gt_3m", "unknown"],
        ["2週間未満", "2週間以上1か月未満", "1か月以上2か月未満", "2か月以上3か月未満", "推定された入院月数(※2) > 3か月", "3か月を超える期間", "推定された入院月数(※2) > 不明"], strict=True))],
    *[(13 + k, f"dx_{s}", w) for k, (s, w) in enumerate(zip(
        ["f0", "f00", "f01", "f02_09", "f1", "f10", "stimulants", "other_substances", "f2", "f3", "f30_31", "f32_39",
         "f4", "f5", "f6", "f7", "f8", "f9", "epilepsy", "other", "unknown"],
        ["F0 > 症状性を含む", "F00", "F01", "F02-09", "F1 > 精神作用物質", "F10", "覚せい剤による", "アルコール、覚せい剤を除く",
         "F2 > 統合失調症", "F3 > 気分(感情)障害", "F30‐31", "F32-39", "F4 > 神経症性", "F5 > 生理的障害", "F6 > 成人のパーソナリティ",
         "F7 > 精神遅滞", "F8 > 心理的発達", "F9 > 小児期", "てんかん", "主診断の内訳(※2) > その他", "主診断の内訳(※2) > 不明"], strict=True))],
    *[(34 + k, f"consenter_{s}", w) for k, (s, w) in enumerate(zip(
        ["spouse", "parents", "grandparents", "children", "siblings", "guardian", "court_appointed", "mayor", "other_family", "unknown"],
        ["配偶者", "父母", "祖父母等", "子・孫等", "兄弟姉妹", "後見人又は補佐人", "家庭裁判所が選任した扶養義務者", "市町村長", "その他の家族等", "同意者(※2) > 不明"], strict=True))],
    *[(44 + k, f"committee_{s}", f"実施回数(※2) > {w}") for k, (s, w) in enumerate(zip(
        ["0", "1", "2", "3", "4", "5", "6", "7", "8", "9", "10", "11plus", "unknown"],
        ["0回", "1回", "2回", "3回", "4回", "5回", "6回", "7回", "8回", "9回", "10回", "11回以上", "不明"], strict=True))],
    (57, "committee_patient_participation", "本人参加割合"),
    (58, "committee_family_participation", "家族参加割合"),
    (59, "committee_support_participation", "地域援助事業者参加割合"),
    (60, "extension_none", "延長なし"),
    (61, "extension_any", "延長あり"),
    (62, "extension_1", "延長あり(※2) > 1回"),
    (63, "extension_2", "延長あり(※2) > 2回"),
    (64, "extension_3", "延長あり(※2) > 3回"),
    (65, "extension_4plus", "延長あり(※2) > 4回以上"),
    (66, "extension_unknown", "延長回数不明"),
    (67, "support_referral_rate", "地域援助事業者の紹介があった割合"),
    *[(68 + k, f"status_1y_{s}", f"1年時点入院継続者の入院形態(※2) > {w}") for k, (s, w) in enumerate(zip(
        ["voluntary", "medical_protection", "involuntary", "emergency_involuntary", "urgent", "assessment", "medical_observation", "unknown"],
        ["任意入院", "医療保護入院", "措置入院", "緊急措置入院", "応急入院", "鑑定入院", "医療観察法による入院", "不明"], strict=True))],
]
OUTCOME_VALUE_COLUMNS = [name for _, name, _ in OUTCOME_COLUMNS]
KEY_COLUMNS = ["table_no", "table_name", "level", "area_code", "area_name"]

_TITLE = re.compile(r"(?:施設概要|届出状況)(\d+)\((.+?)\)\((都道府県|政令指定都市)\)")  # NFKC 後の半角括弧


def _norm(s) -> str:
    return re.sub(r"\s+", "", unicodedata.normalize("NFKC", "" if s is None else str(s)))


def _header_labels(rows: list[tuple], top: int, depth: int = 3) -> list[str]:
    """depth 段の表頭（top 行目から）を「段1 > 段2 > …」の見出しにする。

    各段の見出しは、同じ段か上の段に次の見出しが出るまで右へ続く（結合セル）。上の段が変わると下の段は空に戻る。
    """
    width = max(len(rows[top + k]) for k in range(depth))

    def get(k: int, i: int):
        r = rows[top + k]
        return r[i] if i < len(r) else None

    labels, h = [], [""] * depth
    for i in range(width):
        for k in range(depth):
            if get(k, i) is not None:
                h[k] = _norm(get(k, i))
                for j in range(k + 1, depth):
                    h[j] = ""
        labels.append(" > ".join(p for p in h if p))
    return labels


def _check_label(label: str, name: str, word: str) -> bool:
    """列の見出しが期待どおりか。word は見出しの一部（段の区切りは「 > 」）。"""
    if " > ".join(_norm(w) for w in word.split(" > ")) not in label:
        return False
    last = label.split(" > ")[-1]
    if name.endswith("_yes"):
        return last == "有り"
    if name.endswith("_no"):
        return last == "無し"
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


def parse_sheet(rows: list[tuple], title_hint: str = "", columns: list[tuple[int, str, str]] | None = None,
                depth: int = 3) -> tuple[pd.DataFrame, dict]:
    """施設概要・診療実績の1枚を、地域ごとの行にする。表頭の位置は「施設概要n（…）（都道府県）」の行から探す。"""
    columns = COLUMNS if columns is None else columns
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
            labels = _header_labels(rows, i + 1, depth)
            for pos, name, word in columns:
                if not _check_label(labels[pos], name, word):
                    raise ValueError(f"{title_hint}：{pos + 1}列目の見出し「{labels[pos]}」が {name}（{word}）と合いません")
        j = i + 1 + depth  # 表頭の次の行
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
            vals = {nm: _value(row[pos]) if pos < len(row) else None for pos, nm, _ in columns}
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
    report["labels"] = {name: labels[pos] for pos, name, _ in columns} if labels else {}
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


def check_totals(df: pd.DataFrame, value_columns: list[str] | None = None,
                 identity_columns: list[str] | None = None) -> list[str]:
    """都道府県の合計と全国の行、表どうしの内訳（医療法の区分・精神保健福祉法の区分・病院と診療所）を比べる。

    identity_columns：表どうしの内訳を比べる列（省略すると施設数・許可病床・在院患者）。
    """
    msgs = []
    value_columns = VALUE_COLUMNS if value_columns is None else value_columns
    cols = [c for c in value_columns if c in df.columns and c != "patients_per_discharge_counselor"]
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
        idc = identity_columns or (["facilities", "beds_licensed", "inpatients"] if whole == 1 else ["facilities"])
        for c in (c for c in idc if c in w.columns and w[c].notna().any()):
            if (bad := (w[c] - p[c]).abs().gt(1e-6)).any():
                msgs.append(f"表{whole}≠表{'+'.join(map(str, parts))} {c}：{int(bad.sum())}都道府県")
    return msgs


def parse_outcome(rows: list[tuple]) -> tuple[pd.DataFrame, dict]:
    """「医療保護入院の1年間転帰（都道府県別）」のシート（都道府県・全国・政令指定都市）。"""
    out, report, i = [], {"blocks": []}, 0
    while i < len(rows):
        key = _norm(rows[i][0]) if rows[i] and rows[i][0] is not None else ""
        if key not in ("都道府県番号", "政令指定都市番号"):
            i += 1
            continue
        level = "prefecture" if key == "都道府県番号" else "designated_city"
        labels = _header_labels(rows, i, 3)
        for pos, name, word in OUTCOME_COLUMNS:
            if not _check_label(labels[pos], name, word):
                raise ValueError(f"医療保護入院の1年間転帰：{pos + 1}列目の見出し「{labels[pos]}」が {name}（{word}）と合いません")
        j, n = i + 3, 0
        while j < len(rows):
            row = rows[j]
            if not row or (row[0] is None and (len(row) < 2 or row[1] is None)):
                if n:
                    break
                j += 1
                continue
            if isinstance(row[0], str) and row[0].startswith("※"):
                break
            vals = {nm: _value(row[pos]) if pos < len(row) else None for pos, nm, _ in OUTCOME_COLUMNS}
            if row[0] is None and _norm(row[1]) == "全国":
                out.append({"level": "national", "area_code": "00", "area_name": "全国", **vals})
            else:
                out.append({"level": level, "area_code": _area_code(row[0], level), "area_name": _norm(row[1]), **vals})
            n += 1
            j += 1
        report["blocks"].append({"level": level, "rows": n})
        report.setdefault("labels", {name: labels[pos] for pos, name, _ in OUTCOME_COLUMNS})
        i = j
    df = pd.DataFrame(out)
    pref, nat = df[df.level == "prefecture"], df[df.level == "national"]
    if len(nat) and abs(pref["admitted"].sum() - nat["admitted"].iat[0]) > 1e-6:
        report["mismatch"] = f"都道府県の合計 {pref['admitted'].sum():g} ≠ 全国 {nat['admitted'].iat[0]:g}"
    return df, report


KINDS = {
    "facility": ("医療機能・施設概要", COLUMNS, 3),
    "clinical": ("診療実績", CLINICAL_COLUMNS, 5),
}


def parse_file(path: Path, kind: str = "facility") -> tuple[pd.DataFrame, dict[str, pd.DataFrame], dict]:
    """施設概要（kind="facility"）か診療実績（kind="clinical"）のブックを読む。戻り値は（表、別表、報告）。"""
    prefix, columns, depth = KINDS[kind]
    sheets = _workbook_rows(path)
    frames, report, extras = [], {"sheets": {}}, {}
    for title, rows in sheets.items():
        if title.startswith(prefix):
            df, rep = parse_sheet(rows, title, columns, depth)
            frames.append(df)
            report["sheets"][title] = rep["blocks"]
            report.setdefault("labels", rep["labels"])
    if kind == "facility":
        rr_title = next((t for t in sheets if "回答率" in t), None)
        extras["response_rate"] = parse_response_rate(sheets[rr_title]) if rr_title else pd.DataFrame()
    else:
        oc_title = next(t for t in sheets if "転帰" in t and "都道府県" in t)
        extras["outcome_1y"], rep = parse_outcome(sheets[oc_title])
        report["outcome_1y"] = {k: v for k, v in rep.items() if k != "labels"}
        report["outcome_labels"] = rep["labels"]
    df = pd.concat(frames, ignore_index=True)
    as_of = next((_norm(r[0]) for rows in sheets.values() for r in rows[:2] if r and isinstance(r[0], str) and "時点" in r[0]), None)
    df["as_of"] = as_of
    report["as_of"] = as_of
    names = [name for _, name, _ in columns]
    report["total_mismatches"] = check_totals(df, names, names if kind == "clinical" else None)
    return df, extras, report


def parse_dataset(ds: dict):
    from .fetch import raw_path

    kind = ds.get("parser_options", {}).get("kind", "facility")
    (fs,) = ds["files"]
    df, extras, report = parse_file(raw_path(ds["id"], fs), kind)
    labels = report.pop("labels")
    columns = KINDS[kind][1]
    rows = [{"table": "main", "column": name, "position": pos + 1, "label": labels.get(name, "")} for pos, name, _ in columns]
    if kind == "clinical":
        ol = report.pop("outcome_labels")
        rows += [{"table": "outcome_1y", "column": name, "position": pos + 1, "label": ol.get(name, "")} for pos, name, _ in OUTCOME_COLUMNS]
    nat = df[(df.level == "national") & (df.table_no == 1)].iloc[0]
    if kind == "facility":
        print(f"  {report['as_of']}：表 {df['table_no'].nunique()}、行 {len(df):,}。全病院（精神病床あり）"
              f" {int(nat['facilities']):,}、許可精神病床 {int(nat['beds_licensed']):,}、在院患者 {int(nat['inpatients']):,}")
    else:
        oc = extras["outcome_1y"]
        on = oc[oc.level == "national"].iloc[0]
        print(f"  {report['as_of']}：表 {df['table_no'].nunique()}、行 {len(df):,}。全病院 {int(nat['facilities']):,}、"
              f"6月の新規入院 {int(nat['new_admissions_june']):,}。医療保護入院の1年間転帰 {len(oc)}行（全国 {int(on['admitted']):,}人、1年時点の退院率 {on['discharge_rate_1y']:.1%}）")
    for m in report["total_mismatches"][:10]:
        print(f"  注意: {m}")
    df = df.sort_values(["table_no", "level", "area_code"]).reset_index(drop=True)
    return df, report, {**extras, "__codebook__": pd.DataFrame(rows)}


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


CLINICAL = "mental_health_630_clinical_r7"


def load_clinical(sample: bool = False) -> pd.DataFrame:
    """診療実績（表×地域）。"""
    from . import paths

    if sample:
        df = pd.read_csv(paths.FIXTURES / "mental_health_630_clinical_sample.csv", dtype=str, encoding="utf-8-sig")
        for c in df.columns:
            if c in CLINICAL_VALUE_COLUMNS or c == "table_no":
                df[c] = pd.to_numeric(df[c])
        return df
    return pd.read_parquet(paths.PROCESSED / f"{CLINICAL}.parquet")


def load_outcome(sample: bool = False) -> pd.DataFrame:
    """医療保護入院の1年間転帰（都道府県・政令指定都市・全国）。"""
    from . import paths

    if sample:
        df = pd.read_csv(paths.FIXTURES / "mental_health_630_outcome_sample.csv", dtype=str, encoding="utf-8-sig")
        for c in df.columns:
            if c in OUTCOME_VALUE_COLUMNS:
                df[c] = pd.to_numeric(df[c])
        return df
    return pd.read_parquet(paths.PROCESSED / f"{CLINICAL}__outcome_1y.parquet")


# 専門外来：{指標のキー: (診療実績の列の頭, 分母の人口, 関連する拠点などの列)}
SPECIALTY = {
    "child": ("clinic_child", "under20", {}),
    "addiction": ("clinic_addiction", "total", {"hub_addiction_specialized": "hub_addiction_specialized_yes",
                                                 "hub_addiction_treatment": "hub_addiction_treatment_yes"}),
    "dementia": ("clinic_dementia", "65plus", {"dementia_center": "dementia_center_yes"}),
    "depression": ("clinic_depression", "total", {}),
    "developmental": ("clinic_developmental", "total", {}),
    "eating": ("clinic_eating", "total", {"hub_eating": "hub_eating_yes"}),
}


def specialty_clinics(clinical: pd.DataFrame, population: pd.DataFrame, key: str) -> tuple[pd.DataFrame, list[str]]:
    """精神病床を有する病院のうち、専門外来を設置している病院の数（人口100万人あたり）。"""
    col, pop, related = SPECIALTY[key]
    pick = {"hospitals": ("all", "facilities"), "clinic_hospitals": ("all", f"{col}_yes")}
    pick |= {name: ("all", src) for name, src in related.items()}
    out, notes = prefecture_table(clinical, population, pick, pop=pop)
    out["clinic_share_pct"] = rate(out["clinic_hospitals"], out["hospitals"], 100, 1)
    out["clinic_hospitals_per_1m"] = rate(out["clinic_hospitals"], out["population"], 1_000_000, 2)
    if (n := int((out["clinic_hospitals"] == 0).sum())):
        notes.append(f"設置している病院が0の都道府県 {n}")
    order = ["pref_code", "pref_name", "hospitals", "clinic_hospitals", "clinic_share_pct", *related, "population", "clinic_hospitals_per_1m"]
    return out[order], notes


def load_population(sample: bool = False) -> pd.DataFrame:
    from . import inputs

    return inputs.population(POPULATION, sample=sample)


POPULATIONS = {  # 分母の人口：住民基本台帳の列の組
    "total": ["pop_total"],
    "under20": ["pop_0_14", "age_15_19"],
    "65plus": ["pop_65plus"],
}


def prefecture_table(facility: pd.DataFrame, population: pd.DataFrame | None,
                     pick: dict[str, tuple[str, str]], pop: str = "total") -> tuple[pd.DataFrame, list[str]]:
    """都道府県ごとの1行の表。pick は {出力の列名: (表の区分 TABLES のキー, 元の列名)}。

    施設概要・診療実績のどちらの表でも使える（列 level・table_no・area_code が同じ）。
    population を渡すと、住民基本台帳の都道府県の人口（列 population。pop で総人口・20歳未満・65歳以上を選ぶ）を付ける。
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
        p = p.assign(pref_code=p["municipality_code"].str[:2]).set_index("pref_code")[POPULATIONS[pop]].sum(axis=1, min_count=1)
        out["population"] = out["pref_code"].map(p).astype("Int64")
        if (n := int(out["population"].isna().sum())):
            notes.append(f"人口の表に行がない都道府県 {n}（値は欠損）")
    return out, notes


def rate(num: pd.Series, den: pd.Series, scale: float, digits: int) -> pd.Series:
    """num ÷ den × scale（den が0か欠損なら欠損）。"""
    den = den.astype("Float64")
    return (num.astype("Float64") / den.where(den > 0) * scale).round(digits)
