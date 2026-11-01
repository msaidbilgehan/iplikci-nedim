"""settings.toml: what the user set (architecture §20). It may hold personal details (names, company names, an
e-mail address) but never a secret; secrets live in the system keyring (secrets.py).

The file is checked whole when it is read: an unknown section or key, or a value of the wrong kind, is an error
that names the key and the fix, in Turkish. A typo must never quietly fall back to a default, least of all in
business_names, which keeps company documents out.
"""

import re
import tomllib
from collections.abc import Callable, MutableMapping
from dataclasses import dataclass, field
from datetime import date, datetime
from pathlib import Path
from typing import Any, cast

import tomlkit
import tomlkit.exceptions

from .paths import write_private

DEFAULT_PORT = 8643
# The domains the banks' statement e-mails come from, base domains included; a subdomain counts too.
BANK_SENDERS = (
    "garantibbva.com.tr",
    "isbank.com.tr",
    "ileti.isbank.com.tr",
    "qnb.com.tr",
    "email.qnb.com.tr",
    "qnbfinansbank.com",
    "email.qnbfinansbank.com",
    "teb.com.tr",
    "vakifbank.com.tr",
)
CHANNELS = ("email", "telegram", "desktop")
DETAIL_LEVELS = ("full", "summary", "minimal")
_DOMAIN = re.compile(r"[a-z0-9](?:[a-z0-9-]*[a-z0-9])?(?:\.[a-z0-9](?:[a-z0-9-]*[a-z0-9])?)+")
_ADDRESS = re.compile(r"[^@\s\"\\]+@[a-z0-9.-]+\.[a-z]{2,}", re.IGNORECASE)
_HOURS = re.compile(r"([01]\d|2[0-3]):[0-5]\d-([01]\d|2[0-3]):[0-5]\d")
_CONTROL = re.compile(r"[\x00-\x1f\x7f]")


class SettingsError(ValueError):
    """settings.toml is not what the program reads; the message names the key and the fix."""


@dataclass(frozen=True, slots=True)
class Identity:
    names: tuple[str, ...] = ()  # the user's own names, to recognise transfers between own accounts
    business_names: tuple[str, ...] = ()  # company names: their documents are out of scope


@dataclass(frozen=True, slots=True)
class Server:
    port: int = DEFAULT_PORT
    remote: str = "off"  # "off" or "tailscale" (ADR-0012)


@dataclass(frozen=True, slots=True)
class Mail:
    address: str = ""
    connector: str = "imap"  # "imap" or "browser_bridge" (ADR-0016)
    imap_host: str = "imap.gmail.com"
    imap_port: int = 993
    folder: str = "auto"  # "auto": Gmail's All Mail, INBOX elsewhere
    start_day: date | None = None
    bank_senders: tuple[str, ...] = BANK_SENDERS
    other_senders: tuple[str, ...] = ()  # bills, subscriptions, shops
    verify_sender: bool = True  # only e-mails whose sender the receiving server verified (DMARC pass)
    smtp_host: str = "smtp.gmail.com"  # only for accounts that allow app passwords


def _default_detail() -> dict[str, str]:
    return {"email": "full", "telegram": "summary", "desktop": "summary"}


@dataclass(frozen=True, slots=True)
class Notify:
    quiet_hours: str = "23:00-08:00"
    detail: dict[str, str] = field(default_factory=_default_detail)


@dataclass(frozen=True, slots=True)
class Fx:
    providers: tuple[str, ...] = ("document", "tcmb", "ecb")


@dataclass(frozen=True, slots=True)
class Privacy:
    mcp_masking: str = "off"  # "off", "accounts" or "accounts_and_names"


@dataclass(frozen=True, slots=True)
class Backup:
    keep_days: int = 14
    folder: str = ""  # where the backups go; empty: backups/ in the data folder


@dataclass(frozen=True, slots=True)
class Settings:
    identity: Identity = Identity()
    server: Server = Server()
    mail: Mail = Mail()
    notify: Notify = field(default_factory=Notify)
    fx: Fx = Fx()
    privacy: Privacy = Privacy()
    backup: Backup = Backup()


# --- reading ------------------------------------------------------------------------------------------

type Check = Callable[[str, Any], Any]


def _text(where: str, value: Any) -> str:
    if not isinstance(value, str) or _CONTROL.search(value):
        raise SettingsError(f"{where} bir metin olmalı")
    return value.strip()


def _names(example: str) -> Check:
    def check(where: str, value: Any) -> tuple[str, ...]:
        if not isinstance(value, list) or not all(isinstance(n, str) and n.strip() for n in value):  # pyright: ignore[reportUnknownVariableType] - TOML value checked here
            raise SettingsError(f"{where} bir ad listesi olmalı, ör. {where.rsplit(' ', 1)[-1]} = [{example}]")
        return tuple(str(n).strip() for n in value)  # pyright: ignore[reportUnknownArgumentType, reportUnknownVariableType] - checked above

    return check


def _domains(where: str, value: Any, required: bool = False) -> tuple[str, ...]:
    if not isinstance(value, list) or (required and not value):
        raise SettingsError(f'{where} alan adlarının listesi olmalı, ör. ["banka.com.tr"]')
    found: list[str] = []
    for item in value:  # pyright: ignore[reportUnknownVariableType] - TOML value checked here
        domain = item.strip().lower().lstrip("@") if isinstance(item, str) else ""
        if not _DOMAIN.fullmatch(domain):
            raise SettingsError(f"{where} içinde geçersiz alan adı {item!r} (örnek: banka.com.tr)")
        found.append(domain)
    return tuple(dict.fromkeys(found))


def _bank_domains(where: str, value: Any) -> tuple[str, ...]:
    """The bank senders: at least one, since e-mail is searched by them."""
    return _domains(where, value, required=True)


def sender_domains(where: str, value: Any) -> tuple[str, ...]:
    """A list of sender domains as settings.toml takes mail.other_senders: each in lower case without a leading @,
    each once. A SettingsError names the first value that is no domain; where names the list in the message."""
    return _domains(where, value)


def _port(where: str, value: Any) -> int:
    if not isinstance(value, int) or isinstance(value, bool) or not 0 < value < 65536:
        raise SettingsError(f"{where} 1 ile 65535 arasında bir sayı olmalı")
    return value


def _days(where: str, value: Any) -> int:
    if not isinstance(value, int) or isinstance(value, bool) or value < 1:
        raise SettingsError(f"{where} pozitif bir gün sayısı olmalı")
    return value


def _flag(where: str, value: Any) -> bool:
    if not isinstance(value, bool):
        raise SettingsError(f"{where} true ya da false olmalı")
    return value


def _day(where: str, value: Any) -> date:
    if not isinstance(value, date) or isinstance(value, datetime):  # a TOML date, not a date and time
        raise SettingsError(f"{where} bir tarih olmalı, ör. 2024-01-01")
    return value


def _one_of(*options: str) -> Check:
    def check(where: str, value: Any) -> str:
        if value not in options:
            raise SettingsError(f"{where} şunlardan biri olmalı: {', '.join(options)}")
        return str(value)

    return check


def _address(where: str, value: Any) -> str:
    text = _text(where, value)
    if text and not _ADDRESS.fullmatch(text):
        raise SettingsError(f"{where} bir e-posta adresi olmalı")
    return text


def _host(where: str, value: Any) -> str:
    text = _text(where, value).lower()
    if not _DOMAIN.fullmatch(text):
        raise SettingsError(f"{where} bir alan adı olmalı (ör. imap.gmail.com)")
    return text


def _folder(where: str, value: Any) -> str:
    text = _text(where, value)
    if not text:
        raise SettingsError(f'{where} bir klasör adı ya da "auto" olmalı')
    return text


def _location(where: str, value: Any) -> str:
    text = _text(where, value)
    if text and not Path(text).expanduser().is_absolute():
        raise SettingsError(f'{where} bir klasörün tam yolu olmalı, ör. "/Volumes/Yedek/iplikci" (boş: veri klasörü)')
    return text


def _quiet_hours(where: str, value: Any) -> str:
    text = _text(where, value)
    if text and not _HOURS.fullmatch(text):
        raise SettingsError(f'{where} "SS:DD-SS:DD" biçiminde olmalı, ör. "23:00-08:00" (boş: sessiz saat yok)')
    return text


def _detail(where: str, value: Any) -> dict[str, str]:
    if not isinstance(value, dict):
        raise SettingsError(f'{where} kanal başına ayrıntı düzeyi olmalı, ör. {{email = "full"}}')
    detail = _default_detail()
    for channel, level in value.items():  # pyright: ignore[reportUnknownVariableType] - TOML value checked here
        if channel not in CHANNELS or level not in DETAIL_LEVELS:
            raise SettingsError(
                f"{where}: kanal {', '.join(CHANNELS)} ve düzey {', '.join(DETAIL_LEVELS)} olabilir "
                f"({channel} = {level!r} verildi)"
            )
        detail[str(channel)] = str(level)
    return detail


def _providers(where: str, value: Any) -> tuple[str, ...]:
    known = ("document", "tcmb", "ecb", "frankfurter")
    if not isinstance(value, list) or not value or not all(p in known for p in value):  # pyright: ignore[reportUnknownVariableType] - TOML value checked here
        raise SettingsError(f"{where} şunlardan oluşan bir liste olmalı: {', '.join(known)}")
    return tuple(str(p) for p in value)  # pyright: ignore[reportUnknownArgumentType, reportUnknownVariableType] - checked above


_SCHEMA: dict[str, tuple[type, dict[str, Check]]] = {
    "identity": (Identity, {"names": _names('"Ad Soyad"'), "business_names": _names('"ŞİRKET ADI"')}),
    "server": (Server, {"port": _port, "remote": _one_of("off", "tailscale")}),
    "mail": (
        Mail,
        {
            "address": _address,
            "connector": _one_of("imap", "browser_bridge"),
            "imap_host": _host,
            "imap_port": _port,
            "folder": _folder,
            "start_day": _day,
            "bank_senders": _bank_domains,
            "other_senders": _domains,
            "verify_sender": _flag,
            "smtp_host": _host,
        },
    ),
    "notify": (Notify, {"quiet_hours": _quiet_hours, "detail": _detail}),
    "fx": (Fx, {"providers": _providers}),
    "privacy": (Privacy, {"mcp_masking": _one_of("off", "accounts", "accounts_and_names")}),
    "backup": (Backup, {"keep_days": _days, "folder": _location}),
}


def parse(data: dict[str, Any], name: str = "settings.toml") -> Settings:
    """Settings from the tables of a settings file; name says which file in the messages."""
    sections: dict[str, Any] = {}
    for section, table in data.items():
        if section not in _SCHEMA:
            raise SettingsError(f"{name}: bilinmeyen bölüm [{section}] (bölümler: {', '.join(_SCHEMA)})")
        if not isinstance(table, dict):
            raise SettingsError(f"{name}: [{section}] bir tablo olmalı")
        model, checks = _SCHEMA[section]
        values: dict[str, Any] = {}
        for key, value in table.items():  # pyright: ignore[reportUnknownVariableType] - TOML table checked here
            if key not in checks:
                raise SettingsError(f"{name} [{section}]: bilinmeyen ayar {key!r} (ayarlar: {', '.join(checks)})")
            values[str(key)] = checks[str(key)](f"{name} [{section}] {key}", value)  # pyright: ignore[reportUnknownArgumentType] - key is a TOML key, a str
        sections[section] = model(**values)
    return Settings(**sections)


def update(path: Path, section: str, values: dict[str, Any]) -> Settings:
    """Set keys of one section of settings.toml, keeping everything else in the file as it was, comments too. The
    result is checked before it is written, so a value the program would refuse never reaches the file. A value of
    None removes its key. Returns the new settings."""
    text = path.read_text(encoding="utf-8") if path.exists() else ""
    try:
        document = tomlkit.parse(text)
    except tomlkit.exceptions.ParseError as exc:
        raise SettingsError(f"{path} okunamadı: {exc}") from exc
    tables: MutableMapping[str, Any] = document  # a TOML document is a mapping of its tables
    table: MutableMapping[str, Any] = tables.setdefault(section, tomlkit.table())
    for key, value in values.items():
        if value is None:
            table.pop(key, None)
        else:
            table[key] = list(cast(tuple[Any, ...], value)) if isinstance(value, tuple) else value
    new_text = tomlkit.dumps(document)
    settings = parse(tomllib.loads(new_text), str(path))
    tmp = path.with_name(f".{path.name}.yeni")
    write_private(tmp, new_text)
    tmp.replace(path)
    return settings


def load(path: Path) -> Settings:
    """The settings in path; the defaults when there is no such file yet."""
    try:
        with path.open("rb") as f:
            data = tomllib.load(f)
    except FileNotFoundError:
        return Settings()
    except tomllib.TOMLDecodeError as exc:
        raise SettingsError(f"{path} okunamadı: {exc}") from exc
    return parse(data, str(path))
