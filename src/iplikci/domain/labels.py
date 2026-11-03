"""Turkish labels of the domain codes and the Turkish money format: the one place they live (ADR-0006).

Every code has a label here; tests/test_domain.py fails when a new code arrives without one.
"""

from collections.abc import Mapping
from decimal import Decimal
from enum import StrEnum

from .codes import (
    AccountGroup,
    AccountType,
    Actor,
    BackupReason,
    CategoryReason,
    Certainty,
    Channel,
    ChannelStage,
    DeliveryStatus,
    DetailLevel,
    DocumentKind,
    DocumentStatus,
    EventKind,
    EvidenceStatus,
    FlowKind,
    ForecastPart,
    HabitStatus,
    InvoiceKind,
    InvoiceStatus,
    MonthStatus,
    Necessity,
    NecessityReason,
    PaidStatus,
    PaymentKind,
    RateSource,
    RuleLayer,
    SeriesPeriod,
    SeriesStatus,
    SetupStep,
    SourceKind,
    StatementCheck,
    TodoAction,
    TodoKind,
    Tone,
    TransactionKind,
    TransferStep,
    UnusualKind,
)
from .money import Money, Unit, round_half_up

MONTHS = (
    "Ocak",
    "Şubat",
    "Mart",
    "Nisan",
    "Mayıs",
    "Haziran",
    "Temmuz",
    "Ağustos",
    "Eylül",
    "Ekim",
    "Kasım",
    "Aralık",
)

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
    Certainty.EXCLUDED: "Ekstrede yok",
    Certainty.INFO: "Yalnızca bilgi",
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
    DocumentKind.NOTICE: "Banka bildirimi",
    DocumentKind.INVOICE: "Fatura ya da makbuz",
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

BACKUP_REASON: dict[BackupReason, str] = {
    BackupReason.DAILY: "Günlük",
    BackupReason.MANUAL: "Elle",
    BackupReason.BEFORE_RESTORE: "Geri yükleme öncesi",
}

SERIES_STATUS: dict[SeriesStatus, str] = {
    SeriesStatus.ACTIVE: "Devam ediyor",
    SeriesStatus.ENDED: "Bitti",
    SeriesStatus.CANCELLED: "İptal edildi",
    SeriesStatus.PAID_AFTER_CANCEL: "İptalden sonra ödeme var",
}

SERIES_PERIOD: dict[SeriesPeriod, str] = {
    SeriesPeriod.MONTH: "Ayda bir",
    SeriesPeriod.HALF_YEAR: "Altı ayda bir",
    SeriesPeriod.YEAR: "Yılda bir",
}

PAYMENT_KIND: dict[PaymentKind, str] = {
    PaymentKind.REGULAR: "Düzenli ödeme",
    PaymentKind.PERIODIC: "Dönemsel ödeme",
    PaymentKind.INCOME: "Düzenli gelir",
    PaymentKind.INSTALLMENT: "Kart taksiti",
    PaymentKind.LOAN: "Kredi taksiti",
    PaymentKind.CARD_DUE: "Kart son ödemesi",
    PaymentKind.BILL: "Fatura",
}

INVOICE_KIND: dict[InvoiceKind, str] = {
    InvoiceKind.BILL: "Fatura",
    InvoiceKind.RECEIPT: "Makbuz",
}

INVOICE_STATUS: dict[InvoiceStatus, str] = {
    InvoiceStatus.MATCHED: "Eşleşti",
    InvoiceStatus.PENDING: "Bekliyor",
    InvoiceStatus.UNMATCHED: "Eşleşmedi",
}

EVENT_KIND: dict[EventKind, str] = {
    EventKind.DOCUMENT_RECEIVED: "Belge geldi",
    EventKind.DOCUMENT_PROCESSED: "Belge okundu",
    EventKind.DOCUMENT_UNPROCESSED: "Belge tanınmadı",
    EventKind.DOCUMENT_UNREADABLE: "Belge okunamadı",
    EventKind.TRANSACTION_CREATED: "Yeni işlem",
    EventKind.TRANSACTION_CONFIRMED: "Geçici işlem kesinleşti",
    EventKind.TRANSACTION_LARGE: "Büyük harcama",
    EventKind.EVIDENCE_UNMATCHED: "Ekstrede görünmeyen dekont",
    EventKind.INVOICE_MATCHED: "Fatura eşleşti",
    EventKind.INVOICE_PENDING: "Fatura bekliyor",
    EventKind.INVOICE_UNMATCHED: "Fatura eşleşmedi",
    EventKind.PAYMENT_DUE_SOON: "Son ödeme yaklaşıyor",
    EventKind.EXPECTED_PAYMENT_MISSING: "Beklenen ödeme gelmedi",
    EventKind.BALANCE_FORECAST_NEGATIVE: "Hesap eksiye düşecek",
    EventKind.SUBSCRIPTION_PRICE_CHANGED: "Düzenli ödeme zammı",
    EventKind.SUBSCRIPTION_PAID_AFTER_CANCEL: "İptalden sonra ödeme",
    EventKind.INCOME_RECEIVED: "Gelir geldi",
    EventKind.INCOME_LATE: "Gelir gecikti",
    EventKind.MONTH_ENDED: "Ay bitti",
    EventKind.MONTH_CLOSED: "Ay kapandı",
    EventKind.MONTH_NEEDS_CHECK: "Ay kontrol gerektiriyor",
    EventKind.PARSER_FORMAT_ALARM: "Okuyucu biçim alarmı",
    EventKind.MAIL_AUTH_FAILED: "E-posta girişi reddedildi",
    EventKind.MAIL_BRIDGE_ALARM: "Eklenti Gmail sayfasını tanımadı",
    EventKind.MAIL_BRIDGE_SILENT: "Tarayıcı eklentisi görünmüyor",
    EventKind.BACKUP_FAILED: "Yedek alınamadı",
    EventKind.BRIDGE_PAIRED: "Eklenti eşleşti",
    EventKind.BRIDGE_REVOKED: "Eklentinin eşleşmesi iptal edildi",
}

CHANNEL: dict[Channel, str] = {
    Channel.IN_APP: "Uygulama içi",
    Channel.DESKTOP: "Masaüstü",
    Channel.EMAIL: "E-posta",
    Channel.TELEGRAM: "Telegram",
}

DETAIL_LEVEL: dict[DetailLevel, str] = {
    DetailLevel.FULL: "Tam",
    DetailLevel.SUMMARY: "Özet",
    DetailLevel.MINIMAL: "Asgari",
}

DELIVERY_STATUS: dict[DeliveryStatus, str] = {
    DeliveryStatus.PENDING: "Gönderilecek",
    DeliveryStatus.SENT: "Gönderildi",
    DeliveryStatus.HELD: "Özete kaldı",
    DeliveryStatus.DIGESTED: "Özetle gönderildi",
    DeliveryStatus.FAILED: "Gönderilemedi",
}

TODO_KIND: dict[TodoKind, str] = {
    TodoKind.UNCATEGORIZED: "Kategorisiz işlemler",
    TodoKind.UNMATCHED_EVIDENCE: "Ekstrede görünmeyen kanıt",
    TodoKind.UNMATCHED_INVOICE: "Eşleşmeyen fatura",
    TodoKind.UNVERIFIED_STATEMENT: "Doğrulanmayan ekstre",
    TodoKind.MISSING_DOCUMENTS: "Eksik belge",
    TodoKind.UNPROCESSED_DOCUMENT: "İşlenmeyen belge",
    TodoKind.ORPHAN_ANNOTATION: "Eşi bulunamayan düzeltme",
    TodoKind.SPLIT_DROPPED: "Uygulanamayan bölme",
    TodoKind.FORMAT_ALARM: "Okuyucu biçim alarmı",
}

TODO_ACTION: dict[TodoAction, str] = {
    TodoAction.ADD_RULE: "Kural ekle",
    TodoAction.UPLOAD: "Belge yükle",
    TodoAction.REPARSE: "Yeniden oku",
    TodoAction.OPEN: "Göster",
    TodoAction.ASK_CLAUDE: "Claude'a ver",
    TodoAction.IGNORE: "Yok say",
}

CHANNEL_STAGE: dict[ChannelStage, str] = {
    ChannelStage.READY: "Hazır",
    ChannelStage.STOPPED: "Durdu",
    ChannelStage.UNAVAILABLE: "Kullanılamıyor",
    ChannelStage.NO_BOT: "Kurulmadı",
    ChannelStage.TOKEN_LOST: "Belirteç gerekli",
    ChannelStage.NOT_PAIRED: "Eşleşmedi",
}

CATEGORY_REASON: dict[CategoryReason, str] = {
    CategoryReason.RULE: "Kategori kuralı",
    CategoryReason.BANK_CATEGORY: "Bankanın yazdığı kategori",
    CategoryReason.WEAK_RULE: "Zayıf anahtar sözcük",
    CategoryReason.INVOICE: "Faturadaki satıcı",
    CategoryReason.TRANSFER_RULE: "Transfer kuralı",
    CategoryReason.KIND: "İşlemin türü",
    CategoryReason.FEE: "Faiz ve ücret",
    CategoryReason.OWN_TRANSFER: "Kendi hesaplarınız arası",
    CategoryReason.PERSON: "Kişiye gönderilen para",
    CategoryReason.INCOME: "Gelen para",
    CategoryReason.UNCATEGORIZED: "Hiçbir kural bulamadı",
    CategoryReason.USER: "Sizin düzeltmeniz",
    CategoryReason.SPLIT: "Sizin bölmeniz",
}

TRANSFER_STEP: dict[TransferStep, str] = {
    TransferStep.OWN_NAME: "Karşı taraf sizsiniz",
    TransferStep.OWN_ACCOUNT: "Açıklama kendi hesabınızı anıyor",
    TransferStep.RULE: "Bir kural karşı tarafı ya da amacı adlandırıyor",
    TransferStep.LIKE_NAMED: "Kuralın adlandırdığı bir ödemeyle aynı banka ve tutar",
    TransferStep.PAIRED: "Başka bir hesabınızda karşılığı var",
    TransferStep.UNCOVERED_BANK: "Hesabınız olan bir bankaya, dökümünün kapsamadığı bir günde",
    TransferStep.PERSON: "Kişiye gönderilen para",
    TransferStep.INCOME: "Gelen para",
}

RULE_LAYER: dict[RuleLayer, str] = {RuleLayer.OWN: "Sizin kurallarınız", RuleLayer.SHIPPED: "Hazır kurallar"}

HABIT_STATUS: dict[HabitStatus, str] = {
    HabitStatus.MONTHLY: "Her ay",
    HabitStatus.NEW: "Yeni alışkanlık",
    HabitStatus.OCCASIONAL: "Ara sıra",
    HabitStatus.STOPPED: "Durdu",
    HabitStatus.ONE_OFF: "Tek seferlik",
}

NECESSITY_REASON: dict[NecessityReason, str] = {
    NecessityReason.USER: "Sizin düzeltmeniz",
    NecessityReason.MERCHANT: "İşyerinin kendi düzeyi",
    NecessityReason.CATEGORY: "Kategorisinin düzeyi",
    NecessityReason.DEFAULT: "Kural yok: belirsiz",
}

FORECAST_PART: dict[ForecastPart, str] = {
    ForecastPart.REGULAR: "Düzenli ödemeler",
    ForecastPart.INSTALLMENTS: "Kalan taksitler",
    ForecastPart.VARIABLE: "Değişken harcamalar",
}

UNUSUAL_KIND: dict[UnusualKind, str] = {
    UnusualKind.UNUSUAL_AMOUNT: "Alışılmadık tutar",
    UnusualKind.POSSIBLE_DUPLICATE: "Olası çift çekim",
    UnusualKind.NEW_LARGE: "Yeni bir yerde büyük tutar",
    UnusualKind.UNEXPECTED_FEE: "Beklenmedik ücret",
}

ACCOUNT_GROUP: dict[AccountGroup, str] = {
    AccountGroup.CARDS: "Kredi kartları",
    AccountGroup.CURRENT: "Vadesiz",
    AccountGroup.DEPOSIT: "Vadeli",
    AccountGroup.OVERDRAFT: "KMH",
    AccountGroup.FX: "Döviz",
    AccountGroup.GOLD: "Altın",
    AccountGroup.BROKERAGE: "Yatırım",
    AccountGroup.LOAN: "Krediler",
}

PAID_STATUS: dict[PaidStatus, str] = {
    PaidStatus.FULL: "Tamamı ödendi",
    PaidStatus.MINIMUM: "Asgari ödendi",
    PaidStatus.PARTIAL: "Kısmen ödendi",
    PaidStatus.UNPAID: "Ödenmedi",
    PaidStatus.OPEN: "Son ödeme tarihi gelmedi",
    PaidStatus.NOTHING_DUE: "Borç yoktu",
}

SETUP_STEP: dict[SetupStep, str] = {
    SetupStep.DATA_FOLDER: "Veri klasörü",
    SetupStep.NAMES: "Adınız",
    SetupStep.BUSINESS_NAMES: "Şirket adları",
    SetupStep.MAIL: "E-posta",
    SetupStep.SENDERS: "Bankalar ve göndericiler",
    SetupStep.DOCUMENTS: "Eski belgeler",
    SetupStep.NOTIFICATIONS: "Bildirimler",
    SetupStep.SERVICE: "Servis",
    SetupStep.REMOTE: "Uzaktan erişim",
}

RATE_SOURCE: dict[RateSource, str] = {
    RateSource.DOCUMENT: "Belgedeki kur",
    RateSource.TCMB: "TCMB",
    RateSource.ECB: "ECB",
    RateSource.FRANKFURTER: "Frankfurter (ECB)",
}

STATEMENT_CHECK: dict[StatementCheck, str] = {
    StatementCheck.VERIFIED: "Tutarlı",
    StatementCheck.FAILED: "Tutmuyor",
    StatementCheck.NOTHING: "Denetlenecek satır yok",
}

FLOW_KIND: dict[FlowKind, str] = {
    FlowKind.ACCOUNT: "Hesap",
    FlowKind.INCOME: "Gelir",
    FlowKind.SPENDING: "Harcama",
    FlowKind.PEOPLE: "Kişiler",
    FlowKind.SAVING: "Birikim ve yatırım",
    FlowKind.LOAN: "Kredi",
    FlowKind.CASH: "Nakit",
    FlowKind.ELSEWHERE: "Belgesi olmayan hesap",
}


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
    BackupReason: _table(BACKUP_REASON),
    SeriesStatus: _table(SERIES_STATUS),
    SeriesPeriod: _table(SERIES_PERIOD),
    PaymentKind: _table(PAYMENT_KIND),
    InvoiceKind: _table(INVOICE_KIND),
    InvoiceStatus: _table(INVOICE_STATUS),
    EventKind: _table(EVENT_KIND),
    Channel: _table(CHANNEL),
    DetailLevel: _table(DETAIL_LEVEL),
    DeliveryStatus: _table(DELIVERY_STATUS),
    ChannelStage: _table(CHANNEL_STAGE),
    TodoKind: _table(TODO_KIND),
    TodoAction: _table(TODO_ACTION),
    AccountGroup: _table(ACCOUNT_GROUP),
    PaidStatus: _table(PAID_STATUS),
    FlowKind: _table(FLOW_KIND),
    StatementCheck: _table(STATEMENT_CHECK),
    RateSource: _table(RATE_SOURCE),
    CategoryReason: _table(CATEGORY_REASON),
    TransferStep: _table(TRANSFER_STEP),
    RuleLayer: _table(RULE_LAYER),
    HabitStatus: _table(HABIT_STATUS),
    UnusualKind: _table(UNUSUAL_KIND),
    NecessityReason: _table(NECESSITY_REASON),
    ForecastPart: _table(FORECAST_PART),
    SetupStep: _table(SETUP_STEP),
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


def format_rate(value: Decimal) -> str:
    """A TL rate as TCMB's bulletin prints it: Decimal("36.45213") → "36,4521", four decimals rounded half up, dots
    between thousands, a comma before the decimals."""
    return f"{round_half_up(value, 4):,.4f}".replace(",", " ").replace(".", ",").replace(" ", ".")


def format_money(money: Money) -> str:
    """Money("1234.5", "TRY") → "1.234,50 TL"."""
    return f"{format_amount(money.amount)} {currency_label(money.currency)}"
