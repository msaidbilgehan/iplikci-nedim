"""Build this system's installer (ADR-0017, "Paketleme biçimi"): a portable CPython (python-build-standalone, as uv
installs it and checks it), İplikçi Nedim and its locked dependencies installed into it, and a launcher that runs
`python -I -X utf8 -m iplikci uygulama`. Nothing is frozen: the reading and viewer processes and the service run
exactly as an installed copy runs them.

    uv run python packaging/build.py        # into dist/paket/

- macOS: "İplikçi Nedim.app" (ad-hoc signed, not notarized: K22) in a disk image.
- Linux: an AppImage; appimagetool on the PATH or in APPIMAGETOOL.
- Windows: the program's folder and an Inno Setup script, compiled into a setup program when ISCC is found.

The web interface must be built first (`npm run build` in web/). This is a development tool: it runs uv, the
system's packaging tools and, for the interpreter, uv's download; it never touches the data folder."""

import argparse
import os
import platform
import plistlib
import shutil
import subprocess
import sys
import tempfile
import tomllib
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
ASSETS = ROOT / "packaging" / "assets"
UI = ROOT / "src" / "iplikci" / "api" / "ui" / "index.html"
EXTENSION = ROOT / "src" / "iplikci" / "browser_extension" / "manifest.json"
NAME = "İplikçi Nedim"
SLUG = "iplikci-nedim"
BUNDLE_ID = "com.iplikci.app"
LAUNCH = ("-I", "-X", "utf8", "-m", "iplikci", "uygulama")
INSTALLED = (  # what the installed program must import and carry
    "import iplikci.api.app, iplikci.parsers.registry; from iplikci.app import extension; "
    "assert (extension.BUILT / extension.MANIFEST).is_file(), 'eklenti yok'; print('iplikci', iplikci.__version__)"
)


def run(*args: str | Path, cwd: Path = ROOT) -> None:
    print("+", " ".join(str(a) for a in args), flush=True)
    subprocess.run([str(a) for a in args], cwd=cwd, check=True)


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
    # uv also links the minor version's name to the install: the folder itself is the one that is no link.
    [root] = [p for p in installs.iterdir() if p.is_dir() and not p.is_symlink() and p.name.startswith("cpython-")]
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
    extension inside it (K20: the service hands the extension to the browser)."""
    if not UI.is_file():
        sys.exit(f"Arayüz derlenmemiş ({UI} yok): önce web/ klasöründe npm ci && npm run build")
    if not EXTENSION.is_file():
        sys.exit(f"Eklenti derlenmemiş ({EXTENSION} yok): önce extension/ klasöründe npm ci && npm run build")
    wheels = work / "wheel"
    run("uv", "build", "--wheel", "--out-dir", wheels)
    requirements = work / "requirements.txt"
    export = ("uv", "export", "--quiet", "--frozen", "--no-dev", "--no-emit-project", "--format", "requirements-txt")
    run(*export, "-o", requirements)
    run("uv", "pip", "install", "--python", python, "--require-hashes", "--compile-bytecode", "-r", requirements)
    [wheel] = wheels.glob("*.whl")
    run("uv", "pip", "install", "--python", python, "--no-deps", "--compile-bytecode", wheel)
    run(python, "-I", "-c", INSTALLED)


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
target="$HOME/.local/lib/iplikci/$version"
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


def linux(python_root: Path, out: Path, work: Path) -> Path:
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
; Always: after an update the app registers the service again.
Filename: "{{app}}\\python\\pythonw.exe"; Parameters: "{launch}"; Flags: nowait skipifsilent

[UninstallRun]
Filename: "{{app}}\\python\\python.exe"; Parameters: "-I -X utf8 -m iplikci servis kaldir"; Flags: runhidden; \
RunOnceId: "servis"

[Code]
// An update: the running service holds the older Python's files open. It is taken off the computer first and waits
// until the process has ended; the app opened at the end registers and starts it again from the new files.
function PrepareToInstall(var NeedsRestart: Boolean): String;
var
  Code: Integer;
  Python: String;
begin
  Result := '';
  Python := ExpandConstant('{{app}}\\python\\python.exe');
  if FileExists(Python) then
    Exec(Python, '-I -X utf8 -m iplikci servis kaldir', '', SW_HIDE, ewWaitUntilTerminated, Code);
end;
"""


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
    text = ISS.format(
        version=version(),
        out=out,
        slug=SLUG,
        arch=arch(),
        icon=ASSETS / "iplikci.ico",
        source=folder,
        launch=" ".join(LAUNCH),
    )
    script.write_text(text, encoding="utf-8-sig")  # Inno Setup reads UTF-8 by its byte order mark
    compiler = iscc()
    if compiler is None:
        print(f"ISCC bulunamadı: kurulum programı derlenmedi; klasör hazır: {folder}")
        shutil.copy2(script, out / script.name)
        return folder
    run(compiler, script)
    return out / f"{SLUG}-{version()}-windows-{arch()}.exe"


def main() -> None:
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
