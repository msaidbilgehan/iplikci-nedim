"""Garanti BBVA account movement exports ("Hesap Hareketleri", XLS)."""

import re

from ...domain.codes import DocumentKind
from ...domain.models import ParseResult
from ...domain.text import fold
from ..accounts import bank_account
from ..common import Skipped
from ..contract import Detection, Format, Probe, SourceDocument
from ..movements import Movement, build_statement
from ..sheet import cells, key_values, to_date, to_number
from ..text import parse_dmy

ID = "garanti.account_xls"


def _counterparty(desc: str, label: str) -> str:
    if fold(label) != "PARA TRANSFERI":
        return ""
    text = re.sub(r"^FAST\d+-", "", desc.strip())
    if "Havale" in text:
        return text.split("Havale")[0].strip()
    return text.split("-")[0].strip()


def read(doc: SourceDocument) -> ParseResult:
    rows = doc.rows
    header = next((i for i, r in enumerate(rows) if cells(r)[:3] == ["Tarih", "Açıklama", "Etiket"]), None)
    if header is None:
        raise Skipped("Garanti tablo başlığı yok")
    info = key_values(rows[:header])
    m = re.match(r"(\d+)\s*-\s*(\d+)\s+(\w+)", info.get("Hesap", ""))
    if not m:
        raise ValueError("Garanti hesap numarası okunamadı")
    account = bank_account("Garanti BBVA", m[2], m[3].upper())
    cols = {name: i for i, name in enumerate(str(v).strip() for v in rows[header])}
    moves = []
    for r in rows[header + 1 :]:
        d = to_date(r[cols["Tarih"]])
        amount = to_number(r[cols["Tutar"]])
        if not d or amount is None:
            continue
        desc, label = str(r[cols["Açıklama"]]).strip(), str(r[cols["Etiket"]]).strip()
        moves.append(Movement(d, desc, amount, to_number(r[cols["Bakiye"]]), label, _counterparty(desc, label)))
    start, end = parse_dmy(info.get("Başlangıç", "")), parse_dmy(info.get("Bitiş", ""))
    stmt = build_statement(doc, account, moves, start, end, oldest_first=False)
    # Company accounts carry "Şirket Ünvanı" instead of "Ad Soyad".
    holder = info.get("Ad Soyad") or info.get("Şirket Ünvanı", "")
    return ParseResult(parser=ID, accounts=[account], statements=[stmt], holder=holder)


class AccountXls:
    id = ID
    version = 1
    bank = "Garanti BBVA"
    name = "Garanti BBVA hesap hareketleri (XLS)"
    document_type = DocumentKind.ACCOUNT_STATEMENT
    formats = frozenset({Format.SHEET})

    def detect(self, probe: Probe) -> Detection | None:
        head = fold(" ".join(" ".join(cells(r)) for r in probe.rows[:16]))
        if probe.sheet == "xls" and "GARANTI BANKASI" in head:
            return Detection(1.0, "XLS tablonun başında Garanti Bankası adı")
        return None

    def parse(self, doc: SourceDocument) -> ParseResult:
        return read(doc)


PARSER = AccountXls()
