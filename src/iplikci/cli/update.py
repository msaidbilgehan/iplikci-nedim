"""`iplikci guncelleme`: the program's own updates (ADR-0022, F21): where they stand, a check now, an install now and
whether the program installs a new version by itself. The service's worker checks and installs: while it runs, the
commands ask it to; without it, `denetle` checks here and `kur` waits for its next start."""

import argparse
import sys

from ..app import update
from ..app.update import UpdateError
from ..app.workspace import Workspace
from ..domain.codes import Actor
from ..service import client, instance
from .common import local_time, open_workspace

MODES = {"otomatik": "auto", "sor": "ask", "kapali": "off"}
MODE_WORDS = {
    "auto": "yeni sürüm kendiliğinden kurulur",
    "ask": "yeni sürüm haber verilir, kurulumu siz başlatırsınız",
    "off": "yeni sürüm denetlenmez",
}
INSTALLATION_WORDS = {
    "macos_app": "macOS uygulaması",
    "linux_copy": "Linux (AppImage)",
    "windows_setup": "Windows kurulum programı",
    "manual": "elle kurulmuş kopya: kendini güncellemez",
}


def update_command(argv: list[str]) -> int:
    parser = argparse.ArgumentParser(
        prog="iplikci guncelleme",
        description="İplikçi Nedim'in güncellemeleri: yeni sürüm günde bir, 05.00'ten sonra GitHub'dan denetlenir; "
        "imzası ve dosyası doğrulanır, önce yedek alınır, sonra kurulur. Elle kurulmuş kopya yalnızca haber verir.",
    )
    commands = parser.add_subparsers(dest="komut", required=True, metavar="KOMUT")
    commands.add_parser("durum", help="sürümü ve güncellemelerin durumunu göster")
    commands.add_parser(
        "denetle",
        help="yeni sürümü şimdi denetle",
        description="Servis çalışıyorsa servisten ister, yoksa burada denetler.",
    )
    commands.add_parser(
        "kur",
        help="bulunan yeni sürümü şimdi kur",
        description="Son denetimin bulduğu yeni sürümü servise kurdurur; servis önce yedek alır, sonra yeni sürümle "
        "yeniden başlar.",
    )
    choose = commands.add_parser("mod", help="yeni sürüm kendiliğinden mi kurulsun, sorulsun mu, denetlenmesin mi")
    choose.add_argument("mod", choices=sorted(MODES))
    args = parser.parse_args(argv)
    ws = open_workspace(parser)
    running = instance.current(ws.run) is not None
    try:
        if args.komut == "mod":
            print("\n".join(status_lines(update.set_mode(ws, MODES[args.mod], Actor.USER))))
            return 0
        if args.komut == "denetle":
            if running:
                return _ask(ws, "/api/update/check", "Servis yeni sürümü denetliyor; sonucu: iplikci guncelleme durum")
            print("\n".join(status_lines(update.check(ws, forced=True))))
            return 0
        if args.komut == "kur":
            if not running:
                update.request_install(ws, Actor.USER)
                print("Kurulum servisin bir sonraki açılışında yapılır.")
                return 0
            return _ask(ws, "/api/update/install", "Servis yeni sürümü kuruyor; bitince yeni sürümle yeniden başlar.")
    except UpdateError as exc:
        print(str(exc), file=sys.stderr)
        return 1
    print("\n".join(status_lines(update.state(ws))))
    return 0


def _ask(ws: Workspace, path: str, said: str) -> int:
    try:
        client.call(ws, "POST", path)
    except client.ServiceError as exc:
        print(f"Servise iletilemedi: {exc}", file=sys.stderr)
        return 1
    print(said)
    return 0


def status_lines(found: update.UpdateState) -> list[str]:
    """update.state in lines, for the terminal."""
    lines = [
        f"Sürüm: {found.version} · {INSTALLATION_WORDS.get(found.installation, found.installation)}",
        f"Ayar: {MODE_WORDS.get(found.mode, found.mode)}",
    ]
    if found.checked_at:
        lines.append(f"Son denetim: {local_time(found.checked_at)}")
    else:
        lines.append("Son denetim: henüz yok")
    if found.check_error:
        lines.append(f"Son denetimin sorunu: {found.check_error}")
    if found.installing:
        lines.append(f"Kuruluyor: {found.installing}")
    if found.available is not None:
        lines.append(f"Yeni sürüm: {found.available.version} ({found.available.date}) · {found.available.page}")
    elif found.checked_at and not found.check_error:
        lines.append("Güncel: daha yeni bir sürüm yok")
    if found.last is not None:
        how = "kuruldu" if found.last.ok else f"kurulamadı: {found.last.error}"
        lines.append(
            f"Son güncelleme: {found.last.from_version} → {found.last.to_version}, {local_time(found.last.at)}, {how}"
        )
    return lines
