"""質問窓口の「表示の切り替え」の読み取り（site/command.js）のテスト。node で実行する。"""

from __future__ import annotations

import json
import shutil
import subprocess
from pathlib import Path

import pytest

from chiiki_od import codes

ROOT = Path(__file__).resolve().parents[1]
RUNNER = ROOT / "tests" / "site_command_runner.cjs"

pytestmark = pytest.mark.skipif(shutil.which("node") is None, reason="node がないため飛ばす")

INDICATORS = [
    {"id": "homecare", "name": "65歳以上人口1万人あたり訪問介護事業所数"},
    {"id": "share", "name": "構想区域ごとの回復期病床の割合（休棟中を除く許可病床数に占める割合）"},
    {"id": "per100k", "name": "構想区域ごとの75歳以上人口10万人あたり回復期病床数"},
]
MUNI = [
    {"code": "43100", "name": "熊本市"},
    {"code": "43202", "name": "八代市"},
    {"code": "13206", "name": "府中市"},
    {"code": "34208", "name": "府中市"},
    {"code": "01234", "name": "北広島市"},
    {"code": "34100", "name": "広島市"},
    {"code": "07465", "name": "石川町"},
    {"code": "10424", "name": "長野原町"},
    {"code": "12100", "name": "千葉市"},
]
KOSO = [
    {"code": "4301", "name": "熊本・上益城"},
    {"code": "4307", "name": "阿蘇"},
    {"code": "1602", "name": "富山"},
    {"code": "0703", "name": "県南"},
    {"code": "0806", "name": "県南"},
    {"code": "0401", "name": "仙南"},
    {"code": "2703", "name": "堺市"},
]
CTX = {
    "prefectures": codes.PREFECTURES,
    "indicators": INDICATORS,
    "units": {"homecare": "municipality", "share": "koso_kuiki", "per100k": "koso_kuiki"},
    "areas": {"homecare": MUNI, "share": KOSO, "per100k": KOSO},
}


def run(cases: list[dict]) -> list[dict]:
    r = subprocess.run(
        ["node", str(RUNNER)],
        input=json.dumps({"ctx": CTX, "cases": cases}, ensure_ascii=False),
        capture_output=True,
        text=True,
        encoding="utf-8",
        check=True,
    )
    return json.loads(r.stdout)


def one(q: str, current: str | None = "homecare") -> dict:
    return run([{"q": q, "current": current}])[0]


@pytest.mark.parametrize(
    "q, pref",
    [
        ("熊本県の結果を出して", "43"),
        ("熊本の結果を表示", "43"),
        ("熊本県", "43"),
        ("ｸﾏﾓﾄ県は無理でも、東京都に切り替えて", "13"),
        ("北海道だけ見せてください", "01"),
        ("全国に戻して", ""),
        ("大阪府で絞り込んで", "27"),
    ],
)
def test_都道府県を切り替える(q, pref):
    r = one(q)
    assert r["display"] is True
    assert r["pref"] == pref


@pytest.mark.parametrize(
    "q",
    [
        "表示中の結果で、値が特に低い地域はどこ？",
        "回復期病床の割合の分母から休棟中の病床を除いたのはなぜ？",
        "熊本県の値が低いのはなぜ？",
        "並べ方はどう決まる？",
        "この割合にしているのは何のため？",
    ],
)
def test_質問は表示の依頼とみなさない(q):
    assert one(q)["display"] is False


def test_表示と質問が一緒の依頼():
    r = one("熊本県を表示して、注意点も教えて")
    assert r["display"] is True and r["question"] is True and r["pref"] == "43"
    r = one("熊本県を出してくれますか？")
    assert r["display"] is True and r["question"] is False


def test_並べ方():
    assert one("値の小さい順に並べて")["sort"] == "asc"
    assert one("多い順にして")["sort"] == "desc"
    assert one("コード順で表示")["sort"] == "code"


def test_長い地名の一部は都道府県とみなさない():
    assert one("北広島市を表示して")["areas"] == ["01234"]
    assert one("北広島市を表示して")["pref"] == "01"
    r = one("石川町を表示して")
    assert r["areas"] == ["07465"] and r["pref"] == "07"
    assert one("長野原町を出して")["pref"] == "10"
    # 「東京都府中市」の「京都府」は京都府ではない
    r = one("東京都府中市を出して")
    assert r["pref"] == "13" and r["areas"] == ["13206"]


def test_市区町村():
    r = one("熊本市を出して")
    assert r["pref"] == "43" and r["areas"] == ["43100"]
    r = one("千葉市の結果を見たい")
    assert r["pref"] == "12" and r["areas"] == ["12100"]
    # 同じ名前が2つ：両方を候補として返す（サイトがボタンで選んでもらう）
    assert sorted(one("府中市を表示")["areas"]) == ["13206", "34208"]
    assert one("広島県の府中市を表示")["areas"] == ["34208"]


def test_構想区域():
    r = one("熊本・上益城を出して", current="share")
    assert r["pref"] == "43" and r["areas"] == ["4301"]
    assert one("熊本上益城区域を表示", current="share")["areas"] == ["4301"]
    assert one("熊本県の阿蘇を表示して", current="share")["areas"] == ["4307"]
    # 2文字の区域名は、都道府県がないと照合しない（「県南部」の「県南」も除く）
    assert one("阿蘇を表示して", current="share")["areas"] == []
    assert one("茨城県の県南部を表示", current="share")["areas"] == []
    assert one("茨城県の県南を表示", current="share")["areas"] == ["0806"]
    assert sorted(one("県南区域を表示", current="share")["areas"]) == ["0703", "0806"]
    # 区域名と県の短い名前が同じなら都道府県として読む。「区域」と付ければ区域
    r = one("富山を出して", current="share")
    assert r["pref"] == "16" and r["areas"] == []
    assert one("富山区域を出して", current="share")["areas"] == ["1602"]
    assert one("堺市の回復期病床の割合を出して", current="share")["areas"] == ["2703"]


def test_指標を選ぶ():
    r = one("熊本県の回復期病床の割合を出して", current=None)
    assert r["indicator"] == "share" and r["pref"] == "43"
    assert one("75歳以上人口あたりの回復期病床数を出して", current=None)["indicator"] == "per100k"
    assert one("訪問介護事業所を熊本県で", current="share")["indicator"] == "homecare"
    # どちらとも取れるとき：表示中の指標があればそれ、なければ候補を返す
    assert one("回復期病床を熊本県で出して", current="per100k")["indicator"] == "per100k"
    r = one("回復期病床を熊本県で出して", current=None)
    assert r["indicator"] is None and sorted(r["ties"]) == ["per100k", "share"]
    # 指標名がなければ、表示中の指標のまま
    assert one("熊本県の結果を出して", current="share")["indicator"] is None
