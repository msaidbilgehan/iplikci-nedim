"""The category rules (F15): the rules as the Rules screen shows them, a change previewed against the ledger, and the
change written. A change is the whole rule file or one narrow edit (a named merchant, an ended payment and its
undoing, a commitment category, a merchant's own necessity); the interface previews every one before it writes it.
Reading needs a session or the token; writing, the service's own pages."""

from datetime import date
from decimal import Decimal
from typing import Annotated, Literal

from fastapi import APIRouter, Depends, Request
from pydantic import BaseModel, Field

from ...app import rules
from ...app.analysis import Analysis
from ...app.invoices import minor
from ...app.rules import Actor, Change, Necessity, RulesError, TransactionKind
from ...app.workspace import Busy, Workspace
from ..context import context_of
from ..guard import Principal
from ..models import MoneyOut
from ..problems import Problem
from .deps import only

router = APIRouter()

READ = [Depends(only(Principal.BROWSER, Principal.CLIENT))]
WRITE = [Depends(only(Principal.BROWSER))]
Name = Annotated[str, Field(min_length=1, max_length=120)]


class CategoryOut(BaseModel):
    name: str
    group: str
    slot: int  # the group's colour slot: 1–8, 0 for "Diğer"
    necessity: Necessity | None  # null: "Belirsiz" until a rule says
    regular: bool  # a commitment category (`_düzenli`)
    own: bool  # the user's rule file names it; otherwise only the rules shipped with the app do


class EndedOut(BaseModel):
    merchant: str
    month: str  # the last month with a payment, YYYY-MM
    own: bool  # the user's own rules say so; a shipped one cannot be taken back here


class MerchantNecessityOut(BaseModel):
    merchant: str
    necessity: Necessity


class CategoryRulesOut(BaseModel):
    content: str  # the user's rule file as it is (YAML, Turkish keys); "" before the first change
    categories: list[CategoryOut]
    ended: list[EndedOut]  # newest month first
    merchant_necessity: list[MerchantNecessityOut]
    history: list[str]  # the rule file's earlier versions, newest first


class WriteRulesIn(BaseModel):
    """The whole rule file, as the user edited it."""

    action: Literal["write"]
    content: str = Field(max_length=1_000_000)


class MerchantRuleIn(BaseModel):
    """A named merchant under a category: its rows get the category ("bu işyerini her zaman X say")."""

    action: Literal["merchant"]
    category: Name
    merchant: Name
    patterns: list[Annotated[str, Field(min_length=1, max_length=200)]] = Field(min_length=1, max_length=20)
    necessity: Necessity | None = None  # the merchant's own level, when it differs from its category's


class EndedIn(BaseModel):
    """A payment the user ended ("İptal ettim"): none is expected after month."""

    action: Literal["ended"]
    merchant: Name
    month: str = Field(pattern=r"^\d{4}-(0[1-9]|1[0-2])$")
    note: str = Field(default="", max_length=200)


class NotEndedIn(BaseModel):
    """A payment expected again."""

    action: Literal["not_ended"]
    merchant: Name


class CommitmentIn(BaseModel):
    """A category of commitments (its payments are regular even when the amount changes), or no longer."""

    action: Literal["commitment"]
    category: Name
    on: bool


class MerchantNecessityIn(BaseModel):
    """A merchant's own level of necessity; null takes it back to its category's."""

    action: Literal["necessity"]
    merchant: Name
    necessity: Necessity | None


RuleChangeIn = Annotated[
    WriteRulesIn | MerchantRuleIn | EndedIn | NotEndedIn | CommitmentIn | MerchantNecessityIn,
    Field(discriminator="action"),
]


class RowLabelsOut(BaseModel):
    merchant: str
    category: str
    necessity: Necessity | None
    kind: TransactionKind


class ChangedRowOut(BaseModel):
    fingerprint: str
    day: date
    description: str
    amount: MoneyOut  # TL; above zero money leaves the user
    before: RowLabelsOut
    after: RowLabelsOut


class CategoryMoveOut(BaseModel):
    before: str
    after: str
    count: int
    total: MoneyOut


class RuleChangeOut(BaseModel):
    content: str  # the rule file the change makes
    diff: str  # against the file now, as a unified diff
    changed: int  # rows whose category, necessity, kind or merchant name it changes
    moves: list[CategoryMoveOut]  # the most rows first
    examples: list[ChangedRowOut]
    saved: bool
    backup: str  # the earlier version's name in the history; "" when nothing was saved or there was none


def _money(value: Decimal) -> MoneyOut:
    return MoneyOut(minor=minor(value, "TRY"), currency="TRY")


def _out(change: Change) -> RuleChangeOut:
    def labels(found: rules.Labels) -> RowLabelsOut:
        return RowLabelsOut(
            merchant=found.merchant, category=found.category, necessity=found.necessity, kind=found.kind
        )

    return RuleChangeOut(
        content=change.content,
        diff=change.diff,
        changed=change.changed,
        moves=[
            CategoryMoveOut(before=m.before, after=m.after, count=m.count, total=_money(m.total)) for m in change.moves
        ],
        examples=[
            ChangedRowOut(
                fingerprint=e.fingerprint,
                day=e.day,
                description=e.description,
                amount=_money(e.amount),
                before=labels(e.before),
                after=labels(e.after),
            )
            for e in change.examples
        ],
        saved=change.saved,
        backup=change.backup,
    )


def _text(ws: Workspace, analysis: Analysis, body: RuleChangeIn) -> str:
    """The rule file the change makes."""
    match body:
        case WriteRulesIn():
            return body.content
        case MerchantRuleIn():
            return rules.merchant_rule(ws, body.category, body.merchant, body.patterns, body.necessity)
        case EndedIn():
            return rules.ended(ws, analysis.dataset, body.merchant, body.month, body.note)
        case NotEndedIn():
            return rules.not_ended(ws, body.merchant)
        case CommitmentIn():
            return rules.commitment(ws, body.category, body.on)
        case MerchantNecessityIn():
            return rules.merchant_necessity(ws, body.merchant, body.necessity)


@router.get("/api/rules/categories", dependencies=READ)
def category_rules(request: Request) -> CategoryRulesOut:
    """The categories with their groups, colours, necessity and commitment flags, the ended payments, the merchants'
    own levels, the user's rule file and its history."""
    try:
        found = rules.read(context_of(request).ws)
    except RulesError as exc:
        raise Problem(409, "rules_invalid", str(exc)) from exc
    return CategoryRulesOut(
        content=found.content,
        categories=[CategoryOut.model_validate(c, from_attributes=True) for c in found.categories],
        ended=[EndedOut(merchant=e.merchant, month=e.month, own=e.own) for e in found.ended],
        merchant_necessity=[MerchantNecessityOut(merchant=m, necessity=n) for m, n in found.merchant_necessity.items()],
        history=found.history,
    )


@router.post("/api/rules/categories/preview", dependencies=READ)
def preview_category_rules(request: Request, body: RuleChangeIn) -> RuleChangeOut:
    """What a change would do to the ledger: the diff, the rows it moves and from which category to which. Nothing
    is written."""
    context = context_of(request)
    try:
        analysis = context.analysis.get()
        return _out(rules.preview(context.ws, analysis.dataset, _text(context.ws, analysis, body)))
    except RulesError as exc:
        raise Problem(400, "rules_refused", str(exc)) from exc
    except Busy as exc:
        raise Problem(409, "documents_busy", "Belgeler şu an okunuyor; birazdan yeniden deneyin.") from exc


@router.put("/api/rules/categories", dependencies=WRITE)
def change_category_rules(request: Request, body: RuleChangeIn) -> RuleChangeOut:
    """Write the change: the rule file before it goes to the history, the analysis is made again, and what moved
    is returned."""
    context = context_of(request)
    try:
        text = _text(context.ws, context.analysis.get(), body)
        return _out(rules.save(context.ws, context.analysis, text, Actor.USER))
    except RulesError as exc:
        raise Problem(400, "rules_refused", str(exc)) from exc
    except Busy as exc:
        raise Problem(409, "documents_busy", "Belgeler şu an okunuyor; birazdan yeniden deneyin.") from exc
