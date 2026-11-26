"""在宅医療等連携機能の年次推移（D.S.氏の方法）を、合成サンプルで手計算と照合する。

tests/fixtures/psc_trend_*_sample.csv（FY2022〜2024）
  FY2024：P・S・C判定のサンプル（zaitaku_psc_*_sample.csv）と同じ5病院。
          ニの入退院支援加算1は、月別の公表値 200＋95 と「*」1か月。年間合計票は300なので、補完値は (300−295)÷1＝5
  FY2023：イチ、ニ（オープンデータ医療機関コードが変わったが医療機関コード（医科）は同じ）、
          キュウ（令和7年度までに廃止。報告された構想区域コード 4399 はマスタにない → 所在地 43202 八代市 → 八代）
          ニの入退院支援加算1は 100＋「*」1か月 → 100＋5＝105（退院800の13％で×）
  FY2022：イチ（P4 は退院100の6％で○）、サン（コードが変わり医療機関コードもない → 法人名を除いた名称で照合）
"""

import pandas as pd
import pytest

from chiiki_od import areas, psc_trend, runner, zaitaku_psc

ITEMS = psc_trend.TREND_ITEMS


@pytest.fixture(scope="module")
def evaluated():
    inp = psc_trend.load_inputs(sample=True)
    years, cal, notes = psc_trend.evaluate(**inp)
    return years, cal, notes


def test_item_map_handles_renames_and_new_items():
    m = psc_trend.item_map()
    get = lambda table, c, rep: m[(m.table == table) & (m.r7_column == c) & (m.report == rep)].iloc[0]  # noqa: E731
    # 令和3年度は一般病床・療養病床の列が4つ前にある
    assert get("ward", "w019", "r3")["column"] == "w015"
    # 「うち介護施設、…」と「うち、介護施設、…」の表記の揺れ
    assert get("ward", "w189", "r3")["column"] == "w190"
    # 令和4年度改定で名前が変わった病床初期加算
    r = get("form2_monthly", "m178", "r3")
    assert r["column"] == "m156" and r["how"] == "改定で名前が変わった項目"
    # 入退院支援加算３は令和7年度報告から
    assert m[(m.r7_column == "m175") & (m.report != "r7")]["column"].isna().all()


def test_calibration_from_r7_annual(evaluated):
    _, cal, _ = evaluated
    k = cal.set_index(["pref_code", "column"])
    assert k.loc[("43", "m172"), "k"] == 5  # (300 − 295) ÷ 1
    assert k.loc[("00", "m172"), "n_secret"] == 1
    assert k.loc[("43", "m181"), "k"] == 5  # 非公表の月がない項目は1〜9の中央の値


def test_fy2024_matches_star_table_when_calibration_is_exact(evaluated):
    years, _, _ = evaluated
    t = years[years.fiscal_year == 2024].set_index("od_facility_code")
    r, _ = zaitaku_psc.evaluate(**zaitaku_psc.load_inputs(sample=True))
    r = r.set_index("od_facility_code")
    assert sorted(t.index) == sorted(r.index)
    for code in r.index:
        assert [t.loc[code, c] for c in ITEMS] == [r.loc[code, c] for c in ITEMS], code
    assert t.loc["4300000002", "S1_value"] == 300  # 295＋1×5


def test_past_year_estimate_and_missing_item(evaluated):
    years, _, notes = evaluated
    h = years[(years.fiscal_year == 2023)].set_index("od_facility_code")
    assert h.loc["4300000012", "S1_value"] == 105 and h.loc["4300000012", "S1"] == "×"
    assert h.loc["4300000009", "S6"] == "○" and h.loc["4300000009", "items_met"] == 3  # S6・C1・C3
    assert any("FY2023" in n and "入退院支援加算３" in n for n in notes)
    assert "type" not in years.columns and "is_P" not in years.columns  # 11項目では類型を判定しない


def test_link_to_r7(evaluated):
    years, _, _ = evaluated
    link = psc_trend.link_to_r7(years)
    by = dict(zip(zip(years.fiscal_year, years.od_facility_code, strict=True), link["link"], strict=True))
    to = dict(zip(zip(years.fiscal_year, years.od_facility_code, strict=True), link["r7_code"], strict=True))
    assert by[(2023, "4300000012")] == "2_medical_code" and to[(2023, "4300000012")] == "4300000002"
    assert by[(2022, "4300000033")] == "3_name" and to[(2022, "4300000033")] == "4300000003"
    assert pd.isna(to[(2023, "4300000009")])


def test_link_prefers_code_over_name():
    years = pd.DataFrame({
        "fiscal_year": [2024, 2023, 2023],
        "od_facility_code": ["01", "01", "02"],
        "medical_code_ika": [None, None, None],
        "pref_code": ["08", "08", "08"],
        "facility_name": ["宮本病院", "宮本病院", "医療法人社団恵仁会 宮本病院"],
    })
    link = psc_trend.link_to_r7(years)
    assert link["r7_code"].tolist()[:2] == ["01", "01"] and pd.isna(link["r7_code"].iloc[2])


def test_koso_trend_indicator():
    res, notes = runner.execute("zaitaku_renkei_trend_koso", sample=True)[:2]
    r = res.set_index(["koso_kuiki_code", "fiscal_year"])
    assert r.loc[("4312", "FY2024"), "hospitals"] == 2 and r.loc[("4312", "FY2024"), "items_met_sum"] == 5
    assert r.loc[("4312", "FY2024"), "items_per_hospital"] == 2.5
    assert r.loc[("4308", "FY2023"), "hospitals"] == 1  # 廃止した病院は所在地の市区町村で割り当てる
    assert r.loc[("4308", "FY2022"), "n_C4"] == 1
    assert pd.isna(r.loc[("4302", "FY2024"), "items_per_hospital"])  # 病院のない区域は値なし
    assert set(res["koso_kuiki_code"]) == set(areas.koso_reference()["koso_kuiki_code"])
    assert any("補完値" in n for n in notes)


def test_hospital_trend_uses_psc_ids():
    res, _ = runner.execute("zaitaku_renkei_trend_hospital", sample=True)[:2]
    r, _ = zaitaku_psc.evaluate(**zaitaku_psc.load_inputs(sample=True))
    ids = pd.concat([r[["od_facility_code"]], zaitaku_psc.mask_ids(r)], axis=1).set_index("od_facility_code")["hospital_id"]
    ni, san = ids["4300000002"], ids["4300000003"]
    assert res.loc[res.hospital_id == ni, "fiscal_year"].tolist() == ["FY2023", "FY2024"]
    assert res.loc[res.hospital_id == san, "fiscal_year"].tolist() == ["FY2022", "FY2024"]
    assert "合成病院キュウ" not in res.to_string() and "4300000009" not in res.to_string()
    assert not res.astype(str).apply(lambda s: s.str.contains("合成病院|43000000")).any().any()  # 名前とコードは載せない
    assert set(res.loc[res.hospital_id == san, "koso_kuiki_code"]) == {"4308"}


def test_mask_ids_keeps_psc_hospital_table_order():
    r, _ = zaitaku_psc.evaluate(**zaitaku_psc.load_inputs(sample=True))
    t = zaitaku_psc.hospital_table(r)
    ids = zaitaku_psc.mask_ids(r)
    assert sorted(t["hospital_id"]) == sorted(ids["hospital_id"])
    assert t["hospital_id"].tolist() == sorted(t["hospital_id"], key=lambda s: (s[:4], len(s), s))
