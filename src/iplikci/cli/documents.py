"""`iplikci ekle` and the MVP's panel: documents into the archive through a plan the user sees first."""

import argparse
import sys
from collections import Counter

from ..app import intake
from ..app.workspace import Busy, StalePlan
from ..settings.config import DEFAULT_PORT
from .common import clear_progress, open_workspace, show_progress


def add_command(argv: list[str]) -> int:
    parser = argparse.ArgumentParser(
        prog="iplikci ekle",
        description="Banka belgelerini arşive alır. Yol verilirse oradaki dosyalar okunur ve hiç taşınmaz; yol "
        "verilmezse gelen klasöründekiler alınır ve arşive geçince oradan kalkar. Şirket belgeleri alınmaz. "
        "--uygula verilmezse hiçbir şeye dokunmaz, yalnızca planı gösterir.",
    )
    parser.add_argument("yol", nargs="*", help="dosya, klasör, zip ya da mbox (varsayılan: gelen klasörü)")
    parser.add_argument("--uygula", action="store_true", help="planı uygula")
    args = parser.parse_args(argv)
    ws = open_workspace(parser)
    print("Belgeler okunuyor…", file=sys.stderr)
    try:
        plan = intake.plan_paths(ws, args.yol) if args.yol else intake.plan_inbox(ws)
    except (FileNotFoundError, ValueError) as exc:
        parser.error(str(exc))
    _print_plan(plan)
    if not args.uygula:
        if plan.changes:
            print("\nHiçbir dosyaya dokunulmadı. Uygulamak için aynı komutu --uygula ile çalıştırın.")
        return 0
    try:
        done = intake.apply(ws, plan)
    except (Busy, StalePlan) as exc:
        print(str(exc), file=sys.stderr)
        return 1
    labels = intake.ACTION_LABELS
    print("\nUygulandı: " + ", ".join(f"{labels.get(k, k)}: {v}" for k, v in sorted(done.counts.items())))
    if done.trash:
        print(f"Çöp kutusuna taşınanlar (geri alınabilir): {done.trash}")
    return 0


def panel_command(argv: list[str]) -> int:
    from .. import panel

    parser = argparse.ArgumentParser(
        prog="iplikci panel",
        description="Raporu ve yeni belge ekleme yerini (tek dosya, çok dosya ya da klasör) yerel bir web panelinde "
        "açar. Yalnızca bu bilgisayardan erişilir (127.0.0.1); internete hiçbir şey gönderilmez.",
    )
    parser.add_argument("--port", type=int, help=f"port (varsayılan: settings.toml [server] port ya da {DEFAULT_PORT})")
    parser.add_argument("--ac", action="store_true", help="paneli tarayıcıda aç")
    args = parser.parse_args(argv)
    return panel.serve(open_workspace(parser), args.port, args.ac, show_progress, clear_progress)


def _print_plan(plan: intake.Plan) -> None:
    changes = plan.changes
    if not changes:
        print("Alınacak belge yok.")
        return
    by_action = Counter(intake.ACTION_LABELS.get(c.action, c.action) for c in changes)
    print("Plan: " + ", ".join(f"{label}: {n}" for label, n in sorted(by_action.items())))
    for c in changes:
        target = c.outcome.reading(c.name).display_name if c.outcome and c.outcome.result else ""
        line = f"  {intake.ACTION_LABELS.get(c.action, c.action):<45} {c.name}"
        if target and target != c.name:
            line += f" → {target}"
        if c.copy_of:
            line += f" (eşi: {c.copy_of})"
        if c.reason:
            line += f" ({c.reason})"
        print(line)
