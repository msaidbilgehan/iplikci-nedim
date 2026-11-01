"""İş Bankası's notice of an overdue card debt collected from an account ("Hesabınızdan Gecikmedeki Kredi Kartı
Borcunuzun Tahsilatı"): the bank took what was not paid by the due date from the customer's account.

The body is one sentence: "Merhaba, 1234 no ile biten kredi kartınıza ait son ödeme tarihinde ödenmeyen 1.258,21
TL'lik borç tutarı, 1234-567890 no'lu hesabınızdan takas yoluyla tahsil edilmiştir." The day is the message's, in
Turkey's time. The account number drops the leading zero of its seven digits ("1234-0567890" in the lists).

The row is a payment to the card, booked on the card like a card payment receipt (TEB's): the next statement shows
it, and until then it lowers the card's debt (insights.paid_after). The account's side is its list's own row.
"""

import re
from datetime import UTC, timedelta, timezone

from ....domain.codes import AccountType, DocumentKind, TransactionKind
from ....domain.models import Account, ParseResult, SourceRef, Transaction
from ....domain.text import fold
from ...contract import Detection, Format, Probe, SourceDocument
from ...text import parse_tr_amount, unfold_span

ID = "isbank.notice.collection"
SENDER = "isbank.com.tr"
_SENTENCE = re.compile(
    r"(\d{4}) NO ILE BITEN KREDI KARTINIZA AIT SON ODEME TARIHINDE ODENMEYEN ([\d.]+,\d{2}) TL.LIK BORC TUTARI, "
    r"(\d{4})-(\d{5,7}) NO.LU HESABINIZDAN TAKAS YOLUYLA TAHSIL EDILMISTIR"
)
_TURKEY = timezone(timedelta(hours=3))  # Turkey keeps UTC+3 all year (since 2016)


def _card(last4: str) -> Account:
    """The card as its statements name it (isbank.maximum_card)."""
    return Account(
        id=f"isbank-{last4}",
        label=f"İş Bankası Maximum •{last4}",
        bank="İş Bankası",
        type=AccountType.CREDIT_CARD,
        number=last4,
    )


def read(doc: SourceDocument) -> ParseResult:
    mail = doc.mail
    found = _SENTENCE.search(fold(mail.text))
    if found is None:
        raise ValueError("İş Bankası tahsilat bildiriminde cümle okunamadı")
    if mail.sent is None:
        raise ValueError("İş Bankası tahsilat bildiriminin gönderildiği tarih yok")
    amount = parse_tr_amount(found[2])
    if amount is None:
        raise ValueError(f"İş Bankası tahsilat bildiriminde tutar okunamadı: {found[2]!r}")
    day = (mail.sent if mail.sent.tzinfo else mail.sent.replace(tzinfo=UTC)).astimezone(_TURKEY).date()
    card = _card(found[1])
    paying = f"{found[3]}-{found[4].zfill(7)}"
    row = Transaction(
        date=day,
        description=f"Maximum •{found[1]} gecikmiş borç tahsilatı ({paying} no'lu hesaptan)",
        amount=amount,
        kind=TransactionKind.CARD_PAYMENT_NO_STATEMENT,
        account=card.id,
        source=doc.name,
        ref=SourceRef(span=unfold_span(mail.text, *found.span(2))),
    )
    return ParseResult(
        parser=ID,
        accounts=[card],
        transactions=[row],
        receipt_key=f"isbank-tahsilat-{day:%Y%m%d}-{found[1]}-{round(amount * 100)}",
        title="Kart Borcu Tahsilatı",
    )


class CollectionNotice:
    id = ID
    version = 1
    bank = "İş Bankası"
    name = "İş Bankası gecikmiş kart borcu tahsilatı bildirimi"
    document_type = DocumentKind.NOTICE
    formats = frozenset({Format.EMAIL})

    def detect(self, probe: Probe) -> Detection | None:
        folded = fold(probe.text)
        ours = probe.sender == SENDER or probe.sender.endswith("." + SENDER)
        if ours and "NO ILE BITEN KREDI KARTINIZA" in folded and "TAKAS YOLUYLA TAHSIL" in folded:
            return Detection(1.0, "İş Bankası'ndan gecikmiş kart borcunun hesaptan tahsil edildiği bildirim")
        return None

    def parse(self, doc: SourceDocument) -> ParseResult:
        return read(doc)


PARSER = CollectionNotice()
