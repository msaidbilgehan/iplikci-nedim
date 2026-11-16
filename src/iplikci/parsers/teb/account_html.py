"""TEB account movements: CEPTETEB's "Hesap Hareketlerim", an HTML table saved as .xls."""

import re
from typing import Any

from ...domain.codes import AccountType, DocumentKind
from ...domain.models import ParseResult
from ...domain.text import fold
from ..accounts import bank_account, bank_from_iban, period_of
from ..common import Skipped
from ..contract import Detection, Format, Probe, SourceDocument
from ..movements import Movement, build_statement
from ..sheet import key_values, to_number
from ..text import parse_dmy

ID = "teb.account_html"


def sender_of(description: str) -> str:
    """Who sent the money in, as TEB writes it: "<Ad Soyad> den gelen havale tutarı"; "" for any other row."""
    sender = re.match(r"(.+?)\s+den gelen", description)
    return sender[1] if sender else ""


def holder_info(rows: list[list[Any]]) -> dict[str, str]:
    """The export's "label | value" rows at the top: Hesap, IBAN, Hesap Türü, Hesap Sahibi…"""
    return key_values(r for r in rows[:20] if len(r) == 2)


def read(doc: SourceDocument) -> ParseResult:
    rows = doc.rows
    info = holder_info(rows)
    number = info.get("Hesap", "")
    kind = fold(info.get("Hesap Türü", ""))
    currency = "GR" if kind.endswith("GR") else "TL"
    moves = []
    for i, r in enumerate(rows):
        if len(r) != 7 or not re.match(r"\d{2}/\d{2}/\d{4}$", r[0]):
            continue
        amount = to_number(r[4])
        if amount is None:
            continue
        desc = r[3]
        moves.append(Movement(parse_dmy(r[0]), desc, amount, to_number(r[5]), "", sender_of(desc), doc.row_ref(i)))
    if not number:
        raise Skipped("TEB hesap bilgisi yok")
    # A TL account that runs below zero is the overdraft (KMH) account.
    overdraft = currency == "TL" and any((m.balance or 0) < -1 for m in moves)
    account = bank_account("TEB", number, currency, AccountType.OVERDRAFT if overdraft else None)
    period = re.search(r"\d{2}/\d{2}/\d{4}\s*-\s*\d{2}/\d{2}/\d{4}(?=\s*tarihleri)", doc.html)
    start, end = period_of(period[0] if period else "")
    stmt = build_statement(doc, account, moves, start, end, oldest_first=False)
    return ParseResult(parser=ID, accounts=[account], statements=[stmt], holder=info.get("Hesap Sahibi", ""))


class AccountHtml:
    id = ID
    version = 2
    bank = "TEB"
    name = "TEB hesap hareketleri (CEPTETEB)"
    document_type = DocumentKind.ACCOUNT_STATEMENT
    formats = frozenset({Format.SHEET})

    def detect(self, probe: Probe) -> Detection | None:
        if probe.sheet == "html" and bank_from_iban(holder_info(probe.rows).get("IBAN", "")) == "TEB":
            return Detection(1.0, "HTML tablonun IBAN'ı TEB'in")
        return None

    def parse(self, doc: SourceDocument) -> ParseResult:
        return read(doc)


PARSER = AccountHtml()
