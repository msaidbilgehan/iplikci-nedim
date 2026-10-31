"""Shared logic for account movement lists (hesap hareketleri).

Every bank exports a different table, but the rows mean the same things: fees,
salary, credit-card payments, currency or gold purchases, bill payments,
debit-card purchases and transfers. Transfers are only marked as candidates
("aday") here; whether one goes to the user's own account, to a landlord or to
a relative is decided later, once all accounts are known (analysis.py).
"""

import re
from dataclasses import dataclass
from datetime import date

from ..models import Account, Statement, Transaction
from ..textutil import fold, format_tr_amount

CANDIDATE = "aday"

# Five-digit bank codes inside a Turkish IBAN (TRkk BBBBB ...).
BANK_CODES = {
    "00010": "Ziraat Bankası", "00012": "Halkbank", "00015": "Vakıfbank", "00032": "TEB",
    "00046": "Akbank", "00062": "Garanti BBVA", "00064": "İş Bankası", "00067": "Yapı Kredi",
    "00099": "ING", "00111": "QNB", "00134": "Denizbank", "00205": "Kuveyt Türk",
}


def bank_from_iban(iban: str) -> str:
    digits = re.sub(r"\D", "", iban)
    return BANK_CODES.get(digits[2:7], "") if len(digits) >= 7 else ""


@dataclass
class Movement:
    date: date
    description: str
    amount: float  # as printed by the bank: + money in, - money out
    balance: float | None = None
    label: str = ""  # the bank's own type column (Etiket, İşlem Tipi, İŞLEM)
    counterparty: str = ""


def check_balances(movements: list[Movement], oldest_first: bool, opening: float | None = None) -> tuple[int, int]:
    """Count rows whose printed balance equals the previous balance plus the amount."""
    rows = movements if oldest_first else list(reversed(movements))
    ok = total = 0
    prev_balance = opening
    for m in rows:
        if prev_balance is not None and m.balance is not None:
            total += 1
            ok += abs(prev_balance + m.amount - m.balance) < 0.015
        if m.balance is not None:
            prev_balance = m.balance
    return ok, total


_FEES = (
    "FAST UCRETI", "EFT UCRETI", "EFT) UCRETI", "HAVALE UCRETI", "ISLEM UCRETI", "UCRET H",
    "KESINTI VE EKLERI", "BSMV", "KKDF", "FAIZ", "KAMBIYO", "KMV", "KGV TUTARI", "MASRAF", "KOMISYON",
    "HESAP ISLETIM",
)
_CARD_PAYMENT = (
    "KRE.KART BORC ODEME", "K.KARTI ODEME", "KREDI KARTINA ODENEN", "NOLU KART ODEMESI", "KART ODEMESI",
    "OTO TAH", "KREDI KARTI ODEME",
)
_FX = ("DOVIZ AL", "DOVIZ SAT", "DVZ AL", "ALTIN")
_BILL_LABELS = ("FATURA", "TELEKOMUNIKASYON", "KURUM ODEMESI")


def classify(m: Movement, currency: str) -> str | None:
    """Preliminary kind of a movement, or None when the row should be dropped."""
    f = fold(f"{m.description} {m.label}")
    if not m.amount:
        return None  # failed or informational rows ("BAKIYE YETERSIZ")
    fx_row = any(p in f for p in _FX)
    if currency != "TL" and fx_row:
        return None  # the TL side of the same conversion carries it
    if any(p in f for p in _FEES):
        return "faiz_ucret"
    if "MAAS ODEMESI" in f or "MAASODEMESI" in f:
        return "gelir"
    if any(p in f for p in _CARD_PAYMENT):
        return "kart_odemesi"
    if fx_row:
        return "transfer"  # buying or selling currency/gold between own accounts
    if "NAKIT AVANS" in f and m.amount > 0:
        return "transfer"  # cash advance landing in the account; the card statement has the debt
    if "IPTAL" in f:
        return "iptal"
    if any(p in fold(m.label) for p in _BILL_LABELS) or " FATURA NO" in f:
        return "harcama"
    if fold(m.label) == "ALISVERIS" or re.search(r"\bSATIS-\d", f):
        return "harcama"
    if f.startswith("IADE") and m.amount > 0:
        return "iade"
    return CANDIDATE


def month_end_balances(movements: list[Movement], oldest_first: bool) -> dict[str, float]:
    """Balance after the last movement of each month, in the account's currency."""
    rows = movements if oldest_first else list(reversed(movements))
    return {f"{m.date:%Y-%m}": m.balance for m in rows if m.balance is not None}


def build_statement(doc, account: Account, movements: list[Movement], start: date, end: date,
                    oldest_first: bool, opening: float | None = None, closing: float | None = None) -> Statement:
    ok, total = check_balances(movements, oldest_first, opening)
    chronological = movements if oldest_first else list(reversed(movements))
    with_balance = [m for m in chronological if m.balance is not None]
    if opening is None and with_balance:
        opening = round(with_balance[0].balance - with_balance[0].amount, 2)
    if closing is None and with_balance:
        closing = with_balance[-1].balance
    stmt = Statement(
        account=account.id, cut_date=end, currency=account.currency, source=doc.name,
        previous=opening, total=closing, start=start, checks_ok=ok, checks_total=total,
        balances=month_end_balances(movements, oldest_first),
    )
    for m in movements:
        kind = classify(m, account.currency)
        if kind is None:
            continue
        stmt.transactions.append(Transaction(
            date=m.date, description=m.description.strip(), amount=round(-m.amount, 2), kind=kind,
            account=account.id, counterparty=m.counterparty.strip(), source=doc.name,
            original=f"{format_tr_amount(abs(m.amount))} {account.currency}" if account.currency != "TL" else "",
        ))
    _pair_cancellations(stmt.transactions)
    return stmt


def _pair_cancellations(txns: list[Transaction]) -> None:
    """A cancelled transfer and its reversal cancel out; both become plain transfers."""
    for t in txns:
        if t.kind != "iptal":
            continue
        t.kind = "transfer"
        for other in txns:
            if other is not t and other.date == t.date and other.kind == CANDIDATE and abs(other.amount + t.amount) < 0.01:
                other.kind = "transfer"
                break


# --- counterparty extraction --------------------------------------------------

_BANK_SUFFIX = r"(?:Bankası|Bank|BANKASI|BANK)\s+(?:A\.Ş\.|A\.S\.|T\.A\.O\.?|T\.A\.)"


def receiver_after_bank(text: str) -> str:
    """'... Yapı ve Kredi Bankası A.Ş. Veli Örneksoy hesabına ...' -> 'Veli Örneksoy'."""
    m = re.search(_BANK_SUFFIX + r"\s+(.+?)\s+hesabına", text)
    return m[1] if m else ""


def sender_after_bank(text: str) -> str:
    """'... Enpara Bank A.Ş. Kemal Denemeci hesabından ...' -> 'Kemal Denemeci'."""
    m = re.search(_BANK_SUFFIX + r"\s+(.+?)\s+hesabından", text)
    return m[1] if m else ""
