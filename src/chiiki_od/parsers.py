"""汎用の読み込み（1行見出しの表）で足りないデータの専用パーサー。

datasets/<id>.yaml に `parser: <名前>` と書くと、変換時にここの関数が呼ばれる。
関数は (DataFrame, report) または (DataFrame, report, extras) を返す。
extras の各表は data/processed/<output>__<名前>.parquet に、"__codebook__" は codebooks/<id>.csv に保存する。DataFrame の列は datasets/<id>.yaml の columns の name に合わせる。
"""

from __future__ import annotations


def parse_population_jumin_age(ds: dict):
    """住民基本台帳 年齢階級別人口（市区町村別）。詳細は chiiki_od.jumin。"""
    from .jumin import parse_dataset

    return parse_dataset(ds)


def parse_bed_function_report(ds: dict):
    from .bfr import parse_dataset

    return parse_dataset(ds)


def parse_medical_facility_survey(ds: dict):
    """医療施設調査 二次医療圏・市区町村編（市区町村別の施設数・病床数）。詳細は chiiki_od.iryo_shisetsu。"""
    from .iryo_shisetsu import parse_dataset

    return parse_dataset(ds)


def parse_kouseikyoku(ds: dict):
    """地方厚生局の届出受理医療機関名簿（施設基準の届出）。詳細は chiiki_od.kouseikyoku。"""
    from .kouseikyoku import parse_dataset

    return parse_dataset(ds)


PARSERS = {
    "population_jumin_age": parse_population_jumin_age,
    "bed_function_report": parse_bed_function_report,
    "medical_facility_survey": parse_medical_facility_survey,
    "kouseikyoku": parse_kouseikyoku,
}
