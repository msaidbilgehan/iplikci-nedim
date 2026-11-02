"""The installers' own scripts (ADR-0017, packaging/build.py): the macOS app's executable and the Windows installer's
script. Nothing here builds a package; the app's executable runs against a stand-in for its Python."""

import importlib.util
import shutil
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


@pytest.mark.parametrize(
    ("place", "lasts"),
    [
        ("/Applications/İplikçi Nedim.app", True),
        ("/Users/ayse/Applications/İplikçi Nedim.app", True),
        ("/Volumes/Harici Disk/Applications/İplikçi Nedim.app", True),
        ("/Volumes/Harici Disk/Users/ayse/Applications/İplikçi Nedim.app", True),
        ("/Volumes/İplikçi Nedim/İplikçi Nedim.app", False),  # the disk image
        ("/Volumes/Harici Disk/İndirilenler/İplikçi Nedim.app", False),
        ("/private/var/folders/xy/T/AppTranslocation/1234/d/İplikçi Nedim.app", False),
    ],
)
def test_the_mac_app_and_the_program_agree_on_where_the_app_lasts(place, lasts):
    text = build_script().mac_launcher()
    block = text[text.index('case "$app" in') : text.index("esac") + len("esac")]
    script = f'misplaced() {{ echo tasinmali; exit 1; }}\napp="$1"\n{block}\necho kalir\n'  # a stand-in for the window
    done = subprocess.run(["/bin/sh", "-c", script, "sh", place], capture_output=True, text=True, check=False)
    assert done.stdout.strip() == ("kalir" if lasts else "tasinmali")
    python = Path(place) / "Contents" / "Resources" / "python" / "bin" / "python3"
    assert (launcher.misplaced(python, "darwin") is None) == lasts


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


def appimage(tmp_path: Path) -> tuple[Path, dict[str, str]]:
    """The AppImage as it is mounted, on stand-ins: AppRun, the version and a Python that only says it ran; the
    desktop's window programs write down what they would show; a home of its own."""
    mount = tmp_path / "mount"
    python = mount / "python" / "bin" / "python3"
    python.parent.mkdir(parents=True)
    (mount / "python" / "lib").mkdir()
    (mount / "python" / "lib" / "os.py").write_text("# standart kütüphanenin yerine\n", encoding="utf-8")
    python.write_text('#!/bin/sh\necho "çalıştı: $0 $*"\n', encoding="utf-8")
    python.chmod(0o755)
    (mount / "VERSION").write_text("9.9.9", encoding="utf-8")
    script = mount / "AppRun"
    script.write_text(build_script().apprun(), encoding="utf-8")
    script.chmod(0o755)
    desktop = tmp_path / "masaustu"
    desktop.mkdir()
    for name in ("zenity", "kdialog", "notify-send"):
        (desktop / name).write_text(f'#!/bin/sh\nprintf "%s\\n" "$@" > "$(dirname "$0")/{name}.gosterdi"\n')
        (desktop / name).chmod(0o755)
    return script, {"PATH": f"{desktop}:/usr/bin:/bin", "HOME": str(tmp_path / "ev")}


def start(script: Path, env: dict[str, str]) -> subprocess.CompletedProcess[str]:
    return subprocess.run([str(script)], env=env, capture_output=True, text=True, check=False, timeout=60)


POSIX = pytest.mark.skipif(sys.platform == "win32", reason="AppRun is a shell script for Linux")


@POSIX
def test_the_appimage_copies_its_python_once_and_runs_the_program_from_the_copy(tmp_path):
    script, env = appimage(tmp_path)
    target = tmp_path / "ev" / ".local" / "lib" / "iplikci" / "9.9.9"
    for _ in range(2):  # the second start finds the copy whole
        done = start(script, env)
        assert done.returncode == 0, done.stderr
        assert done.stdout.strip() == f"çalıştı: {target}/bin/python3 -I -X utf8 -m iplikci uygulama"
    assert sorted(p.name for p in target.parent.iterdir()) == ["9.9.9"]  # no copy half made beside it


@POSIX
def test_a_version_folder_left_without_its_python_is_made_again_whole(tmp_path):
    script, env = appimage(tmp_path)
    target = tmp_path / "ev" / ".local" / "lib" / "iplikci" / "9.9.9"
    (target / "lib").mkdir(parents=True)  # a copy cut short, or partly removed
    for _ in range(2):  # it used to fail at every start from then on
        done = start(script, env)
        assert done.returncode == 0, done.stderr
    assert sorted(p.name for p in target.iterdir()) == ["bin", "lib"]
    assert sorted(p.name for p in target.parent.iterdir()) == ["9.9.9"]


@POSIX
def test_an_appimage_that_cannot_copy_its_python_says_so_in_the_desktops_window(tmp_path):
    script, env = appimage(tmp_path)
    shutil.rmtree(tmp_path / "mount" / "python")  # nothing to copy
    done = start(script, env)
    assert done.returncode == 1
    shown = (tmp_path / "masaustu" / "zenity.gosterdi").read_text(encoding="utf-8")
    assert "--error" in shown and "İplikçi Nedim açılamadı: çalışma ortamı" in shown
    assert not list((tmp_path / "ev" / ".local" / "lib" / "iplikci").iterdir())  # nothing half made stays


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


def test_the_portable_python_is_the_install_itself_never_the_link_uv_makes_to_it(tmp_path, monkeypatch):
    build = build_script()
    install = "cpython-3.13.18-windows-x86_64-none"
    link = "cpython-3.13-windows-x86_64-none"  # the minor version's name: a junction on Windows

    def uv(*args: object, cwd: Path | None = None) -> None:  # what `uv python install` leaves, as stand-ins
        installs = Path(str(args[list(args).index("--install-dir") + 1]))
        (installs / install / "Lib").mkdir(parents=True)
        (installs / install / "Lib" / "EXTERNALLY-MANAGED").write_text("", encoding="utf-8")
        (installs / link).mkdir()

    is_junction = Path.is_junction
    monkeypatch.setattr(build, "run", uv)
    monkeypatch.setattr(Path, "is_junction", lambda path: path.name == link or is_junction(path))
    root = build.standalone_python(tmp_path)
    assert root.name == install and not (root / "Lib" / "EXTERNALLY-MANAGED").exists()


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
