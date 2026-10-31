"""Command line entry points.

    iplikci [KAYNAK ...]            rapor üret
    iplikci aysonu [AY] [--ac]      ay sonu raporları: hangi ay kapandı, hangisi neyi bekliyor
    iplikci duzenle [KAYNAK ...]    belgeleri klasörle (önce yalnızca plan gösterir)
    iplikci panel [--ac]            raporu ve belge ekleme yerini yerel web panelinde aç
    iplikci eposta [--kur]          bankaların e-postayla gönderdiği belgeleri gelen kutusuna al
    iplikci otomatik [--kur]        e-postayı al, gelen kutusunu yerleştir (--kur: kendiliğinden)
    iplikci mcp                     Claude için MCP sunucusu (istemci başlatır)
"""

import argparse
import csv
import getpass
import logging
import re
import sys
import tomllib
import webbrowser
from collections import Counter
from datetime import date, datetime, timedelta
from pathlib import Path

from . import duzenle, month_end
from .analysis import Dataset
from .insights import Insights, interpret, receipt_amount, tl
from .models import DEFAULT_EXPENSE_KINDS
from .parsers.common import set_business_names
from .pipeline import run
from .report import build_payload
from .workspace import (
    DEFAULT_INBOX,
    DEFAULT_PORT,
    SETTINGS,
    Busy,
    Workspace,
    analyze,
    business_names,
    home,
    output_lock,
    write_outputs,
)


def _settings(parser: argparse.ArgumentParser) -> tuple[dict, Path]:
    base = home()
    path = base / SETTINGS
    if not path.exists():
        return {}, base
    with path.open("rb") as f:
        settings = tomllib.load(f)
    try:
        set_business_names(business_names(settings))
    except ValueError as exc:
        parser.error(str(exc))
    return settings, path.parent


def _workspace(parser: argparse.ArgumentParser, base: Path | None = None) -> Workspace:
    try:
        return Workspace.load(base)
    except (OSError, ValueError, tomllib.TOMLDecodeError) as exc:
        parser.error(str(exc))


def _progress(i: int, n: int, name: str) -> None:
    if sys.stderr.isatty():
        print(f"\r  belgeler okunuyor {i}/{n}", end="", file=sys.stderr, flush=True)


def _clear_progress() -> None:
    if sys.stderr.isatty():
        print("\r" + " " * 60 + "\r", end="", file=sys.stderr)


def _inbox(settings: dict, base: Path) -> Path:
    return (base / settings.get("gelen_klasoru", DEFAULT_INBOX)).resolve()


def _sources(parser: argparse.ArgumentParser, given: list[str], settings: dict, base: Path) -> list[Path]:
    sources = [Path(p) for p in given] or [base / p for p in settings.get("kaynaklar", [])]
    if not sources:
        parser.error(f"kaynak verilmedi ve {SETTINGS} içinde 'kaynaklar' yok")
    missing = [str(p) for p in sources if not p.exists()]
    if missing:
        parser.error("bulunamadı: " + ", ".join(missing))
    # Documents waiting in the inbox count too, unless the sources were named explicitly.
    inbox = _inbox(settings, base)
    if not given and inbox.is_dir() and not any(inbox.is_relative_to(s.resolve()) for s in sources):
        sources.append(inbox)
    return sources


def main(argv: list[str] | None = None) -> int:
    argv = sys.argv[1:] if argv is None else argv
    # pdfminer warns about harmless font metadata in some bank PDFs.
    logging.getLogger("pdfminer").setLevel(logging.ERROR)
    commands = {"duzenle": organize, "panel": panel_command, "eposta": mail_command, "otomatik": automatic,
                "mcp": mcp_command, "aysonu": month_end_command}
    if argv[:1] and argv[0] in commands:
        return commands[argv[0]](argv[1:])
    return report(argv)


def report(argv: list[str]) -> int:
    parser = argparse.ArgumentParser(
        prog="iplikci",
        description="Banka ekstrelerini ve hesap hareketlerini (PDF/HTML/XLS, mbox, klasör veya zip) okuyup "
                    "gider, gelir, gereklilik ve tahmin raporu üretir. Belgeleri klasörlemek için: iplikci duzenle",
    )
    parser.add_argument("kaynak", nargs="*", help="mbox dosyası, klasör, zip ya da tek belge (varsayılan: ayarlar.toml)")
    parser.add_argument("-o", "--cikti", help="çıktı klasörü (varsayılan: cikti)")
    parser.add_argument("-k", "--kurallar", help="kategori kuralları (varsayılan: kategoriler.yaml)")
    parser.add_argument("--ac", action="store_true", help="raporu tarayıcıda aç")
    parser.add_argument("--onbellek-yok", action="store_true", help="önbelleği kullanma, tüm belgeleri yeniden oku")
    args = parser.parse_args(argv)

    settings, base = _settings(parser)
    sources = _sources(parser, args.kaynak, settings, base)
    out = Path(args.cikti) if args.cikti else base / settings.get("cikti", "cikti")
    rules = Path(args.kurallar) if args.kurallar else base / settings.get("kurallar", "kategoriler.yaml")
    if not rules.exists():
        parser.error(f"kategori dosyası bulunamadı: {rules}")
    out.mkdir(parents=True, exist_ok=True)

    print("Kaynaklar taranıyor…", file=sys.stderr)
    with output_lock(out):
        ds, stats = run(sources, rules, None if args.onbellek_yok else out, _progress, settings)
        _clear_progress()

        ins = interpret(ds)
        months = month_end.build(ds, ins)
        outputs = write_outputs(out, ds, ins, build_payload(ds, stats, ins, months), months)

    _summary(ds, stats)
    _interpretation(ins)
    _closing(months[-3:])
    print(f"\nRapor : {outputs.html}\nCSV   : {outputs.csv}\nExcel : {outputs.xlsx}\n"
          f"Ay sonu: {outputs.month_end / month_end.INDEX}")
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


def _month_detail(me: month_end.MonthEnd, ds: Dataset) -> None:
    t = me.totals
    print(f"{me.name} — {me.label}\n{me.summary}\n")
    print(f"Gider {tl(t.expense)} · gelir {tl(t.income) if t.income is not None else 'bilinmiyor'} · kişilere "
          f"{tl(t.people)} · borç {tl(t.debt)} · birikim {tl(t.saving)}"
          + (f" · kalan {tl(t.left)}" if t.left is not None else ""))
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
            print(f"  {line.txn.date:%d.%m.%Y} {ds.accounts[line.txn.account].label}: {line.txn.description} "
                  f"{receipt_amount(ds, line)}")


def _summary(ds, stats) -> None:
    status = Counter(d.status for d in ds.documents)
    cards = [s for s in ds.statements if not s.is_account]
    accounts = [s for s in ds.statements if s.is_account]
    print(f"{stats['documents']} benzersiz belge ({stats['duplicates']} kopya atlandı): "
          f"{len(cards)} kart ekstresi, {len(accounts)} hesap dökümü, {status['dekont']} dekont, "
          f"{status['is']} şirket belgesi, {status['atlandi']} atlandı, {status['hata']} hata")
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


def organize(argv: list[str]) -> int:
    parser = argparse.ArgumentParser(
        prog="iplikci duzenle",
        description="Kişisel ekstre ve hesap dökümlerini <hedef>/<Banka>/<Hesap>/ altına anlaşılır adlarla taşır; "
                    "şirket belgelerini, kopyaları ve kullanılmayan belgeleri çöp kutusuna taşır. "
                    "--uygula verilmezse hiçbir dosyaya dokunmaz, yalnızca planı gösterir.",
    )
    parser.add_argument("kaynak", nargs="*", help="taranacak klasör, mbox, zip veya belgeler (varsayılan: ayarlar.toml)")
    parser.add_argument("--hedef", help="düzenlenmiş belgelerin klasörü (varsayılan: ayarlar.toml 'belge_klasoru')")
    parser.add_argument("--cop", help="silinenlerin taşınacağı klasör (varsayılan: sistemin çöp kutusu)")
    parser.add_argument("--uygula", action="store_true", help="planı uygula (dosyaları taşı)")
    args = parser.parse_args(argv)

    settings, base = _settings(parser)
    sources = _sources(parser, args.kaynak, settings, base)
    target = args.hedef or settings.get("belge_klasoru")
    if not target:
        parser.error(f"--hedef verilmedi ve {SETTINGS} içinde 'belge_klasoru' yok")
    root = (Path(target) if args.hedef else base / target).resolve()
    out = base / settings.get("cikti", "cikti")
    out.mkdir(parents=True, exist_ok=True)

    print("Belgeler taranıyor…", file=sys.stderr)
    with output_lock(out):
        plans = duzenle.plan(sources, root, out, _progress, inbox=_inbox(settings, base))
        _clear_progress()
        _print_plan(plans, root)
        stamp = datetime.now().strftime("%Y-%m-%d %H.%M.%S")
        if not args.uygula:
            plan_path = out / "duzenleme-plani.csv"
            _write_plan(plans, plan_path)
            print(f"\nHiçbir dosyaya dokunulmadı. Ayrıntılı plan: {plan_path}")
            print("Uygulamak için aynı komutu --uygula ile çalıştırın.")
            return 0

        trash = Path(args.cop) / f"iplikci silinenler {stamp}" if args.cop else duzenle.default_trash(root)
        log = root.parent / f"belge-duzenleme-kaydi {stamp}.csv"
        counts = duzenle.apply(plans, root, trash, log, keep=tuple(sources))
        if not args.cop:
            trash = duzenle.move_to_system_trash(trash)
    print("\nUygulandı: " + ", ".join(f"{duzenle.ACTION_LABELS[k]}: {v}" for k, v in sorted(counts.items())))
    if trash.exists():
        print(f"Silinenler (geri alınabilir): {trash}")
    print(f"Kayıt: {log}")
    return 0


def panel_command(argv: list[str]) -> int:
    from . import panel

    parser = argparse.ArgumentParser(
        prog="iplikci panel",
        description="Raporu ve yeni belge ekleme yerini (tek dosya, çok dosya ya da klasör) yerel bir web panelinde "
                    "açar. Yalnızca bu bilgisayardan erişilir (127.0.0.1); internete hiçbir şey gönderilmez.",
    )
    parser.add_argument("--port", type=int, help=f"port (varsayılan: ayarlar.toml 'panel_portu' ya da {DEFAULT_PORT})")
    parser.add_argument("--ac", action="store_true", help="paneli tarayıcıda aç")
    args = parser.parse_args(argv)
    return panel.serve(_workspace(parser), args.port, args.ac, _progress, _clear_progress)


def automatic(argv: list[str]) -> int:
    from . import automation

    parser = argparse.ArgumentParser(
        prog="iplikci otomatik",
        description="E-posta kuruluysa bankaların yeni e-postalarını alır, gelen kutusundaki belgeleri plan "
                    "göstermeden yerleştirir, raporu yeniden üretir ve bildirim gösterir. --kur ile kendiliğinden "
                    "çalışır: gelen kutusuna belge düştükçe (macOS, Linux) ve saatte bir.",
    )
    which = parser.add_mutually_exclusive_group()
    which.add_argument("--kur", action="store_true",
                       help="arka plan görevini kur (macOS: launchd, Linux: systemd, Windows: Görev Zamanlayıcı)")
    which.add_argument("--kaldir", action="store_true", help="arka plan görevini kaldır")
    which.add_argument("--durum", action="store_true", help="arka plan görevinin durumunu göster")
    parser.add_argument("--kayit", help=argparse.SUPPRESS)  # the Windows task writes its own log
    args = parser.parse_args(argv)
    if args.kayit:
        log = open(args.kayit, "a", encoding="utf-8", buffering=1)  # noqa: SIM115 - open for the whole run
        sys.stdout = sys.stderr = log
    ws = _workspace(parser)
    if args.kur:
        try:
            where = automation.install(ws)
        except (OSError, RuntimeError) as exc:
            print(f"Kurulamadı: {exc}", file=sys.stderr)
            return 1
        print(f"Kuruldu: {where}\nİzlenen klasör: {ws.inbox}\nKayıt: {ws.output / automation.LOG_NAME}\n"
              "Kaldırmak için: uv run iplikci otomatik --kaldir")
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
    if out.log:
        print(f"  kayıt: {out.log}")
    return 0


def mail_command(argv: list[str]) -> int:
    from . import email_fetch
    from .workspace import Busy

    parser = argparse.ArgumentParser(
        prog="iplikci eposta",
        description="Bankaların e-postayla gönderdiği ekstreleri, hesap dökümlerini ve dekontları IMAP ile (Gmail) "
                    "alır; yenilerini gelen kutusuna kopyalar. E-posta kutusu salt okunur açılır: orada hiçbir şey "
                    "değişmez. Yalnızca ayarlar.toml [eposta] gondericiler alan adlarından gelen ve sunucunun "
                    "göndereni doğruladığı e-postalar alınır.",
    )
    which = parser.add_mutually_exclusive_group()
    which.add_argument("--kur", action="store_true", help="e-posta hesabını kur (adres ve uygulama şifresi sorulur)")
    which.add_argument("--durum", action="store_true", help="kurulu hesabı ve son alımı göster")
    which.add_argument("--kaldir", action="store_true", help="hesabı ve şifresini unut")
    parser.add_argument("--adres", help="--kur için e-posta adresi (verilmezse sorulur)")
    parser.add_argument("--baslangic", type=_day, metavar="YYYY-AA-GG",
                        help="bu günden sonra gelen e-postalar (değiştirilirse kutu o günden yeniden okunur)")
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
        copied = 0
        while True:
            out = email_fetch.fetch(ws, progress=_mail_progress)
            _clear_progress()
            print(out.message)
            for _, path in out.copied:
                print(f"  + {path.relative_to(ws.inbox)}")
            copied += len(out.copied)
            if not out.more:
                break
    except (email_fetch.MailError, Busy) as exc:
        _clear_progress()
        print(f"E-posta alınamadı: {exc}", file=sys.stderr)
        return 1
    if copied:
        print(f"\nBelgeler {ws.inbox} klasöründe bekliyor. Yerleştirmek için panelde Belge ekle'yi açın ya da: "
              "uv run iplikci duzenle --uygula")
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
        print(f"Bu sistemde kullanılabilir bir anahtar zinciri yok: şifreyi {email_fetch.PASSWORD_ENV} ortam "
              "değişkeniyle verin (arka plan görevi için de).")
    print(f"Kuruldu: {acc.address}, {acc.start:%d.%m.%Y} sonrası, {len(acc.senders)} banka alan adı.\n"
          "E-postaları şimdi almak için: uv run iplikci eposta\n"
          "Arka plan görevi kuruluysa (otomatik --kur) yeni e-postalar saatte bir kendiliğinden alınır.")
    return 0


def mcp_command(argv: list[str]) -> int:
    from . import mcp_server

    parser = argparse.ArgumentParser(
        prog="iplikci mcp",
        description="Claude için MCP sunucusu (stdio). MCP istemcisi (Claude Code, Claude Desktop) "
                    "kendisi başlatır.",
    )
    parser.add_argument("--klasor",
                        help="ayarlar.toml dosyasının klasörü (varsayılan: IPLIKCI_HOME, yoksa çalışma klasörü)")
    args = parser.parse_args(argv)
    return mcp_server.serve(_workspace(parser, Path(args.klasor) if args.klasor else None))


def _print_plan(plans: list, root: Path) -> None:
    by_action = Counter(p.action for p in plans)
    print("Plan: " + ", ".join(f"{duzenle.ACTION_LABELS[k]}: {v}" for k, v in sorted(by_action.items())))
    tree = Counter(p.target.parent.relative_to(root) for p in plans if p.target is not None and p.action == duzenle.KEEP)
    print(f"\n{root}/")
    for folder, n in sorted(tree.items(), key=lambda kv: str(kv[0])):
        print(f"  {folder}/  ({n} belge)")
    reasons = Counter((p.action, p.reason.split(':')[0]) for p in plans if p.action != duzenle.KEEP)
    if reasons:
        print("\nTaşınmayan / silinecek belgeler:")
        for (action, reason), n in sorted(reasons.items()):
            print(f"  {n:4} × {duzenle.ACTION_LABELS[action]} — {reason}")


def _write_plan(plans: list, path: Path) -> None:
    with path.open("w", encoding="utf-8-sig", newline="") as f:
        w = csv.writer(f, delimiter=";")
        w.writerow(["İşlem", "Eski konum", "Yeni konum", "Neden"])
        rows = [[duzenle.ACTION_LABELS[p.action], str(p.path or f"{p.archive} › {p.name}"), str(p.target or ""), p.reason]
                for p in plans]
        w.writerows(sorted(rows))
