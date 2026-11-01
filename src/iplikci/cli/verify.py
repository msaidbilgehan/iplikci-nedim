"""`iplikci dogrula`: the verification baseline, the archive's integrity and the rebuild check."""

import argparse
import sys
from datetime import date

from .. import baseline
from ..app import checks, rebuild
from ..app.analysis import analyze
from ..app.workspace import Busy, Workspace
from .common import clear_progress, day_arg, open_workspace, show_progress


def verify_command(argv: list[str]) -> int:
    parser = argparse.ArgumentParser(
        prog="iplikci dogrula",
        description="Belgeleri ve arşivi denetler. --taban doğrulama tabanını alır ve kayıtlı tabanla karşılaştırır: "
        "daha az doğrulanan ekstre, yeni bir okunamayan belge ya da yeni belge gelmeden yeniden açılan bir ay "
        "gerilemedir; komut 1 ile biter ve taban kaydedilmez. Taban veri klasöründe (baseline.json) durur. --arsiv "
        "arşivdeki her belgenin bozulmadığını ve veritabanının arşivle tutarlı olduğunu denetler. --yeniden-kur "
        "veritabanını arşivden ve birincil verilerden yanında yeniden kurar ve sonucun aynı çıktığını denetler.",
    )
    which = parser.add_mutually_exclusive_group(required=True)
    which.add_argument("--taban", action="store_true", help="doğrulama tabanını al ve öncekiyle karşılaştır")
    which.add_argument("--arsiv", action="store_true", help="arşiv bütünlüğünü ve veritabanı tutarlılığını denetle")
    which.add_argument(
        "--yeniden-kur", action="store_true", help="veritabanını arşivden yeniden kur ve sonucu karşılaştır"
    )
    parser.add_argument("--tarih", type=day_arg, help="ayların kapanışına bakılan gün, YYYY-AA-GG (varsayılan: bugün)")
    parser.add_argument("--kabul", action="store_true", help="--taban: gerileme olsa da yeni tabanı kaydet")
    parser.add_argument("--yeniden-oku", action="store_true", help="--taban: bütün belgeleri yeniden oku")
    args = parser.parse_args(argv)
    day = args.tarih or date.today()
    ws = open_workspace(parser)
    try:
        if args.arsiv:
            return _verify_archive(ws)
        if args.yeniden_kur:
            return _verify_rebuild(ws, day)
        return _verify_baseline(ws, day, args, parser)
    except Busy as exc:
        print(str(exc), file=sys.stderr)
        return 1


def _verify_baseline(ws: Workspace, day: date, args: argparse.Namespace, parser: argparse.ArgumentParser) -> int:
    path = ws.layout.baseline
    try:
        previous = baseline.load(path)
    except ValueError as exc:
        parser.error(f"kayıtlı taban okunamadı ({path}): {exc}")
    a = analyze(ws, show_progress, today=day, reread=args.yeniden_oku)
    clear_progress()
    current = baseline.take(a.dataset, a.stats, a.months, day)
    print("\n".join(baseline.describe(current)))
    changes = baseline.compare(previous, current) if previous else []
    if previous is None:
        print("\nKayıtlı taban yok: bu taban sonraki karşılaştırmalar için kaydediliyor.")
    else:
        print(
            f"\nKayıtlı tabana göre ({date.fromisoformat(previous['day']):%d.%m.%Y}):"
            if changes
            else "\nKayıtlı tabanla aynı."
        )
    for c in changes:
        print(f"  {'!' if c.regression else '·'} {c.label}: {_shown(c.before)} → {_shown(c.after)}")
    regressions = sum(c.regression for c in changes)
    if regressions and not args.kabul:
        print(
            f"\n{regressions} gerileme var (!): önce bunlar düzeltilir. Taban kaydedilmedi; değişiklik bilinçliyse "
            "--kabul ile kaydedin.",
            file=sys.stderr,
        )
        return 1
    baseline.save(path, current)
    print(f"\nTaban: {path}")
    return 0


def _verify_archive(ws: Workspace) -> int:
    print("Arşivdeki belgeler yeniden özetleniyor…", file=sys.stderr)
    r = checks.archive(ws)
    i = r.integrity
    print(f"Arşiv: {i.checked} nesne denetlendi · veritabanında {r.documents} belge")
    problems = [f"bozulmuş nesne: {sha}" for sha in i.corrupt]
    problems += [f"yanlış yerde duran nesne: {path}" for path in i.misplaced]
    problems += [f"nesne olmayan dosya: {path}" for path in i.strays]
    problems += [f"arşivde olmayan belge: {sha}" for sha in r.missing]
    problems += [f"veritabanı: {text}" for text in r.database]
    notes = [f"yeniden yazılabilir yapılmış nesne: {sha}" for sha in i.writable]
    notes += [f"veritabanında adı olmayan nesne: {sha}" for sha in r.unknown]
    notes += [f"kaldırıldığı hâlde arşivde duran nesne: {sha}" for sha in r.lingering]
    if r.stale:
        notes.append(f"{r.stale} belge yeni okuyucularla yeniden okunmayı bekliyor (bir sonraki raporda okunur)")
    for line in problems:
        print(f"  ! {line}")
    for line in notes:
        print(f"  · {line}")
    if not r.ok:
        print(f"\n{len(problems)} sorun var (!): arşivdeki dosyalara dokunmayın; önce yedekten bakın.", file=sys.stderr)
        return 1
    print("\nArşiv sağlam; veritabanı arşivle tutarlı.")
    return 0


def _verify_rebuild(ws: Workspace, day: date) -> int:
    print("Veritabanı arşivden yanında yeniden kuruluyor…", file=sys.stderr)
    r = rebuild.check(ws, today=day, progress=show_progress)
    clear_progress()
    print(f"Birincil veriler: {r.documents} belge, {r.annotations} düzeltme")
    if r.ok:
        print("Yeniden kurulan veritabanı aynı sonucu veriyor.")
        return 0
    for line in r.differences:
        print(f"  ! {line}")
    print(f"\n{len(r.differences)} fark var (!): veritabanı arşivden aynı kurulamıyor.", file=sys.stderr)
    return 1


def _shown(value: object) -> str:
    return "—" if value is None else str(value)
