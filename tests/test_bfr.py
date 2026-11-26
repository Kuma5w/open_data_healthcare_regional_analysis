"""病床機能報告パーサーを、公表ファイルと同じ形の小さな合成Excelで確かめる。"""

import io
import zipfile

import openpyxl
import pandas as pd
import pytest

from chiiki_od import bfr

MEMBER = "別紙１_データ定義.xlsx"
SHEET = "病床様式2病棟票"

# データ定義：表頭4段（空欄は続き）、項目名、必須区分、データ型、秘匿化、未回答ゼロ、備考
DEFINITION = [
    ["オープンデータ表頭", None, None, None, "項目名", "必須区分", "データ型", "秘匿化項目", "未回答時にゼロを入力する項目", "備考"],
    ["オープンデータ\n医療機関コード", None, None, None, "オープンデータ\n医療機関コード\n(R7)", None, "文字列", None, None, None],
    ["医療機関名", None, None, None, "医療機関名", None, "文字列", None, None, None],
    ["オープンデータ\n病棟コード", None, None, None, "病棟コード\n（R7）", None, "文字列", None, None, None],
    ["報告月", None, None, None, "報告月", "月別必須", "数値", None, None, "0は年間値を示す"],
    ["１．算定する入院料", "入院基本料", "急性期一般入院基本料", None, "急性期一般入院基本料", "月別必須", "数値", "※", "○", None],
    [None, None, "地域一般入院基本料", None, "地域一般入院基本料", "月別必須", "数値", "※", "○", None],
    [None, "特定入院料", "救命救急入院料１", None, "救命救急入院料１", "月別必須", "数値", "※", "○", None],
    ["２．平均在院日数", None, None, None, "平均在院日数", "任意項目", "数値", None, None, None],
]

ITEMS = [r[4] for r in DEFINITION[1:]]
DATA = [
    ["0101", "A病院", "0101100", 1, 0, 12, "*", 15.5],
    ["0101", "A病院", "0101100", 2, "未報告又はデータ不備", 30, 0, "-"],
    ["0202", "B病院", "0202100", 1, 5, "-", 3, 20],
]


def _xlsx(rows) -> bytes:
    wb = openpyxl.Workbook()
    ws = wb.active
    for r in rows:
        ws.append(r)
    buf = io.BytesIO()
    wb.save(buf)
    return buf.getvalue()


@pytest.fixture
def files(tmp_path):
    notes = tmp_path / "notes.zip"
    wb = openpyxl.Workbook()
    wb.active.title = SHEET
    for r in DEFINITION:
        wb.active.append(r)
    buf = io.BytesIO()
    wb.save(buf)
    with zipfile.ZipFile(notes, "w") as z:
        z.writestr(MEMBER, buf.getvalue())

    width = len(ITEMS)
    header = [["見出し"] * width, [""] * width, [""] * width, [""] * width, ITEMS, ["月別必須"] * width]
    data = tmp_path / "main.xlsx"
    data.write_bytes(_xlsx(header + DATA))
    return notes, data


def test_definition_fills_headers_and_names_keys(files):
    notes, _ = files
    cb = bfr.load_definition(notes, MEMBER, SHEET, "m")
    assert cb["column"].tolist()[:4] == ["od_facility_code", "facility_name", "od_ward_code", "report_month"]
    assert cb["column"].tolist()[4:] == ["m005", "m006", "m007", "m008"]
    # 空欄の表頭は上の行から引き継ぐ。新しい大項目では下位の段を引き継がない
    row6 = cb.set_index("column").loc["m006"]
    assert (row6["h1"], row6["h2"], row6["h3"]) == ("１．算定する入院料", "入院基本料", "地域一般入院基本料")
    assert cb.set_index("column").loc["m007", "h2"] == "特定入院料"
    assert pd.isna(cb.set_index("column").loc["m008", "h2"])
    assert cb.set_index("column").loc["m005", "secret"]
    assert cb.set_index("column").loc["m005", "zero_if_blank"]


def test_tokens_become_missing_and_are_kept_in_flags(files):
    notes, data = files
    cb = bfr.load_definition(notes, MEMBER, SHEET, "m")
    df, flags, info = bfr.parse_file(data, cb)
    assert len(df) == 3
    assert df["od_facility_code"].tolist() == ["0101", "0101", "0202"]  # 先頭の0を保つ
    assert str(df["m005"].dtype) == "Int64"
    assert df["m005"].tolist()[0] == 0  # 0は0のまま（未回答0の可能性はコードブックで示す）
    assert df["m005"].isna().tolist() == [False, True, False]
    assert str(df["m008"].dtype) == "Float64"  # 小数を含む列は Float64
    got = set(zip(flags["row"], flags["column"], flags["token"], strict=True))
    assert got == {(0, "m007", "*"), (1, "m005", "未報告又はデータ不備"), (1, "m008", "-"), (2, "m006", "-")}
    stats = info["stats"].set_index("column")
    assert stats.loc["m007", "n_secret_1_9"] == 1
    assert stats.loc["m005", "n_unreported"] == 1


def test_wrong_sheet_is_detected(files, tmp_path):
    notes, _ = files
    cb = bfr.load_definition(notes, MEMBER, SHEET, "m")
    width = len(ITEMS)
    other = tmp_path / "other.xlsx"
    other.write_bytes(_xlsx([[""] * width] * 4 + [[f"別の項目{i}" for i in range(width)], [""] * width] + DATA))
    with pytest.raises(ValueError, match="一致しません"):
        bfr.parse_file(other, cb)
