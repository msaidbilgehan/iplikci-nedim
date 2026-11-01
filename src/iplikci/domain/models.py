"""The models the readers fill and the ledger combines: accounts, statements, rows, securities."""

from dataclasses import dataclass, field
from datetime import date

# Transaction kinds. Sign convention for every kind: amount > 0 is money leaving
# the user, amount < 0 is money coming in (refund, income, transfer in).
KINDS = {
    "harcama": "Harcama",
    "iade": "İade / indirim",
    "faiz_ucret": "Faiz & banka ücreti",
    "kisiye_transfer": "Kişilere gönderilen para",
    "kredi_anapara": "Kredi & borç anapara ödemesi",
    "nakit_avans": "Nakit avans / çekim",
    "yatirim": "Birikim & yatırım (döviz, altın, BES)",
    "gelir": "Gelir",
    "ekstresiz_kart": "Ekstresi olmayan kart ödemesi",
    "kart_odemesi": "Kredi kartı borç ödemesi",
    "transfer": "Kendi hesaplarım arası transfer",
}

# Kinds counted as "gider" unless the user switches them on/off in the report.
# Debt principal, cash advances, savings, card payments and transfers move money
# between the user's own pockets (or repay earlier spending) and would double
# count purchases; money sent to other people is shown but kept apart.
DEFAULT_EXPENSE_KINDS = ("harcama", "iade", "faiz_ucret")

# How necessary a spending category is; set per category in kategoriler.yaml.
NECESSITY = ("Gerekli", "İsteğe bağlı", "Gereksiz", "Belirsiz")

ACCOUNT_TYPES_WITH_STATEMENTS = ("Kredi kartı", "Banka kartı")

# A brokerage account holds securities, not the user's income or bills: its statements never decide
# which months are complete or whether a month's income is known.
INVESTMENT_TYPE = "Yatırım hesabı"


@dataclass
class Account:
    id: str
    label: str
    bank: str
    # "Kredi kartı", "Banka kartı", "Vadesiz hesap", "Vadeli hesap", "Ek hesap (KMH)", "Döviz hesabı",
    # "Altın hesabı", "Yatırım hesabı", "Kredi"
    type: str
    currency: str = "TL"
    number: str = ""  # card last digits or account number, for file names and own-account detection
    note: str = ""


@dataclass
class Transaction:
    date: date
    description: str
    amount: float
    kind: str
    account: str
    original: str = ""  # foreign amount, e.g. "19,99 USD"
    installment: str = ""  # e.g. "8/12"
    bank_category: str = ""  # category heading printed by the bank, if any
    counterparty: str = ""  # sender/receiver of a bank transfer
    source: str = ""
    # Filled in by categorize.py
    merchant: str = ""
    category: str = ""
    group: str = ""
    necessity: str = ""
    # Set by analysis.py: a receipt's row that no statement shows yet (it waits for the next one).
    provisional: bool = False
    # Set by analysis.py from the row as read (domain.fingerprint), and the user's note and tags bound to it.
    fingerprint: str = ""
    note: str = ""
    tags: tuple[str, ...] = ()


@dataclass
class Security:
    """A security held in an investment account, valued at the market price its statement prints."""

    code: str  # exchange ticker, e.g. "ORNEK"
    name: str
    quantity: float
    value: float  # market value in TL on as_of
    as_of: date


@dataclass
class Statement:
    """A card statement (hesap özeti) or an account movement list (hesap hareketleri)."""

    account: str
    cut_date: date  # statement cut date, or the last day of an account movement list
    currency: str
    source: str
    previous: float | None  # previous balance printed on the statement
    total: float | None  # statement balance printed on the statement
    transactions: list[Transaction] = field(default_factory=list[Transaction])
    # Debit-card statements only print the sum of purchases, not a balance.
    total_is_sum: bool = False
    # Account movement lists: covered period and running-balance checks.
    # previous / total then hold the opening and closing balance.
    start: date | None = None
    checks_ok: int = 0
    checks_total: int = 0
    balances: dict[str, float] = field(default_factory=dict[str, float])  # "YYYY-MM" -> month-end balance
    # Investment accounts: the securities held at the end of the statement (previous / total are the cash).
    securities: list[Security] = field(default_factory=list[Security])

    @property
    def is_account(self) -> bool:
        return self.start is not None

    @property
    def computed_total(self) -> float:
        lines = round(sum(t.amount for t in self.transactions), 2)
        return lines if self.total_is_sum else round((self.previous or 0) + lines, 2)

    @property
    def difference(self) -> float | None:
        if self.is_account:
            return float(self.checks_total - self.checks_ok)
        if self.total is None:
            return None
        return round(self.computed_total - self.total, 2)

    @property
    def verified(self) -> bool:
        if self.is_account:
            return self.checks_total > 0 and self.checks_ok == self.checks_total
        return self.difference is not None and abs(self.difference) < 0.015


@dataclass
class ParseResult:
    """What a parser extracted from one document."""

    parser: str
    accounts: list[Account] = field(default_factory=list[Account])
    statements: list[Statement] = field(default_factory=list[Statement])
    # Transactions that don't belong to a statement (bank receipts / dekont).
    transactions: list[Transaction] = field(default_factory=list[Transaction])
    # Unique id of a receipt so the same receipt in PDF and HTML is counted once.
    receipt_key: str = ""
    # Account holder printed on the document; used to recognise own transfers.
    holder: str = ""
    # Short title for the document, used when filing it ("Kredi Taksiti 5678").
    title: str = ""
