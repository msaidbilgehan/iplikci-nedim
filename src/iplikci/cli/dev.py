"""`iplikci dev`: the developers' tools: the demo data folder, the readers' probes and tests, and the interface's
API types."""

import argparse
import os
import shlex
from pathlib import Path

from .. import demo
from ..parsers import tools as parser_tools
from ..parsers.common import set_business_names
from ..parsers.contract import Document
from ..settings import config
from ..settings.paths import HOME_ENV, Layout
from ..vault.store import sha256_of


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
    types = commands.add_parser(
        "api-tipleri",
        help="arayüzün API tiplerini servisin OpenAPI belgesinden üret",
        description="Servisin OpenAPI belgesinden arayüzün TypeScript tiplerini üretir (ADR-0007). Depodaki yeri "
        "web/src/api/schema.ts'dir; API'nin modelleri değişince yeniden üretilir.",
    )
    types.add_argument("dosya", type=Path, help="yazılacak dosya (ör. web/src/api/schema.ts)")
    args = parser.parse_args(argv)
    if args.komut == "parser":
        return _parser_tool(args, readers)
    if args.komut == "api-tipleri":
        return _api_types(args.dosya)
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


def _api_types(target: Path) -> int:
    from ..api import typescript
    from ..api.app import openapi_document

    text = typescript.render(openapi_document())
    target = target.expanduser()
    if target.exists() and target.read_text(encoding="utf-8") == text:
        print(f"{target}: değişmedi")
        return 0
    target.write_text(text, encoding="utf-8")
    print(f"{target}: yazıldı")
    return 0
