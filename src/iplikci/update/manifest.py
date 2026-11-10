"""A release's manifest (ADR-0022): which version it is, what it brings, and the name, size and SHA-256 of every file
the release carries, signed with Ed25519. The release workflow writes and signs it (packaging/release.py); the
installed program believes nothing of a release before the signature checks with a key it carries (keys.TRUSTED).

The manifest is JSON. Fields this version does not know are left alone, so a newer manifest still reads; a field it
knows with a wrong value refuses the whole manifest."""

import base64
import binascii
import json
import platform
import re
import sys
from collections.abc import Mapping
from dataclasses import dataclass, field
from typing import Any, cast

from cryptography.exceptions import InvalidSignature
from cryptography.hazmat.primitives import serialization
from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PrivateKey, Ed25519PublicKey

from . import keys

FORMAT = 1
PRODUCT = "iplikci-nedim"
NOTES_LIMIT = 50_000  # characters: a changelog section, never a book
SIZE_LIMIT = 1 << 31  # bytes: GitHub keeps a release's file under 2 GB
_VERSION = re.compile(r"\d+(?:\.\d+){1,3}")
_DAY = re.compile(r"\d{4}-\d{2}-\d{2}")
_PLATFORM = re.compile(r"(macos|linux|windows)-[a-z0-9_]+")
_NAME = re.compile(r"[A-Za-z0-9][A-Za-z0-9._-]{0,199}")
_SHA256 = re.compile(r"[0-9a-f]{64}")
_SYSTEMS = {"darwin": "macos", "win32": "windows"}
_MACHINES = {"amd64": "x86_64", "x64": "x86_64", "arm64": "aarch64"}  # as packaging/build.py names them


class ManifestError(Exception):
    """The manifest or its signature is not one this program accepts; the message says why (Turkish)."""


@dataclass(frozen=True, slots=True)
class Entry:
    name: str  # the release's file
    size: int
    sha256: str


@dataclass(frozen=True, slots=True)
class Extension:
    version: str
    file: Entry


@dataclass(frozen=True, slots=True)
class Manifest:
    version: str
    tag: str
    date: str  # YYYY-MM-DD
    notes: str  # the changelog's section, Markdown
    updates: Mapping[str, Entry] = field(default_factory=dict[str, Entry])  # by platform_key: what the program installs
    installers: Mapping[str, Entry] = field(default_factory=dict[str, Entry])  # by platform_key: for a person
    extension: Extension | None = None  # the browser extension's store package


def platform_key(system: str | None = None, machine: str | None = None) -> str | None:
    """This system's name in a manifest, as the release's files are named: macos-aarch64, linux-x86_64,
    windows-x86_64. None for a system the program is not built for."""
    system = sys.platform if system is None else system
    name = _SYSTEMS.get(system, "linux" if system.startswith("linux") else "")
    if not name:
        return None
    arch = (platform.machine() if machine is None else machine).lower()
    return f"{name}-{_MACHINES.get(arch, arch)}"


def render(manifest: Manifest) -> bytes:
    """The manifest as the release carries it: JSON, its keys sorted, UTF-8. The signature is over these bytes."""

    def entry(e: Entry) -> dict[str, Any]:
        return {"name": e.name, "size": e.size, "sha256": e.sha256}

    data: dict[str, Any] = {
        "format": FORMAT,
        "product": PRODUCT,
        "version": manifest.version,
        "tag": manifest.tag,
        "date": manifest.date,
        "notes": manifest.notes,
        "updates": {key: entry(e) for key, e in manifest.updates.items()},
        "installers": {key: entry(e) for key, e in manifest.installers.items()},
        "extension": None
        if manifest.extension is None
        else {"version": manifest.extension.version, "file": entry(manifest.extension.file)},
    }
    text = json.dumps(data, ensure_ascii=False, indent=2, sort_keys=True) + "\n"
    parse(text.encode())  # what this writes, this reads
    return text.encode()


def sign(manifest: bytes, private_key_pem: bytes, key_name: str) -> bytes:
    """The signature file of a manifest: the key's name and the Ed25519 signature over the manifest's bytes."""
    try:
        key = serialization.load_pem_private_key(private_key_pem, password=None)
    except (ValueError, TypeError) as exc:
        raise ManifestError(f"imza anahtarı okunamadı: {exc}") from None
    if not isinstance(key, Ed25519PrivateKey):
        raise ManifestError("imza anahtarı bir Ed25519 anahtarı değil")
    signature = base64.b64encode(key.sign(manifest)).decode()
    return (json.dumps({"key": key_name, "signature": signature}, sort_keys=True) + "\n").encode()


def verify(manifest: bytes, signature: bytes, trusted: Mapping[str, str] | None = None) -> Manifest:
    """The manifest, once its signature checks with a key of `trusted` (the program's own, keys.TRUSTED, by
    default); ManifestError otherwise, before anything of the manifest is believed."""
    trusted = keys.TRUSTED if trusted is None else trusted
    try:
        found: object = json.loads(signature.decode("utf-8"))
    except (UnicodeDecodeError, ValueError):
        raise ManifestError("bildirgenin imza dosyası okunamadı") from None
    if not isinstance(found, dict):
        raise ManifestError("bildirgenin imza dosyası okunamadı")
    sealed = cast(dict[str, object], found)
    name, value = sealed.get("key"), sealed.get("signature")
    if not isinstance(name, str) or not isinstance(value, str):
        raise ManifestError("bildirgenin imza dosyası eksik")
    if name not in trusted:
        raise ManifestError(f"bildirge bu programın tanımadığı bir anahtarla imzalanmış ({name[:40]})")
    try:
        raw = base64.b64decode(value, validate=True)
        Ed25519PublicKey.from_public_bytes(base64.b64decode(trusted[name], validate=True)).verify(raw, manifest)
    except (binascii.Error, ValueError, InvalidSignature):
        raise ManifestError(
            "bildirgenin imzası doğrulanamadı: dosya değiştirilmiş ya da başka biri imzalamış"
        ) from None
    return parse(manifest)


def parse(data: bytes) -> Manifest:
    """The manifest in data, every field this version knows checked; ManifestError names the first that is wrong.
    It says nothing of who wrote it: verify does."""
    try:
        found: object = json.loads(data.decode("utf-8"))
    except (UnicodeDecodeError, ValueError):
        raise ManifestError("bildirge okunamadı: JSON değil") from None
    if not isinstance(found, dict):
        raise ManifestError("bildirge okunamadı: bir nesne değil")
    top = cast(dict[str, object], found)
    if top.get("format") != FORMAT:
        raise ManifestError(f"bildirgenin biçimi bu programın okuduğu değil ({top.get('format')!r})")
    if top.get("product") != PRODUCT:
        raise ManifestError("bildirge başka bir ürünün")
    version = _text(top, "version", _VERSION)
    tag = _text(top, "tag")
    if tag != f"v{version}":
        raise ManifestError(f"bildirgenin etiketi sürümüyle uyuşmuyor ({tag!r})")
    notes = top.get("notes", "")
    if not isinstance(notes, str) or len(notes) > NOTES_LIMIT:
        raise ManifestError("bildirgenin notu okunamadı")
    return Manifest(
        version=version,
        tag=tag,
        date=_text(top, "date", _DAY),
        notes=notes,
        updates=_entries(top, "updates"),
        installers=_entries(top, "installers"),
        extension=_extension(top.get("extension")),
    )


def _text(table: dict[str, object], key: str, pattern: re.Pattern[str] | None = None) -> str:
    value = table.get(key)
    if not isinstance(value, str) or (pattern is not None and not pattern.fullmatch(value)):
        raise ManifestError(f"bildirgede {key} okunamadı")
    return value


def _entries(table: dict[str, object], key: str) -> dict[str, Entry]:
    value = table.get(key, {})
    if not isinstance(value, dict):
        raise ManifestError(f"bildirgede {key} okunamadı")
    found: dict[str, Entry] = {}
    for name, entry in cast(dict[object, object], value).items():
        if not isinstance(name, str) or not _PLATFORM.fullmatch(name):
            raise ManifestError(f"bildirgede {key} içinde tanınmayan bir sistem var")
        found[name] = _entry(entry, f"{key}.{name}")
    return found


def _entry(value: object, where: str) -> Entry:
    if not isinstance(value, dict):
        raise ManifestError(f"bildirgede {where} okunamadı")
    table = cast(dict[str, object], value)
    name, size, digest = table.get("name"), table.get("size"), table.get("sha256")
    if not isinstance(name, str) or not _NAME.fullmatch(name) or ".." in name:
        raise ManifestError(f"bildirgede {where} dosyasının adı okunamadı")
    if not isinstance(size, int) or isinstance(size, bool) or not 0 < size < SIZE_LIMIT:
        raise ManifestError(f"bildirgede {where} dosyasının boyutu okunamadı")
    if not isinstance(digest, str) or not _SHA256.fullmatch(digest):
        raise ManifestError(f"bildirgede {where} dosyasının özeti okunamadı")
    return Entry(name, size, digest)


def _extension(value: object) -> Extension | None:
    if value is None:
        return None
    if not isinstance(value, dict):
        raise ManifestError("bildirgede extension okunamadı")
    table = cast(dict[str, object], value)
    return Extension(_text(table, "version", _VERSION), _entry(table.get("file"), "extension"))
