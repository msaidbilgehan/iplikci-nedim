"""The interface (web/, ADR-0008) as the service serves it, and the pages a browser sees when it cannot come in.

The interface is built into the package's ui/ folder (`npm run build` in web/): its files are served as they are,
and every other page address gets index.html, so the single-page app opens on any of its addresses. Its hashed
files never change and may be kept by the browser; its service worker (sw.js) keeps the app shell, never the API's
answers, and is asked again on every visit (no-store). A development copy that was never built says so on its home
page. The pages here carry no script, no style and no external resource (the CSP allows none inline); the user
never needs a terminal (K14)."""

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
<title>İplikçi Nedim</title></head>
<body>
<h1>{title}</h1>
{body}
</body>
</html>"""

SIGN_IN_FIRST = _PAGE.format(
    title="Önce giriş yapın",
    body="<p>Bu sayfa İplikçi Nedim'in açtığı giriş bağlantısıyla açılır. Arayüzü İplikçi Nedim'den yeniden açın.</p>",
)

LOGIN_EXPIRED = _PAGE.format(
    title="Bu giriş bağlantısı artık geçerli değil",
    body=(
        "<p>Giriş bağlantıları tek kullanımlıktır ve iki dakika geçerlidir. Arayüzü İplikçi Nedim'den yeniden açın;"
        " yeni bir bağlantı açılır.</p>"
    ),
)

NOT_BUILT = _PAGE.format(
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
