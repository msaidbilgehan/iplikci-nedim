"""A search box's text (domain.search): a comma between its parts finds the rows of any one, the words of a part all
of theirs, a quoted term as written."""

import pytest
from hypothesis import given
from hypothesis import strategies as st

from iplikci.domain.search import exactly, parse
from iplikci.domain.text import fold


def finds(search: str, text: str) -> bool:
    return parse(search).found_in(fold(text))


def test_a_comma_finds_the_rows_of_either_part():
    assert [p.text for p in parse("Ayşe, Mehmet").parts] == ["Ayşe", "Mehmet"]
    assert finds("Ayşe, Mehmet", "FAST AYSE ORNEK")
    assert finds("Ayşe, Mehmet", "EFT MEHMET ORNEK")
    assert not finds("Ayşe, Mehmet", "MIGROS")


def test_the_words_of_a_part_are_all_needed_as_before():
    assert finds("migros kadıköy", "MIGROS KADIKOY SUBE")
    assert not finds("migros kadıköy", "MIGROS ATASEHIR")
    assert finds("migros kadıköy, a101", "A101 MAGAZA")
    assert not finds("migros kadıköy, a101", "MIGROS ATASEHIR")


def test_a_comma_needs_no_space_and_a_trailing_one_adds_no_part():
    assert [p.text for p in parse("market,kira").parts] == ["market", "kira"]
    assert [p.text for p in parse("market, ").parts] == ["market"]
    assert [p.text for p in parse(" , ,market,, ").parts] == ["market"]


def test_an_empty_search_finds_every_row():
    assert parse("").parts == ()
    assert parse(" , ").parts == ()
    assert finds("", "ANY ROW")


def test_a_comma_between_digits_is_a_decimal_comma():
    assert [p.terms for p in parse("1,50").parts] == [("1,50",)]
    assert finds("12,99 usd", "NETFLIX 12,99 USD")
    assert [p.text for p in parse("1, 50").parts] == ["1", "50"]
    assert [p.text for p in parse("kira,5").parts] == ["kira", "5"]


def test_a_quoted_term_is_searched_as_written():
    search = parse('"ornek gida, kadikoy"')
    assert [(p.text, p.terms) for p in search.parts] == [('"ornek gida, kadikoy"', ("ORNEK GIDA, KADIKOY",))]
    assert finds('"ornek gida, kadikoy"', "ORNEK GIDA, KADIKOY SUBE")
    assert not finds('"ornek gida, kadikoy"', "KADIKOY ORNEK GIDA")
    assert [p.text for p in parse('"a, b" c, d').parts] == ['"a, b" c', "d"]


@pytest.mark.parametrize("quoted", ["“ornek, kadikoy”", "„ornek, kadikoy”", '"ornek, kadikoy'])
def test_curly_and_unclosed_quotes_keep_a_term_too(quoted):
    assert [p.terms for p in parse(quoted).parts] == [("ORNEK, KADIKOY",)]


def test_terms_are_compared_folded():
    assert finds("KİRA", "kira ödemesi")
    assert finds("şube", "SUBE")


def test_a_part_written_twice_is_kept_once():
    assert [p.text for p in parse("Ayşe, ayse, AYŞE").parts] == ["Ayşe"]


def test_a_name_searched_exactly_is_itself_without_a_comma_or_a_quote():
    assert exactly("ORNEK MARKET") == "ORNEK MARKET"
    assert exactly("ORNEK GIDA, KADIKOY") == '"ORNEK GIDA, KADIKOY"'
    assert exactly('ORNEK "X, Y" LTD') == '"ORNEK" "X, Y" "LTD"'
    assert exactly("12,50 TL") == "12,50 TL"


NAMES = st.text(alphabet=st.sampled_from(list('aB1 ,"“”„ıİşŞ\t-.')), max_size=30)


@given(NAMES)
def test_a_name_searched_exactly_finds_its_own_row_as_one_part(name):
    found = parse(exactly(name))
    assert len(found.parts) <= 1
    assert found.found_in(fold(name))


@given(NAMES)
def test_a_part_searched_alone_is_the_same_part(text):
    for part in parse(text).parts:
        assert parse(part.text).parts == (part,)
