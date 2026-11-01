"""Garanti BBVA receipts (dekont) of single transfers: outgoing FAST, outgoing havale and incoming
transfers into a TL or foreign-currency account.

One page of "LABEL : value" lines on the left; the customer's name and address sit in the right
column of the header block. Receipts of incoming transfers mask the account number ("1012/****321")
and the customer's name; analysis.resolve_masked points them at the account the lists name.
"""

import re
from decimal import Decimal

from ..domain.codes import TransactionKind
from ..domain.models import TRY, Account, ParseResult, Transaction
from ..pdfutil import Line, page_lines
from ..textutil import fold, format_tr_amount, parse_dmy, parse_tr_amount, squash, title_tr
from .common import BUSINESS_REASON, Skipped, currency_code, is_business
from .hesap import bank_from_iban
from .hesaplar import bank_account

NAME = "Garanti BBVA dekont"
_RIGHT_COLUMN = 300  # the customer's name and address start right of this in the header block
_TITLES = {"HESAPTAN FAST": "Giden FAST", "HESAPTAN HESABA HAVALE": "Giden Havale"}


def detect(first_page: str) -> bool:
    s = squash(first_page)
    return "GARANTIBANKASI" in s and "DEKONT" in s and "HESAPNUMARASI" in s and "SIRANO" in s


class _Fields:
    """The receipt's 'LABEL : value' lines. In the header block (down to DÜZENLENME TARİHİ) only the
    left column counts; below it a value runs to the end of the line."""

    def __init__(self, lines: list[Line]):
        self.lines = lines
        self.header_end = next((line.top for line in lines if line.folded.startswith("DUZENLENME")), 0.0)

    def get(self, label: str) -> str:
        for line in self.lines:
            f = line.folded
            if not f.startswith(label) or not f[len(label) :].lstrip().startswith(":"):
                continue  # "ALACAKLI IBAN" is not "ALACAKLI"
            words = [w for w in line.words if w.x0 < _RIGHT_COLUMN or line.top > self.header_end]
            return " ".join(w.text for w in words).split(":", 1)[1].strip()
        return ""


def _holder(lines: list[Line]) -> str:
    """The name under 'SAYIN' in the right column; empty when the receipt masks it."""
    for i, line in enumerate(lines[:-1]):
        if any(fold(w.text) == "SAYIN" and w.x0 >= _RIGHT_COLUMN for w in line.words):
            name = " ".join(w.text for w in lines[i + 1].words if w.x0 >= _RIGHT_COLUMN)
            return "" if "*" in name else name
    return ""


def _amount(lines: list[Line]) -> tuple[Decimal, str] | None:
    """'TUTAR : - 500,00 TL' on the SIRA NO line: (signed amount as printed, currency)."""
    for line in lines:
        m = re.search(r"\bTUTAR\s*:\s*([+-])?\s*([\d.]+,\d{2})\s*(TL|EUR|USD|GBP)\b", line.folded)
        if m and line.folded.startswith("SIRA NO"):
            value = parse_tr_amount(m[2])
            return (-value if m[1] == "-" else value), currency_code(m[3])
    return None


def _note(lines: list[Line], title: str) -> str:
    """The sender's note: after the FAST reference, or the free line under the IBAN of a havale."""
    for i, line in enumerate(lines):
        if line.folded.startswith("FAST REF NO"):
            return " - ".join(line.text.split(" - ")[2:]).strip()
        if title == "Giden Havale" and line.folded.startswith("IBAN:") and i + 1 < len(lines):
            below = lines[i + 1].text
            return "" if ":" in below else below.strip()
    return ""


def _receiver(fields: _Fields) -> str:
    # FAST: "ALACAKLI : AD SOYAD"; havale: "ALACAKLI HESAP : 00759 / 7654321 AD SOYAD"
    m = re.match(r"\d+\s*/\s*\d+\s+(.+)", fields.get("ALACAKLI HESAP"))
    return fields.get("ALACAKLI") or (m[1] if m else "")


def _account(number: str, currency: str) -> Account:
    """The account the lists name ("garanti-1234567"); a masked number keeps only the digits shown."""
    account = bank_account("Garanti BBVA", number, currency)
    if "*" in number:
        account.label = account.label.replace(number, "…" + number.rsplit("*", 1)[1])
    return account


def parse(doc, pdf) -> ParseResult:
    lines = page_lines(pdf.pages[0])
    fields = _Fields(lines)
    holder = _holder(lines)
    if is_business(holder):
        raise Skipped(BUSINESS_REASON, business=True)
    number = re.match(r"\d+\s*/\s*([\d*]+)", fields.get("HESAP NUMARASI"))
    day = parse_dmy(fields.get("ISLEM TARIHI"))  # incoming transfers append a reference: "01/10/2026-EF08/22"
    amount = _amount(lines)
    if not (number and day and amount):
        raise ValueError("Garanti dekontunda hesap numarası, işlem tarihi ya da tutar bulunamadı")
    printed, currency = amount
    branch = next((i for i, line in enumerate(lines) if line.folded.startswith("SUBE ADI")), 0)
    heading = lines[branch - 1].folded if branch else ""  # the receipt's title sits right above
    title = _TITLES.get(heading) or ("Gelen Transfer" if printed > 0 else title_tr(heading) or "Transfer")
    account = _account(number[1], currency)
    sequence = re.search(r"SIRA NO\s*:\s*(\S+)", " ".join(line.folded for line in lines))
    result = ParseResult(
        parser=NAME,
        accounts=[account],
        holder=holder,
        title=title,
        receipt_key=f"garanti-dekont-{sequence[1] if sequence else doc.sha256}",
    )
    note = _note(lines, title)
    if printed < 0:
        party, arrow = _receiver(fields), "→"
        bank = bank_from_iban(fields.get("ALACAKLI IBAN"))
    else:
        party, arrow = fields.get("GONDEREN"), "←"
        bank = fields.get("GONDEREN BANKA").split("(")[0].strip()
    text = f"{title} {arrow} {party}" + (f" ({bank})" if bank else "") + (f" — {note}" if note else "")
    # Whether it went to the user's own account, the landlord or a friend is decided once every
    # account is known (analysis.py), like a transfer row of an account list.
    result.transactions.append(
        Transaction(
            date=day,
            description=text,
            amount=-printed,
            kind=TransactionKind.TRANSFER_CANDIDATE,
            account=account.id,
            counterparty=party,
            source=doc.name,
            original=f"{format_tr_amount(abs(printed))} {currency}" if currency != TRY else "",
        )
    )
    fee_text = fields.get("KOMISYON TOPLAMI") or fields.get("MASRAF TOPLAMI")
    fee = re.match(r"([\d.]+,\d{2})\s*(TL|EUR|USD|GBP)?", fee_text)
    payer = _fee_account(fields, currency_code(fee[2] or ""), account) if fee and parse_tr_amount(fee[1]) else None
    if payer:
        if payer.id != account.id:
            result.accounts.append(payer)
        result.transactions.append(
            Transaction(
                date=day,
                description=f"{title} masrafı ve BSMV",
                amount=parse_tr_amount(fee[1]),
                kind=TransactionKind.INTEREST_FEE,
                account=payer.id,
                source=doc.name,
            )
        )
    return result


def _fee_account(fields: _Fields, currency: str, account: Account) -> Account | None:
    """The account the fee was taken from ("KOMİSYON HESABI : 00106 / 1234567"), else the transfer's own
    account when the fee is in its currency."""
    payer = re.match(r"\d+\s*/\s*(\d+)", fields.get("KOMISYON HESABI") or fields.get("MASRAF HESABI"))
    if payer:
        return bank_account("Garanti BBVA", payer[1], currency)
    return account if currency == account.currency else None
