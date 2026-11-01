"""Bank documents from e-mail: only verified bank senders, the mailbox untouched, each e-mail once."""

import io
import json
import os
import stat
import zipfile
from datetime import date

import pytest

from iplikci import email_fetch
from iplikci.app import reading
from iplikci.app.workspace import Workspace
from iplikci.demo import teb_export, text_pdf
from iplikci.domain.codes import DocumentStatus, SourceKind
from iplikci.email_fetch import Account, MailError, NotConfigured, fetch, search_criteria, setup
from iplikci.parsers import registry
from iplikci.settings.config import SettingsError
from iplikci.storage import documents

from conftest import ADDRESS, APP_PASSWORD, FEBRUARY, JANUARY, add, bank_mail


def with_settings(ws: Workspace, text: str) -> Workspace:
    ws.layout.settings.write_text(text, encoding="utf-8")
    return Workspace.load(ws.home)


def bodies_fetched(server) -> list[str]:
    return [c[2] for c in server.commands if c[:2] == ("UID", "FETCH") and c[3] == "(BODY.PEEK[])"]


def kept(ws: Workspace) -> list[documents.DocumentRow]:
    with ws.db() as db:
        return documents.every(db)


def test_a_verified_bank_statement_goes_into_the_vault(ws, mail):
    mail.messages[101] = bank_mail(teb_export(JANUARY))
    got = fetch(ws)
    assert (got.scanned, got.with_documents, got.unverified) == (1, 1, 0)
    [c] = got.stored
    assert c.status is DocumentStatus.PROCESSED and ws.vault.read(c.sha256) == teb_export(JANUARY)
    assert got.message.startswith("1 yeni banka e-postası okundu; 1 yeni belge arşive alındı (1 hesap dökümü)")
    assert got.folder == "[Gmail]/Tüm Postalar"  # All Mail, found by its \All flag in any language
    with ws.db() as db:
        [source] = documents.sources(db, c.sha256)
    assert (source.kind, source.origin, source.sender) == (
        SourceKind.EMAIL,
        "E-posta 2026-02-02 teb.com.tr",
        "teb.com.tr",
    )
    assert source.sent_at.startswith("2026-02-02T10:00:00")


def test_the_mailbox_is_only_read(ws, mail):
    mail.messages[101] = bank_mail(teb_export(JANUARY))
    fetch(ws)
    assert ("SELECT", '"[Gmail]/T&APw-m Postalar"', True) in mail.commands  # EXAMINE: read-only
    sent = {c[1] if c[0] == "UID" else c[0] for c in mail.commands}
    assert sent == {"LOGIN", "SELECT", "SEARCH", "FETCH", "LOGOUT"}  # never STORE, COPY, MOVE or EXPUNGE
    assert bodies_fetched(mail) == ["101"]  # BODY.PEEK: not even marked as read


def test_mail_whose_sender_is_not_verified_is_ignored(ws, mail):
    january = teb_export(JANUARY)
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
    got = fetch(ws)
    assert (got.scanned, got.unverified, got.stored) == (5, 5, [])
    assert kept(ws) == [] and "5 e-postanın göndereni doğrulanamadı" in got.message


def test_mail_from_other_senders_is_not_even_counted(ws, mail):
    mail.messages[101] = bank_mail(teb_export(JANUARY), sender="kampanya@teb.com.tr.saldirgan.example")
    mail.messages[102] = bank_mail(teb_export(JANUARY), sender="arkadas@example.com")
    got = fetch(ws)
    assert (got.scanned, got.stored) == (0, []) and got.message == "yeni banka e-postası yok"


def test_a_subdomain_of_a_bank_counts(ws, mail):
    mail.messages[101] = bank_mail(teb_export(JANUARY), sender="ekstre@ileti.teb.com.tr")
    assert len(fetch(ws).stored) == 1


def test_each_e_mail_is_read_once(ws, mail):
    mail.messages[101] = bank_mail(teb_export(JANUARY))
    assert len(fetch(ws).stored) == 1
    mail.messages[102] = bank_mail(FEBRUARY)
    mail.commands.clear()
    second = fetch(ws)
    assert len(second.stored) == 1 and bodies_fetched(mail) == ["102"]
    mail.commands.clear()
    third = fetch(ws)
    assert third.message == "yeni banka e-postası yok" and bodies_fetched(mail) == []


def test_a_new_mailbox_generation_is_read_again_without_keeping_twice(ws, mail):
    mail.messages[101] = bank_mail(teb_export(JANUARY))
    fetch(ws)
    mail.uidvalidity = 8  # the server renumbered the mailbox: the old position means nothing
    again = fetch(ws)
    assert again.scanned == 1 and again.stored == [] and "1 zaten vardı" in again.message
    assert len(kept(ws)) == 1


def test_documents_already_in_the_vault_are_not_kept_again(ws, mail):
    add(ws, "ocak.xls", teb_export(JANUARY))
    mail.messages[101] = bank_mail(teb_export(JANUARY))
    got = fetch(ws)
    assert got.stored == [] and "1 zaten vardı" in got.message and len(kept(ws)) == 1


def test_zip_attachments_are_opened_in_memory(ws, mail):
    buf = io.BytesIO()
    with zipfile.ZipFile(buf, "w") as zf:
        zf.writestr("ekstreler/HesapHareketleri.xls", teb_export(JANUARY))
        zf.writestr("okubeni.txt", "belge değil")
    mail.messages[101] = bank_mail(buf.getvalue(), name="ekstreler.zip")
    got = fetch(ws)
    assert [c.name for c in got.stored] == ["HesapHareketleri.xls"]
    assert [d.name for d in kept(ws)] == ["HesapHareketleri.xls"]  # the zip itself is not kept


def test_a_large_backlog_is_read_in_parts(ws, mail, monkeypatch):
    monkeypatch.setattr(email_fetch, "MAX_MESSAGES", 1)
    mail.messages |= {101: bank_mail(teb_export(JANUARY)), 102: bank_mail(FEBRUARY)}
    first = fetch(ws)
    assert first.more and len(first.stored) == 1 and "sonraki alımda sürecek" in first.message
    second = fetch(ws)
    assert not second.more and len(second.stored) == 1 and bodies_fetched(mail) == ["101", "102"]


def test_fetching_needs_an_account(ws):
    with pytest.raises(NotConfigured, match="eposta --kur"):
        fetch(ws)
    assert email_fetch.status(ws) == {"configured": False, "hint": email_fetch.SETUP_HINT}


def test_setup_checks_the_password_and_keeps_it_out_of_files(ws, imap):
    acc, stored, folder = setup(ws, f" {ADDRESS} ", "abcd efgh ijkl mnop", date(2026, 1, 1))
    assert (acc.address, stored, folder) == (ADDRESS, True, "[Gmail]/Tüm Postalar")
    assert imap.stored == {ADDRESS: APP_PASSWORD}  # Google shows app passwords in groups of four
    state = ws.run / email_fetch.STATE_NAME
    assert json.loads(state.read_text(encoding="utf-8"))["address"] == ADDRESS
    for path in (p for p in ws.home.rglob("*") if p.is_file()):
        assert APP_PASSWORD.encode() not in path.read_bytes(), path
    if os.name != "nt":
        assert stat.S_IMODE(state.stat().st_mode) == 0o600
    assert email_fetch.status(ws)["address"] == ADDRESS


def test_a_wrong_password_says_what_to_do_and_keeps_nothing(ws, imap):
    with pytest.raises(MailError, match="uygulama şifresi"):
        setup(ws, ADDRESS, "normal-gmail-sifresi", date(2026, 1, 1))
    assert imap.stored == {} and not (ws.run / email_fetch.STATE_NAME).exists()


def test_forget_removes_the_password_and_the_account(ws, mail):
    assert email_fetch.forget(ws) and mail.stored == {}
    assert not email_fetch.configured(ws) and not email_fetch.forget(ws)


def test_other_servers_read_the_inbox_with_a_plain_search(ws, imap):
    imap.capabilities = ("IMAP4REV1",)
    ws = with_settings(ws, '[mail]\nimap_host = "imap.example.com"\nbank_senders = ["teb.com.tr"]\n')
    setup(ws, ADDRESS, APP_PASSWORD, date(2026, 1, 1))
    imap.messages[101] = bank_mail(teb_export(JANUARY))
    assert len(fetch(ws).stored) == 1
    [search] = [c for c in imap.commands if c[:2] == ("UID", "SEARCH")]
    assert ("SELECT", "INBOX", True) in imap.commands and not any("X-GM-RAW" in a for a in search)


@pytest.mark.parametrize("senders", ['["teb.com.tr\\" OR ALL"]', '["teb com"]', "[]", '"teb.com.tr"'])
def test_sender_settings_cannot_reach_the_imap_command(ws, senders):
    with pytest.raises(SettingsError, match="bank_senders"):
        with_settings(ws, f"[mail]\nbank_senders = {senders}\n")


def test_the_search_asks_for_any_bank_domain_since_the_start_day():
    acc = Account(ADDRESS, date(2026, 3, 5), senders=("a.com.tr", "b.com", "c.com"))
    assert search_criteria(acc, 41, gmail=True) == [
        "UID 42:*",
        "SINCE 5-Mar-2026",
        'OR FROM "a.com.tr" OR FROM "b.com" FROM "c.com"',
        'X-GM-RAW "has:attachment"',
    ]
    assert search_criteria(acc, 0, gmail=False)[-1] == 'OR FROM "a.com.tr" OR FROM "b.com" FROM "c.com"'


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
    assert email_fetch.utf7_encode(name) == coded and email_fetch.utf7_decode(coded) == name


def test_a_changed_start_day_reads_the_mailbox_again(ws, mail):
    mail.messages[101] = bank_mail(teb_export(JANUARY))
    fetch(ws)
    email_fetch.set_start(ws, date(2025, 6, 1))
    mail.commands.clear()
    fetch(ws)
    [search] = [c for c in mail.commands if c[:2] == ("UID", "SEARCH")]
    assert "UID 1:*" in search and "SINCE 1-Jun-2025" in search


def test_new_readers_read_the_archived_attachments_not_the_mailbox(ws, mail, monkeypatch):
    mail.messages[101] = bank_mail(teb_export(JANUARY))
    fetch(ws)
    reader = registry.find("teb.account_html")
    monkeypatch.setattr(reader, "version", reader.version + 1)
    mail.commands.clear()
    assert fetch(ws).message == "yeni banka e-postası yok"
    [search] = [c for c in mail.commands if c[:2] == ("UID", "SEARCH")]
    assert "UID 1:*" not in search  # the mailbox is not read from the start (ADR-0005)
    with ws.db() as db:
        assert reading.read_pending(ws, db) == 1  # the attachment is read again from the archive


def test_a_bank_document_without_money_movements_is_kept_and_named(ws, mail):
    policy = text_pdf([(402, 32, "Katılım Sertifika Numarası : 1"), (159, 104, "ANINDA KREDİ HAYAT SİGORTASI")])
    mail.messages[101] = bank_mail(policy, name="Police.pdf", sender="bilgi@qnb.com.tr")
    got = fetch(ws)
    [c] = got.stored
    assert (c.status, c.reason) == (DocumentStatus.UNPROCESSED, "sigorta poliçesi/bilgilendirmesi")
    assert "1 yeni belge arşive alındı (1 para hareketi olmayan belge)" in got.message
