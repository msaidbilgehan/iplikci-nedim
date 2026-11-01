"""`iplikci eposta`: the IMAP connector for the accounts that allow app passwords (ADR-0015). While the service
runs, it fetches: `al` asks it to, instead of opening a second connection beside its own."""

import argparse
import getpass
import sys
from typing import Any

from ..app import mail
from ..app.workspace import Busy, Workspace
from ..service import instance
from .common import clear_progress, day_arg, local_time, open_workspace

MAIL_PASSWORD_HELP = """\
Gmail, programların girişi için uygulama şifresi ister (normal Gmail şifresi çalışmaz):
  1. Google hesabınızda 2 Adımlı Doğrulama açık olmalı.
  2. Google hesabınızın uygulama şifreleri sayfasında "iplikci" adıyla bir uygulama şifresi oluşturun ve
     gösterilen 16 harfi aşağıya yapıştırın.
Gelişmiş Koruma'daki hesaplarda uygulama şifresi yoktur; onlar için tarayıcı eklentisi var.
Şifre bu bilgisayarın anahtar zincirinde saklanır; ayar dosyasına ya da kayıtlara yazılmaz.
E-posta kutusu salt okunur açılır: orada hiçbir şey okundu işaretlenmez, taşınmaz, silinmez."""

BRIDGE_FETCHES = "E-postayı tarayıcı eklentisi getiriyor: tarayıcı açıkken yeni iletiler kendiliğinden gelir."


def mail_command(argv: list[str]) -> int:
    parser = argparse.ArgumentParser(
        prog="iplikci eposta",
        description="Bankaların ve listedeki diğer göndericilerin e-postalarını IMAP ile alır ve arşive koyar "
        "(uygulama şifresine izin veren hesaplar; Gelişmiş Koruma'daki Gmail için tarayıcı eklentisi var). E-posta "
        "kutusu salt okunur açılır: orada hiçbir şey değişmez. Yalnızca listedeki alan adlarından gelen ve sunucunun "
        "göndereni doğruladığı e-postalar alınır. Servis çalışırken e-postayı servis alır.",
    )
    commands = parser.add_subparsers(dest="komut", required=True, metavar="KOMUT")
    setup = commands.add_parser(
        "kur",
        help="e-posta hesabını kur",
        description="E-posta hesabını kurar: adres ve uygulama şifresi sorulur; şifre yazılırken görünmez ve "
        "anahtar zincirinde saklanır.",
    )
    setup.add_argument("--adres", help="e-posta adresi (verilmezse sorulur)")
    commands.add_parser("durum", help="bağlantıyı ve son alımı göster", description="Bağlantıyı ve son alımı yazar.")
    commands.add_parser("kaldir", help="hesabı ve şifresini unut", description="IMAP hesabını ve şifresini unutur.")
    fetch = commands.add_parser(
        "al",
        help="yeni e-postaları şimdi al",
        description="Yeni e-postaları şimdi alır; servis çalışıyorsa servisten ister.",
    )
    for command in (setup, fetch):
        command.add_argument(
            "--baslangic",
            type=day_arg,
            metavar="YYYY-AA-GG",
            help="bu günden sonra gelen e-postalar (değiştirilirse kutu o günden yeniden okunur)",
        )
    args = parser.parse_args(argv)
    ws = open_workspace(parser)
    if args.komut == "kur":
        return _setup(ws, args)
    try:
        if args.komut == "durum":
            print("\n".join(_status_lines(mail.status(ws))))
            return 0
        if args.komut == "kaldir":
            print("Hesap ve şifresi silindi." if mail.remove(ws) else "Kurulu bir IMAP hesabı yok.")
            return 0
        return _fetch(ws, args)
    except (mail.MailError, Busy) as exc:
        clear_progress()
        print(f"E-posta alınamadı: {exc}", file=sys.stderr)
        return 1


def _fetch(ws: Workspace, args: argparse.Namespace) -> int:
    if mail.status(ws)["connector"] == mail.BRIDGE:
        print(BRIDGE_FETCHES)
        return 0
    if args.baslangic:
        mail.set_start(ws, args.baslangic)
    acc = mail.account(ws)
    if acc is None:
        raise mail.NotConfigured(f"{mail.NOT_SET_UP} Kurmak için: iplikci eposta kur")
    if instance.current(ws.run) is not None:
        from ..service import client

        try:
            client.call(ws, "POST", "/api/mail/fetch")
        except client.ServiceError as exc:
            print(f"Servise iletilemedi: {exc}", file=sys.stderr)
            return 1
        print("Servis yeni e-postaları alıyor; sonucu: iplikci eposta durum")
        return 0
    print(f"E-posta kutusu okunuyor ({acc.server}, {acc.start:%d.%m.%Y} sonrası)…", file=sys.stderr)
    while True:
        out = mail.fetch(ws, progress=_progress)
        clear_progress()
        print(out.message)
        if not out.more:
            return 0


def _status_lines(state: dict[str, Any]) -> list[str]:
    """What mail.status says, a line each; never the address."""
    if state["connector"] == mail.BRIDGE:
        lines = [f"Bağlantı: tarayıcı eklentisi · {BRIDGE_FETCHES}"]
    elif not state["configured"]:
        return ["Bağlantı: IMAP, kurulu değil (kurmak için: iplikci eposta kur)"]
    else:
        lines = [f"Bağlantı: IMAP ({state['server']}) · {state['start']} sonrası gelenler"]
    lines.append(f"Son alım: {local_time(state['lastRun'])}" if state["lastRun"] else "Son alım: henüz yok")
    if state["stopped"]:
        lines.append("Durdu: giriş reddedildi; hesap yeniden kurulana dek hiç denenmez (hesap kilitlenmesin diye)")
    if state["lastError"]:
        lines.append(f"Son hata: {state['lastError']}")
    if state["totals"]:
        lines.append("Şimdiye dek: " + ", ".join(f"{name} {n}" for name, n in sorted(state["totals"].items())))
    return lines


def _progress(i: int, n: int) -> None:
    if sys.stderr.isatty():
        print(f"\r  e-postalar indiriliyor {i}/{n}", end="", file=sys.stderr, flush=True)


def _setup(ws: Workspace, args: argparse.Namespace) -> int:
    try:
        return _ask_and_set_up(ws, args)
    except (mail.MailError, Busy, argparse.ArgumentTypeError) as exc:
        print(f"Kurulamadı: {exc}", file=sys.stderr)
    except (EOFError, KeyboardInterrupt):
        print("\nKurulum yarıda bırakıldı; hiçbir şey kaydedilmedi.", file=sys.stderr)
    return 1


def _ask_and_set_up(ws: Workspace, args: argparse.Namespace) -> int:
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
        start = day_arg(answer) if answer else default
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
        "Servis çalışıyorsa yeni e-postalar kendiliğinden alınır; şimdi almak için: iplikci eposta al"
    )
    return 0
