"""Readable names for documents, after the MVP organizer's scheme (ADR-0003):

    <Banka>/<Hesap veya kart>/<tarih> <banka> <hesap> <belge türü>.<uzantı>

The vault keeps originals by content; these names are what a download is called and how a read-only tree
can be laid out for browsing.
"""

import re
from pathlib import PurePosixPath

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
    folders = {
        "Kredi kartı": (f"{product} Kredi Kartı {number}", f"{product} {number}"),
        "Banka kartı": (f"{product} Banka Kartı {number}", f"{product} {number}"),
        "Vadesiz hesap": (f"Vadesiz Hesap {a.currency} {number}", f"Vadesiz {a.currency} {number}"),
        "Vadeli hesap": (f"Vadeli Hesap {a.currency} {number}", f"Vadeli {a.currency} {number}"),
        "Yatırım hesabı": (f"Yatırım Hesabı {number}", f"Yatırım {number}"),
        "Döviz hesabı": (f"Döviz Hesabı {a.currency} {number}", f"Döviz {a.currency} {number}"),
        "Ek hesap (KMH)": (f"Ek Hesap (KMH) {number}", f"Ek Hesap {number}"),
        "Altın hesabı": (f"Altın Hesabı {number}", f"Altın {number}"),
        "Kredi": (f"İhtiyaç Kredisi {number}", f"Kredi {number}"),
    }
    folder, short = folders.get(a.type, (a.label, a.label))
    if nickname:
        folder, short = f"{folder} {nickname}", f"{short} {nickname}"
    return name_part(folder), name_part(short)


def display_path(result: ParseResult, ext: str) -> PurePosixPath:
    """Where a read document sits in the organizer's tree: bank, account, then its name."""
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
    return PurePosixPath(a.bank, folder, f"{t.date:%Y-%m-%d} {bank} {name_part(result.title or 'İşlem')} Dekont{ext}")


def display_name(result: ParseResult, ext: str) -> str:
    return display_path(result, ext).name
