"""Garanti BBVA's transfer notices: the e-mails it sends when a transfer above a set amount leaves an account ("Para
Transferi Bilgilendirmesi").

Two layouts reach the mailbox.
- The older one (from info.garantibbva.com.tr) greets the customer by name and names the transfer in its first
  sentence: "Havale Para transferi işleminiz gerçekleşmiştir.", "Başka Banka Para transferi …", "EFT Emri Para transferi
  emriniz işleme alınmıştır.".
- The newer one (from garantibbva.com.tr) opens with "Giden PT Bilgilendirmesi - 'Havale' işlem tipi için email …
  Başka Bankaya Transfer".
Both then print:
- the sender's block ("Gönderen Bilgileri:" name, branch "MERKEZ - 106", account number);
- the receiver's block ("Alıcı Bilgileri:" name and IBAN, the newer layout adding the bank's name; or a Garanti branch
  and account after a "/");
- "Tutar: 1.234,56 TL", "İşlem Tarihi: dd.mm.yyyy hh:mm" and "Açıklama:" with the sender's note.
Since 2026 the names are masked but for the first letters of their words and the account number but for its last
three digits ("****567"); before, both were printed whole.

No reference number is printed: a notice is known by its account, its minute and its amount. Garanti mails a receipt
(dekont) for some of the same transfers; the analysis counts such a movement once (analysis._drop_told_twice).
"""

import re

from ....domain.codes import DocumentKind, TransactionKind
from ....domain.models import Account, ParseResult, SourceRef, Transaction
from ....domain.text import fold
from ...accounts import bank_account, bank_from_iban
from ...common import BUSINESS_REASON, Skipped, currency_code, is_business
from ...contract import Detection, Format, Probe, SourceDocument
from ...text import parse_dmy, parse_tr_amount, squash, unfold_span

ID = "garanti.notice.transfer"
SENDER = "garantibbva.com.tr"
_SENDER_BLOCK = re.compile(r"\bGONDEREN BILGILERI ?: ?(.*?) ALICI BILGILERI ?:")
_RECEIVER_BLOCK = re.compile(r"\bALICI BILGILERI ?: ?(.*?) TUTAR ?:")
_AMOUNT = re.compile(r"\bTUTAR ?: ?([\d.]+,\d{2}) ?(TL|USD|EUR|GBP)\b")
_WHEN = re.compile(r"\bISLEM TARIHI ?: ?(\d{2}\.\d{2}\.\d{4}) (\d{2}):(\d{2})")
# The note runs to the closing words of either layout.
_NOTE = re.compile(r"\bACIKLAMA ?: ?(.*?)(?= IYI GUNLER DILERIZ| PARA TRANSFERLERI BILGILENDIRMELERI|$)")
# The sender's block ends with the branch and the account: "MERKEZ - 106 1234567" or "… - 106 ****567".
_OWN_ACCOUNT = re.compile(r" - \d{3,5} (\*+\d{3,4}|\d{5,9})$")
_GREETING = re.compile(r"\bSAYIN (.+?),")  # the older layout greets the account's holder by name
_IBAN = re.compile(r"TR\d{2}(?:[\d*]| (?=[\d*]))+")
# A receiver at Garanti itself: "AD SOYAD / ŞUBE - 123 1234567".
_GARANTI_RECEIVER = re.compile(r"(.*?) / .+? - \d{3,5} \d{5,9}$")


class _Text:
    """The body's text, its folded form for the patterns and the way back to the letters as printed."""

    def __init__(self, text: str) -> None:
        self.text = text
        self.folded = fold(text)

    def printed(self, start: int, end: int) -> str:
        """What folded[start:end] is in the text as printed, without the spaces around it."""
        while start < end and self.folded[start] == " ":
            start += 1
        while end > start and self.folded[end - 1] == " ":
            end -= 1
        span = unfold_span(self.text, start, end) if start < end else None
        return self.text[span[0] : span[1]] if span else ""


def _title(head: str) -> str:
    """The transfer's kind, from the words above the blocks: another bank's account first, the newer heading says
    "Havale" for every kind."""
    if "BASKA BANKA" in head:
        return "Giden Transfer"
    if "EFT" in head:
        return "Giden EFT"
    return "Giden Havale"


def _account(number: str, currency: str) -> Account:
    """The account the lists name ("garanti-1234567"); a masked number keeps only the digits shown."""
    account = bank_account("Garanti BBVA", number, currency)
    if "*" in number:
        account.label = account.label.replace(number, "…" + number.rsplit("*", 1)[1])
    return account


def _receiver(text: _Text, start: int, end: int) -> tuple[str, str]:
    """The receiver's name and bank from its block: a name and an IBAN, the bank's name after it in the newer layout,
    or a Garanti branch and account."""
    block = text.folded[start:end]
    iban = _IBAN.search(block)
    if iban is not None:
        name = text.printed(start, start + iban.start()).rstrip(" -")
        after = text.printed(start + iban.end(), end)
        return name, after or bank_from_iban(iban[0].replace(" ", ""))
    garanti = _GARANTI_RECEIVER.match(block)
    if garanti is not None:
        return text.printed(start, start + garanti.end(1)), "Garanti BBVA"
    return text.printed(start, end), ""


def read(doc: SourceDocument) -> ParseResult:
    text = _Text(doc.mail.text)
    f = text.folded
    sender, receiver = _SENDER_BLOCK.search(f), _RECEIVER_BLOCK.search(f)
    amount, when = _AMOUNT.search(f), _WHEN.search(f)
    day = parse_dmy(when[1]) if when else None
    value = parse_tr_amount(amount[1]) if amount else None
    owner = _OWN_ACCOUNT.search(sender[1]) if sender else None
    if not (sender and receiver and amount and when and day and value and owner):
        raise ValueError("Garanti para transferi bildiriminde hesap, alıcı, tutar ya da işlem tarihi bulunamadı")
    greeting = _GREETING.search(f[: sender.start()])
    holder = text.printed(greeting.start(1), greeting.end(1)) if greeting else ""  # the newer layout masks it
    # The greeting names who the e-mail is for; the sender's block names whose account it is, and a company's account
    # may write to the person who uses it.
    if is_business(holder) or is_business(sender[1][: owner.start()]):
        raise Skipped(BUSINESS_REASON, business=True)
    currency = currency_code(amount[2])
    account = _account(owner[1], currency)
    party, bank = _receiver(text, receiver.start(1), receiver.end(1))
    note = _NOTE.search(f)
    remark = text.printed(note.start(1), note.end(1)) if note else ""
    title = _title(f[: sender.start()])
    described = f"{title} → {party}" + (f" ({bank})" if bank else "") + (f" — {remark}" if remark else "")
    span = unfold_span(text.text, amount.start(1), amount.end(2))
    # Whether it went to the user's own account, the landlord or a friend is decided once every account is known
    # (analysis.py), like a transfer row of an account list.
    row = Transaction(
        date=day,
        description=described,
        amount=value,
        kind=TransactionKind.TRANSFER_CANDIDATE,
        account=account.id,
        counterparty=party,
        source=doc.name,
        ref=SourceRef(span=span),
    )
    shown = re.sub(r"\D", "", owner[1])[-3:]
    return ParseResult(
        parser=ID,
        accounts=[account],
        transactions=[row],
        receipt_key=f"garanti-pt-{day:%Y%m%d}{when[2]}{when[3]}-{shown}-{round(value * 100)}",
        holder=holder,
        title=title,
    )


class TransferNotice:
    id = ID
    version = 1
    bank = "Garanti BBVA"
    name = "Garanti BBVA para transferi bildirimi"
    document_type = DocumentKind.NOTICE
    formats = frozenset({Format.EMAIL})

    def detect(self, probe: Probe) -> Detection | None:
        s = squash(probe.text)
        ours = probe.sender == SENDER or probe.sender.endswith("." + SENDER)
        if ours and "PARATRANSFER" in s and "GONDERENBILGILERI" in s and "ALICIBILGILERI" in s and "TUTAR:" in s:
            return Detection(1.0, "garantibbva.com.tr'den para transferi bildirimi: gönderen, alıcı ve tutar")
        return None

    def parse(self, doc: SourceDocument) -> ParseResult:
        return read(doc)


PARSER = TransferNotice()
