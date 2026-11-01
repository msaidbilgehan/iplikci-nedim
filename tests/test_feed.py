"""The feed (ADR-0014): two analyses compared, the difference as events; the first one only takes note."""

from datetime import date

from iplikci.app import background
from iplikci.fakes import teb
from iplikci.feed.snapshot import BULK, Change, Snapshot, diff
from iplikci.storage import events, jobs

from conftest import add


def snap(month="2026-11", rows=None, receipts=None, months=None, invoices=None) -> Snapshot:
    return Snapshot(month, rows or {}, receipts or {}, months or {}, invoices or {})


def test_the_first_snapshot_only_takes_note():
    assert diff(None, snap(rows={"a": ("teb-1", "2026-10-01")}, months={"2026-10": "closed"})) == []


def test_each_new_row_is_news():
    before = snap(rows={"a": ("teb-1", "2026-10-01")})
    after = snap(
        rows={"a": ("teb-1", "2026-10-01"), "c": ("teb-1", "2026-10-09"), "b": ("isbank-2", "2026-10-03")},
        receipts={"b": "provisional"},
    )
    assert diff(before, after) == [
        Change("transaction.created", "b", {"account": "isbank-2", "date": "2026-10-03", "provisional": True}),
        Change("transaction.created", "c", {"account": "teb-1", "date": "2026-10-09", "provisional": False}),
    ]


def test_many_new_rows_at_once_are_one_event():
    rows = {f"fp{i:03d}": ("teb-1", f"2026-{1 + i % 9:02d}-1{i % 10}") for i in range(BULK + 1)}
    assert diff(snap(), snap(rows=rows)) == [
        Change("transaction.created", "", {"count": BULK + 1, "from": "2026-01-10", "to": "2026-09-18"})
    ]


def test_a_receipt_row_a_statement_now_shows_is_confirmed():
    before = snap(receipts={"r1": "provisional", "r2": "provisional"})
    after = snap(receipts={"r1": "matched", "r2": "unmatched"})
    assert diff(before, after) == [Change("transaction.confirmed", "r1")]


def test_months_speak_as_the_month_end_news_did():
    before = snap(
        month="2026-10", months={"2026-07": "waiting", "2026-08": "waiting", "2026-09": "waiting", "2026-10": "running"}
    )
    after = snap(
        month="2026-11",
        months={
            "2026-07": "closed",
            "2026-08": "closed",
            "2026-09": "check",
            "2026-10": "waiting",
            "2026-11": "running",
        },
    )
    assert diff(before, after) == [
        Change("month.needs_check", "2026-09"),
        Change("month.ended", "2026-10", {"status": "waiting"}),
    ]
    assert diff(after, snap(month="2026-11", months={**after.months, "2026-10": "closed"})) == [
        Change("month.closed", "2026-10")
    ]


def test_a_bill_that_arrives_or_whose_status_changes_is_news():
    before = snap(invoices={"a:0": "pending", "b:0": "pending", "c:0": "matched"})
    after = snap(invoices={"a:0": "matched", "b:0": "pending", "c:0": "matched", "d:0": "pending", "e:0": "unmatched"})
    assert diff(before, after) == [
        Change("invoice.matched", "a:0"),
        Change("invoice.pending", "d:0"),
        Change("invoice.unmatched", "e:0"),
    ]
    many = {f"x{i:03d}:0": "pending" for i in range(BULK + 1)}
    assert diff(snap(), snap(invoices=many)) == [Change("invoice.pending", "", {"count": BULK + 1})]


def test_a_snapshot_survives_its_dump_and_a_damaged_one_is_none():
    s = snap(rows={"a": ("teb-1", "2026-10-01")}, receipts={"a": "matched"}, months={"2026-10": "closed"})
    assert Snapshot.load(s.dump()) == s
    older = {k: v for k, v in s.dump().items() if k != "invoices"}  # saved before bills were kept
    assert Snapshot.load(older) == s
    assert Snapshot.load(None) is None
    assert Snapshot.load({"month": "2026-11"}) is None
    assert Snapshot.load([1, 2]) is None


def test_taking_a_document_in_queues_a_refresh_and_records_what_arrived(ws):
    add(ws, "teb.xls", teb.account_export(teb.running_rows(teb.ACCOUNT_MOVES)))
    with ws.db() as db:
        kinds = [e.kind for e in events.entries(db)]
        queued = [j["kind"] for j in db.rows("SELECT kind FROM jobs WHERE status = 'queued'")]
    assert kinds == ["document.received", "document.processed"]
    assert queued == [background.REFRESH]


def test_a_refresh_records_what_changed_since_the_last_one(ws):
    assert background.refresh(ws, today=date(2026, 11, 15)) == []  # nothing before it: it only takes note
    add(ws, "teb.xls", teb.account_export(teb.running_rows(teb.ACCOUNT_MOVES)))
    changed = background.refresh(ws, today=date(2026, 11, 15))
    # The rows, and October: it ended, and its page waits for the documents still due.
    assert set(changed) == {"transaction.created", "month.ended"}
    assert background.refresh(ws, today=date(2026, 11, 15)) == []  # nothing new: nothing to tell
    with ws.db() as db:
        created = events.entries(db, "transaction.created")
        [ended] = events.entries(db, "month.ended")
    assert len(created) == changed.count("transaction.created") == len(teb.ACCOUNT_MOVES)
    assert all(e.target and e.detail["account"].startswith("teb-") for e in created)
    assert ended.target == "2026-10"


def test_the_worker_does_a_queued_refresh(ws):
    add(ws, "teb.xls", teb.account_export(teb.running_rows(teb.ACCOUNT_MOVES)))
    from iplikci.jobs.worker import Worker

    worker = Worker(ws.connect, background.handlers(ws))
    with ws.db() as db:
        assert worker.step(db)
        assert jobs.counts(db) == {"done": 1, "queued": 1}  # the refresh asks for the notifications at once
        assert jobs.last_done(db, background.REFRESH) is not None
