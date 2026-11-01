"""`iplikci yedek`: take, list, restore and rehearse backups (architecture §19)."""

import argparse
import sys
from pathlib import Path

from ..app import backup
from ..app.workspace import Busy, Workspace
from ..domain.codes import BackupReason
from ..domain.labels import BACKUP_REASON
from ..service import instance
from .common import human_size, local_time, open_workspace


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
    ws = open_workspace(parser)
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
        f"{local_time(b.created_at)} · {reason} · {b.documents} belge, {b.annotations} düzeltme · {human_size(b.size)}"
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
