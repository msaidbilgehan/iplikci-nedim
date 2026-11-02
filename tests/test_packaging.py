"""The installers' own scripts (ADR-0017, packaging/build.py): the macOS app's executable and the Windows installer's
script. Nothing here builds a package; the app's executable runs against a stand-in for its Python."""

import importlib.util
import subprocess
import sys
from pathlib import Path
from types import ModuleType

import pytest

from iplikci.service import launcher

BUILD = Path(__file__).resolve().parents[1] / "packaging" / "build.py"
MARK = "com.apple.quarantine"


def build_script() -> ModuleType:
    spec = importlib.util.spec_from_file_location("iplikci_build", BUILD)
    assert spec is not None and spec.loader is not None
    found = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(found)
    return found


def test_the_mac_app_says_what_the_program_says_when_it_runs_from_where_it_cannot_stay():
    app = Path("/Volumes/İplikçi Nedim/İplikçi Nedim.app/Contents/Resources/python/bin/python3")
    assert build_script().MISPLACED == launcher.misplaced(app, "darwin")


def _marked(path: Path) -> bool:
    return subprocess.run(["xattr", "-p", MARK, str(path)], capture_output=True, check=False).returncode == 0


@pytest.mark.skipif(sys.platform != "darwin", reason="the download's quarantine mark is macOS's")
def test_the_mac_app_takes_the_download_mark_off_its_own_files_and_runs_its_python(tmp_path):
    app = tmp_path / "İplikçi Nedim.app"
    executable = app / "Contents" / "MacOS" / "iplikci-nedim"
    python = app / "Contents" / "Resources" / "python" / "bin" / "python3"
    library = app / "Contents" / "Resources" / "python" / "lib" / "libpython3.13.dylib"
    for path in (executable, python, library):
        path.parent.mkdir(parents=True, exist_ok=True)
    executable.write_text(build_script().mac_launcher(), encoding="utf-8")
    python.write_text('#!/bin/sh\necho "$@" > "$(dirname "$0")/calistirildi"\n', encoding="utf-8")  # a stand-in
    python.chmod(0o755)
    library.write_bytes(b"sahte kutuphane")
    for path in (python, library):  # as a browser leaves what it downloaded
        subprocess.run(["xattr", "-w", MARK, "0083;6720a000;Safari;", str(path)], check=True)
    beside = tmp_path / "baska-bir-dosya"
    beside.write_bytes(b"uygulamanin disinda")
    subprocess.run(["xattr", "-w", MARK, "0083;6720a000;Safari;", str(beside)], check=True)

    done = subprocess.run(["/bin/sh", str(executable)], capture_output=True, check=False, timeout=30)

    assert done.returncode == 0, done.stderr
    assert (python.parent / "calistirildi").read_text(encoding="utf-8").split() == [
        "-I", "-X", "utf8", "-m", "iplikci", "uygulama"
    ]  # fmt: skip
    assert not _marked(python) and not _marked(library)
    assert _marked(beside)  # only the app's own files


def test_a_windows_update_takes_the_service_off_and_replaces_the_whole_python():
    build = build_script()
    script = build.ISS.format(
        version="0.7.0",
        out="C:\\cikti",
        slug=build.SLUG,
        arch="x86_64",
        icon="C:\\simge.ico",
        source="C:\\kaynak",
        launch=" ".join(build.LAUNCH),
    )
    assert 'Type: filesandordirs; Name: "{app}\\python"' in script.split("[InstallDelete]")[1].split("[Files]")[0]
    assert "function PrepareToInstall(var NeedsRestart: Boolean): String;" in script
    assert "Exec(Python, '-I -X utf8 -m iplikci servis kaldir'" in script
    run = script[script.index("[Run]") : script.index("[UninstallRun]")]
    assert "postinstall" not in run and "-m iplikci uygulama" in run  # the app always opens and registers the service


def test_leaving_out_what_the_program_never_uses_keeps_the_standard_library_on_every_system(tmp_path):
    build = build_script()
    windows = tmp_path / "windows"  # python-build-standalone's Windows layout
    for name in (
        "Lib/threading.py",
        "Lib/tkinter/__init__.py",
        "Lib/site-packages/pip/__init__.py",
        "tcl/tk8.6/tk.tcl",
    ):
        (windows / name).parent.mkdir(parents=True, exist_ok=True)
        (windows / name).write_text("", encoding="utf-8")
    build.prune(windows)
    assert (windows / "Lib" / "threading.py").is_file()  # lib/thread* is Tcl's, never the standard library's
    assert not any((windows / name).exists() for name in ("Lib/tkinter", "Lib/site-packages/pip", "tcl"))
    unix = tmp_path / "unix"
    for name in ("lib/thread2.8.9/pkgIndex.tcl", "lib/python3.13/threading.py", "lib/python3.13/idlelib/run.py"):
        (unix / name).parent.mkdir(parents=True, exist_ok=True)
        (unix / name).write_text("", encoding="utf-8")
    build.prune(unix)
    assert (unix / "lib" / "python3.13" / "threading.py").is_file()
    assert not (unix / "lib" / "thread2.8.9").exists() and not (unix / "lib" / "python3.13" / "idlelib").exists()
