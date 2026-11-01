"""Command line entry points. Every command works on the data folder: IPLIKCI_HOME, else the platform's
(ADR-0002).

iplikci                         raporu üret (exports/)
iplikci ekle [YOL ...]          belgeleri arşive al: önce plan, --uygula ile uygula (yol yoksa gelen klasörü)
iplikci aysonu [AY] [--ac]      ay sonu raporları: hangi ay kapandı, hangisi neyi bekliyor
iplikci panel [--ac]            raporu ve belge ekleme yerini yerel web panelinde aç
iplikci eposta [--kur]          bankaların e-postayla gönderdiği belgeleri arşive al
iplikci otomatik [--kur]        e-postayı al, gelen klasörünü arşive al (--kur: kendiliğinden)
iplikci mcp                     Claude için MCP sunucusu (istemci başlatır)
iplikci dogrula --taban         doğrulama tabanını al, öncekiyle karşılaştır (gerilemede çıkış kodu 1)
iplikci dev demo [KLASÖR]       sahte belgelerle demo veri klasörü kur
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
from pathlib import Path

from . import baseline, demo, month_end
from .analysis import Dataset
from .app import intake
from .app.analysis import analyze
from .app.workspace import Busy, StalePlan, Workspace
from .insights import Insights, receipt_amount, tl
from .models import DEFAULT_EXPENSE_KINDS
from .settings.config import DEFAULT_PORT, SettingsError
from .settings.paths import HOME_ENV


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
        "otomatik": automatic,
        "mcp": mcp_command,
        "aysonu": month_end_command,
        "dogrula": verify_command,
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
        description="Ay sonu raporlarını üretir (cikti/ay-sonu/) ve her ayın ekstrelerle kapanıp kapanmadığını "
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
        description="Belgelerin doğrulama tabanını alır ve kayıtlı tabanla karşılaştırır. Daha az doğrulanan "
        "ekstre, yeni bir okunamayan belge ya da yeni belge gelmeden yeniden açılan bir ay gerilemedir: komut 1 "
        "ile biter ve taban kaydedilmez. Taban veri klasöründe (baseline.json) durur.",
    )
    which = parser.add_mutually_exclusive_group(required=True)
    which.add_argument("--taban", action="store_true", help="doğrulama tabanını al ve öncekiyle karşılaştır")
    parser.add_argument("--tarih", type=_day, help="ayların kapanışına bakılan gün, YYYY-AA-GG (varsayılan: bugün)")
    parser.add_argument("--kabul", action="store_true", help="gerileme olsa da yeni tabanı kaydet")
    parser.add_argument("--yeniden-oku", action="store_true", help="bütün belgeleri yeniden oku")
    args = parser.parse_args(argv)
    day = args.tarih or date.today()
    ws = _workspace(parser)
    path = ws.layout.baseline
    try:
        previous = baseline.load(path)
    except ValueError as exc:
        parser.error(f"kayıtlı taban okunamadı ({path}): {exc}")
    try:
        a = analyze(ws, _progress, today=day, reread=args.yeniden_oku)
    except Busy as exc:
        print(str(exc), file=sys.stderr)
        return 1
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


def _shown(value: object) -> str:
    return "—" if value is None else str(value)


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
    args = parser.parse_args(argv)
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


def automatic(argv: list[str]) -> int:
    from . import automation

    parser = argparse.ArgumentParser(
        prog="iplikci otomatik",
        description="E-posta kuruluysa bankaların yeni e-postalarını alır, gelen klasöründeki belgeleri plan "
        "göstermeden arşive alır, raporu yeniden üretir ve bildirim gösterir. --kur ile kendiliğinden "
        "çalışır: gelen klasörüne belge düştükçe (macOS, Linux) ve saatte bir.",
    )
    which = parser.add_mutually_exclusive_group()
    which.add_argument(
        "--kur",
        action="store_true",
        help="arka plan görevini kur (macOS: launchd, Linux: systemd, Windows: Görev Zamanlayıcı)",
    )
    which.add_argument("--kaldir", action="store_true", help="arka plan görevini kaldır")
    which.add_argument("--durum", action="store_true", help="arka plan görevinin durumunu göster")
    parser.add_argument("--kayit", help=argparse.SUPPRESS)  # the Windows task writes its own log
    parser.add_argument("--ev", help=argparse.SUPPRESS)  # the data folder the installed job works on
    args = parser.parse_args(argv)
    if args.kayit:
        log = open(args.kayit, "a", encoding="utf-8", buffering=1)  # noqa: SIM115 - open for the whole run
        sys.stdout = sys.stderr = log
    ws = _workspace(parser, Path(args.ev) if args.ev else None)
    if args.kur:
        try:
            where = automation.install(ws)
        except (OSError, RuntimeError) as exc:
            print(f"Kurulamadı: {exc}", file=sys.stderr)
            return 1
        print(
            f"Kuruldu: {where}\nİzlenen klasör: {ws.inbox}\nKayıt: {ws.logs / automation.LOG_NAME}\n"
            "Kaldırmak için: uv run iplikci otomatik --kaldir"
        )
        return 0
    if args.kaldir:
        print("Kaldırıldı." if automation.uninstall() else "Kurulu bir arka plan görevi yok.")
        return 0
    if args.durum:
        for key, value in automation.status(ws).items():
            print(f"{key}: {value}")
        return 0
    out = automation.run(ws, notify=not sys.stdout.isatty())
    print(f"{datetime.now():%Y-%m-%d %H:%M:%S} {out.message}")
    if out.mail_log:
        print(f"  {out.mail_log}")
    if out.trash:
        print(f"  çöp kutusuna taşınanlar: {out.trash}")
    return 0


def mail_command(argv: list[str]) -> int:
    from . import email_fetch

    parser = argparse.ArgumentParser(
        prog="iplikci eposta",
        description="Bankaların e-postayla gönderdiği ekstreleri, hesap dökümlerini ve dekontları IMAP ile (Gmail) "
        "alır ve arşive koyar. E-posta kutusu salt okunur açılır: orada hiçbir şey değişmez. Yalnızca "
        "settings.toml [mail] bank_senders alan adlarından gelen ve sunucunun göndereni doğruladığı e-postalar "
        "alınır.",
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
        except (email_fetch.MailError, Busy, argparse.ArgumentTypeError) as exc:
            print(f"Kurulamadı: {exc}", file=sys.stderr)
        except (EOFError, KeyboardInterrupt):
            print("\nKurulum yarıda bırakıldı; hiçbir şey kaydedilmedi.", file=sys.stderr)
        return 1
    try:
        if args.durum:
            for key, value in email_fetch.status(ws).items():
                print(f"{key}: {value}")
            return 0
        if args.kaldir:
            print("Hesap ve şifresi silindi." if email_fetch.forget(ws) else "Kurulu bir e-posta hesabı yok.")
            return 0
        if args.baslangic:
            email_fetch.set_start(ws, args.baslangic)
        acc = email_fetch.account(ws)
        if acc is None:
            raise email_fetch.NotConfigured(email_fetch.SETUP_HINT)
        print(f"{acc.address} okunuyor ({acc.server}, {acc.start:%d.%m.%Y} sonrası)…", file=sys.stderr)
        while True:
            out = email_fetch.fetch(ws, progress=_mail_progress)
            _clear_progress()
            print(out.message)
            for c in out.stored:
                print(f"  + {c.name}")
            if not out.more:
                break
    except (email_fetch.MailError, Busy) as exc:
        _clear_progress()
        print(f"E-posta alınamadı: {exc}", file=sys.stderr)
        return 1
    return 0


def _day(text: str) -> date:
    try:
        return date.fromisoformat(text)
    except ValueError:
        raise argparse.ArgumentTypeError(f"tarih YYYY-AA-GG biçiminde olmalı: {text!r}") from None


def _mail_progress(i: int, n: int, name: str) -> None:
    if sys.stderr.isatty():
        print(f"\r  e-postalar indiriliyor {i}/{n}", end="", file=sys.stderr, flush=True)


def _mail_setup(ws: Workspace, args: argparse.Namespace) -> int:
    from . import email_fetch

    print(email_fetch.APP_PASSWORD_HELP + "\n")
    address = args.adres or input("E-posta adresi: ").strip()
    if sys.stdin.isatty():
        secret = getpass.getpass("Uygulama şifresi (yazarken görünmez): ")
    else:  # piped in: one line, never an argument (arguments are visible to every process)
        secret = sys.stdin.readline().rstrip("\r\n")
    start = args.baslangic
    if start is None and sys.stdin.isatty():
        default = email_fetch.default_start()
        answer = input(f"Hangi günden sonra gelen e-postalar okunsun? [{default.isoformat()}]: ").strip()
        start = _day(answer) if answer else default
    print("Bağlanılıyor…", file=sys.stderr)
    acc, stored, folder = email_fetch.setup(ws, address, secret, start)
    print(f"Bağlandı: '{folder}' klasörü salt okunur açıldı.")
    if stored:
        print("Şifre bu bilgisayarın anahtar zincirinde saklandı.")
    else:
        print(
            f"Bu sistemde kullanılabilir bir anahtar zinciri yok: şifreyi {email_fetch.PASSWORD_ENV} ortam "
            "değişkeniyle verin (arka plan görevi için de)."
        )
    print(
        f"Kuruldu: {acc.address}, {acc.start:%d.%m.%Y} sonrası, {len(acc.senders)} banka alan adı.\n"
        "E-postaları şimdi almak için: uv run iplikci eposta\n"
        "Arka plan görevi kuruluysa (otomatik --kur) yeni e-postalar saatte bir kendiliğinden alınır."
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
