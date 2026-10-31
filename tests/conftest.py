"""A synthetic workspace (settings, rules, document folders), a synthetic TEB account export and a
fake IMAP server with synthetic bank e-mails.

Nothing here touches the real Trash, the system keyring or the network: every test collects
set-aside files in its own folder, and the e-mail fetch talks to FakeImap.
"""

import imaplib
import re
from datetime import date
from email.message import EmailMessage
from pathlib import Path

import pytest

from iplikci import duzenle, email_fetch
from iplikci.parsers.common import set_business_names
from iplikci.workspace import Workspace

RULES = """\
# Deneme kuralları
Yeme & İçme:
  Kafe & Kahve:
    Örnek Kahve: [ORNEK KAHVE]  # isimli işletme
    _: [KAHVE]
  Market & Gıda:
    _: [MARKET]
  Boş Kategori: {}

_gereklilik:
  Gerekli:
    - Market & Gıda
  İsteğe bağlı:
    - Kafe & Kahve

_biten:
  Eski Abonelik: 2025-01  # örnek not
"""

HOLDER = "ÖRNEK KULLANICI"

# Transfers to people: a landlord, family, a debt repayment, a pension fund (all names made up).
PEOPLE_RULES = """\
Ev & Faturalar:
  Kira:
    Ev kirası (Veli Örneksoy): [VELI ORNEKSOY]
    _: [KIRA]
Aile & Kişiler:
  Borç Geri Ödemesi:
    _tür: borç
    Borç iadesi: [BORC IADE, BORC ODEME]
  Aile:
    _tür: kişi
    Ayşe Soyadoğlu: [AYSE SOYADOGLU]
Birikim & Yatırım:
  Bireysel Emeklilik (BES):
    _tür: yatırım
    Anadolu Hayat: [ANADOLU HAYAT]

_gereklilik:
  Gerekli:
    - Kira
"""


def teb_export(
    rows: list[tuple], number: str = "123456789", holder: str = HOLDER, period: str = "01/01/2026 - 31/01/2026"
) -> bytes:
    """A CEPTETEB "Hesap Hareketlerim" export (HTML saved as .xls), rows newest first:
    (date, description, amount, balance)."""
    info = [
        ("Şube", "999-DENEME"),
        ("Hesap", number),
        ("IBAN", f"TR00000320000000000{number[-7:]}"),
        ("Hesap Türü", "Vadesiz TL"),
        ("Hesap Sahibi", holder),
        ("Bakiye", "0,00"),
    ]
    head = "".join(f"<tr><td>{k}</td><td>{v}</td></tr>" for k, v in info)
    body = "".join(
        f"<tr><td>{d}</td><td>{d}</td><td>10:00</td><td>{desc}</td><td>{amount}</td><td>{balance}</td><td>{i}</td></tr>"
        for i, (d, desc, amount, balance) in enumerate(rows)
    )
    return (
        "<html><body><table><tr><td></td><td>Hesap Hareketlerim</td></tr>" + head + "</table>"
        f'<div class="prompt"> {period} tarihleri arasındaki işlemleriniz aşağıdadır.</div>'
        "<table><tr><td>Tarih</td><td>Valör</td><td>Saat</td><td>Açıklama</td><td>Tutar</td><td>Bakiye</td>"
        "<td>Dekont</td></tr>" + body + "</table></body></html>"
    ).encode("utf-8")


JANUARY = [  # verified: 0 + 1.000 = 1.000, 1.000 - 120 = 880
    ("20/01/2026", "KAHVECI DUKKAN", "-120,00", "880,00"),
    ("05/01/2026", "ORNEK SIRKET den gelen havale", "1.000,00", "1.000,00"),
]


FEBRUARY = teb_export([("10/02/2026", "MARKET ALISVERIS", "-80,00", "800,00")], period="01/02/2026 - 28/02/2026")


@pytest.fixture(autouse=True)
def private_trash(tmp_path_factory, monkeypatch):
    trash = tmp_path_factory.mktemp("cop-kutusu")
    monkeypatch.setattr(duzenle, "MAC_TRASH", trash)
    return trash


@pytest.fixture(autouse=True)
def no_business_names():
    """The company names live in module state that a workspace sets: every test starts and ends without any."""
    set_business_names([])
    yield
    set_business_names([])


@pytest.fixture(autouse=True)
def no_keyring_or_network(monkeypatch):
    def refuse(*args):
        raise AssertionError("a test reached the system keyring or the network")

    monkeypatch.setattr(email_fetch, "_keyring", refuse)
    monkeypatch.setattr(email_fetch, "connect", refuse)
    monkeypatch.delenv(email_fetch.PASSWORD_ENV, raising=False)


@pytest.fixture
def ws(tmp_path) -> Workspace:
    (tmp_path / "Bankalar").mkdir()
    (tmp_path / "Gelen").mkdir()
    (tmp_path / "kategoriler.yaml").write_text(RULES, encoding="utf-8")
    (tmp_path / "ayarlar.toml").write_text(
        'kaynaklar = ["Bankalar"]\nbelge_klasoru = "Bankalar"\ngelen_klasoru = "Gelen"\ncikti = "cikti"\n'
        'kurallar = "kategoriler.yaml"\n',
        encoding="utf-8",
    )
    return Workspace.load(tmp_path)


def put(path: Path, data: bytes | str) -> Path:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_bytes(data.encode() if isinstance(data, str) else data)
    return path


# --- e-mail -------------------------------------------------------------------------------------------

ADDRESS = "kullanici@example.com"
APP_PASSWORD = "abcdefghijklmnop"


def bank_mail(
    attachment: bytes | None,
    name: str = "HesapHareketleri.xls",
    sender: str = "bilgi@teb.com.tr",
    results: tuple[str, ...] | None = None,
) -> bytes:
    """A bank e-mail as Gmail stores it: its own Authentication-Results on top (DMARC pass unless
    results say otherwise), the statement attached."""
    domain = sender.rpartition("@")[2]
    msg = EmailMessage()
    if results is None:
        results = (
            (
                f"mx.google.com; dkim=pass header.i=@{domain}; spf=pass smtp.mailfrom={domain}; "
                f"dmarc=pass (p=REJECT sp=REJECT dis=NONE) header.from={domain}"
            ),
        )
    for line in results:
        msg["Authentication-Results"] = line
    msg["From"] = f"Banka <{sender}>"
    msg["To"] = ADDRESS
    msg["Subject"] = "Hesap hareketleriniz"
    msg["Date"] = "Mon, 02 Feb 2026 10:00:00 +0300"
    msg.set_content("Hesap hareketleriniz ektedir.")
    if attachment is not None:
        msg.add_attachment(attachment, maintype="application", subtype="vnd.ms-excel", filename=name)
    return msg.as_bytes()


class FakeImap:
    """What the fetch uses of imaplib.IMAP4_SSL, over a dict of messages by UID; every command is
    recorded. Search ignores the sender criteria: the fetch must check every sender itself."""

    def __init__(self, gmail: bool = True):
        self.messages: dict[int, bytes] = {}
        self.uidvalidity = 7
        self.password = APP_PASSWORD
        self.capabilities = ("IMAP4REV1", "IDLE", "X-GM-EXT-1") if gmail else ("IMAP4REV1", "IDLE")
        self.commands: list[tuple] = []

    def login(self, user: str, password: str):
        self.commands.append(("LOGIN", user))
        if password != self.password:
            raise imaplib.IMAP4.error(b"[AUTHENTICATIONFAILED] Invalid credentials (Failure)")
        return "OK", [b"authenticated (Success)"]

    def list(self):
        return "OK", [
            b'(\\HasNoChildren) "/" "INBOX"',
            b'(\\HasNoChildren \\Sent) "/" "[Gmail]/G&APY-nderilmi&AV8- Postalar"',
            b'(\\All \\HasNoChildren) "/" "[Gmail]/T&APw-m Postalar"',
        ]

    def select(self, mailbox: str, readonly: bool = False):
        self.commands.append(("SELECT", mailbox, readonly))
        return "OK", [str(len(self.messages)).encode()]

    def response(self, code: str):
        return code, [str(self.uidvalidity).encode()]

    def uid(self, command: str, *args: str):
        self.commands.append(("UID", command, *args))
        if command == "SEARCH":
            low = int(re.search(r"UID (\d+):\*", " ".join(args))[1])
            hits = [u for u in sorted(self.messages) if u >= low] or sorted(self.messages)[-1:]  # n:* holds the newest
            return "OK", [" ".join(map(str, hits)).encode()]
        uids = [int(u) for u in args[0].split(",")]
        if command == "FETCH" and args[1] == "(RFC822.SIZE)":
            return "OK", [f"{i} (UID {u} RFC822.SIZE {len(self.messages[u])})".encode() for i, u in enumerate(uids, 1)]
        if command == "FETCH" and args[1] == "(BODY.PEEK[])":
            raw = self.messages[uids[0]]
            return "OK", [(f"1 (UID {uids[0]} BODY[] {{{len(raw)}}}".encode(), raw), b")"]
        raise AssertionError(f"the fetch must not send {command} {args}")

    def logout(self):
        self.commands.append(("LOGOUT",))
        return "BYE", [b"LOGOUT Requested"]


@pytest.fixture
def imap(monkeypatch) -> FakeImap:
    """A fake mail server; passwords "stored in the keyring" land in imap.stored."""
    server = FakeImap()
    server.stored = {}
    monkeypatch.setattr(email_fetch, "connect", lambda acc: server)
    monkeypatch.setattr(
        email_fetch, "store_password", lambda address, secret: server.stored.update({address: secret}) or True
    )
    monkeypatch.setattr(email_fetch, "load_password", lambda address: server.stored[address])
    monkeypatch.setattr(email_fetch, "delete_password", lambda address: server.stored.pop(address, None))
    return server


@pytest.fixture
def mail(ws, imap) -> FakeImap:
    """ws with an e-mail account set up (e-mails from 2026-01-01 on)."""
    email_fetch.setup(ws, ADDRESS, APP_PASSWORD, date(2026, 1, 1))
    imap.commands.clear()
    return imap


# --- synthetic PDFs ---------------------------------------------------------------------------------

_UNICODE_MAP = (
    b"/CIDInit /ProcSet findresource begin 12 dict begin begincmap\n"
    b"/CIDSystemInfo << /Registry (Adobe) /Ordering (UCS) /Supplement 0 >> def\n"
    b"/CMapName /Adobe-Identity-UCS def /CMapType 2 def\n"
    b"1 begincodespacerange <0000> <FFFF> endcodespacerange\n"
    b"1 beginbfrange <0020> <02FF> <0020> endbfrange\n"
    b"endcmap CMapName currentdict /CMap defineresource pop end end"
)
CHAR = 4.5  # width of every character at the default size: half an em of 9 points


def text_pdf(*pages: list[tuple[float, float, str]], size: float = 9.0) -> bytes:
    """A PDF whose pages hold the given text runs, (x, top, text) in points from the top left as
    pdfplumber reports them. Its font maps each character to itself (Turkish letters too) and
    gives every one the same width, so a run's words land where a bank's layout puts them."""
    height = 842
    objects = [b"<< /Type /Catalog /Pages 2 0 R >>", b""]  # the page tree follows once the pages exist

    def add(body: bytes) -> int:
        objects.append(body)
        return len(objects)

    def stream(data: bytes) -> bytes:
        return b"<< /Length %d >>\nstream\n%s\nendstream" % (len(data), data)

    descriptor = add(
        b"<< /Type /FontDescriptor /FontName /Deneme /Flags 32 /FontBBox [0 -200 500 800] "
        b"/ItalicAngle 0 /Ascent 800 /Descent -200 /CapHeight 700 /StemV 80 >>"
    )
    glyphs = add(
        b"<< /Type /Font /Subtype /CIDFontType2 /BaseFont /Deneme /CIDSystemInfo << /Registry (Adobe) "
        b"/Ordering (Identity) /Supplement 0 >> /FontDescriptor %d 0 R /DW 500 /CIDToGIDMap /Identity >>" % descriptor
    )
    font = add(
        b"<< /Type /Font /Subtype /Type0 /BaseFont /Deneme /Encoding /Identity-H /DescendantFonts [%d 0 R] "
        b"/ToUnicode %d 0 R >>" % (glyphs, add(stream(_UNICODE_MAP)))
    )
    kids = []
    for runs in pages:
        ops = b"".join(
            b"BT /F1 %.1f Tf 1 0 0 1 %.2f %.2f Tm <%s> Tj ET\n"
            % (size, x, height - top - 0.8 * size, text.encode("utf-16-be").hex().encode())
            for x, top, text in runs
        )
        content = add(stream(ops))
        kids.append(
            add(
                b"<< /Type /Page /Parent 2 0 R /MediaBox [0 0 595 %d] /Resources << /Font << /F1 %d 0 R >> >> "
                b"/Contents %d 0 R >>" % (height, font, content)
            )
        )
    objects[1] = b"<< /Type /Pages /Kids [%s] /Count %d >>" % (b" ".join(b"%d 0 R" % k for k in kids), len(kids))
    out, offsets = b"%PDF-1.4\n", []
    for number, body in enumerate(objects, 1):
        offsets.append(len(out))
        out += b"%d 0 obj\n%s\nendobj\n" % (number, body)
    xref = len(out)
    out += b"xref\n0 %d\n0000000000 65535 f \n" % (len(objects) + 1)
    out += b"".join(b"%010d 00000 n \n" % o for o in offsets)
    return out + b"trailer\n<< /Size %d /Root 1 0 R >>\nstartxref\n%d\n%%%%EOF\n" % (len(objects) + 1, xref)


def right(x1: float, top: float, text: str) -> tuple[float, float, str]:
    """A right-aligned run ending at x1, like the amount columns of a statement."""
    return x1 - len(text) * CHAR, top, text
