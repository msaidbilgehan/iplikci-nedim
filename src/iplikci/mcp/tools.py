"""The MCP tools (ADR-0011, architecture §17): what each one does, its arguments and hints, on the same use cases the
screens read (`app`). A Session holds what a conversation shares: the workspace, the analysis, the plans shown and not
yet applied. The protocol is the SDK's (`server`); this module knows nothing of it.

What a tool returns becomes part of the conversation with the model that called it. Amounts are exact in the ledger
and numbers in the answers; a tool that changes something shows its plan first and applies it when asked again with
the plan's id.
"""

import json
import logging
import re
from calendar import monthrange
from collections import Counter, defaultdict
from collections.abc import Callable
from dataclasses import dataclass
from datetime import date, datetime, timedelta
from decimal import Decimal
from typing import Any, cast

from .. import month_end
from ..app import accounts, closing, intake, invoices, notify, outlook
from ..app import mail as email
from ..app import rules as category_rules
from ..app.analysis import Current, document_gaps, summary
from ..app.uploads import inbox_files
from ..app.workspace import Busy, SchemaMismatch, StalePlan, Workspace
from ..categorize import Categorizer
from ..domain.codes import Actor, EventKind, InvoiceStatus, Necessity, SeriesPeriod, TransactionKind
from ..domain.labels import (
    CHANNEL,
    DETAIL_LEVEL,
    EVENT_KIND,
    INVOICE_KIND,
    INVOICE_STATUS,
    PAYMENT_KIND,
    SERIES_PERIOD,
    SERIES_STATUS,
)
from ..domain.models import Transaction
from ..domain.money import round_half_up, to_decimal
from ..domain.text import fold
from ..insights import HABIT_STATUS, STATUS, receipt_amount
from ..upcoming import HORIZON

ZERO = Decimal(0)
_log = logging.getLogger(__name__)


def _plain(value: object) -> object:
    """What JSON cannot hold, as the model reads it: an exact amount as a number, anything else (a date) as text."""
    if isinstance(value, Decimal):
        return float(value)
    return str(value)


class ToolError(Exception):
    """The tool could not do what was asked; the message goes back to the model."""


Args = dict[str, Any]  # a tool's arguments, as its schema checked them
Json = dict[str, Any]  # what a tool returns: JSON the model reads


@dataclass(frozen=True)
class Tool:
    """A tool as the server lists it: its hints say what it does to this computer (ADR-0011)."""

    name: str
    title: str
    description: str
    schema: Json
    run: Callable[["Session", Args], Json]
    read_only: bool = True
    destructive: bool = False  # what it changes it may take away (files moved to the system's Trash)
    open_world: bool = False  # reaches outside this computer (the mail server)
    # Whether a call with these arguments changes something; None: every call of a tool that is not read-only.
    writes: Callable[[Args], bool] | None = None

    @property
    def idempotent(self) -> bool:
        """Asking again changes nothing more: true of every tool that only reads."""
        return self.read_only

    def changes(self, args: Args) -> bool:
        """Whether this call would change something: refused while the service is down (Session.offline)."""
        return self.writes(args) if self.writes is not None else not self.read_only


@dataclass(frozen=True, slots=True)
class Outcome:
    """A tool's answer: its JSON text, and whether it is an error the model reads (a refusal, a bad argument)."""

    text: str
    error: bool = False


# What a tool that changes something says while the service is down: the bridge then reads the database alone.
OFFLINE = (
    "İplikçi Nedim'in servisi çalışmıyor: servis kapalıyken yalnızca okuyan araçlar çalışır ve bu araç bir şeyi "
    "değiştirir. İplikçi Nedim uygulamasını açın (servis kendiliğinden başlar), sonra yeniden deneyin."
)
CANNOT_READ = "İplikçi Nedim'in servisi çalışmıyor ve veritabanı okunamadı"


class Session:
    """What the tools of one server share: the workspace, its analysis and the plans shown but not applied. offline:
    the service is down and the database is only read (ADR-0011); a call that would change something is refused."""

    def __init__(self, ws: Workspace, current: Current | None = None, offline: bool = False) -> None:
        self.ws = ws
        self.current = current or Current(ws, write=False)
        self.plans: dict[str, intake.Plan] = {}
        self.today: Callable[[], date] = date.today  # the day the calendar and the forecast start from
        self.offline = offline

    def call(self, name: str, arguments: Args | None) -> Outcome:
        """Run the tool called name: its answer as JSON text, or the reason it could not, for the model."""
        tool = TOOLS_BY_NAME.get(name)
        if tool is None:
            return Outcome(f"bilinmeyen araç: {name}", error=True)
        try:
            args = _check(tool.schema, arguments or {})
            if self.offline and tool.changes(args):
                return Outcome(OFFLINE, error=True)
            value = tool.run(self, args)
        except (ToolError, Busy, StalePlan, ValueError, FileNotFoundError, email.MailError) as exc:
            return Outcome(str(exc), error=True)
        except SchemaMismatch as exc:
            return Outcome(
                f"{CANNOT_READ}: {exc}. İplikçi Nedim uygulamasını açın, servis veritabanını hazırlar.", True
            )
        except Exception as exc:  # told to the model, the details logged; the server keeps running  # noqa: BLE001
            _log.exception("tool %s failed", name)
            return Outcome(f"beklenmeyen hata: {type(exc).__name__}: {exc}", error=True)
        return Outcome(json.dumps(value, ensure_ascii=False, default=_plain))

    def keep(self, plan: intake.Plan) -> None:
        self.plans[plan.id] = plan
        while len(self.plans) > 8:
            self.plans.pop(next(iter(self.plans)))


# --- argument checks (the subset of JSON Schema the tools use) --------------------------------------

_TYPES: dict[str, Callable[[Any], bool]] = {
    "string": lambda v: isinstance(v, str),
    "integer": lambda v: isinstance(v, int) and not isinstance(v, bool),
    "number": lambda v: isinstance(v, (int, float)) and not isinstance(v, bool),
    "boolean": lambda v: isinstance(v, bool),
    "array": lambda v: isinstance(v, list),
}


def _check_value(name: str, spec: Json, value: Any) -> None:
    if not _TYPES[spec["type"]](value):
        raise ToolError(f"'{name}' {spec['type']} olmalı")
    if "enum" in spec and value not in spec["enum"]:
        raise ToolError(f"'{name}' şunlardan biri olmalı: {', '.join(map(str, spec['enum']))}")
    if "pattern" in spec and not re.fullmatch(spec["pattern"], value):
        raise ToolError(f"'{name}' biçimi uygun değil ({spec.get('description', spec['pattern'])})")
    if "minimum" in spec and value < spec["minimum"] or "maximum" in spec and value > spec["maximum"]:
        raise ToolError(f"'{name}' {spec.get('minimum')}–{spec.get('maximum')} arasında olmalı")
    if spec["type"] == "array":
        if len(value) < spec.get("minItems", 0):
            raise ToolError(f"'{name}' en az {spec['minItems']} öğe içermeli")
        for item in value:
            _check_value(f"{name}[]", spec["items"], item)


def _check(schema: Json, args: object) -> Args:
    if not isinstance(args, dict):
        raise ToolError("arguments bir nesne olmalı")
    given = cast(Args, args)
    props: Json = schema.get("properties", {})
    unknown = sorted(set(given) - set(props))
    if unknown:
        raise ToolError(f"bilinmeyen parametre: {', '.join(unknown)}")
    missing = [n for n in schema.get("required", []) if n not in given]
    if missing:
        raise ToolError(f"gerekli parametre eksik: {', '.join(missing)}")
    for name, value in given.items():
        _check_value(name, props[name], value)
    return given


# --- tools ------------------------------------------------------------------------------------------


def _status(s: Session, args: Args) -> Json:
    a = s.current.get()
    tl_ = a.insights.timeline
    waiting = inbox_files(s.ws)
    html = s.ws.exports / "gider_raporu.html"
    updated = datetime.fromtimestamp(html.stat().st_mtime).isoformat(timespec="minutes") if html.exists() else None
    return {
        "workspace": {
            "home": str(s.ws.home),
            "vault": str(s.ws.layout.vault),
            "inbox": str(s.ws.inbox),
            "exports": str(s.ws.exports),
            "rules": str(s.ws.rules),
        },
        "read": summary(a),
        "inbox": {"waiting": len(waiting), "files": [str(p.relative_to(s.ws.inbox)) for p in waiting[:50]]},
        "completeMonths": {"window": tl_.window, "lastComplete": tl_.last_complete, "newestStatement": tl_.as_of},
        "documentGaps": [
            {
                "account": g.account,
                "kind": g.kind,
                "lastStatement": g.last,
                "daysSinceLastStatement": g.behind,
                "missingMonths": list(g.months),
            }
            for g in document_gaps(a.dataset)
        ],
        "report": {"html": str(html), "updated": updated},
        "email": email.status(s.ws),
    }


def _plan_view(s: Session, p: intake.Plan, empty: str = "Alınacak belge yok.") -> Json:
    s.keep(p)
    changes = p.changes
    return {
        "plan_id": p.id,
        "changes": len(changes),
        "byAction": dict(Counter(intake.ACTION_LABELS.get(c.action, c.action) for c in changes)),
        "items": [intake.describe(c, s.ws) for c in changes[:200]],
        "note": "Hiçbir dosyaya dokunulmadı. Kullanıcı onaylarsa apply_inbox(plan_id) çağırın." if changes else empty,
    }


def _import(s: Session, args: Args) -> Json:
    return _plan_view(s, intake.plan_paths(s.ws, args["paths"]), "Bu yollarda yeni belge yok.")


def _fetch_email(s: Session, args: Args) -> Json:
    got = email.fetch(s.ws, wait=30)
    out = {
        "message": got.message,
        "emails": got.scanned,
        "stored": got.stored,
        "documents": got.documents,
        "known": got.known,
        "unverifiedSkipped": got.unverified,
        "businessSkipped": got.business,
        "tooLargeSkipped": got.too_large,
        "folder": got.folder,
        "more": got.more,
    }
    if got.more:
        out["note"] = "Daha fazla e-posta var: fetch_email'i yeniden çağırın."
    if got.stored:
        s.current.refresh(write=False)
    return out


def _plan(s: Session, args: Args) -> Json:
    return _plan_view(s, intake.plan_inbox(s.ws), "Gelen klasöründe alınacak belge yok.")


def _apply(s: Session, args: Args) -> Json:
    p = s.plans.pop(args["plan_id"], None)
    if p is None:
        raise ToolError("bu plan yok ya da eskidi: önce plan_inbox ya da import_documents ile yeni plan alın")
    s.plans.clear()  # applying one plan makes the others stale
    done = intake.apply(s.ws, p, Actor.MCP)
    a = s.current.refresh(write=True)
    return {
        "done": [intake.describe(c, s.ws) for c in done.items if c.changes_something][:200],
        "counts": {intake.ACTION_LABELS.get(k, k): v for k, v in done.counts.items()},
        "trash": str(done.trash) if done.trash else None,
        "report": summary(a),
        "outputs": a.outputs and {k: str(v) for k, v in vars(a.outputs).items()},
    }


def _build(s: Session, args: Args) -> Json:
    a = s.current.refresh(write=True)
    return {"report": summary(a), "outputs": {k: str(v) for k, v in vars(a.outputs).items()}}


def _insights(s: Session, args: Args) -> Json:
    a = s.current.get()
    ins, p = a.insights, a.payload["insights"]
    return {
        "window": ins.timeline.window,
        "lastComplete": ins.timeline.last_complete,
        "asOf": ins.timeline.as_of,
        "findings": [{"tone": f.tone, "title": f.title, "text": f.text} for f in ins.findings],
        "steps": [{"title": st.title, "text": st.text, "monthly": round_half_up(st.monthly)} for st in ins.steps],
        "budget": p["budget"],
        "flow": p["flow"],
        "trend": p["trend"],
        "holdings": p["holdings"],
        "income": p["income"],
        "note": "flow: pencere aylarının aylık ortalamaları; budget: bugünkü tipik ay ve öneri.",
    }


def _bound(value: str | None, end: bool) -> date | None:
    if not value:
        return None
    if len(value) == 7:
        y, m = int(value[:4]), int(value[5:])
        return date(y, m, monthrange(y, m)[1] if end else 1)
    return date.fromisoformat(value)


def _transactions(s: Session, args: Args) -> Json:
    a = s.current.get()
    ds = a.dataset
    lo, hi = _bound(args.get("from"), False), _bound(args.get("to"), True)
    text = fold(args.get("text", ""))
    kinds = set(args.get("kinds") or _KINDS)
    picked: list[Transaction] = []
    for t in ds.transactions:
        if lo and t.date < lo or hi and t.date > hi or t.kind not in kinds:
            continue
        if text and text not in fold(f"{t.merchant} {t.description} {t.counterparty}"):
            continue
        if "category" in args and fold(t.category) != fold(args["category"]):
            continue
        if "group" in args and fold(t.group) != fold(args["group"]):
            continue
        if "account" in args and fold(args["account"]) not in fold(ds.accounts[t.account].label):
            continue
        if "necessity" in args and (t.necessity or Necessity.UNKNOWN) != args["necessity"]:
            continue
        if "min_amount" in args and t.amount < to_decimal(args["min_amount"]):
            continue
        if "max_amount" in args and t.amount > to_decimal(args["max_amount"]):
            continue
        picked.append(t)
    limit = args.get("limit", 50)
    out: Json = {
        "count": len(picked),
        "total": round_half_up(sum((t.amount for t in picked), ZERO)),
        "out": round_half_up(sum((t.amount for t in picked if t.amount > 0), ZERO)),
        "in": round_half_up(sum((t.amount for t in picked if t.amount < 0), ZERO)),
    }
    if args.get("group_by"):
        keys: dict[str, Callable[[Transaction], str]] = {
            "month": lambda t: f"{t.date:%Y-%m}",
            "category": lambda t: t.category,
            "group": lambda t: t.group,
            "merchant": lambda t: t.merchant,
            "kind": lambda t: t.kind,
            "necessity": lambda t: t.necessity or Necessity.UNKNOWN,
            "account": lambda t: ds.accounts[t.account].label,
        }
        sums: dict[str, Decimal] = defaultdict(Decimal)
        counts: Counter[str] = Counter()
        for t in picked:
            key = keys[args["group_by"]](t)
            sums[key] += t.amount
            counts[key] += 1
        found = sorted(sums, key=(lambda k: k) if args["group_by"] == "month" else (lambda k: -abs(sums[k])))
        rows: list[Json] = [{"key": k, "total": round_half_up(sums[k]), "count": counts[k]} for k in found]
        out["groups"], out["groupsShown"] = rows[:limit], min(limit, len(rows))
        return out
    order = args.get("sort", "date_desc")
    picked.sort(key=lambda t: t.amount if order.startswith("amount") else t.date, reverse=order.endswith("desc"))
    rows: list[Json] = []
    for t in picked[:limit]:
        row: Json = {
            "date": t.date,
            "merchant": t.merchant,
            "description": t.description,
            "amount": t.amount,
            "kind": t.kind,
            "category": t.category,
            "group": t.group,
            "necessity": t.necessity,
            "account": ds.accounts[t.account].label,
            "fingerprint": t.fingerprint,
        }
        row |= {
            k: v
            for k, v in (
                ("installment", t.installment),
                ("original", t.original),
                ("counterparty", t.counterparty),
                ("provisional", t.provisional),
                ("note", t.note),
                ("tags", list(t.tags)),
            )
            if v
        }
        rows.append(row)
    out["rows"], out["rowsShown"] = rows, len(rows)
    return out


def _regular(s: Session, args: Args) -> Json:
    a = s.current.get()
    ds, ins = a.dataset, a.insights
    shown = [x["show"] for x in a.payload["insights"]["series"]]
    rows: list[Json] = []
    for sr, show in zip(ins.series, shown):
        if args.get("status") and sr.status != args["status"] or not args.get("status") and not show:
            continue
        change = sr.price_change()
        rows.append(
            {
                "merchant": sr.merchant,
                "category": sr.last.category,
                "necessity": sr.last.necessity,
                "kind": sr.last.kind,
                "status": sr.status,
                "statusLabel": STATUS[sr.status],
                "monthly": round_half_up(sr.monthly),
                "lastAmount": round_half_up(abs(sr.last.amount)),
                "last": sr.last.date,
                "first": sr.payments[0].date,
                "next": sr.expected,
                "payments": len(sr.payments),
                "dayOfMonth": sr.day,
                "priceChange": change
                and {"from": round_half_up(change[0]), "to": round_half_up(change[1]), "since": change[2]},
                "accounts": sorted({ds.accounts[t.account].label for t in sr.payments}),
            }
        )
    income = [
        {"payer": sr.merchant, "monthly": round_half_up(sr.monthly), "last": sr.last.date, "status": STATUS[sr.status]}
        for sr in ins.income
        if sr.running
    ]
    return {
        "series": rows,
        "income": income,
        "note": "Varsayılan liste raporla aynı: sürenler ve pencere içinde bitenler. status ile süzülebilir.",
    }


def _series_view(v: outlook.SeriesView, labels: dict[str, str]) -> Json:
    change = v.price_change
    return {
        "id": v.id,
        "payee": v.payee,
        "period": v.period,
        "periodLabel": SERIES_PERIOD[v.period],
        "status": v.status,
        "statusLabel": SERIES_STATUS[v.status],
        "note": v.note or None,
        "category": v.category,
        "necessity": v.necessity,
        "kind": v.kind,
        "account": labels.get(v.account, v.account),
        "amount": round_half_up(v.amount),
        "lastDay": v.last_day,
        "lastAmount": round_half_up(v.last_amount),
        "nextDay": v.next_day,
        "priceChange": change
        and {"from": round_half_up(change.before), "to": round_half_up(change.after), "since": change.since},
        "payments": len(v.rows),
        "provisional": sum(r.certainty == "provisional" for r in v.rows),
        "documents": sorted({r.document for r in v.rows if r.document}),
        "lastFingerprints": [r.fingerprint for r in v.rows[-3:]],
    }


def _subscriptions(s: Session, args: Args) -> Json:
    found = outlook.subscriptions(s.current.get())
    labels = found.labels
    series = [v for v in found.series if (args.get("all") or v.listed) and args.get("period", v.period) == v.period]
    return {
        "window": found.window,
        "asOf": found.as_of,
        "series": [_series_view(v, labels) for v in series],
        "income": [_series_view(v, labels) for v in found.income if args.get("all") or v.listed],
        "installments": [
            {
                "card": labels.get(i.account, i.account),
                "title": i.title,
                "installment": f"{i.number}/{i.count}",
                "amount": round_half_up(i.amount),
                "left": i.left,
                "remaining": round_half_up(i.remaining),
                "lastCut": i.last,
                "fingerprint": i.row,
            }
            for i in found.installments
        ],
        "note": "amount: aylık seride ayda, dönemselde dönem başına beklenen tutar (süren serilerde). nextDay son "
        "ödemeden sonraki beklenen gün; belgeler o günden önce bitiyorsa geçmiş bir gün olabilir. Varsayılan liste "
        "sürenler ve pencere içinde biten taahhütlerdir; all=true hepsini verir.",
    }


def _due_view(item: outlook.Due, labels: dict[str, str]) -> Json:
    return {
        "day": item.day,
        "kind": item.kind,
        "kindLabel": PAYMENT_KIND[item.kind],
        "title": item.title,
        "account": labels.get(item.account, item.account),
        "amount": round_half_up(item.amount),
        "minimum": None if item.minimum is None else round_half_up(item.minimum),
        "basis": item.basis,
        "series": item.series or None,
        "fingerprints": list(item.rows),
    }


def _upcoming(s: Session, args: Args) -> Json:
    found = outlook.calendar(s.current.get(), s.today())
    until = min(found.end, found.today + timedelta(days=args.get("days", HORIZON) - 1))
    items = [item for item in found.items if item.day <= until]
    return {
        "today": found.today,
        "until": until,
        "items": [_due_view(item, found.labels) for item in items],
        "totalOut": round_half_up(sum((item.amount for item in items if item.amount > 0), ZERO)),
        "totalIn": round_half_up(-sum((item.amount for item in items if item.amount < 0), ZERO)),
        "note": "Tahmin: amount > 0 para çıkışı, < 0 para girişi; gün ve tutarlar geçmiş ödemelerden beklenendir, "
        "basis neye dayandığını söyler. Taksit kartın kesim gününde, kart son ödemesi ekstreden gelir.",
    }


def _cash_flow(s: Session, args: Args) -> Json:
    found = outlook.cash_flow(s.current.get(), s.today())
    f, labels = found.forecast, found.labels
    step = 1 if args.get("daily") else 7

    def point(p: tuple[date, Decimal] | None) -> Json | None:
        return p and {"day": p[0], "balance": p[1]}

    def spread(sp: outlook.Spread | None) -> Json | None:
        return sp and {"monthly": round_half_up(sp.monthly), "months": list(sp.months), "after": sp.after}

    return {
        "label": f.label,
        "today": f.today,
        "until": f.end,
        "accounts": [
            {
                "account": a.label,
                "start": {
                    "balance": a.start.balance,
                    "stated": a.start.stated,
                    "day": a.start.on,
                    "source": "banka bildirimi" if a.start.notice else "hesap dökümü",
                    "movesAfter": a.start.moves,
                    "knownThrough": a.start.through,
                },
                "endBalance": a.end,
                "lowest": point(a.lowest),
                "firstBelowZero": point(a.negative),
                "spend": spread(a.spend),
                "cardPayments": spread(a.cards),
                "overdraftInterest": a.interest,
                "items": [_due_view(item, labels) for item in a.items],
                "balances": [point(p) for p in a.days[::step]]
                + ([point(a.days[-1])] if (len(a.days) - 1) % step else []),
                "notes": a.notes,
            }
            for a in f.accounts
        ],
        "elsewhere": [_due_view(item, labels) for item in f.elsewhere],
        "skipped": [{"account": labels.get(account, account), "reason": why} for account, why in f.skipped],
        "notes": f.notes,
    }


def _invoice_view(v: invoices.InvoiceView, labels: dict[str, str]) -> Json:
    row = v.row
    return {
        "key": v.key,
        "kind": v.kind,
        "kindLabel": INVOICE_KIND[v.kind],
        "status": v.status,
        "statusLabel": INVOICE_STATUS[v.status],
        "seller": v.seller,
        "number": v.number or None,
        "issued": v.issued,
        "due": v.due,
        "total": v.total,
        "currency": v.currency,
        "lines": [
            {"description": line.description, "amount": line.amount, "quantity": line.quantity} for line in v.lines
        ],
        "window": {"from": v.window[0], "to": v.window[1]},
        "document": v.document,
        "paidBy": row
        and {
            "fingerprint": row.fingerprint,
            "day": row.day,
            "account": labels.get(row.account, row.account),
            "amount": row.amount,
            "description": row.description,
        },
        "reasons": list(v.reasons),
    }


def _invoices(s: Session, args: Args) -> Json:
    found = invoices.overview(s.current.get())
    items = [v for v in found.items if args.get("status", v.status) == v.status]
    return {
        "counts": {str(status): n for status, n in found.counts.items()},
        "invoices": [_invoice_view(v, found.labels) for v in items],
        "note": "Banka dışı göndericilerin faturaları ve makbuzları hiçbir toplama girmez; harcamayı onu ödeyen banka "
        "satırı sayar. total belgenin kendi para birimindedir (currency); paidBy onu ödeyen banka satırıdır, tutarı "
        "TL. pending: penceresi (window) geçmedi ya da banka belgeleri o günlere henüz ulaşmadı; son ödemesi gelmemiş "
        "fatura upcoming_payments takviminde de görünür. unmatched: yalnızca bilgi, reasons olası nedenleri söyler. "
        "Sıra: bekleyenler son ödeme gününe göre, sonra eşleşmeyenler ve eşleşenler en yenisi önce.",
    }


def _habits(s: Session, args: Args) -> Json:
    ins = s.current.get().insights
    return {
        "window": ins.timeline.window,
        "habits": [
            {
                "name": h.name,
                "category": h.category,
                "necessity": h.necessity,
                "byCategory": h.by_category,
                "status": h.status,
                "statusLabel": HABIT_STATUS[h.status],
                "pattern": h.pattern,
                "count": h.count,
                "months": h.months,
                "windowMonths": h.span,
                "total": round_half_up(h.total),
                "recentMonthly": round_half_up(h.recent),
                "expectedMonthly": round_half_up(h.monthly),
                "last": h.last,
            }
            for h in ins.habits
        ],
    }


def _accounts(s: Session, args: Args) -> Json:
    a = s.current.get()
    ds = a.dataset
    held = {h.label: h for h in a.insights.holdings}
    rows: list[Json] = []
    for acc in sorted(ds.accounts.values(), key=lambda x: (x.bank, x.type, x.label)):
        covered = accounts.statements_of(ds, acc.id)
        h = held.get(acc.label)
        rows.append(
            {
                "label": acc.label,
                "bank": acc.bank,
                "type": acc.type,
                "currency": acc.currency,
                "note": acc.note or None,
                "statements": covered.count,
                "verified": covered.verified,
                "first": covered.first,
                "last": covered.last,
                "fullMonths": covered.full_months,
                "partialMonths": covered.partial_months,
                "balance": h and {"amount": h.amount, "valueTL": h.value, "asOf": h.as_of, "note": h.note},
            }
        )
    return {"accounts": rows}


def _totals(t: month_end.Totals) -> Json:
    return {
        "expense": round_half_up(t.expense),
        "income": None if t.income is None else round_half_up(t.income),
        "people": round_half_up(t.people),
        "debt": round_half_up(t.debt),
        "saving": round_half_up(t.saving),
        "feesAndInterest": round_half_up(t.fees),
        "left": None if t.left is None else round_half_up(t.left),
    }


def _month_end(s: Session, args: Args) -> Json:
    a = s.current.get()
    if "month" not in args:
        return {
            "months": [
                {
                    "month": me.month,
                    "status": me.status,
                    "statusLabel": me.label,
                    "closing": me.summary,
                    "totals": _totals(me.totals),
                    "provisional": len(me.provisional),
                    "notOnStatement": len(me.unmatched),
                }
                for me in closing.months(a, date.today())
            ],
            "note": "status: closed (bütün belgeler geldi ve tutarlı), waiting, missing, check, running (bu ay). "
            "Ayrıntı için month ile çağırın.",
        }
    me = closing.month(a, args["month"], date.today())  # an older month than those with a page is built on request
    ds = a.dataset
    return {
        "month": me.month,
        "status": me.status,
        "statusLabel": me.label,
        "closing": me.summary,
        "totals": _totals(me.totals),
        "incomeNote": me.income_note,
        "previousMonth": me.previous and _totals(me.previous),
        "typicalExpense": me.typical,
        "accounts": [
            {
                "account": ac.account.label,
                "status": ac.status,
                "statusLabel": month_end.ACCOUNT_STATUS[ac.status],
                "coveredDays": ac.covered,
                "neededDays": ac.needed,
                "note": ac.note,
                "monthEndBalance": ac.balance,
                "currency": ac.account.currency,
                "nextCut": ac.next_cut,
                "waitsForIt": ac.blocking,
            }
            for ac in me.accounts
        ],
        "expenseByGroup": [{"group": g, "total": round_half_up(v)} for g, _, v in me.groups],
        "expenseByNecessity": [{"necessity": n, "total": round_half_up(v)} for n, _, v in me.levels],
        "topCategories": [{"category": c, "total": round_half_up(v), "count": n} for c, _, v, n in me.categories],
        "regularPayments": [
            {
                "merchant": sr.merchant,
                "paid": [{"date": t.date, "amount": abs(t.amount)} for t in paid],
                "expected": expected,
            }
            for sr, paid, expected in me.regular
        ],
        "provisional": [
            {
                "date": t.date,
                "account": ds.accounts[t.account].label,
                "description": t.description,
                "kind": t.kind,
                "amount": t.amount,
            }
            for t in me.provisional
        ],
        "notOnStatement": [
            {
                "date": line.txn.date,
                "account": ds.accounts[line.txn.account].label,
                "description": line.txn.description,
                "amount": receipt_amount(ds, line),
            }
            for line in me.unmatched
        ],
        "page": str(s.ws.exports / month_end.FOLDER / me.file),
    }


def _personal_text(s: Session) -> str:
    return s.ws.rules.read_text(encoding="utf-8") if s.ws.rules.exists() else ""


def _read_rules(s: Session, args: Args) -> Json:
    rules = Categorizer.layered(s.ws.rules)
    groups: dict[str, list[str]] = defaultdict(list)
    for category, group in rules.categories.items():
        groups[group].append(category)
    return {
        "path": str(s.ws.rules),
        "content": _personal_text(s),
        "layers": "content kişisel kurallardır; uygulamayla gelen genel kuralların üstüne biner, tutan kişisel "
        "kural önce gelir. categories ikisinin birleşimidir.",
        "categories": dict(groups),
        "necessity": rules.necessity,
        "regular": sorted(rules.regular),
        "ended": rules.ended,
    }


def _rule_labels(found: category_rules.Labels) -> Json:
    return {"merchant": found.merchant, "category": found.category, "necessity": found.necessity, "kind": found.kind}


def _change_rules(s: Session, edit: Callable[[], str]) -> Json:
    """Make the change through the rules' use case (app.rules: the history, the audit log, the analysis again) and
    tell it as the MVP's tools did: the diff, the earlier file kept, which rows moved, the report written."""
    try:
        change = category_rules.save(s.ws, s.current, edit, Actor.MCP, write=True)
    except category_rules.RulesError as exc:
        raise ToolError(str(exc)) from exc
    outputs = s.current.get().outputs
    return {
        "diff": change.diff,
        "backup": str(s.ws.rules_history / change.backup) if change.backup else None,
        "effect": {
            "changed": change.changed,
            "examples": [
                {
                    "date": e.day,
                    "description": e.description,
                    "amount": e.amount,
                    "before": _rule_labels(e.before),
                    "after": _rule_labels(e.after),
                }
                for e in change.examples
            ],
            "moves": [{"from": m.before, "to": m.after, "count": m.count, "total": m.total} for m in change.moves],
        },
        "report": str(outputs.html) if outputs is not None else None,
    }


def _add_rule(s: Session, args: Args) -> Json:
    return _change_rules(
        s, lambda: category_rules.merchant_rule(s.ws, args["category"], args["merchant"], args["patterns"])
    )


def _mark_ended(s: Session, args: Args) -> Json:
    ds = s.current.get().dataset
    return _change_rules(
        s, lambda: category_rules.ended(s.ws, ds, args["merchant"], args["month"], args.get("note", ""))
    )


def _write_rules(s: Session, args: Args) -> Json:
    return _change_rules(s, lambda: args["content"])


def _alert_view(rule: notify.AlertRule) -> Json:
    c = rule.condition
    return {
        "name": rule.name,
        "event": rule.event,
        "eventLabel": EVENT_KIND[rule.event],
        "days": c.days,
        "amount": c.amount,
        "text": c.text or None,
        "channels": [CHANNEL[ch] for ch in rule.channels],
        "detail": DETAIL_LEVEL[rule.detail] if rule.detail else None,
        "enabled": rule.enabled,
        "quietHours": rule.quiet,
    }


def _alert_from(args: Args) -> notify.AlertRule:
    try:
        event = notify.EventKind(args.get("event"))
    except ValueError:
        raise ToolError("event bilinen bir olay olmalı (alerts action=list olayları listeler)") from None
    amount = args.get("amount")
    return notify.AlertRule(
        str(args.get("name", "")).strip(),
        event,
        notify.Condition(args.get("days"), None if amount is None else to_decimal(amount), str(args.get("text", ""))),
        tuple(notify.Channel(ch) for ch in args.get("channels", ["desktop", "telegram"])),
        notify.DetailLevel(args["detail"]) if args.get("detail") else None,
        quiet=args.get("quiet_hours", True),
    )


def _alerts(s: Session, args: Args) -> Json:
    found = notify.load_rules(s.ws)
    rules = list(found.rules)
    action = args.get("action", "list")
    if action != "list":
        if action == "add":
            rule = _alert_from(args)
            if any(r.key == rule.key for r in rules):
                raise ToolError(f"'{rule.name}' adında bir kural zaten var")
            rules.append(rule)
        else:
            name = fold(str(args.get("name", "")))
            if not any(r.key == name for r in rules):
                raise ToolError(
                    f"'{args.get('name', '')}' adında bir kural yok (alerts action=list kuralları listeler)"
                )
            rules = [
                notify.AlertRule(r.name, r.event, r.condition, r.channels, r.detail, action == "open", r.quiet)
                if r.key == name
                else r
                for r in rules
            ]
        try:
            notify.save_rules(s.ws, rules, Actor.MCP)
        except notify.RulesError as exc:
            raise ToolError(str(exc)) from exc
        found = notify.load_rules(s.ws)
    state = notify.status(s.ws)
    return {
        "rules": [_alert_view(r) for r in found.rules],
        "own": found.own,
        "problem": found.problem or None,
        "channels": [
            {"channel": CHANNEL[c.channel], "on": c.on, "ready": c.ready, "note": c.note} for c in state.channels
        ],
        "events": [
            {"event": e.kind, "label": e.label, "days": e.days, "amount": e.amount, "text": e.text}
            for e in notify.event_catalog()
        ]
        if action == "list"
        else None,
        "note": "Her kural bir olayı izler; olay olunca uygulama içi kutuya ve kuralın kanallarına bildirim gider, "
        "bir olay için her kanala bir kez. days: en çok kaç gün kala, amount: en az kaç TL, text: başlığında geçen "
        "yazı (yalnızca olayın izin verdiği koşullar). Sessiz saatte gelenler özetle gider.",
    }


def _schema(required: tuple[str, ...] = (), **properties: Json) -> Json:
    return {"type": "object", "properties": properties, "required": list(required), "additionalProperties": False}


_TEXT = {"type": "string"}
_MONTH_OR_DAY = {"type": "string", "pattern": r"\d{4}-\d{2}(-\d{2})?", "description": "YYYY-AA ya da YYYY-AA-GG"}
_GROUP_BY = ["month", "category", "group", "merchant", "kind", "account", "necessity"]
# The kinds a ledger row can have: transfer candidates are resolved before.
_KINDS = [k.value for k in TransactionKind if k is not TransactionKind.TRANSFER_CANDIDATE]
_SORT = ["date_desc", "date_asc", "amount_desc", "amount_asc"]

TOOLS = (
    Tool(
        "status",
        "Durum",
        "Belgelerin ve hesapların durumu: kaç belge okundu ve bankanın toplamıyla/bakiyeyle tutarlı mı, "
        "okunamayanlar, gelen klasöründe bekleyenler, tam aylar, eksik ya da güncel olmayan belgeler "
        "(hangi hesabın hangi belgesi indirilmeli), rapor dosyası ve e-postadan belge almanın durumu.",
        _schema(),
        _status,
    ),
    Tool(
        "import_documents",
        "Belge içe aktar",
        "Bu bilgisayardaki dosya, klasör, zip ya da mbox (e-posta arşivi) yollarındaki banka belgelerini okur ve "
        "arşive almanın planını plan_id ile döndürür; hiçbir dosyaya dokunmaz, asıllar hiçbir zaman taşınmaz. Plan "
        "her belge için ne olacağını söyler: yeni belge arşive (okunamayan ve para hareketi olmayan da), arşivde "
        "olan için yalnızca kaynak kaydı, şirket belgesi hiç alınmaz. Arşive almak için kullanıcı onaylayınca "
        "apply_inbox.",
        _schema(
            ("paths",),
            paths={"type": "array", "minItems": 1, "items": _TEXT, "description": "mutlak yollar; ~ kullanılabilir"},
        ),
        _import,
        read_only=False,
    ),
    Tool(
        "fetch_email",
        "E-postadan belge al",
        "Kullanıcının e-posta kutusunu (Gmail, IMAP) salt okunur açar ve bankaların gönderdiği kart ekstresi, hesap "
        "dökümü ve dekont eklerini doğrudan arşive alır (şirket belgeleri hariç); e-posta kutusunda hiçbir şeyi "
        "değiştirmez. Yalnızca ayarlardaki banka alan adlarından gelen ve sunucunun göndereni doğruladığı (DMARC) "
        "e-postalar sayılır. Son alımdan sonra gelenleri okur. Kurulu değilse bağlantıyı kullanıcı kendisi "
        "kurar; şifre sohbete girmez.",
        _schema(),
        _fetch_email,
        read_only=False,
        open_world=True,
    ),
    Tool(
        "plan_inbox",
        "Gelen kutusu planı",
        "Gelen klasöründeki dosyalara ne olacağını gösterir, hiçbir dosyaya dokunmaz: hangi belge hangi adla arşive "
        "alınacak (belge türü, hesap, dönem, tutarlılık kontrolüyle), hangileri okunamadı ya da para hareketi "
        "taşımıyor (onlar da arşive), hangileri zaten arşivde, hangileri şirket belgesi ya da belge değil diye çöp "
        "kutusuna gidecek. Dönen plan_id apply_inbox içindir.",
        _schema(),
        _plan,
    ),
    Tool(
        "apply_inbox",
        "Planı uygula",
        "plan_inbox ya da import_documents ile gösterilen planı aynen uygular: belgeleri arşive alır, gelen "
        "klasöründen ayrılanları çöp kutusuna (geri alınabilir) taşır, denetim kaydına yazar, raporu yeniden "
        "üretir. Yalnızca kullanıcı planı görüp onayladıktan sonra çağırın.",
        _schema(("plan_id",), plan_id=_TEXT),
        _apply,
        read_only=False,
        destructive=True,
    ),
    Tool(
        "build_report",
        "Raporu üret",
        "HTML raporu, islemler.csv ve islemler.xlsx dosyalarını yeniden üretir; okunan belge sayılarını ve kontrol "
        "sonuçlarını döndürür.",
        _schema(),
        _build,
        read_only=False,
    ),
    Tool(
        "insights",
        "Değerlendirme",
        "Programın yorumu: tam aylar penceresi, öne çıkanlar, önerilen adımlar (aylık etkisiyle), aylık bütçe "
        "(bugün ve öneri), gelir-gider ortalamaları, varlıklar ve borçlar, harcama eğilimi, düzenli gelir.",
        _schema(),
        _insights,
    ),
    Tool(
        "transactions",
        "İşlemler",
        "İşlemleri süzer, sıralar ya da gruplar (group_by ile aylık, kategori, işyeri… toplamları). amount > 0 para "
        "çıkışı, < 0 para girişi. Gider toplamı için kinds = [purchase, refund, interest_fee] verin; varsayılan bütün "
        "türlerdir.",
        _schema(
            (),
            **{
                "from": _MONTH_OR_DAY,
                "to": _MONTH_OR_DAY,
                "text": {
                    "type": "string",
                    "description": "işyeri, açıklama ya da karşı tarafta geçen metin "
                    "(Türkçe karakter ve büyük/küçük harf duyarsız)",
                },
                "category": _TEXT,
                "group": {"type": "string", "description": "ana grup"},
                "kinds": {"type": "array", "items": {"type": "string", "enum": _KINDS}},
                "account": {"type": "string", "description": "hesap adında geçen metin"},
                "necessity": {"type": "string", "enum": [n.value for n in Necessity]},
                "min_amount": {"type": "number"},
                "max_amount": {"type": "number"},
                "group_by": {"type": "string", "enum": _GROUP_BY},
                "sort": {"type": "string", "enum": _SORT},
                "limit": {"type": "integer", "minimum": 1, "maximum": 500},
            },
        ),
        _transactions,
    ),
    Tool(
        "regular_payments",
        "Düzenli ödemeler",
        "Düzenli ödemeler ve abonelikler (kira, faturalar, üyelikler): durumu (devam, bitti, iptal, iptal_sonrasi), "
        "aylık tutarı, son ve beklenen sonraki ödeme, fiyat değişimi; ayrıca düzenli gelirler.",
        _schema(status={"type": "string", "enum": list(STATUS)}),
        _regular,
    ),
    Tool(
        "subscriptions",
        "Abonelikler",
        "Düzenli (aylık) ve dönemsel (altı ayda ya da yılda bir) ödemeler: durumu (active, ended, cancelled, "
        "paid_after_cancel), beklenen tutarı (aylıkta ayda, dönemselde dönem başına), son ve beklenen sonraki ödeme, "
        "fiyat değişimi, dayandığı belgeler ve satırlar; ayrıca düzenli gelirler ve kalan taksitli alışverişler.",
        _schema(
            all={"type": "boolean", "description": "biten ve listede görünmeyenler de"},
            period={"type": "string", "enum": [p.value for p in SeriesPeriod]},
        ),
        _subscriptions,
    ),
    Tool(
        "upcoming_payments",
        "Yaklaşan ödemeler",
        "Bugünden itibaren 60 günün takvimi: düzenli ve dönemsel ödemeler (en son hangi hesaptan ödendiyse), maaş ve "
        "düzenli gelirler, kalan kart taksitleri, kredi taksitleri ve kart son ödemeleri; her biri günü, tutarı, "
        "hesabı ve neye dayandığıyla. Tahmindir.",
        _schema(days={"type": "integer", "minimum": 1, "maximum": HORIZON, "description": "kaç gün (varsayılan 60)"}),
        _upcoming,
    ),
    Tool(
        "cash_flow_forecast",
        "Nakit akışı öngörüsü",
        "TL banka hesaplarının önümüzdeki 60 gün için gün gün bakiye tahmini: başlangıç bakiyesi (son belge ve "
        "sonraki dekont ve bildirimler), beklenen ödemeler ve gelirler, seri dışı çıkışların aylık medyanı, eksiye "
        "düştüğü gün ve tutar, en düşük gün, varsayımlar. Öngörüye girmeyen hesaplar nedeniyle listelenir.",
        _schema(daily={"type": "boolean", "description": "bakiyeleri haftalık değil gün gün ver"}),
        _cash_flow,
    ),
    Tool(
        "invoices",
        "Faturalar ve makbuzlar",
        "Banka dışı göndericilerin e-postayla gelen faturaları ve makbuzları (telefon, internet, enerji, abonelik, "
        "alışveriş): satıcı, numara, tarih, son ödeme, tutar ve kalemler; her biri eşleşti (onu ödeyen banka "
        "satırıyla), bekliyor (penceresi geçmedi ya da banka belgeleri o günlere henüz ulaşmadı) ya da eşleşmedi "
        "(yalnızca bilgi, olası nedenleriyle). Hiçbiri toplamlara girmez.",
        _schema(status={"type": "string", "enum": [s.value for s in InvoiceStatus]}),
        _invoices,
    ),
    Tool(
        "alerts",
        "Bildirim kuralları",
        "Bildirim kurallarını listeler (action=list; olaylar, koşulları ve kanalların durumu ile), yeni kural ekler "
        "(action=add: name, event, isteğe bağlı days, amount, text, channels, detail, quiet_hours) ya da bir kuralı kapatır "
        "(action=close) veya yeniden açar (action=open; name ile). Değişiklik rules/alerts.yaml'a yazılır, önceki "
        "dosya kural geçmişinde saklanır; okunamayacak bir kural yazılmaz.",
        _schema(
            action={"type": "string", "enum": ["list", "add", "close", "open"]},
            name=_TEXT,
            event={"type": "string", "enum": [k.value for k in EventKind]},
            days={"type": "integer", "minimum": 0, "maximum": 60},
            amount={"type": "number", "minimum": 0},
            text=_TEXT,
            channels={"type": "array", "items": {"type": "string", "enum": ["desktop", "telegram", "email"]}},
            detail={"type": "string", "enum": ["full", "summary", "minimal"]},
            quiet_hours={"type": "boolean", "description": "false: sessiz saatte de hemen gider"},
        ),
        _alerts,
        read_only=False,
        writes=lambda args: args.get("action", "list") != "list",
    ),
    Tool(
        "habits",
        "Alışkanlıklar",
        "İsteğe bağlı harcamalar (işyerine göre) ve kaçınılabilir maliyetler (faiz, ücret; kategoriye göre): durumu "
        "(her ay, yeni, ara sıra, durdu, tek seferlik), sıklığı ve bundan sonraki aylık maliyeti.",
        _schema(),
        _habits,
    ),
    Tool(
        "accounts",
        "Hesaplar",
        "Hesaplar ve kartlar: banka, tür, para birimi, belge sayısı ve tutarlılığı, belgelerin kapsadığı dönem, "
        "eksik kalan aylar, son bakiye.",
        _schema(),
        _accounts,
    ),
    Tool(
        "month_end",
        "Ay sonu ve kapanış",
        "Ay sonu raporu ve ekstre ile kapanış. month verilmezse son aylar: her ayın durumu (closed: bütün "
        "hesapların ekstresi/dökümü ayın tamamını kapsıyor, tutarlı ve dekontlar eşleşti; waiting: ekstre "
        "bekleniyor; missing: belge eksik; check: kontrol gerekli; running: ay sürüyor), gider, gelir, kalan. "
        "month ile o ayın ayrıntısı: hesap hesap hangi ekstre ya da döküm bekleniyor (sonraki kesim tarihi), ay "
        "sonu bakiyeleri, gider dağılımı, düzenli ödemeler, ekstresi gelmeden dekontlardan işlenen geçici kayıtlar "
        "ve ekstrede görünmeyen dekontlar.",
        _schema(month={"type": "string", "pattern": r"\d{4}-\d{2}", "description": "YYYY-AA"}),
        _month_end,
    ),
    Tool(
        "read_rules",
        "Kategori kurallarını oku",
        "Kişisel kural dosyasının metni ve kuralların özeti (kişisel kurallar ve uygulamayla gelen genel kurallar "
        "birlikte): ana gruplar ve kategoriler, gereklilik seviyeleri, düzenli ödeme kategorileri, bitti olarak "
        "işaretlenen ödemeler.",
        _schema(),
        _read_rules,
    ),
    Tool(
        "add_rule",
        "Kategori kuralı ekle",
        "Bir işyerini bir kategoriye bağlayan isimli kural ekler (işyeri varsa desenlerini genişletir). İsimli "
        "kurallar bütün anahtar kelimelerden önce denenir. Desenler büyük/küçük harf ve Türkçe karakter "
        "duyarsızdır; 're:' ile başlayan desen ASCII büyük harfe çevrilmiş açıklamaya uygulanan düzenli ifadedir. "
        "Değişikliğin hangi işlemleri taşıdığını döndürür; dosyanın yedeği alınır.",
        _schema(
            ("category", "merchant", "patterns"),
            category={"type": "string", "description": "var olan kategori (read_rules → categories)"},
            merchant={"type": "string", "description": "raporda görünecek işyeri adı"},
            patterns={"type": "array", "minItems": 1, "items": _TEXT},
        ),
        _add_rule,
        read_only=False,
    ),
    Tool(
        "mark_ended",
        "Bitti olarak işaretle",
        "Kullanıcının bittiğini ya da iptal ettiğini söylediği bir ödemeyi veya bıraktığı bir alışkanlığı `_biten` "
        "bölümüne yazar: işyeri adı raporda göründüğü gibi, son ödemenin ayı. Tahmine ve alışkanlıklara girmez; o "
        "aydan sonra ödeme görünürse rapor uyarır.",
        _schema(
            ("merchant", "month"),
            merchant=_TEXT,
            month={"type": "string", "pattern": r"\d{4}-\d{2}", "description": "YYYY-AA"},
            note={"type": "string", "description": "kısa not (ör. kullanıcının söylediği)"},
        ),
        _mark_ended,
        read_only=False,
    ),
    Tool(
        "write_rules",
        "Kategori kurallarını yaz",
        "Kişisel kural dosyasının tamamını verilen metinle değiştirir (önce read_rules ile okuyun, yorumları "
        "koruyun). Metin programın okuyabileceği kurallar değilse hiçbir şey yazılmaz. Eski dosyanın kopyası "
        "kural geçmişine alınır; değişikliğin farkı ve etkilediği işlemler döner.",
        _schema(("content",), content=_TEXT),
        _write_rules,
        read_only=False,
    ),
)
TOOLS_BY_NAME = {t.name: t for t in TOOLS}
