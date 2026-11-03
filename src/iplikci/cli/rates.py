"""`iplikci kurlar`: the exchange rates (F12, architecture §15): fetch them now, and see where they stand. While the
service runs, it fetches: `al` asks it to, as `eposta al` does, instead of fetching beside it."""

import argparse
import sys

from ..app import fx
from ..app.workspace import Busy, Workspace
from ..domain.labels import RATE_SOURCE
from ..service import instance
from .common import clear_progress, local_time, open_workspace


def rates_command(argv: list[str]) -> int:
    parser = argparse.ArgumentParser(
        prog="iplikci kurlar",
        description="Döviz kurları: TCMB'nin günlük bülteni; TCMB'ye ulaşılamazsa ECB'nin referans kurları. Geçmiş "
        "kurlar verinin kapsadığı günler için bir kez çekilir; sonra her gün, saat 16.30 geçince, o günün bülteni "
        "gelir. Kur sağlayıcılarına yalnızca tarih gider. Servis çalışırken kurları servis çeker.",
    )
    commands = parser.add_subparsers(dest="komut", required=True, metavar="KOMUT")
    fetch = commands.add_parser(
        "al",
        help="kurları şimdi çek",
        description="Bugünün bültenini ve son bültenden bu yana kaçan iş günlerini çeker; --gecmis ile verinin "
        "kapsadığı günlerden henüz istenmemiş olanların hepsini. Servis çalışıyorsa servisten ister.",
    )
    fetch.add_argument("--gecmis", action="store_true", help="geçmişin eksik günlerini de çek")
    commands.add_parser(
        "durum",
        help="kurların durumunu göster",
        description="Hangi sağlayıcıların sorulduğunu, son bülteni, saklanan ve eksik günleri, son çekimi ve hatasını "
        "yazar.",
    )
    args = parser.parse_args(argv)
    ws = open_workspace(parser)
    if args.komut == "durum":
        print("\n".join(status_lines(fx.status(ws))))
        return 0
    try:
        return _fetch(ws, args.gecmis)
    except Busy as exc:
        clear_progress()
        print(f"Kurlar çekilemedi: {exc}", file=sys.stderr)
        return 1


def _fetch(ws: Workspace, history: bool) -> int:
    if not fx.providers_of(ws):
        print("Ayarlarda kur sağlayıcısı yok: kurlar ağdan çekilmiyor, belgelerdeki kurlar kullanılıyor.")
        return 0
    if instance.current(ws.run) is not None:
        from ..service import client

        try:
            client.call(ws, "POST", "/api/fx/fetch", {"history": history})
        except client.ServiceError as exc:
            print(f"Servise iletilemedi: {exc}", file=sys.stderr)
            return 1
        print("Servis kurları çekiyor; sonucu: iplikci kurlar durum")
        return 0
    while True:
        done = fx.fetch(ws, history, progress=_progress)
        clear_progress()
        print(done.message)
        if done.error and not done.stored:
            return 1
        if not done.more:
            return 0


def status_lines(found: fx.RatesStatus) -> list[str]:
    """fx.status in lines: the summary, then each part on its own."""
    lines = [f"Kurlar: {found.summary}"]
    names = [RATE_SOURCE[s] for s in found.providers]
    if len(names) == 2:  # TCMB first, the reference rates when it cannot be reached
        lines.append(f"Sağlayıcılar: {names[0]}; ulaşılamazsa {names[1]}")
    elif names:
        lines.append(f"Sağlayıcı: {names[0]}")
    for kept in found.sources:
        lines.append(f"{RATE_SOURCE[kept.source]}: son kur {kept.newest:%d.%m.%Y} · {kept.days} gün")
    if found.start is not None:
        lines.append(f"Geçmişin ilk günü: {found.start:%d.%m.%Y} · eksik iş günü: {found.missing}")
    lines.append(f"Son çekim: {local_time(found.last_run)}" if found.last_run else "Son çekim: henüz yok")
    if found.last_error:
        lines.append(f"Son hata: {found.last_error}")
    return lines


def _progress(i: int, n: int) -> None:
    if sys.stderr.isatty():
        print(f"\r  kurlar çekiliyor {i}/{n}", end="", file=sys.stderr, flush=True)
