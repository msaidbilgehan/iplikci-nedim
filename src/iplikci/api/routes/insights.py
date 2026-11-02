"""The Değerlendirme screen's interpretation (F10): highlights, steps, the monthly budget, habits, money in and out,
what changed and the large one-off purchases, the regular income and the unusual movements. No filter changes it;
every part says its window and numbers. Reading needs a session or the token."""

from datetime import date

from fastapi import APIRouter, Depends, Request
from pydantic import BaseModel

from ...app import assessment
from ...app.analysis import Analysis, account_labels
from ...app.assessment import HabitStatus, Necessity, SeriesStatus, Tone, UnusualKind
from ...app.links import Link
from ...app.workspace import Busy
from ..context import Context, context_of
from ..guard import Principal
from ..models import LinkOut, MoneyOut, RowOut, link_out, money, row_out
from ..problems import Problem
from .deps import only

router = APIRouter()


class InsightsWindowOut(BaseModel):
    months: list[str]  # the complete months the interpretation uses, oldest first
    as_of: date  # the newest statement's end
    last_complete: str


class FindingOut(BaseModel):
    tone: Tone
    title: str
    text: str
    link: LinkOut


class StepOut(BaseModel):
    title: str
    text: str
    monthly: MoneyOut | None  # money freed per month; null when it depends on a choice the data cannot price


class BudgetLineOut(BaseModel):
    label: str
    now: MoneyOut  # the typical month today
    plan: MoneyOut  # the month the steps lead to
    note: str


class HabitOut(BaseModel):
    name: str
    category: str
    necessity: Necessity | None
    by_category: bool  # an avoidable cost counted by its category, not a merchant
    status: HabitStatus
    pattern: str
    count: int
    months: int
    span: int
    total: MoneyOut
    recent: MoneyOut  # monthly average of the last three complete months
    monthly: MoneyOut  # what it costs per month from now on
    last: date
    link: LinkOut


class FlowOut(BaseModel):
    """Each a monthly average over the window's months."""

    months: list[str]
    income: MoneyOut
    expense: MoneyOut
    people: MoneyOut
    unnamed_people: MoneyOut  # of it, sent to people the statement does not name
    debt: MoneyOut
    saving: MoneyOut
    fx: MoneyOut  # foreign currency and gold bought with TL; below zero when sold
    left: MoneyOut  # may be below zero: then minor is negative
    debt_start: MoneyOut
    debt_end: MoneyOut
    other_typical: MoneyOut


class ChangeOut(BaseModel):
    category: str
    before: MoneyOut
    recent: MoneyOut


class TrendOut(BaseModel):
    before: list[str]
    recent: list[str]
    before_average: MoneyOut
    recent_average: MoneyOut
    usual_before: MoneyOut  # without the large one-off purchases
    usual_recent: MoneyOut
    changes: list[ChangeOut]
    large: list[RowOut]
    threshold: MoneyOut


class IncomeOut(BaseModel):
    name: str
    monthly: MoneyOut
    last: date
    status: SeriesStatus


class UnusualOut(BaseModel):
    kind: UnusualKind
    row: RowOut
    text: str
    link: LinkOut


class InsightsOut(BaseModel):
    window: InsightsWindowOut
    findings: list[FindingOut]
    steps: list[StepOut]
    budget: list[BudgetLineOut]
    habits: list[HabitOut]
    flow: FlowOut | None
    trend: TrendOut | None
    income: list[IncomeOut]
    unusual: list[UnusualOut]


def _analysis(context: Context) -> Analysis:
    try:
        return context.analysis.get()
    except Busy as exc:
        raise Problem(503, "busy", str(exc)) from exc


def _link(found: Link) -> LinkOut:
    out = link_out(found)
    assert out is not None  # a link given is never None
    return out


def _flow(f: assessment.Flow | None) -> FlowOut | None:
    if f is None:
        return None
    return FlowOut(
        months=list(f.months),
        income=money(f.income),
        expense=money(f.expense),
        people=money(f.people),
        unnamed_people=money(f.unnamed_people),
        debt=money(f.debt),
        saving=money(f.saving),
        fx=money(f.fx),
        left=money(f.left),
        debt_start=money(f.debt_start),
        debt_end=money(f.debt_end),
        other_typical=money(f.other_typical),
    )


def _trend(t: assessment.Trend | None, labels: dict[str, str]) -> TrendOut | None:
    if t is None:
        return None
    return TrendOut(
        before=list(t.before),
        recent=list(t.recent),
        before_average=money(t.before_average),
        recent_average=money(t.recent_average),
        usual_before=money(t.usual_before),
        usual_recent=money(t.usual_recent),
        changes=[ChangeOut(category=c.category, before=money(c.before), recent=money(c.recent)) for c in t.changes],
        large=[row_out(r, labels) for r in t.large],
        threshold=money(t.threshold),
    )


def _habit(h: assessment.HabitLine) -> HabitOut:
    return HabitOut(
        name=h.name,
        category=h.category,
        necessity=h.necessity,
        by_category=h.by_category,
        status=h.status,
        pattern=h.pattern,
        count=h.count,
        months=h.months,
        span=h.span,
        total=money(h.total),
        recent=money(h.recent),
        monthly=money(h.monthly),
        last=h.last,
        link=_link(h.link),
    )


@router.get("/api/insights", dependencies=[Depends(only(Principal.BROWSER, Principal.CLIENT))])
def insights(request: Request) -> InsightsOut:
    """The interpretation over the complete months; no filter changes it."""
    context = context_of(request)
    a = _analysis(context)
    found = assessment.assess(a, context.today())
    labels = account_labels(a)
    w = found.window
    return InsightsOut(
        window=InsightsWindowOut(months=list(w.months), as_of=w.as_of, last_complete=w.last_complete),
        findings=[FindingOut(tone=f.tone, title=f.title, text=f.text, link=_link(f.link)) for f in found.findings],
        steps=[
            StepOut(title=s.title, text=s.text, monthly=money(s.monthly) if s.monthly is not None else None)
            for s in found.steps
        ],
        budget=[BudgetLineOut(label=b.label, now=money(b.now), plan=money(b.plan), note=b.note) for b in found.budget],
        habits=[_habit(h) for h in found.habits],
        flow=_flow(found.flow),
        trend=_trend(found.trend, labels),
        income=[IncomeOut(name=i.name, monthly=money(i.monthly), last=i.last, status=i.status) for i in found.income],
        unusual=[
            UnusualOut(kind=u.kind, row=row_out(u.row, labels), text=u.text, link=_link(u.link)) for u in found.unusual
        ],
    )
