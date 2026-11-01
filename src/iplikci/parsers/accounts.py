"""Accounts as the banks' documents name them: one id for an account whether a list, a receipt or a passbook shows it."""

import re
from datetime import date

from ..domain.codes import AccountType
from ..domain.models import TRY, Account
from .common import currency_code
from .text import parse_dmy

# Five-digit bank codes inside a Turkish IBAN (TRkk BBBBB ...).
BANK_CODES = {
    "00010": "Ziraat Bankası",
    "00012": "Halkbank",
    "00015": "Vakıfbank",
    "00032": "TEB",
    "00046": "Akbank",
    "00062": "Garanti BBVA",
    "00064": "İş Bankası",
    "00067": "Yapı Kredi",
    "00099": "ING",
    "00111": "QNB",
    "00134": "Denizbank",
    "00205": "Kuveyt Türk",
}
_SLUGS = {"Garanti BBVA": "garanti", "İş Bankası": "isbank", "TEB": "teb", "Vakıfbank": "vakifbank", "QNB": "qnb"}


def bank_from_iban(iban: str) -> str:
    digits = re.sub(r"\D", "", iban)
    return BANK_CODES.get(digits[2:7], "") if len(digits) >= 7 else ""


def bank_account(bank: str, number: str, currency: str, kind: AccountType | None = None) -> Account:
    """The account as every document of that bank names it: lists, receipts and passbooks share its id. currency is
    as the document prints it ("TL", "USD", "GR")."""
    currency = currency_code(currency)
    if currency == "GR":
        type_, word = AccountType.GOLD, "Altın"
    elif currency != TRY:
        type_, word = AccountType.FX, f"Vadesiz {currency}"
    else:
        type_ = kind or AccountType.CURRENT
        word = {AccountType.OVERDRAFT: "Ek Hesap", AccountType.DEPOSIT: "Vadeli TL"}.get(type_, "Vadesiz TL")
    shown = number if len(number) <= 12 else "…" + number[-6:]
    return Account(
        id=f"{_SLUGS[bank]}-{number}",
        label=f"{bank} {word} {shown}",
        bank=bank,
        type=type_,
        currency=currency,
        number=number,
    )


def period_of(text: str) -> tuple[date | None, date | None]:
    """The first two dates of a "01.10.2026 - 31.10.2026" period."""
    found = re.findall(r"(\d{2}[./]\d{2}[./]\d{4})", text)
    if len(found) >= 2:
        return parse_dmy(found[0]), parse_dmy(found[1])
    return None, None
