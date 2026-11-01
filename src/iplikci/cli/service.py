"""`iplikci servis` and `iplikci ac`: the service in the foreground or in the system's service manager, its status
as the running service reports it (/api/system), and a login link from it."""

import argparse
import sys
import webbrowser
from pathlib import Path
from typing import Any

from ..app.workspace import Workspace
from ..domain.codes import DocumentStatus
from ..domain.labels import DOCUMENT_STATUS
from ..service import instance, logs, manager
from .common import human_size, local_time, open_workspace


def service_command(argv: list[str]) -> int:
    parser = argparse.ArgumentParser(
        prog="iplikci servis",
        description="İplikçi Nedim servisi: API, olay akışı ve arka plan işleri, yalnızca 127.0.0.1'de. Her veri "
        "klasörünün tek bir servisi çalışır. kur servisi işletim sisteminin servis yöneticisine kaydeder (macOS'ta "
        "launchd, Linux'ta systemd, Windows'ta Görev Zamanlayıcı): oturum açılışında başlar, hatayla durursa yeniden "
        "başlar. calistir servisi ön planda çalıştırır ve arayüz için tek kullanımlık bir giriş bağlantısı yazar.",
    )
    commands = parser.add_subparsers(dest="komut", required=True, metavar="KOMUT")
    commands.add_parser(
        "kur",
        help="arka plan servisini kur ve başlat",
        description="Arka plan servisini kurar ve başlatır; eski kaydın yerine geçer. Servis kurulu bir kopyayı "
        "çalıştırır, geliştirme klasörünü asla.",
    )
    commands.add_parser(
        "kaldir",
        help="arka plan servisini durdur ve kaldır",
        description="Arka plan servisini durdurur ve kaldırır; veri klasörüne dokunmaz.",
    )
    commands.add_parser(
        "durum",
        help="servis çalışıyor mu; kuyruk, e-posta ve disk",
        description="Servisin çalışıp çalışmadığını, kaydını, kuyruğunu, e-posta alımını ve disk kullanımını yazar. "
        "Servis çalışmıyorsa 1 ile biter.",
    )
    commands.add_parser(
        "yeniden-baslat",
        help="arka plan servisini yeniden başlat",
        description="Arka plan servisini yeniden başlatır, örneğin yeni bir sürüm kurulduktan sonra.",
    )
    run = commands.add_parser(
        "calistir",
        help="servisi ön planda çalıştır",
        description="Servisi ön planda çalıştırır; servis yöneticisi de bu komutu çalıştırır.",
    )
    run.add_argument("--ev", type=Path, help="veri klasörü (varsayılan: IPLIKCI_HOME, yoksa sistemin klasörü)")
    args = parser.parse_args(argv)
    if args.komut == "calistir":
        return _service_run(open_workspace(parser, args.ev))
    ws = open_workspace(parser)
    if args.komut == "durum":
        return _service_status(ws)
    try:
        if args.komut == "kur":
            return _service_install(ws)
        if args.komut == "yeniden-baslat":
            return _service_restart()
        removed = manager.for_platform().uninstall()
    except manager.ManagerError as exc:
        print(str(exc), file=sys.stderr)
        return 1
    print("Arka plan servisi kaldırıldı." if removed else "Arka plan servisi kurulu değildi.")
    return 0


def _service_run(ws: Workspace) -> int:
    from ..service import runner  # the web stack loads only for the service

    try:
        runner.run(ws)
    except instance.AlreadyRunning as exc:
        print(f"{str(exc)[:1].upper()}{str(exc)[1:]}.", file=sys.stderr)
        return 1
    except KeyboardInterrupt:
        pass
    return 0


def _service_install(ws: Workspace) -> int:
    service = manager.for_platform()
    service.install(manager.installed_program(ws.home))
    print(f"Arka plan servisi kuruldu ({service.name}): {service.location}")
    print("Oturum açılışında kendiliğinden başlar; hatayla durursa yeniden başlar.")
    holder = instance.current(ws.run)
    if holder is not None and holder.pid:
        print(f"Bu veri klasörünü şu an süreç {holder.pid} sunuyor; o durunca arka plan servisi devralır.")
    from ..api.context import UI

    if not (UI / "index.html").is_file():
        print(
            "Uyarı: bu kopyada arayüz derlenmemiş; servis çalışır, arayüz açılmaz. Önce web/ klasöründe npm run build, "
            "sonra kopyayı yeniden kurun."
        )
    return 0


def _service_restart() -> int:
    service = manager.for_platform()
    if not service.installed():
        print("Arka plan servisi kurulu değil; önce kurun: iplikci servis kur", file=sys.stderr)
        return 1
    service.restart()
    print("Arka plan servisi yeniden başlatıldı.")
    return 0


def _service_status(ws: Workspace) -> int:
    from ..service import client

    holder = instance.current(ws.run)
    print(_holder_line(holder, ws.port))
    try:
        service = manager.for_platform()
        installed = service.installed()
    except manager.ManagerError as exc:
        print(f"Arka plan servisi: {exc}")
    else:
        print(
            f"Arka plan servisi: kurulu ({service.name}, {service.location})"
            if installed
            else "Arka plan servisi: kurulu değil; oturum açılışında başlamaz"
        )
    if holder is not None:
        try:
            found = client.call(ws, "GET", "/api/system")
        except client.ServiceError as exc:
            print(f"Servisten durum alınamadı: {exc}", file=sys.stderr)
            return 1
        for line in _system_lines(found, ws):
            print(line)
    print(f"Günlük: {ws.logs / logs.LOG_NAME}")
    return 0 if holder is not None else 1


def _holder_line(holder: instance.Holder | None, port: int) -> str:
    if holder is None:
        return "Servis çalışmıyor."
    parts = [f"Servis çalışıyor: http://127.0.0.1:{holder.port or port}"]
    if holder.pid:
        parts.append(f"süreç {holder.pid}")
    if holder.started_at:
        parts.append(f"başlangıç {local_time(holder.started_at)}")
    if holder.version:
        parts.append(f"sürüm {holder.version}")
    return " · ".join(parts)


def _system_lines(found: dict[str, Any], ws: Workspace) -> list[str]:
    """What /api/system says, a line per area. The service may be another version than this command: a missing
    part is left out."""
    lines: list[str] = []
    home = (found.get("service") or {}).get("home")
    if home and home != str(ws.home):
        lines.append(f"Dikkat: bu adreste başka bir veri klasörünün servisi yanıt veriyor ({home}).")
    documents: dict[str, int] = found.get("documents") or {}
    if documents:
        shown = ", ".join(f"{_status_label(code)}: {n}" for code, n in sorted(documents.items()))
        lines.append(f"Belgeler: {shown}")
    counts: dict[str, int] = (found.get("queue") or {}).get("counts") or {}
    lines.append(f"Kuyruk: {counts.get('queued', 0)} bekleyen, {counts.get('failed', 0)} başarısız iş")
    if mail_state := found.get("mail"):
        lines.append(_mail_line(mail_state))
    if backups := found.get("backup"):
        lines.append(_backups_line(backups))
    if disk := found.get("disk"):
        lines.append(
            f"Disk: arşiv {human_size(disk.get('vault', 0))} · veritabanı {human_size(disk.get('database', 0))} · "
            f"boş {human_size(disk.get('free', 0))}"
        )
    return lines


def _status_label(code: str) -> str:
    try:
        return DOCUMENT_STATUS[DocumentStatus(code)]
    except ValueError:
        return code


def _mail_line(state: dict[str, Any]) -> str:
    connector = "tarayıcı eklentisi" if state.get("connector") == "browser_bridge" else "IMAP"
    if not state.get("configured"):
        return f"E-posta ({connector}): kurulu değil"
    if state.get("stopped"):
        return f"E-posta ({connector}): giriş reddedildi; bağlantı yeniden kurulana dek alım durdu"
    last = f"son alım {local_time(state['last_run'])}" if state.get("last_run") else "henüz alım yok"
    error = f" · son hata: {state['last_error']}" if state.get("last_error") else ""
    return f"E-posta ({connector}): {last}{error}"


def _backups_line(state: dict[str, Any]) -> str:
    if not state.get("count"):
        return "Yedek: henüz yok"
    line = f"Yedek: son {local_time(state['last'])} · {state['count']} yedek, {human_size(state.get('size', 0))}"
    if state.get("rehearsal"):
        verdict = "geçti" if state.get("rehearsal_ok") else "sorun buldu"
        line += f" · geri yükleme provası {local_time(state['rehearsal'])}: {verdict}"
    return line


def open_command(argv: list[str]) -> int:
    parser = argparse.ArgumentParser(
        prog="iplikci ac",
        description="Arayüzü tarayıcıda tek kullanımlık bir giriş bağlantısıyla açar. Servis çalışıyor olmalı.",
    )
    parser.add_argument("--yazdir", action="store_true", help="bağlantıyı tarayıcıda açmadan yazdır")
    args = parser.parse_args(argv)
    from ..service import client

    ws = open_workspace(parser)
    try:
        url = str(client.call(ws, "POST", "/api/login-links")["url"])
    except client.ServiceDown as exc:
        print(f"{exc}. Geliştirme için servisi başlatın: uv run iplikci servis calistir", file=sys.stderr)
        return 1
    except client.ServiceError as exc:
        print(str(exc), file=sys.stderr)
        return 1
    if args.yazdir or not webbrowser.open(url):
        print(url)
    return 0
