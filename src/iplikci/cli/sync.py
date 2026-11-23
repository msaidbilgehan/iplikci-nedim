"""`iplikci esitleme`: the sync folder (ADR-0025, F22): where it stands, the places it can go, turning it on in a
folder and off, a round now, and sending the notifications that leave the computer from this one. The service runs the
rounds every minute; without it, `simdi` runs one here."""

import argparse
import sys

from ..app import notify, sync
from ..app.sync import SyncError
from ..app.workspace import Workspace
from ..domain.codes import Actor
from ..service import client, instance
from .common import local_time, open_workspace

CHANNEL_WORDS = {"telegram": "Telegram", "email": "e-posta"}


def sync_command(argv: list[str]) -> int:
    parser = argparse.ArgumentParser(
        prog="iplikci esitleme",
        description="Eşitleme ve yedek: belgeleriniz ve kararlarınız Google Drive'ın (ya da başka bir eşitleme "
        "uygulamasının) klasörü üzerinden öteki bilgisayarlarınıza gider; klasör, verilerin bilgisayar dışındaki "
        "kopyasıdır. Veritabanı klasöre konmaz.",
    )
    commands = parser.add_subparsers(dest="komut", required=True, metavar="KOMUT")
    commands.add_parser("durum", help="eşitlemenin durumunu ve bilgisayarları göster")
    commands.add_parser("yerler", help="bu bilgisayardaki eşitleme klasörlerini (Google Drive, iCloud Drive…) göster")
    turn_on = commands.add_parser(
        "ac",
        help="eşitlemeyi bir klasörde aç",
        description="Klasörde bir veri kümesi yoksa başlatır, varsa ona katılır: katılan bilgisayarın eski verisinden "
        "öteki bilgisayarlarda olmayanlar kalır, ikisinde de olanlarda klasördeki geçerli olur.",
    )
    turn_on.add_argument("klasor", metavar="KLASÖR", help="eşitleme klasörünün tam yolu")
    turn_on.add_argument("--ad", default="", help="bu bilgisayarın öteki bilgisayarlarda görünen adı")
    commands.add_parser("kapat", help="eşitlemeyi kapat (klasör ve veriler olduğu gibi kalır)")
    commands.add_parser("simdi", help="şimdi bir eşitleme turu yap")
    here = commands.add_parser("buradan", help="Telegram ve e-posta bildirimlerini bu bilgisayar göndersin")
    here.add_argument(
        "kanal", nargs="*", choices=["telegram", "eposta"], help="kanallar (boş: gönderebildiklerinin hepsi)"
    )
    args = parser.parse_args(argv)
    ws = open_workspace(parser)
    try:
        if args.komut == "yerler":
            for p in sync.places(ws):
                what = "veri kümesi var, katılınır" if p.exists else ("kullanılabilir" if p.usable else p.problem)
                print(f"{p.service}{f' ({p.account})' if p.account else ''}: {p.folder} — {what}")
            return 0
        if args.komut == "ac":
            print(
                "\n".join(status_lines(sync.turn_on(ws, args.klasor, args.ad, Actor.USER, notify.external_ready(ws))))
            )
            _wake(ws)
            return 0
        if args.komut == "kapat":
            print("\n".join(status_lines(sync.turn_off(ws, Actor.USER))))
            return 0
        if args.komut == "simdi":
            if instance.current(ws.run) is not None:
                return _wake(ws, "Servis eşitleme turunu başlattı; sonucu: iplikci esitleme durum")
            done = sync.run_round(ws, lambda: notify.external_ready(ws))
            print(f"Tur bitti: {done.fetched} belge geldi, {done.published} belge klasöre kondu.")
            if done.problem:
                print(f"Sorun: {done.problem}", file=sys.stderr)
                return 1
            return 0
        if args.komut == "buradan":
            ready = notify.external_ready(ws)
            wanted = ["email" if k == "eposta" else k for k in args.kanal] or list(ready)
            print("\n".join(status_lines(sync.claim(ws, [c for c in wanted if c in ready], Actor.USER))))
            return 0
    except SyncError as exc:
        print(str(exc), file=sys.stderr)
        return 1
    print("\n".join(status_lines(sync.status(ws))))
    return 0


def _wake(ws: Workspace, said: str = "") -> int:
    if instance.current(ws.run) is None:
        return 0
    try:
        client.call(ws, "POST", "/api/sync/round")
    except client.ServiceError as exc:
        print(f"Servise iletilemedi: {exc}", file=sys.stderr)
        return 1
    if said:
        print(said)
    return 0


def status_lines(found: sync.Status) -> list[str]:
    """sync.status in lines, for the terminal."""
    if not found.on:
        return ["Eşitleme kapalı."]
    names = {d.id: d.name for d in found.devices}
    lines = [
        f"Eşitleme açık: {found.folder}" + (f" ({found.service})" if found.service else ""),
        f"Bu bilgisayar: {found.name}",
        (
            f"Belgeler: {found.documents}; gelmeyi bekleyen {found.waiting_down}, "
            f"klasöre gitmeyi bekleyen {found.waiting_up}"
        ),
    ]
    for d in found.devices:
        state = "eşitlemeyi kapattı" if d.left else f"son görülme {local_time(d.seen_at)}" if d.seen_at else ""
        lines.append(f"  · {d.name}{' (bu bilgisayar)' if d.me else ''} — {d.system} {d.app}, {state}")
    for channel, device in sorted(found.senders.items()):
        lines.append(f"{CHANNEL_WORDS.get(channel, channel)} bildirimlerini gönderen: {names.get(device, device)}")
    if found.last_at:
        lines.append(f"Son tur: {local_time(found.last_at)}")
    if found.problem:
        lines.append(f"Sorun: {found.problem} ({local_time(found.since)} beri)")
    return lines
