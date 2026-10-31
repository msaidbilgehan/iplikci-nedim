"""Rules shared by every card parser."""

import hashlib
import re
from collections.abc import Iterable

from ..models import Transaction
from ..textutil import fold, parse_us_amount, squash


class Skipped(Exception):
    """The document is not a statement or receipt this program understands.

    business=True marks documents of the user's company accounts, which are out
    of scope: only personal money flows are analysed.
    """

    def __init__(self, reason: str, business: bool = False):
        super().__init__(reason)
        self.business = business


class Unreadable(Exception):
    """A bank document that cannot be read as it is (a password-protected PDF). Unlike Skipped it
    is kept for a manual look: the organizer never sets it aside as unused."""


# Marks of company documents: business card and account products, payroll. The user's company names come from
# the settings (identity.business_names), never from the code.
_BUSINESS_MARKS = (
    "SIRKETKREDIKARTI", "GIRISIMCIKREDIKART", "KREDILITICARIMEVDUAT", "UCRETBORDROSU", "AYLIKOZETRAPORU",
)
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
    global _business_names
    _business_names = tuple(sorted({s for s in map(_business_name, names) if len(s) >= 3}))


def business_names_signature() -> str:
    """Changes whenever the company names do: a parse cache made with other names is stale."""
    if not _business_names:
        return ""
    return hashlib.sha256("\n".join(_business_names).encode()).hexdigest()[:16]


BUSINESS_REASON = "şirket belgesi — kapsam dışı"

# Bank documents without money movements, named so a summary says what they are (matched on the
# squashed text of the first page, only once no reader took the document).
_NOT_STATEMENTS = (
    (("HAYATSIGORTASI", "SIGORTABASVURU", "KATILIMSERTIFIKA", "SIGORTALARBILGILENDIRME", "POLICE"),
     "sigorta poliçesi/bilgilendirmesi"),
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
    "FAIZ", "KKDF", "BSMV", "NAKIT AVANS UCRETI", "ODEME UCRETI", "KART UCRETI",
    "UYELIK UCRETI", "YILLIK UCRET", "YILLIK UYELIK", "DIJITAL UYELIK", "DIJITALUYELIK",
    "KART AIDATI", "HESAP ISLETIM", "EFT UCRETI", "HAVALE UCRETI", "LIMIT ASIM", "GECIKME",
    "ATM KULLANIM", "TAHSILATI UCRETI", "TAHSILAT UCRETI", "SURCHARGE",
)
_PAYMENT_PATTERNS = (
    "HESAPTAN AKTARIM", "OTOMATIK TAHSILAT", "ODEME TESEKKUR", "ODEMENIZ ICIN TESEKKUR",
    "ODEMELERINIZ ICIN", "TAHSILAT", "KREDI KARTI ODEMESI",
)
_CASH_PATTERNS = ("NAKIT AVANS", "KARTTAN AKTARIM", "NAKIT CEKIM", "ATM ")
# A deferred statement ("ekstre erteleme") is booked as a payment plus the same amount
# charged again: old debt moving to a later statement, not new spending.
_DEFERRAL_PATTERNS = ("ERTELENEN EKSTRE", "EKSTRE ERTELEME")


def _has(patterns: tuple[str, ...], f: str, sq: str) -> bool:
    # Some statements print a line without spaces ("HESAPTANAKTARIM"), so multi-word
    # patterns are also tried with the spaces removed.
    return any(p in f or (" " in p.strip() and p.replace(" ", "") in sq) for p in patterns)


def classify_kind(description: str, amount: float) -> str:
    """Decide the transaction kind from a statement line."""
    f = fold(description)
    sq = f.replace(" ", "")
    if _has(_DEFERRAL_PATTERNS, f, sq):
        return "transfer"
    if amount < 0 and _has(_PAYMENT_PATTERNS, f, sq):
        return "kart_odemesi"
    if _has(_FEE_PATTERNS, f, sq):
        return "faiz_ucret"
    if _has(_CASH_PATTERNS, f, sq):
        return "nakit_avans"
    if amount < 0:
        return "iade"
    return "harcama"


def pair_deferrals(txns: list[Transaction]) -> None:
    """The payment line a deferral books against the old balance is not a real payment either."""
    for deferred in [t for t in txns if t.kind == "transfer" and t.amount > 0]:
        payment = next((t for t in txns if t.kind == "kart_odemesi" and t.date == deferred.date
                        and abs(t.amount + deferred.amount) < 0.01), None)
        if payment:
            payment.kind = "transfer"


_FZ = re.compile(r"FZ:\s*([\d.,]+)\s+VR/FN:\s*([\d.,]+)")


def split_interest(txn: Transaction) -> list[Transaction]:
    """Split an installment cash-advance line into principal and interest.

    İş Bankası prints e.g. "TAKSİTLİ NAKİT AVANS ... FZ:120.00 VR/FN:36.00 1.500,00":
    120.00 interest and 36.00 tax are a cost, the rest repays the advance.
    """
    m = _FZ.search(fold(txn.description))
    if not m or "NAKIT AVANS" not in fold(txn.description) or "UCRET" in fold(txn.description):
        return [txn]
    interest = (parse_us_amount(m[1]) or 0) + (parse_us_amount(m[2]) or 0)
    interest = round(min(interest, txn.amount), 2)
    principal = round(txn.amount - interest, 2)
    out = []
    if principal:
        out.append(Transaction(**{**txn.__dict__, "amount": principal, "kind": "kredi_anapara"}))
    if interest:
        out.append(Transaction(**{
            **txn.__dict__, "amount": interest, "kind": "faiz_ucret",
            "description": txn.description + " (faiz ve vergi payı)",
        }))
    return out


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
