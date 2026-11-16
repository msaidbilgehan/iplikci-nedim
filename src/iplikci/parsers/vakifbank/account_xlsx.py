"""Vakıfbank account movement exports ("Hesap Hareketleri", XLSX)."""

import re

from ...domain.codes import DocumentKind
from ...domain.models import ParseResult
from ...domain.text import fold, title_tr
from ..accounts import bank_account, period_of
from ..common import Skipped
from ..contract import Detection, Format, Probe, SourceDocument
from ..movements import Movement, build_statement, receiver_after_bank, sender_after_bank
from ..sheet import cells, key_values, to_date, to_number

ID = "vakifbank.account_xlsx"


def read(doc: SourceDocument) -> ParseResult:
    rows = doc.rows
    header = next((i for i, r in enumerate(rows) if "HESAP NO" in cells(r) and "İŞLEM" in cells(r)), None)
    if header is None:
        raise Skipped("Vakıfbank tablo başlığı yok")
    info = key_values(rows[:header])
    iban = re.sub(r"\s", "", info.get("IBAN", ""))
    number = iban[-16:] if iban else ""
    currency = (
        "TL" if fold(info.get("HESAP TÜRÜ", "")).endswith("TL") else info.get("HESAP TÜRÜ", "").split()[-1].upper()
    )
    account = bank_account("Vakıfbank", number, currency)
    nickname = info.get("RUMUZ", "")
    if nickname:
        account.label += f" ({nickname})"
    col = {str(v).strip(): i for i, v in enumerate(rows[header]) if v is not None}
    moves = []
    for i, r in enumerate(rows[header + 1 :], header + 1):
        d = to_date(r[col["İŞLEM TARİHİ"]])
        amount = to_number(r[col["TUTAR"]])
        if not d or amount is None:
            continue
        label = str(r[col["İŞLEM"]] or "").strip()
        desc = str(r[col["AÇIKLAMA"]] or "").strip()
        if amount < 0:
            counterparty = receiver_after_bank(desc)
        else:
            counterparty = sender_after_bank(desc)
            salary = re.search(r"\(\d+_\d+_(.+?)\)", desc)
            if salary:
                counterparty = title_tr(salary[1])
            company = re.search(r"sorgu numaralı (.+?) tarafından", desc)
            if company:
                counterparty = company[1]
        moves.append(
            Movement(
                d,
                f"{label}: {desc}" if label else desc,
                amount,
                to_number(r[col["BAKİYE"]]),
                label,
                counterparty,
                doc.row_ref(i),
            )
        )
    start, end = period_of(info.get("TARİH ARALIĞI", ""))
    stmt = build_statement(doc, account, moves, start, end, oldest_first=True)
    return ParseResult(parser=ID, accounts=[account], statements=[stmt], holder=info.get("HESAP SAHİBİ", ""))


class AccountXlsx:
    id = ID
    version = 2
    bank = "Vakıfbank"
    name = "Vakıfbank hesap hareketleri (XLSX)"
    document_type = DocumentKind.ACCOUNT_STATEMENT
    formats = frozenset({Format.SHEET})

    def detect(self, probe: Probe) -> Detection | None:
        head = fold(" ".join(" ".join(cells(r)) for r in probe.rows[:10]))
        if probe.sheet == "xlsx" and "VB MUSTERI NO" in head:
            return Detection(1.0, 'XLSX tablonun başında "VB Müşteri No"')
        return None

    def parse(self, doc: SourceDocument) -> ParseResult:
        return read(doc)


PARSER = AccountXlsx()
