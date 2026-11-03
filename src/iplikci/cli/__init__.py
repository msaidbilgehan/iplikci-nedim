"""Command line entry points. Every command works on the data folder: IPLIKCI_HOME, else the platform's
(ADR-0002). The commands are for developers and the users who want them; every user command has its place in the
interface (K14), and both call the same use cases in `app`. What the service owns (its status, a login link, an
e-mail fetch while it runs) the commands ask the running service for.

iplikci                         raporu üret (exports/)
iplikci ekle [YOL ...]          belgeleri arşive al: önce plan, --uygula ile uygula (yol yoksa gelen klasörü)
iplikci aysonu [AY] [--ac]      ay sonu raporları: hangi ay kapandı, hangisi neyi bekliyor
iplikci islem ara|duzelt|yetimler   işlem ara; nota, etikete, kategori ve gereklilik düzeltmesine bak ya da ekle
iplikci eposta kur|durum|kaldir|al   IMAP hesabı (uygulama şifresine izin veren hesaplar) ve şimdi alım
iplikci bildirim durum|kurallar|gecmis|dene   bildirim kanalları, kuralları, gönderilenler, deneme bildirimi
iplikci telegram kur|eslestir|kaldir   Telegram botunun belirteci (gizli istemle) ve sohbet eşleştirmesi
iplikci kurlar al [--gecmis]|durum   döviz kurlarını şimdi çek (--gecmis: geçmişin eksik günleri); kurların durumu
iplikci mcp                     Claude için MCP sunucusu (istemci başlatır)
iplikci servis calistir         servisi ön planda çalıştır (API, 127.0.0.1)
iplikci servis kur|kaldir|durum|yeniden-baslat   arka plan servisi (launchd, systemd, Görev Zamanlayıcı)
iplikci ac                      arayüzü tek kullanımlık giriş bağlantısıyla aç (servis çalışıyor olmalı)
iplikci uygulama                uygulamayı aç: servisi kaydet ve başlat, arayüzü aç (kurulum paketinin başlatıcısı)
iplikci yedek al|liste|geri-yukle|prova   yedek al, listele, geri yükle; geri yüklemenin provası
iplikci dogrula --taban         doğrulama tabanını al, öncekiyle karşılaştır (gerilemede çıkış kodu 1)
iplikci dev demo [KLASÖR]       sahte belgelerle demo veri klasörü kur
iplikci dev parser probe|debug DOSYA   okuyucular belgeyi tanıyor mu; okuyan okuyucu ne okuyor
iplikci dev parser test [KİMLİK]       okuyucular sahte belgelerini doğru okuyor mu
"""

import logging
import sys
from collections.abc import Callable

from .backup import backup_command
from .dev import dev_command
from .documents import add_command
from .mail import mail_command
from .mcp import mcp_command
from .notify import notify_command, telegram_command
from .rates import rates_command
from .report import month_end_command, report
from .service import app_command, open_command, service_command
from .transactions import transaction_command
from .verify import verify_command

COMMANDS: dict[str, Callable[[list[str]], int]] = {
    "ekle": add_command,
    "eposta": mail_command,
    "bildirim": notify_command,
    "telegram": telegram_command,
    "kurlar": rates_command,
    "mcp": mcp_command,
    "aysonu": month_end_command,
    "islem": transaction_command,
    "dogrula": verify_command,
    "servis": service_command,
    "ac": open_command,
    "uygulama": app_command,
    "yedek": backup_command,
    "dev": dev_command,
}


def main(argv: list[str] | None = None) -> int:
    argv = sys.argv[1:] if argv is None else argv
    # pdfminer warns about harmless font metadata in some bank PDFs.
    logging.getLogger("pdfminer").setLevel(logging.ERROR)
    if argv[:1] and argv[0] in COMMANDS:
        return COMMANDS[argv[0]](argv[1:])
    return report(argv)
