"""The IMAP connector (ADR-0015): only verified senders, the mailbox untouched, each message once, a refused login
never tried again, and IDLE asking for a fetch as soon as mail arrives."""

import io
import os
import socket
import stat
import threading
import time
import zipfile
from datetime import date

import pytest
from fastapi.testclient import TestClient

from iplikci import cli
from iplikci.api.app import create_app
from iplikci.api.context import Context
from iplikci.app import background, kinds, reading
from iplikci.app import mail as mail_app
from iplikci.app.workspace import Workspace
from iplikci.domain.codes import DocumentStatus, SourceKind
from iplikci.fakes import teb
from iplikci.fakes.files import text_pdf
from iplikci.ingest.mail import imap as protocol
from iplikci.ingest.mail.idle import IdleWatcher, WatchTarget
from iplikci.ingest.mail.imap import Account, LoginRefused, MailError, search_criteria
from iplikci.parsers import registry
from iplikci.service import client, instance
from iplikci.settings import config
from iplikci.settings.config import SettingsError
from iplikci.storage import documents, events, jobs
from iplikci.storage import mail as mail_store

from conftest import ADDRESS, APP_PASSWORD, FEBRUARY, JANUARY, FakeImap, add, bank_mail


def with_settings(ws: Workspace, text: str) -> Workspace:
    ws.layout.settings.write_text(text, encoding="utf-8")
    return Workspace.load(ws.home)


def bodies_fetched(server) -> list[str]:
    return [c[2] for c in server.commands if c[:2] == ("UID", "FETCH") and c[3] == "(BODY.PEEK[])"]


def kept(ws: Workspace) -> list[documents.DocumentRow]:
    with ws.db() as db:
        return documents.every(db)


def names(ws: Workspace) -> list[str]:
    return sorted(d.name for d in kept(ws))


def test_a_verified_bank_mail_goes_into_the_vault_whole(ws, mail):
    mail.messages[101] = bank_mail(teb.account_export(JANUARY))
    got = mail_app.fetch(ws)
    assert (got.scanned, got.stored, got.documents, got.unverified) == (1, 1, 2, 0)
    assert got.message == "1 yeni e-posta okundu; 1 ileti arşive alındı (2 yeni belge)"
    assert got.folder == "[Gmail]/Tüm Postalar"  # All Mail, found by its \All flag in any language
    statement = next(d for d in kept(ws) if d.name == "HesapHareketleri.xls")
    assert statement.status is DocumentStatus.PROCESSED and ws.vault.read(statement.sha256) == teb.account_export(
        JANUARY
    )
    with ws.db() as db:
        [source] = documents.sources(db, statement.sha256)
    assert (source.kind, source.origin, source.sender) == (
        SourceKind.EMAIL,
        "E-posta 2026-02-02 teb.com.tr › HesapHareketleri.xls",
        "teb.com.tr",
    )


def test_the_mailbox_is_only_read(ws, mail):
    mail.messages[101] = bank_mail(teb.account_export(JANUARY))
    mail_app.fetch(ws)
    assert ("SELECT", '"[Gmail]/T&APw-m Postalar"', True) in mail.commands  # EXAMINE: read-only
    sent = {c[1] if c[0] == "UID" else c[0] for c in mail.commands}
    assert sent == {"LOGIN", "SELECT", "SEARCH", "FETCH", "LOGOUT"}  # never STORE, COPY, MOVE or EXPUNGE
    assert bodies_fetched(mail) == ["101"]  # BODY.PEEK: not even marked as read


def test_mail_whose_sender_is_not_verified_is_counted_and_dropped(ws, mail):
    january = teb.account_export(JANUARY)
    mail.messages |= {
        101: bank_mail(january, results=("mx.google.com; dmarc=fail (p=NONE) header.from=teb.com.tr",)),
        # A forged "pass" below Gmail's own verdict: only the topmost header counts.
        102: bank_mail(
            january,
            results=(
                "mx.google.com; dmarc=fail (p=NONE) header.from=teb.com.tr",
                "mx.google.com; dmarc=pass header.from=teb.com.tr",
            ),
        ),
        103: bank_mail(january, results=("mx.saldirgan.example; dmarc=pass header.from=teb.com.tr",)),
        104: bank_mail(january, results=()),
        105: bank_mail(january, results=("mx.google.com; dmarc=pass header.from=baska.example",)),
    }
    got = mail_app.fetch(ws)
    assert (got.scanned, got.unverified, got.stored) == (5, 5, 0)
    assert kept(ws) == [] and "5 e-postanın göndereni doğrulanamadı" in got.message


def test_mail_from_other_senders_is_not_even_counted(ws, mail):
    mail.messages[101] = bank_mail(teb.account_export(JANUARY), sender="kampanya@teb.com.tr.saldirgan.example")
    mail.messages[102] = bank_mail(teb.account_export(JANUARY), sender="arkadas@example.com")
    got = mail_app.fetch(ws)
    assert (got.scanned, got.stored) == (0, 0) and got.message == "yeni e-posta yok"


def test_a_subdomain_of_a_bank_counts(ws, mail):
    mail.messages[101] = bank_mail(teb.account_export(JANUARY), sender="ekstre@ileti.teb.com.tr")
    assert mail_app.fetch(ws).stored == 1


def test_each_message_is_read_once(ws, mail):
    mail.messages[101] = bank_mail(teb.account_export(JANUARY))
    assert mail_app.fetch(ws).stored == 1
    mail.messages[102] = bank_mail(FEBRUARY)
    mail.commands.clear()
    assert mail_app.fetch(ws).stored == 1 and bodies_fetched(mail) == ["102"]
    mail.commands.clear()
    assert mail_app.fetch(ws).message == "yeni e-posta yok" and bodies_fetched(mail) == []


def test_a_new_mailbox_generation_is_read_again_without_keeping_twice(ws, mail):
    mail.messages[101] = bank_mail(teb.account_export(JANUARY))
    mail_app.fetch(ws)
    mail.uidvalidity = 8  # the server renumbered the mailbox: the old position means nothing
    again = mail_app.fetch(ws)
    assert (again.again, again.scanned, again.stored, again.known) == (True, 1, 0, 1)
    assert "1 e-posta baştan okundu" in again.message and len(kept(ws)) == 2


def test_an_attachment_already_in_the_vault_is_not_kept_again(ws, mail):
    add(ws, "ocak.xls", teb.account_export(JANUARY))
    mail.messages[101] = bank_mail(teb.account_export(JANUARY))
    got = mail_app.fetch(ws)
    assert (got.stored, got.documents) == (1, 1)  # the message is new, its statement is not
    assert names(ws) == ["E-posta 2026-02-02 teb.com.tr.eml", "ocak.xls"]


def test_zip_attachments_are_opened_in_memory(ws, mail):
    buf = io.BytesIO()
    with zipfile.ZipFile(buf, "w") as zf:
        zf.writestr("ekstreler/HesapHareketleri.xls", teb.account_export(JANUARY))
        zf.writestr("okubeni.txt", "belge değil")
    mail.messages[101] = bank_mail(buf.getvalue(), name="ekstreler.zip")
    mail_app.fetch(ws)
    assert names(ws) == ["E-posta 2026-02-02 teb.com.tr.eml", "HesapHareketleri.xls"]  # the zip itself is not kept


def reading_from_start(ws: Workspace) -> bool:
    with ws.db() as db:
        return mail_app.first_read(db, config.load(ws.layout.settings))


def test_a_large_backlog_is_read_in_parts(ws, mail, monkeypatch):
    monkeypatch.setattr(mail_app, "MAX_MESSAGES", 1)
    mail.messages |= {101: bank_mail(teb.account_export(JANUARY)), 102: bank_mail(FEBRUARY)}
    assert reading_from_start(ws)  # set up, nothing read yet
    first = mail_app.fetch(ws)
    assert first.more and first.stored == 1 and "sonraki alımda sürecek" in first.message
    assert reading_from_start(ws)  # the history is still coming: what the feed tells from it is held back
    second = mail_app.fetch(ws)
    assert not second.more and second.stored == 1 and bodies_fetched(mail) == ["101", "102"]
    assert not reading_from_start(ws)
    config.update(ws.layout.settings, "mail", {"start_day": date(2025, 6, 1)})
    assert reading_from_start(ws)  # another start day: the mailbox is read again from the start


def test_fetching_needs_an_account(ws):
    with pytest.raises(mail_app.NotConfigured):
        mail_app.fetch(ws)
    assert mail_app.status(ws)["configured"] is False


def test_setup_checks_the_password_and_keeps_it_out_of_files(ws, imap):
    acc, stored, folder = mail_app.setup_imap(ws, f" {ADDRESS} ", "abcd efgh ijkl mnop", date(2026, 1, 1))
    assert (acc.address, stored, folder) == (ADDRESS, True, "[Gmail]/Tüm Postalar")
    assert imap.stored == {ADDRESS: APP_PASSWORD}  # Google shows app passwords in groups of four
    settings = config.load(ws.layout.settings)
    assert (settings.mail.connector, settings.mail.address, settings.mail.start_day) == (
        "imap",
        ADDRESS,
        date(2026, 1, 1),
    )
    for path in (p for p in ws.home.rglob("*") if p.is_file()):
        assert APP_PASSWORD.encode() not in path.read_bytes(), path
    if os.name != "nt":
        assert stat.S_IMODE(ws.layout.settings.stat().st_mode) == 0o600
    status = mail_app.status(ws)
    assert status["configured"] is True and ADDRESS not in repr(status)  # the address stays out of outputs


def test_a_wrong_password_says_what_to_do_and_keeps_nothing(ws, imap):
    with pytest.raises(LoginRefused, match="uygulama şifresi"):
        mail_app.setup_imap(ws, ADDRESS, "normal-gmail-sifresi", date(2026, 1, 1))
    assert imap.stored == {} and config.load(ws.layout.settings).mail.address == ""


def test_the_settings_file_keeps_what_the_user_wrote(ws, imap):
    ws = with_settings(ws, '# benim notum\n[identity]\nnames = ["Örnek Kişi"]  # adım\n')
    mail_app.setup_imap(ws, ADDRESS, APP_PASSWORD, date(2026, 1, 1))
    text = ws.layout.settings.read_text(encoding="utf-8")
    assert "# benim notum" in text and "# adım" in text and 'connector = "imap"' in text


def test_remove_forgets_the_password_and_the_account(ws, mail):
    assert mail_app.remove(ws) and mail.stored == {}
    assert mail_app.account(ws) is None and not mail_app.remove(ws)


def test_a_refused_login_stops_the_connector_and_is_told_once(ws, mail):
    mail.password = "baska-bir-sifre"  # the user revoked the app password
    with pytest.raises(LoginRefused):
        mail_app.fetch(ws)
    connections = mail.connections
    with pytest.raises(MailError, match="reddetti"):
        mail_app.fetch(ws)  # stopped: no second login attempt
    background.poll_mail(ws)
    assert mail.connections == connections
    with ws.db() as db:
        assert [e.kind for e in events.entries(db, mail_app.AUTH_FAILED)] == [mail_app.AUTH_FAILED]
        assert mail_store.load(db, mail_app.IMAP).stopped
    assert mail_app.watch_target(ws) is None  # the IDLE watcher does not try either
    mail.password = APP_PASSWORD
    mail_app.setup_imap(ws, ADDRESS, APP_PASSWORD, date(2026, 1, 1))  # set up again: it runs again
    assert mail_app.fetch(ws).message == "yeni e-posta yok"


def test_other_servers_read_the_inbox(ws, imap):
    imap.capabilities = ("IMAP4REV1",)
    ws = with_settings(ws, '[mail]\nimap_host = "imap.example.com"\nbank_senders = ["teb.com.tr"]\n')
    mail_app.setup_imap(ws, ADDRESS, APP_PASSWORD, date(2026, 1, 1))
    imap.messages[101] = bank_mail(teb.account_export(JANUARY))
    assert mail_app.fetch(ws).stored == 1
    assert ("SELECT", "INBOX", True) in imap.commands


@pytest.mark.parametrize("senders", ['["teb.com.tr\\" OR ALL"]', '["teb com"]', "[]", '"teb.com.tr"'])
def test_sender_settings_cannot_reach_the_imap_command(ws, senders):
    with pytest.raises(SettingsError, match="bank_senders"):
        with_settings(ws, f"[mail]\nbank_senders = {senders}\n")


def test_the_search_asks_for_any_listed_domain_since_the_start_day():
    acc = Account(ADDRESS, date(2026, 3, 5), senders=("a.com.tr", "b.com", "c.com"))
    assert search_criteria(acc, 41) == [
        "UID 42:*",
        "SINCE 5-Mar-2026",
        'OR FROM "a.com.tr" OR FROM "b.com" FROM "c.com"',
    ]


@pytest.mark.parametrize(
    "name, coded",
    [
        ("Tüm Postalar", "T&APw-m Postalar"),
        ("INBOX", "INBOX"),
        ("Ekstre & Dekont", "Ekstre &- Dekont"),
        ("Gönderilmiş", "G&APY-nderilmi&AV8-"),
        ("日本語", "&ZeVnLIqe-"),
    ],
)
def test_folder_names_use_modified_utf7(name, coded):
    assert protocol.utf7_encode(name) == coded and protocol.utf7_decode(coded) == name


def test_a_changed_start_day_reads_the_mailbox_again(ws, mail):
    mail.messages[101] = bank_mail(teb.account_export(JANUARY))
    mail_app.fetch(ws)
    mail_app.set_start(ws, date(2025, 6, 1))
    mail.commands.clear()
    mail_app.fetch(ws)
    [search] = [c for c in mail.commands if c[:2] == ("UID", "SEARCH")]
    assert "UID 1:*" in search and "SINCE 1-Jun-2025" in search


def test_new_readers_read_the_archived_attachments_not_the_mailbox(ws, mail, monkeypatch):
    mail.messages[101] = bank_mail(teb.account_export(JANUARY))
    mail_app.fetch(ws)
    reader = registry.find("teb.account_html")
    monkeypatch.setattr(reader, "version", reader.version + 1)
    mail.commands.clear()
    assert mail_app.fetch(ws).message == "yeni e-posta yok"
    [search] = [c for c in mail.commands if c[:2] == ("UID", "SEARCH")]
    assert "UID 1:*" not in search  # the mailbox is not read from the start (ADR-0005)
    with ws.db() as db:
        # From the archive: the statement, and the message itself, which no reader took (the readers changed).
        assert reading.read_pending(ws, db) == 2


def test_a_bank_document_without_money_movements_is_kept_and_named(ws, mail):
    policy = text_pdf([(402, 32, "Katılım Sertifika Numarası : 1"), (159, 104, "ANINDA KREDİ HAYAT SİGORTASI")])
    mail.messages[101] = bank_mail(policy, name="Police.pdf", sender="bilgi@qnb.com.tr")
    mail_app.fetch(ws)
    [doc] = [d for d in kept(ws) if d.name == "Police.pdf"]
    assert (doc.status, doc.reason) == (DocumentStatus.UNPROCESSED, "sigorta poliçesi/bilgilendirmesi")


def test_the_service_fetches_on_its_own_and_continues_a_backlog(ws, mail, monkeypatch):
    monkeypatch.setattr(mail_app, "MAX_MESSAGES", 1)
    mail.messages |= {101: bank_mail(teb.account_export(JANUARY)), 102: bank_mail(FEBRUARY)}
    background.poll_mail(ws)
    with ws.db() as db:
        queued = [r["kind"] for r in db.rows("SELECT kind FROM jobs WHERE status = ?", (jobs.QUEUED,))]
    assert kinds.MAIL_FETCH in queued  # one more fetch follows at once


# --- IDLE ----------------------------------------------------------------------------------------------------


class IdleServer(FakeImap):
    """FakeImap with a real socket pair, so IDLE can wait on it as on a server."""

    def __init__(self):
        super().__init__()
        self.ours, self.theirs = socket.socketpair()
        self.reader = self.ours.makefile("rb")
        self.idles = 0

    def socket(self):
        return self.ours

    def send(self, data: bytes):
        if data.endswith(b" IDLE\r\n"):
            self.idles += 1
            self.theirs.sendall(b"+ idling\r\n")
        elif data == b"DONE\r\n":
            self.theirs.sendall(b"IPLKIDLE OK IDLE terminated\r\n")

    def readline(self) -> bytes:
        return self.reader.readline()


def until(condition, seconds: float = 5.0) -> bool:
    deadline = time.monotonic() + seconds
    while not condition():
        if time.monotonic() > deadline:
            return False
        time.sleep(0.01)
    return True


def watch(server: FakeImap, password: str = APP_PASSWORD) -> tuple[IdleWatcher, list[str], list[str]]:
    news: list[str] = []
    refusals: list[str] = []
    account = Account(ADDRESS, date(2026, 1, 1), senders=("teb.com.tr",))
    target = WatchTarget(account, password, lambda host, port: server)
    watcher = IdleWatcher(lambda: target, lambda: news.append("haber"), refusals.append, renew=0.5, first_wait=0.01)
    return watcher, news, refusals


def test_idle_asks_for_a_fetch_at_once_and_whenever_mail_arrives():
    server = IdleServer()
    watcher, news, _ = watch(server)
    watcher.start()
    try:
        assert until(lambda: news == ["haber"] and server.idles >= 1)  # what came while it was away
        server.theirs.sendall(b"* 7 EXISTS\r\n")
        assert until(lambda: len(news) == 2)
        assert until(lambda: server.idles >= 2)  # renewed
    finally:
        watcher.stop()


def test_idle_never_tries_a_refused_password_again():
    server = IdleServer()
    watcher, news, refusals = watch(server, password="yanlis")
    watcher.start()
    assert until(lambda: bool(refusals))
    watcher.stop()
    assert news == [] and len(refusals) == 1
    assert [c[0] for c in server.commands].count("LOGIN") == 1


def test_a_server_without_idle_leaves_it_to_the_regular_fetch():
    server = IdleServer()
    server.capabilities = ("IMAP4REV1",)
    watcher, news, _ = watch(server)
    watcher.start()
    assert until(lambda: ("LOGOUT",) in server.commands)
    watcher.stop()
    assert news == [] and server.idles == 0


def test_the_service_watches_only_a_set_up_unstopped_account(ws, mail):
    target = mail_app.watch_target(ws)
    assert target is not None and target.account.address == ADDRESS and target.password == APP_PASSWORD
    mail_app.remove(ws)
    assert mail_app.watch_target(ws) is None


def test_waiting_in_idle_stops_when_asked():
    server = IdleServer()
    stop = threading.Event()
    stop.set()
    assert protocol.wait_for_news(server, 30, stop) is False and server.idles == 1


# --- the command line and the API ---------------------------------------------------------------------------


def test_the_command_fetches_itself_when_no_service_runs(ws, mail, monkeypatch, capsys):
    monkeypatch.setenv("IPLIKCI_HOME", str(ws.home))
    mail.messages[101] = bank_mail(teb.account_export(JANUARY))
    assert cli.main(["eposta", "al"]) == 0
    assert "1 ileti arşive alındı" in capsys.readouterr().out and len(kept(ws)) == 2
    assert cli.main(["eposta", "durum"]) == 0
    out = capsys.readouterr().out
    assert "Bağlantı: IMAP (imap.gmail.com) · 2026-01-01 sonrası gelenler" in out and "Son alım: " in out
    assert ADDRESS not in out  # never the address


def test_the_command_asks_the_running_service_to_fetch(ws, mail, monkeypatch, capsys):
    monkeypatch.setenv("IPLIKCI_HOME", str(ws.home))
    asked: list[tuple[str, str]] = []
    monkeypatch.setattr(client, "call", lambda ws, method, path, body=None: asked.append((method, path)) or {})
    opened = mail.connections
    with instance.held(ws.run, instance.Holder(111, ws.port, "", "")):
        assert cli.main(["eposta", "al"]) == 0
    assert asked == [("POST", "/api/mail/fetch")] and mail.connections == opened  # no connection beside its own
    assert "Servis yeni e-postaları alıyor" in capsys.readouterr().out


def test_the_command_says_what_is_missing(ws, monkeypatch, capsys):
    monkeypatch.setenv("IPLIKCI_HOME", str(ws.home))
    assert cli.main(["eposta", "al"]) == 1
    assert "iplikci eposta kur" in capsys.readouterr().err
    assert cli.main(["eposta", "durum"]) == 0 and "IMAP, kurulu değil" in capsys.readouterr().out
    config.update(ws.layout.settings, "mail", {"connector": "browser_bridge"})
    assert cli.main(["eposta", "al"]) == 0 and "tarayıcı eklentisi getiriyor" in capsys.readouterr().out


def test_the_command_forgets_the_account(ws, mail, monkeypatch, capsys):
    monkeypatch.setenv("IPLIKCI_HOME", str(ws.home))
    assert cli.main(["eposta", "kaldir"]) == 0 and "silindi" in capsys.readouterr().out
    assert mail.stored == {} and mail_app.account(ws) is None


def test_the_interface_asks_for_a_fetch_only_of_a_ready_imap_account(ws, imap):
    app = TestClient(create_app(Context(ws=ws, token="belirtec")), base_url="http://127.0.0.1:8643")
    bearer = {"Authorization": "Bearer belirtec"}
    assert app.post("/api/mail/fetch", headers=bearer).json()["code"] == "mail_not_ready"
    mail_app.setup_imap(ws, ADDRESS, APP_PASSWORD, date(2026, 1, 1))
    assert app.post("/api/mail/fetch", headers=bearer).status_code == 202
    with ws.db() as db:
        assert db.scalar("SELECT count(*) FROM jobs WHERE kind = ? AND status = 'queued'", (kinds.MAIL_FETCH,)) == 1
    config.update(ws.layout.settings, "mail", {"connector": "browser_bridge"})
    assert app.post("/api/mail/fetch", headers=bearer).json()["code"] == "mail_by_extension"
