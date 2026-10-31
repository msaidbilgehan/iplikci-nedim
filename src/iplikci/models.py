"""Data model shared by parsers, analysis and the report."""

from dataclasses import asdict, dataclass, field
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

    def to_dict(self) -> dict:
        d = asdict(self)
        d["date"] = self.date.isoformat()
        return d

    @classmethod
    def from_dict(cls, d: dict) -> "Transaction":
        d = dict(d)
        d["date"] = date.fromisoformat(d["date"])
        return cls(**d)


@dataclass
class Security:
    """A security held in an investment account, valued at the market price its statement prints."""

    code: str  # exchange ticker, e.g. "ORNEK"
    name: str
    quantity: float
    value: float  # market value in TL on as_of
    as_of: date

    def to_dict(self) -> dict:
        return {**asdict(self), "as_of": self.as_of.isoformat()}

    @classmethod
    def from_dict(cls, d: dict) -> "Security":
        return cls(**{**d, "as_of": date.fromisoformat(d["as_of"])})


@dataclass
class Statement:
    """A card statement (hesap özeti) or an account movement list (hesap hareketleri)."""

    account: str
    cut_date: date  # statement cut date, or the last day of an account movement list
    currency: str
    source: str
    previous: float | None  # previous balance printed on the statement
    total: float | None  # statement balance printed on the statement
    transactions: list[Transaction] = field(default_factory=list)
    # Debit-card statements only print the sum of purchases, not a balance.
    total_is_sum: bool = False
    # Account movement lists: covered period and running-balance checks.
    # previous / total then hold the opening and closing balance.
    start: date | None = None
    checks_ok: int = 0
    checks_total: int = 0
    balances: dict[str, float] = field(default_factory=dict)  # "YYYY-MM" -> month-end balance
    # Investment accounts: the securities held at the end of the statement (previous / total are the cash).
    securities: list[Security] = field(default_factory=list)

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

    def to_dict(self) -> dict:
        d = asdict(self)
        d["cut_date"] = self.cut_date.isoformat()
        d["start"] = self.start.isoformat() if self.start else None
        d["transactions"] = [t.to_dict() for t in self.transactions]
        d["securities"] = [s.to_dict() for s in self.securities]
        return d

    @classmethod
    def from_dict(cls, d: dict) -> "Statement":
        d = dict(d)
        d["cut_date"] = date.fromisoformat(d["cut_date"])
        d["start"] = date.fromisoformat(d["start"]) if d.get("start") else None
        d["transactions"] = [Transaction.from_dict(t) for t in d["transactions"]]
        d["securities"] = [Security.from_dict(s) for s in d.get("securities", [])]
        return cls(**d)


@dataclass
class ParseResult:
    """What a parser extracted from one document."""

    parser: str
    accounts: list[Account] = field(default_factory=list)
    statements: list[Statement] = field(default_factory=list)
    # Transactions that don't belong to a statement (bank receipts / dekont).
    transactions: list[Transaction] = field(default_factory=list)
    # Unique id of a receipt so the same receipt in PDF and HTML is counted once.
    receipt_key: str = ""
    # Account holder printed on the document; used to recognise own transfers.
    holder: str = ""
    # Short title for the document, used when filing it ("Kredi Taksiti 5678").
    title: str = ""

    def to_dict(self) -> dict:
        return {
            "parser": self.parser,
            "accounts": [asdict(a) for a in self.accounts],
            "statements": [s.to_dict() for s in self.statements],
            "transactions": [t.to_dict() for t in self.transactions],
            "receipt_key": self.receipt_key,
            "holder": self.holder,
            "title": self.title,
        }

    @classmethod
    def from_dict(cls, d: dict) -> "ParseResult":
        return cls(
            parser=d["parser"],
            accounts=[Account(**a) for a in d["accounts"]],
            statements=[Statement.from_dict(s) for s in d["statements"]],
            transactions=[Transaction.from_dict(t) for t in d["transactions"]],
            receipt_key=d.get("receipt_key", ""),
            holder=d.get("holder", ""),
            title=d.get("title", ""),
        )
