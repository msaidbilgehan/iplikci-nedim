"""Rules shared by every card parser."""

import hashlib
import re
from collections.abc import Iterable
from decimal import Decimal

from ..domain.codes import TransactionKind
from ..domain.models import TRY, Transaction
from ..domain.money import CENT, round_half_up
from ..domain.text import fold
from .text import parse_us_amount, squash


class Skipped(Exception):
    """The document is not a statement or receipt this program understands.

    business=True marks documents of the user's company accounts, which are out
    of scope: only personal money flows are analysed. parser names the reader that
    recognised the document and then gave up on it.
    """

    def __init__(self, reason: str, business: bool = False, parser: str = ""):
        super().__init__(reason)
        self.business = business
        self.parser = parser


class Unreadable(Exception):
    """A bank document that cannot be read as it is (a password-protected PDF, a reader that failed on it).
    Unlike Skipped it is kept for a manual look, never set aside as unused. parser names the reader that
    recognised the document, when one did."""

    def __init__(self, reason: str, parser: str = ""):
        super().__init__(reason)
        self.parser = parser


def caused_by(exc: BaseException, kind: type[BaseException]) -> bool:
    """Whether exc is a kind, or was raised from one or wraps one: pdfplumber hands on what pdfminer raises inside an
    exception of its own (a password error, a failed allocation)."""
    seen: set[int] = set()
    todo: list[object] = [exc]
    while todo:
        e = todo.pop()
        if not isinstance(e, BaseException) or id(e) in seen:
            continue
        if isinstance(e, kind):
            return True
        seen.add(id(e))
        todo += [e.__cause__, e.__context__, *e.args]
    return False


# Marks of company documents: business card and account products, payroll. The user's company names come from
# the settings (identity.business_names), never from the code.
_BUSINESS_MARKS = (
    "SIRKETKREDIKARTI",
    "GIRISIMCIKREDIKART",
    "TICARIKREDIKART",  # banks write to a company's contact about its commercial cards …
    "TICARIMUSTERI",  # … to their commercial customers …
    "KOBI",  # … and to small businesses (KOBİ)
    "KREDILITICARIMEVDUAT",
    "UCRETBORDROSU",
    "AYLIKOZETRAPORU",
    "IMZASIRKULER",  # a company's signature circular …
    "GENELKURUL",  # … and its general assembly
)
_given_names: tuple[str, ...] = ()
_business_names: tuple[str, ...] = ()
# Legal forms after a company's name, written in any spelling ("A.Ş.", "ANONİM ŞİRKETİ", "SAN. VE TİC. LTD. ŞTİ."):
# a name is looked for without them, so a document that spells the form another way still matches it.
_LEGAL_FORMS = frozenset({"AS", "ANONIM", "SIRKETI", "LTD", "LIMITED", "STI", "SAN", "SANAYI", "TIC", "TICARET", "VE"})


def _business_name(name: str) -> str:
    words = [re.sub(r"[^A-Z0-9]", "", w) for w in fold(name).split()]
    while words and words[-1] in _LEGAL_FORMS:
        words.pop()
    return "".join(words)


def set_business_names(names: Iterable[str]) -> None:
    """The user's company names, squashed like the headers they are looked for in. The readers have no
    settings of their own, so the workspace hands the names over when it loads them. A name shorter than
    three letters would mark nearly every document as a company's: it is left out."""
    global _given_names, _business_names
    _given_names = tuple(names)
    _business_names = tuple(sorted({s for s in map(_business_name, _given_names) if len(s) >= 3}))


def business_names() -> tuple[str, ...]:
    """The names as set_business_names got them: the reading process gets them with every document (worker.py)."""
    return _given_names


def business_names_signature() -> str:
    """Changes whenever the company check does, the company names or the marks in this module: a reading made with
    another check is stale, so a company document kept before is found."""
    return hashlib.sha256("\n".join(_BUSINESS_MARKS + ("",) + _business_names).encode()).hexdigest()[:16]


# An SGK workplace number: 26 digits, given to whoever employs someone. Premiums paid under one are an employer's, part
# of a payroll; the premiums a person pays for themselves go under their identity number. (A household that employs a
# domestic worker has one too: such a message is set aside as well, and it moves no money of its own.)
_WORKPLACE_NUMBER = re.compile(r"(?<![\d.,])\d{26}(?![\d.,])")
_SGK = re.compile(r"\b(?:SGK|SSK)\b")


def pays_as_employer(text: str) -> bool:
    """Whether a message's body is about premiums paid as an employer: SGK named beside a workplace number. Only pass
    a message's body no reader took here: a reader's row may name anything."""
    return bool(_WORKPLACE_NUMBER.search(text)) and bool(_SGK.search(fold(text)))


BUSINESS_REASON = "şirket belgesi — kapsam dışı"
# An e-mail is kept whole; a message no reader of bodies took (Phase 4) is kept with this reason.
MESSAGE_REASON = "e-posta iletisi; bu tür iletinin gövdesi henüz okunmuyor"

# Bank documents without money movements, named so a summary says what they are (matched on the
# squashed text of the first page, only once no reader took the document).
_NOT_STATEMENTS = (
    (
        ("HAYATSIGORTASI", "SIGORTABASVURU", "KATILIMSERTIFIKA", "SIGORTALARBILGILENDIRME", "POLICE"),
        "sigorta poliçesi/bilgilendirmesi",
    ),
    (("KREDISIBILGIFORMU", "KREDISISOZLESMESI", "KREDIKULLANIMBEYANI", "KREDISITERCIHFORMU"), "kredi sözleşmesi/formu"),
    (("TALIMATFORMU",), "talimat formu"),
    (("SOZLESMESI",), "sözleşme"),
)
NOT_A_STATEMENT = "ekstre veya hesap hareketi değil"


def not_a_statement(text: str) -> str:
    """Why a document no reader took is not used: what it is when recognisable. The mark found first
    wins: a document names itself in its title ("ÖDEME HİZMETLERİ ÇERÇEVE SÖZLEŞMESİ" mentions a
    policy only later)."""
    s = squash(text[:3000])
    found = [(s.find(m), reason) for marks, reason in _NOT_STATEMENTS for m in marks if m in s]
    return min(found)[1] if found else NOT_A_STATEMENT


def is_business(header: str) -> bool:
    """Only pass a file name, a document title or an account holder here, never
    transaction lines: personal statements mention the company too
    ("GOOGLE*GSUITE <company domain>")."""
    s = squash(header)
    return any(mark in s for mark in _BUSINESS_MARKS + _business_names)


_FEE_PATTERNS = (
    "FAIZ",
    "KKDF",
    "BSMV",
    "NAKIT AVANS UCRETI",
    "ODEME UCRETI",
    "KART UCRETI",
    "UYELIK UCRETI",
    "YILLIK UCRET",
    "YILLIK UYELIK",
    "DIJITAL UYELIK",
    "DIJITALUYELIK",
    "KART AIDATI",
    "HESAP ISLETIM",
    "EFT UCRETI",
    "HAVALE UCRETI",
    "LIMIT ASIM",
    "GECIKME",
    "ATM KULLANIM",
    "TAHSILATI UCRETI",
    "TAHSILAT UCRETI",
    "SURCHARGE",
)
_PAYMENT_PATTERNS = (
    "HESAPTAN AKTARIM",
    "OTOMATIK TAHSILAT",
    "ODEME TESEKKUR",
    "ODEMENIZ ICIN TESEKKUR",
    "ODEMELERINIZ ICIN",
    "TAHSILAT",
    "KREDI KARTI ODEMESI",
)
_CASH_PATTERNS = ("NAKIT AVANS", "KARTTAN AKTARIM", "NAKIT CEKIM", "ATM ")
# A deferred statement ("ekstre erteleme") is booked as a payment plus the same amount
# charged again: old debt moving to a later statement, not new spending.
_DEFERRAL_PATTERNS = ("ERTELENEN EKSTRE", "EKSTRE ERTELEME")


def _has(patterns: tuple[str, ...], f: str, sq: str) -> bool:
    # Some statements print a line without spaces ("HESAPTANAKTARIM"), so multi-word
    # patterns are also tried with the spaces removed.
    return any(p in f or (" " in p.strip() and p.replace(" ", "") in sq) for p in patterns)


def classify_kind(description: str, amount: Decimal) -> TransactionKind:
    """Decide the transaction kind from a statement line."""
    f = fold(description)
    sq = f.replace(" ", "")
    if _has(_DEFERRAL_PATTERNS, f, sq):
        return TransactionKind.OWN_TRANSFER
    if amount < 0 and _has(_PAYMENT_PATTERNS, f, sq):
        return TransactionKind.CARD_PAYMENT
    if _has(_FEE_PATTERNS, f, sq):
        return TransactionKind.INTEREST_FEE
    if _has(_CASH_PATTERNS, f, sq):
        return TransactionKind.CASH_ADVANCE
    if amount < 0:
        return TransactionKind.REFUND
    return TransactionKind.PURCHASE


def pair_deferrals(txns: list[Transaction]) -> None:
    """The payment line a deferral books against the old balance is not a real payment either."""
    for deferred in [t for t in txns if t.kind == TransactionKind.OWN_TRANSFER and t.amount > 0]:
        payment = next(
            (
                t
                for t in txns
                if t.kind == TransactionKind.CARD_PAYMENT
                and t.date == deferred.date
                and abs(t.amount + deferred.amount) < CENT
            ),
            None,
        )
        if payment:
            payment.kind = TransactionKind.OWN_TRANSFER


_FZ = re.compile(r"FZ:\s*([\d.,]+)\s+VR/FN:\s*([\d.,]+)")


def split_interest(txn: Transaction) -> list[Transaction]:
    """Split an installment cash-advance line into principal and interest.

    İş Bankası prints e.g. "TAKSİTLİ NAKİT AVANS ... FZ:120.00 VR/FN:36.00 1.500,00":
    120.00 interest and 36.00 tax are a cost, the rest repays the advance.
    """
    m = _FZ.search(fold(txn.description))
    if not m or "NAKIT AVANS" not in fold(txn.description) or "UCRET" in fold(txn.description):
        return [txn]
    interest = (parse_us_amount(m[1]) or Decimal(0)) + (parse_us_amount(m[2]) or Decimal(0))
    interest = round_half_up(min(interest, txn.amount))
    principal = round_half_up(txn.amount - interest)
    out = []
    if principal:
        out.append(Transaction(**{**txn.__dict__, "amount": principal, "kind": TransactionKind.LOAN_PRINCIPAL}))
    if interest:
        out.append(
            Transaction(
                **{
                    **txn.__dict__,
                    "amount": interest,
                    "kind": TransactionKind.INTEREST_FEE,
                    "description": txn.description + " (faiz ve vergi payı)",
                }
            )
        )
    return out


def currency_code(token: str) -> str:
    """The ISO code of a currency as a document prints it: "TL", "TRY" and "YTL" are the lira; gold stays "GR"."""
    token = token.strip().upper()
    return TRY if token in ("", "TL", "TRY", "YTL") else token


def agreed[T](values: Iterable[T | None]) -> T | None:
    """The value a statement prints for one of its terms (its due date, its minimum payment, the card's limit), however
    often it prints it: None when it prints none, a malformed one, or two that differ. Statements print their due
    date twice, and a reader never picks one of two different values."""
    found = set(values)
    return found.pop() if len(found) == 1 else None


_INSTALLMENT = re.compile(r"(\d{1,2})\s*/\s*(\d{1,2})\s*TAKS", re.IGNORECASE)
_INSTALLMENT_GARANTI = re.compile(r"x(\d{1,2})=.*?(\d{1,2})\.\s*Taksit", re.IGNORECASE)


def installment_label(text: str) -> str:
    """'1/3 taksidi (1.234,00)' -> '1/3'; '250,00x12=3.000,00 8.Taksit' -> '8/12'."""
    m = _INSTALLMENT.search(text)
    if m:
        return f"{int(m[1])}/{int(m[2])}"
    m = _INSTALLMENT_GARANTI.search(text)
    if m:
        return f"{int(m[2])}/{int(m[1])}"
    return ""
