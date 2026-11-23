"""The to-do list (F19) for the Yapılacaklar screen and the dashboard's number: every item with the steps that
settle it, and taking items off the list or putting them back, one or many at once. Reading needs a session or the
token; changing, the service's own pages."""

from typing import Annotated

from fastapi import APIRouter, Depends, Query, Request
from pydantic import BaseModel, Field

from ...app import todos
from ...app.invoices import minor
from ...app.todos import Actor, TodoAction, TodoKind
from ...app.workspace import Busy
from ..context import context_of
from ..guard import Principal
from ..models import LinkOut, MoneyOut, link_out
from ..problems import Problem
from .deps import only

router = APIRouter()

READ = [Depends(only(Principal.BROWSER, Principal.CLIENT))]
WRITE = [Depends(only(Principal.BROWSER))]


class TodoOut(BaseModel):
    key: str  # what it stands for; the same thing keeps its key
    kind: TodoKind
    title: str
    detail: str  # what it is, with its numbers and window
    count: int  # the rows or documents it stands for
    amount: MoneyOut | None  # their total in TL, where it applies
    target: str  # a merchant, a row's fingerprint, a document's sha256, an account or a reader
    link: LinkOut | None  # where the interface shows it
    actions: list[TodoAction]  # in the order to offer them
    prompt: str  # a request to paste into Claude with the MCP server connected; "" when it offers none
    ignored: bool  # the user took it off the list


class TodosOut(BaseModel):
    items: list[TodoOut]  # by kind in F19's order
    counts: dict[TodoKind, int]  # on the list, by kind: what the user took off is not counted
    ignored: int  # how many the user took off


Key = Annotated[str, Field(min_length=1, max_length=1000)]


class TodoIgnoredIn(BaseModel):
    keys: Annotated[list[Key], Field(min_length=1, max_length=1000)]  # the items the user chose, together
    ignored: bool  # true takes them off the list, false puts them back


@router.get("/api/todos", dependencies=READ)
def todo_list(request: Request, with_ignored: bool = Query(False)) -> TodosOut:
    """What keeps the data from being complete and right; with_ignored also lists what the user took off."""
    context = context_of(request)
    try:
        found = todos.items(context.ws, context.analysis.get(), context.today(), with_ignored=True)
    except Busy as exc:
        raise Problem(409, "documents_busy", "Belgeler şu an okunuyor; birazdan yeniden deneyin.") from exc
    counts = dict.fromkeys(TodoKind, 0)
    for item in found:
        if not item.ignored:
            counts[item.kind] += 1
    return TodosOut(
        items=[
            TodoOut(
                key=t.key,
                kind=t.kind,
                title=t.title,
                detail=t.detail,
                count=t.count,
                amount=MoneyOut(minor=minor(t.amount, "TRY"), currency="TRY") if t.amount is not None else None,
                target=t.target,
                link=link_out(t.link),
                actions=list(t.actions),
                prompt=t.prompt,
                ignored=t.ignored,
            )
            for t in found
            if with_ignored or not t.ignored
        ],
        counts=counts,
        ignored=sum(t.ignored for t in found),
    )


@router.post("/api/todos/ignored", status_code=204, dependencies=WRITE)
def todo_ignored(request: Request, body: TodoIgnoredIn) -> None:
    """Take items off the list, or put them back, all at once; the audit log keeps each."""
    todos.ignore(context_of(request).ws, body.keys, body.ignored, Actor.USER)
