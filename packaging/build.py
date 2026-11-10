"""Build this system's installer (ADR-0017, "Paketleme biçimi"): a portable CPython (python-build-standalone, as uv
installs it and checks it), İplikçi Nedim and its locked dependencies installed into it, and a launcher that runs
`python -I -X utf8 -m iplikci uygulama`. Nothing is frozen: the reading and viewer processes and the service run
exactly as an installed copy runs them.

    uv run python packaging/build.py        # into dist/paket/

- macOS: "İplikçi Nedim.app" (ad-hoc signed, not notarized: K22) in a disk image, and the app archived by ditto as
  the update file the installed program unpacks (ADR-0022).
- Linux: an AppImage (appimagetool on the PATH or in APPIMAGETOOL), and its Python folder as a .tar.gz, the update file.
- Windows: the program's folder and an Inno Setup script, compiled into a setup program when ISCC is found; the setup
  program is also the update file, run without a window.

Before anything is packaged, the installed program starts the service on an empty data folder and must answer with
its version; each update file is then unpacked as the installed program would unpack it and its Python must say the
version too. An update that cannot start is never made.

The web interface must be built first (`npm run build` in web/). This is a development tool: it runs uv, the
system's packaging tools and, for the interpreter, uv's download; it never touches the data folder."""

import argparse
import io
import json
import os
import platform
import plistlib
import posixpath
import re
import secrets
import shutil
import socket
import subprocess
import sys
import tarfile
import tempfile
import time
import tomllib
import urllib.error
import urllib.request
from pathlib import Path
from typing import Any

from iplikci.update import install as updater

ROOT = Path(__file__).resolve().parents[1]
ASSETS = ROOT / "packaging" / "assets"
UI = ROOT / "src" / "iplikci" / "api" / "ui" / "index.html"
EXTENSION = ROOT / "src" / "iplikci" / "browser_extension"  # written by `npm run build` in extension/
NAME = "İplikçi Nedim"
SLUG = "iplikci-nedim"
BUNDLE_ID = "com.iplikci.app"
LAUNCH = ("-I", "-X", "utf8", "-m", "iplikci", "uygulama")
QUIET = "--sessiz"  # the app opened at the end of a silent update: the service registered, no browser (ADR-0022)
SMOKE_SECONDS = 120.0  # how long the installed program may take to start the service and answer
INSTALLED = (  # what the installed program must import; its last line is where it carries the extension
    "import iplikci.api.app, iplikci.parsers.registry; from iplikci.app import extension; "
    "print('iplikci', iplikci.__version__); print(extension.BUILT)"
)
_PAGE_REFERENCE = re.compile(r'(?:src|href)="([^"]+)"')


def run(*args: str | Path, cwd: Path = ROOT) -> None:
    print("+", " ".join(str(a) for a in args), flush=True)
    subprocess.run([str(a) for a in args], cwd=cwd, check=True)


def output(*args: str | Path) -> str:
    """What a command prints, shown as it is kept."""
    print("+", " ".join(str(a) for a in args), flush=True)
    done = subprocess.run([str(a) for a in args], cwd=ROOT, check=True, capture_output=True, text=True)
    print(done.stdout, end="", flush=True)
    return done.stdout


def version() -> str:
    with (ROOT / "pyproject.toml").open("rb") as f:
        return str(tomllib.load(f)["project"]["version"])


def arch() -> str:
    machine = platform.machine().lower()
    return {"amd64": "x86_64", "arm64": "aarch64"}.get(machine, machine)


def interpreter(root: Path) -> Path:
    """The Python of a standalone install: python.exe on Windows, bin/python3 elsewhere."""
    return root / "python.exe" if sys.platform == "win32" else root / "bin" / "python3"


def standalone_python(work: Path) -> Path:
    """A portable CPython of the version .python-version pins, the folder it lives in. It is ours alone, so the
    marker that keeps package installers out of a system's Python goes."""
    pinned = (ROOT / ".python-version").read_text(encoding="utf-8").strip()
    installs = work / "pythons"
    run("uv", "python", "install", pinned, "--install-dir", installs, "--no-bin")
    # uv also links the minor version's name to the install, with a junction on Windows: the folder itself is the one
    # that is no link.
    [root] = [
        p
        for p in installs.iterdir()
        if p.is_dir() and not p.is_symlink() and not p.is_junction() and p.name.startswith("cpython-")
    ]
    for marker in root.rglob("EXTERNALLY-MANAGED"):
        marker.unlink()
    return root


# What the program never uses and the package need not carry: the package installer, test suites, the Tk GUI toolkit,
# IDLE and the C headers.
PRUNED = (
    "include",
    "share",
    "lib/tcl*",
    "lib/tk*",
    "lib/itcl*",
    "lib/thread*",
    "lib/libtcl*",
    "lib/libtk*",
    "lib/python3.*/ensurepip",
    "lib/python3.*/idlelib",
    "lib/python3.*/tkinter",
    "lib/python3.*/turtledemo",
    "lib/python3.*/test",
    "lib/python3.*/site-packages/pip",
    "lib/python3.*/site-packages/pip-*",
    "lib/python3.*/site-packages/PyObjCTest",
    "Lib/ensurepip",
    "Lib/idlelib",
    "Lib/tkinter",
    "Lib/turtledemo",
    "Lib/test",
    "Lib/site-packages/pip",
    "Lib/site-packages/pip-*",
    "tcl",
)


def prune(root: Path) -> None:
    """Leave out what PRUNED names, its letters' case kept: on Windows a pattern would otherwise match without it,
    and lib/thread* (Tcl's thread package) would take Lib/threading.py."""
    for pattern in PRUNED:
        for found in root.glob(pattern, case_sensitive=True):
            if found.is_dir() and not found.is_symlink():
                shutil.rmtree(found)
            else:
                found.unlink()


def install_program(python: Path, work: Path) -> None:
    """The locked dependencies with their hashes, then the program's wheel, the built interface and the built browser
    extension inside it (K20: the service hands the extension to the browser), checked file by file before the
    build and again in the installed copy: the service copies the extension into the data folder as it finds it."""
    if not UI.is_file():
        sys.exit(f"Arayüz derlenmemiş ({UI} yok): önce web/ klasöründe npm ci && npm run build")
    missing = missing_extension_files(EXTENSION)
    if missing:
        sys.exit(
            f"Eklenti derlenmemiş ya da yarım ({EXTENSION}: {', '.join(missing)} yok): önce extension/ klasöründe "
            "npm ci && npm run build"
        )
    wheels = work / "wheel"
    run("uv", "build", "--wheel", "--out-dir", wheels)
    requirements = work / "requirements.txt"
    export = ("uv", "export", "--quiet", "--frozen", "--no-dev", "--no-emit-project", "--format", "requirements-txt")
    run(*export, "-o", requirements)
    run("uv", "pip", "install", "--python", python, "--require-hashes", "--compile-bytecode", "-r", requirements)
    [wheel] = wheels.glob("*.whl")
    run("uv", "pip", "install", "--python", python, "--no-deps", "--compile-bytecode", wheel)
    carried = Path(output(python, "-I", "-c", INSTALLED).splitlines()[-1])
    missing = missing_extension_files(carried)
    if missing:
        sys.exit(f"Kurulan program eklentiyi eksik taşıyor ({carried}: {', '.join(missing)} yok)")


def missing_extension_files(root: Path) -> list[str]:
    """What the built extension at root lacks of extension_files(); all of it when it has no manifest."""
    if not (root / "manifest.json").is_file():
        return ["manifest.json"]
    return [name for name in extension_files(root) if not (root / name).is_file()]


def extension_files(root: Path) -> list[str]:
    """What a built extension must hold: its manifest, every file the manifest names, and every file its pages load
    or link to, each page's own references followed in turn."""
    wanted = {"manifest.json", *_named_in(json.loads((root / "manifest.json").read_text(encoding="utf-8")))}
    pages = sorted(name for name in wanted if name.endswith(".html"))
    while pages:
        page = pages.pop()
        if not (root / page).is_file():
            continue
        for reference in _PAGE_REFERENCE.findall((root / page).read_text(encoding="utf-8")):
            target = reference.split("#")[0].split("?")[0]
            if not target or ":" in target:  # a part of the page, another site
                continue
            beside = posixpath.dirname(page)
            name = posixpath.normpath(target.lstrip("/") if target.startswith("/") else posixpath.join(beside, target))
            if name not in wanted:
                wanted.add(name)
                if name.endswith(".html"):
                    pages.append(name)
    return sorted(wanted)


def _named_in(manifest: dict[str, Any]) -> set[str]:
    """The files a Manifest V3 manifest names: the service worker, the pages, the icons, the content scripts and the
    resources the pages may load (patterns left out)."""
    found: list[Any] = []

    def section(key: str) -> dict[str, Any]:
        value = manifest.get(key)
        return value if isinstance(value, dict) else {}

    found += [section("background").get("service_worker"), section("options_ui").get("page")]
    found += [manifest.get("options_page"), manifest.get("devtools_page"), section("action").get("default_popup")]
    for icons in (section("icons"), section("action").get("default_icon")):
        found += list(icons.values()) if isinstance(icons, dict) else [icons]
    for script in manifest.get("content_scripts") or []:
        found += [*(script.get("js") or []), *(script.get("css") or [])] if isinstance(script, dict) else []
    for entry in manifest.get("web_accessible_resources") or []:
        found += list(entry.get("resources") or []) if isinstance(entry, dict) else []
    return {
        posixpath.normpath(name.lstrip("/")) for name in found if isinstance(name, str) and name and "*" not in name
    }


def free_port() -> int:
    with socket.socket() as s:
        s.bind(("127.0.0.1", 0))
        return int(s.getsockname()[1])


SMOKE_SETTINGS = """[server]
port = {port}

[notify]
channels = []

[fx]
providers = ["document"]

[updates]
mode = "off"
"""


def smoke(python: Path, work: Path) -> None:
    """The installed program starts the service on an empty data folder of its own and answers with its version
    (ADR-0022: an update that cannot start is never published). Nothing leaves the computer: no channel, no rate
    provider, no update check, a made-up API token instead of the keychain's."""
    home = work / "deneme-veri"
    home.mkdir()
    port = free_port()
    (home / "settings.toml").write_text(SMOKE_SETTINGS.format(port=port), encoding="utf-8")
    env = {**os.environ, "IPLIKCI_HOME": str(home), "IPLIKCI_API_TOKEN": secrets.token_urlsafe(24)}
    command = [str(python), "-I", "-X", "utf8", "-m", "iplikci", "servis", "calistir", "--ev", str(home)]
    print("+", " ".join(command), flush=True)
    log = (work / "deneme-servis.log").open("wb")
    service = subprocess.Popen(command, env=env, stdout=log, stderr=subprocess.STDOUT)
    try:
        deadline = time.monotonic() + SMOKE_SECONDS
        while not _answers(port):
            if service.poll() is not None or time.monotonic() > deadline:
                sys.exit(f"Kurulan program servisi başlatamadı:\n{_tail(work / 'deneme-servis.log')}")
            time.sleep(0.5)
        holder = json.loads((home / "run" / "servis.json").read_text(encoding="utf-8"))
        if holder.get("version") != version():
            sys.exit(f"Kurulan programın servisi {holder.get('version')!r} sürümü, {version()} değil")
        print(f"Servis {version()} açıldı ve yanıt verdi (port {port})", flush=True)
    finally:
        service.terminate()
        try:
            service.wait(timeout=30)
        except subprocess.TimeoutExpired:
            service.kill()
            service.wait(timeout=30)
        log.close()


def _answers(port: int) -> bool:
    try:
        with urllib.request.urlopen(f"http://127.0.0.1:{port}/healthz", timeout=2) as answer:
            return answer.status == 200
    except (urllib.error.URLError, OSError):
        return False


def _tail(path: Path, lines: int = 40) -> str:
    try:
        return "\n".join(path.read_text(encoding="utf-8", errors="replace").splitlines()[-lines:])
    except OSError:
        return ""


def check_update_file(unpack: updater.Unpack, archive: Path, python_inside: str, work: Path) -> None:
    """The update file unpacks as the installed program unpacks it (update.install), and its Python says this
    version."""
    into = work / "guncelleme-denemesi"
    shutil.rmtree(into, ignore_errors=True)
    into.mkdir()
    unpack(archive, into)
    said = updater.probe(into / python_inside)
    if said != version():
        sys.exit(f"Güncelleme dosyasındaki program {said!r} sürümü, {version()} değil: {archive.name}")
    print(f"Güncelleme dosyası açıldı ve {said} sürümünü söyledi: {archive.name}", flush=True)
    shutil.rmtree(into, ignore_errors=True)


MISPLACED = (  # as service/launcher.misplaced says it, for an app that cannot run its Python from where it is
    "İplikçi Nedim'i önce Uygulamalar klasörüne taşıyın, sonra oradan açın. Disk görüntüsünden ya da indirildiği "
    "yerden açılan uygulama her açılışta başka bir yerde çalışır; arka plan servisi onu bulamaz."
)
MAC_LAUNCHER = """#!/bin/sh
# Opens İplikçi Nedim: the Python inside the app runs the program isolated, in UTF-8 (ADR-0017).
app="$(cd "$(dirname "$0")/../.." && pwd -P)"
misplaced() {{
    # A disk image's place, or the random one macOS runs a downloaded app from, goes away: said before the Python runs,
    # which macOS would refuse there while it keeps the download's mark.
    /usr/bin/osascript -e 'on run argv' \\
        -e 'display dialog (item 1 of argv) with title "İplikçi Nedim" buttons {{"Tamam"}} default button 1' \\
        -e 'end run' "{misplaced}" >/dev/null 2>&1
    exit 1
}}
# The patterns service/launcher.misplaced tells the same with.
case "$app" in
*/AppTranslocation/*) misplaced ;;
/Volumes/*/Applications/*) ;; # an Applications folder on another disk lasts as /Applications does
/Volumes/*) misplaced ;;
esac
# Unsigned (K22): macOS asks the user once whether to open the app. What the app carries, its Python and libraries,
# would be refused file by file while they keep the download's quarantine mark; the user has just opened the app, so
# the mark goes from the app's own files.
python="$app/Contents/Resources/python/bin/python3"
if /usr/bin/xattr -p com.apple.quarantine "$python" >/dev/null 2>&1; then
    /usr/bin/xattr -dr com.apple.quarantine "$app" 2>/dev/null
fi
exec "$python" {launch}
"""


def mac_launcher() -> str:
    """The app's own executable: it runs the Python inside the app (Contents/Resources/python)."""
    return MAC_LAUNCHER.format(misplaced=MISPLACED, launch=" ".join(LAUNCH))


def macos(python_root: Path, out: Path, work: Path) -> Path:
    app = work / f"{NAME}.app"
    contents = app / "Contents"
    (contents / "MacOS").mkdir(parents=True)
    resources = contents / "Resources"
    shutil.copytree(python_root, resources / "python", symlinks=True)
    shutil.copy2(ASSETS / "iplikci.icns", resources / "iplikci.icns")
    launcher = contents / "MacOS" / SLUG
    launcher.write_text(mac_launcher(), encoding="utf-8")
    launcher.chmod(0o755)
    (contents / "Info.plist").write_bytes(
        plistlib.dumps(
            {
                "CFBundleName": NAME,
                "CFBundleDisplayName": NAME,
                "CFBundleIdentifier": BUNDLE_ID,
                "CFBundleExecutable": SLUG,
                "CFBundleIconFile": "iplikci.icns",
                "CFBundlePackageType": "APPL",
                "CFBundleShortVersionString": version(),
                "CFBundleVersion": version(),
                "LSMinimumSystemVersion": "12.0",
                "NSHighResolutionCapable": True,
            }
        )
    )
    run("codesign", "--force", "--deep", "--sign", "-", app)  # ad-hoc: no Apple account, nothing notarized (K22)
    update = out / f"{SLUG}-{version()}-macos-{arch()}.zip"  # the update file: the app with its attributes (ADR-0022)
    update.unlink(missing_ok=True)
    run("ditto", "-c", "-k", "--sequesterRsrc", "--keepParent", app, update)
    check_update_file(updater.unpack_app, update, f"{app.name}/Contents/Resources/python/bin/python3", work)
    staging = work / "dmg"
    staging.mkdir()
    shutil.move(app, staging / app.name)
    (staging / "Applications").symlink_to("/Applications")
    image = out / f"{SLUG}-{version()}-macos-{arch()}.dmg"
    image.unlink(missing_ok=True)
    run("hdiutil", "create", "-volname", NAME, "-srcfolder", staging, "-format", "UDZO", "-ov", image)
    return image


APPRUN = """#!/bin/sh
# İplikçi Nedim as an AppImage (ADR-0017). The AppImage is mounted somewhere new at every start, and the service
# starts the Python it was registered with at every login: the Python is copied once per version to a place that
# lasts, outside the data folder (ADR-0002), and the program runs from there. A problem is said in the desktop's own
# window, as service/dialog.py says it.
say() {
    if command -v zenity >/dev/null 2>&1; then
        zenity --error --title="İplikçi Nedim" --no-markup --text="$1"
    elif command -v kdialog >/dev/null 2>&1; then
        kdialog --title "İplikçi Nedim" --error "$1"
    elif command -v notify-send >/dev/null 2>&1; then
        notify-send --urgency=critical "İplikçi Nedim" "$1"
    else
        echo "$1" >&2
    fi
}
here="$(dirname "$(readlink -f "$0")")"
version="$(cat "$here/VERSION" 2>/dev/null)"
if [ -z "$version" ]; then
    say "İplikçi Nedim açılamadı: indirilen paket bozuk. Paketi yeniden indirip açın."
    exit 1
fi
copies="$HOME/.local/lib/iplikci"
# The program updates itself into a copy of a newer version beside this one (ADR-0022): this AppImage, kept where the
# user opens it from, then runs the newest whole copy rather than copying an older Python again.
newest="$(ls -1 "$copies" 2>/dev/null | grep -E '^[0-9]+(\\.[0-9]+)*$' | sort -t. -k1,1n -k2,2n -k3,3n -k4,4n | tail -n 1)"
if [ -n "$newest" ] && [ "$newest" != "$version" ] && [ -x "$copies/$newest/bin/python3" ]; then
    highest="$(printf '%s\\n%s\\n' "$newest" "$version" | sort -t. -k1,1n -k2,2n -k3,3n -k4,4n | tail -n 1)"
    if [ "$highest" = "$newest" ]; then
        exec "$copies/$newest/bin/python3" LAUNCH
    fi
fi
target="$copies/$version"
if [ ! -x "$target/bin/python3" ]; then
    rm -rf "$target"  # a copy without its Python (cut short, or partly removed) is made again whole
    temp="$target.yeni.$$"  # this start's own: a start beside it copies into a folder of its own
    if mkdir -p "$temp" && cp -a "$here/python/." "$temp/"; then
        if [ -x "$target/bin/python3" ]; then
            rm -rf "$temp"  # a start beside this one was done first
        else
            rm -rf "$target" && mv "$temp" "$target"
        fi
    fi
    rm -rf "$temp"
fi
if [ ! -x "$target/bin/python3" ]; then
    say "İplikçi Nedim açılamadı: çalışma ortamı $target klasörüne kopyalanamadı. Diskte yer açıp yeniden deneyin."
    exit 1
fi
exec "$target/bin/python3" LAUNCH
"""

DESKTOP = """[Desktop Entry]
Type=Application
Name=İplikçi Nedim
Comment=Kişisel finans asistanı
Exec=AppRun
Icon=iplikci-nedim
Categories=Office;Finance;
Terminal=false
"""


def apprun() -> str:
    """The AppImage's own executable: it copies the Python once per version and runs the program from the copy."""
    return APPRUN.replace("LAUNCH", " ".join(LAUNCH))


def copy_archive(python_root: Path, archive: Path) -> None:
    """The Python folder as the Linux update file: its entries at the archive's root, links kept as links."""
    archive.unlink(missing_ok=True)
    with tarfile.open(archive, "w:gz") as tar:
        for entry in sorted(python_root.iterdir()):
            tar.add(entry, arcname=entry.name)


def linux(python_root: Path, out: Path, work: Path) -> Path:
    update = out / f"{SLUG}-{version()}-linux-{arch()}.tar.gz"  # the update file (ADR-0022)
    copy_archive(python_root, update)
    check_update_file(updater.unpack_copy, update, "bin/python3", work)
    appdir = work / "AppDir"
    appdir.mkdir()
    shutil.copytree(python_root, appdir / "python", symlinks=True)
    (appdir / "VERSION").write_text(version(), encoding="utf-8")
    executable = appdir / "AppRun"
    executable.write_text(apprun(), encoding="utf-8")
    executable.chmod(0o755)
    (appdir / f"{SLUG}.desktop").write_text(DESKTOP, encoding="utf-8")
    shutil.copy2(ASSETS / "iplikci.png", appdir / f"{SLUG}.png")
    tool = os.environ.get("APPIMAGETOOL") or shutil.which("appimagetool")
    if tool is None:
        sys.exit("appimagetool bulunamadı: PATH'e koyun ya da APPIMAGETOOL ile yolunu verin")
    image = out / f"{SLUG}-{version()}-linux-{arch()}.AppImage"
    image.unlink(missing_ok=True)
    os.environ["ARCH"] = arch()
    run(tool, appdir, image)
    return image


ISS = """; İplikçi Nedim's Windows installer (ADR-0017): into the user's own folder, no administrator rights; the Start
; menu opens the app, which registers the background service and opens the interface. An update takes the service
; off first, as it holds the Python's files open, replaces the whole Python and opens the app, which registers the
; service again. Removing it removes the service first; the data folder stays.
[Setup]
AppName=İplikçi Nedim
AppVersion={version}
AppPublisher=İplikçi Nedim
DefaultDirName={{localappdata}}\\Programs\\İplikçi Nedim
DisableProgramGroupPage=yes
PrivilegesRequired=lowest
OutputDir={out}
OutputBaseFilename={slug}-{version}-windows-{arch}
SetupIconFile={icon}
UninstallDisplayIcon={{app}}\\iplikci.ico
Compression=lzma2
SolidCompression=yes
WizardStyle=modern

[Languages]
Name: "turkish"; MessagesFile: "compiler:Languages\\Turkish.isl"

[Tasks]
Name: "desktopicon"; Description: "Masaüstüne kısayol koy"; Flags: unchecked

[InstallDelete]
; No file of an older version stays importable.
Type: filesandordirs; Name: "{{app}}\\python"

[Files]
Source: "{source}\\*"; DestDir: "{{app}}"; Flags: recursesubdirs createallsubdirs ignoreversion

[Icons]
Name: "{{userprograms}}\\İplikçi Nedim"; Filename: "{{app}}\\python\\pythonw.exe"; Parameters: "{launch}"; \
IconFilename: "{{app}}\\iplikci.ico"
Name: "{{userdesktop}}\\İplikçi Nedim"; Filename: "{{app}}\\python\\pythonw.exe"; Parameters: "{launch}"; \
IconFilename: "{{app}}\\iplikci.ico"; Tasks: desktopicon

[Run]
; Always: after an update the app registers the service again. Run by hand, it opens the interface too; run silently by
; the program's own update (ADR-0022), it registers and starts the service without a browser.
Filename: "{{app}}\\python\\pythonw.exe"; Parameters: "{launch}"; Flags: nowait skipifsilent
Filename: "{{app}}\\python\\pythonw.exe"; Parameters: "{launch} {quiet}"; Flags: nowait runhidden; Check: WizardSilent

[UninstallRun]
Filename: "{{app}}\\python\\python.exe"; Parameters: "-I -X utf8 -m iplikci servis kaldir"; Flags: runhidden; \
RunOnceId: "servis"

[Code]
// An update: the running service holds the older Python's files open. It is taken off the computer first and waits
// until the process has ended; the app opened at the end registers and starts it again from the new files. When the
// service does not end, the update stops here: replacing files a running process holds would leave a broken program.
// An older program that cannot run at all holds nothing, and the update repairs it.
function PrepareToInstall(var NeedsRestart: Boolean): String;
var
  Code: Integer;
  Python: String;
begin
  Result := '';
  Python := ExpandConstant('{{app}}\\python\\python.exe');
  if FileExists(Python) then
    if Exec(Python, '-I -X utf8 -m iplikci servis kaldir', '', SW_HIDE, ewWaitUntilTerminated, Code) then
      if Code <> 0 then
        Result := '{stopped}';
end;
"""
SERVICE_NOT_STOPPED = (  # the Windows installer's own words when the update cannot go on (Inno Setup's quoting)
    "İplikçi Nedim''in arka plan servisi durdurulamadı, bu yüzden güncelleme yapılmadı. Bilgisayarı yeniden "
    "başlatın, sonra kurulum programını yeniden çalıştırın."
)


def inno_script(out: Path | str, source: Path | str) -> str:
    """The Inno Setup script of the installer: the program's folder source, the setup program written into out."""
    return ISS.format(
        version=version(),
        out=out,
        slug=SLUG,
        arch=arch(),
        icon=ASSETS / "iplikci.ico",
        source=source,
        launch=" ".join(LAUNCH),
        quiet=QUIET,
        stopped=SERVICE_NOT_STOPPED,
    )


def iscc() -> str | None:
    found = shutil.which("iscc") or shutil.which("ISCC")
    if found:
        return found
    default = Path(os.environ.get("ProgramFiles(x86)", r"C:\Program Files (x86)")) / "Inno Setup 6" / "ISCC.exe"
    return str(default) if default.is_file() else None


def windows(python_root: Path, out: Path, work: Path) -> Path:
    folder = out / f"{SLUG}-{version()}-windows-{arch()}"
    shutil.rmtree(folder, ignore_errors=True)
    shutil.copytree(python_root, folder / "python")
    shutil.copy2(ASSETS / "iplikci.ico", folder / "iplikci.ico")
    script = work / "iplikci.iss"
    script.write_text(inno_script(out, folder), encoding="utf-8-sig")  # Inno Setup reads UTF-8 by its byte order mark
    compiler = iscc()
    if compiler is None:
        print(f"ISCC bulunamadı: kurulum programı derlenmedi; klasör hazır: {folder}")
        shutil.copy2(script, out / script.name)
        return folder
    run(compiler, script)
    return out / f"{SLUG}-{version()}-windows-{arch()}.exe"


def speak_utf8() -> None:
    """Write the Turkish messages as UTF-8: a Windows console (and the Windows runner) encodes with its code page,
    which has no "ı", and a message would end the build."""
    for stream in (sys.stdout, sys.stderr):
        if isinstance(stream, io.TextIOWrapper):
            stream.reconfigure(encoding="utf-8", errors="replace")


def main() -> None:
    speak_utf8()
    parser = argparse.ArgumentParser(description="Bu sistemin kurulum paketini dist/paket/ klasörüne üretir.")
    parser.add_argument("--cikti", type=Path, default=ROOT / "dist" / "paket", help="paketin yazılacağı klasör")
    args = parser.parse_args()
    out = args.cikti.resolve()
    out.mkdir(parents=True, exist_ok=True)
    with tempfile.TemporaryDirectory(prefix="iplikci-paket-") as temp:
        work = Path(temp)
        python_root = standalone_python(work)
        install_program(interpreter(python_root), work)
        prune(python_root)
        smoke(interpreter(python_root), work)
        if sys.platform == "darwin":
            made = macos(python_root, out, work)
        elif sys.platform.startswith("linux"):
            made = linux(python_root, out, work)
        elif sys.platform == "win32":
            made = windows(python_root, out, work)
        else:
            sys.exit(f"bu sistem için paket yok: {sys.platform}")
    print(f"Paket: {made}")


if __name__ == "__main__":
    main()
