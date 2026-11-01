"""Local web panel: the report plus a place to add documents.

    iplikci panel [--port 8643] [--ac]

Listens on 127.0.0.1 only. The address printed at start carries a one-time key; opening it sets a
session cookie, and every request needs that cookie and the panel's own Host header, so neither a web
site open in the same browser (DNS rebinding included) nor another account on the Mac can read the
data. Writes also need the panel's Origin and a custom header, which a cross-site request can only
send after a CORS preflight the panel never answers.
"""

import hmac
import html
import json
import os
import re
import secrets
import signal
import socket
import socketserver
import sys
import threading
import traceback
import webbrowser
from http.cookies import CookieError, SimpleCookie
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from urllib.parse import parse_qs, unquote, urlsplit

from . import month_end
from .app import intake
from .app import mail as email
from .app.analysis import Current, document_gaps
from .app.uploads import MAX_UPLOAD_BYTES, UPLOAD_EXTENSIONS, inbox_files, save_upload
from .app.workspace import Busy, StalePlan, Workspace
from .domain.codes import DocumentStatus
from .report import PANEL_CSP, render_html

STATE_NAME = ".panel.json"  # port, pid and address of the running panel, so a second start just opens it
# The month-end pages carry no script at all: nothing more than their own style.
MONTH_CSP = month_end.CSP + "; base-uri 'none'; form-action 'none'; frame-ancestors 'none'"
_MONTH_PAGE = re.compile(r"/" + month_end.FOLDER + r"/(\d{4}-\d{2}\.html|" + re.escape(month_end.INDEX) + ")")
_MAX_JSON = 64 * 1024
_DRAIN_LIMIT = 32 << 20  # a refused upload up to this size is read to its end so the browser gets the answer
_PLANS_KEPT = 8

_DENIED = """<!doctype html><html lang="tr"><meta charset="utf-8"><title>İplikçi Nedim</title>
<body style="font:15px/1.5 system-ui,sans-serif;max-width:560px;margin:60px auto;padding:0 20px">
<h1 style="font-size:20px">Bu panel bu bağlantıyla açılamaz</h1>
<p>Panel yalnızca başlatıldığında terminalde yazan bağlantıyla açılır (adresin sonundaki anahtarla).
Paneli yeniden açmak için <code>uv run iplikci panel --ac</code> çalıştırın.</p>
</body></html>"""


class Panel:
    """State the request threads share: the key, the latest analysis and the plans shown."""

    def __init__(self, ws: Workspace, port: int):
        self.ws = ws
        self.port = port
        self.key = secrets.token_urlsafe(24)
        self.cookie = f"iplikci_panel_{port}"  # cookies ignore the port: one name per panel
        self.hosts = {f"127.0.0.1:{port}", f"localhost:{port}"}
        self.origins = {f"http://{host}" for host in self.hosts}
        self.current = Current(ws, write=True)
        self.plans: dict[str, intake.Plan] = {}
        self._lock = threading.Lock()
        self._page: tuple[object, dict, str] | None = None  # (analysis, e-mail status, page)

    @property
    def url(self) -> str:
        return f"http://127.0.0.1:{self.port}/?anahtar={self.key}"

    def page(self) -> str:
        """The report with the panel's parts, redone when a document, the inbox, the rules or the
        e-mail setup changed (`eposta --kur` may run while the panel is open)."""
        a = self.current.get()
        status = email.status(self.ws)
        mail = {k: status.get(k) for k in ("configured", "lastRun", "lastError", "stopped")}
        with self._lock:
            if self._page and self._page[0] is a and self._page[1] == mail:
                return self._page[2]
        gaps = [
            {
                "account": g.account,
                "kind": g.kind,
                "last": g.last.isoformat(),
                "behind": g.behind,
                "months": list(g.months),
            }
            for g in document_gaps(a.dataset)
        ]
        data = {
            "inbox": str(self.ws.inbox),
            "inboxName": self.ws.inbox.name,
            "accept": sorted(UPLOAD_EXTENSIONS),
            "maxBytes": MAX_UPLOAD_BYTES,
            "pending": len(inbox_files(self.ws)),
            "gaps": gaps,
            "mail": mail,
        }
        text = render_html(a.payload, panel=data)
        with self._lock:
            self._page = (a, mail, text)
        return text

    def month_page(self, name: str) -> str | None:
        """A month-end page or their index, from the latest analysis; None for a month without a page."""
        a = self.current.get()
        if name == month_end.INDEX:
            return month_end.render_index(a.months, a.made, "/")
        me = next((m for m in a.months if m.file == name), None)
        if me is None:
            return None
        return month_end.render_month(me, a.dataset, [m.month for m in a.months], a.made, "/")

    def plan(self) -> dict:
        p = intake.plan_inbox(self.ws)
        with self._lock:
            self.plans[p.id] = p
            while len(self.plans) > _PLANS_KEPT:
                self.plans.pop(next(iter(self.plans)))
        return {"id": p.id, "items": [intake.describe(c, self.ws) for c in p.changes], "changes": len(p.changes)}

    def apply(self, plan_id: str) -> dict:
        with self._lock:
            p = self.plans.pop(plan_id, None)
            if p is not None:
                self.plans.clear()  # applying one makes every other plan stale
        if p is None:
            raise StalePlan("bu plan artık geçerli değil; gelen kutusu yeniden okunuyor")
        done = intake.apply(self.ws, p)
        self.current.refresh()
        known = [c for c in done.items if c.verdict is intake.Verdict.KNOWN and c.path is not None]
        set_aside = [c for c in done.items if c.verdict not in (intake.Verdict.STORE, intake.Verdict.KNOWN)]
        return {
            "stored": len(done.stored),
            "unreadable": sum(c.status is DocumentStatus.UNREADABLE for c in done.stored),
            "known": len(known),
            "trashed": sum(c.path is not None for c in set_aside),
            "trash": str(done.trash) if done.trash else None,
        }

    def fetch_mail(self) -> dict:
        """One e-mail fetch (at most email.MAX_MESSAGES e-mails; "more" asks for another)."""
        got = email.fetch(self.ws, wait=10)
        if got.stored:
            self.current.refresh()
        return got.as_dict() | {"lastRun": email.status(self.ws).get("lastRun")}


class _Body:
    """The request body, read at most to its declared length."""

    def __init__(self, raw, length: int):
        self.raw, self.left = raw, length

    def read(self, n: int) -> bytes:
        if self.left <= 0:
            return b""
        chunk = self.raw.read(min(n, self.left))
        self.left -= len(chunk)
        return chunk

    def drain(self) -> bool:
        """Read what is left (if not too much) so the browser can read the answer; False if it was not."""
        if self.left > _DRAIN_LIMIT:
            return False
        while self.left > 0 and self.read(1 << 20):
            pass
        return True


class _Handler(BaseHTTPRequestHandler):
    server_version = "iplikci"
    sys_version = ""

    @property
    def panel(self) -> Panel:
        return self.server.panel

    def log_message(self, format, *args) -> None:
        pass  # the terminal shows the panel's address, not every request

    # --- checks -----------------------------------------------------------------------------
    def _host_ok(self) -> bool:
        return self.headers.get("Host", "") in self.panel.hosts

    def _cookie_ok(self) -> bool:
        jar = SimpleCookie()
        try:
            jar.load(self.headers.get("Cookie", ""))
        except CookieError:
            return False
        morsel = jar.get(self.panel.cookie)
        return morsel is not None and hmac.compare_digest(morsel.value.encode(), self.panel.key.encode())

    def _write_ok(self) -> bool:
        return self.headers.get("Origin") in self.panel.origins and self.headers.get("X-Iplikci") == "1"

    # --- answers ----------------------------------------------------------------------------
    def _send(self, status: int, body: bytes, ctype: str, extra: tuple = ()) -> None:
        self.send_response(status)
        for name, value in (
            ("Content-Type", ctype),
            ("Content-Length", str(len(body))),
            ("Cache-Control", "no-store"),
            ("X-Content-Type-Options", "nosniff"),
            ("Referrer-Policy", "no-referrer"),
            ("Cross-Origin-Resource-Policy", "same-origin"),
            ("Cross-Origin-Opener-Policy", "same-origin"),
            ("X-Frame-Options", "DENY"),
            *extra,
        ):
            self.send_header(name, value)
        self.end_headers()
        self.wfile.write(body)

    def _json(self, value: dict, status: int = 200) -> None:
        self._send(status, json.dumps(value, ensure_ascii=False).encode(), "application/json; charset=utf-8")

    def _html(self, page: str, status: int = 200) -> None:
        self._send(
            status,
            page.encode(),
            "text/html; charset=utf-8",
            (("Content-Security-Policy", PANEL_CSP + "; frame-ancestors 'none'"),),
        )

    def _length(self) -> int | None:
        try:
            length = int(self.headers.get("Content-Length", ""))
        except ValueError:
            return None
        return length if length >= 0 else None

    # --- requests ---------------------------------------------------------------------------
    def do_GET(self) -> None:
        if not self._host_ok():
            return self._html(_DENIED, 403)
        url = urlsplit(self.path)
        if url.path == "/" and url.query:
            key = parse_qs(url.query).get("anahtar", [""])[0]
            if hmac.compare_digest(key.encode(), self.panel.key.encode()):
                # Into a cookie and out of the address bar (and the browser history).
                cookie = f"{self.panel.cookie}={self.panel.key}; Path=/; HttpOnly; SameSite=Strict"
                return self._send(303, b"", "text/plain; charset=utf-8", (("Location", "/"), ("Set-Cookie", cookie)))
        if not self._cookie_ok():
            return self._html(_DENIED, 403)
        if url.path == "/":
            try:
                return self._html(self.panel.page())
            except Busy as exc:
                return self._html(f"<!doctype html><meta charset=utf-8><p>{html.escape(str(exc))}</p>", 503)
        page = _MONTH_PAGE.fullmatch(url.path)
        if page:
            try:
                text = self.panel.month_page(page[1])
            except Busy as exc:
                return self._html(f"<!doctype html><meta charset=utf-8><p>{html.escape(str(exc))}</p>", 503)
            if text is None:
                return self._json({"error": "bu ayın raporu yok"}, 404)
            return self._send(200, text.encode(), "text/html; charset=utf-8", (("Content-Security-Policy", MONTH_CSP),))
        if url.path == "/favicon.ico":
            return self._send(204, b"", "image/x-icon")
        return self._json({"error": "bulunamadı"}, 404)

    def do_POST(self) -> None:
        body = _Body(self.rfile, self._length() or 0)
        if not (self._host_ok() and self._cookie_ok() and self._write_ok()):
            self.close_connection = not body.drain()
            return self._json({"error": "bu istek panelden gelmiyor"}, 403)
        path = urlsplit(self.path).path
        try:
            if path == "/api/yukle":
                return self._upload(body)
            if body.left > _MAX_JSON:
                self.close_connection = not body.drain()
                return self._json({"error": "istek çok büyük"}, 413)
            raw = body.read(_MAX_JSON)
            request = json.loads(raw or b"{}")
            if not isinstance(request, dict):
                return self._json({"error": "geçersiz istek"}, 400)
            if path == "/api/plan":
                return self._json(self.panel.plan())
            if path == "/api/uygula":
                return self._json(self.panel.apply(str(request.get("plan", ""))))
            if path == "/api/eposta":
                return self._json(self.panel.fetch_mail())
            return self._json({"error": "bulunamadı"}, 404)
        except (Busy, StalePlan, email.NotConfigured) as exc:
            return self._json({"error": str(exc)}, 409)
        except email.MailError as exc:  # the mail server refused or could not be reached
            return self._json({"error": str(exc)}, 502)
        except ValueError as exc:
            return self._json({"error": str(exc)}, 400)
        except Exception as exc:  # the panel keeps serving; the details go to the terminal  # noqa: BLE001
            traceback.print_exc(file=sys.stderr)
            return self._json({"error": f"beklenmeyen hata ({type(exc).__name__}); ayrıntı terminalde"}, 500)

    def _upload(self, body: _Body) -> None:
        if self._length() is None:
            return self._json({"error": "dosya boyutu bildirilmedi (Content-Length)"}, 411)
        name = unquote(self.headers.get("X-Dosya-Adi", ""))
        if body.left > MAX_UPLOAD_BYTES:
            self.close_connection = True
            return self._json({"error": f"dosya {MAX_UPLOAD_BYTES >> 20} MB sınırından büyük"}, 413)
        try:
            up = save_upload(self.panel.ws, name, body, body.left)
        except ConnectionError as exc:
            self.close_connection = True
            return self._json({"error": str(exc)}, 400)
        self.close_connection = not body.drain()
        return self._json({"status": up.status, "name": up.name, "reason": up.reason})


class _Server(ThreadingHTTPServer):
    daemon_threads = True
    panel: Panel

    def server_bind(self) -> None:
        # HTTPServer would look the address up for a host name; 127.0.0.1 needs no lookup.
        socketserver.TCPServer.server_bind(self)
        self.server_name, self.server_port = self.server_address[:2]


def make_server(ws: Workspace, port: int) -> tuple[_Server, Panel]:
    server = _Server(("127.0.0.1", port), _Handler)
    server.panel = Panel(ws, server.server_address[1])
    return server, server.panel


def _running(ws: Workspace) -> str | None:
    """Address of a panel of this workspace that is already running, if any."""
    try:
        state = json.loads((ws.run / STATE_NAME).read_text(encoding="utf-8"))
        if os.name != "nt":  # on Windows os.kill would end the process instead of checking it
            os.kill(int(state["pid"]), 0)
        with socket.create_connection(("127.0.0.1", int(state["port"])), timeout=0.5):
            return str(state["url"])
    except (OSError, ValueError, KeyError, TypeError):
        return None


def _write_state(ws: Workspace, panel: Panel) -> None:
    path = ws.run / STATE_NAME
    fd = os.open(path, os.O_WRONLY | os.O_CREAT | os.O_TRUNC, 0o600)  # the address holds the key
    if hasattr(os, "fchmod"):  # an older file keeps its mode on open; Windows has no such modes
        os.fchmod(fd, 0o600)
    with os.fdopen(fd, "w", encoding="utf-8") as f:
        json.dump({"pid": os.getpid(), "port": panel.port, "url": panel.url}, f)


def _remove_state(ws: Workspace) -> None:
    path = ws.run / STATE_NAME
    try:
        if json.loads(path.read_text(encoding="utf-8")).get("pid") == os.getpid():
            path.unlink()
    except (OSError, ValueError):
        pass


_STOPS = tuple(s for s in (signal.SIGTERM, getattr(signal, "SIGHUP", None)) if s is not None)  # no SIGHUP on Windows


def _ignore_stops() -> None:
    """A second signal (`kill` sent twice, Ctrl+C again) must not cut the cleanup short."""
    for sig in (*_STOPS, signal.SIGINT):
        signal.signal(sig, signal.SIG_IGN)


def _interrupt(signum, frame) -> None:
    _ignore_stops()
    raise KeyboardInterrupt


def serve(ws: Workspace, port: int | None = None, open_browser: bool = False, progress=None, read_done=None) -> int:
    running = _running(ws)
    if running:
        print(f"Panel zaten çalışıyor: {running}")
        if open_browser:
            webbrowser.open(running)
        return 0
    port = ws.port if port is None else port
    try:
        server, panel = make_server(ws, port)
    except OSError as exc:
        print(
            f"127.0.0.1:{port} kullanılamıyor ({exc.strerror}). Başka bir port deneyin: --port {port + 1}",
            file=sys.stderr,
        )
        return 1
    ws.inbox.mkdir(parents=True, exist_ok=True)
    ws.exports.mkdir(parents=True, exist_ok=True)
    print("Belgeler okunuyor…", file=sys.stderr)
    panel.current.get(progress)  # the first page should not wait for the documents
    if read_done:
        read_done()
    _write_state(ws, panel)
    for sig in _STOPS:  # `kill` or a closed terminal: clean up as for Ctrl+C
        signal.signal(sig, _interrupt)
    print(f"\nPanel: {panel.url}\nGelen belgeler: {ws.inbox}\nKapatmak için Ctrl+C.", flush=True)
    if open_browser:
        webbrowser.open(panel.url)
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        _ignore_stops()
        print("\nPanel kapatıldı.")
    finally:
        _ignore_stops()
        server.server_close()
        _remove_state(ws)
    return 0
