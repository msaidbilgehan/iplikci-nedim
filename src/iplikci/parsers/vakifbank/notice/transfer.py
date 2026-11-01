"""Vakıfbank's transfer notices (K21): the e-mails it sends when a FAST payment comes in or goes out ("VAKIFBANK -
FAST Anlık Ödeme Bilgilendirmesi") and when money leaves a deposit account by EFT ("Bilgilendirme: Mevduat Hesabı Para
Çıkışları").

The body is a table of "Label : value" rows under a sentence that says which way the money went: "Hesabınıza FAST
Anlık Ödeme gelmiştir." (in), "Bankamızdan gönderdiğiniz FAST Anlık Ödeme işleminiz başarı ile
gerçekleştirilmiştir." (out) or "Mevduat hesabınızdan gerçekleşen para çıkış detayları aşağıda yer almaktadır." (out).
The account number is masked but for its last four digits ("*************1234", "00158********1234"), the names but
for the first letters of their words ("Ör**** Ki****"). A FAST notice ends with the account's balance after the
payment ("Güncel Bakiye : 2.000 TL"); an amount drops its decimals when they are zero ("2.000 TL", "12.345,67 TL").

Vakıfbank mails no account list, so these notices are what the mailbox tells of the account. The account keeps the
masked number; a list the user adds later takes the rows over (analysis.resolve_masked).
"""

import re
from decimal import Decimal

from ....domain.codes import DocumentKind, TransactionKind
from ....domain.labels import format_amount
from ....domain.models import TRY, Account, ParseResult, SourceRef, Transaction
from ....domain.text import fold
from ...accounts import bank_account
from ...common import BUSINESS_REASON, Skipped, currency_code, is_business
from ...contract import Detection, Format, Probe, SourceDocument
from ...text import parse_dmy, squash, unfold_span

ID = "vakifbank.notice.transfer"
SENDER = "vakifbank.com.tr"
# The labels of the body's table, folded. A value runs to the next label, the last one to the closing words.
_LABELS = (
    "ISLEM TARIHI",
    "HESAP NUMARASI",
    "GONDEREN BANKA",
    "GONDEREN ADI SOYADI",
    "ALICI BANKA",
    "ALICI ADI SOYADI",
    "ALICI IBAN",
    "SORGU NUMARASI",
    "ISLEM KANALI",
    "ISLEM TIPI",
    "ISLEM TUTARI",
    "GUNCEL BAKIYE",
)
_LABEL = re.compile(r"\b(" + "|".join(_LABELS) + r") ?: ?")
_CLOSING = re.compile(r"\bSAYGILARIMIZLA\b")
_MONEY = re.compile(r"(-)?(\d{1,3}(?:\.\d{3})+|\d+)(?:,(\d{2}))? ?(TL|TRY|USD|EUR|GBP)\b")
_SHOWN = re.compile(r"[\d*]*(\d{4})")  # an account number, masked or not, and its last four digits
# The sentence above the table: money in, or out by FAST or another way (EFT, havale).
_IN, _OUT_FAST, _OUT = "HESABINIZA FAST", "GONDERDIGINIZ FAST", "PARA CIKIS"
_GREETING, _SENTENCES = "SAYIN ", ("HESABINIZA", "BANKAMIZDAN", "MEVDUAT HESABINIZDAN")


class _Fields:
    """The values of the body's "Label : value" rows and where each one is in the body's text."""

    def __init__(self, text: str) -> None:
        self.text = text
        self.folded = fold(text)
        found = list(_LABEL.finditer(self.folded))
        closing = _CLOSING.search(self.folded)
        stop = closing.start() if closing else len(self.folded)
        self.head = self.folded[: found[0].start()] if found else self.folded  # the greeting and the sentence
        self._spans: dict[str, tuple[int, int]] = {}
        for here, after in zip(found, [*found[1:], None], strict=True):
            self._spans.setdefault(here[1], (here.end(), max(here.end(), after.start() if after else stop)))
        # A colon inside a value is a row whose label this reader does not know, running into the value before it:
        # the bank changed the notice, and a name or an amount read now could be wrong.
        for label in self._spans:
            if " : " in f" {self.folded_value(label)} ":
                raise ValueError(f"Vakıfbank bildiriminde {label} satırından sonra tanınmayan bir alan var")

    def folded_value(self, label: str) -> str:
        """The value folded (upper case, no marks); "" when the notice has no such row."""
        start, end = self._spans.get(label, (0, 0))
        return self.folded[start:end].strip()

    def value(self, label: str) -> str:
        """The value as printed, its letters' case and marks kept."""
        span = self.span(label)
        return self.text[span[0] : span[1]] if span else ""

    def span(self, label: str) -> tuple[int, int] | None:
        """Where the value is in the body's text, without the spaces around it."""
        start, end = self._spans.get(label, (0, 0))
        value = self.folded[start:end]
        start, end = start + len(value) - len(value.lstrip()), end - len(value) + len(value.rstrip())
        return unfold_span(self.text, start, end) if start < end else None


def _money(fields: _Fields, label: str) -> tuple[Decimal, str] | None:
    """An amount as the notice prints it ("2.000 TL", "-12.345,67 TL"): the amount and its currency."""
    found = _MONEY.match(fields.folded_value(label))
    if found is None:
        return None
    sign, whole, cents, currency = found.groups()
    value = Decimal(f"{whole.replace('.', '')}.{cents or '00'}")
    return (-value if sign else value), currency_code(currency)


def _holder(fields: _Fields) -> str:
    """The customer's name between "Sayın" and the sentence when the notice prints it whole; Vakıfbank masks it."""
    head = fields.head
    start = head.find(_GREETING)
    if start < 0:
        return ""
    start += len(_GREETING)
    ends = [i for i in (head.find(s, start) for s in _SENTENCES) if i > start]
    span = unfold_span(fields.text, start, min(ends)) if ends else None
    name = fields.text[span[0] : span[1]].strip() if span else ""
    return "" if "*" in name else name


def _account(number: str, currency: str) -> Account:
    """The account by the last four digits the notice shows: one id for every notice of it ("vakifbank-****1234")."""
    shown = _SHOWN.fullmatch(number.replace(" ", ""))
    if shown is None:
        raise ValueError("Vakıfbank bildiriminde hesap numarası bulunamadı")
    number = "****" + shown[1]
    account = bank_account("Vakıfbank", number, currency)
    account.label = account.label.replace(number, "…" + shown[1])
    return account


def _way(fields: _Fields) -> tuple[str, int, str, str]:
    """Which way the money went: the title, +1 for money out or -1 for money in, and the labels of the other side's
    bank and name."""
    head = fields.head
    if _IN in head:
        return "Gelen FAST", -1, "GONDEREN BANKA", "GONDEREN ADI SOYADI"
    if _OUT_FAST in head:
        return "Giden FAST", 1, "ALICI BANKA", "ALICI ADI SOYADI"
    if _OUT in head:
        kind = fields.folded_value("ISLEM TIPI")
        title = "Giden EFT" if "EFT" in kind else "Giden Havale" if "HAVALE" in kind else "Para Çıkışı"
        return title, 1, "ALICI BANKA", "ALICI ADI SOYADI"
    raise ValueError("Vakıfbank bildiriminde paranın yönü bulunamadı")


def read(doc: SourceDocument) -> ParseResult:
    fields = _Fields(doc.mail.text)
    holder = _holder(fields)
    if is_business(holder):
        raise Skipped(BUSINESS_REASON, business=True)
    title, sign, bank_label, party_label = _way(fields)
    day = parse_dmy(fields.folded_value("ISLEM TARIHI"))
    amount = _money(fields, "ISLEM TUTARI")
    if day is None or amount is None:
        raise ValueError("Vakıfbank bildiriminde işlem tarihi ya da tutarı bulunamadı")
    value, currency = amount
    account = _account(fields.folded_value("HESAP NUMARASI"), currency)
    balance = _money(fields, "GUNCEL BAKIYE")
    query = re.match(r"\d+", fields.folded_value("SORGU NUMARASI"))
    bank, party = fields.value(bank_label), fields.value(party_label)
    arrow = "←" if sign < 0 else "→"
    text = f"{title} {arrow} {party} ({bank})" if party and bank else f"{title} {arrow} {party or bank or 'banka'}"
    # Whether it went to the user's own account, the landlord or a friend is decided once every account is known
    # (analysis.py), like a transfer row of an account list.
    row = Transaction(
        date=day,
        description=text,
        amount=sign * value,
        kind=TransactionKind.TRANSFER_CANDIDATE,
        account=account.id,
        counterparty=party,
        source=doc.name,
        ref=SourceRef(span=fields.span("ISLEM TUTARI")),
        original=f"{format_amount(value)} {currency}" if currency != TRY else "",
        balance=balance[0] if balance and balance[1] == currency else None,
    )
    return ParseResult(
        parser=ID,
        accounts=[account],
        transactions=[row],
        receipt_key=f"vakifbank-{day:%Y%m%d}-{query[0] if query else doc.sha256}",
        holder=holder,
        title=title,
    )


class TransferNotice:
    id = ID
    version = 1
    bank = "Vakıfbank"
    name = "Vakıfbank FAST ve EFT bildirimi"
    document_type = DocumentKind.NOTICE
    formats = frozenset({Format.EMAIL})

    def detect(self, probe: Probe) -> Detection | None:
        s = squash(probe.text)
        ours = probe.sender == SENDER or probe.sender.endswith("." + SENDER)
        if ours and "HESAPNUMARASI" in s and "ISLEMTUTARI" in s and ("FASTANLIKODEME" in s or "PARACIKIS" in s):
            return Detection(1.0, "vakifbank.com.tr'den FAST ya da para çıkışı bildirimi: hesap numarası ve tutar")
        return None

    def parse(self, doc: SourceDocument) -> ParseResult:
        return read(doc)


PARSER = TransferNotice()
