"""A demo data folder built from fake bank documents (ADR-0002).

Development, the interface tests and the verification baseline's golden file run here instead of on real
documents. Every document comes from the fake document builders (iplikci.fakes), laid out like the banks' own,
with made-up names, numbers and amounts; the tests use the same builders. The documents go into the folder's
vault the way an import does, so the demo's baseline is taken from the vault and the database like a real one.
Card statements and the other readers' documents have builders too; adding them here changes the golden
baseline, so that is a step of its own. The exchange rates are TCMB's made-up bulletins (fakes.fx), one for every
business day the demo covers, read through TCMB's own reader.
"""

from datetime import date
from decimal import Decimal
from pathlib import Path

from .app import fx, intake
from .app.workspace import Workspace
from .categorize import PERSONAL_TEMPLATE
from .domain.codes import Actor, RateSource, SourceKind
from .fakes import HOLDER, Move, garanti, teb
from .fakes import fx as fake_rates
from .fakes.files import text_pdf
from .fx import tcmb
from .fx.provider import weekdays
from .settings.paths import Layout, write_private
from .storage import fx_rates
from .storage.documents import Source

COMPANY = "ÖRNEK TEKNOLOJİ A.Ş."
# The day the demo is looked at: its baseline is taken as on this day, so the golden file never moves.
AS_OF = date(2026, 11, 15)
_SETTINGS = f"""\
# İplikçi Nedim demo veri klasörü: bütün belgeler sahtedir ve kodla üretildi (iplikci dev demo).

[identity]
names = ["{HOLDER}"]
business_names = ["Örnek Teknoloji A.Ş."]
"""


# --- the demo workspace -------------------------------------------------------------------------------

_TEB_NUMBER = "123456789"
_TEB_FOLDER = f"Bankalar/TEB/Vadesiz Hesap TL {_TEB_NUMBER}"
_GARANTI_FOLDER = "Bankalar/Garanti BBVA/Vadesiz Hesap TL 1234567"
_BROKERAGE_FOLDER = "Bankalar/Garanti BBVA/Yatırım Hesabı 1234567-101"
_INBOX = "Gelen Belgeler"
_SECOND_LIST_FROM = date(2026, 7, 5)
_GAS = [Decimal(n) for n in (1500, 1300, 900, 500, 250, 150, 120, 120, 200, 600)]  # a bill moving with the seasons


def _teb_moves(month: int) -> list[Move]:
    """A month on the main account: salary, rent, bills, subscriptions and shopping (all made up)."""

    def on(day: int) -> date:
        return date(2026, month, day)

    moves = [
        Move(on(1), "ÖRNEK İŞVEREN A.Ş. den gelen havale", Decimal(40000)),
        Move(on(3), "VELİ ÖRNEKSOY KİRA ÖDEMESİ", Decimal(-15000)),
        Move(on(3), "FAST Ücreti", Decimal(-8)),
        Move(on(6), "İGDAŞ FATURA ÖDEMESİ", -_GAS[month - 1]),
        Move(on(8), "TURKCELL FATURA ÖDEMESİ", Decimal(-450)),
        Move(on(9), "SPOTIFY ISTANBUL TR", Decimal("-99.99")),
        Move(on(12), "MIGROS ORNEK SUBE ISTANBUL", Decimal(-2150)),
        Move(on(19), "ORNEK KAHVE", Decimal(-180)),
        Move(on(22), "MIGROS ORNEK SUBE ISTANBUL", Decimal(-1840)),
    ]
    if month == 4:
        moves.append(Move(on(25), "TEKNOSA ORNEK AVM", Decimal(-8500)))
    if month == 7:
        moves.append(Move(on(14), "TURKISH AIRLINES ISTANBUL", Decimal(-4200)))
    return sorted(moves, key=lambda m: m.day)


def _teb_lists() -> dict[str, bytes]:
    """The main account in two exports, January–June and from 5 July on: the first days of July were never
    downloaded, so July cannot close."""
    first = [m for month in range(1, 7) for m in _teb_moves(month)]
    later = [m for month in range(7, 11) for m in _teb_moves(month)]
    second = [m for m in later if m.day >= _SECOND_LIST_FROM]
    opening = sum((m.amount for m in first + later if m.day < _SECOND_LIST_FROM), Decimal(0))
    who = f"TEB Vadesiz TL {_TEB_NUMBER} Hesap Hareketleri.xls"
    return {
        f"{_TEB_FOLDER}/2026-01-01 - 2026-06-30 {who}": teb.account_export(
            teb.running_rows(first), _TEB_NUMBER, period="01/01/2026 - 30/06/2026"
        ),
        f"{_TEB_FOLDER}/{_SECOND_LIST_FROM} - 2026-10-31 {who}": teb.account_export(
            teb.running_rows(second, opening), _TEB_NUMBER, period=f"{_SECOND_LIST_FROM:%d/%m/%Y} - 31/10/2026"
        ),
    }


def _garanti_receipts() -> dict[str, bytes]:
    """Two dues payments from an account whose lists the demo does not have: receipts with no statement."""
    havale = [
        (40, 322, "EYLÜL AİDAT ÖDEMESİ"),
        (40, 350, "ALACAKLI HESAP"),
        (172, 350, ":"),
        (184, 350, "00759 / 7654321 ÖRNEK SİTE YÖNETİMİ"),
        (40, 421, "MASRAF TOPLAMI"),
        (172, 421, ":"),
        (184, 421, "4,43 TL"),
    ]
    fast = garanti.fast_body("ŞUBAT AİDAT ÖDEMESİ", "ÖRNEK SİTE YÖNETİMİ")
    return {
        f"{_GARANTI_FOLDER}/2026-02-14 Garanti Giden FAST Dekont.pdf": garanti.receipt(
            "HESAPTAN FAST", "106/1234567", HOLDER, fast, "- 1.250,00 TL", date(2026, 2, 14), "10.15.42.000001"
        ),
        f"{_GARANTI_FOLDER}/2026-09-10 Garanti Giden Havale Dekont.pdf": garanti.receipt(
            "HESAPTAN HESABA HAVALE",
            "106/1234567",
            HOLDER,
            havale,
            "- 1.250,00 TL",
            date(2026, 9, 10),
            "11.02.07.000002",
        ),
    }


def _brokerage_statements() -> dict[str, bytes]:
    """Month-end holdings of the brokerage account, June–October: quiet months with no cash moves."""
    values = {
        date(2026, 6, 30): "1,234.50",
        date(2026, 7, 31): "1,260.00",
        date(2026, 8, 31): "1,198.00",
        date(2026, 9, 30): "1,305.50",
        date(2026, 10, 30): "1,342.00",  # the 31st is a Saturday: the month's last business day
    }
    out = {}
    for day, value in values.items():
        page = garanti.holdings_page(f"{day:%d/%m/%Y}", [("ORNEK", "ÖRNEK SANAYİ A.Ş.", "20.000", value)], value, value)
        name = f"{day:%Y-%m}-01 - {day:%Y-%m}-{_month_end(day):%d} Garanti Yatırım 1234567-101 Hesap Hareketleri.pdf"
        out[f"{_BROKERAGE_FOLDER}/{name}"] = text_pdf(page)
    return out


def _month_end(day: date) -> date:
    following = date(day.year + day.month // 12, day.month % 12 + 1, 1)
    return date.fromordinal(following.toordinal() - 1)


def _inbox(lists: dict[str, bytes]) -> dict[str, bytes]:
    """Waiting to be filed: a second copy of a list, a company's list and a form that is not a statement."""
    company = teb.running_rows([Move(date(2026, 10, 2), "ÖRNEK MÜŞTERİ den gelen havale", Decimal(25000))])
    form = text_pdf([(201, 97, "SGK Otomatik Ödeme Talimat Formu"), (70, 146, "Türk Ekonomi Bankası A.Ş.")])
    return {
        f"{_INBOX}/HesapHareketleri.xls": next(iter(lists.values())),
        f"{_INBOX}/HesapHareketleri (1).xls": teb.account_export(
            company, "555666777", COMPANY, period="01/10/2026 - 31/10/2026"
        ),
        f"{_INBOX}/TalimatFormu.pdf": form,
    }


def documents() -> dict[str, bytes]:
    """Every document of the demo, by its path in the workspace."""
    lists = _teb_lists()
    return lists | _garanti_receipts() | _brokerage_statements() | _inbox(lists)


def _store_rates(ws: Workspace, today: date) -> int:
    """TCMB's made-up bulletins for every business day from the demo's first day through AS_OF or today, whichever
    is later: the screens have a provider's rates to show, and a service on the demo finds no day to fetch from the
    network. A day's rates are the same whenever the demo is built. How many days were stored."""
    with ws.db() as db, db.transaction():
        start = fx.history_start(db)
        days = list(weekdays(start, max(AS_OF, today))) if start else []
        for day in days:
            bulletin = tcmb.parse(fake_rates.tcmb_xml(day, fake_rates.tcmb_rates(day)))
            fx_rates.put(db, bulletin.day, RateSource.TCMB, bulletin.quotes)
    return len(days)


def build(target: Path, today: date | None = None) -> Path:
    """Make a demo data folder at target, which must be missing or empty: nothing is overwritten. Its documents
    go into the vault as an import ("Bankalar/…") and as the inbox would bring them ("Gelen Belgeler/…"); its rates
    reach today (the computer's day when None)."""
    if target.exists() and (not target.is_dir() or any(target.iterdir())):
        raise FileExistsError(f"{target} boş değil: demo veri klasörü yalnızca boş ya da olmayan bir klasöre kurulur")
    layout = Layout(target)
    layout.ensure()
    write_private(layout.settings, _SETTINGS)
    write_private(layout.personal_rules, PERSONAL_TEMPLATE)
    ws = Workspace.load(target)
    incoming = []
    for relative, data in documents().items():
        folder, _, name = relative.rpartition("/")
        kind = SourceKind.INBOX if folder == _INBOX else SourceKind.IMPORT
        incoming.append(intake.Incoming(name, data, Source(kind, name, folder)))
    intake.apply(ws, intake.plan_documents(ws, incoming), Actor.SYSTEM)
    _store_rates(ws, today or date.today())
    return target
