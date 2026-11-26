import pytest

from chiiki_od import codes


@pytest.mark.parametrize(
    "code5, code6",
    [
        ("01000", "010006"),  # 北海道
        ("01100", "011002"),  # 札幌市
        ("01101", "011011"),  # 札幌市中央区（余り0 → 検査数字1）
        ("13101", "131016"),  # 千代田区
        ("14100", "141003"),  # 横浜市
        ("43100", "431001"),  # 熊本市
        ("43101", "431010"),  # 熊本市中央区（余り1 → 検査数字0）
    ],
)
def test_check_digit(code5, code6):
    assert codes.to_code6(code5) == code6
    assert codes.to_code5(code6) == code5


def test_wrong_check_digit_is_rejected():
    with pytest.raises(ValueError, match="検査数字"):
        codes.to_code5("011012")


def test_int_is_rejected():
    # 011011 を数値で読むと 11011 になり、5桁コードと区別できない
    with pytest.raises(TypeError):
        codes.to_code5(11011)


@pytest.mark.parametrize(
    "ward, city",
    [
        ("01101", "01100"),  # 札幌市中央区
        ("01110", "01100"),  # 札幌市清田区（下1桁が0でも区）
        ("14131", "14130"),  # 川崎市川崎区
        ("14151", "14150"),  # 相模原市緑区
        ("27141", "27140"),  # 堺市堺区
        ("40131", "40130"),  # 福岡市東区
        ("43101", "43100"),  # 熊本市中央区
    ],
)
def test_ward_to_city(ward, city):
    assert codes.ward_to_city(ward) == city
    assert codes.is_designated_ward(ward)


@pytest.mark.parametrize("code", ["13101", "13123", "43202", "14100", "01000"])
def test_not_a_ward(code):
    # 東京都の特別区、一般の市、政令市そのもの、都道府県は置き換えない
    assert codes.ward_to_city(code) == code


def test_prefecture_level():
    assert codes.is_prefecture_level("43000")
    assert not codes.is_prefecture_level("43100")
