"""Write the interactive HTML report plus CSV and Excel exports."""

import csv
import json
import re
from collections import defaultdict
from datetime import date, datetime
from decimal import Decimal
from importlib import resources
from pathlib import Path
from typing import Any

from openpyxl import Workbook
from openpyxl.styles import Alignment, Font, PatternFill
from openpyxl.utils import get_column_letter

from . import month_end, mvp_codes
from .analysis import CONFIRMED, NOT_ON_STATEMENT, PROVISIONAL, Dataset, whole
from .categorize import NECESSITY_SLOTS, group_slot
from .domain.codes import DEFAULT_EXPENSE_KINDS, Necessity, TransactionKind
from .domain.labels import ACCOUNT_TYPE, KIND, NECESSITY, currency_label
from .domain.money import round_half_up
from .domain.text import fold, spreadsheet_text
from .insights import HABIT_STATUS, STATUS, Insights, interpret, listed, month_of, saving_of

CLOSING_MONTHS = 7  # months the report's closing card lists: the current one and six before it
PROVISIONAL_LABEL = "Geçici (ekstre bekleniyor)"
LEVELS = list(Necessity)  # the report's levels, in this order
KINDS = [k for k in TransactionKind if k is not TransactionKind.TRANSFER_CANDIDATE]  # the ledger resolves those
ZERO = Decimal(0)

# The report's script still speaks the MVP's codes (mvp_codes); the exports write the Turkish labels.


def _r(value: Decimal) -> Decimal:
    """An amount as the report and the exports show it: two decimals, halves rounded up."""
    return round_half_up(value)


def _script_filter(found: dict[str, Any]) -> dict[str, Any]:
    """A finding's filter as the report's script reads it."""
    kind = found.get("kind")
    return found | {"kind": mvp_codes.KIND[kind]} if kind in mvp_codes.KIND else found


def _closing_payload(months: list[month_end.MonthEnd]) -> list[dict]:
    """The month-end closing of the latest months, newest last, for the report's closing card."""
    return [
        {
            "m": me.month,
            "status": mvp_codes.MONTH[me.status],
            "label": me.label,
            "summary": me.summary,
            "expense": _r(me.totals.expense),
            "income": None if me.totals.income is None else _r(me.totals.income),
            "left": None if me.totals.left is None else _r(me.totals.left),
            "provisional": len(me.provisional),
            "unmatched": len(me.unmatched),
            "open": [f"{a.account.label}: {a.waiting_for}" for a in me.open],
            "file": f"{month_end.FOLDER}/{me.file}",
        }
        for me in months[-CLOSING_MONTHS:]
    ]


def build_payload(
    ds: Dataset, stats: dict[str, int], ins: Insights | None = None, months: list[month_end.MonthEnd] | None = None
) -> dict[str, Any]:
    ins = ins or interpret(ds)
    months = month_end.build(ds, ins) if months is None else months
    account_ids = sorted(ds.accounts, key=lambda a: (ds.accounts[a].bank, ds.accounts[a].type, a))
    account_index = {a: i for i, a in enumerate(account_ids)}
    kinds = KINDS
    groups = ds.groups
    group_index = {g: i for i, g in enumerate(groups)}
    categories = list(ds.categories)
    category_index = {c: i for i, c in enumerate(categories)}
    sources: list[str] = []
    source_index: dict[str, int] = {}

    def src(name: str) -> int:
        if name not in source_index:
            source_index[name] = len(sources)
            sources.append(name)
        return source_index[name]

    with_statements = {s.account for s in ds.statements}
    series_of = {id(t): i for i, s in enumerate(ins.series) for t in s.payments}
    tx = []
    for t in ds.transactions:
        if t.category not in category_index:
            category_index[t.category] = len(categories)
            categories.append(t.category)
        tx.append(
            {
                "d": t.date.isoformat(),
                "a": account_index[t.account],
                "k": kinds.index(t.kind),
                "c": category_index[t.category],
                "m": t.merchant,
                "t": t.description,
                "v": t.amount,
                "i": t.installment,
                "o": t.original,
                "s": src(t.source),
                "n": _level(t.necessity),
                # r: regular payment it belongs to; x: merchant listed as ended (`_biten`);
                # p: from a receipt no statement shows yet (provisional)
                "r": series_of.get(id(whole(ds, t))),  # a split row's parts belong to its series
                "x": 1 if fold(t.merchant) in ds.ended else None,
                "p": 1 if t.provisional else None,
            }
        )
    statuses = [d.status for d in ds.documents]
    return {
        "meta": {
            "generated": datetime.now().strftime("%Y-%m-%d %H:%M"),
            "today": date.today().isoformat(),
            "documents": stats["documents"],
            "duplicates": stats["duplicates"],
            "statements": sum(not s.is_account for s in ds.statements),
            "accountStatements": sum(s.is_account for s in ds.statements),
            "verified": sum(s.verified for s in ds.statements),
            "receipts": statuses.count("dekont"),
            "notices": statuses.count("bildirim"),
            "skipped": statuses.count("atlandi"),
            "business": statuses.count("is"),
            "errors": statuses.count("hata"),
            "warnings": ds.warnings,
            "receiptRows": {
                status: sum(line.status == status for line in ds.receipts)
                for status in (PROVISIONAL, CONFIRMED, NOT_ON_STATEMENT)
            },
        },
        "kinds": [{"id": mvp_codes.KIND[k], "label": KIND[k], "on": k in DEFAULT_EXPENSE_KINDS} for k in kinds],
        "levels": [{"name": NECESSITY[n], "slot": NECESSITY_SLOTS[n]} for n in LEVELS],
        "groups": [{"name": g, "slot": group_slot(groups, g)} for g in groups],
        "categories": [
            {"name": c, "group": group_index.get(ds.categories.get(c, ""), len(groups) - 1)} for c in categories
        ],
        "accounts": [
            {
                "id": a,
                "label": ds.accounts[a].label,
                "bank": ds.accounts[a].bank,
                "type": ACCOUNT_TYPE[ds.accounts[a].type],
                "currency": currency_label(ds.accounts[a].currency),
                "note": ds.accounts[a].note,
                "statements": a in with_statements,
            }
            for a in account_ids
        ],
        "tx": tx,
        "sources": sources,
        "statements": [
            {
                "a": account_index[s.account],
                "cut": s.cut_date.isoformat(),
                "cur": currency_label(s.currency),
                "start": s.start.isoformat() if s.start else None,
                "n": len(s.transactions),
                "total": s.total,
                "calc": s.computed_total,
                "ok": s.verified,
                "checks": [s.checks_ok, s.checks_total] if s.is_account else None,
                "src": s.source,
            }
            for s in ds.statements
        ],
        "coverage": {str(account_index[a]): months for a, months in ds.coverage.items() if a in account_index},
        "documents": [
            {"name": d.name, "status": d.status, "detail": d.detail}
            for d in sorted(ds.documents, key=lambda d: (d.status, d.name))
        ],
        "insights": _insights_payload(ds, ins, account_index, category_index),
        "closing": _closing_payload(months),
    }


def _level(level: Necessity | None) -> int:
    return LEVELS.index(level) if level in LEVELS else -1


def _insights_payload(ds: Dataset, ins: Insights, account_index: dict, category_index: dict) -> dict:
    """The interpretation, with accounts and categories as indexes like the transactions."""
    tl_ = ins.timeline
    window = set(tl_.window)

    def series(s) -> dict:
        change = s.price_change()
        shown = listed(s, ds, tl_.window)
        return {
            "m": s.merchant,
            "c": category_index[s.last.category],
            "lv": _level(s.last.necessity),
            "k": mvp_codes.KIND[s.last.kind],
            "a": sorted({account_index[t.account] for t in s.payments}),
            "v": _r(s.monthly),
            "lastv": _r(abs(s.last.amount)),
            "last": s.last.date.isoformat(),
            "first": s.payments[0].date.isoformat(),
            "next": s.expected.isoformat() if s.expected else None,
            "n": len(s.payments),
            "day": s.day,
            "status": s.status,
            "show": shown,
            "change": [_r(change[0]), _r(change[1]), change[2].isoformat()] if change else None,
            "total": _r(sum((abs(t.amount) for t in s.payments if month_of(t.date) in window), ZERO)),
        }

    fl, tr = ins.flow, ins.trend
    return {
        "asOf": tl_.as_of.isoformat(),
        "lastComplete": tl_.last_complete,
        "window": tl_.window,
        "statusLabels": STATUS,
        "habitLabels": HABIT_STATUS,
        "series": [series(s) for s in ins.series],
        "income": [
            {"m": s.merchant, "v": _r(s.monthly), "last": s.last.date.isoformat(), "status": s.status}
            for s in ins.income
            if s.running
        ],
        "habits": [
            {
                "name": h.name,
                "c": category_index[h.category],
                "lv": _level(h.necessity),
                "byCat": h.by_category,
                "count": h.count,
                "months": h.months,
                "span": h.span,
                "total": _r(h.total),
                "recent": _r(h.recent),
                "monthly": _r(h.monthly),
                "last": h.last.isoformat(),
                "status": h.status,
                "pattern": h.pattern,
            }
            for h in ins.habits
        ],
        "trend": tr
        and {
            "before": tr.before,
            "recent": tr.recent,
            "beforeAvg": tr.before_avg,
            "recentAvg": tr.recent_avg,
            "usualBefore": tr.usual_before,
            "usualRecent": tr.usual_recent,
            "changes": [{"c": ch.category, "before": ch.before, "recent": ch.recent} for ch in tr.changes],
            "big": [{"d": t.date.isoformat(), "m": t.merchant, "v": t.amount} for t in tr.big],
        },
        "flow": fl
        and {
            "income": fl.income,
            "expense": fl.expense,
            "people": fl.people,
            "debt": fl.debt,
            "saving": fl.saving,
            "fx": fl.fx,
            "left": fl.left,
            "debtStart": fl.debt_start,
            "debtEnd": fl.debt_end,
            "otherTypical": fl.other_typical,
        },
        "holdings": [
            {
                "label": h.label,
                "kind": h.kind,
                "cur": currency_label(h.currency),
                "amount": h.amount,
                "value": h.value,
                "asOf": h.as_of.isoformat(),
                "note": h.note,
                "cost": h.cost,
            }
            for h in ins.holdings
        ],
        "findings": [
            {"tone": f.tone, "title": f.title, "text": f.text, "filter": _script_filter(f.filter)} for f in ins.findings
        ],
        "steps": [{"title": st.title, "text": st.text, "monthly": st.monthly} for st in ins.steps],
        "budget": [{"label": b.label, "now": b.now, "plan": b.plan, "note": b.note} for b in ins.budget],
    }


def _template(name: str) -> str:
    return resources.files("iplikci").joinpath("templates", name).read_text(encoding="utf-8")


REPORT_CSP = "default-src 'none'; style-src 'unsafe-inline'; script-src 'unsafe-inline'; img-src data:"


def _json_block(value) -> str:
    # "<" is escaped so no description can close the <script> element early.
    return json.dumps(value, ensure_ascii=False, separators=(",", ":"), default=_json_number).replace("<", "\\u003c")


def _json_number(value: object) -> float:
    """The page's script counts in JavaScript numbers: an exact amount becomes one at this boundary."""
    if isinstance(value, Decimal):
        return float(value)
    raise TypeError(f"{type(value).__name__} JSON'a yazılamaz")


def render_html(payload: dict[str, Any]) -> str:
    """The self-contained report: one file that opens anywhere, with nothing fetched from elsewhere."""
    html = _template("rapor.html")
    values = {
        "/*__CSS__*/": _template("rapor.css"),
        "/*__JS__*/": _template("rapor.js"),
        "__DATA__": _json_block(payload),
    }
    # One pass over the template: text inserted from the data is never searched for placeholders.
    return re.sub("|".join(map(re.escape, values)), lambda m: values[m[0]], html)


def write_html(payload: dict[str, Any], path: Path) -> None:
    path.write_text(render_html(payload), encoding="utf-8")


_COLUMNS = [
    "Tarih",
    "Ay",
    "Banka",
    "Hesap",
    "İşlem türü",
    "Ana grup",
    "Kategori",
    "Gereklilik",
    "İşyeri / kişi",
    "Açıklama",
    "Tutar (TL)",
    "Taksit",
    "Döviz tutarı",
    "Gider sayılır",
    "Kaynak dosya",
    "Durum",
]


def _rows(ds: Dataset):
    for t in ds.transactions:
        a = ds.accounts[t.account]
        yield [
            t.date,
            t.date.strftime("%Y-%m"),
            a.bank,
            a.label,
            KIND[t.kind],
            t.group,
            t.category,
            NECESSITY[t.necessity] if t.necessity else "",
            t.merchant,
            t.description,
            t.amount,
            t.installment,
            t.original,
            "Evet" if t.kind in DEFAULT_EXPENSE_KINDS else "Hayır",
            t.source,
            PROVISIONAL_LABEL if t.provisional else "",
        ]


def write_csv(ds: Dataset, path: Path) -> None:
    """Semicolon-separated, comma decimals, UTF-8 with BOM: opens cleanly in Turkish Excel. A text that starts like a
    formula is written to be read as text."""
    with path.open("w", encoding="utf-8-sig", newline="") as f:
        w = csv.writer(f, delimiter=";")
        w.writerow(_COLUMNS)
        for row in _rows(ds):
            row[0] = row[0].strftime("%d.%m.%Y")
            row[10] = f"{row[10]:.2f}".replace(".", ",")
            w.writerow([spreadsheet_text(v) if isinstance(v, str) and i != 10 else v for i, v in enumerate(row)])


def _as_text(wb: Workbook) -> None:
    """Every text cell kept as text: openpyxl writes a string that starts with "=" as a formula, and a document's
    text (a transfer's description, which its sender writes) must never run when the workbook is opened."""
    for sheet in wb.worksheets:
        for row in sheet.iter_rows():
            for cell in row:
                if cell.data_type == "f":
                    cell.data_type = "s"


_HEADER_FONT = Font(bold=True, color="FFFFFF")
_HEADER_FILL = PatternFill("solid", fgColor="2A78D6")
_MONEY = '#,##0.00 "TL";[Red]-#,##0.00 "TL"'


def _sheet_header(ws, headers: list[str], widths: list[int]) -> None:
    ws.append(headers)
    for i, w in enumerate(widths, 1):
        cell = ws.cell(row=1, column=i)
        cell.font, cell.fill = _HEADER_FONT, _HEADER_FILL
        cell.alignment = Alignment(vertical="center")
        ws.column_dimensions[get_column_letter(i)].width = w
    ws.freeze_panes = "A2"


def _money(ws, first_col: int = 2) -> None:
    for row in ws.iter_rows(min_row=2, min_col=first_col):
        for cell in row:
            cell.number_format = _MONEY
    ws.auto_filter.ref = ws.dimensions


def _monthly(ds: Dataset, key) -> dict[str, dict[str, Decimal]]:
    totals: dict[str, dict[str, Decimal]] = defaultdict(lambda: defaultdict(Decimal))
    for t in ds.transactions:
        k = key(t)
        if k is not None:
            totals[t.date.strftime("%Y-%m")][k] += t.amount
    return totals


def write_xlsx(
    ds: Dataset, path: Path, ins: Insights | None = None, months: list[month_end.MonthEnd] | None = None
) -> None:
    ins = ins or interpret(ds)
    months = month_end.build(ds, ins) if months is None else months
    wb = Workbook()
    ws = wb.active
    ws.title = "İşlemler"
    _sheet_header(ws, _COLUMNS, [11, 9, 12, 30, 24, 22, 28, 13, 28, 50, 14, 8, 18, 12, 40, 24])
    for row in _rows(ds):
        ws.append(row)
    for cell in ws["A"][1:]:
        cell.number_format = "DD.MM.YYYY"
    for cell in ws["K"][1:]:
        cell.number_format = _MONEY
    ws.auto_filter.ref = ws.dimensions

    expense = lambda t: t.kind in DEFAULT_EXPENSE_KINDS
    by_group = _monthly(ds, lambda t: t.group if expense(t) else None)
    groups = [g for g in ds.groups if any(m.get(g) for m in by_group.values())]
    ws = wb.create_sheet("Aylık Özet")
    _sheet_header(ws, ["Ay", *groups, "Toplam"], [10] + [16] * len(groups) + [16])
    for month in sorted(by_group):
        values = [_r(by_group[month].get(g, ZERO)) for g in groups]
        ws.append([month, *values, _r(sum(values, ZERO))])
    _money(ws)

    by_level = _monthly(ds, lambda t: (t.necessity or Necessity.UNKNOWN) if expense(t) else None)
    ws = wb.create_sheet("Gereklilik")
    _sheet_header(ws, ["Ay", *(NECESSITY[n] for n in LEVELS), "Toplam"], [10] + [16] * (len(LEVELS) + 1))
    for month in sorted(by_level):
        values = [_r(by_level[month].get(n, ZERO)) for n in LEVELS]
        ws.append([month, *values, _r(sum(values, ZERO))])
    _money(ws)

    flows = _monthly(ds, lambda t: t.kind)
    # What each month set aside, as the month-end page counts it (insights.saving_of): BES and investments, currency,
    # gold and deposits; below zero what was taken out of the savings.
    saved: dict[str, Decimal] = defaultdict(Decimal)
    for t in ds.transactions:
        found = saving_of(t, ds.accounts)
        if found is not None:
            saved[month_of(t.date)] += found[1]
    ws = wb.create_sheet("Gelir-Gider")
    _sheet_header(
        ws,
        ["Ay", "Gelir", "Gider", "Net (gelir − gider)", "Kişilere gönderilen", "Borç ödemeleri", "Birikim"],
        [10, 16, 16, 18, 18, 16, 16],
    )
    for month in sorted(flows):
        f = flows[month]
        income = -f.get(TransactionKind.INCOME, ZERO)
        spent = sum((f.get(k, ZERO) for k in DEFAULT_EXPENSE_KINDS), ZERO)
        ws.append(
            [
                month,
                _r(income),
                _r(spent),
                _r(income - spent),
                _r(f.get(TransactionKind.P2P_TRANSFER, ZERO)),
                _r(f.get(TransactionKind.LOAN_PRINCIPAL, ZERO)),
                _r(saved.get(month, ZERO)),
            ]
        )
    _money(ws)

    ws = wb.create_sheet("Ekstreler")
    _sheet_header(
        ws,
        [
            "Hesap",
            "Başlangıç",
            "Kesim / bitiş",
            "Para birimi",
            "İşlem sayısı",
            "Önceki bakiye",
            "Belgedeki toplam",
            "Hesaplanan",
            "Kontrol",
            "Dosya",
        ],
        [32, 12, 12, 10, 12, 16, 16, 16, 18, 60],
    )
    for s in ds.statements:
        check = (
            f"Bakiye {s.checks_ok}/{s.checks_total}"
            if s.is_account
            else "Tutarlı"
            if s.verified
            else f"Fark {s.difference}"
        )
        ws.append(
            [
                ds.accounts[s.account].label,
                s.start,
                s.cut_date,
                currency_label(s.currency),
                len(s.transactions),
                s.previous,
                s.total,
                None if s.is_account else s.computed_total,
                check,
                s.source,
            ]
        )
    for col in "BC":
        for cell in ws[col][1:]:
            cell.number_format = "DD.MM.YYYY"
    for col in "FGH":
        for cell in ws[col][1:]:
            cell.number_format = "#,##0.00"
    _insight_sheets(wb, ds, ins)
    _month_end_sheets(wb, months)
    _as_text(wb)  # the workbook writes no formula of its own
    wb.save(path)


def _month_end_sheets(wb: Workbook, months: list[month_end.MonthEnd]) -> None:
    """The month-end closing: one row per month, then one per account and month."""
    ws = wb.create_sheet("Ay Sonu", 3)
    _sheet_header(
        ws,
        [
            "Ay",
            "Durum",
            "Gider",
            "Gelir",
            "Kişilere gönderilen",
            "Borç ödemesi",
            "Birikim",
            "Ay sonunda kalan",
            "Geçici kayıt",
            "Ekstrede görünmeyen dekont",
            "Kapanış",
        ],
        [10, 18, 14, 14, 18, 14, 16, 16, 12, 14, 110],
    )
    for me in reversed(months):
        t = me.totals
        ws.append(
            [
                me.month,
                me.label,
                _r(t.expense),
                None if t.income is None else _r(t.income),
                _r(t.people),
                _r(t.debt),
                _r(t.saving),
                None if t.left is None else _r(t.left),
                len(me.provisional),
                len(me.unmatched),
                me.summary,
            ]
        )
    for row in ws.iter_rows(min_row=2):
        for cell in row[2:8]:
            cell.number_format = _MONEY
        row[10].alignment = Alignment(wrap_text=True, vertical="top")
    ws.auto_filter.ref = ws.dimensions

    ws = wb.create_sheet("Kapanış", 4)
    _sheet_header(
        ws,
        [
            "Ay",
            "Hesap",
            "Durum",
            "Kapsanan gün",
            "Belgeler",
            "Dekontlar",
            "Ay sonu bakiyesi",
            "Para birimi",
            "Açıklama",
        ],
        [10, 36, 14, 13, 40, 30, 16, 10, 90],
    )
    labels = ((CONFIRMED, "eşleşti"), (PROVISIONAL, "geçici"), (NOT_ON_STATEMENT, "ekstrede yok"))
    for me in reversed(months):
        for a in me.accounts:
            docs = ", ".join(
                f"{month_end.period_text(lo, hi)} {month_end.statement_check(s)[2]}" for s, lo, hi in a.statements
            )
            receipts = ", ".join(f"{n} {label}" for status, label in labels if (n := a.count(status)))
            ws.append(
                [
                    me.month,
                    a.account.label,
                    month_end.ACCOUNT_STATUS[a.status],
                    f"{a.covered}/{a.needed}",
                    docs,
                    receipts,
                    a.balance,
                    currency_label(a.account.currency),
                    a.note,
                ]
            )
    for cell in ws["G"][1:]:
        cell.number_format = "#,##0.00"
    ws.auto_filter.ref = ws.dimensions


def _insight_sheets(wb: Workbook, ds: Dataset, ins: Insights) -> None:
    window = ins.timeline.window
    ws = wb.create_sheet("Değerlendirme", 0)
    _sheet_header(ws, ["Bölüm", "Başlık", "Açıklama", "Aylık etki (TL)"], [16, 34, 120, 16])
    for f in ins.findings:
        ws.append([{"dikkat": "Dikkat", "iyi": "İyi", "bilgi": "Bilgi"}[f.tone], f.title, f.text, None])
    for i, st in enumerate(ins.steps, 1):
        ws.append([f"Adım {i}", st.title, st.text, _r(st.monthly) if st.monthly else None])
    ws.append([])
    ws.append(["Bütçe", "Kalem", "Not", "Bugün (TL)", "Öneri (TL)"])
    for b in ins.budget:
        ws.append(["Bütçe", b.label, b.note, _r(b.now), _r(b.plan)])
    for row in ws.iter_rows(min_row=2):
        row[2].alignment = Alignment(wrap_text=True, vertical="top")
        for cell in row[3:5]:
            cell.number_format = _MONEY
    ws.column_dimensions["E"].width = 16

    ws = wb.create_sheet("Düzenli Ödemeler", 1)
    _sheet_header(
        ws,
        [
            "İşyeri / kişi",
            "Kategori",
            "Gereklilik",
            "Durum",
            "Aylık tutar",
            "Son ödeme",
            "Son tutar",
            "Sonraki (beklenen)",
            "Ödeme sayısı",
            "Hesap",
        ],
        [30, 26, 13, 24, 14, 12, 14, 16, 12, 30],
    )
    for sr in ins.series:
        if sr.status == "bitti" and month_of(sr.last.date) < window[0]:
            continue
        ws.append(
            [
                sr.merchant,
                sr.last.category,
                NECESSITY[sr.last.necessity] if sr.last.necessity else "",
                STATUS[sr.status],
                _r(sr.monthly),
                sr.last.date,
                _r(abs(sr.last.amount)),
                sr.expected,
                len(sr.payments),
                ", ".join(dict.fromkeys(ds.accounts[t.account].label for t in sr.payments)),
            ]
        )
    for col, fmt in (("E", _MONEY), ("G", _MONEY), ("F", "DD.MM.YYYY"), ("H", "DD.MM.YYYY")):
        for cell in ws[col][1:]:
            cell.number_format = fmt
    ws.auto_filter.ref = ws.dimensions

    ws = wb.create_sheet("Alışkanlıklar", 2)
    _sheet_header(
        ws,
        [
            "Kalem",
            "Kategori",
            "Gereklilik",
            "Durum",
            "Ne sıklıkla",
            "Son 3 ayda aylık",
            f"{len(window)} ayda toplam",
            "Beklenen aylık",
        ],
        [30, 26, 13, 16, 40, 16, 16, 16],
    )
    for h in ins.habits:
        ws.append(
            [
                h.name,
                h.category,
                NECESSITY[h.necessity] if h.necessity else "",
                HABIT_STATUS[h.status],
                h.pattern,
                _r(h.recent),
                _r(h.total),
                _r(h.monthly),
            ]
        )
    for col in "FGH":
        for cell in ws[col][1:]:
            cell.number_format = _MONEY
    ws.auto_filter.ref = ws.dimensions
