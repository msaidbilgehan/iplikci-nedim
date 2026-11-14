"""The release workflow's own scripts (ADR-0022): the manifest, its signature and notes from the built files
(packaging/release.py), the installers under names without the version that the browser extension leads to
(ADR-0024), and the extension's new version to the Chrome Web Store (packaging/chrome_store.py), whose Google is a
fake here."""

import base64
import importlib.util
import json
import re
import zipfile
from pathlib import Path
from types import ModuleType

import pytest
import yaml
from cryptography.hazmat.primitives import hashes, serialization
from cryptography.hazmat.primitives.asymmetric import padding, rsa
from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PrivateKey

from iplikci.update import keys, manifest, source

PACKAGING = Path(__file__).resolve().parents[1] / "packaging"
EXTENSION_PROGRAM = PACKAGING.parent / "extension" / "src" / "bridge" / "program.ts"  # where the extension leads
WORKFLOW = PACKAGING.parent / ".github" / "workflows" / "packages.yml"
# The machines of GitHub's runners the Paketler workflow builds on (macos-latest is Apple Silicon since 2024).
RUNNERS = {"macos-latest": "macos-aarch64", "ubuntu-latest": "linux-x86_64", "windows-latest": "windows-x86_64"}


def script(name: str) -> ModuleType:
    spec = importlib.util.spec_from_file_location(f"iplikci_{name}", PACKAGING / f"{name}.py")
    assert spec is not None and spec.loader is not None
    found = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(found)
    return found


RELEASE = script("release")
STORE = script("chrome_store")

CHANGELOG = """# Değişiklik günlüğü

## [1.2.3] — 2026-11-11 — Güncellemeler

### Eklenenler

- Program kendini günceller.

## [1.2.2] — 2026-11-10 — Önceki

- Eski.
"""


@pytest.fixture
def root(tmp_path) -> Path:
    (tmp_path / "proje").mkdir()
    (tmp_path / "proje" / "pyproject.toml").write_text('[project]\nversion = "1.2.3"\n', encoding="utf-8")
    return tmp_path / "proje"


@pytest.fixture
def files(tmp_path) -> Path:
    folder = tmp_path / "surum"
    folder.mkdir()
    for name in (
        "iplikci-nedim-1.2.3-macos-aarch64.dmg",
        "iplikci-nedim-1.2.3-macos-aarch64.zip",
        "iplikci-nedim-1.2.3-linux-x86_64.AppImage",
        "iplikci-nedim-1.2.3-linux-x86_64.tar.gz",
        "iplikci-nedim-1.2.3-windows-x86_64.exe",
        "iplikci-kopru-0.8.0.zip",
    ):
        (folder / name).write_bytes(name.encode())
    return folder


@pytest.fixture
def signing(monkeypatch) -> str:
    key = Ed25519PrivateKey.generate()
    raw = key.public_key().public_bytes(serialization.Encoding.Raw, serialization.PublicFormat.Raw)
    monkeypatch.setattr(keys, "TRUSTED", {"deneme": base64.b64encode(raw).decode()})
    pem = key.private_bytes(serialization.Encoding.PEM, serialization.PrivateFormat.PKCS8, serialization.NoEncryption())
    return pem.decode()


def test_the_notes_are_the_changelogs_section_of_the_version():
    assert RELEASE.notes(CHANGELOG, "1.2.3") == "### Eklenenler\n\n- Program kendini günceller.\n"
    assert RELEASE.title(CHANGELOG, "1.2.3") == "İplikçi Nedim 1.2.3 — Güncellemeler"
    with pytest.raises(RELEASE.ReleaseError):
        RELEASE.notes(CHANGELOG, "9.9.9")


def test_the_release_names_every_file_and_is_signed_with_the_trusted_key(root, files, signing):
    release, signed = RELEASE.make("v1.2.3", files, CHANGELOG, {"UPDATE_SIGNING_KEY": signing}, "2026-11-11", root)
    assert signed
    found = manifest.verify((files / source.MANIFEST).read_bytes(), (files / source.SIGNATURE).read_bytes())
    assert found == release
    assert sorted(found.updates) == ["linux-x86_64", "macos-aarch64", "windows-x86_64"]
    assert found.updates["windows-x86_64"] == found.installers["windows-x86_64"]  # the setup program is both
    assert found.updates["linux-x86_64"].name.endswith(".tar.gz") and found.installers["linux-x86_64"].name.endswith(
        ".AppImage"
    )
    assert found.extension is not None and found.extension.version == "0.8.0"
    assert found.notes.startswith("### Eklenenler")


def test_the_release_is_dated_as_its_changelog_heading_says(root, files):
    # The workflow runs on UTC: a release tagged after midnight in Turkey would otherwise carry the day before.
    release, _ = RELEASE.make("v1.2.3", files, CHANGELOG, {}, None, root)
    assert release.date == "2026-11-11"
    assert RELEASE.changelog_day("## [1.2.4] — Başlıksız\n", "1.2.4") is None


def test_a_key_the_program_does_not_trust_never_signs_a_release(root, files, signing):
    other = Ed25519PrivateKey.generate().private_bytes(
        serialization.Encoding.PEM, serialization.PrivateFormat.PKCS8, serialization.NoEncryption()
    )
    with pytest.raises(RELEASE.ReleaseError, match="UPDATE_SIGNING_KEY yanlış"):
        RELEASE.make("v1.2.3", files, CHANGELOG, {"UPDATE_SIGNING_KEY": other.decode()}, "2026-11-11", root)
    assert not (files / source.SIGNATURE).exists()


def test_without_the_key_nothing_is_signed(root, files):
    _, signed = RELEASE.make("v1.2.3", files, CHANGELOG, {}, "2026-11-11", root)
    assert not signed and not (files / source.SIGNATURE).exists()


def test_a_tag_that_is_not_the_programs_version_is_refused(root, files):
    with pytest.raises(RELEASE.ReleaseError, match="etiket v1.2.4"):
        RELEASE.make("v1.2.4", files, CHANGELOG, {}, "2026-11-11", root)


def test_a_release_missing_a_systems_file_is_refused(root, files):
    (files / "iplikci-nedim-1.2.3-linux-x86_64.tar.gz").unlink()
    with pytest.raises(RELEASE.ReleaseError, match="linux"):
        RELEASE.make("v1.2.3", files, CHANGELOG, {}, "2026-11-11", root)
    (files / "iplikci-nedim-1.2.2-linux-x86_64.tar.gz").write_bytes(b"eski")
    with pytest.raises(RELEASE.ReleaseError, match="başka bir sürümün"):
        RELEASE.make("v1.2.3", files, CHANGELOG, {}, "2026-11-11", root)


def test_the_installers_go_by_names_without_the_version_and_the_update_files_as_the_copies_expect(root, files, signing):
    release, _ = RELEASE.make("v1.2.3", files, CHANGELOG, {"UPDATE_SIGNING_KEY": signing}, "2026-11-11", root)
    assert {key: found.name for key, found in release.installers.items()} == {
        "macos-aarch64": "iplikci-nedim-macos-aarch64.dmg",
        "linux-x86_64": "iplikci-nedim-linux-x86_64.AppImage",
        "windows-x86_64": "iplikci-nedim-windows-x86_64.exe",
    }
    assert {key: found.name for key, found in release.updates.items()} == {
        "macos-aarch64": "iplikci-nedim-1.2.3-macos-aarch64.zip",
        "linux-x86_64": "iplikci-nedim-1.2.3-linux-x86_64.tar.gz",
        "windows-x86_64": "iplikci-nedim-windows-x86_64.exe",  # the setup program is the update file too
    }
    # The folder the workflow uploads whole: each file the manifest names, as big and with the digest it says.
    assert sorted(path.name for path in files.iterdir()) == [
        "iplikci-kopru-0.8.0.zip",
        "iplikci-nedim-1.2.3-linux-x86_64.tar.gz",
        "iplikci-nedim-1.2.3-macos-aarch64.zip",
        "iplikci-nedim-linux-x86_64.AppImage",
        "iplikci-nedim-macos-aarch64.dmg",
        source.MANIFEST,
        source.SIGNATURE,
        "iplikci-nedim-windows-x86_64.exe",
    ]
    for found in [*release.updates.values(), *release.installers.values()]:
        assert RELEASE.entry(files / found.name) == found
    assert (files / "iplikci-nedim-macos-aarch64.dmg").read_bytes() == b"iplikci-nedim-1.2.3-macos-aarch64.dmg"
    # An installed copy fetches its update file from the release with its tag, whatever the name.
    assert source.tagged("v1.2.3", release.updates["windows-x86_64"].name).endswith(
        "/releases/download/v1.2.3/iplikci-nedim-windows-x86_64.exe"
    )


def test_a_release_without_an_installer_the_extension_offers_is_refused(root, files):
    (files / "iplikci-nedim-1.2.3-macos-aarch64.dmg").unlink()
    with pytest.raises(RELEASE.ReleaseError, match="macos-aarch64 kurulum paketi"):
        RELEASE.make("v1.2.3", files, CHANGELOG, {}, "2026-11-11", root)
    assert (files / "iplikci-nedim-1.2.3-linux-x86_64.AppImage").exists()  # nothing renamed before it was refused


def test_the_extension_leads_to_the_releases_the_program_updates_from():
    text = EXTENSION_PROGRAM.read_text(encoding="utf-8")
    assert re.findall(r'export const REPO = "([^"]+)";', text) == [source.REPO]


def test_the_extension_offers_each_installer_under_the_name_every_release_gives_it():
    offered = set(re.findall(r'"(iplikci-nedim-[A-Za-z0-9._-]+)"', EXTENSION_PROGRAM.read_text(encoding="utf-8")))
    assert offered == {RELEASE.stable_name(key) for key in RELEASE.OFFERED}


def test_the_installers_offered_are_those_the_release_workflow_builds():
    runners = yaml.safe_load(WORKFLOW.read_text(encoding="utf-8"))["jobs"]["paket"]["strategy"]["matrix"]["os"]
    assert sorted(RUNNERS[runner] for runner in runners) == sorted(RELEASE.OFFERED)


# --- the Chrome Web Store ---------------------------------------------------------------------------------------------


def service_account() -> tuple[dict[str, str], rsa.RSAPublicKey]:
    key = rsa.generate_private_key(public_exponent=65537, key_size=2048)
    pem = key.private_bytes(serialization.Encoding.PEM, serialization.PrivateFormat.PKCS8, serialization.NoEncryption())
    account = {
        "client_email": "yayinci@proje.iam.gserviceaccount.com",
        "private_key": pem.decode(),
        "private_key_id": "k1",
    }
    return account, key.public_key()


def package(tmp_path: Path, version: str) -> Path:
    path = tmp_path / f"iplikci-kopru-{version}.zip"
    with zipfile.ZipFile(path, "w") as archive:
        archive.writestr("manifest.json", json.dumps({"manifest_version": 3, "version": version}))
    return path


def test_the_service_account_signs_its_claim_for_the_store_alone():
    account, public = service_account()
    token = STORE.assertion(account, 1_000_000)
    header, claims, signature = token.split(".")

    def decoded(part: str) -> dict:
        return json.loads(base64.urlsafe_b64decode(part + "=" * (-len(part) % 4)))

    assert decoded(header) == {"alg": "RS256", "typ": "JWT", "kid": "k1"}
    assert decoded(claims) == {
        "iss": "yayinci@proje.iam.gserviceaccount.com",
        "scope": "https://www.googleapis.com/auth/chromewebstore",
        "aud": "https://oauth2.googleapis.com/token",
        "iat": 1_000_000,
        "exp": 1_003_600,
    }
    raw = base64.urlsafe_b64decode(signature + "=" * (-len(signature) % 4))
    public.verify(raw, f"{header}.{claims}".encode(), padding.PKCS1v15(), hashes.SHA256())


class FakeGoogle:
    """Google's token server and the store's API, by address; every request kept."""

    def __init__(self, published: str = "0.7.0", upload_states: tuple[str, ...] = ("SUCCEEDED",)) -> None:
        self.published = published
        self.states = list(upload_states)
        self.uploaded = False
        self.asked: list[tuple[str, str]] = []

    def __call__(self, request) -> tuple[int, bytes]:
        url = request.full_url
        self.asked.append((request.get_method(), url))
        if url == STORE.TOKEN_URL:
            return 200, json.dumps({"access_token": "belirtec", "expires_in": 3600}).encode()
        assert request.get_header("Authorization") == "Bearer belirtec"
        if url.endswith(":fetchStatus"):
            status = {"publishedItemRevisionStatus": {"distributionChannels": [{"crxVersion": self.published}]}}
            if self.uploaded:
                status["lastAsyncUploadState"] = self.states.pop(0)
            return 200, json.dumps(status).encode()
        if url.endswith(":upload"):
            self.uploaded = True
            return 200, json.dumps({"uploadState": self.states.pop(0), "crxVersion": "0.8.0"}).encode()
        if url.endswith(":publish"):
            return 200, json.dumps({"state": "PENDING_REVIEW"}).encode()
        return 404, b"{}"


def store(google: FakeGoogle) -> object:
    account, _ = service_account()
    return STORE.Store(STORE.Settings("yayinci", "a" * 32, account), google, clock=lambda: 1_000_000)


def test_a_newer_version_is_uploaded_and_sent_for_review(tmp_path):
    google = FakeGoogle()
    said = STORE.release(store(google), package(tmp_path, "0.8.0"), sleep=lambda s: None)
    assert said == "0.8.0 yüklendi ve incelemeye gönderildi (PENDING_REVIEW)"
    paths = [url.split("/items/")[-1] if "/items/" in url else url for _, url in google.asked]
    assert paths == [STORE.TOKEN_URL, "a" * 32 + ":fetchStatus", "a" * 32 + ":upload", "a" * 32 + ":publish"]
    assert ("POST", f"{STORE.UPLOAD}/v2/publishers/yayinci/items/{'a' * 32}:upload") in google.asked


def test_a_version_the_store_has_already_is_not_uploaded(tmp_path):
    google = FakeGoogle(published="0.8.0")
    assert "yeni değil" in STORE.release(store(google), package(tmp_path, "0.8.0"))
    assert not any(url.endswith(":upload") for _, url in google.asked)


def test_an_upload_still_under_way_is_waited_for(tmp_path):
    google = FakeGoogle(upload_states=("IN_PROGRESS", "IN_PROGRESS", "SUCCEEDED"))
    waited: list[float] = []
    said = STORE.release(store(google), package(tmp_path, "0.8.0"), sleep=waited.append)
    assert said.startswith("0.8.0 yüklendi") and len(waited) == 2


def test_a_failed_upload_is_never_published(tmp_path):
    google = FakeGoogle(upload_states=("FAILED",))
    with pytest.raises(STORE.StoreError, match="yüklenemedi"):
        STORE.release(store(google), package(tmp_path, "0.8.0"), sleep=lambda s: None)
    assert not any(url.endswith(":publish") for _, url in google.asked)


def test_a_dry_run_sends_nothing(tmp_path):
    google = FakeGoogle()
    assert (
        STORE.release(store(google), package(tmp_path, "0.8.0"), dry_run=True) == "0.8.0 yüklenecekti (mağazada: 0.7.0)"
    )
    assert not any(url.endswith((":upload", ":publish")) for _, url in google.asked)


def test_the_stores_settings_must_all_be_there():
    with pytest.raises(STORE.StoreError, match="CWS_ITEM_ID, CWS_SERVICE_ACCOUNT_KEY"):
        STORE.settings_from({"CWS_PUBLISHER_ID": "yayinci"})
    with pytest.raises(STORE.StoreError, match="servis hesabının anahtarı değil"):
        STORE.settings_from({"CWS_PUBLISHER_ID": "y", "CWS_ITEM_ID": "a", "CWS_SERVICE_ACCOUNT_KEY": "{}"})


def test_the_stores_versions_are_the_published_and_the_one_under_review():
    status = {
        "publishedItemRevisionStatus": {"distributionChannels": [{"crxVersion": "0.7.0", "deployPercentage": 100}]},
        "submittedItemRevisionStatus": {"distributionChannels": [{"crxVersion": "0.8.0"}]},
    }
    assert STORE.store_versions(status) == ["0.7.0", "0.8.0"]
    assert STORE.store_versions({}) == []
