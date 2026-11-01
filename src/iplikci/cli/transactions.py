"""`iplikci islem`: find transactions and keep the user's corrections by their fingerprints."""

import argparse
import re
import sys
from decimal import Decimal

from ..app import annotate
from ..app.analysis import Analysis, analyze
from ..app.workspace import Busy, Workspace
from ..categorize import Categorizer
from ..domain.codes import Actor
from ..domain.labels import NECESSITY, format_amount
from ..domain.text import fold
from ..storage import annotations
from .common import clear_progress, open_workspace, show_progress


def transaction_command(argv: list[str]) -> int:
    parser = argparse.ArgumentParser(
        prog="iplikci islem",
        description="İşlemleri arar; bir işleme not, etiket, kategori ya da gereklilik düzeltmesi ekler. Düzeltme "
        "işlemin parmak iziyle saklanır: belgeler yeniden okunduğunda kaybolmaz.",
    )
    commands = parser.add_subparsers(dest="komut", required=True, metavar="KOMUT")
    find = commands.add_parser("ara", help="işlemleri parmak izleriyle listele", description="İşlemleri arar.")
    find.add_argument("metin", nargs="*", help="satıcıda, açıklamada, notta ya da etikette geçen sözcükler")
    find.add_argument("--ay", help="yalnızca bu ay, YYYY-AA")
    find.add_argument("--sinir", type=int, default=30, help="en çok kaç işlem (varsayılan 30, en yenileri)")
    fix = commands.add_parser(
        "duzelt",
        help="bir işleme not, etiket, kategori ya da gereklilik ekle",
        description="Bir işlemin notunu, etiketlerini, kategorisini ya da gerekliliğini değiştirir. Boş değer "
        "('') o alanı siler; kategori ve gereklilik yeniden kurallardan gelir.",
    )
    fix.add_argument("iz", metavar="PARMAK_İZİ", help="işlemin parmak izi ya da en az ilk 6 karakteri")
    fix.add_argument("--not", dest="note", help="not")
    fix.add_argument("--etiket", nargs="*", help="etiketler, öncekilerin yerine; değer verilmezse etiketler silinir")
    fix.add_argument("--kategori", help="yalnızca bu işlemin kategorisi")
    fix.add_argument("--gereklilik", help=f"yalnızca bu işlemin gerekliliği: {', '.join(NECESSITY.values())}")
    orphans = commands.add_parser(
        "yetimler",
        help="hiçbir işlemin taşımadığı düzeltmeler",
        description="Belgeler yeniden okunduktan sonra eşi bulunamayan düzeltmeleri gösterir.",
    )
    orphans.add_argument("--birak", metavar="PARMAK_İZİ", help="bu düzeltmeyi sil")
    args = parser.parse_args(argv)
    ws = open_workspace(parser)
    try:
        a = analyze(ws, show_progress)
    except Busy as exc:
        print(str(exc), file=sys.stderr)
        return 1
    clear_progress()
    if args.komut == "ara":
        return _find_transactions(a, args, parser)
    if args.komut == "duzelt":
        return _fix_transaction(ws, a, args, parser)
    return _orphans(ws, a, args, parser)


def _row_line(t, label: str) -> str:
    what = t.category + (f" · {NECESSITY[t.necessity]}" if t.necessity else "")
    line = f"{t.fingerprint[:10]}  {t.date:%d.%m.%Y}  {format_amount(t.amount):>12} TL  {t.merchant[:30]:30}  {what}"
    extra = [f"not: {t.note}"] if t.note else []
    extra += [f"#{tag}" for tag in t.tags]
    return line + (f"  [{label}]" if label else "") + (f"\n{' ' * 12}{'  '.join(extra)}" if extra else "")


def _find_transactions(a: Analysis, args: argparse.Namespace, parser: argparse.ArgumentParser) -> int:
    if args.ay and not re.fullmatch(r"\d{4}-\d{2}", args.ay):
        parser.error("--ay YYYY-AA biçiminde olmalı")
    words = [fold(w) for w in args.metin]
    found = [
        t
        for t in a.dataset.transactions
        if (not args.ay or f"{t.date:%Y-%m}" == args.ay)
        and all(w in fold(f"{t.merchant} {t.description} {t.counterparty} {t.note} {' '.join(t.tags)}") for w in words)
    ]
    if not found:
        print("Bu aramayla işlem yok.")
        return 0
    shown = found[-max(1, args.sinir) :]
    for t in reversed(shown):
        print(_row_line(t, a.dataset.accounts[t.account].label if t.account in a.dataset.accounts else ""))
    if len(found) > len(shown):
        print(f"… {len(found) - len(shown)} işlem daha var; aramayı daraltın ya da --sinir verin.")
    return 0


def _fix_transaction(ws: Workspace, a: Analysis, args: argparse.Namespace, parser: argparse.ArgumentParser) -> int:
    try:
        t = annotate.find(a.dataset, args.iz)
    except LookupError as exc:
        parser.error(str(exc))
    changes: dict = {}
    try:
        if args.note is not None:
            changes["note"] = args.note
        if args.etiket is not None:
            changes["tags"] = tuple(args.etiket)
        if args.kategori is not None:
            category = args.kategori.strip()
            changes["category"] = annotate.category(Categorizer.layered(ws.rules), category) if category else ""
        if args.gereklilik is not None:
            level = args.gereklilik.strip()
            changes["necessity"] = annotate.necessity(level) if level else None
    except ValueError as exc:
        parser.error(str(exc))
    if not changes:
        parser.error("neyin değişeceğini yazın: --not, --etiket, --kategori ya da --gereklilik")
    label = a.dataset.accounts[t.account].label if t.account in a.dataset.accounts else t.account
    with ws.db() as db:
        kept = annotations.change(db, t.fingerprint, annotate.subject(t, label), Actor.USER, **changes)
    print(_row_line(t, label).split("\n")[0])
    if kept is None:
        print("Bu işlemin düzeltmesi kalmadı: kategori ve gereklilik kurallardan gelir.")
        return 0
    parts = [f"not: {kept.note}"] if kept.note else []
    parts += [f"etiketler: {', '.join(kept.tags)}"] if kept.tags else []
    parts += [f"kategori: {kept.category}"] if kept.category else []
    parts += [f"gereklilik: {NECESSITY[kept.necessity]}"] if kept.necessity else []
    print("Kaydedildi — " + "; ".join(parts))
    return 0


def _orphans(ws: Workspace, a: Analysis, args: argparse.Namespace, parser: argparse.ArgumentParser) -> int:
    if args.birak:
        prefix = args.birak.strip().lower()
        hits = [o for o in a.orphans if o.fingerprint.startswith(prefix)] if len(prefix) >= 6 else []
        if len(hits) != 1:
            parser.error(f"{args.birak} ile başlayan tek bir yetim düzeltme yok")
        with ws.db() as db:
            annotations.remove(db, hits[0].fingerprint, Actor.USER)
        print(f"Silindi: {hits[0].fingerprint[:10]}")
        return 0
    if not a.orphans:
        print("Eşi bulunamayan düzeltme yok.")
        return 0
    for o in a.orphans:
        s = o.subject
        amount = format_amount(Decimal(s.amount).scaleb(-2))  # the subject keeps kuruş
        print(f"{o.fingerprint[:10]}  {s.date}  {amount:>12} TL  {s.label}  {s.description}")
        parts = [f"not: {o.note}"] if o.note else []
        parts += [f"#{tag}" for tag in o.tags]
        parts += [f"kategori: {o.category}"] if o.category else []
        parts += [f"gereklilik: {NECESSITY[o.necessity]}"] if o.necessity else []
        print(" " * 12 + "  ".join(parts))
    print(
        "\nBu işlemler belgeler yeniden okunduğunda değişti ya da kalktı. Doğru işlemi bulup (iplikci islem ara) "
        "düzeltmeyi yeniden ekleyin; sonra bu kaydı --birak ile silin."
    )
    return 0
