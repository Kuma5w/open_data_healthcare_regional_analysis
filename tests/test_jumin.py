"""住民基本台帳の年齢階級別人口パーサーを、公表ファイルと同じ形の合成Excelで確かめる。"""

import openpyxl

from chiiki_od import jumin

AGES = [f"{a}歳～{a + 4}歳" for a in range(0, 100, 5)] + ["100歳以上"]


def _row(code, pref, name, sex, ages):
    return [code, pref, name, sex, sum(ages), *ages]


def test_levels_and_age_groups(tmp_path):
    a = [1] * 21  # 各階級1人 → 総数21、65歳以上8、75歳以上6
    wb = openpyxl.Workbook()
    ws = wb.active
    ws.append(["令和8年1月1日住民基本台帳"])
    ws.append(["", "", "", "", "総数", *AGES])
    ws.append(["団体コード", "都道府県名", "市区町村名", "性別", "人"])
    ws.append(_row("-", "合計", "-", "計", [3 * x for x in a]))
    ws.append(_row("010006", "北海道", "-", "計", [3 * x for x in a]))
    ws.append(_row("011002", "北海道", "札幌市", "計", a))
    ws.append(_row("011011", "北海道", "札幌市中央区", "計", a))
    ws.append(_row("013030", "北海道", "石狩郡当別町", "計", a))
    ws.append(_row("023001", "青森県", "東津軽郡", "計", a))
    ws.append(_row("011011", "北海道", "札幌市中央区", "男", a[:-1] + [0]))
    ws.append(["注1：外国人住民の内訳は非公表"])
    p = tmp_path / "pop.xlsx"
    wb.save(p)

    df, report = jumin.parse_file(p)
    assert report["as_of"] == "令和8年1月1日"
    t = df[df.sex == "total"].set_index("municipality_code")
    assert t.loc["00000", "level"] == "national"
    assert t.loc["01000", "level"] == "prefecture"
    assert t.loc["01100", "level"] == "designated_city"
    assert t.loc["01101", "level"] == "ward"
    assert t.loc["01303", "level"] == "municipality"  # 郡名を含むが町
    assert t.loc["02300", "level"] == "county"
    assert t.loc["01101", ["pop_total", "pop_65plus", "pop_75plus", "pop_0_14"]].tolist() == [21, 8, 6, 3]
    assert report["sum_of_units"] == 21 * 2  # 区と町だけを足す（政令市の合計・郡の合計は足さない）
    assert report["footnotes"] == ["注1：外国人住民の内訳は非公表"]
    assert (df["age_sum_gap"] == 0).all()
