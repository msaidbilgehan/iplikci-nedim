"""`iplikci bildirim` and `iplikci telegram`: the notifications' channels, rules and history, a test on a channel,
the Telegram bot set up with its token in a hidden prompt (F13, ADR-0010), and whether it takes the documents its
chat sends it (ADR-0021). The interface's Bildirimler screen does the same."""

import argparse
import getpass
import sys
import time
from datetime import datetime

from ..app import notify, telegram
from ..app.notify import Actor, Channel, NotifyError, RulesError, SettingsError
from ..app.workspace import Workspace
from ..domain.labels import CHANNEL, DELIVERY_STATUS, DETAIL_LEVEL, EVENT_KIND, format_amount
from ..notify.channels import SendError
from .common import local_time, open_workspace

TELEGRAM_HELP = """\
Telegram bildirimleri sizin oluşturduğunuz bir bottan gelir:
  1. Telegram'da @BotFather ile konuşun ve /newbot yazın; bota bir ad ve "_bot" ile biten bir kullanıcı adı verin.
  2. BotFather'ın verdiği belirteci (123456789:AA… biçiminde) aşağıya yapıştırın.
Belirteç bu bilgisayarın anahtar zincirinde saklanır; ayar dosyasına ya da kayıtlara yazılmaz.
Ardından bir eşleştirme kodu gösterilir: bota "/start <kod>" gönderin; bildirimler o sohbete gelir.
O sohbetten bota dosya olarak gönderdiğiniz banka belgeleri de arşive alınır (kapatmak için: iplikci telegram
belgeler kapat)."""

CHECK_EVERY = 3.0  # seconds between two looks at the bot's messages while a pairing code is open
_CHANNELS = {
    "uygulama": Channel.IN_APP,
    "masaustu": Channel.DESKTOP,
    "telegram": Channel.TELEGRAM,
    "eposta": Channel.EMAIL,
}


def notify_command(argv: list[str]) -> int:
    parser = argparse.ArgumentParser(
        prog="iplikci bildirim",
        description="Bildirimler: kanallar, kurallar, gönderilenler ve bir kanala deneme bildirimi.",
    )
    commands = parser.add_subparsers(dest="komut", required=True, metavar="KOMUT")
    commands.add_parser("durum", help="kanalları ve sessiz saati göster", description="Kanalları ve sayıları yazar.")
    commands.add_parser("kurallar", help="bildirim kurallarını listele", description="Bildirim kurallarını yazar.")
    history = commands.add_parser("gecmis", help="gönderilen bildirimler", description="En yeni bildirimleri yazar.")
    history.add_argument("--kanal", choices=list(_CHANNELS), help="yalnızca bu kanal")
    history.add_argument("--sayi", type=int, default=20, help="en çok bu kadar (varsayılan 20)")
    test = commands.add_parser("dene", help="bir kanala deneme bildirimi gönder", description="Deneme bildirimi.")
    test.add_argument("kanal", choices=list(_CHANNELS))
    args = parser.parse_args(argv)
    ws = open_workspace(parser)
    try:
        if args.komut == "durum":
            print("\n".join(_status_lines(notify.status(ws))))
        elif args.komut == "kurallar":
            found = notify.load_rules(ws)
            print("\n".join(_rule_lines(found)))
        elif args.komut == "gecmis":
            channel = _CHANNELS[args.kanal] if args.kanal else None
            print("\n".join(_history_lines(notify.history(ws, limit=max(1, args.sayi), channel=channel))))
        else:
            notify.send_test(ws, _CHANNELS[args.kanal])
            print(f"Deneme bildirimi gönderildi: {CHANNEL[_CHANNELS[args.kanal]]}.")
    except (NotifyError, RulesError) as exc:
        print(f"Olmadı: {exc}", file=sys.stderr)
        return 1
    return 0


def _status_lines(found: notify.Status) -> list[str]:
    lines = [f"Sessiz saat: {found.quiet_hours or 'yok'}"]
    for state in found.channels:
        mark = "hazır" if state.ready else "açık, hazır değil" if state.on else "kapalı"
        level = f", {DETAIL_LEVEL[found.detail[state.channel]].lower()}" if state.channel in found.detail else ""
        lines.append(f"  {CHANNEL[state.channel]}: {mark}{level} — {state.note}")
    counts = ", ".join(f"{DELIVERY_STATUS[s].lower()} {n}" for s, n in found.counts.items() if n)
    lines.append(f"Bildirimler: {counts or 'henüz yok'}; kutuda okunmamış {found.unread}")
    lines.append(f"Telegram'dan belge alma: {'açık' if found.telegram_documents else 'kapalı'}")
    if found.rules.problem:
        lines.append(f"Kural dosyası okunamadı, uygulamayla gelen kurallar geçerli: {found.rules.problem}")
    return lines


def _rule_lines(found: notify.Rules) -> list[str]:
    lines = [] if found.own else ["Uygulamayla gelen kurallar (kendi kural dosyanız yok):"]
    if found.problem:
        lines.append(f"Kural dosyası okunamadı, uygulamayla gelen kurallar geçerli: {found.problem}")
    for rule in found.rules:
        c = rule.condition
        parts = [
            *([f"en çok {c.days} gün kala"] if c.days is not None else []),
            *([f"en az {format_amount(c.amount)} TL"] if c.amount is not None else []),
            *([f"başlığında “{c.text}”"] if c.text else []),
        ]
        channels = ", ".join(CHANNEL[ch] for ch in rule.channels) or "yalnızca uygulama"
        state = "" if rule.enabled else " (kapalı)"
        condition = f" [{'; '.join(parts)}]" if parts else ""
        lines.append(f"  {rule.name}{state}: {EVENT_KIND[rule.event]}{condition} → {channels}")
    return lines


def _history_lines(found: list[notify.Notification]) -> list[str]:
    if not found:
        return ["Henüz bildirim yok."]
    lines: list[str] = []
    for n in found:
        status = DELIVERY_STATUS[notify.DeliveryStatus(n.status)]
        error = f" ({n.error})" if n.error and n.status != "sent" else ""
        lines.append(f"{local_time(n.sent_at or n.created_at)}  {CHANNEL[Channel(n.channel)]}  {status}{error}")
        lines.append(f"    {n.title}: {n.body}")
    return lines


def telegram_command(argv: list[str]) -> int:
    parser = argparse.ArgumentParser(
        prog="iplikci telegram",
        description="Telegram bildirim kanalı: kendi botunuzun belirteci ve onunla eşleşen sohbet.",
    )
    commands = parser.add_subparsers(dest="komut", required=True, metavar="KOMUT")
    commands.add_parser(
        "kur",
        help="bot belirtecini gir ve sohbeti eşleştir",
        description="Bot belirteci sorulur (yazılırken görünmez) ve anahtar zincirinde saklanır; ardından bota "
        "gönderilecek eşleştirme kodu gösterilir.",
    )
    commands.add_parser("eslestir", help="yeni bir eşleştirme kodu al", description="Yeni bir eşleştirme kodu.")
    documents = commands.add_parser(
        "belgeler",
        help="eşleşen sohbetin bota gönderdiği belgeleri al ya da alma",
        description="Eşleşen sohbetten bota dosya olarak gönderilen banka belgeleri arşive alınır; kapalıyken servis "
        "botun iletilerini okumaz.",
    )
    documents.add_argument("durum", choices=["ac", "kapat"])
    commands.add_parser("kaldir", help="belirteci ve sohbeti unut", description="Belirteci ve sohbeti unutur.")
    args = parser.parse_args(argv)
    ws = open_workspace(parser)
    try:
        if args.komut == "kur":
            return _set_up(ws)
        if args.komut == "eslestir":
            return _pair(ws)
        if args.komut == "belgeler":
            on = args.durum == "ac"
            telegram.set_documents(ws, on, Actor.USER)
            print("Telegram'dan belge alma açıldı." if on else "Telegram'dan belge alma kapatıldı.")
            return 0
        notify.remove_telegram(ws, Actor.USER)
        print("Telegram belirteci ve eşleşen sohbet unutuldu.")
        return 0
    except (NotifyError, SendError, SettingsError) as exc:
        print(f"Olmadı: {exc}", file=sys.stderr)
        return 1
    except (EOFError, KeyboardInterrupt):
        print("\nYarıda bırakıldı.", file=sys.stderr)
        return 1


def _set_up(ws: Workspace) -> int:
    print(TELEGRAM_HELP + "\n")
    if sys.stdin.isatty():
        token = getpass.getpass("Bot belirteci (yazarken görünmez): ")
    else:  # piped in: one line, never an argument (arguments are visible to every process)
        token = sys.stdin.readline().rstrip("\r\n")
    found = notify.set_telegram_token(ws, token, Actor.USER)
    print(f"Bot doğrulandı: @{found.bot}")
    if not found.in_keyring:
        print(
            "Bu sistemde anahtar zinciri yok: belirteci IPLIKCI_TELEGRAM_TOKEN ortam değişkeniyle verin (servis için de)."
        )
    return _pair(ws)


def _pair(ws: Workspace) -> int:
    pairing = telegram.start_pairing(ws)
    print(f"Telegram'da @{pairing.bot} botuna şunu gönderin: /start {pairing.code}")
    if pairing.link:
        print(f"Ya da bu bağlantıyı açın: {pairing.link}")
    ends = datetime.fromisoformat(pairing.expires)
    print(
        f"Kodun geçerli olduğu son an: {local_time(pairing.expires)}. Bekleniyor (vazgeçmek için Ctrl+C)…",
        file=sys.stderr,
    )
    while datetime.now().astimezone() < ends:
        if telegram.check_pairing(ws):
            print("Eşleşti: bildirimler artık bu sohbete gelecek.")
            return 0
        time.sleep(CHECK_EVERY)
    print("Kodun süresi doldu; yeniden deneyin: iplikci telegram eslestir", file=sys.stderr)
    return 1
