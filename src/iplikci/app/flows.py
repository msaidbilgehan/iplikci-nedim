"""Where the money went between the accounts (F07's Sankey and its table): from the payers of income into the
accounts, between the accounts, and out of them to the spending groups, people, savings, loans and cash, over a
window of days.

Only counted rows move money here, in TL. A transfer between own accounts goes from the account it left to the one
it reached: the ledger names the other side (Reason.pair); one whose other side no document shows goes to or comes
from "elsewhere", as does a card payment whose card or paying account no document shows. Money that went both ways
between two places is shown by its difference, so the flow has no loops: a Sankey cannot draw one.
"""

from collections import defaultdict
from dataclasses import dataclass
from datetime import date, timedelta
from decimal import Decimal

from ..analysis import Dataset
from ..domain.codes import CARD_TYPES, AccountType, FlowKind, TransactionKind
from ..domain.models import Transaction
from ..insights import complete_months, month_of
from .analysis import Analysis
from .links import Link, Screen

# What the API names from here: the use case, its records and the codes they carry.
__all__ = ["Edge", "FlowKind", "Flows", "Node", "TransactionKind", "flows"]

PAYERS = 5  # the income payers named apiece; the others are one "other income" node
OTHER_INCOME = "Diğer gelir"
OTHER_GROUP = "Diğer"
_PAYMENT_DAYS = (-1, 4)  # a card's side of a payment is booked this many days after the paying account's side
ZERO = Decimal(0)
CENT = Decimal("0.01")


@dataclass(frozen=True, slots=True)
class Node:
    id: str  # an account's id, else "<kind>" or "<kind>:<name>"
    kind: FlowKind
    name: str  # an income's payer or a spending group; "" for an account (the screens name it) and the others
    account: str  # an account node's account id; "" for the others


@dataclass(frozen=True, slots=True)
class Edge:
    source: str  # a node's id
    target: str
    amount: Decimal  # in TL, above zero: what went this way less what came back
    rows: int
    kinds: tuple[TransactionKind, ...]  # the kinds of the rows it adds up
    link: Link  # those rows on the Transactions screen


@dataclass(frozen=True, slots=True)
class Flows:
    start: date
    end: date
    nodes: list[Node]
    edges: list[Edge]  # the largest first
    note: str


@dataclass
class _Sum:
    amount: Decimal = ZERO  # from the first node of the key to the second; below zero the other way
    rows: int = 0
    kinds: set[TransactionKind] | None = None
    accounts: set[str] | None = None


def default_window(ds: Dataset, today: date) -> tuple[date, date]:
    """The newest complete month; before there is one, the current month up to today."""
    done = [m for m in complete_months(ds) if m < month_of(today)]
    if not done:
        return today.replace(day=1), today
    month = max(done)
    first = date(int(month[:4]), int(month[5:]), 1)
    nxt = date(first.year + first.month // 12, first.month % 12 + 1, 1)
    return first, nxt - timedelta(days=1)


def _card_side(ds: Dataset, t: Transaction) -> str | None:
    """The card a paying account's card payment reached: the card whose statement shows a payment of the same amount
    a few days later, else the one whose last digits it names, else the only credit card of its bank."""
    low, high = _PAYMENT_DAYS
    for other in ds.transactions:
        card = ds.accounts.get(other.account)
        if (
            card is not None
            and card.type in CARD_TYPES
            and other.kind is TransactionKind.CARD_PAYMENT
            and abs(other.amount + t.amount) <= CENT
            and low <= (other.date - t.date).days <= high
        ):
            return card.id
    source = ds.accounts.get(t.account)
    cards = [a for a in ds.accounts.values() if a.type == AccountType.CREDIT_CARD]
    named = [a for a in cards if a.number and a.number[-4:] in t.description]
    if len(named) == 1:
        return named[0].id
    same = [a for a in cards if source is not None and a.bank == source.bank]
    return same[0].id if len(same) == 1 else None


def _paid_from_an_account(ds: Dataset, t: Transaction) -> bool:
    """Whether a card's side of a payment has its paying account's side among the counted rows."""
    low, high = _PAYMENT_DAYS
    for other in ds.transactions:
        source = ds.accounts.get(other.account)
        if (
            source is not None
            and source.type not in CARD_TYPES
            and other.kind is TransactionKind.CARD_PAYMENT
            and abs(other.amount + t.amount) <= CENT
            and low <= (t.date - other.date).days <= high
        ):
            return True
    return False


def _outside(t: Transaction, payer: dict[str, str]) -> tuple[FlowKind, str] | None:
    """The node outside the accounts a row's money came from or went to; None for a move between accounts."""
    match t.kind:
        case TransactionKind.PURCHASE | TransactionKind.REFUND | TransactionKind.INTEREST_FEE:
            return FlowKind.SPENDING, t.group or OTHER_GROUP
        case TransactionKind.INCOME:
            return FlowKind.INCOME, payer.get(t.merchant or t.counterparty, OTHER_INCOME)
        case TransactionKind.P2P_TRANSFER:
            return FlowKind.PEOPLE, ""
        case TransactionKind.INVESTMENT:
            return FlowKind.SAVING, ""
        case TransactionKind.LOAN_PRINCIPAL:
            return FlowKind.LOAN, ""
        case TransactionKind.CASH_ADVANCE:
            return FlowKind.CASH, ""
        case _:
            return None


def _node_id(kind: FlowKind, name: str) -> str:
    return f"{kind.value}:{name}" if name else kind.value


def _place_filter(*ends: Node) -> list[tuple[str, str]]:
    """What narrows a band's rows to the place outside the accounts it reaches, beside its accounts and kinds: a
    spending group's name, an income's payer (as the rules name the merchant). The payers beyond the few named apiece
    have no filter of their own: their band leads to every income of its account."""
    for node in ends:
        if node.kind is FlowKind.SPENDING:
            return [("group", node.name)]
        if node.kind is FlowKind.INCOME and node.name != OTHER_INCOME:
            return [("merchant", node.name)]
    return []


def flows(a: Analysis, start: date, end: date) -> Flows:
    """The money's flow over the days from start to end."""
    ds = a.dataset
    rows = [t for t in ds.transactions if start <= t.date <= end]
    # Where every row of every document is: the other side of a transfer may be a foreign account's row the ledger
    # left out (moving foreign currency between own accounts has no TL value of its own).
    where = {t.fingerprint: t.account for s in ds.statements for t in s.transactions}
    where |= {line.txn.fingerprint: line.txn.account for line in ds.receipts}
    counted = {t.fingerprint for t in ds.transactions}
    income: defaultdict[str, Decimal] = defaultdict(Decimal)
    for t in rows:
        if t.kind is TransactionKind.INCOME and t.amount < 0:
            income[t.merchant or t.counterparty] -= t.amount
    payer = {name: name or OTHER_INCOME for name, _ in sorted(income.items(), key=lambda x: -x[1])[:PAYERS]}
    sums: defaultdict[tuple[str, str], _Sum] = defaultdict(_Sum)
    nodes: dict[str, Node] = {}

    def add(source: str, target: str, amount: Decimal, t: Transaction) -> None:
        """Money from source to target; kept under the pair's sorted key, so two ways net out."""
        key, sign = ((source, target), 1) if source <= target else ((target, source), -1)
        found = sums[key]
        found.amount += sign * amount
        found.rows += 1
        found.kinds = (found.kinds or set()) | {t.kind}
        found.accounts = (found.accounts or set()) | {t.account}

    def account_node(account: str) -> str:
        nodes.setdefault(account, Node(account, FlowKind.ACCOUNT, "", account))
        return account

    def other_node(kind: FlowKind, name: str) -> str:
        node = _node_id(kind, name)
        nodes.setdefault(node, Node(node, kind, name, ""))
        return node

    for t in rows:
        here = account_node(t.account)
        if (outside := _outside(t, payer)) is not None:
            node = other_node(*outside)
            add(here, node, t.amount, t)  # above zero out of the account, below zero into it
            continue
        if t.kind is TransactionKind.OWN_TRANSFER or t.kind is TransactionKind.TRANSFER_CANDIDATE:
            pair = t.reason.pair
            if t.amount < 0 and pair in counted:
                continue  # the side the money left adds it
            other = where.get(pair) if pair else None
            there = account_node(other) if other and other != t.account else other_node(FlowKind.ELSEWHERE, "")
            add(here, there, t.amount, t)
        elif t.kind is TransactionKind.CARD_PAYMENT:
            if t.account in ds.accounts and ds.accounts[t.account].type in CARD_TYPES:
                if not _paid_from_an_account(ds, t):
                    add(other_node(FlowKind.ELSEWHERE, ""), here, -t.amount, t)
                continue
            card = _card_side(ds, t)
            add(here, account_node(card) if card else other_node(FlowKind.ELSEWHERE, ""), t.amount, t)
        elif t.kind is TransactionKind.CARD_PAYMENT_NO_STATEMENT:
            # A payment to a card no statement shows: told by the card's receipt, or by the paying account's list.
            if t.account in ds.accounts and ds.accounts[t.account].type in CARD_TYPES:
                add(other_node(FlowKind.ELSEWHERE, ""), here, abs(t.amount), t)
            else:
                add(here, other_node(FlowKind.ELSEWHERE, ""), t.amount, t)
    edges: list[Edge] = []
    for (first, second), found in sums.items():
        if abs(found.amount) < CENT:
            continue
        source, target = (first, second) if found.amount > 0 else (second, first)
        kinds = tuple(sorted(found.kinds or ()))
        query: list[tuple[str, str]] = [("from", start.isoformat()), ("to", end.isoformat())]
        query += [("account", account) for account in sorted(found.accounts or ())]
        query += [("kind", kind.value) for kind in kinds]
        query += _place_filter(nodes[source], nodes[target])
        edges.append(
            Edge(source, target, abs(found.amount), found.rows, kinds, Link(Screen.TRANSACTIONS, query=tuple(query)))
        )
    edges.sort(key=lambda e: (-e.amount, e.source, e.target))
    used = {e.source for e in edges} | {e.target for e in edges}
    note = (
        "Sayılan satırlar, TL olarak. Kendi hesaplarınız arasındaki transferler gittiği hesaba bağlanır; karşı tarafı "
        'belgelerde olmayanlar "belgesi olmayan hesap"a gider. İki yönde geçen para farkıyla gösterilir. Döviz '
        "hesaplarınızın kendi aralarındaki transferleri TL karşılığı olmadığından sayılmaz."
    )
    return Flows(start, end, [n for n in nodes.values() if n.id in used], edges, note)
