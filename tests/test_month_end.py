"""Month-end closing and reports: when a month closes, what an open month waits for, the pages."""

from datetime import date, datetime

import pytest

from iplikci import cli, month_end
from iplikci.analysis import build
from iplikci.categorize import Categorizer
from iplikci.demo import teb_export
from iplikci.insights import interpret
from iplikci.models import Account, ParseResult, Security, Statement, Transaction
from iplikci.sources import Document

from conftest import JANUARY, RULES, put

HOLDER = "ÖRNEK KULLANICI"
CHECKING = Account("teb-123456789", "TEB Vadesiz TL 123456789", "TEB", "Vadesiz hesap", number="123456789")
CARD = Account("teb-4321", "TEB Bonus •4321", "TEB", "Kredi kartı", number="4321")
STOCKS = Account(
    "garanti-yatirim-1-101", "Garanti BBVA Yatırım 1-101", "Garanti BBVA", "Yatırım hesabı", number="1-101"
)


@pytest.fixture(scope="module")
def cat(tmp_path_factory):
    rules = tmp_path_factory.mktemp("kurallar") / "kategoriler.yaml"
    rules.write_text(RULES, encoding="utf-8")
    return Categorizer(rules)


def spend(d: date, desc: str, amount: float, account: Account = CARD, kind: str = "harcama") -> Transaction:
    return Transaction(d, desc, amount, kind, account.id, source="belge")


def listing(
    start: date, end: date, *rows: Transaction, checks: tuple[int, int] = (1, 1), opening: float = 5000.0
) -> ParseResult:
    closing = round(opening - sum(r.amount for r in rows), 2)
    s = Statement(
        CHECKING.id,
        end,
        "TL",
        f"liste-{end}.xls",
        opening,
        closing,
        list(rows),
        start=start,
        checks_ok=checks[0],
        checks_total=checks[1],
        balances={f"{end:%Y-%m}": closing},
    )
    return ParseResult("liste", accounts=[CHECKING], statements=[s])


def card(cut: date, *rows: Transaction, previous: float = 0.0) -> ParseResult:
    s = Statement(
        CARD.id, cut, "TL", f"ekstre-{cut}.pdf", previous, round(previous + sum(r.amount for r in rows), 2), list(rows)
    )
    return ParseResult("ekstre", accounts=[CARD], statements=[s])


def brokerage(month_start: date, month_last: date) -> ParseResult:
    s = Statement(
        STOCKS.id,
        month_last,
        "TL",
        "hisse.pdf",
        100.0,
        100.0,
        [],
        start=month_start,
        checks_ok=1,
        checks_total=1,
        securities=[Security("ORNEK", "Örnek A.Ş.", 10, 2500.0, month_last)],
    )
    return ParseResult("hisse", accounts=[STOCKS], statements=[s])


def receipt(d: date, amount: float, account: Account = CHECKING) -> ParseResult:
    t = Transaction(d, "Giden FAST → ALİ VELİ", amount, "aday", account.id, counterparty="ALİ VELİ", source="dekont")
    return ParseResult("dekont", accounts=[account], transactions=[t], receipt_key=f"r-{d}", holder=HOLDER)


def month(cat, today: date, which: str, *results: ParseResult) -> month_end.MonthEnd:
    docs = [(Document(f"{i}.pdf", "test", b"", f"sha{i}"), r, None) for i, r in enumerate(results)]
    ds = build(docs, cat, {"ad_soyad": HOLDER})
    [me] = month_end.build(ds, interpret(ds), today=today, months=[which])
    return me


def autumn(*extra: ParseResult) -> list[ParseResult]:
    """A checking account listed through October and a card whose statements cover it (cut on the 18th)."""
    return [
        listing(date(2026, 9, 1), date(2026, 10, 31), spend(date(2026, 10, 5), "MARKET", 400.0, CHECKING)),
        card(date(2026, 9, 18)),
        card(date(2026, 10, 18), spend(date(2026, 10, 2), "ORNEK KAHVE", 120.0)),
        card(date(2026, 11, 18), spend(date(2026, 10, 25), "MARKET ALISVERIS", 300.0)),
        *extra,
    ]


def by_label(me: month_end.MonthEnd) -> dict[str, month_end.AccountClose]:
    return {a.account.label: a for a in me.accounts}


# --- closing -----------------------------------------------------------------------------------------


def test_a_month_closes_when_every_account_covers_it_and_checks_out(cat):
    me = month(cat, date(2026, 11, 25), "2026-10", *autumn())
    assert me.status == month_end.CLOSED
    assert {a.status for a in me.accounts} == {month_end.CLOSED}
    assert me.summary.startswith("Bütün hesapların belgeleri ayın tamamını kapsıyor")
    assert me.totals.expense == 820.0 and me.totals.income == 0.0


def test_an_open_month_waits_for_the_card_statement_after_the_next_cut(cat):
    me = month(cat, date(2026, 11, 10), "2026-10", *autumn()[:-1])
    assert me.status == month_end.WAITING
    waiting = by_label(me)["TEB Bonus •4321"]
    assert (waiting.status, waiting.next_cut, waiting.late) == (month_end.WAITING, date(2026, 11, 18), False)
    assert waiting.note == "19–31 Ekim ekstresi e-postayla bekleniyor (sonraki kesim ~18.11.2026)"
    assert me.summary == "Kapanması için bekleniyor: TEB Bonus •4321 (19–31 Ekim ekstresi, kesim ~18.11)."


def test_a_statement_past_its_cut_date_is_late(cat):
    me = month(cat, date(2026, 11, 30), "2026-10", *autumn()[:-1])
    assert by_label(me)["TEB Bonus •4321"].late
    assert "e-posta gelmediyse ekstreyi bankadan indirin" in by_label(me)["TEB Bonus •4321"].note


def test_a_missing_list_between_two_others_is_a_document_to_download(cat):
    me = month(
        cat,
        date(2026, 12, 5),
        "2026-10",
        listing(date(2026, 9, 1), date(2026, 9, 30)),
        listing(date(2026, 11, 1), date(2026, 11, 30)),
    )
    checking = by_label(me)["TEB Vadesiz TL 123456789"]
    assert (me.status, checking.status, checking.covered, checking.needed) == (
        month_end.MISSING,
        month_end.MISSING,
        0,
        31,
    )
    assert checking.note.startswith("1–31 Ekim için hesap dökümü yok: bankadan indirip")


def test_a_list_that_does_not_check_out_or_misses_a_receipt_needs_a_look(cat):
    me = month(cat, date(2026, 11, 25), "2026-10", *autumn(receipt(date(2026, 10, 10), 300.0)))
    checking = by_label(me)["TEB Vadesiz TL 123456789"]
    assert (me.status, checking.status) == (month_end.CHECK, month_end.CHECK)
    assert checking.note == "1 dekont satırı ekstrede yok"
    assert [line.txn.amount for line in me.unmatched] == [300.0]

    me = month(cat, date(2026, 11, 25), "2026-10", listing(date(2026, 10, 1), date(2026, 10, 31), checks=(3, 4)))
    assert me.status == month_end.CHECK
    assert by_label(me)["TEB Vadesiz TL 123456789"].note == "01.10–31.10 dökümünde bakiye 3/4 satır tutarlı"


def test_the_brokerage_statement_never_holds_the_month_open(cat):
    me = month(cat, date(2026, 11, 25), "2026-10", *autumn(brokerage(date(2026, 9, 1), date(2026, 9, 30))))
    stocks = by_label(me)["Garanti BBVA Yatırım 1-101"]
    assert (stocks.status, stocks.blocking, me.status) == (month_end.WAITING, False, month_end.CLOSED)
    # The October statement comes in the first days of November: on the 25th it is late.
    assert stocks.note == (
        "1–31 Ekim ekstresi e-postayla bekleniyor (ay sonu ekstresi); beklenen tarih geçti: "
        "e-posta gelmediyse ekstreyi bankadan indirin"
    )


def test_the_current_month_runs_and_counts_its_provisional_receipts(cat):
    me = month(cat, date(2026, 11, 12), "2026-11", *autumn(receipt(date(2026, 11, 3), 250.0)))
    assert me.status == month_end.RUNNING
    assert [t.amount for t in me.provisional] == [250.0]
    assert "1 işlem dekontlardan geçici olarak işlendi" in me.summary
    assert by_label(me)["TEB Vadesiz TL 123456789"].needed == 12  # the days so far


def test_income_is_unknown_in_a_month_only_card_statements_cover(cat):
    me = month(cat, date(2026, 11, 25), "2026-10", *autumn()[1:])
    assert me.totals.income is None and me.totals.left is None
    assert me.income_note == "bu ay için hesap dökümü yok: gelir bilinmiyor"


def test_the_current_month_knows_its_income_from_a_list_of_its_days_so_far(cat):
    pay = Transaction(date(2026, 11, 3), "MAAS ODEMESI", -1000.0, "gelir", CHECKING.id, source="belge")
    me = month(cat, date(2026, 11, 12), "2026-11", listing(date(2026, 11, 1), date(2026, 11, 12), pay))
    assert (me.status, me.totals.income, me.income_note) == (month_end.RUNNING, 1000.0, month_end.INCOME_NOTE)


def test_a_month_end_balance_is_the_one_the_list_printed(cat):
    me = month(cat, date(2026, 11, 25), "2026-10", *autumn())
    assert by_label(me)["TEB Vadesiz TL 123456789"].balance == 4600.0
    assert by_label(me)["TEB Bonus •4321"].balance is None  # a card's balance is its statement total


# --- pages ---------------------------------------------------------------------------------------------


def test_pages_escape_statement_text_and_carry_no_script(cat, tmp_path):
    shop = spend(date(2026, 10, 2), '<img src=x onerror="alert(1)"> KAHVE', 120.0)
    docs = [
        (Document(f"{i}.pdf", "test", b"", f"sha{i}"), r, None)
        for i, r in enumerate([listing(date(2026, 9, 1), date(2026, 10, 31)), card(date(2026, 10, 18), shop)])
    ]
    ds = build(docs, cat, {"ad_soyad": HOLDER})
    months = month_end.build(ds, interpret(ds), today=date(2026, 11, 2))
    written = month_end.write_all(months, ds, tmp_path / "ay-sonu", made=datetime(2026, 11, 2, 9, 30))
    assert [p.name for p in written] == ["2026-09.html", "2026-10.html", "2026-11.html", "index.html"]
    page = (tmp_path / "ay-sonu" / "2026-10.html").read_text(encoding="utf-8")
    assert "<script" not in page and "<img" not in page and "&lt;img src=x" in page
    assert f'content="{month_end.CSP}"' in page.replace("&#x27;", "'")
    assert '<a href="2026-09.html">' in page and '<a href="2026-11.html">' in page
    assert 'href="../gider_raporu.html"' in page
    index = (tmp_path / "ay-sonu" / "index.html").read_text(encoding="utf-8")
    assert index.count('href="2026-') == 3 and "Ay sonu raporları" in index
    # November has no list yet: the index says why its income and what was left are unknown.
    assert "Bu ay için hesap dökümü yok: gelir bilinmiyor." in index


def test_the_month_end_command_writes_a_months_page_and_refuses_a_month_to_come(ws, monkeypatch, capsys):
    put(ws.documents / "TEB" / "Vadesiz Hesap TL 123456789" / "ocak.xls", teb_export(JANUARY))
    monkeypatch.chdir(ws.base)
    assert cli.main(["aysonu", "2026-01"]) == 0
    assert "Ocak 2026 — Kapandı" in capsys.readouterr().out
    assert (ws.output / month_end.FOLDER / "2026-01.html").exists()
    with pytest.raises(SystemExit):
        cli.main(["aysonu", "2999-01"])
    assert "2999-01 henüz gelmedi" in capsys.readouterr().err


def test_the_pages_cover_the_current_month_and_the_twelve_before_it(cat):
    docs = [
        (Document("0.pdf", "test", b"", "sha0"), card(date(2023, 1, 18), spend(date(2023, 1, 2), "MARKET", 1.0)), None)
    ]
    ds = build(docs, cat, {"ad_soyad": HOLDER})
    months = month_end.report_months(ds, date(2026, 11, 2))
    assert (months[0], months[-1], len(months)) == ("2025-11", "2026-11", 13)
