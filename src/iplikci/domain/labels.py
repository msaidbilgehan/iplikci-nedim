"""Turkish labels of the domain codes and the Turkish money format: the one place they live (ADR-0006).

Every code has a label here; tests/test_domain.py fails when a new code arrives without one.
"""

from collections.abc import Mapping
from decimal import Decimal
from enum import StrEnum

from .codes import (
    AccountType,
    Actor,
    Certainty,
    DocumentKind,
    DocumentStatus,
    EvidenceStatus,
    MonthStatus,
    Necessity,
    SourceKind,
    Tone,
    TransactionKind,
)
from .money import Money, Unit, round_half_up

KIND: dict[TransactionKind, str] = {
    TransactionKind.PURCHASE: "Harcama",
    TransactionKind.REFUND: "İade / indirim",
    TransactionKind.INTEREST_FEE: "Faiz & banka ücreti",
    TransactionKind.P2P_TRANSFER: "Kişilere gönderilen para",
    TransactionKind.LOAN_PRINCIPAL: "Kredi & borç anapara ödemesi",
    TransactionKind.CASH_ADVANCE: "Nakit avans / çekim",
    TransactionKind.INVESTMENT: "Birikim & yatırım (döviz, altın, BES)",
    TransactionKind.INCOME: "Gelir",
    TransactionKind.CARD_PAYMENT_NO_STATEMENT: "Ekstresi olmayan kart ödemesi",
    TransactionKind.CARD_PAYMENT: "Kredi kartı borç ödemesi",
    TransactionKind.OWN_TRANSFER: "Kendi hesaplarım arası transfer",
    TransactionKind.TRANSFER_CANDIDATE: "Çözülmemiş transfer",
}

NECESSITY: dict[Necessity, str] = {
    Necessity.REQUIRED: "Gerekli",
    Necessity.OPTIONAL: "İsteğe bağlı",
    Necessity.UNNECESSARY: "Gereksiz",
    Necessity.UNKNOWN: "Belirsiz",
}

ACCOUNT_TYPE: dict[AccountType, str] = {
    AccountType.CREDIT_CARD: "Kredi kartı",
    AccountType.DEBIT_CARD: "Banka kartı",
    AccountType.CURRENT: "Vadesiz hesap",
    AccountType.DEPOSIT: "Vadeli hesap",
    AccountType.OVERDRAFT: "Ek hesap (KMH)",
    AccountType.FX: "Döviz hesabı",
    AccountType.GOLD: "Altın hesabı",
    AccountType.BROKERAGE: "Yatırım hesabı",
    AccountType.LOAN: "Kredi",
}

EVIDENCE_STATUS: dict[EvidenceStatus, str] = {
    EvidenceStatus.MATCHED: "Ekstreyle eşleşti",
    EvidenceStatus.PROVISIONAL: "Geçici — ekstre bekleniyor",
    EvidenceStatus.UNMATCHED: "Ekstrede görünmüyor",
    EvidenceStatus.NO_STATEMENT: "Ekstresi olmayan dönem",
}

CERTAINTY: dict[Certainty, str] = {
    Certainty.CONFIRMED: "Kesin",
    Certainty.PROVISIONAL: "Geçici",
    Certainty.EXCLUDED: "Toplama girmez",
    Certainty.INFO: "Bilgi",
}

DOCUMENT_STATUS: dict[DocumentStatus, str] = {
    DocumentStatus.PROCESSED: "İşlendi",
    DocumentStatus.UNPROCESSED: "İşlenmedi",
    DocumentStatus.UNREADABLE: "Okunamadı",
    DocumentStatus.REMOVED: "Kaldırıldı",
}

DOCUMENT_KIND: dict[DocumentKind, str] = {
    DocumentKind.CARD_STATEMENT: "Kart ekstresi",
    DocumentKind.ACCOUNT_STATEMENT: "Hesap dökümü",
    DocumentKind.RECEIPT: "Dekont",
}

SOURCE_KIND: dict[SourceKind, str] = {
    SourceKind.EMAIL: "E-posta",
    SourceKind.UPLOAD: "Yükleme",
    SourceKind.INBOX: "Gelen klasörü",
    SourceKind.IMPORT: "İçe aktarma",
}

# A month as a whole, and one account within a month: the same codes read differently.
MONTH_STATUS: dict[MonthStatus, str] = {
    MonthStatus.CLOSED: "Kapandı",
    MonthStatus.WAITING: "Ekstre bekleniyor",
    MonthStatus.MISSING: "Belge eksik",
    MonthStatus.CHECK: "Kontrol gerekli",
    MonthStatus.RUNNING: "Ay sürüyor",
}
ACCOUNT_MONTH_STATUS: dict[MonthStatus, str] = {
    MonthStatus.CLOSED: "Kapandı",
    MonthStatus.WAITING: "Bekleniyor",
    MonthStatus.MISSING: "Belge eksik",
    MonthStatus.CHECK: "Kontrol edin",
    MonthStatus.RUNNING: "Sürüyor",
}

TONE: dict[Tone, str] = {Tone.ATTENTION: "Dikkat", Tone.INFO: "Bilgi", Tone.GOOD: "İyi"}

ACTOR: dict[Actor, str] = {
    Actor.USER: "Kullanıcı",
    Actor.MCP: "MCP",
    Actor.SYSTEM: "Sistem",
    Actor.MIGRATION: "Taşıma",
}

UNIT: dict[Unit, str] = {Unit.GRAM: "gram", Unit.SHARE: "adet"}


def _table[K: StrEnum](labels: Mapping[K, str]) -> dict[StrEnum, str]:
    return {code: text for code, text in labels.items()}


# Every table above, by the code type it labels.
TABLES: dict[type[StrEnum], dict[StrEnum, str]] = {
    TransactionKind: _table(KIND),
    Necessity: _table(NECESSITY),
    AccountType: _table(ACCOUNT_TYPE),
    EvidenceStatus: _table(EVIDENCE_STATUS),
    Certainty: _table(CERTAINTY),
    DocumentStatus: _table(DOCUMENT_STATUS),
    DocumentKind: _table(DOCUMENT_KIND),
    SourceKind: _table(SOURCE_KIND),
    MonthStatus: _table(MONTH_STATUS),
    Tone: _table(TONE),
    Actor: _table(ACTOR),
    Unit: _table(UNIT),
}

# The interface writes the Turkish lira as "TL" (ADR-0006).
CURRENCY: dict[str, str] = {"TRY": "TL"}


def label(code: StrEnum) -> str:
    """The Turkish label of any domain code."""
    return TABLES[type(code)][code]


def currency_label(currency: str) -> str:
    return CURRENCY.get(currency, currency)


def format_amount(value: Decimal) -> str:
    """Decimal("1234.5") → "1.234,50": two decimals rounded half up, dots between thousands, a comma
    before the decimals."""
    return f"{round_half_up(value):,.2f}".replace(",", " ").replace(".", ",").replace(" ", ".")


def format_money(money: Money) -> str:
    """Money("1234.5", "TRY") → "1.234,50 TL"."""
    return f"{format_amount(money.amount)} {currency_label(money.currency)}"
