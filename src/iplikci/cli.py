"""Command line entry points. Every command works on the data folder: IPLIKCI_HOME, else the platform's
(ADR-0002).

iplikci                         raporu üret (exports/)
iplikci ekle [YOL ...]          belgeleri arşive al: önce plan, --uygula ile uygula (yol yoksa gelen klasörü)
iplikci aysonu [AY] [--ac]      ay sonu raporları: hangi ay kapandı, hangisi neyi bekliyor
iplikci islem ara|duzelt|yetimler   işlem ara; nota, etikete, kategori ve gereklilik düzeltmesine bak ya da ekle
iplikci panel [--ac]            raporu ve belge ekleme yerini yerel web panelinde aç
iplikci eposta [--kur]          bankaların e-postalarını IMAP ile al (uygulama şifresine izin veren hesaplar)
iplikci mcp                     Claude için MCP sunucusu (istemci başlatır)
iplikci servis calistir         servisi ön planda çalıştır (API, 127.0.0.1)
iplikci servis kur|kaldir|durum|yeniden-baslat   arka plan servisi (launchd, systemd, Görev Zamanlayıcı)
iplikci ac                      arayüzü tek kullanımlık giriş bağlantısıyla aç (servis çalışıyor olmalı)
iplikci yedek al|liste|geri-yukle|prova   yedek al, listele, geri yükle; geri yüklemenin provası
iplikci dogrula --taban         doğrulama tabanını al, öncekiyle karşılaştır (gerilemede çıkış kodu 1)
iplikci dev demo [KLASÖR]       sahte belgelerle demo veri klasörü kur
iplikci dev parser probe|debug DOSYA   okuyucular belgeyi tanıyor mu; okuyan okuyucu ne okuyor
iplikci dev parser test [KİMLİK]       okuyucular sahte belgelerini doğru okuyor mu
"""

import argparse
import getpass
import logging
import os
import re
import shlex
import sys
import webbrowser
from collections import Counter
from datetime import date, datetime, timedelta
from decimal import Decimal
from pathlib import Path
from typing import Any

from . import baseline, demo, month_end
from .analysis import Dataset
from .app import annotate, backup, checks, intake, rebuild
from .app.analysis import Analysis, analyze
from .app.workspace import Busy, StalePlan, Workspace
from .categorize import Categorizer
from .domain.codes import DEFAULT_EXPENSE_KINDS, Actor, BackupReason, DocumentStatus
from .domain.labels import BACKUP_REASON, DOCUMENT_STATUS, NECESSITY, format_amount
from .domain.text import fold
from .insights import Insights, receipt_amount, tl
from .parsers import tools as parser_tools
from .parsers.common import set_business_names
from .parsers.contract import Document
from .service import instance, logs, manager
from .settings import config
from .settings.config import DEFAULT_PORT, SettingsError
from .settings.paths import HOME_ENV, Layout
from .storage import annotations
from .vault.store import sha256_of


def _workspace(parser: argparse.ArgumentParser, home: Path | None = None) -> Workspace:
    try:
        return Workspace.load(home)
    except (OSError, SettingsError) as exc:
        parser.error(str(exc))


def _progress(i: int, n: int, name: str) -> None:
    if sys.stderr.isatty():
        print(f"\r  belgeler okunuyor {i}/{n}", end="", file=sys.stderr, flush=True)


def _clear_progress() -> None:
    if sys.stderr.isatty():
        print("\r" + " " * 60 + "\r", end="", file=sys.stderr)


def main(argv: list[str] | None = None) -> int:
    argv = sys.argv[1:] if argv is None else argv
    # pdfminer warns about harmless font metadata in some bank PDFs.
    logging.getLogger("pdfminer").setLevel(logging.ERROR)
    commands = {
        "ekle": add_command,
        "panel": panel_command,
        "eposta": mail_command,
        "mcp": mcp_command,
        "aysonu": month_end_command,
        "islem": transaction_command,
        "dogrula": verify_command,
        "servis": service_command,
        "ac": open_command,
        "yedek": backup_command,
        "dev": dev_command,
    }
    if argv[:1] and argv[0] in commands:
        return commands[argv[0]](argv[1:])
    return report(argv)


def report(argv: list[str]) -> int:
    parser = argparse.ArgumentParser(
        prog="iplikci",
        description="Arşivdeki banka belgelerinden gider, gelir, gereklilik ve tahmin raporunu üretir (exports/). "
        "Belge eklemek için: iplikci ekle",
    )
    parser.add_argument("--ac", action="store_true", help="raporu tarayıcıda aç")
    parser.add_argument("--yeniden-oku", action="store_true", help="bütün belgeleri yeniden oku")
    args = parser.parse_args(argv)
    ws = _workspace(parser)
    print("Belgeler okunuyor…", file=sys.stderr)
    try:
        a = analyze(ws, _progress, write=True, reread=args.yeniden_oku)
    except Busy as exc:
        print(str(exc), file=sys.stderr)
        return 1
    _clear_progress()
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
    ws = _workspace(parser)
    try:
        a = analyze(ws, _progress, write=True)
    except Busy as exc:
        print(str(exc), file=sys.stderr)
        return 1
    _clear_progress()
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
    parser.add_argument("--tarih", type=_day, help="ayların kapanışına bakılan gün, YYYY-AA-GG (varsayılan: bugün)")
    parser.add_argument("--kabul", action="store_true", help="--taban: gerileme olsa da yeni tabanı kaydet")
    parser.add_argument("--yeniden-oku", action="store_true", help="--taban: bütün belgeleri yeniden oku")
    args = parser.parse_args(argv)
    day = args.tarih or date.today()
    ws = _workspace(parser)
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
    a = analyze(ws, _progress, today=day, reread=args.yeniden_oku)
    _clear_progress()
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
    r = rebuild.check(ws, today=day, progress=_progress)
    _clear_progress()
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


# --- the service ---------------------------------------------------------------------------------------


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
        return _service_run(_workspace(parser, args.ev))
    ws = _workspace(parser)
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
    from .service import runner  # the web stack loads only for the service

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
    from .service import client

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
        parts.append(f"başlangıç {_local_time(holder.started_at)}")
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
            f"Disk: arşiv {_size(disk.get('vault', 0))} · veritabanı {_size(disk.get('database', 0))} · "
            f"boş {_size(disk.get('free', 0))}"
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
    last = f"son alım {_local_time(state['last_run'])}" if state.get("last_run") else "henüz alım yok"
    error = f" · son hata: {state['last_error']}" if state.get("last_error") else ""
    return f"E-posta ({connector}): {last}{error}"


def _backups_line(state: dict[str, Any]) -> str:
    if not state.get("count"):
        return "Yedek: henüz yok"
    line = f"Yedek: son {_local_time(state['last'])} · {state['count']} yedek, {_size(state.get('size', 0))}"
    if state.get("rehearsal"):
        verdict = "geçti" if state.get("rehearsal_ok") else "sorun buldu"
        line += f" · geri yükleme provası {_local_time(state['rehearsal'])}: {verdict}"
    return line


def _local_time(iso: str) -> str:
    """An ISO time in the computer's time zone, as Turkish readers write it."""
    try:
        return datetime.fromisoformat(iso).astimezone().strftime("%d.%m.%Y %H:%M")
    except ValueError:
        return iso


def _size(n: int) -> str:
    """A byte count in the largest unit under 1024 of it, with a decimal comma."""
    value, unit = float(n), "B"
    for unit in ("B", "KB", "MB", "GB", "TB"):
        if value < 1024 or unit == "TB":
            break
        value /= 1024
    return f"{value:.0f} {unit}" if unit == "B" else f"{value:.1f} {unit}".replace(".", ",")


def open_command(argv: list[str]) -> int:
    parser = argparse.ArgumentParser(
        prog="iplikci ac",
        description="Arayüzü tarayıcıda tek kullanımlık bir giriş bağlantısıyla açar. Servis çalışıyor olmalı.",
    )
    parser.add_argument("--yazdir", action="store_true", help="bağlantıyı tarayıcıda açmadan yazdır")
    args = parser.parse_args(argv)
    from .service import client

    ws = _workspace(parser)
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


# --- backups -------------------------------------------------------------------------------------------


def backup_command(argv: list[str]) -> int:
    parser = argparse.ArgumentParser(
        prog="iplikci yedek",
        description="Yedekler: veritabanının tutarlı bir kopyası, birincil verilerin dökümü, ayarlar, kurallar ve "
        "belgelerin asılları. Servis her gece bir yedek alır ve yedekleri 14 gün saklar; ayda bir en yeni yedeği "
        "geçici bir klasöre geri yükleyip denetler.",
    )
    commands = parser.add_subparsers(dest="komut", required=True, metavar="KOMUT")
    commands.add_parser("al", help="şimdi bir yedek al", description="Şimdi bir yedek alır.")
    commands.add_parser("liste", help="yedekleri listele", description="Yedekleri en yenisinden başlayarak listeler.")
    restore = commands.add_parser(
        "geri-yukle",
        help="bir yedeği geri yükle",
        description="Bir yedeği geri yükler: veritabanını, ayarları ve kuralları yedektekiyle değiştirir, arşivde "
        "eksik olan belgeleri yedekten kopyalar. Önce şimdiki hâlin yedeğini alır; geri yükleme böylece geri "
        "alınabilir. Servis çalışırken yapılamaz. --uygula verilmezse hiçbir şeye dokunmaz, yalnızca ne olacağını "
        "yazar. --hedef ile yedek boş ya da yeni bir klasöre kurulur (örneğin başka bir bilgisayara taşırken).",
    )
    restore.add_argument("yedek", help="yedeğin adı (iplikci yedek liste) ya da klasörünün yolu")
    restore.add_argument("--hedef", type=Path, help="boş ya da yeni bir veri klasörü")
    restore.add_argument("--uygula", action="store_true", help="geri yüklemeyi yap")
    rehearse = commands.add_parser(
        "prova",
        help="bir yedeğin geri yüklenebildiğini denetle",
        description="Bir yedeği (verilmezse en yenisini) geçici bir klasöre geri yükler ve dogrula --arsiv ile "
        "--yeniden-kur denetimlerinden geçirir. Sorun bulursa 1 ile biter.",
    )
    rehearse.add_argument("yedek", nargs="?", help="yedeğin adı ya da klasörünün yolu (varsayılan: en yenisi)")
    args = parser.parse_args(argv)
    ws = _workspace(parser)
    try:
        if args.komut == "al":
            made = backup.take(ws, BackupReason.MANUAL)
            print(f"Yedek alındı: {made.path}\n{_backup_line(made)}")
            return 0
        if args.komut == "liste":
            return _backup_list(backup.every(ws), backup.folder(ws))
        if args.komut == "geri-yukle":
            return _backup_restore(ws, backup.find(ws, args.yedek), args.hedef, apply=args.uygula)
        return _backup_rehearse(ws, backup.find(ws, args.yedek) if args.yedek else None)
    except (backup.BackupError, Busy) as exc:
        print(str(exc), file=sys.stderr)
        return 1


def _backup_line(b: backup.Backup) -> str:
    reason = BACKUP_REASON[b.reason]
    return (
        f"{_local_time(b.created_at)} · {reason} · {b.documents} belge, {b.annotations} düzeltme · {_size(b.size)}"
        + (f" · {len(b.damaged)} bozuk asıl dışarıda kaldı" if b.damaged else "")
    )


def _backup_list(backups: list[backup.Backup], root: Path) -> int:
    if not backups:
        print(f"Henüz yedek yok ({root}).")
        return 0
    print(f"Yedekler ({root}):")
    for b in backups:
        print(f"  {b.name}  {_backup_line(b)}")
    return 0


def _backup_restore(ws: Workspace, chosen: backup.Backup, target: Path | None, *, apply: bool) -> int:
    print(f"Yedek: {chosen.name}\n  {_backup_line(chosen)}")
    if target is None:
        holder = instance.current(ws.run)
        if holder is not None:
            print(
                "Servis çalışırken geri yüklenemez: önce servisi durdurun (iplikci servis kaldir; ön plandaysa Ctrl+C).",
                file=sys.stderr,
            )
            return 1
        print(f"Bu veri klasörüne geri yüklenecek: {ws.home}\nÖnce şimdiki hâlin yedeği alınacak.")
    else:
        print(f"Bu klasöre kurulacak: {target}")
    if not apply:
        print("\nHiçbir şeye dokunulmadı. Geri yüklemek için aynı komutu --uygula ile çalıştırın.")
        return 0
    done = backup.restore(ws, chosen, target)
    print(f"\nGeri yüklendi: {done.home} · arşive geri kopyalanan belge: {done.objects}")
    if done.safety:
        print(f"Önceki hâlin yedeği: {done.safety} (geri almak için onu geri yükleyin)")
    if done.unknown:
        print(f"{done.unknown} belge arşivde duruyor ama bu yedeğin veritabanında yok (yedekten sonra gelmişler).")
    return 0


def _backup_rehearse(ws: Workspace, chosen: backup.Backup | None) -> int:
    print("Yedek geçici bir klasöre geri yükleniyor ve denetleniyor…", file=sys.stderr)
    result = backup.rehearse(ws, chosen)
    print(f"Yedek: {result.backup}")
    for line in result.problems:
        print(f"  ! {line}")
    for line in result.differences:
        print(f"  ! yeniden kurulunca: {line}")
    if not result.ok:
        print(f"\n{len(result.problems) + len(result.differences)} sorun var (!).", file=sys.stderr)
        return 1
    print("Geri yükleme provası geçti: arşiv sağlam, veritabanı arşivden aynı kuruluyor.")
    return 0


# --- transactions and the user's corrections ---------------------------------------------------------


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
    ws = _workspace(parser)
    try:
        a = analyze(ws, _progress)
    except Busy as exc:
        print(str(exc), file=sys.stderr)
        return 1
    _clear_progress()
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


def dev_command(argv: list[str]) -> int:
    parser = argparse.ArgumentParser(prog="iplikci dev", description="Geliştirici araçları.")
    commands = parser.add_subparsers(dest="komut", required=True, metavar="KOMUT")
    demo_parser = commands.add_parser(
        "demo",
        help="sahte belgelerle bir demo veri klasörü kur",
        description="Sahte banka belgeleriyle bir demo veri klasörü kurar (ADR-0002): belgeler arşive alınır ve "
        "okunur. Klasör yoksa açılır; varsa boş olmalıdır: hiçbir dosyanın üzerine yazılmaz.",
    )
    demo_parser.add_argument("klasor", nargs="?", help=f"veri klasörü (varsayılan: {HOME_ENV})")
    readers = commands.add_parser(
        "parser",
        help="okuyucuları belgeler ve sahte belgeler üzerinde dene",
        description="Okuyucuları (ADR-0005) bu süreçte çalıştırır; bir okuyucu hata verirse izi görünür. Şirket "
        "adları veri klasörünün ayarlarından okunur; klasöre bir şey yazılmaz.",
    )
    tool = readers.add_subparsers(dest="arac", required=True, metavar="ARAÇ")
    for name, text in (
        ("probe", "seçimin belgede ne gördüğünü ve her okuyucunun ne dediğini göster"),
        ("debug", "belgeyi okuyan okuyucunun okuduğunu satır satır, yerleriyle göster"),
    ):
        tool.add_parser(name, help=text, description=text[0].upper() + text[1:] + ".").add_argument(
            "dosya", help="belge"
        )
    tested = tool.add_parser(
        "test",
        help="okuyucuların sahte belgelerini oku ve denetle",
        description="Sahte belgeleri okur ve denetler: doğru okuyucu, hesap, satır sayısı, her satırın yeri, "
        "doğrulanan ekstre. Bir sorun varsa çıkış kodu 1'dir.",
    )
    tested.add_argument("kimlik", nargs="?", help="yalnızca bu okuyucu (ör. garanti.bonus_card)")
    args = parser.parse_args(argv)
    if args.komut == "parser":
        return _parser_tool(args, readers)
    given = args.klasor or os.environ.get(HOME_ENV, "").strip()
    if not given:
        demo_parser.error(f"klasör verilmedi ve {HOME_ENV} tanımlı değil")
    target = Path(given).expanduser().resolve()
    try:
        demo.build(target)
    except FileExistsError as exc:
        demo_parser.error(str(exc))
    print(
        f"Demo veri klasörü hazır: {target}\nDoğrulama tabanı için: "
        f"{HOME_ENV}={shlex.quote(str(target))} uv run iplikci dogrula --taban --tarih {demo.AS_OF}"
    )
    return 0


def _parser_tool(args: argparse.Namespace, parser: argparse.ArgumentParser) -> int:
    if args.arac == "test":
        ok, lines = parser_tools.test(args.kimlik)
        print("\n".join(lines))
        return 0 if ok else 1
    path = Path(args.dosya).expanduser()
    try:
        data = path.read_bytes()
    except OSError as exc:
        parser.error(f"{path}: {exc.strerror or exc}")
    layout = Layout.default()
    if layout.settings.exists():  # the app's company names, read without touching the data folder
        set_business_names(config.load(layout.settings).identity.business_names)
    doc = Document(path.name, str(path.parent), data, sha256_of(data))
    print("\n".join(parser_tools.probe(doc) if args.arac == "probe" else parser_tools.debug(doc)))
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
        f"{status['is']} şirket belgesi, {status['atlandi']} atlandı, {status['hata']} hata"
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
    ws = _workspace(parser)
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
    from . import panel

    parser = argparse.ArgumentParser(
        prog="iplikci panel",
        description="Raporu ve yeni belge ekleme yerini (tek dosya, çok dosya ya da klasör) yerel bir web panelinde "
        "açar. Yalnızca bu bilgisayardan erişilir (127.0.0.1); internete hiçbir şey gönderilmez.",
    )
    parser.add_argument("--port", type=int, help=f"port (varsayılan: settings.toml [server] port ya da {DEFAULT_PORT})")
    parser.add_argument("--ac", action="store_true", help="paneli tarayıcıda aç")
    args = parser.parse_args(argv)
    return panel.serve(_workspace(parser), args.port, args.ac, _progress, _clear_progress)


def mail_command(argv: list[str]) -> int:
    from .app import mail

    parser = argparse.ArgumentParser(
        prog="iplikci eposta",
        description="Bankaların ve listedeki diğer göndericilerin e-postalarını IMAP ile alır ve arşive koyar "
        "(uygulama şifresine izin veren hesaplar; Gelişmiş Koruma'daki Gmail için tarayıcı eklentisi var). E-posta "
        "kutusu salt okunur açılır: orada hiçbir şey değişmez. Yalnızca listedeki alan adlarından gelen ve sunucunun "
        "göndereni doğruladığı e-postalar alınır.",
    )
    which = parser.add_mutually_exclusive_group()
    which.add_argument("--kur", action="store_true", help="e-posta hesabını kur (adres ve uygulama şifresi sorulur)")
    which.add_argument("--durum", action="store_true", help="kurulu hesabı ve son alımı göster")
    which.add_argument("--kaldir", action="store_true", help="hesabı ve şifresini unut")
    parser.add_argument("--adres", help="--kur için e-posta adresi (verilmezse sorulur)")
    parser.add_argument(
        "--baslangic",
        type=_day,
        metavar="YYYY-AA-GG",
        help="bu günden sonra gelen e-postalar (değiştirilirse kutu o günden yeniden okunur)",
    )
    args = parser.parse_args(argv)
    ws = _workspace(parser)
    if args.kur:
        try:
            return _mail_setup(ws, args)
        except (mail.MailError, Busy, argparse.ArgumentTypeError) as exc:
            print(f"Kurulamadı: {exc}", file=sys.stderr)
        except (EOFError, KeyboardInterrupt):
            print("\nKurulum yarıda bırakıldı; hiçbir şey kaydedilmedi.", file=sys.stderr)
        return 1
    try:
        if args.durum:
            for key, value in mail.status(ws).items():
                print(f"{key}: {value}")
            return 0
        if args.kaldir:
            print("Hesap ve şifresi silindi." if mail.remove(ws) else "Kurulu bir IMAP hesabı yok.")
            return 0
        if args.baslangic:
            mail.set_start(ws, args.baslangic)
        acc = mail.account(ws)
        if acc is None:
            raise mail.NotConfigured(f"{mail.NOT_SET_UP} Kurmak için: uv run iplikci eposta --kur")
        print(f"E-posta kutusu okunuyor ({acc.server}, {acc.start:%d.%m.%Y} sonrası)…", file=sys.stderr)
        while True:
            out = mail.fetch(ws, progress=_mail_progress)
            _clear_progress()
            print(out.message)
            if not out.more:
                break
    except (mail.MailError, Busy) as exc:
        _clear_progress()
        print(f"E-posta alınamadı: {exc}", file=sys.stderr)
        return 1
    return 0


MAIL_PASSWORD_HELP = """\
Gmail, programların girişi için uygulama şifresi ister (normal Gmail şifresi çalışmaz):
  1. Google hesabınızda 2 Adımlı Doğrulama açık olmalı.
  2. Google hesabınızın uygulama şifreleri sayfasında "iplikci" adıyla bir uygulama şifresi oluşturun ve
     gösterilen 16 harfi aşağıya yapıştırın.
Gelişmiş Koruma'daki hesaplarda uygulama şifresi yoktur; onlar için tarayıcı eklentisi var.
Şifre bu bilgisayarın anahtar zincirinde saklanır; ayar dosyasına ya da kayıtlara yazılmaz.
E-posta kutusu salt okunur açılır: orada hiçbir şey okundu işaretlenmez, taşınmaz, silinmez."""


def _day(text: str) -> date:
    try:
        return date.fromisoformat(text)
    except ValueError:
        raise argparse.ArgumentTypeError(f"tarih YYYY-AA-GG biçiminde olmalı: {text!r}") from None


def _mail_progress(i: int, n: int) -> None:
    if sys.stderr.isatty():
        print(f"\r  e-postalar indiriliyor {i}/{n}", end="", file=sys.stderr, flush=True)


def _mail_setup(ws: Workspace, args: argparse.Namespace) -> int:
    from .app import mail

    print(MAIL_PASSWORD_HELP + "\n")
    address = args.adres or input("E-posta adresi: ").strip()
    if sys.stdin.isatty():
        secret = getpass.getpass("Uygulama şifresi (yazarken görünmez): ")
    else:  # piped in: one line, never an argument (arguments are visible to every process)
        secret = sys.stdin.readline().rstrip("\r\n")
    start = args.baslangic
    if start is None and sys.stdin.isatty():
        default = mail.default_start()
        answer = input(f"Hangi günden sonra gelen e-postalar okunsun? [{default.isoformat()}]: ").strip()
        start = _day(answer) if answer else default
    print("Bağlanılıyor…", file=sys.stderr)
    acc, stored, folder = mail.setup_imap(ws, address, secret, start)
    print(f"Bağlandı: '{folder}' klasörü salt okunur açıldı.")
    if stored:
        print("Şifre bu bilgisayarın anahtar zincirinde saklandı.")
    else:
        print(
            "Bu sistemde kullanılabilir bir anahtar zinciri yok: şifreyi IPLIKCI_MAIL_PASSWORD ortam değişkeniyle "
            "verin (servis için de)."
        )
    print(
        f"Kuruldu: {acc.start:%d.%m.%Y} sonrası, {len(acc.senders)} gönderici alan adı.\n"
        "Servis çalışıyorsa yeni e-postalar kendiliğinden alınır; şimdi almak için: uv run iplikci eposta"
    )
    return 0


def mcp_command(argv: list[str]) -> int:
    from . import mcp_server

    parser = argparse.ArgumentParser(
        prog="iplikci mcp",
        description="Claude için MCP sunucusu (stdio). MCP istemcisi (Claude Code, Claude Desktop) kendisi başlatır.",
    )
    parser.add_argument("--klasor", help=f"veri klasörü (varsayılan: {HOME_ENV}, yoksa platformun veri klasörü)")
    args = parser.parse_args(argv)
    return mcp_server.serve(_workspace(parser, Path(args.klasor) if args.klasor else None))


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
