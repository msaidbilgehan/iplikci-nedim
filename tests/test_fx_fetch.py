"""Fetching the exchange rates and keeping them (architecture §15): the history once, for the days the data covers;
the day's bulletin from 16:30; ECB's reference rates when TCMB cannot be reached; and where it all stands. Every
answer is a fake one (conftest.FakeProviders), and a run's pauses are counted, never slept."""

import logging
from datetime import date, datetime, time
from decimal import Decimal

import pytest
from fastapi.testclient import TestClient

from iplikci import cli, egress
from iplikci.api.app import create_app
from iplikci.api.context import Context
from iplikci.app import background, fx, kinds
from iplikci.app.workspace import Workspace
from iplikci.cli import service as service_cli
from iplikci.domain.codes import RateSource
from iplikci.fakes import Move, teb
from iplikci.fakes import fx as fake
from iplikci.fx import ecb, frankfurter, tcmb
from iplikci.fx.book import RateBook
from iplikci.fx.provider import weekdays
from iplikci.service import client, instance
from iplikci.settings import config
from iplikci.storage import fx_rates, jobs

from conftest import add

# The data covers Thursday 29 October 2026, a holiday with no bulletin, to Monday 2 November; the runs are on
# Tuesday the 3rd. The weekend between asks nothing.
REPUBLIC_DAY, FRIDAY, MONDAY, TUESDAY = date(2026, 10, 29), date(2026, 10, 30), date(2026, 11, 2), date(2026, 11, 3)


class Pauses(list[float]):
    """A pace's sleep: the pauses a run made, kept instead of slept."""

    def __call__(self, seconds: float) -> None:
        self.append(seconds)


@pytest.fixture
def pauses(monkeypatch) -> Pauses:
    """The pauses of every run in the test, the job's too."""
    kept = Pauses()
    monkeypatch.setattr(fx, "POLITE", fx.Pace(sleep=kept))
    return kept


@pytest.fixture
def covered(ws) -> Workspace:
    """ws whose data covers REPUBLIC_DAY to MONDAY: a TEB list of those days."""
    moves = [Move(FRIDAY, "MARKET ALISVERIS", Decimal(-80)), Move(MONDAY, "ORNEK KAHVE", Decimal(-20))]
    add(ws, "liste.xls", teb.account_export(teb.running_rows(moves, Decimal(1000)), period="29/10/2026 - 02/11/2026"))
    return ws


def publish(providers, *days: date, today: date | None = None) -> None:
    """TCMB's fake bulletin for each of days, at its own address; today.xml holds today's when given."""
    for day in days:
        providers.answers[(egress.TCMB, tcmb.day_path(day))] = (200, fake.tcmb_xml(day, fake.tcmb_rates(day)))
    if today is not None:
        providers.answers[(egress.TCMB, tcmb.TODAY)] = (200, fake.tcmb_xml(today, fake.tcmb_rates(today)))


def reference(*days: date) -> dict[date, dict[str, str]]:
    return {day: fake.reference_rates(day) for day in days}


def asked_days(ws: Workspace, source: RateSource = RateSource.TCMB) -> dict[date, bool]:
    with ws.db() as db:
        return {day: a.published for day, a in fx_rates.asked(db, source).items()}


def book(ws: Workspace) -> RateBook:
    with ws.db() as db:
        return RateBook(fx_rates.every(db))


def providers_are(ws: Workspace, *names: str) -> None:
    config.update(ws.layout.settings, "fx", {"providers": list(names)})


# --- the history ---------------------------------------------------------------------------------------


def test_the_data_covers_the_days_from_its_oldest_statement_or_row(ws, covered):
    with covered.db() as db:
        assert fx.first_day(db) == REPUBLIC_DAY  # the list's period begins before its first row
    empty = Workspace.load(ws.home.parent / "bos")
    with empty.db() as db:
        assert fx.first_day(db) is None


def test_the_history_asks_tcmb_for_every_weekday_the_data_covers_the_newest_first(covered, providers, pauses):
    publish(providers, FRIDAY, MONDAY, today=TUESDAY)
    done = fx.fetch(covered, history=True, today=TUESDAY)
    assert providers.paths(egress.TCMB) == [
        "/kurlar/today.xml",
        "/kurlar/202611/02112026.xml",
        "/kurlar/202610/30102026.xml",
        "/kurlar/202610/29102026.xml",  # 404: Republic Day
    ]  # never the weekend between
    assert (done.asked, done.stored, done.missing, done.error, done.more) == (4, 3, 0, "", False)
    assert pauses == [0.5, 0.5, 0.5]  # between two requests, never before the first
    assert asked_days(covered) == {REPUBLIC_DAY: False, FRIDAY: True, MONDAY: True, TUESDAY: True}
    quote = book(covered).on("USD", MONDAY)
    published = {r.code: r for r in fake.tcmb_rates(MONDAY)}["USD"]
    assert quote is not None and quote.source is RateSource.TCMB and str(quote.buying) == published.buying


def test_a_day_once_answered_is_never_asked_again(covered, providers, pauses):
    publish(providers, FRIDAY, MONDAY, today=TUESDAY)
    fx.fetch(covered, history=True, today=TUESDAY)
    providers.asked.clear()
    done = fx.fetch(covered, history=True, today=TUESDAY)
    assert providers.asked == [] and (done.asked, done.stored, done.missing) == (0, 0, 0)
    assert "yoktu" in done.message


def test_a_run_stops_at_its_limit_and_the_next_goes_on_where_it_stopped(covered, providers, pauses):
    publish(providers, FRIDAY, MONDAY, today=TUESDAY)
    first = fx.fetch(covered, history=True, today=TUESDAY, pace=fx.Pace(limit=2, sleep=pauses))
    assert (first.asked, first.missing, first.more) == (2, 2, True)
    assert "bir sonraki çekimde" in first.message
    second = fx.fetch(covered, history=True, today=TUESDAY, pace=fx.Pace(limit=2, sleep=pauses))
    assert (second.asked, second.missing, second.more) == (2, 0, False)
    assert providers.paths(egress.TCMB)[2:] == ["/kurlar/202610/30102026.xml", "/kurlar/202610/29102026.xml"]


def test_ten_business_days_in_a_row_without_a_bulletin_are_an_error_never_holidays(ws, providers, pauses):
    rows = teb.running_rows([Move(date(2026, 10, 20), "MARKET", Decimal(-5))], Decimal(9))
    add(ws, "ekim.xls", teb.account_export(rows, period="19/10/2026 - 02/11/2026"))  # 11 business days
    providers_are(ws, "document", "tcmb")
    publish(providers, today=TUESDAY)  # today's bulletin, but every day's own file answers 404: they moved
    done = fx.fetch(ws, history=True, today=TUESDAY)
    assert "üst üste" in done.error and len(providers.paths(egress.TCMB)) == 1 + fx.SILENCE
    assert asked_days(ws) == {TUESDAY: True}  # none of them is marked a holiday: a later run asks again


def test_the_history_reaches_no_further_back_than_the_new_lira(ws, providers, pauses):
    moves = [Move(date(2004, 12, 30), "ESKI KAYIT", Decimal(-1))]
    add(ws, "eski.xls", teb.account_export(teb.running_rows(moves, Decimal(10)), period="30/12/2004 - 03/01/2005"))
    with ws.db() as db:
        assert fx.first_day(db) == date(2004, 12, 30) and fx.history_start(db) == fx.EARLIEST
    publish(providers, date(2005, 1, 3), date(2005, 1, 4), today=date(2005, 1, 5))
    fx.fetch(ws, history=True, today=date(2005, 1, 5))
    paths = ["/kurlar/today.xml", "/kurlar/200501/04012005.xml", "/kurlar/200501/03012005.xml"]
    assert providers.paths(egress.TCMB) == paths  # Monday the 3rd was the new lira's first business day


# --- the day -------------------------------------------------------------------------------------------


def test_the_daily_fetch_takes_todays_bulletin_and_the_days_missed_since_the_newest(covered, providers, pauses):
    with covered.db() as db:
        fx_rates.put(db, FRIDAY, RateSource.TCMB, tcmb.parse(fake.tcmb_xml(FRIDAY, fake.tcmb_rates(FRIDAY))).quotes)
    publish(providers, MONDAY, today=TUESDAY)
    done = fx.fetch(covered, today=TUESDAY)
    # Republic Day is before the newest bulletin: the history asks for it, the day's fetch does not.
    assert providers.paths(egress.TCMB) == ["/kurlar/today.xml", "/kurlar/202611/02112026.xml"]
    assert (done.stored, done.missing) == (2, 1)


def test_todays_bulletin_before_15_30_is_the_day_befores_and_leaves_today_for_a_later_run(covered, providers, pauses):
    publish(providers, today=MONDAY)  # Tuesday morning: today.xml still holds Monday's bulletin
    fx.fetch(covered, today=TUESDAY)
    assert asked_days(covered) == {MONDAY: True}  # Monday's file is not asked again; Tuesday is not done yet
    publish(providers, today=TUESDAY)
    fx.fetch(covered, today=TUESDAY)
    assert asked_days(covered) == {MONDAY: True, TUESDAY: True}
    assert providers.paths(egress.TCMB) == ["/kurlar/today.xml", "/kurlar/today.xml"]


def test_a_weekend_day_asks_for_no_bulletin_of_its_own(covered, providers, pauses):
    publish(providers, FRIDAY)
    fx.fetch(covered, today=date(2026, 10, 31))  # a Saturday, with no bulletin kept yet
    assert providers.asked == []


# --- when TCMB cannot be reached -------------------------------------------------------------------------


def test_when_tcmb_cannot_be_reached_ecb_fills_its_days_and_tcmb_is_asked_again_later(covered, providers, pauses):
    providers.down.add(egress.TCMB)
    providers.answers[(egress.ECB, ecb.RECENT)] = (200, fake.ecb_xml(reference(REPUBLIC_DAY, FRIDAY, MONDAY)))
    done = fx.fetch(covered, history=True, today=TUESDAY)
    assert providers.asked == [(egress.TCMB, tcmb.TODAY), (egress.ECB, ecb.RECENT)]  # ECB once, for every day
    assert "TCMB" in done.error and "ulaşılamadı" in done.error and not done.more
    assert done.missing == 3  # TCMB's own days are still to come
    # ECB published on Republic Day; Tuesday's rates are not out yet and wait for a later run.
    assert asked_days(covered, RateSource.ECB) == {REPUBLIC_DAY: True, FRIDAY: True, MONDAY: True}
    usd = book(covered).on("USD", MONDAY)
    assert usd is not None and usd.source is RateSource.ECB and usd.buying == usd.selling

    providers.down.clear()
    publish(providers, FRIDAY, MONDAY, today=TUESDAY)
    providers.asked.clear()
    again = fx.fetch(covered, history=True, today=TUESDAY)
    assert {host for host, _ in providers.asked} == {egress.TCMB} and again.missing == 0
    usd = book(covered).on("USD", MONDAY)
    assert usd is not None and usd.source is RateSource.TCMB  # TCMB's own over the reference rate


def test_an_older_history_comes_from_ecbs_whole_history_in_one_request(ws, providers, pauses):
    rows = teb.running_rows([Move(date(2026, 1, 5), "MARKET", Decimal(-5))], Decimal(9))
    add(ws, "ocak.xls", teb.account_export(rows))  # January 2026
    providers.down.add(egress.TCMB)
    # The history begins long before the data (in 1999); ECB published nothing on New Year's Day.
    history = reference(date(2025, 12, 31), date(2026, 1, 2), date(2026, 1, 5), TUESDAY)
    providers.answers[(egress.ECB, ecb.HISTORY)] = (200, fake.ecb_zip(history))
    fx.fetch(ws, history=True, today=TUESDAY)
    assert providers.paths(egress.ECB) == [ecb.HISTORY]
    found = asked_days(ws, RateSource.ECB)
    assert (found[date(2026, 1, 1)], found[date(2026, 1, 2)], found[TUESDAY]) == (False, True, True)
    assert len(found) == 219 and date(2025, 12, 31) not in found  # every weekday of 2026 up to today, no other


def test_frankfurter_fills_the_days_when_the_settings_name_it_before_ecb(covered, providers, pauses):
    providers_are(covered, "document", "tcmb", "frankfurter", "ecb")
    providers.down.add(egress.TCMB)
    path = frankfurter.path(REPUBLIC_DAY - frankfurter.LEAD, TUESDAY)
    rates = reference(date(2026, 10, 28), REPUBLIC_DAY, FRIDAY, MONDAY)
    providers.answers[(egress.FRANKFURTER, path)] = (200, fake.frankfurter_json(rates))
    fx.fetch(covered, history=True, today=TUESDAY)
    assert providers.paths(egress.FRANKFURTER) == [path] and providers.paths(egress.ECB) == []
    assert asked_days(covered, RateSource.FRANKFURTER) == {REPUBLIC_DAY: True, FRIDAY: True, MONDAY: True}


def test_without_tcmb_in_the_settings_the_reference_rates_stand_in_its_place(covered, providers, pauses):
    providers_are(covered, "document", "ecb")
    providers.answers[(egress.ECB, ecb.RECENT)] = (200, fake.ecb_xml(reference(REPUBLIC_DAY, FRIDAY, MONDAY)))
    done = fx.fetch(covered, history=True, today=TUESDAY)
    assert providers.paths(egress.TCMB) == [] and providers.paths(egress.ECB) == [ecb.RECENT]
    assert (done.error, done.missing) == ("", 0)
    assert fx.status(covered, TUESDAY).providers == (RateSource.ECB,)


def test_without_a_provider_in_the_settings_nothing_is_asked(covered, providers, pauses):
    providers_are(covered, "document")
    done = fx.fetch(covered, history=True, today=TUESDAY)
    assert providers.asked == [] and done.missing == 0
    found = fx.status(covered, TUESDAY)
    assert found.providers == () and "ağdan çekilmiyor" in found.summary
    assert fx.request_missing(covered, TUESDAY) is False


def test_a_provider_error_is_recorded_and_logged_never_raised(covered, providers, pauses, caplog):
    providers_are(covered, "document", "tcmb")
    providers.answers[(egress.TCMB, tcmb.TODAY)] = (500, b"<html>hata</html>")
    with caplog.at_level(logging.WARNING, logger="iplikci.fx"):
        done = fx.fetch(covered, history=True, today=TUESDAY)
    assert done.error == "TCMB 500 yanıtı verdi" and done.stored == 0
    assert [r.levelno for r in caplog.records] == [logging.WARNING]
    found = fx.status(covered, TUESDAY)
    assert found.last_error == "TCMB 500 yanıtı verdi" and found.last_run
    assert found.summary == "henüz kur yok · 3 iş günü eksik · son hata: TCMB 500 yanıtı verdi"


# --- where they stand ----------------------------------------------------------------------------------


def test_the_status_tells_the_newest_bulletin_the_days_kept_and_what_is_missing(covered, providers, pauses):
    publish(providers, MONDAY, today=TUESDAY)
    fx.fetch(covered, history=True, today=TUESDAY, pace=fx.Pace(limit=2, sleep=pauses))
    found = fx.status(covered, TUESDAY)
    assert found.sources == (fx.SourceDays(RateSource.TCMB, TUESDAY, 2),) and found.days == 2
    assert (found.start, found.missing, found.last_error) == (REPUBLIC_DAY, 2, "")
    assert found.summary == "TCMB'nin son bülteni 03.11.2026 · 2 günün kurları saklı · 2 iş günü eksik"


def test_the_status_without_documents_waits_for_the_first_one(ws):
    found = fx.status(ws, TUESDAY)
    assert found.providers == (RateSource.TCMB, RateSource.ECB)  # the settings' defaults
    assert found.summary == "henüz kur yok · geçmiş kurlar ilk belge gelince çekilir" and found.missing == 0


# --- the service's jobs --------------------------------------------------------------------------------


def test_the_rates_are_fetched_every_day_from_half_past_four(ws):
    [job] = [p for p in background.PERIODIC if p.kind == kinds.FX_RATES]
    assert job.payload == {"history": True}
    assert job.key(datetime.combine(TUESDAY, time(16, 29))) == "fx.rates@2026-11-02"
    assert job.key(datetime.combine(TUESDAY, time(16, 30))) == "fx.rates@2026-11-03"
    assert kinds.FX_RATES in background.handlers(ws) and kinds.LABELS[kinds.FX_RATES]


def test_the_job_queues_the_next_run_at_its_limit_and_new_rates_refresh_the_analysis(covered, providers, monkeypatch):
    monkeypatch.setattr(fx, "POLITE", fx.Pace(limit=1, sleep=lambda _s: None))
    today = date.today()  # the job runs on the computer's day, a weekend or not
    publish(providers, *weekdays(REPUBLIC_DAY, today), today=today)
    with covered.db() as db:
        db.execute("DELETE FROM jobs")
    background.handlers(covered)[kinds.FX_RATES]({"history": True})
    with covered.db() as db:
        waiting = {(j["kind"], j["payload"]) for j in db.rows("SELECT kind, payload FROM jobs WHERE status = 'queued'")}
    assert waiting == {(kinds.FX_RATES, '{"history": true}'), (kinds.REFRESH, "{}")}


def test_the_service_start_queues_the_history_once_and_only_when_days_are_missing(covered, providers, pauses):
    assert fx.request_missing(covered, TUESDAY) is True
    assert fx.request_missing(covered, TUESDAY) is False  # one waits already
    with covered.db() as db:
        [job] = [j for j in db.rows("SELECT * FROM jobs WHERE kind = ?", (kinds.FX_RATES,))]
        jobs.finish(db, int(job["id"]), "2026-11-03T13:30:00+00:00")
    publish(providers, FRIDAY, MONDAY, today=TUESDAY)
    fx.fetch(covered, history=True, today=TUESDAY)
    assert fx.request_missing(covered, TUESDAY) is False  # nothing is missing any more


# --- the System screen, the interface's request and the command line ----------------------------------


def test_the_system_status_carries_where_the_rates_stand(covered, providers, pauses):
    publish(providers, FRIDAY, MONDAY, today=TUESDAY)
    fx.fetch(covered, history=True, today=TUESDAY)
    context = Context(ws=covered, token="belirtec", today=lambda: TUESDAY)
    app = TestClient(create_app(context), base_url="http://127.0.0.1:8643")
    rates = app.get("/api/system", headers={"Authorization": "Bearer belirtec"}).json()["rates"]
    assert rates["providers"] == ["tcmb", "ecb"]
    assert rates["sources"] == [{"source": "tcmb", "newest": "2026-11-03", "days": 3}]
    assert (rates["start"], rates["missing"], rates["last_error"]) == ("2026-10-29", 0, "") and rates["last_run"]
    assert rates["summary"] == "TCMB'nin son bülteni 03.11.2026 · 3 günün kurları saklı · geçmiş tamam"


def test_the_interface_asks_the_worker_for_a_fetch_the_history_too(ws):
    app = TestClient(create_app(Context(ws=ws, token="belirtec")), base_url="http://127.0.0.1:8643")
    bearer = {"Authorization": "Bearer belirtec"}
    assert app.post("/api/fx/fetch", headers=bearer).status_code == 202
    assert app.post("/api/fx/fetch", headers=bearer, json={"history": True}).json() == {"queued": True}
    with ws.db() as db:
        queued = [j["payload"] for j in db.rows("SELECT payload FROM jobs WHERE kind = ?", (kinds.FX_RATES,))]
    assert queued == ['{"history": false}', '{"history": true}']
    providers_are(ws, "document")
    refused = app.post("/api/fx/fetch", headers=bearer)
    assert refused.status_code == 409 and refused.json()["code"] == "fx_no_provider"


def test_the_command_fetches_itself_when_no_service_runs(covered, providers, pauses, monkeypatch, capsys):
    monkeypatch.setenv("IPLIKCI_HOME", str(covered.home))
    today = date.today()  # the command runs on the computer's day
    publish(providers, *weekdays(REPUBLIC_DAY, today), today=today)
    assert cli.main(["kur", "al", "--gecmis"]) == 0
    assert "günün kurları geldi" in capsys.readouterr().out
    assert cli.main(["kur", "durum"]) == 0
    out = capsys.readouterr().out
    assert "Kurlar: TCMB'nin son bülteni" in out and "geçmiş tamam" in out
    assert "Sağlayıcılar: TCMB; ulaşılamazsa ECB" in out and "Geçmişin ilk günü: 29.10.2026" in out
    assert "Son çekim: " in out and "henüz yok" not in out


def test_the_command_says_when_the_providers_fail(covered, providers, pauses, monkeypatch, capsys):
    monkeypatch.setenv("IPLIKCI_HOME", str(covered.home))
    providers.down |= {egress.TCMB, egress.ECB}
    assert cli.main(["kur", "al", "--gecmis"]) == 1  # the history has days to ask on any day of the week
    assert "ulaşılamadı" in capsys.readouterr().out
    assert cli.main(["kur", "durum"]) == 0 and "Son hata: TCMB: www.tcmb.gov.tr" in capsys.readouterr().out


def test_the_command_asks_the_running_service_to_fetch(covered, providers, monkeypatch, capsys):
    monkeypatch.setenv("IPLIKCI_HOME", str(covered.home))
    asked: list[tuple[str, str, object]] = []
    monkeypatch.setattr(client, "call", lambda ws, method, path, body=None: asked.append((method, path, body)) or {})
    with instance.held(covered.run, instance.Holder(111, covered.port, "", "")):
        assert cli.main(["kur", "al", "--gecmis"]) == 0
    assert asked == [("POST", "/api/fx/fetch", {"history": True})] and providers.asked == []
    assert "Servis kurları çekiyor" in capsys.readouterr().out


def test_the_service_status_has_a_line_for_the_rates_unless_the_service_is_older(ws):
    lines = service_cli._system_lines({"rates": {"summary": "TCMB'nin son bülteni 02.11.2026"}}, ws)
    assert "Kurlar: TCMB'nin son bülteni 02.11.2026" in lines
    assert not [line for line in service_cli._system_lines({}, ws) if line.startswith("Kurlar")]
