"""The few pages the service serves before the interface (web/) exists: the home page's stand-in and the pages a
browser sees when it cannot come in. No script, no style, no external resource (the CSP allows none inline); the
user never needs a terminal (K14)."""

from fastapi import APIRouter
from starlette.responses import HTMLResponse

router = APIRouter(include_in_schema=False)

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

HOME = _PAGE.format(
    title="İplikçi Nedim çalışıyor",
    body="<p>Servis bu bilgisayarda çalışıyor. Arayüz yakında bu sayfada açılacak.</p>",
)


@router.get("/")
def home() -> HTMLResponse:
    return HTMLResponse(HOME)
