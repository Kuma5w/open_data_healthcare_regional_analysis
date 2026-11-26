"""変換の基本動作：欠損記号をゼロにしない、列名の変化を見逃さない。"""

import pandas as pd
import pytest

from chiiki_od.convert import apply_columns

COLUMNS = [
    {"source": "コード", "name": "code", "type": "str"},
    {"source": "病床数", "name": "beds", "type": "int"},
]


def test_na_symbols_become_missing_not_zero():
    df = pd.DataFrame({"コード": ["01100", "01101", "01102"], "病床数": ["50", "未報告又はデータ不備", "－"]})
    out, report = apply_columns(df, COLUMNS, ["未報告又はデータ不備", "－"])
    assert out["code"].tolist() == ["01100", "01101", "01102"]  # 先頭の0が残る
    assert out["beds"].iloc[0] == 50
    assert out["beds"].isna().sum() == 2
    assert report["na_symbols"] == {"beds": 2}


def test_unparsed_numbers_are_reported():
    df = pd.DataFrame({"コード": ["01100"], "病床数": ["約50"]})
    out, report = apply_columns(df, COLUMNS, [])
    assert out["beds"].isna().all()
    assert report["unparsed_numbers"] == {"beds": 1}


def test_missing_column_raises_with_actual_columns():
    df = pd.DataFrame({"コード": ["01100"], "許可病床数": ["50"]})
    with pytest.raises(ValueError, match="許可病床数"):
        apply_columns(df, COLUMNS, [])
