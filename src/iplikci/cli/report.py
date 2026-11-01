"""The report and the month-end pages (exports/), with a summary on the terminal."""

import argparse
import re
import sys
import webbrowser
from collections import Counter
from datetime import date, timedelta

from .. import month_end
from ..analysis import Dataset
from ..app.analysis import analyze
from ..app.workspace import Busy
from ..domain.codes import DEFAULT_EXPENSE_KINDS
from ..insights import Insights, receipt_amount, tl
from .common import clear_progress, open_workspace, show_progress


def report(argv: list[str]) -> int:
    parser = argparse.ArgumentParser(
        prog="iplikci",
        description="Arşivdeki banka belgelerinden gider, gelir, gereklilik ve tahmin raporunu üretir (exports/). "
        "Belge eklemek için: iplikci ekle",
    )
    parser.add_argument("--ac", action="store_true", help="raporu tarayıcıda aç")
    parser.add_argument("--yeniden-oku", action="store_true", help="bütün belgeleri yeniden oku")
    args = parser.parse_args(argv)
    ws = open_workspace(parser)
    print("Belgeler okunuyor…", file=sys.stderr)
    try:
        a = analyze(ws, show_progress, write=True, reread=args.yeniden_oku)
    except Busy as exc:
        print(str(exc), file=sys.stderr)
        return 1
    clear_progress()
    _summary(a.dataset, a.stats)
    _interpretation(a.insights)
    _closing(a.months[-3:])
    outputs = a.outputs
    assert outputs is not None
    print(
        f"\nRapor : {outputs.html}\nCSV   : {outputs.csv}\nExcel : {outputs.xlsx}\n"
        f"Ay sonu: {outputs.month_end / month_end.INDEX}"
    )
    if args.ac:
        webbrowser.open(outputs.html.resolve().as_uri())
    return 0


def _closing(months: list[month_end.MonthEnd]) -> None:
    if not months:
        return
    print("\nAy sonu kapanışı:")
    for me in reversed(months):
        print(f"  {me.name:14} {me.label:17} {me.summary}")


def month_end_command(argv: list[str]) -> int:
    parser = argparse.ArgumentParser(
        prog="iplikci aysonu",
        description="Ay sonu raporlarını üretir (exports/ay-sonu/) ve her ayın ekstrelerle kapanıp kapanmadığını "
        "yazar: hangi hesabın hangi ekstresi ya da dökümü bekleniyor, dekontlar eşleşti mi. Ay verilirse "
        "o ayın ayrıntısını gösterir.",
    )
    parser.add_argument("ay", nargs="?", help="YYYY-AA (varsayılan: son aylar)")
    parser.add_argument("--ac", action="store_true", help="raporu tarayıcıda aç")
    args = parser.parse_args(argv)
    if args.ay and not re.fullmatch(r"\d{4}-(0[1-9]|1[0-2])", args.ay):
        parser.error(f"ay YYYY-AA biçiminde olmalı: {args.ay!r}")
    if args.ay and args.ay > f"{date.today():%Y-%m}":
        parser.error(f"{args.ay} henüz gelmedi: ay sonu raporu ancak başlamış bir ay için çıkar")
    ws = open_workspace(parser)
    try:
        a = analyze(ws, show_progress, write=True)
    except Busy as exc:
        print(str(exc), file=sys.stderr)
        return 1
    clear_progress()
    assert a.outputs is not None
    folder = a.outputs.month_end
    if not args.ay:
        _closing(a.months)
        page = folder / month_end.INDEX
    else:
        me = next((m for m in a.months if m.month == args.ay), None)
        if me is None:  # older than the pages kept: written on request
            [me] = month_end.build(a.dataset, a.insights, months=[args.ay])
            month_end.write_page(me, a.dataset, folder, [args.ay])
        _month_detail(me, a.dataset)
        page = folder / me.file
    print(f"\nRapor: {page}")
    if args.ac:
        webbrowser.open(page.resolve().as_uri())
    return 0


def _month_detail(me: month_end.MonthEnd, ds: Dataset) -> None:
    t = me.totals
    print(f"{me.name} — {me.label}\n{me.summary}\n")
    print(
        f"Gider {tl(t.expense)} · gelir {tl(t.income) if t.income is not None else 'bilinmiyor'} · kişilere "
        f"{tl(t.people)} · borç {tl(t.debt)} · birikim {tl(t.saving)}"
        + (f" · kalan {tl(t.left)}" if t.left is not None else "")
    )
    print("\nHesaplar:")
    for a in me.accounts:
        print(f"  {month_end.ACCOUNT_STATUS[a.status]:13} {a.account.label}: {a.note}")
    if me.provisional:
        print(f"\nGeçici kayıtlar ({len(me.provisional)}): ekstre ya da döküm gelince kesinleşecek")
        for x in me.provisional:
            print(f"  {x.date:%d.%m.%Y} {x.merchant or x.description} {tl(x.amount)}")
    if me.unmatched:
        print(f"\nEkstrede görünmeyen dekontlar ({len(me.unmatched)}):")
        for line in me.unmatched:
            print(
                f"  {line.txn.date:%d.%m.%Y} {ds.accounts[line.txn.account].label}: {line.txn.description} "
                f"{receipt_amount(ds, line)}"
            )


def _summary(ds, stats) -> None:
    status = Counter(d.status for d in ds.documents)
    cards = [s for s in ds.statements if not s.is_account]
    accounts = [s for s in ds.statements if s.is_account]
    print(
        f"{stats['documents']} benzersiz belge ({stats['duplicates']} kopya atlandı): "
        f"{len(cards)} kart ekstresi, {len(accounts)} hesap dökümü, {status['dekont']} dekont, "
        f"{status['bildirim']} banka bildirimi, {status['is']} şirket belgesi, {status['atlandi']} atlandı, "
        f"{status['hata']} hata"
    )
    print(f"Kart ekstreleri: {sum(s.verified for s in cards)}/{len(cards)} bankanın toplamıyla tutarlı")
    print(f"Hesap dökümleri: {sum(s.verified for s in accounts)}/{len(accounts)} satır satır bakiyeyle tutarlı")
    for s in ds.statements:
        if not s.verified:
            detail = f"bakiye {s.checks_ok}/{s.checks_total}" if s.is_account else f"fark {s.difference}"
            print(f"  ! {ds.accounts[s.account].label} {s.cut_date}: {detail} ({s.source})")
    for d in ds.documents:
        if d.status == "hata":
            print(f"  ! okunamadı: {d.name}: {d.detail}")
    for w in ds.warnings:
        print(f"  ! {w}")
    if not ds.transactions:
        return
    print(f"{len(ds.transactions)} işlem, {ds.transactions[0].date:%m.%Y} – {ds.transactions[-1].date:%m.%Y}")
    # Last 12 months (this one included) of expenses, as a quick sanity check in the terminal.
    today = date.today()
    start = date(today.year - 1, today.month, 1) + timedelta(days=31)
    start = start.replace(day=1)
    spent = sum(t.amount for t in ds.transactions if t.kind in DEFAULT_EXPENSE_KINDS and t.date >= start)
    print(f"Son 12 ay gider: {spent:,.0f} TL".replace(",", "."))


def _interpretation(ins: Insights) -> None:
    if not ins.findings:
        return
    window = ins.timeline.window
    print(f"\nDeğerlendirme ({len(window)} tam ay, {window[0]} – {window[-1]}):")
    marks = {"dikkat": "!", "iyi": "+", "bilgi": "·"}
    for f in ins.findings:
        print(f"  {marks[f.tone]} {f.title}")
    print("Önerilen adımlar:")
    for i, st in enumerate(ins.steps, 1):
        print(f"  {i}. {st.title}" + (f" (ayda ~{tl(st.monthly)})" if st.monthly >= 1 else ""))
