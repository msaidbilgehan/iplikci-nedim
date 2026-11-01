"""TEB Bonus credit card statements, with a text layer or as page images read with OCR (PDF)."""

import re
from decimal import Decimal

from ...domain.codes import DocumentKind
from ...domain.models import TRY, Account, ParseResult, Statement, Transaction
from ...domain.text import fold
from ..common import Skipped, classify_kind, installment_label
from ..contract import Detection, Format, Probe, SourceDocument
from ..pdf import Line, find_header, find_word, page_lines, page_text, take_amount
from ..text import parse_dmy, parse_tr_amount, squash
from ._card import card_account

ID = "teb.bonus_card"

# "12/11 FİNDEKS ... (9/8. Taksit)" and "ornek.com ... (Yurt dışı işlem tutarı EUR.12,34)"
_ORIGINAL_DATE = re.compile(r"^\d{2}/\d{2}\s+")
_INSTALLMENT = re.compile(r"\((\d{1,2})/(\d{1,2})\.\s*taksit\)", re.IGNORECASE)
_FOREIGN = re.compile(r"\(Yurt\s*dışı\s*işlem\s*tutarı\s*([A-Z]{3})\.([\d.]+,(?:\d{1,2}|-))\)", re.IGNORECASE)
_CARD = re.compile(r"KARTNUMARASI:?(\d{6,8})\*{4,6}(\d{4})")


def _split_description(desc: str) -> tuple[str, str, str]:
    """Return (clean description, installment 'k/n', original foreign amount)."""
    installment = original = ""
    m = _INSTALLMENT.search(desc)
    if m:
        installment = f"{int(m[2])}/{int(m[1])}"
        desc = desc.replace(m[0], "")
    m = _FOREIGN.search(desc)
    if m:
        amount = parse_tr_amount(m[2])
        original = f"{amount:.2f} {m[1].upper()}".replace(".", ",") if amount is not None else ""
        desc = desc.replace(m[0], "")
    return _ORIGINAL_DATE.sub("", desc).strip(), installment, original


def _parse_statement(doc: SourceDocument, first: str) -> ParseResult:
    sq = squash(first)
    card = _CARD.search(sq)
    cut = re.search(r"(?<!SONRAKI)HESAPKESIMTARIHI:?(\d{2}/\d{2}/\d{4})", sq)
    total = re.search(r"DONEMBORCU:?(TL\.?[\d.]+,(?:\d{2}|-))", sq)
    if not (card and cut):
        raise ValueError("kart numarası / hesap kesim tarihi bulunamadı")
    account = card_account(card[2])
    stmt = Statement(
        account=account.id,
        cut_date=parse_dmy(cut[1]),
        currency=TRY,
        source=doc.name,
        previous=Decimal(0),
        total=parse_tr_amount(total[1]) if total else None,
    )
    for page in doc.pdf.pages:
        lines = page_lines(page)
        start = 0
        while True:
            h = find_header(lines[start:], "TARIH", "TUTAR", "BONUS")
            if h is None:
                break
            h += start
            _parse_section(lines, h, stmt, account, doc)
            start = h + 1
    holder = re.search(r"SAYIN\s*([A-ZÇĞİÖŞÜ ]+?)\s*(?:\n|HESAP|SON)", first)
    return ParseResult(parser=ID, accounts=[account], statements=[stmt], holder=holder[1] if holder else "")


def _add(stmt: Statement, account: Account, doc: SourceDocument, line: Line, date, desc: str, amount: Decimal) -> None:
    desc, installment, original = _split_description(desc)
    stmt.transactions.append(
        Transaction(
            date=date,
            description=desc,
            amount=amount,
            kind=classify_kind(desc, amount),
            account=account.id,
            installment=installment or installment_label(desc),
            original=original,
            source=doc.name,
            ref=line.ref,
        )
    )


def _parse_section(lines: list[Line], h: int, stmt: Statement, account: Account, doc: SourceDocument) -> None:
    header = lines[h]
    tutar = find_word(header, "TUTAR")
    for line in lines[h + 1 :]:
        if find_word(line, "TARIH") and find_word(line, "TUTAR"):
            return  # next card section (ek kart) starts here
        amount, used = take_amount(line, tutar.x0, align="left")
        if amount is None:
            continue
        date = parse_dmy(line.words[0].text)
        desc = " ".join(w.text for w in line.words[1 if date else 0 :] if w not in used and w.x1 < tutar.x0 - 4)
        if date is None:
            if "DEVIR" in fold(desc):
                stmt.previous = amount
            continue  # per-card subtotal lines
        _add(stmt, account, doc, line, date, desc, amount)


# --- statements delivered as page images, read with OCR -------------------------


def _tl(text: str) -> Decimal | None:
    m = re.search(r"-?TL\.?\s*[\d.]+,(?:\d{1,2}|-)", text.replace(" ", ""))
    return parse_tr_amount(m[0]) if m else None


def _parse_ocr(doc: SourceDocument, pages: list[list[Line]]) -> ParseResult:
    """Each OCR "word" is one table cell: [sıra] [tarih] [açıklama] [tutar] [kalan taksit] [bonus]."""
    lines = [line for page in pages for line in page]
    text = "\n".join(line.text for line in lines)
    card = re.search(r"\d{6}\*{6}(\d{4})", text)
    cut = next((re.search(r"\d{2}/\d{2}/\d{4}", ln.text) for ln in lines if "Hesap Kesim" in ln.text), None)
    total = next((_tl(ln.text) for ln in lines if "Dönem Borcu" in ln.text), None)
    if not (card and cut):
        raise ValueError("OCR: kart numarası / hesap kesim tarihi okunamadı")
    account = card_account(card[1])
    stmt = Statement(
        account=account.id, cut_date=parse_dmy(cut[0]), currency=TRY, source=doc.name, previous=Decimal(0), total=total
    )
    for line in lines:
        if "ÖNCEKİ DÖNEM" in line.text.upper():
            stmt.previous = _tl(line.text) or Decimal(0)
            continue
        date_i = next((i for i, w in enumerate(line.words) if re.fullmatch(r"\d{2}/\d{2}/\d{4}", w.text)), None)
        if date_i is None or date_i > 1:
            continue
        rest = line.words[date_i + 1 :]
        amount_i = next(
            (i for i, w in enumerate(rest) if re.fullmatch(r"-?TL\.?[\d.]+,(?:\d{1,2}|-)", w.text.replace(" ", ""))),
            None,
        )
        if amount_i is None or amount_i == 0:
            continue
        desc = " ".join(w.text for w in rest[:amount_i])
        desc = re.sub(r"[^\w)]+$", "", desc).strip()  # contactless-payment icon read as ")))"
        _add(
            stmt,
            account,
            doc,
            line,
            parse_dmy(line.words[date_i].text),
            desc,
            parse_tr_amount(rest[amount_i].text.replace(" ", "")),
        )
    return ParseResult(parser=ID, accounts=[account], statements=[stmt])


class BonusCard:
    id = ID
    version = 1
    bank = "TEB"
    name = "TEB Bonus kart ekstresi"
    document_type = DocumentKind.CARD_STATEMENT
    formats = frozenset({Format.PDF, Format.SCAN})

    def detect(self, probe: Probe) -> Detection | None:
        s = squash(probe.text)
        # TEB's card payment receipt is the receipt reader's.
        if "KREDIKARTEKSTREOZETI" in s and "KREDIKARTIODEMEDEKONTU" not in s:
            return Detection(1.0, '"Kredi Kart Ekstre Özeti" başlığı')
        return None

    def parse(self, doc: SourceDocument) -> ParseResult:
        if doc.scanned:
            return _parse_ocr(doc, doc.ocr_pages)
        first = page_text(doc.pdf.pages[0])
        if "GIRISIMCI" in squash(first):
            raise Skipped("şirket kartı (Girişimci) — kapsam dışı")
        return _parse_statement(doc, first)


PARSER = BonusCard()
