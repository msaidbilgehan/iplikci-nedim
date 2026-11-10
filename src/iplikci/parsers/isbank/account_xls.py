"""İş Bankası account summaries ("Hesap Özeti", XLS).

A FAST, EFT or havale row names the other side first ("<AD SOYAD>*<açıklama>*…"). A transfer between two accounts at
the bank ("Para Transferi") names the account it went to and its holder: "1234/0123456 HESABA <AD SOYAD> Hesaplar
Arası Akt"; the user's own name there makes it a transfer between own accounts, whether or not a document of the other
account has come.
"""

import re

from ...domain.codes import DocumentKind
from ...domain.models import ParseResult
from ...domain.text import fold
from ..accounts import bank_account, period_of
from ..common import Skipped
from ..contract import Detection, Format, Probe, SourceDocument
from ..movements import Movement, build_statement
from ..sheet import cells, key_values, to_date, to_number

ID = "isbank.account_xls"


def _receiver(desc: str) -> str:
    """Whom a transfer between two accounts at the bank went to: the words between "HESABA" and "Hesaplar Arası"; ""
    for any other text."""
    words = desc.split()
    folded = [fold(w) for w in words]
    if "HESABA" not in folded:
        return ""
    start = folded.index("HESABA") + 1
    end = next((j for j in range(start, len(folded) - 1) if folded[j : j + 2] == ["HESAPLAR", "ARASI"]), start)
    return " ".join(words[start:end])


def read(doc: SourceDocument) -> ParseResult:
    rows = doc.rows
    header = next((i for i, r in enumerate(rows) if str(r[0]).strip().startswith("Tarih/Saat")), None)
    if header is None:
        raise Skipped("İş Bankası tablo başlığı yok")
    info = key_values(rows[:header])
    holder = next(
        (c[0].replace("Sayın", "").strip() for c in map(cells, rows[:header]) if c and c[0].startswith("Sayın")), ""
    )
    digits = re.sub(r"\D", "", info.get("IBAN", ""))
    branch_account = re.search(r"(\d{4})(\d{7})$", digits)  # IBAN ends with branch (4) + account (7)
    number = f"{branch_account[1]}-{branch_account[2]}" if branch_account else digits[-11:]
    currency = "TL"
    balance_text = info.get("Mevcut Bakiye", "")
    for cur in ("USD", "EUR", "GBP"):
        if cur in balance_text:
            currency = cur
    account = bank_account("İş Bankası", number, currency)
    names = [str(v).strip() for v in rows[header]]
    col = {n: i for i, n in enumerate(names) if n}
    desc_start, desc_end = col["Açıklama"], col.get("Referans", len(names))
    moves = []
    for i, r in enumerate(rows[header + 1 :], header + 1):
        d = to_date(str(r[0]))
        amount = to_number(r[col["İşlem Tutarı*"]])
        if not d or amount is None:
            continue
        desc = " ".join(str(v).strip() for v in r[desc_start:desc_end] if str(v).strip())
        label = str(r[col["İşlem Tipi"]]).strip()
        named = label in ("FAST", "EFT", "Havale") and "*" in desc
        counterparty = desc.split("*")[0].strip() if named else _receiver(desc)
        moves.append(Movement(d, desc, amount, to_number(r[col["Bakiye"]]), label, counterparty, doc.row_ref(i)))
    start, end = period_of(info.get("Sorgulama Kriterleri", ""))
    stmt = build_statement(doc, account, moves, start, end, oldest_first=False)
    return ParseResult(parser=ID, accounts=[account], statements=[stmt], holder=holder)


class AccountXls:
    id = ID
    version = 2
    bank = "İş Bankası"
    name = "İş Bankası hesap özeti (XLS)"
    document_type = DocumentKind.ACCOUNT_STATEMENT
    formats = frozenset({Format.SHEET})

    def detect(self, probe: Probe) -> Detection | None:
        head = fold(" ".join(" ".join(cells(r)) for r in probe.rows[:16]))
        if probe.sheet == "xls" and "HESAP OZETI" in head and "URUN-DOVIZ TIPI" in head:
            return Detection(1.0, 'XLS tablonun başında "Hesap Özeti" ve "Ürün-Döviz Tipi"')
        return None

    def parse(self, doc: SourceDocument) -> ParseResult:
        return read(doc)


PARSER = AccountXls()
