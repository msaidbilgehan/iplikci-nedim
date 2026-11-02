"""Where an item of a screen leads in the interface (F05, F06; architecture §18): every number leads to what it rests
on, every row to its document. The service names the place, a screen and what to open there; the interface knows
the screens' addresses."""

from collections.abc import Mapping
from dataclasses import dataclass
from enum import StrEnum


class Screen(StrEnum):
    """A screen of the interface, as a link names it, and what the link's id holds there: document (a document's
    sha256, its query's "satir" a row's fingerprint to open it at), documents, transaction (a row's fingerprint),
    transactions, account (an account's id), accounts, month (YYYY-MM), invoice (a bill's or a receipt's key),
    invoices, subscription (a series' id), calendar (a day, YYYY-MM-DD, or "" for the days from today on), forecast
    (an account's id), insights, fx, todo (a kind of item to see to), system, notifications. A list screen opens with
    the link's query as its filters."""

    DOCUMENT = "document"  # /belgeler/:id: the document's sha256
    DOCUMENTS = "documents"  # /belgeler: the list, narrowed by the link's query (status)
    TRANSACTION = "transaction"  # a row of /islemler: its fingerprint
    TRANSACTIONS = "transactions"  # /islemler: the list, narrowed by the link's query (its filters)
    ACCOUNT = "account"  # /hesaplar/:id: the account's id
    ACCOUNTS = "accounts"  # /hesaplar
    MONTH = "month"  # /ay-sonu/:ay: the month, YYYY-MM
    INVOICE = "invoice"  # a bill or a receipt of /faturalar: its key, "<sha256>:<position>"
    INVOICES = "invoices"  # /faturalar, narrowed by the link's query (status)
    SUBSCRIPTION = "subscription"  # a series of /abonelikler: its id
    CALENDAR = "calendar"  # /takvim: the day, YYYY-MM-DD; "" for the days from today on
    FORECAST = "forecast"  # the forecast of /takvim: the account's id
    INSIGHTS = "insights"  # /degerlendirme
    FX = "fx"  # /doviz
    TODO = "todo"  # /yapilacaklar: the kind of item to see to
    SYSTEM = "system"  # /sistem
    NOTIFICATIONS = "notifications"  # /bildirimler


@dataclass(frozen=True, slots=True)
class Link:
    screen: Screen
    id: str = ""
    query: tuple[tuple[str, str], ...] = ()  # filters the list screen opens with, as its address's query


def finding_link(found: Mapping[str, object]) -> Link:
    """A finding of the interpretation leads to the rows it rests on when it names them (its filter: merchant,
    category, kind, provisional), else to the Değerlendirme screen."""
    query: list[tuple[str, str]] = []
    for key in ("merchant", "category", "kind"):
        if isinstance(value := found.get(key), str) and value:
            query.append((key, value))
    if found.get("provisional"):
        query.append(("certainty", "provisional"))
    return Link(Screen.TRANSACTIONS, query=tuple(query)) if query else Link(Screen.INSIGHTS)
