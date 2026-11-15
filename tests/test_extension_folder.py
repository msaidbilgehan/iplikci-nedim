"""The browser extension's folder (ADR-0016, K20): until the extension is in a store, the browser loads it unpacked
from the data folder's extension/, which the service makes when asked, shows in the file manager and keeps up with
the program. No test opens a window: the file manager is a stand-in."""

import json
import os
import re
from pathlib import Path

import pytest
from fastapi.testclient import TestClient

from iplikci.api.app import create_app
from iplikci.api.context import Context
from iplikci.app import extension
from iplikci.service import dialog, runner

SHOW_FOLDER = dialog.show_folder  # as the program has it; the tests' guard puts a refusal in its place
TOKEN = "deneme-belirteci"
BASE = "http://127.0.0.1:8643"
OWN_PAGE = {"Origin": BASE, "X-Iplikci": "1"}


def built_extension(root: Path, version: str = "0.4.0", script: str = "// arka plan") -> Path:
    """An extension as `npm run build` leaves it: a manifest, a script and an icon in a folder of its own."""
    (root / "icons").mkdir(parents=True, exist_ok=True)
    (root / extension.MANIFEST).write_text(json.dumps({"manifest_version": 3, "version": version}), encoding="utf-8")
    (root / "background.js").write_text(script, encoding="utf-8")
    (root / "icons" / "128.png").write_bytes(b"\x89PNG sahte")
    return root


@pytest.fixture
def carried(tmp_path, monkeypatch) -> Path:
    """The extension the installed program carries."""
    found = built_extension(tmp_path / "paketteki")
    monkeypatch.setattr(extension, "BUILT", found)
    return found


@pytest.fixture
def shown(monkeypatch) -> list[Path]:
    opened: list[Path] = []
    monkeypatch.setattr(dialog, "show_folder", lambda path: opened.append(path) or True)
    return opened


def test_the_folder_is_made_only_when_asked_and_holds_the_carried_extension(ws, carried, shown):
    assert extension.state(ws).folder is None and not ws.layout.extension.exists()
    found = extension.show(ws)
    assert (found.folder, found.version, found.opened, shown) == (ws.layout.extension, "0.4.0", True, [found.folder])
    assert (found.folder / "icons" / "128.png").read_bytes() == b"\x89PNG sahte"
    assert extension.state(ws) == extension.ExtensionState(
        True, "0.4.0", ws.layout.extension, True, extension.STORE_URL
    )


def test_only_the_user_can_read_the_copy(ws, carried, shown):
    folder = extension.prepare(ws)
    assert (folder.stat().st_mode & 0o777, (folder / "background.js").stat().st_mode & 0o777) == (0o700, 0o600)


def test_a_newer_program_brings_the_copy_up_to_date_at_the_start(ws, carried, tmp_path):
    folder = extension.prepare(ws)
    (folder / "old.js").write_text("// eski sürümün dosyası", encoding="utf-8")
    (folder / ".DS_Store").write_bytes(b"Finder'in kendi dosyasi")
    built_extension(carried, version="0.5.0", script="// yeni arka plan")
    assert extension.state(ws).current is False
    assert extension.refresh(ws) is True
    assert json.loads((folder / extension.MANIFEST).read_text(encoding="utf-8"))["version"] == "0.5.0"
    assert (folder / "background.js").read_text(encoding="utf-8") == "// yeni arka plan"
    assert not (folder / "old.js").exists() and (folder / ".DS_Store").exists()  # hidden files are not ours
    assert extension.refresh(ws) is False and extension.state(ws).current


def test_the_start_makes_no_folder_the_user_never_asked_for(ws, carried):
    assert extension.refresh(ws) is False and not ws.layout.extension.exists()


def test_a_copy_kept_busy_is_tried_again_at_the_next_start(ws, carried, monkeypatch):
    extension.prepare(ws)
    built_extension(carried, version="0.5.0")

    def busy(*args):
        raise PermissionError("the browser holds a file")

    monkeypatch.setattr(extension.os, "replace", busy)
    assert extension.refresh(ws) is False
    assert json.loads((ws.layout.extension / extension.MANIFEST).read_text(encoding="utf-8"))["version"] == "0.4.0"
    assert [p.name for p in ws.layout.extension.rglob(".yeni-*")] == []  # no half-written copy is left


def test_a_program_without_the_extension_says_so(ws):
    assert extension.state(ws) == extension.ExtensionState(False, "", None, False, extension.STORE_URL)
    with pytest.raises(extension.ExtensionError, match="eklentisini taşımıyor"):
        extension.prepare(ws)


def test_the_service_brings_the_folder_up_to_date_as_it_starts():
    source = Path(runner.__file__).read_text(encoding="utf-8")
    assert source.index("lifecycle.apply_pending_restore(ws)") < source.index("extension.refresh(ws)")


@pytest.mark.parametrize(
    ("platform", "which", "expected"),
    [
        ("darwin", None, ["open", "/klasor"]),
        ("win32", None, ["explorer", "/klasor"]),
        ("linux", "/usr/bin/xdg-open", ["xdg-open", "/klasor"]),
        ("linux", None, None),
        ("freebsd14", None, None),
    ],
)
def test_the_file_manager_of_each_system(platform, which, expected):
    assert dialog.folder_command(Path("/klasor"), platform, which=lambda name: which) == expected


def test_a_folder_that_cannot_be_shown_is_said(tmp_path):
    started: list[list[str]] = []

    def run(args):
        started.append(list(args))
        return 1

    assert SHOW_FOLDER(tmp_path, "darwin", run) is False and started == [["open", str(tmp_path)]]
    assert SHOW_FOLDER(tmp_path, "win32", run) is True  # Explorer answers 1 even when it opened the folder
    assert SHOW_FOLDER(tmp_path, "sunos5", run) is False and len(started) == 2


@pytest.fixture
def client(ws) -> TestClient:
    found = TestClient(create_app(Context(ws=ws, token=TOKEN)), base_url=BASE)
    url = found.post("/api/login-links", headers={"Authorization": f"Bearer {TOKEN}"}).json()["url"]
    assert found.get(url, follow_redirects=False).status_code == 303
    return found


def test_the_page_makes_the_folder_and_learns_where_it_is(client, ws, carried, shown):
    bearer = {"Authorization": f"Bearer {TOKEN}"}
    before = client.get("/api/extension", headers=bearer).json()
    assert before == {
        "available": True,
        "version": "0.4.0",
        "folder": "",
        "current": False,
        "store": extension.STORE_URL,
    }
    assert client.post("/api/extension/folder", headers=bearer).status_code == 403  # the token reads, never opens
    made = client.post("/api/extension/folder", headers=OWN_PAGE)
    assert made.json() == {"folder": str(ws.layout.extension), "version": "0.4.0", "opened": True}
    after = client.get("/api/extension", headers=bearer).json()
    assert (after["folder"], after["current"]) == (str(ws.layout.extension), True)


def test_without_the_extension_the_page_is_told_why(client):
    found = client.post("/api/extension/folder", headers=OWN_PAGE)
    assert (found.status_code, found.json()["code"]) == (409, "extension_unavailable")


def test_a_file_in_the_way_of_the_folder_is_said_and_nothing_breaks(client, ws, carried, shown):
    ws.layout.extension.parent.mkdir(parents=True, exist_ok=True)
    ws.layout.extension.write_text("bir dosya", encoding="utf-8")  # a file where the folder would go
    found = client.post("/api/extension/folder", headers=OWN_PAGE)
    assert (found.status_code, found.json()["code"]) == (409, "extension_folder_failed")
    assert found.json()["title"].startswith("Eklentinin klasörü hazırlanamadı") and shown == []
    assert client.get("/api/extension", headers={"Authorization": f"Bearer {TOKEN}"}).status_code == 200


@pytest.mark.skipif(os.name == "nt" or os.geteuid() == 0, reason="a file only its owner may read")
def test_a_file_the_service_cannot_read_never_stops_its_start(ws, carried, tmp_path, monkeypatch):
    folder = extension.prepare(ws)
    (folder / "background.js").chmod(0o000)  # in the copy: written over with the carried one
    newer = built_extension(tmp_path / "yeni", "0.5.0", "// yeni")
    monkeypatch.setattr(extension, "BUILT", newer)
    assert extension.refresh(ws) is True
    assert (folder / "background.js").read_text(encoding="utf-8") == "// yeni" and extension.state(ws).current
    (newer / "background.js").chmod(0o000)  # in what the program carries: tried again at the next start
    try:
        assert extension.refresh(ws) is False and extension.state(ws).current is False
    finally:
        (newer / "background.js").chmod(0o600)


def test_a_file_renamed_only_in_case_keeps_its_new_name(ws, carried, tmp_path, monkeypatch):
    folder = extension.prepare(ws)
    newer = built_extension(tmp_path / "yeni", "0.5.0")
    (newer / "background.js").rename(newer / "Background.js")
    monkeypatch.setattr(extension, "BUILT", newer)
    assert extension.refresh(ws) is True
    assert sorted(p.name for p in folder.iterdir() if p.is_file()) == ["Background.js", extension.MANIFEST]
    assert extension.state(ws).current and extension.refresh(ws) is False  # and it is not rewritten at every start


def test_the_store_page_is_shown_once_the_extension_is_published_there(client, carried, monkeypatch):
    bearer = {"Authorization": f"Bearer {TOKEN}"}
    page = "https://chromewebstore.google.com/detail/iplikci-nedim-koprusu/abcdefghijklmnopabcdefghijklmnop"
    monkeypatch.setattr(extension, "STORE_URL", page)
    assert client.get("/api/extension", headers=bearer).json()["store"] == page


def test_the_store_address_is_the_published_items_page():
    # The interface leads there first: a typo would send every new user to the store's "not found" page.
    assert re.fullmatch(r"https://chromewebstore\.google\.com/detail/[a-p]{32}", extension.STORE_URL)
    item = extension.STORE_URL.rsplit("/", 1)[1]
    store_notes = Path(__file__).resolve().parents[1] / "extension" / "store" / "README.md"
    assert item in store_notes.read_text(encoding="utf-8")


def test_the_store_summary_is_the_manifests_description_and_fits_the_store():
    # The store shows the manifest's description under the extension's name and in its search; it takes 132
    # characters at most, and the listing's notes must say the same words the package carries.
    repo = Path(__file__).resolve().parents[1]
    manifest = json.loads((repo / "extension" / "static" / "manifest.json").read_text(encoding="utf-8"))
    summary = manifest["description"]
    listing = " ".join((repo / "extension" / "store" / "listing.md").read_text(encoding="utf-8").split())
    assert len(summary) <= 132
    assert f'"{summary}"' in listing


def test_the_cursor_tells_the_extension_the_version_the_program_carries(carried, tmp_path):
    assert extension.carried_version() == "0.4.0"
    assert extension.carried_version(tmp_path / "yok") == ""
