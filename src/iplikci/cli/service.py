"""`iplikci servis`, `iplikci ac` and `iplikci uygulama`: the service in the foreground or in the system's service
manager, its status as the running service reports it (/api/system), a login link from it, and what opening the
installed app does (ADR-0017)."""

import argparse
import os
import sys
import webbrowser
from decimal import Decimal
from pathlib import Path
from typing import Any

from ..app.workspace import Workspace
from ..domain.codes import Channel, DeliveryStatus, DocumentStatus
from ..domain.labels import CHANNEL, DELIVERY_STATUS, DOCUMENT_STATUS
from ..insights import pct
from ..service import instance, logs, manager
from ..settings.config import SettingsError
from .common import human_size, local_time, open_workspace

STOP_SECONDS = 30.0  # how long removing the service waits for it to finish its requests and end


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
        help="servis çalışıyor mu; kuyruk, e-posta, kurlar ve disk",
        description="Servisin çalışıp çalışmadığını, kaydını, kuyruğunu, e-posta alımını, yedekleri, eşitlemeyi, "
        "döviz kurlarını ve disk kullanımını yazar. Servis çalışmıyorsa 1 ile biter.",
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
        return _service_remove(ws)
    except manager.ManagerError as exc:
        print(str(exc), file=sys.stderr)
        return 1


def _service_remove(ws: Workspace) -> int:
    """Unregister the service and wait until its process ended: the program is updated right after, and a running
    service whose files are replaced fails its requests."""
    if not manager.for_platform().uninstall():
        print("Arka plan servisi kurulu değildi.")
        return 0
    still = instance.wait_stopped(ws.run, STOP_SECONDS)
    if still is not None:
        who = f"süreç {still.pid}" if still.pid else "bir süreç"
        print(
            f"Arka plan servisi kaldırıldı, ama bu veri klasörünü hâlâ {who} sunuyor; o durmadan program "
            "güncellenmemeli.",
            file=sys.stderr,
        )
        return 1
    print("Arka plan servisi durdu ve kaldırıldı.")
    return 0


def _service_run(ws: Workspace) -> int:
    from ..app import lifecycle
    from ..service import runner  # the web stack loads only for the service

    try:
        code = runner.run(ws)  # a restart asked from the interface exits with lifecycle.RESTART
    except instance.AlreadyRunning as exc:
        print(f"{str(exc)[:1].upper()}{str(exc)[1:]}.", file=sys.stderr)
        return 1
    except KeyboardInterrupt:
        return 0
    if code == lifecycle.RESTART:
        _come_back()
    return code


def _come_back() -> None:
    """What the system's service manager needs, beyond the RESTART exit, to start the service again: nothing for
    launchd and systemd; on Windows a helper that waits for this process to end and runs the task."""
    try:
        manager.for_platform().restart_after(os.getpid())
    except (manager.ManagerError, OSError) as exc:
        print(f"Servis kendiliğinden yeniden başlamayabilir: {exc}", file=sys.stderr)


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
        try:  # a service of an older version has no notifications: the line is left out
            print(_notify_line(client.call(ws, "GET", "/api/notify/settings")))
        except client.ServiceError:
            pass
        try:  # nor one before ADR-0025 the sync
            print(_sync_line(client.call(ws, "GET", "/api/sync")))
        except client.ServiceError:
            pass
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
        if covered := mail_state.get("coverage"):
            lines.append(_coverage_line(covered))
    if backups := found.get("backup"):
        lines.append(_backups_line(backups))
    if (rates := found.get("rates")) and rates.get("summary"):  # one older than Phase 8 has none
        lines.append(f"Kurlar: {rates['summary']}")
    if disk := found.get("disk"):
        lines.append(
            f"Disk: arşiv {human_size(disk.get('vault', 0))} · veritabanı {human_size(disk.get('database', 0))} · "
            f"boş {human_size(disk.get('free', 0))}"
        )
    return lines


def _notify_line(found: dict[str, Any]) -> str:
    """The notification channels and how the notifications went: "Bildirimler: Masaüstü hazır, Telegram kapalı …"."""
    channels: list[str] = []
    for state in found.get("channels") or []:
        try:
            channel = Channel(state.get("channel"))
        except ValueError:
            continue
        if channel is not Channel.IN_APP:
            word = "hazır" if state.get("ready") else "açık, hazır değil" if state.get("on") else "kapalı"
            channels.append(f"{CHANNEL[channel]} {word}")
    counts: list[str] = []
    for code, n in (found.get("counts") or {}).items():
        if not n:
            continue
        try:
            status = DeliveryStatus(code)
        except ValueError:
            continue
        counts.append(f"{DELIVERY_STATUS[status].lower()} {n}")
    tail = f" · {', '.join(counts)}" if counts else " · henüz bildirim yok"
    return f"Bildirimler: {', '.join(channels) or 'kanal yok'}{tail}"


def _sync_line(found: dict[str, Any]) -> str:
    """The sync folder (ADR-0025): "Eşitleme: açık, Google Drive · 2 bilgisayar · son tur …"."""
    if not found.get("on"):
        return "Eşitleme: kapalı"
    parts = [f"Eşitleme: açık, {found.get('service') or found.get('folder', '')}"]
    devices: list[dict[str, Any]] = found.get("devices") or []
    parts.append(f"{sum(1 for d in devices if not d.get('left'))} bilgisayar")
    if found.get("last_at"):
        parts.append(f"son tur {local_time(found['last_at'])}")
    waiting = int(found.get("waiting_down", 0)) + int(found.get("waiting_up", 0))
    if waiting:
        parts.append(f"{waiting} belge taşınmayı bekliyor")
    if found.get("problem"):
        parts.append(f"sorun: {found['problem']}")
    return " · ".join(parts)


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


def _coverage_line(covered: dict[str, Any]) -> str:
    """F01's measure: the bank messages read or knowingly classified."""
    total = int(covered.get("total", 0))
    if not total:
        return "E-posta kapsamı: henüz banka iletisi yok"
    unknown = int(covered.get("unknown", 0))
    # Rounded down, as the System screen shows it: a measure with a target (F01: 90%) is never rounded up to it.
    share = Decimal((total - unknown) * 100 // total) / 100
    return (
        f"E-posta kapsamı: {total} banka iletisinin {pct(share)} işlendi ya da bilerek "
        f"sınıflandı; {unknown} tanesi henüz tanınmıyor"
    )


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


def app_command(argv: list[str]) -> int:
    parser = argparse.ArgumentParser(
        prog="iplikci uygulama",
        description="Uygulamayı açar: arka plan servisini bu kopya için kaydeder, çalışmıyorsa başlatır, eski bir "
        "sürüm çalışıyorsa yeniden başlatır ve arayüzü tarayıcıda tek kullanımlık bir giriş bağlantısıyla açar; ilk "
        "açılışta kurulum sihirbazı açılır. Kurulum paketinin başlatıcısı bunu çalıştırır ve sorunları bir pencerede "
        "söyler.",
    )
    parser.add_argument(
        "--sessiz",
        action="store_true",
        help="tarayıcıyı açma: yalnızca servisi kaydet ve başlat (Windows'ta sessiz güncellemenin sonunda)",
    )
    args = parser.parse_args(argv)
    from ..service import dialog, launcher

    try:
        ws = Workspace.load()
        opened = launcher.open_app(
            ws,
            manager.for_platform(),
            sys.platform,
            Path(sys.executable),
            login=(lambda _ws: "") if args.sessiz else None,
        )
    except (OSError, SettingsError) as exc:
        dialog.say(f"Veri klasörü açılamadı: {exc}")
        return 1
    except (launcher.LaunchError, manager.ManagerError) as exc:  # a development copy is refused here too
        dialog.say(str(exc))
        return 1
    if args.sessiz:
        return 0
    if not webbrowser.open(opened.url):
        dialog.say(f"Tarayıcı açılamadı. Arayüzü açmak için bu adresi tarayıcınıza yapıştırın:\n{opened.url}")
    return 0
