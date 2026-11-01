"""QNB's movement notices: the e-mails it sends when money comes into an account or leaves it ("QNB - Fast Para
transferi bildiriminiz", "QNB - Para transferi bildiriminiz", "QNB FINANSBANK - ATM/Banka Kartı Para Çıkışı
Bildiriminiz"; from email.qnbfinansbank.com until 2024, from email.qnb.com.tr since).

After the greeting ("Sayın ÖRNEK KULLANICI") one sentence tells of the movement and the next one of the balance:
- a FAST payment sent: "KADIKÖY şubesindeki hesabınızdan ÖRNEK KİŞİ isimli alıcıya 1,234.56 TL'lik FAST işleminiz
  gerçekleştirilmiştir.";
- one received: "… şubesindeki hesabınıza ÖRNEK KİŞİ tarafından FAST aracılığı ile 1,234.56 TL gönderilmiştir.";
- a transfer received or sent, or money out by card or at an ATM, naming the account's number: "… şubesindeki 12345678
  no'lu hesabınıza ÖRNEK KİŞİ tarafından 1.234,56 TL gönderilmiştir.", "… no'lu hesabınızdan ÖRNEK KİŞİ adına
  1.234,56 TL gönderilmiştir.", "… no'lu hesabınızdan 1.234,56 TL para çıkışı olmuştur.";
- then "Hesabınızın bakiyesi saat 14:05 itibarıyla -1,234.56 TL tutarındadır.": an overdraft account's balance is
  below zero.

Traps:
- The FAST notices print amounts the US way ("1,234.56", "1234.56"), the others the Turkish way ("1.234,56", "99,99"):
  the separator before the last two digits is the decimal one.
- Words come without their Turkish letters at times ("subesindeki", "hesabinizdan"): the patterns read folded text.
  The newest notices write the branch "Kadıköy Şubesi'ndeki" and mask the greeting's name ("Sayın Örnek K***").
- No notice prints the day. The message's date does, in Turkey's time; the balance's time tells a movement just
  before midnight from the message mailed just after it.
- A FAST notice names no account. Its row goes to the one QNB bank account of its currency that the other documents
  name (analysis.resolve_masked); a notice that names the number gives way to what the e-dekont or the list says of
  the account (an overdraft account or not).
- QNB attaches an e-dekont to some FAST notices: the movement then counts once (analysis._drop_told_twice), and the
  receipt's row takes the balance the notice adds.
"""

import re
from datetime import UTC, date, datetime, timedelta, timezone
from decimal import Decimal

from ....domain.codes import DocumentKind, TransactionKind
from ....domain.labels import format_amount
from ....domain.models import TRY, Account, ParseResult, SourceRef, Transaction
from ....domain.text import fold
from ...accounts import bank_account
from ...common import BUSINESS_REASON, Skipped, currency_code, is_business
from ...contract import Detection, Format, Probe, SourceDocument
from ...text import unfold_span

ID = "qnb.notice.transfer"
SENDERS = ("qnb.com.tr", "qnbfinansbank.com")
_AMOUNT = r"-?\d[\d.,]*[.,]\d{2}"
# The movement's sentence, folded: the account's number when it is named, which way the money went, the other side
# when it is named, the amount and the words that end the sentence.
_MOVEMENT = re.compile(
    r"\bSUBESI.?NDEKI (?:(?P<number>\d{5,12}) NO.LU )?HESABINIZ(?P<way>A|DAN) "
    r"(?:(?P<party>.{1,120}?) (?:ISIMLI ALICIYA|TARAFINDAN(?P<fast_in> FAST ARACILIGI ILE)?|ADINA) )?"
    rf"(?P<amount>{_AMOUNT}) (?P<currency>TL|TRY|USD|EUR|GBP)"
    r"(?P<end>.LIK FAST ISLEMINIZ GERCEKLESTIRILMISTIR| GONDERILMISTIR| PARA CIKISI OLMUSTUR)"
)
_BRANCH = re.compile(r"\bSUBESI.?NDEKI ")  # "KADIKÖY şubesindeki", or "Kadıköy Şubesi'ndeki" since 2026
_BALANCE = re.compile(rf"\bHESABINIZIN BAKIYESI SAAT (\d{{2}}):(\d{{2}}) ITIBARIYLA ({_AMOUNT}) (TL|TRY|USD|EUR|GBP)\b")
_TURKEY = timezone(timedelta(hours=3))  # Turkey keeps UTC+3 all year (since 2016)
_SKEW = timedelta(minutes=10)  # how far the bank's clock and the mail server's may differ


def _amount(printed: str) -> Decimal:
    """An amount either way QNB prints it: the separator before the last two digits is the decimal one, the other one
    groups thousands ("1,234.56", "1234.56", "1.234,56", "99,99")."""
    digits = printed.lstrip("-")
    whole, point = digits[:-3], digits[-3]
    if not re.fullmatch(r"\d+(?:[.,]\d{3})*", whole) or point in whole:
        raise ValueError(f"QNB bildiriminde tutar okunamadı: {printed!r}")
    value = Decimal(f"{whole.replace('.', '').replace(',', '')}.{digits[-2:]}")
    return -value if printed.startswith("-") else value


def _day(sent: datetime | None, clock: tuple[int, int] | None) -> date:
    """The movement's day: the message's date in Turkey, the day before when the balance's time is later than the
    message was sent (a movement at 23:58, mailed at 00:01)."""
    if sent is None:
        raise ValueError("QNB bildiriminin gönderildiği tarih yok")
    local = (sent if sent.tzinfo else sent.replace(tzinfo=UTC)).astimezone(_TURKEY)
    if clock is None:
        return local.date()
    at = local.replace(hour=clock[0], minute=clock[1], second=0, microsecond=0)
    return (at - timedelta(days=1)).date() if at > local + _SKEW else at.date()


def _account(number: str | None, currency: str) -> Account:
    """The account the notice tells of. A named number is the account the e-dekont and the list name ("qnb-12345678");
    a FAST notice names none, and its account waits for the one QNB bank account of the currency."""
    account = bank_account("QNB", number or "****", currency)
    if number is None:
        account.label = account.label.removesuffix(" ****")
    return account


def _printed(text: str, span: tuple[int, int]) -> str:
    """What fold(text)[span] is in the text as printed."""
    found = unfold_span(text, *span)
    return text[found[0] : found[1]].strip() if found else ""


def read(doc: SourceDocument) -> ParseResult:
    mail = doc.mail
    holder = "" if "*" in mail.addressee else mail.addressee
    if is_business(holder):
        raise Skipped(BUSINESS_REASON, business=True)
    folded = fold(mail.text)
    movement = _MOVEMENT.search(folded)
    if movement is None:
        raise ValueError("QNB bildiriminde hareket cümlesi okunamadı")
    balance = _BALANCE.search(folded)
    currency = currency_code(movement["currency"])
    value = _amount(movement["amount"])
    day = _day(mail.sent, (int(balance[1]), int(balance[2])) if balance else None)
    account = _account(movement["number"], currency)
    party = _printed(mail.text, movement.span("party")) if movement["party"] else ""
    fast = movement["fast_in"] is not None or "FAST" in movement["end"]
    if movement["way"] == "A":
        title, sign, arrow = ("Gelen FAST" if fast else "Gelen Transfer"), -1, "←"
    elif movement["end"].endswith("PARA CIKISI OLMUSTUR"):
        title, sign, arrow = "Para Çıkışı", 1, ""
    else:
        title, sign, arrow = ("Giden FAST" if fast else "Giden Transfer"), 1, "→"
    channel = " (ATM/banka kartı)" if re.search(r"\bATM\b|\bBANKA KARTI\b", fold(mail.subject)) else ""
    after = _amount(balance[3]) if balance and currency_code(balance[4]) == currency else None
    row = Transaction(
        date=day,
        description=f"{title} {arrow} {party}" if party else f"{title}{channel}",
        amount=sign * value,
        # Whether it went to the user's own account, the landlord or a friend is decided once every account is known
        # (analysis.py), like a transfer row of an account list.
        kind=TransactionKind.TRANSFER_CANDIDATE,
        account=account.id,
        counterparty=party,
        source=doc.name,
        ref=SourceRef(span=unfold_span(mail.text, *movement.span("amount"))),
        original=f"{format_amount(value)} {currency}" if currency != TRY else "",
        balance=after,
    )
    minute = f"{balance[1]}{balance[2]}" if balance else "0000"
    kurus = round(after * 100) if after is not None else "x"
    return ParseResult(
        parser=ID,
        accounts=[account],
        transactions=[row],
        # No reference number is printed: a notice is known by its day and minute, its amount and the balance after it.
        receipt_key=f"qnb-bildirim-{day:%Y%m%d}{minute}-{round(value * 100)}-{kurus}",
        holder=holder,
        title=title,
    )


class TransferNotice:
    id = ID
    version = 1
    bank = "QNB"
    name = "QNB FAST, havale/EFT ve para çıkışı bildirimi"
    document_type = DocumentKind.NOTICE
    formats = frozenset({Format.EMAIL})

    def detect(self, probe: Probe) -> Detection | None:
        ours = any(probe.sender == s or probe.sender.endswith("." + s) for s in SENDERS)
        folded = fold(probe.text)
        if ours and "HESABINIZIN BAKIYESI SAAT" in folded and _BRANCH.search(folded):
            return Detection(1.0, "QNB'den hesap hareketi bildirimi: şube, tutar ve işlem sonrası bakiye")
        return None

    def parse(self, doc: SourceDocument) -> ParseResult:
        return read(doc)


PARSER = TransferNotice()
