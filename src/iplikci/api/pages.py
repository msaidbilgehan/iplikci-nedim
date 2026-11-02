"""The interface (web/, ADR-0008) as the service serves it, and the pages a browser sees when it cannot come in.

The interface is built into the package's ui/ folder (`npm run build` in web/): its files are served as they are,
and every other page address gets index.html, so the single-page app opens on any of its addresses. Its hashed
files never change and may be kept by the browser; its service worker (sw.js) keeps the app shell, never the API's
answers, and is asked again on every visit (no-store). A development copy that was never built says so on its home
page. The pages here carry no script, no style and no external resource (the CSP allows none inline), only the logo
and the tab's icons, which open without a session; the user never needs a terminal (K14). The sign-in pages carry a
title of their own: the browser extension tells a tab that shows one from a tab that shows the interface by it, and
opens a login link there (ADR-0019)."""

import mimetypes
from pathlib import Path

from fastapi import APIRouter, Request
from starlette.exceptions import HTTPException
from starlette.responses import FileResponse, HTMLResponse, Response

from .context import context_of

router = APIRouter(include_in_schema=False)

_IMMUTABLE = {"cache-control": "private, max-age=31536000, immutable"}
mimetypes.add_type("application/manifest+json", ".webmanifest")  # the PWA's manifest; Python's table lacks it
_NOT_PAGES = ("api/", "giris", "healthz")

_PAGE = """<!doctype html>
<html lang="tr">
<head><meta charset="utf-8"><meta name="viewport" content="width=device-width, initial-scale=1">
<meta name="color-scheme" content="light dark">
<link rel="icon" href="/favicon-32.png" type="image/png" sizes="32x32">
<link rel="icon" href="/favicon-16.png" type="image/png" sizes="16x16">
<title>{tab}</title></head>
<body>
<p><img src="/logo.png" alt="İplikçi Nedim" width="64" height="64"></p>
<h1>{title}</h1>
{body}
</body>
</html>"""

# The browser extension looks for this title (extension/src/bridge/panel.ts): the interface's own tabs are called
# "<screen> · İplikçi Nedim".
SIGN_IN_TITLE = "Giriş · İplikçi Nedim"
# Where the interface opens from, as the pages a browser without a session sees say it.
_OPENED_FROM = (
    "Arayüzü İplikçi Nedim uygulamasını açarak ya da tarayıcı eklentisinin penceresindeki “İplikçi Nedim'i aç”"
    " düğmesiyle açın"
)

SIGN_IN_FIRST = _PAGE.format(
    tab=SIGN_IN_TITLE,
    title="Önce giriş yapın",
    body=f"<p>Bu sayfa İplikçi Nedim'in verdiği tek kullanımlık bir giriş bağlantısıyla açılır. {_OPENED_FROM}.</p>",
)

LOGIN_EXPIRED = _PAGE.format(
    tab=SIGN_IN_TITLE,
    title="Bu giriş bağlantısı artık geçerli değil",
    body=(
        f"<p>Giriş bağlantıları tek kullanımlıktır ve iki dakika geçerlidir. {_OPENED_FROM}; yeni bir bağlantı"
        " açılır.</p>"
    ),
)

NOT_BUILT = _PAGE.format(
    tab="Arayüz derlenmemiş · İplikçi Nedim",
    title="İplikçi Nedim çalışıyor",
    body="<p>Servis bu bilgisayarda çalışıyor. Bu geliştirme kopyasında arayüz derlenmemiş (web/ klasöründe"
    " <code>npm run build</code>).</p>",
)


@router.get("/{path:path}")
def interface(request: Request, path: str) -> Response:
    if path.startswith(_NOT_PAGES):  # an address of the API, answered as its own unknown addresses are
        raise HTTPException(404)
    ui = context_of(request).ui
    index = ui / "index.html"
    if not index.is_file():
        return HTMLResponse(NOT_BUILT)
    found = _file(ui, path)
    if found is not None:
        return FileResponse(found, headers=_IMMUTABLE if path.startswith("assets/") else None)
    if "." in path.rsplit("/", 1)[-1]:  # a file the build does not have, not a page address
        raise HTTPException(404)
    return FileResponse(index)


def _file(ui: Path, path: str) -> Path | None:
    """The built file at path, never one outside ui."""
    if not path:
        return None
    root = ui.resolve()
    candidate = (root / path).resolve()
    return candidate if candidate.is_relative_to(root) and candidate.is_file() else None
