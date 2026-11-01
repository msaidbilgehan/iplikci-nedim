"""Assign merchant, category, group and necessity to transactions using kategoriler.yaml."""

import re
from dataclasses import dataclass, field
from decimal import Decimal
from pathlib import Path

import yaml

from .domain.codes import CARD_TYPES, AccountType, Necessity, TransactionKind
from .domain.labels import NECESSITY
from .domain.models import Account, Transaction
from .textutil import fold, nfc, title_tr

# The generic rules shipped with the app. The user's own rules go above them in a file of their own.
DEFAULT_RULES = Path(__file__).parent / "rules" / "default.yaml"
PERSONAL_TEMPLATE = """\
# Kişisel kategori kurallarınız. Uygulamayla gelen genel kuralların üstüne biner: burada tutan bir kural
# onlardan önce gelir. Yapı aynıdır: Ana grup → Kategori → İşletme ya da kişi adı → [desenler].
#
# Kişiye özgü kararlar buraya yazılır: kira ve aidat alıcıları, aile ve kişiler, gelir kaynakları, biten
# ödemeler (_biten), bir işyerinin gerekliliği (_gereklilik_işyeri).
"""

FINANCE_GROUP = "Banka & Finans"
OTHER_GROUP = "Diğer"
UNCATEGORIZED = "Diğer Harcamalar"
OTHER_INCOME = "Diğer Gelirler"
TO_PEOPLE = "Kişilere Gönderilen"

# Every chart gives a group and a necessity level the same colour: the first eight groups (rule-file
# order) take categorical slots 1-8, later groups and "Diğer" the neutral colour (0). Blue / yellow /
# magenta passed the palette checks as an adjacent stack of necessity levels in both modes.
MAX_COLORED_GROUPS = 8
NECESSITY_SLOTS = {Necessity.REQUIRED: 1, Necessity.OPTIONAL: 4, Necessity.UNNECESSARY: 5, Necessity.UNKNOWN: 0}


def group_slot(groups: list[str], group: str) -> int:
    i = groups.index(group) if group in groups else len(groups)
    return i + 1 if i < MAX_COLORED_GROUPS and group != OTHER_GROUP else 0


# Kinds that are not purchases get a fixed category in the finance group.
KIND_CATEGORY = {
    TransactionKind.LOAN_PRINCIPAL: "Kredi & Borç Anapara",
    TransactionKind.CASH_ADVANCE: "Nakit Avans & Çekim",
    TransactionKind.CARD_PAYMENT_NO_STATEMENT: "Ekstresiz Kart Ödemeleri",
    TransactionKind.CARD_PAYMENT: "Kart Borcu Ödemeleri",
    TransactionKind.OWN_TRANSFER: "Hesaplar Arası Transfer",
    # Trades a brokerage statement prints; a BES or capital payment gets its category from a rule instead.
    TransactionKind.INVESTMENT: "Hisse Senedi Alım-Satımı",
}
FX_CATEGORY = "Döviz & Altın Alım-Satımı"
FEE_CATEGORIES = {
    "card_interest": "Kredi Kartı Faizi",
    "overdraft_interest": "Ek Hesap (KMH) Faizi",
    "loan_interest": "Kredi Faizi",
    "transfer_fee": "Transfer & İşlem Ücretleri",
    "card_fee": "Kart Aidatı & Ücretleri",
}

# `_tür` of a category, as the rule file writes it (folded), per money direction (out, in).
_KIND_BY_TYPE = {
    "": (TransactionKind.PURCHASE, TransactionKind.REFUND),
    "gelir": (TransactionKind.P2P_TRANSFER, TransactionKind.INCOME),
    "kisi": (TransactionKind.P2P_TRANSFER, TransactionKind.INCOME),
    "borc": (TransactionKind.LOAN_PRINCIPAL, TransactionKind.LOAN_PRINCIPAL),
    "yatirim": (TransactionKind.INVESTMENT, TransactionKind.INVESTMENT),
}

_GENERIC = "_"
_WEAK = "_ZAYIF"
_TYPE_KEY = "_TUR"
_MONTH = re.compile(r"\d{4}-\d{2}")


@dataclass
class Rule:
    group: str
    category: str
    merchant: str  # "" for generic keywords
    regex: re.Pattern
    squashed: str  # multi-word pattern without spaces, for descriptions printed without spaces

    def find(self, folded: str, squashed: str) -> int | None:
        m = self.regex.search(folded)
        if m:
            return m.start()
        if self.squashed and self.squashed in squashed:
            return squashed.index(self.squashed)
        return None


def _compile(pattern: str) -> tuple[re.Pattern, str]:
    pattern = str(pattern)
    if pattern.startswith("re:"):
        return re.compile(pattern[3:]), ""
    p = fold(pattern)
    # Match at the start of a word: "BIM" finds "BIM A.S." but not "EBIM".
    return re.compile(r"(?<![A-Z])" + re.escape(p)), (p.replace(" ", "") if " " in p else "")


def _level(value: str, name: str) -> Necessity:
    """A necessity level as the rule file writes it (its Turkish label)."""
    level = {fold(label): code for code, label in NECESSITY.items()}.get(fold(value))
    if not level:
        raise ValueError(f"{name}: bilinmeyen gereklilik '{value}' (seçenekler: {', '.join(NECESSITY.values())})")
    return level


def _ended(entries: dict, name: str) -> dict[str, str]:
    """`_biten`: merchant -> month ("YYYY-MM") after which no payment is expected.
    YAML reads 2026-10-12 as a date, so only the year and month are kept."""
    out = {}
    for merchant, when in entries.items():
        month = str(when)[:7]
        if not _MONTH.fullmatch(month):
            raise ValueError(f"{name}: _biten altında '{merchant}' için ay YYYY-AA biçiminde olmalı (ör. 2026-10)")
        out[fold(str(merchant))] = month
    return out


def _earliest(rules: list[Rule], f: str, sq: str) -> Rule | None:
    best, best_pos = None, None
    for rule in rules:
        pos = rule.find(f, sq)
        if pos is not None and (best_pos is None or pos < best_pos):
            best, best_pos = rule, pos
    return best


@dataclass
class RuleSet:
    """The rules of one rule file (a layer)."""

    name: str
    groups: list[str] = field(default_factory=list)  # in file order
    categories: dict[str, str] = field(default_factory=dict)  # category -> group, in file order
    types: dict[str, str] = field(default_factory=dict)  # category -> `_tür`
    necessity: dict[str, Necessity] = field(default_factory=dict)  # category -> level
    merchant_necessity: dict[str, Necessity] = field(default_factory=dict)  # folded merchant -> level
    ended: dict[str, str] = field(default_factory=dict)  # folded merchant -> last month with a payment
    regular: set[str] = field(default_factory=set)  # categories of commitments: rent, dues, bills, subscriptions
    named: list[Rule] = field(default_factory=list)
    generic: list[Rule] = field(default_factory=list)
    weak: list[Rule] = field(default_factory=list)
    bank_categories: dict[str, str] = field(default_factory=dict)

    @classmethod
    def read(cls, path: Path) -> "RuleSet":
        return cls.parse(path.read_text(encoding="utf-8"), path.name)

    @classmethod
    def parse(cls, text: str, name: str) -> "RuleSet":
        data = yaml.safe_load(text) or {}
        if not isinstance(data, dict):
            raise ValueError(f"{name} 'Ana grup: …' eşlemelerinden oluşmalı")  # noqa: TRY004 - the user's file, not a bug
        rules = cls(name)
        for group, categories in data.items():
            group = nfc(str(group))
            key = fold(group)
            if key == "_BANKA_KATEGORILERI":
                rules.bank_categories = {fold(k): nfc(str(v)) for k, v in (categories or {}).items()}
                continue
            if key == "_GEREKLILIK":
                for level, names in (categories or {}).items():
                    for category in names or []:
                        rules.necessity[nfc(str(category))] = _level(str(level), name)
                continue
            if key == "_GEREKLILIK_ISYERI":
                rules.merchant_necessity = {fold(str(k)): _level(str(v), name) for k, v in (categories or {}).items()}
                continue
            if key == "_BITEN":
                rules.ended = _ended(categories or {}, name)
                continue
            if key == "_DUZENLI":
                rules.regular = {nfc(str(c)) for c in categories or []}
                continue
            if group.startswith("_"):
                continue
            rules.groups.append(group)
            for category, merchants in (categories or {}).items():
                category = nfc(str(category))
                rules.categories[category] = group
                for merchant, patterns in (merchants or {}).items():
                    merchant = nfc(str(merchant))
                    if fold(merchant) == _TYPE_KEY:
                        rules.types[category] = fold(str(patterns)).lower()
                        continue
                    if isinstance(patterns, str):
                        patterns = [patterns]
                    target = {_GENERIC: rules.generic, _WEAK: rules.weak}.get(fold(merchant), rules.named)
                    for p in patterns or []:
                        regex, squashed = _compile(p)
                        target.append(
                            Rule(group, category, "" if target is not rules.named else merchant, regex, squashed)
                        )
        return rules

    def strong(self, f: str, sq: str) -> Rule | None:
        """Named merchants in file order, then the generic keyword found first in the description."""
        for rule in self.named:
            if rule.find(f, sq) is not None:
                return rule
        return _earliest(self.generic, f, sq)


class Categorizer:
    """The rules of one or more layers, the first layer first: the user's own rules go above the ones shipped
    with the app (docs/domain/categorization.md). A rule of an upper layer that matches wins; only when none does
    are the layers below tried."""

    def __init__(self, *paths: Path):
        self._combine([RuleSet.read(p) for p in paths])

    @classmethod
    def layered(cls, personal: Path | None, defaults: Path | None = DEFAULT_RULES) -> "Categorizer":
        """The user's rules over the defaults; a personal file that does not exist yet is simply left out."""
        return cls(*(p for p in (personal, defaults) if p is not None and (p is defaults or p.exists())))

    @classmethod
    def from_layers(cls, *layers: RuleSet) -> "Categorizer":
        c = cls.__new__(cls)
        c._combine(list(layers))
        return c

    def _combine(self, layers: list[RuleSet]) -> None:
        self.layers = layers
        self.groups: list[str] = []
        self.categories: dict[str, str] = {}
        self.types: dict[str, str] = {}
        self.necessity: dict[str, Necessity] = {}
        self.merchant_necessity: dict[str, Necessity] = {}
        self.ended: dict[str, str] = {}
        self.regular: set[str] = set()
        # From the bottom layer up: an upper layer's value replaces the one below; the defaults' group order (and
        # so the colours) stays, and groups only an upper layer has come after them.
        for layer in reversed(layers):
            self.groups += [g for g in layer.groups if g not in self.groups]
            self.categories.update(layer.categories)
            self.types.update(layer.types)
            self.necessity.update(layer.necessity)
            self.merchant_necessity.update(layer.merchant_necessity)
            self.ended.update(layer.ended)
            self.regular |= layer.regular
        for group in (FINANCE_GROUP, OTHER_GROUP):
            if group not in self.groups:
                self.groups.append(group)
        for category in (*KIND_CATEGORY.values(), FX_CATEGORY, *FEE_CATEGORIES.values()):
            self.categories.setdefault(category, FINANCE_GROUP)
        for category in (UNCATEGORIZED, OTHER_INCOME, TO_PEOPLE):
            self.categories.setdefault(category, OTHER_GROUP)
        self.types.setdefault(OTHER_INCOME, "gelir")
        self.types.setdefault(TO_PEOPLE, "kisi")
        # "Diğer" always sorts last so it can take the neutral color.
        self.groups = [g for g in self.groups if g != OTHER_GROUP] + [OTHER_GROUP]

    def match(self, description: str, weak: bool = True) -> Rule | None:
        f = fold(description)
        sq = f.replace(" ", "")
        for layer in self.layers:
            rule = layer.strong(f, sq)
            if rule:
                return rule
        if weak:
            for layer in self.layers:
                rule = _earliest(layer.weak, f, sq)
                if rule:
                    return rule
        return None

    def kind_for(self, category: str, amount: Decimal) -> TransactionKind:
        out_kind, in_kind = _KIND_BY_TYPE.get(self.types.get(category, ""), _KIND_BY_TYPE[""])
        return out_kind if amount > 0 else in_kind

    def resolve_kind(self, t: Transaction) -> bool:
        """Give a transfer candidate a kind and category when a rule names its party or purpose."""
        rule = self.match(f"{t.description} {t.counterparty}", weak=False)
        if not rule:
            return False
        t.kind = self.kind_for(rule.category, t.amount)
        t.category = rule.category
        t.merchant = rule.merchant or display_name(t.counterparty or t.description)
        return True

    def apply(self, txn: Transaction, account: Account | None) -> None:
        bank = account.bank if account else ""
        if txn.kind == TransactionKind.INTEREST_FEE:
            rule = self.match(txn.description, weak=False)
            txn.category = _fee_category(txn, account)
            txn.merchant = (
                rule.merchant if rule and rule.merchant else f"{bank} faiz & ücretleri" if bank else "Faiz & ücretler"
            )
        elif txn.kind == TransactionKind.OWN_TRANSFER:
            f = fold(txn.description)
            txn.category = (
                FX_CATEGORY
                if any(p in f for p in ("DOVIZ", "DVZ", "ALTIN"))
                else KIND_CATEGORY[TransactionKind.OWN_TRANSFER]
            )
            txn.merchant = account.label if account else "Transfer"
        elif txn.category:
            pass  # decided while resolving transfers (rent, family, salary, ...)
        elif txn.kind in KIND_CATEGORY:
            txn.category = KIND_CATEGORY[txn.kind]
            txn.merchant = _finance_merchant(txn, account, bank)
        elif txn.kind == TransactionKind.INCOME:
            rule = self.match(f"{txn.description} {txn.counterparty}", weak=False)
            txn.category = rule.category if rule else OTHER_INCOME
            txn.merchant = (rule.merchant if rule and rule.merchant else "") or display_name(
                txn.counterparty or txn.description
            )
        elif txn.kind == TransactionKind.P2P_TRANSFER:
            txn.category, txn.merchant = TO_PEOPLE, display_name(txn.counterparty or txn.description)
        else:
            # Named merchants and keywords first, then the bank's own category
            # heading, and only then the weak keywords.
            rule = self.match(txn.description, weak=False)
            hint = "" if rule else self._bank_hint(txn.bank_category)
            if not rule and not hint:
                rule = self.match(txn.description)
            if rule:
                txn.category = rule.category
                txn.merchant = rule.merchant or display_name(txn.description)
                if self.types.get(rule.category) == "yatirim":
                    txn.kind = TransactionKind.INVESTMENT  # e.g. a private pension paid by card
            else:
                txn.category = hint or UNCATEGORIZED
                txn.merchant = display_name(txn.description)
        txn.group = self.categories.get(txn.category, OTHER_GROUP)
        txn.necessity = self.necessity_for(txn)

    def necessity_for(self, txn: Transaction) -> Necessity | None:
        """The necessity level the rules give a categorized row (None for rows that are no spending)."""
        if txn.kind == TransactionKind.INTEREST_FEE:
            return self.necessity.get(txn.category, Necessity.UNNECESSARY)
        if txn.kind not in (TransactionKind.PURCHASE, TransactionKind.REFUND, TransactionKind.P2P_TRANSFER):
            return None
        return self.merchant_necessity.get(fold(txn.merchant)) or self.necessity.get(txn.category, Necessity.UNKNOWN)

    def _bank_hint(self, bank_category: str) -> str:
        if not bank_category:
            return ""
        f = fold(bank_category)
        for layer in self.layers:
            for key, category in layer.bank_categories.items():
                if key in f:
                    return category
        return ""


def _fee_category(txn: Transaction, account: Account | None) -> str:
    """Split bank costs into what caused them: card interest, overdraft, loan, transfers, card fees."""
    f = fold(txn.description)
    kind = account.type if account else None
    card = kind in CARD_TYPES
    if card and any(
        p in f for p in ("YILLIK", "UYELIK", "AIDAT", "NAKIT AVANS UCRETI", "KART UCRETI", "ODEME UCRETI", "ATM")
    ):
        return FEE_CATEGORIES["card_fee"]
    if (
        not card
        and kind != AccountType.LOAN
        and "FAIZ" not in f
        and any(p in f for p in ("UCRET", "EFT", "HAVALE", "KESINTI VE EKLERI", "KAMBIYO", "KMV", "MASRAF", "KOMISYON"))
    ):
        return FEE_CATEGORIES["transfer_fee"]
    if kind == AccountType.LOAN:
        return FEE_CATEGORIES["loan_interest"]
    if not card:
        return FEE_CATEGORIES["overdraft_interest"]
    return FEE_CATEGORIES["card_interest"]


def _finance_merchant(txn: Transaction, account: Account | None, bank: str) -> str:
    if txn.kind == TransactionKind.LOAN_PRINCIPAL:
        return "QNB ihtiyaç kredisi" if account and account.type == AccountType.LOAN else f"{bank} taksitli nakit avans"
    if txn.kind == TransactionKind.CASH_ADVANCE:
        return f"{bank} nakit avans / çekim"
    if account:
        return account.label
    return "Transfer"


# --- merchant display names -------------------------------------------------

_NOISE = [
    re.compile(r"KAZANILAN(\s*MAX[İI]PUAN\s*:?\s*[\d.,]*)?", re.IGNORECASE),
    re.compile(r"-?\s*MAX[İI]PUAN\s*[İI]LAVE\s*:?\s*[\d.,]*", re.IGNORECASE),
    re.compile(r"İŞLEM\s*İPTALI", re.IGNORECASE),
    re.compile(r"^TAKSİTLENDİRME\s*/\s*", re.IGNORECASE),
    re.compile(r"\bFT:\s*\d+"),
    re.compile(r"\bFAT\.?\s*ÖDE\.?", re.IGNORECASE),
    re.compile(r"^\d{2}/\d{2}/\d{4}\s+"),
    re.compile(r"^\d{6,}\s*"),
]
_COUNTRIES = {
    "TR",
    "TU",
    "TUR",
    "IE",
    "DE",
    "NL",
    "US",
    "USA",
    "GB",
    "GBGB",
    "AZ",
    "CA",
    "LU",
    "SG",
    "FR",
    "UTUS",
    "CCAUS",
    "WAUS",
    "IRIR",
    "TRTR",
}
# Statements print the place of a purchase after the merchant's name: the Turkish provinces (and the centres
# printed instead of some), plus the cities online services bill from and a few nearby capitals. Aydın, Bingöl,
# Karaman and Tokat are left out: they are common surnames, and "MEHMET AYDIN" must stay a person's full name.
_CITIES = frozenset(
    {
        "ADANA",
        "ADAPAZARI",
        "ADIYAMAN",
        "AFYON",
        "AFYONKARAHISAR",
        "AGRI",
        "AKSARAY",
        "AMASYA",
        "ANKARA",
        "ANTAKYA",
        "ANTALYA",
        "ARDAHAN",
        "ARTVIN",
        "BALIKESIR",
        "BARTIN",
        "BATMAN",
        "BAYBURT",
        "BILECIK",
        "BITLIS",
        "BOLU",
        "BURDUR",
        "BURSA",
        "CANAKKALE",
        "CANKIRI",
        "CORUM",
        "DENIZLI",
        "DIYARBAKIR",
        "DUZCE",
        "EDIRNE",
        "ELAZIG",
        "ERZINCAN",
        "ERZURUM",
        "ESKISEHIR",
        "GAZIANTEP",
        "GIRESUN",
        "GUMUSHANE",
        "HAKKARI",
        "HATAY",
        "ICEL",
        "IGDIR",
        "ISPARTA",
        "ISTANBUL",
        "ISTANBU",
        "IZMIR",
        "IZMIT",
        "KAHRAMANMARAS",
        "KARABUK",
        "KARS",
        "KASTAMONU",
        "KAYSERI",
        "KILIS",
        "KIRIKKALE",
        "KIRKLARELI",
        "KIRSEHIR",
        "KOCAELI",
        "KONYA",
        "KUTAHYA",
        "MALATYA",
        "MANISA",
        "MARDIN",
        "MERSIN",
        "MUGLA",
        "MUS",
        "NEVSEHIR",
        "NIGDE",
        "ORDU",
        "OSMANIYE",
        "RIZE",
        "SAKARYA",
        "SAMSUN",
        "SANLIURFA",
        "SIIRT",
        "SINOP",
        "SIRNAK",
        "SIVAS",
        "TEKIRDAG",
        "TRABZON",
        "TUNCELI",
        "USAK",
        "VAN",
        "YALOVA",
        "YOZGAT",
        "ZONGULDAK",
        "AMSTERDAM",
        "ATHENS",
        "BAKU",
        "BELLEVUE",
        "BERLIN",
        "CORK",
        "CUPERTINO",
        "DUBLIN",
        "FRANCISCO",
        "LEFKOSA",
        "LONDON",
        "LUXEMBOURG",
        "NICOSIA",
        "PARIS",
        "REDMOND",
        "SEATTLE",
        "SINGAPORE",
        "SOFIA",
        "TBILISI",
    }
)
# A city glued to the merchant's name ("ANONISTANBUL") is cut off as well, longest name first; names shorter
# than five letters would cut real words ("KARAVAN").
_GLUED_CITIES = tuple(sorted((c for c in _CITIES if len(c) >= 5), key=len, reverse=True))


def clean_description(description: str) -> str:
    """Strip reward-point notes, reference numbers and the trailing city/country."""
    s = nfc(description)
    for rx in _NOISE:
        s = rx.sub(" ", s)
    tokens = s.split()
    while tokens:
        last = tokens[-1]
        f = fold(last)
        if f in _COUNTRIES or f in _CITIES:
            tokens.pop()
            continue
        city = next((c for c in _GLUED_CITIES if f.endswith(c) and len(f) > len(c)), None)
        if city and len(f) == len(last):
            tokens[-1] = last[: len(last) - len(city)]
            continue
        break
    return " ".join(tokens).strip(" -/*,")


def display_name(description: str) -> str:
    s = clean_description(description) or description.strip()
    letters = [c for c in s if c.isalpha()]
    if letters and sum(c.isupper() for c in letters) / len(letters) > 0.8:
        return title_tr(s)
    return s
