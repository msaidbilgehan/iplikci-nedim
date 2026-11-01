"""Reading in a process of its own (ADR-0005): the same results, a time limit, a memory limit where the system
enforces one, and a document that brings the process down leaves only itself unreadable."""

import json
import os
import sys
import zlib
from datetime import date
from decimal import Decimal

import pytest
from pdfplumber.utils.exceptions import PdfminerException

from iplikci import demo, parsers
from iplikci.app import reading
from iplikci.domain.codes import AccountType, DocumentStatus, TransactionKind
from iplikci.domain.models import Account, ParseResult, Security, SourceRef, Statement, Transaction
from iplikci.fakes import HOLDER, garanti
from iplikci.fakes.files import pdf_file, text_pdf
from iplikci.parsers import Skipped, Unreadable, registry, wire, worker
from iplikci.parsers.common import caused_by, set_business_names
from iplikci.parsers.contract import Document
from iplikci.storage import documents

from conftest import add

REAL = worker.COMMAND

# A stand-in reading process: it reports ready, then takes one step of its plan per document (answer, die, sleep).
STAND_IN = """\
import json, os, sys, time
plan, reply, pid = sys.argv[1].split(","), sys.argv[2], sys.argv[3]
with open(pid, "w") as f:
    f.write(str(os.getpid()))
out = sys.stdout.buffer
out.write(b'{"ready": true}\\n')
out.flush()
for step in plan:
    header = sys.stdin.buffer.readline()
    if not header:
        break
    job = json.loads(header)
    sys.stdin.buffer.read(job["size"])
    if step == "die":
        sys.exit(1)
    if step == "sleep":
        time.sleep(60)
    out.write(reply.replace("NAME", job["name"]).encode() + b"\\n")
    out.flush()
"""
ANSWER = '{"unreadable": "sahte okuma: NAME", "parser": "sahte.okuyucu"}'


@pytest.fixture
def stand_in(tmp_path, monkeypatch):
    """use(plan, reply): the documents from here on go to a stand-in that follows plan; tmp_path/pid holds its pid."""
    script = tmp_path / "sahte_okuma.py"
    script.write_text(STAND_IN, encoding="utf-8")

    def use(plan: str, reply: str = ANSWER) -> None:
        worker.stop()
        monkeypatch.setattr(worker, "COMMAND", (sys.executable, "-I", str(script), plan, reply, str(tmp_path / "pid")))

    yield use
    worker.stop()


def doc(name: str = "belge.pdf", data: bytes = b"%PDF-1.4") -> Document:
    return Document(name, "test", data, "sha")


def receipt() -> Document:
    fast = garanti.fast_body("ŞUBAT AİDAT", "ÖRNEK SİTE YÖNETİMİ")
    return doc("dekont.pdf", garanti.receipt("HESAPTAN FAST", "106/1234567", HOLDER, fast, "- 1.250,00 TL"))


def outcome(read, document: Document) -> ParseResult | tuple:
    """What reading made of a document: its result, or the exception with all that the app keeps of it."""
    try:
        return read(document)
    except Skipped as exc:
        return "skipped", str(exc), exc.business, exc.parser
    except Unreadable as exc:
        return "unreadable", str(exc), exc.parser


# --- the same results ------------------------------------------------------------------------------------------


def test_every_demo_document_reads_the_same_in_the_reading_process():
    for path, data in demo.documents().items():
        document = doc(path.rpartition("/")[2], data)
        assert outcome(worker.parse_document, document) == outcome(parsers.parse_document, document), path


def test_the_reading_process_reads_with_the_company_names_of_the_moment():
    form = doc("Ornek Tekstil talimat.pdf", text_pdf([(40, 40, "TALİMAT FORMU")]))
    set_business_names(["Örnek Tekstil A.Ş."])
    assert outcome(worker.parse_document, form) == ("skipped", "şirket belgesi — kapsam dışı", True, "")
    set_business_names([])
    assert outcome(worker.parse_document, form) == ("skipped", "talimat formu", False, "")


def full_result() -> ParseResult:
    """A result with every field a reader fills, and every kind of place a row can have."""
    card = Account("kart-1234", "Örnek Kart •1234", "Örnek Bankası", AccountType.CREDIT_CARD, "TRY", "1234", "not")
    rows = [
        Transaction(
            date(2026, 9, 10),
            "ORNEK MARKET",
            Decimal("2150.00"),
            TransactionKind.PURCHASE,
            card.id,
            original="19,99 USD",
            installment="2/6",
            bank_category="Market",
            counterparty="ÖRNEK",
            source="ekstre.pdf",
            ref=SourceRef(page=1, box=(40.0, 301.5, 412.25, 310.5)),
        ),
        Transaction(date(2026, 9, 12), "ODEME", Decimal(-4300), TransactionKind.CARD_PAYMENT, card.id),
        Transaction(
            date(2026, 9, 13),
            "EFT",
            Decimal("1E+3"),
            TransactionKind.TRANSFER_CANDIDATE,
            card.id,
            ref=SourceRef(2, line=7),
        ),
        Transaction(
            date(2026, 9, 14),
            "TABLO",
            Decimal("0.01"),
            TransactionKind.INTEREST_FEE,
            card.id,
            ref=SourceRef(sheet="", row=9),
        ),
    ]
    statement = Statement(
        card.id,
        date(2026, 10, 5),
        "TRY",
        "ekstre.pdf",
        None,
        Decimal("-0.50"),
        rows,
        total_is_sum=True,
        start=date(2026, 9, 6),
        checks_ok=3,
        checks_total=4,
        balances={"2026-09": Decimal("12.30"), "2026-10": Decimal(0)},
        securities=[Security("ORNEK", "ÖRNEK SANAYİ A.Ş.", Decimal("20.5"), Decimal(1342), date(2026, 10, 30))],
    )
    loose = Transaction(
        date(2026, 9, 10),
        "AİDAT",
        Decimal(1250),
        TransactionKind.TRANSFER_CANDIDATE,
        card.id,
        ref=SourceRef(1, span=(0, 48)),
    )
    return ParseResult("ornek.okuyucu", [card], [statement], [loose], "dekont-1", "ÖRNEK KULLANICI", "Aidat")


def test_a_readers_result_crosses_back_unchanged():
    result = full_result()
    assert wire.load(json.loads(json.dumps(wire.dump(result)))) == result


GONE = object()


@pytest.mark.parametrize(
    "path, value",
    [
        (("title",), GONE),
        (("transactions", 0, "amount"), 1250.5),  # amounts cross as text, exactly
        (("transactions", 0, "amount"), "NaN"),
        (("transactions", 0, "amount"), "bin"),
        (("transactions", 0, "kind"), "theft"),
        (("transactions", 0, "description"), 7),
        (("transactions", 0, "ref", "span"), [1, 2, 3]),
        (("statements", 0, "transactions", 0, "ref", "box"), [1, 2, "3", 4]),
        (("statements", 0, "total_is_sum"), "evet"),
        (("statements", 0, "checks_ok"), True),
        (("statements", 0, "cut_date"), "2026-13-01"),
        (("statements", 0, "balances"), ["2026-09"]),
        (("accounts", 0, "type"), None),
        (("accounts",), {"id": "x"}),
    ],
)
def test_the_way_back_takes_nothing_but_a_readers_result(path, value):
    data = wire.dump(full_result())
    *parents, last = path
    target = data
    for key in parents:
        target = target[key]
    if value is GONE:
        del target[last]
    else:
        target[last] = value
    with pytest.raises(ValueError):
        wire.load(data)
    with pytest.raises(ValueError):
        wire.load([data])


# --- the limits ------------------------------------------------------------------------------------------------


def test_a_document_that_runs_out_of_time_is_unreadable_and_the_next_one_still_reads(stand_in, monkeypatch, tmp_path):
    stand_in("sleep")
    monkeypatch.setattr(worker, "TIME_LIMIT", 1.0)
    assert outcome(worker.parse_document, doc()) == ("unreadable", "okuma 1 saniyede bitmedi", "")
    if os.name == "posix":  # the stuck process is gone, not left behind
        with pytest.raises(ProcessLookupError):
            os.kill(int((tmp_path / "pid").read_text()), 0)
    monkeypatch.setattr(worker, "COMMAND", REAL)
    monkeypatch.setattr(worker, "TIME_LIMIT", 60.0)
    assert outcome(worker.parse_document, receipt()) == outcome(parsers.parse_document, receipt())


def test_a_reading_process_that_dies_leaves_the_document_unreadable(stand_in):
    stand_in("die")
    assert outcome(worker.parse_document, doc()) == ("unreadable", worker.CRASH_REASON, "")


def test_a_process_that_read_other_documents_before_dying_gets_one_more_try(stand_in):
    stand_in("answer,die")
    assert outcome(worker.parse_document, doc("a.pdf")) == ("unreadable", "sahte okuma: a.pdf", "sahte.okuyucu")
    # It may have died of what a.pdf left behind: a fresh process reads b.pdf again.
    assert outcome(worker.parse_document, doc("b.pdf")) == ("unreadable", "sahte okuma: b.pdf", "sahte.okuyucu")


@pytest.mark.parametrize(
    "reply", ["bu JSON değil", "[1, 2]", "{}", '{"result": {"parser": 1}}', '{"skipped": 3}', '{"unreadable": null}']
)
def test_a_reply_the_app_cannot_take_leaves_the_document_unreadable(stand_in, reply):
    stand_in("answer", reply)
    assert outcome(worker.parse_document, doc()) == ("unreadable", worker.GARBLED_REASON, "")


def test_a_fresh_process_takes_over_after_its_share_of_documents(stand_in, monkeypatch):
    stand_in("answer,answer,sleep")
    monkeypatch.setattr(worker, "_RECYCLE", 2)
    monkeypatch.setattr(worker, "TIME_LIMIT", 1.0)
    for name in ("a.pdf", "b.pdf", "c.pdf"):  # c.pdf goes to a fresh process, which answers it
        assert outcome(worker.parse_document, doc(name)) == ("unreadable", f"sahte okuma: {name}", "sahte.okuyucu")


def test_nothing_is_recorded_while_no_reading_process_starts(ws, monkeypatch):
    [stored] = add(ws, "dekont.pdf", receipt().data).stored
    reader = registry.find("garanti.receipt")
    monkeypatch.setattr(reader, "version", reader.version + 1)
    worker.stop()
    monkeypatch.setattr(worker, "COMMAND", (sys.executable, "-I", "-c", "raise SystemExit(3)"))
    with pytest.raises(worker.WorkerError), ws.db() as db:
        reading.read_pending(ws, db)
    with ws.db() as db:
        kept = documents.get(db, stored.sha256)
    assert kept.status is DocumentStatus.PROCESSED and reading.stale(kept)  # waits for a reading process


def _inflating_pdf(size: int) -> bytes:
    """A one-page PDF whose content stream unpacks to size bytes of spaces."""
    pack = zlib.compressobj(1)
    spaces = b" " * (1 << 24)
    data = b"".join(pack.compress(spaces) for _ in range(size >> 24)) + pack.flush()
    return pdf_file(
        [
            b"<< /Type /Catalog /Pages 2 0 R >>",
            b"<< /Type /Pages /Kids [3 0 R] /Count 1 >>",
            b"<< /Type /Page /Parent 2 0 R /MediaBox [0 0 595 842] /Contents 4 0 R >>",
            b"<< /Length %d /Filter /FlateDecode >>\nstream\n%s\nendstream" % (len(data), data),
        ]
    )


@pytest.mark.skipif(sys.platform != "linux", reason="adres alanı sınırını yalnızca Linux uygular")
def test_a_document_that_unpacks_beyond_the_memory_limit_is_unreadable():
    bomb = doc("ekstre.pdf", _inflating_pdf(5 << 28))  # 1.25 GiB once unpacked
    assert outcome(worker.parse_document, bomb) == ("unreadable", worker.MEMORY_REASON, "")
    assert outcome(worker.parse_document, receipt()) == outcome(parsers.parse_document, receipt())


def _from(outer: Exception, inner: Exception) -> Exception:
    outer.__cause__ = inner  # raise outer from inner
    return outer


def _during(outer: Exception, inner: Exception) -> Exception:
    outer.__context__ = inner  # outer raised while inner was being handled
    return outer


@pytest.mark.parametrize(
    "exc, found",
    [
        (MemoryError("Unable to allocate output buffer."), True),
        (PdfminerException(MemoryError()), True),  # pdfplumber hands it on as its argument
        (_from(Unreadable("PdfminerException", parser="ornek.okuyucu"), PdfminerException(MemoryError())), True),
        (_during(Skipped("PDF açılamadı"), MemoryError()), True),
        (_from(Unreadable("ValueError: bozuk"), ValueError("bozuk")), False),
    ],
)
def test_a_failed_allocation_is_recognised_however_it_is_handed_on(exc, found):
    assert caused_by(exc, MemoryError) is found
