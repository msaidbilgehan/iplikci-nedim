from datetime import date

import pytest

from iplikci.textutil import (
    fold,
    parse_dmy,
    parse_tr_amount,
    parse_tr_words_date,
    parse_us_amount,
    title_tr,
)


@pytest.mark.parametrize("text, expected", [
    ("1.234,56", 1234.56),
    ("-12.345,67", -12345.67),
    ("4321,09", 4321.09),
    ("1.234,00+", -1234.0),  # Garanti prints credits with a trailing plus
    ("TL.1.500,-", 1500.0),  # TEB
    ("-TL.2.345,-", -2345.0),
    ("TL 1.111,11-", -1111.11),
    ("0,04", 0.04),
    ("1234,56/6", None),
    ("MAXİPUAN:0,07", None),
    ("abc", None),
])
def test_parse_tr_amount(text, expected):
    assert parse_tr_amount(text) == expected


@pytest.mark.parametrize("text, expected", [
    ("2,345.67", 2345.67), ("12.34", 12.34), ("4,321.0", 4321.0), ("11,000.00", 11000.0), ("1.234,5", None),
])
def test_parse_us_amount(text, expected):
    assert parse_us_amount(text) == expected


def test_fold_turkish():
    assert fold("Migros  Örnek Şube İstanbul") == "MIGROS ORNEK SUBE ISTANBUL"
    assert fold("ığüşöç") == "IGUSOC"


def test_dates():
    assert parse_dmy("08/09/2024") == date(2024, 9, 8)
    assert parse_dmy("07.10.2024") == date(2024, 10, 7)
    assert parse_dmy("31/02/2024") is None
    assert parse_tr_words_date("27", "Haziran", "2025") == date(2025, 6, 27)
    assert parse_tr_words_date("1", "AĞUSTOS", "2025") == date(2025, 8, 1)
    assert parse_tr_words_date("1", "Foo", "2025") is None


def test_title_tr():
    assert title_tr("ORNEK COFFEE") == "Ornek Coffee"
    assert title_tr("İSTANBUL ISTANBUL") == "İstanbul İstanbul"
    assert title_tr("ORNEKKOY V.D.") == "Ornekkoy V.D."
