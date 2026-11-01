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

from iplikci import email_fetch
from iplikci.demo import teb_export
from iplikci.parsers.common import set_business_names
from iplikci.vault import trash as vault_trash
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


JANUARY = [  # verified: 0 + 1.000 = 1.000, 1.000 - 120 = 880
    ("20/01/2026", "KAHVECI DUKKAN", "-120,00", "880,00"),
    ("05/01/2026", "ORNEK SIRKET den gelen havale", "1.000,00", "1.000,00"),
]


FEBRUARY = teb_export([("10/02/2026", "MARKET ALISVERIS", "-80,00", "800,00")], period="01/02/2026 - 28/02/2026")


@pytest.fixture(autouse=True)
def private_trash(tmp_path_factory, monkeypatch):
    trash = tmp_path_factory.mktemp("cop-kutusu")
    monkeypatch.setattr(vault_trash, "MAC_TRASH", trash)
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
