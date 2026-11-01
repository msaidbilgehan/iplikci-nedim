"""Türkiye İş Bankası Maximum credit card statements (PDF); the company card is out of scope."""

import re
from decimal import Decimal

from ...domain.codes import AccountType, DocumentKind, TransactionKind
from ...domain.models import TRY, Account, ParseResult, Statement, Transaction
from ...domain.text import fold
from ..common import BUSINESS_REASON, Skipped, agreed, classify_kind, currency_code, installment_label, split_interest
from ..contract import Detection, Format, Probe, SourceDocument
from ..pdf import Line, find_header, find_word, page_lines, page_text, take_amount
from ..text import parse_dmy, parse_tr_amount, squash

ID = "isbank.maximum_card"
_DATE_PREFIX = re.compile(r"^(\d{2}/\d{2}/\d{4})(.*)$")
# This statement's due date: the summary prints it with dots and the box of limits under it again with slashes.
# "Bir Sonraki Son Ödeme Tarihi" is the next statement's.
_DUE = re.compile(r"(?<!SONRAKI)SONODEMETARIHI:?(\d{2}[./]\d{2}[./]\d{4})")


def _account(card_last4: str) -> Account:
    return Account(
        id=f"isbank-{card_last4}",
        label=f"İş Bankası Maximum •{card_last4}",
        bank="İş Bankası",
        type=AccountType.CREDIT_CARD,
        number=card_last4,
    )


def _amount(line: Line, edge: float):
    """İş Bankası prints credit balances with a leading '+' ("+123,45")."""
    amount, used = take_amount(line, edge)
    if amount is not None and (used[-1].text.startswith("+") or used[0].text == "+"):
        amount = -abs(amount)
    return amount, used


def _term(sq: str, label: str, currency: str) -> Decimal | None:
    """The amount the first page (squashed) prints after label, in the statement's currency. The minimum due is
    printed in a fixed width, its empty places filled with asterisks ("Ödenmesi Gereken Asgari Tutar: *1.234,56 TL",
    "*.597,67 TL"), and the box of limits runs its two columns into one line ("Toplam Kart Limiti: 60.000,00 TL Asgari
    Ödeme Oranı: %40,00")."""
    found = re.findall(label + r":?[*.]*(\d[\d.]*,\d{2})(TL|USD|EUR)?", sq)
    return agreed(parse_tr_amount(amount) if currency_code(unit) == currency else None for amount, unit in found)


def _row_description(line: Line, first_rest: str, amount_x0: float, ref_right: float | None) -> str:
    """Everything between the date (and the company card's reference number) and the amount."""
    parts = [first_rest] if first_rest else []
    for w in line.words[1:]:
        if w.x0 >= amount_x0:
            break
        if ref_right is not None and w.x1 <= ref_right + 2 and w.text.isdigit():
            continue  # REFERANS column
        parts.append(w.text)
    return " ".join(p for p in parts if p).strip()


def read(doc: SourceDocument) -> ParseResult:
    pdf = doc.pdf
    first = page_text(pdf.pages[0])
    sq = squash(first)
    if "SIRKETKREDIKARTI" in sq:
        raise Skipped(BUSINESS_REASON, business=True)
    card = re.search(r"KARTNUMARASI:?(\d{4})\*+(\d{4})", sq)
    cut = re.search(r"(?<!SONRAKI)HESAPKESIMTARIHI:?(\d{2}[./]\d{2}[./]\d{4})", sq)
    total_m = re.search(
        r"(?<!ERTELENEBILIR)(?<!ERTELENEN)(?<!TAKSITLENDIRILEN)HESAPOZETIBORCU:?([+-]?[\d.]+,\d{2})(TL|USD|EUR)?", sq
    )
    if not (card and cut):
        raise ValueError("kart numarası / hesap kesim tarihi bulunamadı")
    last4 = card[2]
    account = _account(last4)
    currency = currency_code(total_m[2]) if total_m and total_m[2] else TRY
    total = None
    if total_m:
        # A leading '+' marks a credit balance in the bank's favour of the customer.
        raw = total_m[1]
        total = parse_tr_amount(raw.lstrip("+"))
        if raw.startswith("+") and total is not None:
            total = -total

    stmt = Statement(
        account=account.id,
        cut_date=parse_dmy(cut[1]),
        currency=currency,
        source=doc.name,
        previous=None,
        total=total,
        due_date=agreed(parse_dmy(d) for d in _DUE.findall(sq)),
        minimum_payment=_term(sq, "ODENMESIGEREKENASGARITUTAR", currency),
        # The card's own limit, not the customer's, what is left of it or the cash limit printed beside it.
        credit_limit=_term(sq, "TOPLAMKARTLIMITI", currency),
    )

    for page in pdf.pages:
        lines = page_lines(page)
        h = find_header(lines, "TUTAR", "MAXIPUAN")
        if h is None:
            continue
        header = lines[h]
        tutar = find_word(header, "TUTAR")
        referans = find_word(header, "REFERANS")
        taksit = find_word(header, "TAKSIT")
        last = None  # previous transaction on this page, for wrapped lines
        for line in lines[h + 1 :]:
            first_word = line.words[0].text
            if first_word.startswith("***") and "ONCEKI" in line.folded:
                stmt.previous, _ = _amount(line, tutar.x1)
                continue
            m = _DATE_PREFIX.match(first_word)
            if not m:
                # A cash-advance line may wrap its "FZ:.. VR/FN:.." interest breakdown.
                if last is not None and first_word.startswith("FZ:"):
                    last.description += " " + line.text
                last = None
                continue
            amount, used = _amount(line, tutar.x1)
            if amount is None:
                last = None
                continue  # informational line: points bonus, "taksitlendirildi", ...
            rest = m[2] if not m[2].startswith("-") else ""
            desc = _row_description(line, rest, used[0].x0, referans.x1 if referans else None)
            taksit_text = " ".join(
                w.text for w in line.words if taksit and w.x0 >= taksit.x0 - 25 and w not in used and w.x0 > tutar.x1
            )
            date = parse_dmy(m[1])
            f = fold(desc)
            if "HESAP OZETINE AKTARILAN" in f or "HESAPOZETINEAKTARILAN" in f:
                kind = TransactionKind.OWN_TRANSFER  # foreign-currency balance moved to the TL statement
            else:
                kind = classify_kind(desc, amount)
            last = Transaction(
                date=date,
                description=desc,
                amount=amount,
                kind=kind,
                account=account.id,
                installment=installment_label(taksit_text),
                source=doc.name,
                ref=line.ref,
            )
            stmt.transactions.append(last)

    stmt.transactions = [
        part
        for t in stmt.transactions
        for part in (split_interest(t) if t.kind == TransactionKind.CASH_ADVANCE else [t])
    ]
    holder = re.search(r"SN\.\s*([A-ZÇĞİÖŞÜ ]+?)\s+Hesap Kesim", first)
    return ParseResult(parser=ID, accounts=[account], statements=[stmt], holder=holder[1] if holder else "")


class MaximumCard:
    id = ID
    version = 3
    bank = "İş Bankası"
    name = "İş Bankası Maximum kart hesap özeti"
    document_type = DocumentKind.CARD_STATEMENT
    formats = frozenset({Format.PDF})

    def detect(self, probe: Probe) -> Detection | None:
        s = squash(probe.text)
        if "KREDIKARTIHESAPOZETI" in s and "MAXIPUAN" in s:
            return Detection(1.0, '"Kredi Kartı Hesap Özeti" ve MaxiPuan')
        return None

    def parse(self, doc: SourceDocument) -> ParseResult:
        return read(doc)


PARSER = MaximumCard()
