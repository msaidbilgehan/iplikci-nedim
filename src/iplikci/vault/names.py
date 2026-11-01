"""Readable names for documents, after the MVP organizer's scheme (ADR-0003):

    <Banka>/<Hesap veya kart>/<tarih> <banka> <hesap> <belge türü>.<uzantı>

The vault keeps originals by content; these names are what a download is called and how a read-only tree
can be laid out for browsing.
"""

import re
from pathlib import PurePosixPath

from ..domain.codes import AccountType, DocumentKind
from ..domain.labels import currency_label
from ..domain.models import Account, ParseResult

_BANK_SHORT = {"Garanti BBVA": "Garanti"}
_NOT_IN_NAMES = re.compile(r'[/\\:*?"<>|\x00-\x1f]')  # path separators and what Windows refuses in a name


def name_part(text: str) -> str:
    return _NOT_IN_NAMES.sub("-", text)


def account_names(a: Account) -> tuple[str, str]:
    """(folder name, short name used inside file names) for an account or card."""
    number = (a.label.split()[-1] if a.label.split()[-1].startswith("…") else a.number).lstrip("…")
    nickname = a.label[a.label.index("(") :] if a.label.endswith(")") and "(" in a.label else ""
    product = a.label.replace(a.bank, "", 1).split("•")[0].strip()
    cur = currency_label(a.currency)
    folders = {
        AccountType.CREDIT_CARD: (f"{product} Kredi Kartı {number}", f"{product} {number}"),
        AccountType.DEBIT_CARD: (f"{product} Banka Kartı {number}", f"{product} {number}"),
        AccountType.CURRENT: (f"Vadesiz Hesap {cur} {number}", f"Vadesiz {cur} {number}"),
        AccountType.DEPOSIT: (f"Vadeli Hesap {cur} {number}", f"Vadeli {cur} {number}"),
        AccountType.BROKERAGE: (f"Yatırım Hesabı {number}", f"Yatırım {number}"),
        AccountType.FX: (f"Döviz Hesabı {cur} {number}", f"Döviz {cur} {number}"),
        AccountType.OVERDRAFT: (f"Ek Hesap (KMH) {number}", f"Ek Hesap {number}"),
        AccountType.GOLD: (f"Altın Hesabı {number}", f"Altın {number}"),
        AccountType.LOAN: (f"İhtiyaç Kredisi {number}", f"Kredi {number}"),
    }
    folder, short = folders.get(a.type, (a.label, a.label))
    if nickname:
        folder, short = f"{folder} {nickname}", f"{short} {nickname}"
    return name_part(folder), name_part(short)


# The words a seller's name ends with that say only what kind of company it is: a file name goes without them.
_LEGAL_FORMS = re.compile(
    r"(?:\s+(?:A\.?Ş\.?|ANONİM|ŞİRKETİ|LTD\.?|LİMİTED|ŞTİ\.?|SAN\.?|TİC\.?|VE))+\s*$", re.IGNORECASE
)


def _invoice_path(result: ParseResult, ext: str) -> PurePosixPath:
    """A non-bank sender's bill or receipt: Faturalar, the seller, then its date, the seller and what it is."""
    invoice = result.invoices[0]
    seller = name_part(_LEGAL_FORMS.sub("", invoice.seller).strip() or invoice.seller)
    word = "Fatura" if invoice.due else "Makbuz"
    return PurePosixPath("Faturalar", seller, f"{invoice.issued:%Y-%m-%d} {seller} {word}{ext}")


def display_path(result: ParseResult, ext: str, kind: DocumentKind | None = None) -> PurePosixPath:
    """Where a read document sits in the organizer's tree: bank, account, then its name. A document of rows alone is
    a receipt unless kind says it is a bank's notice; a non-bank sender's bill or receipt sits under Faturalar."""
    if not result.statements and not result.transactions and result.invoices:
        return _invoice_path(result, ext)
    if result.statements:
        s = result.statements[0]
        a = next(acc for acc in result.accounts if acc.id == s.account)
        folder, short = account_names(a)
        bank = _BANK_SHORT.get(a.bank, a.bank)
        who = short if short.startswith(bank) else f"{bank} {short}"  # not "Garanti Garanti Bonus"
        if s.is_account:
            name = f"{s.start:%Y-%m-%d} - {s.cut_date:%Y-%m-%d} {who} Hesap Hareketleri{ext}"
        else:
            name = f"{s.cut_date:%Y-%m-%d} {who} Ekstre{ext}"
        return PurePosixPath(a.bank, folder, name)
    t = result.transactions[0]
    a = next(acc for acc in result.accounts if acc.id == t.account)
    folder, _ = account_names(a)
    bank = _BANK_SHORT.get(a.bank, a.bank)
    word = "Bildirim" if kind is DocumentKind.NOTICE else "Dekont"
    return PurePosixPath(a.bank, folder, f"{t.date:%Y-%m-%d} {bank} {name_part(result.title or 'İşlem')} {word}{ext}")


def display_name(result: ParseResult, ext: str, kind: DocumentKind | None = None) -> str:
    return display_path(result, ext, kind).name
