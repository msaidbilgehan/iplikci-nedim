"""The Değerlendirme screen's spending cards (F10, the MVP report's): tiles, the months by group and by necessity,
categories, merchants, money in and out by month and the three-month forecast. The filters are the Transactions
screen's (the same address query); the forecast follows every one but the period. Without a period the last twelve
months of the data. Reading needs a session or the token."""

from datetime import date
from typing import Annotated

from fastapi import APIRouter, Depends, Request
from pydantic import BaseModel

from ...app import spending
from ...app.analysis import Analysis
from ...app.links import Link
from ...app.spending import ForecastPart, Necessity
from ...app.transactions import Filter
from ...app.workspace import Busy
from ..context import Context, context_of
from ..guard import Principal
from ..models import LinkOut, MoneyOut, link_out, money
from ..problems import Problem
from .deps import only
from .transactions import filters

router = APIRouter()


class PeriodOut(BaseModel):
    start: str  # first month, YYYY-MM
    end: str
    first: str  # the data's first and last month in the accounts kept: the presets' bounds
    last: str


class TilesOut(BaseModel):
    total: MoneyOut
    count: int
    average: MoneyOut | None  # monthly, over the period's whole months, those without spending too
    average_months: int
    partial_months: int  # the period's months that are not whole (covered only partly, or cut by it): averaged nowhere
    income_average: MoneyOut | None  # monthly, over the whole months account lists cover
    income_months: int
    income_share: str | None  # the spending of those months as a share of their income, a decimal ("0.54")
    unnecessary: MoneyOut
    last_month: str | None
    last_total: MoneyOut
    last_partial: bool
    last_change: str | None  # against the up to three whole months before it, a decimal ("-0.12")


class SliceOut(BaseModel):
    key: str  # a group's name, or a necessity's code
    slot: int  # the fixed colour slot; 0 is the neutral grey


class MonthRowOut(BaseModel):
    month: str
    values: list[MoneyOut]  # one per slice, in the slices' order
    partial: bool  # not whole: covered only partly, or cut by the period; drawn lighter, averaged nowhere


class MonthTableOut(BaseModel):
    slices: list[SliceOut]
    months: list[MonthRowOut]


class CategoryLineOut(BaseModel):
    category: str
    group: str
    slot: int
    total: MoneyOut
    share: str | None  # of the total, a decimal
    average: MoneyOut | None  # monthly, over the period's whole months; null without one
    count: int
    link: LinkOut


class MerchantLineOut(BaseModel):
    merchant: str
    category: str
    group: str
    slot: int
    count: int
    total: MoneyOut
    per_row: MoneyOut
    last: date
    link: LinkOut


class FlowMonthOut(BaseModel):
    month: str
    partial: bool  # not whole: drawn lighter, averaged nowhere
    income: MoneyOut
    expense: MoneyOut
    net: MoneyOut
    people: MoneyOut
    debt: MoneyOut
    saving: MoneyOut
    left: MoneyOut


class SpendingForecastLineOut(BaseModel):
    part: ForecastPart
    label: str
    note: str
    necessity: Necessity
    group: str
    slot: int
    amounts: list[MoneyOut]  # one per month ahead
    link: LinkOut | None


class SpendingForecastOut(BaseModel):
    base: list[str]  # the complete months the typical month is taken from
    months: list[str]  # the months ahead
    lines: list[SpendingForecastLineOut]
    totals: list[MoneyOut]
    by_level: MonthTableOut
    actual: MonthTableOut  # the six months before, beside the forecast
    income: MoneyOut
    income_names: list[str]
    saving: MoneyOut
    saving_names: list[str]
    other: MoneyOut  # money to people and debt repaid, the median month of the last six
    left: MoneyOut | None  # null without a regular income


class SpendingOut(BaseModel):
    period: PeriodOut | None
    tiles: TilesOut
    by_group: MonthTableOut
    by_level: MonthTableOut
    categories: list[CategoryLineOut]
    merchants: list[MerchantLineOut]
    flow: list[FlowMonthOut]
    forecast: SpendingForecastOut | None


def _link(found: Link) -> LinkOut:
    out = link_out(found)
    assert out is not None  # a link given is never None
    return out


def _share(value: object) -> str | None:
    return None if value is None else str(value)


def _table(t: spending.MonthTable) -> MonthTableOut:
    return MonthTableOut(
        slices=[SliceOut(key=s.key, slot=s.slot) for s in t.slices],
        months=[MonthRowOut(month=m.month, values=[money(v) for v in m.values], partial=m.partial) for m in t.months],
    )


def _tiles(t: spending.Tiles) -> TilesOut:
    return TilesOut(
        total=money(t.total),
        count=t.count,
        average=money(t.average) if t.average is not None else None,
        average_months=t.average_months,
        partial_months=t.partial_months,
        income_average=money(t.income_average) if t.income_average is not None else None,
        income_months=t.income_months,
        income_share=_share(round(t.income_share, 4) if t.income_share is not None else None),
        unnecessary=money(t.unnecessary),
        last_month=t.last_month,
        last_total=money(t.last_total),
        last_partial=t.last_partial,
        last_change=_share(round(t.last_change, 4) if t.last_change is not None else None),
    )


def _forecast(f: spending.Forecast | None) -> SpendingForecastOut | None:
    if f is None:
        return None
    return SpendingForecastOut(
        base=list(f.base),
        months=list(f.months),
        lines=[
            SpendingForecastLineOut(
                part=line.part,
                label=line.label,
                note=line.note,
                necessity=line.necessity,
                group=line.group,
                slot=line.slot,
                amounts=[money(v) for v in line.amounts],
                link=link_out(line.link),
            )
            for line in f.lines
        ],
        totals=[money(v) for v in f.totals],
        by_level=_table(f.by_level),
        actual=_table(f.actual),
        income=money(f.income),
        income_names=list(f.income_names),
        saving=money(f.saving),
        saving_names=list(f.saving_names),
        other=money(f.other),
        left=money(f.left) if f.left is not None else None,
    )


def _analysis(context: Context) -> Analysis:
    try:
        return context.analysis.get()
    except Busy as exc:
        raise Problem(503, "busy", str(exc)) from exc


@router.get("/api/spending", dependencies=[Depends(only(Principal.BROWSER, Principal.CLIENT))])
def spending_cards(request: Request, f: Annotated[Filter, Depends(filters)]) -> SpendingOut:
    """The spending the filters keep, card by card."""
    found = spending.spending(_analysis(context_of(request)), f)
    p = found.period
    return SpendingOut(
        period=PeriodOut(start=p.start, end=p.end, first=p.first, last=p.last) if p is not None else None,
        tiles=_tiles(found.tiles),
        by_group=_table(found.by_group),
        by_level=_table(found.by_level),
        categories=[
            CategoryLineOut(
                category=c.category,
                group=c.group,
                slot=c.slot,
                total=money(c.total),
                share=_share(round(c.share, 4) if c.share is not None else None),
                average=money(c.average) if c.average is not None else None,
                count=c.count,
                link=_link(c.link),
            )
            for c in found.categories
        ],
        merchants=[
            MerchantLineOut(
                merchant=m.merchant,
                category=m.category,
                group=m.group,
                slot=m.slot,
                count=m.count,
                total=money(m.total),
                per_row=money(m.per_row),
                last=m.last,
                link=_link(m.link),
            )
            for m in found.merchants
        ],
        flow=[
            FlowMonthOut(
                month=m.month,
                partial=m.partial,
                income=money(m.income),
                expense=money(m.expense),
                net=money(m.net),
                people=money(m.people),
                debt=money(m.debt),
                saving=money(m.saving),
                left=money(m.left),
            )
            for m in found.flow
        ],
        forecast=_forecast(found.forecast),
    )
