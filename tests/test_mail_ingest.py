"""Taking one e-mail in (ADR-0015): the trust rule, the company check, and the message kept whole with its
attachments as documents of their own."""

import io
import zipfile

import pytest

from iplikci.app import intake, reading
from iplikci.app.mail import Taken, take
from iplikci.domain.codes import DocumentStatus, SourceKind
from iplikci.ingest.mail.trust import MAX_MESSAGE_BYTES
from iplikci.parsers.common import BUSINESS_REASON, MESSAGE_REASON, set_business_names
from iplikci.settings.config import BANK_SENDERS
from iplikci.storage import audit, documents, events

from conftest import FEBRUARY, bank_mail, put

SENDERS = BANK_SENDERS


def kept(ws) -> list[documents.DocumentRow]:
    with ws.db() as db:
        return documents.every(db)


def test_a_trusted_bank_mail_is_kept_whole_with_its_statement_as_its_child(ws):
    raw = bank_mail(FEBRUARY)
    outcome = take(ws, raw, SENDERS)
    assert (outcome.taken, outcome.domain, outcome.documents) == (Taken.STORED, "teb.com.tr", 2)
    message, statement = sorted(kept(ws), key=lambda d: d.name.endswith(".eml"), reverse=True)
    assert message.name == "E-posta 2026-02-02 teb.com.tr.eml"
    assert (message.status, message.reason, message.sha256) == (
        DocumentStatus.UNPROCESSED,
        MESSAGE_REASON,
        outcome.sha256,
    )
    assert (statement.name, statement.status, statement.parent) == (
        "HesapHareketleri.xls",
        DocumentStatus.PROCESSED,
        message.sha256,
    )
    assert ws.vault.read(message.sha256) == raw
    with ws.db() as db:
        [source] = documents.sources(db, statement.sha256)
        received = [e.target for e in events.entries(db, "document.received")]
    assert (source.kind, source.sender, source.subject) == (SourceKind.EMAIL, "teb.com.tr", "Hesap hareketleriniz")
    assert source.sent_at.startswith("2026-02-02T10:00:00")
    assert sorted(received) == sorted([message.sha256, statement.sha256])


def test_the_same_mail_again_adds_nothing(ws):
    raw = bank_mail(FEBRUARY)
    take(ws, raw, SENDERS)
    again = take(ws, raw, SENDERS)
    assert (again.taken, again.documents) == (Taken.KNOWN, 0)
    assert len(kept(ws)) == 2


@pytest.mark.parametrize(
    ("sender", "results", "expected", "reason"),
    [
        ("kampanya@example.com", None, Taken.UNLISTED, ""),
        (
            "bilgi@teb.com.tr",
            ("mx.google.com; dmarc=fail (p=REJECT) header.from=teb.com.tr",),
            Taken.UNVERIFIED,
            "dmarc:fail",
        ),
        (
            "bilgi@teb.com.tr",
            ("mx.google.com; dmarc=pass header.from=example.com",),
            Taken.UNVERIFIED,
            "header-from:example.com",
        ),
        (
            "bilgi@teb.com.tr",
            ("evil.example; dmarc=pass header.from=teb.com.tr",),
            Taken.UNVERIFIED,
            "server:evil.example",
        ),
        ("bilgi@teb.com.tr", (), Taken.UNVERIFIED, "no-results"),
        (
            "bilgi@teb.com.tr",
            ("mx.google.com; dkim=pass header.i=@teb.com.tr; spf=pass smtp.mailfrom=teb.com.tr",),
            Taken.UNVERIFIED,
            "no-dmarc",
        ),
        (
            "bilgi@teb.com.tr",
            ("mx.google.com; dmarc=bestguesspass header.from=teb.com.tr",),
            Taken.UNVERIFIED,
            "dmarc:bestguesspass",
        ),
        (
            "bilgi@teb.com.tr",
            ("mx.google.com; dmarc=fail header.from=teb.com.tr", "mx.google.com; dmarc=pass header.from=teb.com.tr"),
            Taken.UNVERIFIED,
            "dmarc:fail",
        ),
        (
            "bilgi@teb.com.tr",
            (
                (
                    'mx.google.com; spf=pass (google.com: domain of "dmarc=pass header.from=teb.com.tr"@evil.example '
                    "designates 192.0.2.1 as permitted sender) smtp.mailfrom=x@evil.example; "
                    "dmarc=fail (p=NONE sp=NONE dis=NONE) header.from=teb.com.tr"
                ),
            ),
            Taken.UNVERIFIED,
            "dmarc:fail",
        ),
        (
            "bilgi@teb.com.tr",
            (
                (
                    'mx.google.com; spf=pass smtp.mailfrom="a;dmarc=pass header.from=teb.com.tr"@evil.example; '
                    "dmarc=fail header.from=teb.com.tr"
                ),
            ),
            Taken.UNVERIFIED,
            "dmarc:fail",
        ),
    ],
    ids=[
        "unlisted",
        "dmarc fail",
        "another domain",
        "another server",
        "no header",
        "no dmarc result",
        "a best guess",
        "pass only further down",
        "pass forged in a comment",
        "pass forged in a quoted address",
    ],
)
def test_an_untrusted_mail_leaves_no_trace_but_why(ws, sender, results, expected, reason):
    outcome = take(ws, bank_mail(FEBRUARY, sender=sender, results=results), SENDERS)
    assert (outcome.taken, outcome.reason) == (expected, reason)
    assert kept(ws) == []
    with ws.db() as db:
        assert events.entries(db) == []


def test_a_subdomain_of_a_listed_sender_counts(ws):
    outcome = take(ws, bank_mail(FEBRUARY, sender="ekstre@ileti.teb.com.tr"), SENDERS)
    assert outcome.taken is Taken.STORED


def test_a_subdomain_passing_dmarc_under_its_listed_organizational_domain_counts(ws):
    # Gmail names the domain whose policy it applied: a subdomain without a DMARC record of its own passes as its
    # organizational domain.
    results = ("mx.google.com; dmarc=pass (p=REJECT sp=REJECT dis=NONE) header.from=teb.com.tr",)
    outcome = take(ws, bank_mail(FEBRUARY, sender="kampanya@bilgi.teb.com.tr", results=results), SENDERS)
    assert outcome.taken is Taken.STORED


@pytest.mark.parametrize(
    ("sender", "checked"),
    [
        ("bilgi@teb.com.tr", "com.tr"),  # a public suffix is on no list
        ("bilgi@teb.com.tr", "isbank.com.tr"),  # listed, but not above the sender
        ("bilgi@teb.com.tr", "bilgi.teb.com.tr"),  # below the sender
    ],
    ids=["a public suffix", "another listed domain", "a subdomain of the sender"],
)
def test_dmarc_passing_for_a_domain_that_does_not_cover_the_sender_does_not_count(ws, sender, checked):
    results = (f"mx.google.com; dmarc=pass header.from={checked}",)
    outcome = take(ws, bank_mail(FEBRUARY, sender=sender, results=results), SENDERS)
    assert (outcome.taken, outcome.reason) == (Taken.UNVERIFIED, f"header-from:{checked}")


def test_without_the_sender_check_a_listed_sender_is_enough(ws):
    raw = bank_mail(FEBRUARY, results=())
    assert take(ws, raw, SENDERS, verify=False).taken is Taken.STORED


def test_a_company_mail_kept_before_its_name_was_set_goes_to_the_trash_with_its_attachments(ws, private_trash):
    subject = b"Subject: ORNEK TEKNOLOJI VE BILISIM-01.02.2026 Hesap Ozeti"  # the bank cuts the company's name short
    raw = bank_mail(FEBRUARY).replace(b"Subject: Hesap hareketleriniz", subject)
    assert take(ws, raw, SENDERS).taken is Taken.STORED  # no company name set yet
    personal = take(ws, bank_mail(None, sender="ekstre@isbank.com.tr"), SENDERS)
    set_business_names(["Örnek Teknoloji"])
    with ws.db() as db:
        reading.read_pending(ws, db)
    assert {d.sha256 for d in kept(ws) if d.status is not DocumentStatus.REMOVED} == {personal.sha256}
    with ws.db() as db:
        removed = documents.every(db, [DocumentStatus.REMOVED])
        assert len(audit.targets(db, "document.business")) == 2  # the message and its attachment
    assert {d.reason for d in removed} == {BUSINESS_REASON}
    assert not any(ws.vault.has(d.sha256) for d in removed) and any(private_trash.iterdir())  # moved, not deleted


def test_a_company_mail_is_not_kept(ws):
    raw = bank_mail(FEBRUARY).replace(b"Subject: Hesap hareketleriniz", b"Subject: Sirket Kredi Karti Ekstresi")
    outcome = take(ws, raw, SENDERS)
    assert outcome.taken is Taken.BUSINESS and kept(ws) == []
    with ws.db() as db:
        assert audit.targets(db, "document.business")


def test_a_mail_with_a_company_document_inside_is_not_kept_either(ws):
    raw = bank_mail(b"%PDF-1.4 not really", name="Sirket Kredi Karti Ekstresi.pdf")
    outcome = take(ws, raw, SENDERS)
    assert outcome.taken is Taken.BUSINESS
    assert kept(ws) == []


def test_a_mail_larger_than_the_limit_is_not_read(ws):
    assert take(ws, b"x" * (MAX_MESSAGE_BYTES + 1), SENDERS).taken is Taken.TOO_LARGE


def test_the_documents_in_an_attached_zip_are_the_messages_children(ws):
    blob = io.BytesIO()
    with zipfile.ZipFile(blob, "w") as zf:
        zf.writestr("Ocak/HesapHareketleri.xls", FEBRUARY)
    outcome = take(ws, bank_mail(blob.getvalue(), name="ekstreler.zip"), SENDERS)
    assert outcome.taken is Taken.STORED
    children = [d for d in kept(ws) if d.parent]
    assert [(d.name, d.parent) for d in children] == [("HesapHareketleri.xls", outcome.sha256)]


def test_an_e_mail_file_the_user_brings_is_kept_with_what_it_says_of_itself(ws, tmp_path):
    path = put(tmp_path / "dışarıdan" / "ekstre.eml", bank_mail(FEBRUARY))
    applied = intake.apply(ws, intake.plan_paths(ws, [path]))
    assert {c.name for c in applied.stored} == {"ekstre.eml", "HesapHareketleri.xls"}
    message = next(c for c in applied.stored if c.name == "ekstre.eml")
    assert message.source.sender == "teb.com.tr" and message.source.kind is SourceKind.IMPORT
    assert next(c for c in applied.stored if c.name != "ekstre.eml").parent == message.sha256
