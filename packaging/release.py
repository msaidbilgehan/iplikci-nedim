"""A release's manifest, its signature and its notes (ADR-0022), as the release workflow makes them from the files the
packages' jobs built:

    uv run python packaging/release.py --tag v0.10.0 --files dist/surum --notes dist/notlar.md

- The tag must be the version pyproject.toml holds, and every system's update file and installer must be there:
  iplikci-nedim-<version>-<system>-<arch>.<zip|tar.gz|exe> and .<dmg|AppImage|exe>; the browser extension's store
  package iplikci-kopru-<version>.zip goes in too when it is there.
- The manifest (iplikci-nedim-surum.json) names each file with its size and SHA-256 and carries the changelog's section
  of the version as its notes, which the installed program shows before it installs, and the day its heading gives.
- With UPDATE_SIGNING_KEY in the environment (the Ed25519 private key as PEM, the workflow's secret) the manifest is
  signed (iplikci-nedim-surum.json.sig) and the signature checked with the keys the program trusts: a secret that is
  not the program's key never publishes a release the installed copies would refuse. Without it nothing is signed and
  the command says so; the workflow fails then.

This is a development tool: it reads the repository and the folder of files it is given, and writes into that folder
and the notes' file."""

import argparse
import hashlib
import os
import re
import sys
import tomllib
from collections.abc import Mapping
from datetime import UTC, datetime
from pathlib import Path

from iplikci.update import manifest, source
from iplikci.update.manifest import Entry, Extension, Manifest, ManifestError

ROOT = Path(__file__).resolve().parents[1]
SLUG = "iplikci-nedim"
SYSTEMS = ("macos", "linux", "windows")
UPDATE_SUFFIX = {"macos": ".zip", "linux": ".tar.gz", "windows": ".exe"}
INSTALLER_SUFFIX = {"macos": ".dmg", "linux": ".AppImage", "windows": ".exe"}
_FILE = re.compile(
    rf"{SLUG}-(?P<version>\d+(?:\.\d+)*)-(?P<system>macos|linux|windows)-(?P<arch>[a-z0-9_]+)(?P<suffix>\..+)"
)
_EXTENSION = re.compile(r"iplikci-kopru-(?P<version>\d+(?:\.\d+)*)\.zip")


class ReleaseError(Exception):
    """The release cannot be made from these files; the message says why (Turkish)."""


def project_version(root: Path = ROOT) -> str:
    with (root / "pyproject.toml").open("rb") as f:
        return str(tomllib.load(f)["project"]["version"])


def notes(changelog: str, version: str) -> str:
    """The changelog's section of the version: what follows its "## [version]" heading up to the next version's."""
    lines = changelog.splitlines()
    start = next((i for i, line in enumerate(lines) if line.startswith(f"## [{version}]")), None)
    if start is None:
        raise ReleaseError(f"CHANGELOG.md'de {version} sürümünün bölümü yok")
    end = next((i for i in range(start + 1, len(lines)) if lines[i].startswith("## [")), len(lines))
    return "\n".join(lines[start + 1 : end]).strip() + "\n"


def title(changelog: str, version: str) -> str:
    """The release's title: the version and what the changelog's heading calls it."""
    for line in changelog.splitlines():
        if line.startswith(f"## [{version}]"):
            parts = line.split(" — ")
            return f"İplikçi Nedim {version}" + (f" — {parts[-1].strip()}" if len(parts) >= 3 else "")
    return f"İplikçi Nedim {version}"


def changelog_day(changelog: str, version: str) -> str | None:
    """The day the changelog's heading gives the version ("## [X.Y.Z] — YYYY-MM-DD — title"): the release's day as
    its notes say it, while the workflow's clock (UTC) may still be on the day before."""
    for line in changelog.splitlines():
        if line.startswith(f"## [{version}]"):
            found = re.search(r"\b\d{4}-\d{2}-\d{2}\b", line)
            return found.group(0) if found else None
    return None


def entry(path: Path) -> Entry:
    digest = hashlib.sha256()
    with path.open("rb") as f:
        while chunk := f.read(1 << 20):
            digest.update(chunk)
    return Entry(path.name, path.stat().st_size, digest.hexdigest())


def collect(folder: Path, version: str) -> tuple[dict[str, Entry], dict[str, Entry], Extension | None]:
    """The update files and the installers by system (macos-aarch64, …), and the extension's store package."""
    updates: dict[str, Entry] = {}
    installers: dict[str, Entry] = {}
    extension: Extension | None = None
    for path in sorted(folder.iterdir()):
        found = _FILE.fullmatch(path.name)
        if found is not None:
            if found["version"] != version:
                raise ReleaseError(f"{path.name} başka bir sürümün dosyası ({version} bekleniyordu)")
            system, suffix = found["system"], found["suffix"]
            key = f"{system}-{found['arch']}"
            if suffix == UPDATE_SUFFIX[system]:
                updates[key] = entry(path)
            if suffix == INSTALLER_SUFFIX[system]:
                installers[key] = entry(path)
            continue
        found = _EXTENSION.fullmatch(path.name)
        if found is not None:
            extension = Extension(found["version"], entry(path))
    missing = [s for s in SYSTEMS if not any(key.startswith(f"{s}-") for key in updates)]
    missing += [f"{s} kurulum paketi" for s in SYSTEMS if not any(key.startswith(f"{s}-") for key in installers)]
    if missing:
        raise ReleaseError(f"sürümün dosyaları eksik: {', '.join(missing)}")
    return updates, installers, extension


def make(
    tag: str,
    folder: Path,
    changelog: str,
    environ: Mapping[str, str],
    day: str | None = None,
    root: Path = ROOT,
) -> tuple[Manifest, bool]:
    """Write the manifest, and its signature with a key in the environment, into folder; the manifest and whether it
    was signed."""
    version = project_version(root)
    if tag != f"v{version}":
        raise ReleaseError(f"etiket {tag}, pyproject.toml'un sürümü {version}: etiket v{version} olmalı")
    updates, installers, extension = collect(folder, version)
    release = Manifest(
        version=version,
        tag=tag,
        date=day or changelog_day(changelog, version) or datetime.now(UTC).date().isoformat(),
        notes=notes(changelog, version),
        updates=updates,
        installers=installers,
        extension=extension,
    )
    data = manifest.render(release)
    (folder / source.MANIFEST).write_bytes(data)
    key = environ.get("UPDATE_SIGNING_KEY", "").strip()
    if not key:
        return release, False
    name = manifest.key_name(key.encode())
    if name is None:
        raise ReleaseError(
            "UPDATE_SIGNING_KEY programın güvendiği bir anahtar değil (update/keys.py); UPDATE_SIGNING_KEY yanlış"
        )
    seal = manifest.sign(data, key.encode(), name)
    try:
        manifest.verify(data, seal)
    except ManifestError as exc:
        raise ReleaseError(
            f"imza programın güvendiği anahtarla doğrulanmadı ({exc}); UPDATE_SIGNING_KEY yanlış"
        ) from None
    (folder / source.SIGNATURE).write_bytes(seal)
    return release, True


def main() -> None:
    parser = argparse.ArgumentParser(description="Sürümün bildirgesini, imzasını ve notunu yazar (ADR-0022).")
    parser.add_argument("--tag", required=True, help="sürüm etiketi, ör. v0.10.0")
    parser.add_argument("--files", type=Path, required=True, help="sürümün dosyalarının klasörü")
    parser.add_argument("--notes", type=Path, required=True, help="sürüm notunun yazılacağı dosya")
    parser.add_argument("--title", type=Path, help="sürüm başlığının yazılacağı dosya")
    args = parser.parse_args()
    changelog = (ROOT / "CHANGELOG.md").read_text(encoding="utf-8")
    try:
        release, signed = make(args.tag, args.files, changelog, os.environ)
    except (ReleaseError, ManifestError) as exc:
        sys.exit(f"Sürüm yapılamadı: {exc}")
    args.notes.write_text(release.notes, encoding="utf-8")
    if args.title is not None:
        args.title.write_text(title(changelog, release.version), encoding="utf-8")
    for key, found in sorted(release.updates.items()):
        print(f"{key}: {found.name} {found.size} bayt {found.sha256}")
    if not signed:
        sys.exit("UPDATE_SIGNING_KEY yok: bildirge imzalanmadı, sürüm yayımlanamaz")
    print(f"{source.MANIFEST} ve imzası yazıldı")


if __name__ == "__main__":
    main()
