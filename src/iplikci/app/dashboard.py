"""The dashboard (F06): the net worth, this month against the typical month, the payments due within a week, the open
alerts, the last seven months' closing, how fresh each account's documents are, and how much there is to see to.
Every card says what it shows in one Turkish sentence (the plain view's comment) and leads to its screen.

The net worth adds up the balances "Şu an" shows (app.now), so both screens tell the same estimate: provisional where
receipts and notices moved a balance after the document that printed it. What has no TL value (gold, whose price no
document prints; a balance in a currency no document gives a rate for) is listed apart, never guessed. The to-do
number and the alerts about documents come from the to-do list (app.todos): what the user took off it does not
count here either.
"""

from dataclasses import dataclass
from datetime import UTC, date, datetime, timedelta
from decimal import Decimal
from enum import StrEnum

from .. import month_end
from ..analysis import Dataset
from ..domain.codes import CARD_TYPES, AccountType, Certainty, DocumentKind, DocumentStatus, MonthStatus, PaymentKind
from ..domain.labels import TODO_KIND, format_amount
from ..domain.models import TRY
from ..domain.money import round_half_up
from ..feed.news import TO_PAY
from ..insights import month_of, months_in, pct, shift
from ..report import CLOSING_MONTHS
from ..storage import bridges, documents, events
from ..storage.db import Database
from ..upcoming import Due, add_months
from . import accounts, backup, now, outlook, system, todos
from .analysis import Analysis, account_labels, document_gaps
from .bridge import SILENCE
from .links import Link, Screen
from .mail import BRIDGE, IMAP
from .todos import Todo, TodoKind
from .workspace import Workspace

# What the API names from here: the use case, its records and the codes they carry.
__all__ = [
    "Alert",
    "AlertKind",
    "AlertLevel",
    "Closing",
    "Dashboard",
    "DataFreshness",
    "DocumentKind",
    "DueSoon",
    "Freshness",
    "InCurrency",
    "LastMonths",
    "MonthStatus",
    "NetWorth",
    "OpenAlerts",
    "Part",
    "ThisMonth",
    "TodoCount",
    "TodoKind",
    "TodoSummary",
    "dashboard",
]

DUE_DAYS = 7  # the payments due within a week, today the first day (F06)
CURRENCIES = ("EUR", "USD", now.GOLD)  # the net worth in other units besides TL (F12): gram gold last
COMPARABLE = 0.5  # the month so far is compared with the typical month once documents cover this share of its days
NEAR = Decimal("0.1")  # within this share of the typical month's same days, the month is "near" it
ZERO = Decimal(0)


class AlertKind(StrEnum):
    """What an open alert is about."""

    FINDING = "finding"  # an interpretation finding that asks for attention (insights)
    NEGATIVE = "negative"  # a bank account's forecast goes below zero within its 60 days
    UNREADABLE = "unreadable"  # documents that could not be read as they are
    FORMAT_ALARM = "format_alarm"  # a reader recognised documents and could not read them: a bank's format may change
    MAIL_STOPPED = "mail_stopped"  # the mailbox refused the login, and the e-mail intake stopped
    BRIDGE_SILENT = "bridge_silent"  # the browser extension was not seen for a day
    BACKUP_FAILED = "backup_failed"  # the newest backup, or its rehearsal, failed


class AlertLevel(StrEnum):
    WARNING = "warning"  # worth a look
    CRITICAL = "critical"  # something stopped working, or money runs short within a week


@dataclass(frozen=True, slots=True)
class Part:
    """An account's share of the net worth."""

    account: str
    value: Decimal  # in TL; below zero for a debt (a card's, an overdraft)
    certainty: Certainty


@dataclass(frozen=True, slots=True)
class InCurrency:
    """The net worth in another unit, at the newest rate the documents print."""

    currency: str  # EUR, USD, or GR: grams of gold
    amount: Decimal | None  # None without a rate
    rate: Decimal | None  # TL for one unit
    rate_day: date | None  # the day of the row that printed it
    note: str  # where the rate comes from, or why there is none


@dataclass(frozen=True, slots=True)
class NetWorth:
    total: Decimal  # the assets less the debts, of what has a TL value
    assets: Decimal
    debts: Decimal  # above zero
    certainty: Certainty  # provisional when a part is
    parts: list[Part]  # the largest first
    left_out: list[now.Unknown]  # the accounts without a TL value, and why
    currencies: list[InCurrency]
    note: str  # what it rests on
    say: str
    link: Link


@dataclass(frozen=True, slots=True)
class ThisMonth:
    pace: now.Pace
    say: str
    link: Link  # the month's page


@dataclass(frozen=True, slots=True)
class DueSoon:
    items: list[Due]  # the calendar's payments the user sees to, by day
    total: Decimal  # their sum
    end: date  # the last day looked at
    say: str
    link: Link


@dataclass(frozen=True, slots=True)
class Alert:
    kind: AlertKind
    level: AlertLevel
    title: str
    text: str  # what is wrong and what to do, in Turkish, with its numbers
    count: int  # how many things it stands for: documents, accounts
    account: str  # the account it concerns; "" for none
    link: Link


@dataclass(frozen=True, slots=True)
class OpenAlerts:
    items: list[Alert]  # the critical first
    say: str
    link: Link  # the notifications


@dataclass(frozen=True, slots=True)
class Closing:
    """A month's closing (F11)."""

    month: str
    status: MonthStatus
    summary: str  # the closing in one sentence (MonthEnd.summary)
    expense: Decimal
    income: Decimal | None  # None when no account list covers enough of the month
    left: Decimal | None
    provisional: int  # rows only receipts and notices show
    unmatched: int  # receipt and notice rows the statements do not show
    waiting: list[tuple[str, str]]  # (account, what closes its month) of the accounts that hold the month open
    link: Link


@dataclass(frozen=True, slots=True)
class LastMonths:
    months: list[Closing]  # the oldest first, the current month last
    say: str
    link: Link  # the oldest ended month still open, else the newest ended one


@dataclass(frozen=True, slots=True)
class Freshness:
    """How far an account's documents reach."""

    account: str
    kind: DocumentKind  # what its newest document is
    last: date  # the newest day its documents reach
    behind: int  # days from that to today
    expected: date | None  # when its next statement is due: a card's next cut, a brokerage statement's month end
    late: bool  # that day passed days ago and the statement did not come (five days for a card, ten otherwise)
    missing: tuple[str, ...]  # months inside its statements they cover only partly or not
    note: str
    link: Link


@dataclass(frozen=True, slots=True)
class DataFreshness:
    accounts: list[Freshness]  # the most behind first
    say: str
    link: Link  # the accounts


@dataclass(frozen=True, slots=True)
class TodoCount:
    kind: TodoKind
    count: int  # the to-do list's items of the kind
    link: Link


@dataclass(frozen=True, slots=True)
class TodoSummary:
    kinds: list[TodoCount]  # only the kinds with something to see to, in the list's order
    total: int
    say: str
    link: Link  # the to-do list


@dataclass(frozen=True, slots=True)
class Dashboard:
    today: date
    as_of: date  # the newest statement's end
    net_worth: NetWorth
    month: ThisMonth
    due: DueSoon
    alerts: OpenAlerts
    closing: LastMonths
    freshness: DataFreshness
    todo: TodoSummary


def _amount(value: Decimal, currency: str = TRY) -> str:
    unit = {TRY: "TL", now.GOLD: "gr"}.get(currency, currency)
    return f"{format_amount(value)} {unit}"


def _day(d: date) -> str:
    return f"{d:%d.%m.%Y}"


# --- the net worth ---------------------------------------------------------------------------------------------------


def _in_currency(ds: Dataset, total: Decimal, currency: str) -> InCurrency:
    if currency == now.GOLD:
        return InCurrency(currency, None, None, None, "gram altının TL fiyatı belgelerde yok")
    found = now.newest_rate(ds, currency)
    if found is None:
        return InCurrency(currency, None, None, None, f"belgelerde {currency} kuru yok")
    day, rate = found
    return InCurrency(currency, round_half_up(total / rate), rate, day, f"{_day(day)} belgesindeki kurla")


def _say_net_worth(total: Decimal, provisional: bool, parts: list[Part], left: int) -> str:
    if not parts:
        return "Henüz bakiyesi bilinen bir hesap yok; ekstre ve dökümler geldikçe burada görünür."
    said = f"Net varlığınız {_amount(total)}" if total >= 0 else f"Borçlarınız varlıklarınızdan {_amount(-total)} fazla"
    if provisional:
        said += " (geçici)"
    if left:
        said += f"; {left} hesabın TL değeri bilinmediği için toplama girmedi"
    return said + "."


def net_worth(a: Analysis, found: now.Now) -> NetWorth:
    """The balances and the cards' debts of "Şu an", added up in TL."""
    parts: list[Part] = []
    left: list[now.Unknown] = []
    for b in found.balances:
        if b.value is not None:
            parts.append(Part(b.account, b.value, b.certainty))
            continue
        why = "güncel altın fiyatı belgelerde yok" if b.currency == now.GOLD else f"belgelerde {b.currency} kuru yok"
        left.append(now.Unknown(b.account, f"{_amount(b.balance, b.currency)}; {why}"))
    parts += [Part(c.account, -c.debt, c.certainty) for c in found.cards if c.debt is not None]
    parts.sort(key=lambda p: -abs(p.value))
    assets = sum((p.value for p in parts if p.value > 0), ZERO)
    debts = -sum((p.value for p in parts if p.value < 0), ZERO)
    total = assets - debts
    provisional = any(p.certainty == Certainty.PROVISIONAL for p in parts)
    note = (
        "Hesapların son belgelerindeki bakiyeler, sonraki dekont ve bildirimlerle; kart borçları son ekstreden, "
        "kesimden sonraki ödemeler düşülerek. Değeri bilinmeyenler toplama girmedi."
    )
    left_out = left + found.unknown
    return NetWorth(
        total=total,
        assets=assets,
        debts=debts,
        certainty=Certainty.PROVISIONAL if provisional else Certainty.CONFIRMED,
        parts=parts,
        left_out=left_out,
        currencies=[_in_currency(a.dataset, total, c) for c in CURRENCIES],
        note=note,
        say=_say_net_worth(total, provisional, parts, len(left_out)),
        link=Link(Screen.ACCOUNTS),
    )


# --- this month ------------------------------------------------------------------------------------------------------


def _say_month(p: now.Pace) -> str:
    said = f"Gelen belgelere göre bu ay {_amount(p.spent)} harcandı"
    if p.provisional:
        said += f" ({_amount(p.provisional)} geçici)"
    if p.by_day is None:
        return said + "; tipik ayla karşılaştırmak için en az 3 tam ay gerekiyor."
    if p.covered < COMPARABLE:  # the documents of the month mostly still to come: a comparison would mislead
        covered = pct(p.covered)
        return said + f"; bugüne kadarki günlerin yalnızca {covered} belgelerle kapsandı, karşılaştırmak için erken."
    if not p.by_day:
        return said + "; tam aylarda bu günlere kadar harcama olmamıştı."
    change = p.spent / p.by_day - 1
    if abs(change) < NEAR:
        return said + f"; tipik ayın aynı günlerine ({_amount(p.by_day)}) yakın."
    word = "fazla" if change > 0 else "az"
    return said + f"; tipik ayın aynı günlerinden ({_amount(p.by_day)}) %{round(abs(change) * 100)} {word}."


def this_month(pace: now.Pace) -> ThisMonth:
    return ThisMonth(pace, _say_month(pace), Link(Screen.MONTH, pace.month))


# --- the payments due soon -------------------------------------------------------------------------------------------


def _say_due(items: list[Due], total: Decimal, today: date) -> str:
    if not items:
        return f"Önümüzdeki {DUE_DAYS} günde ödenecek bir şey görünmüyor."
    first = items[0]
    when = {today: "bugün", today + timedelta(days=1): "yarın"}.get(first.day, _day(first.day))
    # A regular or periodic payment's amount is its last one's: an estimate (the calendar's basis).
    estimate = " (tahmini)" if any(i.kind in (PaymentKind.REGULAR, PaymentKind.PERIODIC) for i in items) else ""
    return (
        f"Önümüzdeki {DUE_DAYS} günde {len(items)} ödeme var, toplam {_amount(total)}{estimate}; ilki {when}: "
        f"{first.title}."
    )


def due_soon(a: Analysis, today: date) -> DueSoon:
    """The calendar's payments within a week that the user sees to, as the feed's "payment.due_soon" names them
    (feed.news.due_soon): a card's due date, a non-bank bill, a loan's installment, and a regular or periodic payment
    made from an account. One a card pays comes with the card's statement."""
    items, end = now.upcoming(a, today, DUE_DAYS)
    cards = {account.id for account in a.dataset.accounts.values() if account.type in CARD_TYPES}
    by_card = (PaymentKind.REGULAR, PaymentKind.PERIODIC)
    to_pay = [i for i in items if i.kind in TO_PAY and not (i.kind in by_card and i.account in cards)]
    total = sum((i.amount for i in to_pay), ZERO)
    return DueSoon(to_pay, total, end, _say_due(to_pay, total, today), Link(Screen.CALENDAR))


# --- the alerts ------------------------------------------------------------------------------------------------------


def _finding_link(found: dict[str, object]) -> Link:
    """A finding leads to the rows it rests on when it names them (its filter), else to the interpretation."""
    query: list[tuple[str, str]] = []
    for key in ("merchant", "category", "kind"):
        if isinstance(value := found.get(key), str) and value:
            query.append((key, value))
    if found.get("provisional"):
        query.append(("certainty", Certainty.PROVISIONAL.value))
    return Link(Screen.TRANSACTIONS, query=tuple(query)) if query else Link(Screen.INSIGHTS)


def _negatives(a: Analysis, today: date) -> list[Alert]:
    labels = account_labels(a)
    found: list[Alert] = []
    for account in outlook.cash_flow(a, today).forecast.accounts:
        if account.negative is None:
            continue
        day, balance = account.negative
        days = (day - today).days
        level = AlertLevel.CRITICAL if days < DUE_DAYS else AlertLevel.WARNING
        when = {0: "bugün", 1: "yarın"}.get(days, f"{days} gün sonra")
        # As the notification of "balance.forecast_negative" says it in full (notify.content).
        name = labels.get(account.account, account.account)
        text = f"{name}: öngörüye göre bakiye {_day(day)} günü ({when}) {_amount(balance)} olacak."
        link = Link(Screen.FORECAST, account.account)
        found.append(Alert(AlertKind.NEGATIVE, level, "Hesap eksiye düşecek", text, 1, account.account, link))
    return found


def _documents(db: Database, listed: list[Todo]) -> list[Alert]:
    """The documents that could not be read and the readers' open format alarms, as the to-do list has them."""
    shas = {d.sha256 for d in documents.every(db, [DocumentStatus.UNREADABLE])}
    unreadable = [t for t in listed if t.kind is TodoKind.UNPROCESSED_DOCUMENT and t.target in shas]
    found: list[Alert] = []
    if unreadable:
        link = Link(Screen.DOCUMENTS, query=(("status", DocumentStatus.UNREADABLE.value),))
        text = (
            f"{len(unreadable)} belge olduğu gibi okunamadı: şifreli ya da bozuk olabilir. Belgeler ekranında "
            "nedenleri var."
        )
        title = "Okunamayan belgeler"
        found.append(Alert(AlertKind.UNREADABLE, AlertLevel.WARNING, title, text, len(unreadable), "", link))
    for t in listed:
        if t.kind is TodoKind.FORMAT_ALARM:
            text = f"{t.title}: {t.detail} Okuyucu güncellenince belgeler kendiliğinden yeniden okunur."
            title, link = "Okuyucu biçim alarmı", t.link or Link(Screen.SYSTEM)
            found.append(Alert(AlertKind.FORMAT_ALARM, AlertLevel.WARNING, title, text, t.count, "", link))
    return found


def _mail(ws: Workspace, db: Database, at: datetime) -> list[Alert]:
    health = system.mail_health(ws, db)
    if health.connector == IMAP and health.configured and health.stopped:
        text = "E-posta sunucusu girişi reddetti ve alım durdu; e-posta bağlantısını yeniden kurun."
        link = Link(Screen.SYSTEM)
        return [Alert(AlertKind.MAIL_STOPPED, AlertLevel.CRITICAL, "E-posta alımı durdu", text, 1, "", link)]
    active = [b for b in bridges.every(db) if b.active]
    quiet = [b for b in active if at - datetime.fromisoformat(b.last_seen) >= SILENCE]
    if health.connector == BRIDGE and quiet and len(quiet) == len(active):  # one extension still delivering is enough
        days = min((at - datetime.fromisoformat(b.last_seen)).days for b in quiet)
        text = f"Tarayıcı eklentisi {days} gündür görünmedi; yeni e-postalar tarayıcı açılınca gelir."
        link = Link(Screen.SYSTEM)
        return [Alert(AlertKind.BRIDGE_SILENT, AlertLevel.WARNING, "Eklenti görünmüyor", text, len(quiet), "", link)]
    return []


def _backup(ws: Workspace, db: Database) -> list[Alert]:
    health = backup.health(ws)
    found: list[Alert] = []
    failed = [e for e in events.entries(db, backup.FAILED) if e.detail.get("stage") == "backup"]
    last = datetime.fromisoformat(health.last) if health.last else None
    if failed and (last is None or datetime.fromisoformat(failed[-1].at) > last):
        text = "Son yedek alınamadı; servis yeniden deneyecek. Sistem ekranında ayrıntısı var."
        link = Link(Screen.SYSTEM)
        found.append(Alert(AlertKind.BACKUP_FAILED, AlertLevel.CRITICAL, "Yedek alınamadı", text, 1, "", link))
    if health.rehearsal_ok is False:
        text = "Son yedeğin geri yükleme provası geçmedi; yedekler denetlenmeli. Sistem ekranında ayrıntısı var."
        title, link = "Geri yükleme provası geçmedi", Link(Screen.SYSTEM)
        found.append(Alert(AlertKind.BACKUP_FAILED, AlertLevel.CRITICAL, title, text, 1, "", link))
    return found


def _say_alerts(found: list[Alert]) -> str:
    if not found:
        return "Açık uyarı yok."
    if len(found) == 1:
        return f"Bir açık uyarı var: {found[0].title}."
    critical = sum(alert.level is AlertLevel.CRITICAL for alert in found)
    said = f"{len(found)} açık uyarı var" + (f", {critical} tanesi kritik" if critical else "")
    return said + f"; ilki: {found[0].title}."


def alerts(ws: Workspace, a: Analysis, today: date, listed: list[Todo], at: datetime | None = None) -> OpenAlerts:
    """What asks for attention now: the interpretation's findings that do, the bank accounts whose forecast goes below
    zero, the to-do list's unreadable documents and format alarms, a stopped e-mail intake or a silent browser
    extension, a failed backup or rehearsal. The critical first."""
    at = at or datetime.now(UTC)
    found = [
        Alert(AlertKind.FINDING, AlertLevel.WARNING, f.title, f.text, 1, "", _finding_link(f.filter))
        for f in a.insights.findings
        if f.tone == "dikkat"
    ]
    found += _negatives(a, today)
    with ws.db() as db:
        found += _documents(db, listed) + _mail(ws, db, at) + _backup(ws, db)
    found.sort(key=lambda alert: alert.level != AlertLevel.CRITICAL)
    return OpenAlerts(found, _say_alerts(found), Link(Screen.NOTIFICATIONS))


# --- the closing and the documents' freshness ------------------------------------------------------------------------

# What holds an ended month open, as the closing card says it after the months' names.
_OPEN = (
    (MonthStatus.MISSING, "belge eksik"),
    (MonthStatus.CHECK, "kontrol gerekiyor"),
    (MonthStatus.WAITING, "ekstre bekleniyor"),
)


def _say_closing(months: list[Closing]) -> str:
    ended = [c for c in months if c.status is not MonthStatus.RUNNING]
    if not ended:
        return "Henüz biten bir ayın belgeleri yok."
    said: list[str] = []
    for status, words in _OPEN:
        held = [c.month for c in ended if c.status is status]
        if held:
            said.append(f"{months_in(held)} {words}")
    if not said:
        return f"Biten son {len(ended)} ayın hepsi kapandı."
    closed = sum(c.status is MonthStatus.CLOSED for c in ended)
    return "; ".join(said) + (f"; diğer {closed} ay kapandı." if closed else ".")


def closing(a: Analysis, today: date) -> LastMonths:
    """The last seven months' closing, as the report's closing card shows it: the current month and the six before it
    with documents."""
    months = month_end.report_months(a.dataset, today)[-CLOSING_MONTHS:]
    found: list[Closing] = []
    for me in month_end.build(a.dataset, a.insights, today, months=months):
        found.append(
            Closing(
                month=me.month,
                status=me.status,
                summary=me.summary,
                expense=me.totals.expense,
                income=me.totals.income,
                left=me.totals.left,
                provisional=len(me.provisional),
                unmatched=len(me.unmatched),
                waiting=[(ac.account.id, ac.waiting_for) for ac in me.open],
                link=Link(Screen.MONTH, me.month),
            )
        )
    ended = [c for c in found if c.status is not MonthStatus.RUNNING]
    held = [c for c in ended if c.status is not MonthStatus.CLOSED]
    first = held[0] if held else ended[-1] if ended else None
    return LastMonths(found, _say_closing(found), first.link if first else Link(Screen.MONTH, month_of(today)))


def _expected(account: AccountType, cut: date) -> tuple[date, int] | None:
    """When the statement after one cut on a day is due, and how many days later it is late (month_end.LATE_DAYS):
    a card's comes a month after its cut, a brokerage account's after the next month ends. A list is downloaded or
    mailed when it is (K21): nothing is due."""
    if account in CARD_TYPES:
        return add_months(cut, 1), month_end.LATE_DAYS
    if account == AccountType.BROKERAGE:
        return month_end.last_day(shift(month_of(cut), 1)), 2 * month_end.LATE_DAYS
    return None


def _say_freshness(found: list[Freshness], labels: dict[str, str]) -> str:
    if not found:
        return "Henüz belgesi gelen bir hesap yok."
    late = [labels.get(f.account, f.account) for f in found if f.late]
    if late:
        return f"{len(late)} hesabın beklenen ekstresi gecikti: {', '.join(late)}."
    behind = found[0]
    name = labels.get(behind.account, behind.account)
    return f"Geciken ekstre yok; en geride kalan {name}, belgeleri {_day(behind.last)} tarihine kadar."


def freshness(ws: Workspace, a: Analysis, today: date) -> DataFreshness:
    """How far each open account's documents reach, the most behind first: its newest document, the next statement
    due and whether it is late, and the months its statements skip."""
    ds = a.dataset
    seen = accounts.last_seen(ds)
    gone = accounts.closed(seen)
    holes = {gap.id: gap.months for gap in document_gaps(ds, today)}
    found: list[Freshness] = []
    with ws.db() as db:
        for account, last in seen.items():
            if account in gone or account not in ds.accounts:
                continue
            statements = [s for s in ds.statements if s.account == account]
            newest = max(statements, key=lambda s: s.cut_date) if statements else None
            evidence = [line.txn for line in ds.receipts if line.txn.account == account]
            if newest is not None and newest.cut_date >= max((t.date for t in evidence), default=date.min):
                kind = DocumentKind.ACCOUNT_STATEMENT if newest.is_account else DocumentKind.CARD_STATEMENT
            else:
                told = max(evidence, key=lambda t: t.date)
                doc = documents.get(db, told.document) if told.document else None
                kind = doc.kind if doc is not None and doc.kind is not None else DocumentKind.RECEIPT
            due = _expected(ds.accounts[account].type, newest.cut_date) if newest is not None else None
            late = due is not None and (today - due[0]).days > due[1]
            if newest is None:
                note = "yalnızca dekont ve banka bildirimlerinden biliniyor"
            elif due is None:
                note = f"son döküm {_day(newest.cut_date)}"
            else:
                note = f"son ekstre {_day(newest.cut_date)}; sonraki ~{_day(due[0])}" + (" (gecikti)" if late else "")
            found.append(
                Freshness(
                    account=account,
                    kind=kind,
                    last=last,
                    behind=(today - last).days,
                    expected=due[0] if due else None,
                    late=late,
                    missing=holes.get(account, ()),
                    note=note,
                    link=Link(Screen.ACCOUNT, account),
                )
            )
    found.sort(key=lambda f: (-f.behind, f.account))
    return DataFreshness(found, _say_freshness(found, account_labels(a)), Link(Screen.ACCOUNTS))


def _say_todo(kinds: list[TodoCount], total: int) -> str:
    if not total:
        return "Yapılacak bir şey yok."
    return f"{total} iş bekliyor: " + ", ".join(f"{TODO_KIND[k.kind]} ({k.count})" for k in kinds) + "."


def todo(ws: Workspace, a: Analysis, today: date) -> TodoSummary:
    """How many items of each kind the to-do list holds (app.todos.counts), each leading to the list."""
    counts = todos.counts(ws, a, today)
    kinds = [TodoCount(kind, n, Link(Screen.TODO, kind.value)) for kind, n in counts.items() if n]
    total = sum(counts.values())
    return TodoSummary(kinds, total, _say_todo(kinds, total), Link(Screen.TODO))


def dashboard(ws: Workspace, a: Analysis, today: date, at: datetime | None = None) -> Dashboard:
    found = now.now(a, today)
    return Dashboard(
        today=today,
        as_of=a.insights.timeline.as_of,
        net_worth=net_worth(a, found),
        month=this_month(found.pace),
        due=due_soon(a, today),
        alerts=alerts(ws, a, today, todos.items(ws, a, today), at),
        closing=closing(a, today),
        freshness=freshness(ws, a, today),
        todo=todo(ws, a, today),
    )
