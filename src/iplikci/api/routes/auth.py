"""Coming in and going out (ADR-0007): a one-time login link becomes a session cookie."""

from fastapi import APIRouter, Depends, Request
from starlette.responses import HTMLResponse, RedirectResponse, Response

from ...app import access
from .. import pages
from ..context import context_of
from ..guard import Principal, session_cookie
from ..models import LoginLink
from .deps import only

router = APIRouter()


@router.get("/giris", include_in_schema=False)
def login(request: Request, anahtar: str = "") -> Response:
    """Turn a live login key into a session; the key leaves the address bar with the redirect."""
    context = context_of(request)
    if not context.keys.redeem(anahtar):
        return HTMLResponse(pages.LOGIN_EXPIRED, status_code=403)
    with context.ws.db() as db:
        token = access.open_session(db)
    response = RedirectResponse("/", status_code=303)
    response.headers.append("set-cookie", session_cookie(context, token))
    return response


@router.post("/api/login-links", dependencies=[Depends(only(Principal.CLIENT))])
def login_link(request: Request) -> LoginLink:
    """A one-time login link for the browser, valid for two minutes (`iplikci ac`)."""
    context = context_of(request)
    return LoginLink(url=context.login_url(context.keys.issue()))


@router.post("/api/logout", status_code=204, dependencies=[Depends(only(Principal.BROWSER))])
def logout(request: Request) -> Response:
    context = context_of(request)
    token = request.cookies.get(context.cookie, "")
    with context.ws.db() as db:
        access.close_session(db, token)
    response = Response(status_code=204)
    response.headers.append("set-cookie", f"{context.cookie}=; Path=/; Max-Age=0; HttpOnly; SameSite=Strict")
    return response
