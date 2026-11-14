"""A demo data folder built from fake bank documents (ADR-0002).

Development, the interface tests and the verification baseline's golden file run here instead of on real
documents. Every document comes from the fake document builders (iplikci.fakes), laid out like the banks' own,
with made-up names, numbers and amounts; the tests use the same builders. The documents go into the folder's
vault the way an import does, so the demo's baseline is taken from the vault and the database like a real one.
Four credit cards opened over the year carry their statements, one card of each bank whose card statements are read.
The other readers' documents have builders too; adding them here changes the golden baseline, so each is a step of its
own. The exchange rates are TCMB's made-up bulletins (fakes.fx), one for every
business day the demo covers, read through TCMB's own reader. Two notes stand in Claude's memory (ADR-0023), as Claude
would have written them, so the Claude bağlantısı screen shows what it keeps.
"""

from collections.abc import Callable, Sequence
from dataclasses import dataclass
from datetime import date, timedelta
from decimal import Decimal
from pathlib import Path

from .app import fx, intake, memory
from .app.workspace import Workspace
from .categorize import PERSONAL_TEMPLATE
from .domain.codes import Actor, MemoryKind, RateSource, SourceKind
from .fakes import HOLDER, CardRow, CardTerms, Move, charged, garanti, isbank, qnb, teb
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

# Kurlar demonun kendi sahte TCMB bültenlerinden: demo ağdan kur istemez.
[fx]
providers = ["document"]

# Demo yeni sürümü de sormaz (ADR-0022).
[updates]
mode = "off"
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
    paid = _card_payments()
    first = sorted(
        [m for month in range(1, 7) for m in _teb_moves(month)] + [m for m in paid if m.day.month < 7], key=_day
    )
    later = sorted(
        [m for month in range(7, 11) for m in _teb_moves(month)] + [m for m in paid if m.day.month >= 7], key=_day
    )
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


# --- the cards ------------------------------------------------------------------------------------------------

# Four cards opened one after another from May, each cut on a day of its own and paid in full ten days after its cut:
# the TEB card from the TEB account, whose list shows it, the others from accounts at their own banks the demo has no
# lists of. Their statements up to the demo's day are here, so October closes; November's payments fall after the TEB
# account's last list and stand among the payments to come. A subscription is billed the same day and amount every
# month; the shops are visited on other days for other amounts, and not every month, so none of them makes a series.
_DUE_DAYS = 10
_LIST_END = date(2026, 10, 31)
_TEB_CARD = "4321"
_SHOP_SHARES = tuple(Decimal(s) for s in ("1.00", "0.62", "1.35", "0.81", "1.18", "0.74"))
_SHOP_SHIFTS = (0, 6, -4, 3, -7, 2)


@dataclass(frozen=True, slots=True)
class _Buy:
    day: int
    merchant: str
    amount: Decimal
    subscription: bool = False

    def on(self, month: date, index: int) -> CardRow | None:
        """This purchase in the month of a card's index-th statement, if it was made that month."""
        if self.subscription:
            return CardRow(date(month.year, month.month, self.day), self.merchant, self.amount)
        k = len(self.merchant)
        if (index + k) % 4 == 3:
            return None  # a month without it
        day = self.day + _SHOP_SHIFTS[(index + 2 * k) % len(_SHOP_SHIFTS)]
        share = _SHOP_SHARES[(index + k) % len(_SHOP_SHARES)]
        return CardRow(
            date(month.year, month.month, day), self.merchant, (self.amount * share).quantize(Decimal("0.1"))
        )


@dataclass(frozen=True, slots=True)
class _Card:
    folder: str  # where its statements go, as an import names them
    name: str  # the statement's file name after its cut date
    last4: str
    first_cut: date
    cuts: int
    limit: Decimal
    payment: str  # how its statement prints a payment
    buys: tuple[_Buy, ...]
    build: Callable[[Sequence[CardRow], date, Decimal, str, CardTerms], bytes]


def _teb_card(rows: Sequence[CardRow], cut: date, previous: Decimal, last4: str, terms: CardTerms) -> bytes:
    return teb.bonus_statement([rows], cut, previous, last4, terms=terms)


def _garanti_card(rows: Sequence[CardRow], cut: date, previous: Decimal, last4: str, terms: CardTerms) -> bytes:
    return garanti.bonus_statement([rows], cut, previous, last4, terms=terms)


def _qnb_card(rows: Sequence[CardRow], cut: date, previous: Decimal, last4: str, terms: CardTerms) -> bytes:
    return qnb.card_statement([rows], cut, previous, last4, terms=terms)


def _isbank_card(rows: Sequence[CardRow], cut: date, previous: Decimal, last4: str, terms: CardTerms) -> bytes:
    return isbank.maximum_statement([rows], cut, previous, last4, terms=terms)


_CARDS = (
    _Card(
        "Bankalar/TEB/Bonus Kart 4321",
        "TEB Bonus Kart Ekstresi.pdf",
        _TEB_CARD,
        date(2026, 6, 5),
        6,
        Decimal(60000),
        "CEPTETEB ÖDEME TEŞEKKÜR EDERİZ",
        (
            _Buy(9, "A101 ORNEK MAGAZA ISTANBUL", Decimal(450)),
            _Buy(15, "SHELL ORNEK ISTASYON", Decimal(900)),
            _Buy(22, "YEMEKSEPETI ORNEK", Decimal(300)),
        ),
        _teb_card,
    ),
    _Card(
        "Bankalar/Garanti BBVA/Bonus Kart 2468",
        "Garanti Bonus Kart Ekstresi.pdf",
        "2468",
        date(2026, 7, 10),
        5,
        Decimal(45000),
        "ÖDEMENİZ İÇİN TEŞEKKÜR EDERİZ",
        (
            _Buy(3, "NETFLIX.COM", Decimal("229.99"), subscription=True),
            _Buy(13, "MIGROS ORNEK SUBE ISTANBUL", Decimal(900)),
            _Buy(19, "ORNEK ECZANE", Decimal(200)),
        ),
        _garanti_card,
    ),
    _Card(
        "Bankalar/QNB/Kredi Kartı 1357",
        "QNB Kredi Kartı Ekstresi.pdf",
        "1357",
        date(2026, 8, 12),
        4,
        Decimal(120000),
        "Ödeme - Tesekkür Ederiz -",
        (
            _Buy(2, "YOUTUBE PREMIUM GOOGLE", Decimal("79.99"), subscription=True),
            _Buy(10, "ORNEK RESTORAN KADIKOY", Decimal(600)),
            _Buy(21, "HEPSIBURADA ORNEK", Decimal(700)),
        ),
        _qnb_card,
    ),
    _Card(
        "Bankalar/İş Bankası/Maximum Kart 9753",
        "İş Bankası Maximum Kart Ekstresi.pdf",
        "9753",
        date(2026, 9, 7),
        3,
        Decimal(60000),
        "9999-1234567 HESAPTAN AKTARIM İNTERAKTİF",
        (
            _Buy(12, "BIM ORNEK MAGAZA", Decimal(350)),
            _Buy(17, "ORNEK KITAPEVI KADIKOY", Decimal(180)),
            _Buy(25, "IKEA ORNEK", Decimal(1100)),
        ),
        _isbank_card,
    ),
)


@dataclass(frozen=True, slots=True)
class _Statement:
    cut: date
    previous: Decimal
    rows: tuple[CardRow, ...]
    terms: CardTerms

    @property
    def total(self) -> Decimal:
        return self.previous + charged(self.rows)


def _month_on(day: date, months: int = 1) -> date:
    index = day.month - 1 + months
    return date(day.year + index // 12, index % 12 + 1, day.day)


def _statements(card: _Card) -> list[_Statement]:
    """The card's statements, oldest first: the first starts from nothing (the card was opened in its period), each
    later one carries the debt before it and the payment that cleared it."""
    cuts = [_month_on(card.first_cut, i) for i in range(card.cuts)]
    out: list[_Statement] = []
    previous = Decimal(0)
    for i, cut in enumerate(cuts):
        start = (cuts[i - 1] if i else _month_on(cut, -1)) + timedelta(days=1)
        rows = [CardRow(out[-1].terms.due, card.payment, -previous)] if out else []
        for buy in card.buys:
            for month in (start, cut):
                row = buy.on(month, i)
                if row is not None and row.day is not None and start <= row.day <= cut:
                    rows.append(row)
        rows.sort(key=lambda r: r.day or cut)
        total = previous + charged(rows)
        terms = CardTerms(
            cut + timedelta(days=_DUE_DAYS),
            (total * Decimal("0.4")).quantize(Decimal("0.01")),
            card.limit,
            _month_on(cut),
        )
        out.append(_Statement(cut, previous, tuple(rows), terms))
        previous = total
    return out


def _card_statements() -> dict[str, bytes]:
    out = {}
    for card in _CARDS:
        for s in _statements(card):
            out[f"{card.folder}/{s.cut} {card.name}"] = card.build(s.rows, s.cut, s.previous, card.last4, s.terms)
    return out


def _card_payments() -> list[Move]:
    """The TEB card's payments from the TEB account, on their due dates up to its last list."""
    teb_card = next(card for card in _CARDS if card.last4 == _TEB_CARD)
    return [
        Move(s.terms.due, f"545616******{_TEB_CARD} no.lu Kredi Kartına Ödenen Tutar", -s.total)
        for s in _statements(teb_card)
        if s.terms.due is not None and s.terms.due <= _LIST_END and s.total > 0
    ]


def _day(move: Move) -> date:
    return move.day


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
    return lists | _garanti_receipts() | _brokerage_statements() | _card_statements() | _inbox(lists)


def _store_rates(ws: Workspace) -> int:
    """TCMB's made-up bulletins for every business day from the demo's first day through AS_OF: the screens have a
    provider's rates to show, and the same ones whenever and on whatever day the demo is built, its newest among
    them. The demo's settings ask no provider, so a service on it never reaches the network for more. How many days
    were stored."""
    with ws.db() as db, db.transaction():
        start = fx.history_start(db)
        days = list(weekdays(start, AS_OF)) if start else []
        for day in days:
            bulletin = tcmb.parse(fake_rates.tcmb_xml(day, fake_rates.tcmb_rates(day)))
            fx_rates.put(db, bulletin.day, RateSource.TCMB, bulletin.quotes)
    return len(days)


def build(target: Path) -> Path:
    """Make a demo data folder at target, which must be missing or empty: nothing is overwritten. Its documents
    go into the vault as an import ("Bankalar/…") and as the inbox would bring them ("Gelen Belgeler/…"); its rates
    reach AS_OF."""
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
    _store_rates(ws)
    _remember(ws)
    return target


# What Claude keeps across conversations, as it would have written it: how the user wants the month told, and what
# they save towards. No amount: the tools give those fresh each time.
_NOTES = (
    (
        "ozet-bicimi",
        MemoryKind.FEEDBACK,
        "Aylık özeti önce bir tabloyla, sonra birkaç cümleyle ister",
        (
            "Kullanıcı aylık özeti önce gelir, gider ve kalanı yan yana gösteren bir tabloyla, sonra iki üç cümleyle "
            "istiyor.\nNeden: rakamları yan yana görmeden yoruma güvenmiyor.\nNasıl: tabloyu month_end'in "
            "toplamlarından kurun, yorumu tablonun altına yazın."
        ),
    ),
    (
        "acil-durum-fonu",
        MemoryKind.PROJECT,
        "2026 sonuna kadar üç aylık gidere denk bir acil durum fonu biriktiriyor",
        (
            "Kullanıcı 2026 sonuna kadar üç aylık giderine denk bir birikim yapmak istiyor.\nNeden: geliri her ay "
            "aynı gün gelmiyor.\nNasıl: aylık özette birikimin bu hedefe göre nerede durduğunu söyleyin; birikimi "
            "net_worth, aylık gideri insights verir."
        ),
    ),
)


def _remember(ws: Workspace) -> None:
    for name, kind, description, body in _NOTES:
        memory.write(ws, name, Actor.MCP, kind=kind, description=description, body=body)
