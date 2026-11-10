"""The program's own updates (ADR-0022): the signed manifest, which installer put the running copy where, and putting a
new version in place on macOS and Linux (Windows runs its setup program)."""

import base64
import io
import json
import os
import plistlib
import shutil
import subprocess
import sys
import tarfile
from pathlib import Path

import pytest
from cryptography.hazmat.primitives import serialization
from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PrivateKey

from iplikci import versions
from iplikci.update import install, keys, manifest, source
from iplikci.update.install import Installation, InstallError, Kind
from iplikci.update.manifest import Entry, Extension, Manifest, ManifestError

SHA = "a" * 64


def key_pair() -> tuple[bytes, str]:
    """A private key as PEM and its public key as keys.TRUSTED holds one."""
    private = Ed25519PrivateKey.generate()
    pem = private.private_bytes(
        serialization.Encoding.PEM, serialization.PrivateFormat.PKCS8, serialization.NoEncryption()
    )
    raw = private.public_key().public_bytes(serialization.Encoding.Raw, serialization.PublicFormat.Raw)
    return pem, base64.b64encode(raw).decode()


def release(version: str = "1.2.3", **changes: object) -> Manifest:
    found = Manifest(
        version=version,
        tag=f"v{version}",
        date="2026-11-11",
        notes="### Eklendi\n\n- Güncellemeler.",
        updates={
            "macos-aarch64": Entry(f"iplikci-nedim-{version}-macos-aarch64.zip", 1000, SHA),
            "linux-x86_64": Entry(f"iplikci-nedim-{version}-linux-x86_64.tar.gz", 2000, SHA),
            "windows-x86_64": Entry(f"iplikci-nedim-{version}-windows-x86_64.exe", 3000, SHA),
        },
        installers={"macos-aarch64": Entry(f"iplikci-nedim-{version}-macos-aarch64.dmg", 1100, SHA)},
        extension=Extension("0.8.0", Entry("iplikci-kopru-0.8.0.zip", 50, SHA)),
    )
    return Manifest(**{**{f: getattr(found, f) for f in found.__dataclass_fields__}, **changes})  # pyright: ignore[reportArgumentType]


# --- the manifest -------------------------------------------------------------------------------------------------


@pytest.mark.parametrize(
    ("system", "machine", "key"),
    [
        ("darwin", "arm64", "macos-aarch64"),
        ("darwin", "x86_64", "macos-x86_64"),
        ("linux", "x86_64", "linux-x86_64"),
        ("linux", "aarch64", "linux-aarch64"),
        ("win32", "AMD64", "windows-x86_64"),
        ("freebsd14", "amd64", None),
    ],
)
def test_a_system_is_named_as_the_release_names_its_files(system, machine, key):
    assert manifest.platform_key(system, machine) == key


def test_a_manifest_reads_back_as_it_was_written():
    written = release()
    assert manifest.parse(manifest.render(written)) == written


def test_a_signed_manifest_verifies_with_its_key():
    pem, public = key_pair()
    data = manifest.render(release())
    signature = manifest.sign(data, pem, "deneme")
    assert manifest.verify(data, signature, {"deneme": public}) == release()
    assert json.loads(signature)["key"] == "deneme"


def test_a_manifest_changed_after_signing_is_refused():
    pem, public = key_pair()
    data = manifest.render(release())
    signature = manifest.sign(data, pem, "deneme")
    changed = data.replace(b"1000", b"1001")
    with pytest.raises(ManifestError, match="imzası doğrulanamadı"):
        manifest.verify(changed, signature, {"deneme": public})


def test_a_manifest_signed_by_another_key_is_refused_even_under_a_known_name():
    pem, _ = key_pair()
    _, public = key_pair()
    data = manifest.render(release())
    with pytest.raises(ManifestError, match="imzası doğrulanamadı"):
        manifest.verify(data, manifest.sign(data, pem, "deneme"), {"deneme": public})


def test_a_manifest_signed_by_a_key_the_program_does_not_know_is_refused():
    pem, public = key_pair()
    data = manifest.render(release())
    with pytest.raises(ManifestError, match="tanımadığı"):
        manifest.verify(data, manifest.sign(data, pem, "baska"), {"deneme": public})


@pytest.mark.parametrize("signature", [b"", b"[]", b'{"key": "deneme"}', b'{"key": "deneme", "signature": "%%%"}'])
def test_a_signature_file_that_does_not_read_is_refused(signature):
    _, public = key_pair()
    with pytest.raises(ManifestError):
        manifest.verify(manifest.render(release()), signature, {"deneme": public})


def test_the_program_trusts_one_ed25519_key_of_32_bytes():
    assert list(keys.TRUSTED) == ["2026-11"]
    assert all(len(base64.b64decode(value, validate=True)) == 32 for value in keys.TRUSTED.values())


def test_a_secret_that_is_no_ed25519_key_cannot_sign():
    with pytest.raises(ManifestError):
        manifest.sign(b"{}", b"-----BEGIN PRIVATE KEY-----\nAAAA\n-----END PRIVATE KEY-----\n", "deneme")


def test_fields_a_newer_manifest_adds_are_left_alone():
    data = json.loads(manifest.render(release()))
    data["delta"] = {"from": "1.2.2"}
    assert manifest.parse(json.dumps(data).encode()).version == "1.2.3"


@pytest.mark.parametrize(
    ("change", "message"),
    [
        ({"product": "baska"}, "başka bir ürünün"),
        ({"format": 2}, "biçimi"),
        ({"tag": "v9.9.9"}, "etiketi"),
        ({"version": "1.2"}, "etiketi"),  # tag v1.2.3 no longer matches
        ({"version": "bir"}, "version"),
        ({"date": "11.11.2026"}, "date"),
        ({"notes": 5}, "notu"),
        ({"updates": {"amiga-68k": {"name": "x", "size": 1, "sha256": SHA}}}, "tanınmayan bir sistem"),
        ({"updates": {"linux-x86_64": {"name": "../x", "size": 1, "sha256": SHA}}}, "adı"),
        ({"updates": {"linux-x86_64": {"name": "x", "size": 0, "sha256": SHA}}}, "boyutu"),
        ({"updates": {"linux-x86_64": {"name": "x", "size": True, "sha256": SHA}}}, "boyutu"),
        ({"updates": {"linux-x86_64": {"name": "x", "size": 1, "sha256": "ABC"}}}, "özeti"),
        ({"extension": {"version": "0.8.0"}}, "extension"),
    ],
)
def test_a_field_with_a_wrong_value_refuses_the_whole_manifest(change, message):
    data = json.loads(manifest.render(release()))
    data.update(change)
    with pytest.raises(ManifestError, match=message):
        manifest.parse(json.dumps(data).encode())


@pytest.mark.parametrize("data", [b"\xff", b"[]", b"not json"])
def test_what_is_no_json_object_is_no_manifest(data):
    with pytest.raises(ManifestError):
        manifest.parse(data)


def test_the_releases_are_read_from_their_download_addresses():
    assert source.latest(source.MANIFEST, "sahip/depo") == (
        "/sahip/depo/releases/latest/download/iplikci-nedim-surum.json"
    )
    assert source.tagged("v1.2.3", "a b.zip", "sahip/depo") == "/sahip/depo/releases/download/v1.2.3/a%20b.zip"
    assert source.page("v1.2.3", "sahip/depo") == "https://github.com/sahip/depo/releases/tag/v1.2.3"
    assert source.page(repo="sahip/depo") == "https://github.com/sahip/depo/releases/latest"


@pytest.mark.parametrize(
    ("version", "than", "expected"),
    [("0.10.0", "0.9.16", True), ("0.9.16", "0.10.0", False), ("1.0", "1.0.0", False), ("bir", "0.1", False)],
)
def test_versions_compare_as_numbers(version, than, expected):
    assert versions.newer(version, than) is expected


# --- which installer put the program where --------------------------------------------------------------------


def fake_app(where: Path, version: str = "1.2.2", bundle: str = install.BUNDLE_ID, marker: str = "eski") -> Path:
    app = where / "İplikçi Nedim.app"
    python = app / "Contents" / "Resources" / "python" / "bin"
    python.mkdir(parents=True)
    (python / "python3").write_text(marker, encoding="utf-8")
    (app / "Contents" / "Info.plist").write_bytes(
        plistlib.dumps({"CFBundleIdentifier": bundle, "CFBundleShortVersionString": version})
    )
    return app


def test_the_mac_app_is_known_by_its_place_and_its_bundle(tmp_path):
    app = fake_app(tmp_path)
    python = app / "Contents" / "Resources" / "python" / "bin" / "python3"
    assert install.detect(python, "darwin") == Installation(Kind.MACOS_APP, app)
    assert install.detect(python, "darwin", development=True).kind is Kind.MANUAL
    other = fake_app(tmp_path / "baska", bundle="org.example.app")
    assert install.detect(other / "Contents/Resources/python/bin/python3", "darwin").kind is Kind.MANUAL


def test_a_linux_copy_is_known_by_its_place(tmp_path):
    python = tmp_path / ".local" / "lib" / "iplikci" / "1.2.2" / "bin" / "python3"
    assert install.detect(python, "linux") == Installation(Kind.LINUX_COPY, tmp_path / ".local" / "lib" / "iplikci")
    half = tmp_path / ".local" / "lib" / "iplikci" / "1.2.2.yeni.7" / "bin" / "python3"
    assert install.detect(half, "linux").kind is Kind.MANUAL


def test_the_windows_program_is_known_by_its_uninstaller(tmp_path):
    program = tmp_path / "Programs" / "İplikçi Nedim"
    (program / "python").mkdir(parents=True)
    pythonw = program / "python" / "pythonw.exe"
    assert install.detect(pythonw, "win32").kind is Kind.MANUAL  # no setup program put it there
    (program / "unins000.exe").write_bytes(b"MZ")
    assert install.detect(pythonw, "win32") == Installation(Kind.WINDOWS_SETUP, program)


def test_a_copy_installed_by_hand_is_only_told(tmp_path):
    uv_tool = tmp_path / ".local" / "share" / "uv" / "tools" / "iplikci-nedim" / "bin" / "python"
    for system in ("darwin", "linux", "win32"):
        found = install.detect(uv_tool, system)
        assert found.kind is Kind.MANUAL and not found.automatic


# --- macOS ----------------------------------------------------------------------------------------------------------


def unpacked(version: str, marker: str = "yeni", bundle: str = install.BUNDLE_ID) -> install.Unpack:
    """An unpack that leaves what a release's app archive holds."""

    def unpack(archive: Path, into: Path) -> None:
        assert archive.name == "arsiv.zip"
        fake_app(into, version, bundle, marker)

    return unpack


def says(version: str) -> install.Probe:
    return lambda python: version if python.read_text(encoding="utf-8") == "yeni" else "?"


def contents_marker(app: Path) -> str:
    return (app / "Contents/Resources/python/bin/python3").read_text(encoding="utf-8")


def test_a_new_mac_app_takes_the_place_of_the_contents_and_keeps_the_old_aside(tmp_path):
    app = fake_app(tmp_path)
    install.apply_macos(app, tmp_path / "arsiv.zip", "1.2.3", unpack=unpacked("1.2.3"), run=says("1.2.3"))
    assert contents_marker(app) == "yeni"
    assert (app / install.OLD / "Resources/python/bin/python3").read_text(encoding="utf-8") == "eski"
    assert not (app / install.STAGING).exists()
    assert install.leftovers(Installation(Kind.MACOS_APP, app)) == [app / install.OLD]


@pytest.mark.parametrize(
    ("unpack", "run", "message"),
    [
        (unpacked("1.2.4"), says("1.2.4"), "1.2.3 değil"),
        (unpacked("1.2.3", bundle="org.example.app"), says("1.2.3"), "1.2.3 değil"),
        (unpacked("1.2.3"), says("1.2.2"), "kendini 1.2.2 diye"),
    ],
)
def test_a_mac_app_that_is_not_the_version_promised_changes_nothing(tmp_path, unpack, run, message):
    app = fake_app(tmp_path)
    with pytest.raises(InstallError, match=message):
        install.apply_macos(app, tmp_path / "arsiv.zip", "1.2.3", unpack=unpack, run=run)
    assert contents_marker(app) == "eski"
    assert not (app / install.STAGING).exists() and not (app / install.OLD).exists()


def test_a_mac_app_the_user_cannot_write_is_not_touched(tmp_path):
    app = fake_app(tmp_path)
    (app / "Contents").chmod(0o500)
    try:
        if os.access(app / "Contents", os.W_OK):
            pytest.skip("this user writes everywhere (root)")
        with pytest.raises(InstallError, match="elle kurun"):
            install.apply_macos(app, tmp_path / "arsiv.zip", "1.2.3", unpack=unpacked("1.2.3"), run=says("1.2.3"))
    finally:
        (app / "Contents").chmod(0o700)
    assert contents_marker(app) == "eski"


def test_two_folders_trade_places(tmp_path):
    (tmp_path / "a").mkdir()
    (tmp_path / "a" / "dosya").write_text("a", encoding="utf-8")
    (tmp_path / "b").mkdir()
    (tmp_path / "b" / "dosya").write_text("b", encoding="utf-8")
    install.swap(tmp_path / "a", tmp_path / "b")
    assert (tmp_path / "a" / "dosya").read_text(encoding="utf-8") == "b"
    assert (tmp_path / "b" / "dosya").read_text(encoding="utf-8") == "a"
    assert sorted(p.name for p in tmp_path.iterdir()) == ["a", "b"]


@pytest.mark.skipif(sys.platform != "darwin", reason="ditto is macOS's")
def test_an_app_archived_by_ditto_unpacks_with_its_links(tmp_path):
    app = fake_app(tmp_path / "derleme", "1.2.3", marker="yeni")
    (app / "Contents/Resources/python/bin/python3.13").symlink_to("python3")
    archive = tmp_path / "arsiv.zip"
    subprocess.run(["/usr/bin/ditto", "-c", "-k", "--keepParent", str(app), str(archive)], check=True)
    installed = fake_app(tmp_path / "Uygulamalar")
    install.apply_macos(installed, archive, "1.2.3", run=says("1.2.3"))
    assert contents_marker(installed) == "yeni"
    assert (installed / "Contents/Resources/python/bin/python3.13").is_symlink()


# --- Linux ----------------------------------------------------------------------------------------------------------


def copy_archive(where: Path, marker: str = "yeni", extra: tarfile.TarInfo | None = None) -> Path:
    archive = where / "kopya.tar.gz"
    with tarfile.open(archive, "w:gz") as tar:
        for name, data in (("bin/python3.13", marker.encode()), ("lib/python3.13/os.py", b"")):
            info = tarfile.TarInfo(name)
            info.size, info.mode = len(data), 0o755
            tar.addfile(info, io.BytesIO(data))
        link = tarfile.TarInfo("bin/python3")
        link.type, link.linkname = tarfile.SYMTYPE, "python3.13"
        tar.addfile(link)
        if extra is not None:
            tar.addfile(extra, io.BytesIO(b"x" * extra.size))
    return archive


def test_a_new_linux_copy_is_unpacked_beside_the_others(tmp_path):
    copies = tmp_path / "lib" / "iplikci"
    (copies / "1.2.2" / "bin").mkdir(parents=True)
    python = install.apply_linux(copies, copy_archive(tmp_path), "1.2.3", run=says("1.2.3"))
    assert python == copies / "1.2.3" / "bin" / "python3"
    assert python.read_text(encoding="utf-8") == "yeni" and python.is_symlink()
    assert sorted(p.name for p in copies.iterdir()) == ["1.2.2", "1.2.3"]


def test_a_whole_linux_copy_of_the_version_already_there_is_kept(tmp_path):
    copies = tmp_path / "lib" / "iplikci"
    python = copies / "1.2.3" / "bin" / "python3"
    python.parent.mkdir(parents=True)
    python.write_text("yeni", encoding="utf-8")
    python.chmod(0o755)

    def no_unpack(archive: Path, into: Path) -> None:
        raise AssertionError("unpacked again")

    assert install.apply_linux(copies, tmp_path / "yok.tar.gz", "1.2.3", unpack=no_unpack, run=says("1.2.3")) == python


def test_a_linux_copy_that_does_not_say_its_version_leaves_nothing_behind(tmp_path):
    copies = tmp_path / "lib" / "iplikci"
    copies.mkdir(parents=True)
    with pytest.raises(InstallError, match="kendini"):
        install.apply_linux(copies, copy_archive(tmp_path, marker="bozuk"), "1.2.3", run=says("1.2.3"))
    assert list(copies.iterdir()) == []


def test_an_archive_reaching_outside_its_folder_is_refused(tmp_path):
    escape = tarfile.TarInfo("../disari")
    escape.size = 1
    copies = tmp_path / "lib" / "iplikci"
    copies.mkdir(parents=True)
    with pytest.raises(InstallError, match="açılamadı"):
        install.apply_linux(copies, copy_archive(tmp_path, extra=escape), "1.2.3", run=says("1.2.3"))
    assert not (tmp_path / "lib" / "disari").exists() and list(copies.iterdir()) == []


# --- Windows --------------------------------------------------------------------------------------------------------


def test_the_windows_setup_program_runs_without_a_window_and_keeps_a_log(tmp_path):
    command = install.windows_command(tmp_path / "kurulum.exe", tmp_path / "kurulum.log")
    assert command == [
        str(tmp_path / "kurulum.exe"),
        "/VERYSILENT",
        "/SUPPRESSMSGBOXES",
        "/NORESTART",
        "/SP-",
        f"/LOG={tmp_path / 'kurulum.log'}",
    ]


def test_only_a_mac_update_leaves_program_files_to_remove(tmp_path):
    assert install.leftovers(Installation(Kind.LINUX_COPY, tmp_path)) == []
    assert install.leftovers(install.MANUAL) == []
    app = fake_app(tmp_path)
    (app / install.STAGING).mkdir()
    assert install.leftovers(Installation(Kind.MACOS_APP, app)) == [app / install.STAGING]
    shutil.rmtree(app / install.STAGING)
    assert install.leftovers(Installation(Kind.MACOS_APP, app)) == []
