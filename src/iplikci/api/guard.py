"""The gate every request passes (ADR-0007), as ASGI middleware so the event stream passes it too.

1. The Host header must name the service: a site that rebinds its own name to 127.0.0.1 sends its own name.
2. The sender proves who it is: the API token (`Authorization: Bearer`, the command line and the MCP bridge) or a
   session cookie (a browser). Only the health check and the login link need neither.
3. A browser's writes must come from the service's own pages (Origin) and carry `X-Iplikci: 1`: a cross-site form
   cannot set the header, and a cross-site script can set it only after a CORS preflight the service never answers.

Every answer carries the security headers; a session whose expiry was pushed back gets its cookie again.
"""

from enum import StrEnum

from starlette.concurrency import run_in_threadpool
from starlette.datastructures import Headers, MutableHeaders
from starlette.requests import cookie_parser
from starlette.responses import HTMLResponse, Response
from starlette.types import ASGIApp, Message, Receive, Scope, Send

from ..app import access, bridge
from . import pages
from .context import Context
from .problems import problem

# The health check and the login link need no session; an extension pairs with a code and checks the service it
# paired with before it holds or sends anything (ADR-0016).
OPEN_PATHS = frozenset({"/healthz", "/giris", "/api/bridge/pair", "/api/bridge/hello"})
# A bridge's token opens the mail intake and nothing else.
BRIDGE_PATHS = frozenset({"/api/ingest/mail", "/api/ingest/mail/cursor", "/api/ingest/mail/alarm"})
SAFE_METHODS = frozenset({"GET", "HEAD", "OPTIONS"})
CSP = (
    "default-src 'self'; script-src 'self'; style-src 'self'; img-src 'self' data: blob:; connect-src 'self'; "
    "font-src 'self'; object-src 'none'; base-uri 'none'; form-action 'self'; frame-ancestors 'none'"
)
SECURITY_HEADERS = (
    ("x-content-type-options", "nosniff"),
    ("referrer-policy", "no-referrer"),
    ("x-frame-options", "DENY"),
    ("cross-origin-opener-policy", "same-origin"),
    ("cross-origin-resource-policy", "same-origin"),
    ("content-security-policy", CSP),
)


class Principal(StrEnum):
    BROWSER = "browser"  # a session cookie
    CLIENT = "client"  # the API token: the command line, the MCP bridge
    BRIDGE = "bridge"  # a paired browser extension's token: the mail intake only


def session_cookie(context: Context, token: str) -> str:
    return f"{context.cookie}={token}; Path=/; Max-Age={access.SESSION_SECONDS}; HttpOnly; SameSite=Strict"


class Guard:
    def __init__(self, app: ASGIApp, context: Context) -> None:
        self.app = app
        self.context = context

    async def __call__(self, scope: Scope, receive: Receive, send: Send) -> None:
        if scope["type"] == "lifespan":
            await self.app(scope, receive, send)
            return
        if scope["type"] != "http":  # no websockets
            return
        send = _with_headers(send, SECURITY_HEADERS)
        headers = Headers(scope=scope)
        if headers.get("host", "") not in self.context.hosts:
            await problem(403, "host_denied", "Servise bu adresle ulaşılamaz.")(scope, receive, send)
            return
        path = str(scope["path"])
        if path in OPEN_PATHS:
            await self.app(scope, receive, send)
            return
        principal, renewed = await run_in_threadpool(self._identify, headers)
        if principal is None:
            await self._refuse(path)(scope, receive, send)
            return
        if (principal is Principal.BRIDGE) != (path in BRIDGE_PATHS):
            await problem(403, "forbidden", "Bu işlem bu oturumla yapılamaz.")(scope, receive, send)
            return
        if scope["method"] not in SAFE_METHODS and principal is Principal.BROWSER and not self._own_page(headers):
            await problem(403, "write_denied", "Bu istek yalnızca İplikçi Nedim'in kendi sayfalarından yapılabilir.")(
                scope, receive, send
            )
            return
        scope.setdefault("state", {})["principal"] = principal
        if renewed is not None:
            send = _with_headers(send, (("set-cookie", session_cookie(self.context, renewed)),))
        await self.app(scope, receive, send)

    def _identify(self, headers: Headers) -> tuple[Principal | None, str | None]:
        """Who sends the request, and the session token when its expiry was pushed back."""
        scheme, _, token = headers.get("authorization", "").partition(" ")
        if scheme.lower() == "bearer":
            token = token.strip()
            if access.same_token(token, self.context.token):
                return Principal.CLIENT, None
            return (Principal.BRIDGE if bridge.identify(self.context.ws, token) else None), None
        session = cookie_parser(headers.get("cookie", "")).get(self.context.cookie, "")
        if not session:
            return None, None
        with self.context.ws.db() as db:
            state = access.check_session(db, session)
        if state is access.SessionState.NONE:
            return None, None
        return Principal.BROWSER, session if state is access.SessionState.RENEWED else None

    def _own_page(self, headers: Headers) -> bool:
        return headers.get("origin", "") in self.context.origins and headers.get("x-iplikci", "") == "1"

    @staticmethod
    def _refuse(path: str) -> Response:
        if path.startswith("/api/"):
            return problem(401, "unauthenticated", "Oturum açılmamış ya da süresi dolmuş.")
        return HTMLResponse(pages.SIGN_IN_FIRST, status_code=401)


def _with_headers(send: Send, extra: tuple[tuple[str, str], ...]) -> Send:
    """send, adding the headers the answer does not set itself (Set-Cookie is always added)."""

    async def sending(message: Message) -> None:
        if message["type"] == "http.response.start":
            headers = MutableHeaders(scope=message)
            for name, value in extra:
                if name == "set-cookie" or name not in headers:
                    headers.append(name, value)
            if "cache-control" not in headers:
                headers.append("cache-control", "no-store")
        await send(message)

    return sending
