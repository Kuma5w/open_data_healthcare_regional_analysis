"""市区町村コード（全国地方公共団体コード）の共通処理。

- 5桁: 都道府県2桁＋市区町村3桁（例: 札幌市 "01100"）
- 6桁: 5桁＋検査数字1桁（例: 札幌市 "011002"）

データによって5桁と6桁が混在し、数値として読み込むと先頭の0が落ちる。
このリポジトリでは、内部の結合キーは常に「5桁の文字列」に揃える。
"""

from __future__ import annotations

import csv
from functools import lru_cache

from . import paths

_WEIGHTS = (6, 5, 4, 3, 2)


def check_digit(code5: str) -> str:
    """5桁コードの検査数字を返す（各桁に6,5,4,3,2を掛けた和を11で割った余りを11から引き、1の位をとる）。"""
    if len(code5) != 5 or not code5.isdigit():
        raise ValueError(f"5桁の数字ではありません: {code5!r}")
    s = sum(int(d) * w for d, w in zip(code5, _WEIGHTS, strict=True))
    return str((11 - s % 11) % 10)


def to_code5(code: str) -> str:
    """5桁または6桁のコード文字列を5桁に揃える。6桁なら検査数字を確かめる。

    数値型（int）は受け付けない。先頭の0が落ちた6桁コード（例: 011011 → 11011）と
    5桁コードの区別がつかないため。CSVやExcelは dtype=str で読み込むこと。
    """
    if not isinstance(code, str):
        raise TypeError(
            f"コードは文字列で渡してください（受け取った型: {type(code).__name__}）。"
            "読み込み時に dtype=str を指定すると先頭の0が保たれます。"
        )
    c = code.strip()
    if len(c) == 5 and c.isdigit():
        return c
    if len(c) == 6 and c.isdigit():
        if check_digit(c[:5]) != c[5]:
            raise ValueError(f"検査数字が一致しません: {c}（正しくは {c[:5]}{check_digit(c[:5])}）")
        return c[:5]
    raise ValueError(f"5桁または6桁のコードではありません: {code!r}")


def to_code6(code: str) -> str:
    c5 = to_code5(code)
    return c5 + check_digit(c5)


def is_prefecture_level(code5: str) -> bool:
    """下3桁が000のコードは都道府県そのものを表す（市区町村に割り当てられない）。"""
    return code5[2:] == "000"


@lru_cache(maxsize=1)
def designated_cities() -> dict[str, str]:
    """政令指定都市の 5桁コード → 市名。reference/designated_cities.csv から読む。"""
    with open(paths.REFERENCE / "designated_cities.csv", encoding="utf-8") as f:
        return {row["code5"]: row["city_name"] for row in csv.DictReader(f)}


def ward_to_city(code5: str) -> str:
    """政令指定都市の区のコードを市のコードに置き換える。区でなければそのまま返す。

    区のコードは下3桁が101〜199で、同じ都道府県内で直前にある政令市に属する
    （例: 川崎市 14130 の区は 14131〜14137）。東京都の特別区（13101〜13123）は
    同じ範囲にあるが、東京都に政令市はないため置き換えない。
    """
    cities = designated_cities()
    if code5 in cities:
        return code5
    tail = int(code5[2:])
    if not 101 <= tail <= 199:
        return code5
    candidates = [c for c in cities if c[:2] == code5[:2] and c < code5]
    return max(candidates) if candidates else code5


def is_designated_ward(code5: str) -> bool:
    return ward_to_city(code5) != code5
