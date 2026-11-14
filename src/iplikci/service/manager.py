"""The background service in the system's service manager (architecture §19, ADR-0017): a launchd agent on macOS, a
systemd user unit on Linux and a Task Scheduler task on Windows. Each starts the service for one data folder when the
user logs in and starts it again when it stops on an error; a deliberate stop stays a stop.

The service runs an installed copy of the program, never a development folder: a branch checked out or a file half
edited would otherwise reach the real data at the next restart. Until the installer of Phase 6, a developer installs
a fixed copy with `uv tool install` and registers the service from it.

macOS's packaged app is removed by dragging it to the Trash, which leaves its agent behind. Its agent therefore starts
the service through a guard (GUARD) that removes the agent once the app has left its place, and the running service
watches for the same (app.lifecycle.gone_program, ADR-0017's note of 2026-11-15)."""

import csv
import getpass
import json
import os
import plistlib
import re
import shlex
import subprocess
import sys
import time
from collections.abc import Callable, Mapping, Sequence
from dataclasses import dataclass
from pathlib import Path
from typing import Protocol, cast
from xml.sax.saxutils import escape, unescape

from ..settings.paths import Layout, replace_private
from ..update.install import BUNDLE_ID, Kind, detect
from .logs import OUTPUT_NAME

LABEL = "com.iplikci.service"
UNIT = "iplikci"
DESCRIPTION = "İplikçi Nedim: kişisel finans asistanının arka plan servisi"
RESTART_SECONDS = 30
# Windows: a console program (schtasks) started from pythonw, as the Start menu's app and the service's task run,
# opens a console window of its own for every call unless it is created without one.
WINDOWS = os.name == "nt"
NO_WINDOW = 0x08000000  # CREATE_NO_WINDOW; subprocess names these flags on Windows only
DETACHED = 0x00000008  # DETACHED_PROCESS: no console at all, nothing tied to the one that started it
BREAKAWAY = 0x01000000  # CREATE_BREAKAWAY_FROM_JOB: out of the task's job object, where the job allows it
# A task's status is a word in the system's language; its last result is a number, SCHED_S_TASK_RUNNING while an
# instance runs: the 7th field of `schtasks /Query /V /FO CSV`.
TASK_RUNNING = 0x41301
_LAST_RESULT = 6
STOP_WAIT = 15.0  # seconds a start of the task waits for its ended instance to be done with
PID_WAIT = 120.0  # seconds the Windows helper waits for the service that asked to come back to end
# macOS's packaged app: launchd starts the service through /bin/sh, which first looks whether the app's Python is still
# where the agent says. Without it an app dragged to the Trash, or a Trash emptied, would leave launchd starting a
# program that is not there every RESTART_SECONDS until the user logs out (KeepAlive), and again at every login. The
# guard removes the agent's file and its job instead, says so in the system's log and ends cleanly. An app on another
# disk that is not attached now has not gone: nothing is removed, and the next login looks again. Its arguments follow
# its name ($0): the agent's file, the job, then the service's own command line. left_its_place tells the same in
# Python, for the running service.
SH = "/bin/sh"
GUARD_NAME = "iplikci-servis"
GUARD = """\
plist=$1 job=$2
shift 2
case $1 in
*/.Trash/* | */.Trashes/*) ;;
/Volumes/*)
    disk=${1#/Volumes/}
    [ -d "/Volumes/${disk%%/*}" ] || exit 0
    [ -x "$1" ] && exec "$@" ;;
*) [ -x "$1" ] && exec "$@" ;;
esac
rm -f -- "$plist"
logger -t iplikci-servis "the program left its place ($1): its agent and job are removed" 2>/dev/null
launchctl bootout "$job" 2>/dev/null
exit 0
"""
TRASH_FOLDERS = frozenset({".Trash", ".Trashes"})  # the user's own Trash, and each other disk's


class ManagerError(Exception):
    """The service could not be registered, removed or restarted; the message says why (Turkish)."""


class DevelopmentCopy(ManagerError):
    """This program runs from a development folder, which a service must never run."""


@dataclass(frozen=True, slots=True)
class Completed:
    code: int
    out: str
    err: str

    @property
    def reason(self) -> str:
        return (self.err or self.out).strip() or f"çıkış kodu {self.code}"


type Run = Callable[[Sequence[str]], Completed]
type Spawn = Callable[[Sequence[str]], None]
type Ended = Callable[[int, float], bool]


def creation_flags(*, detached: bool = False) -> int:
    """How a process this program starts is created: without a console window on Windows, detached from this one
    when asked; elsewhere plainly, as subprocess takes no flags there."""
    if not WINDOWS:
        return 0
    return (NO_WINDOW | DETACHED) if detached else NO_WINDOW


def spawn_detached(args: Sequence[str]) -> None:
    """Start a process that outlives this one, its output nowhere. On Windows it has no console and no window and,
    where the task's job object allows it, leaves the job, so the task is done once the service has ended."""
    flags = creation_flags(detached=True)
    try:
        _popen(args, flags | (BREAKAWAY if WINDOWS else 0))
    except PermissionError:
        if not WINDOWS:
            raise
        _popen(args, flags)  # the job allows no breakaway: the helper stays in it


def _popen(args: Sequence[str], flags: int) -> None:
    devnull = subprocess.DEVNULL
    subprocess.Popen(list(args), stdin=devnull, stdout=devnull, stderr=devnull, creationflags=flags)


def process_ended(pid: int, seconds: float) -> bool:
    """Wait up to seconds for the process pid to end; whether it has."""
    if sys.platform == "win32":
        return _wait_windows(pid, seconds)
    deadline = time.monotonic() + seconds
    while True:
        try:
            os.kill(pid, 0)  # signal 0 only asks whether the process is there (on POSIX; Windows would end it)
        except ProcessLookupError:
            return True
        except PermissionError:
            pass  # there, and another user's
        if time.monotonic() >= deadline:
            return False
        time.sleep(0.1)


if sys.platform == "win32":
    import ctypes

    def _wait_windows(pid: int, seconds: float) -> bool:
        kernel32 = ctypes.WinDLL("kernel32", use_last_error=True)
        handle = kernel32.OpenProcess(0x00100000, False, pid)  # SYNCHRONIZE: enough to wait for it
        if not handle:
            return True  # no such process: it has ended
        try:
            return kernel32.WaitForSingleObject(handle, int(seconds * 1000)) == 0  # WAIT_OBJECT_0: it ended
        finally:
            kernel32.CloseHandle(handle)


def run_tool(args: Sequence[str]) -> Completed:
    done = subprocess.run(list(args), capture_output=True, check=False, creationflags=creation_flags())
    encoding = "oem" if os.name == "nt" else "utf-8"  # Windows tools answer in the console's code page
    return Completed(
        done.returncode, done.stdout.decode(encoding, errors="replace"), done.stderr.decode(encoding, errors="replace")
    )


@dataclass(frozen=True, slots=True)
class Program:
    """What the service manager starts: an installed Python running the service for one data folder."""

    python: Path
    home: Path

    def arguments(self) -> list[str]:
        # -I: the service reads untrusted documents, so nothing from the working folder or from PYTHON* variables is
        # importable. -X utf8: one text encoding, whatever the session's locale.
        return [str(self.python), "-I", "-X", "utf8", "-m", "iplikci", "servis", "calistir", "--ev", str(self.home)]

    @property
    def output(self) -> Path:
        return Layout(self.home).logs / OUTPUT_NAME


def development_folder(module: Path | None = None) -> Path | None:
    """The source folder this program runs from when it is a development copy (an editable install or a source tree
    on the path): src/iplikci beside a pyproject.toml. An installed copy lives in site-packages or in a bundle."""
    src = (module or Path(__file__)).resolve().parents[2]
    if src.name == "src" and (src.parent / "pyproject.toml").is_file():
        return src.parent
    return None


def install_command(source: Path) -> str:
    """How a fixed copy is installed from a source folder: with the Python the tests run on (.python-version), as
    uv tool install would otherwise take the newest Python it has."""
    pinned = source / ".python-version"
    version = pinned.read_text(encoding="utf-8").strip() if pinned.is_file() else ""
    return f"uv tool install --reinstall{f' --python {version}' if version else ''} {source}"


def installed_program(home: Path) -> Program:
    """The Python running this program, for the data folder at home; DevelopmentCopy when it runs a development
    folder."""
    source = development_folder()
    if source is not None:
        raise DevelopmentCopy(
            f"Servis geliştirme klasöründen kurulmaz: bu iplikci {source} klasöründen çalışıyor ve servis bir dal "
            "değişince ya da bir dosya yarım kalınca o kodu gerçek veriyle çalıştırırdı. Sabit bir kopya kurup servisi "
            f"onunla kurun: {install_command(source)} ve ardından ~/.local/bin/iplikci servis kur. "
            "Geliştirirken servis ön planda çalışır: uv run iplikci servis calistir"
        )
    # The python is not resolved: a virtual environment's python finds its packages through the path it has.
    return Program(Path(sys.executable).absolute(), home.resolve())


class ServiceManager(Protocol):
    @property
    def name(self) -> str: ...

    @property
    def location(self) -> str:
        """Where the registration lives, for the user."""
        ...

    def install(self, program: Program) -> None:
        """Register the service, replacing an older registration, and start it."""
        ...

    def uninstall(self) -> bool:
        """Stop and remove the service; whether there was one."""
        ...

    def unregister(self) -> bool:
        """Remove the registration and leave the running process alone: the service itself asks for it, and ends
        after its answer with a clean exit, which no service manager restarts. Whether there was one."""
        ...

    def installed(self) -> bool: ...

    def registered(self) -> Program | None:
        """What the registration runs: the Python and the data folder; None when none is registered or it cannot be
        read."""
        ...

    def restart(self) -> None: ...

    def restart_after(self, pid: int) -> None:
        """The service `pid` is ending with the exit code that asks to start it again (app.lifecycle.RESTART): what
        this manager needs for that beyond the exit itself."""
        ...


def _program_in(arguments: Sequence[str]) -> Program | None:
    """The Python and the data folder of a registered command line: its first word and the value after --ev, past the
    guard of a packaged app's agent and the guard's own arguments."""
    found = list(arguments)
    if found[:2] == [SH, "-c"] and len(found) > 6 and found[3] == GUARD_NAME:
        found = found[6:]
    if not found or "--ev" not in found[:-1]:
        return None
    return Program(Path(found[0]), Path(found[found.index("--ev") + 1]))


def guarded(arguments: Sequence[str], agent: Path, job: str) -> list[str]:
    """A packaged app's command line behind its guard (GUARD): what removes the agent at `agent` and the job once the
    program has left its place."""
    return [SH, "-c", GUARD, GUARD_NAME, str(agent), job, *arguments]


def packaged_app(python: Path) -> bool:
    """Whether this Python is the one inside macOS's packaged app, which is removed by dragging it to the Trash."""
    return detect(python, "darwin").kind is Kind.MACOS_APP


def left_its_place(python: Path) -> bool:
    """Whether the program a registration starts has left its place for good, as the guard of a packaged app's agent
    (GUARD) tells it: it lies in a Trash folder, or it is gone from a disk that is here (dragged to the Trash, the
    Trash emptied). An app on another disk that is not attached now has not: it comes back with its disk."""
    parts = python.parts
    if TRASH_FOLDERS.intersection(parts[:-1]):
        return True
    if len(parts) > 2 and parts[:2] == ("/", "Volumes") and not Path("/Volumes", parts[2]).is_dir():
        return False
    return not os.access(python, os.X_OK)


class Launchd:
    """macOS: a launchd agent in the user's session."""

    def __init__(self, user_home: Path | None = None, run: Run | None = None, uid: int | None = None) -> None:
        self.path = (user_home or Path.home()) / "Library" / "LaunchAgents" / f"{LABEL}.plist"
        self._run = run or run_tool
        self._domain = f"gui/{os.getuid() if uid is None else uid}"

    @property
    def name(self) -> str:
        return "launchd"

    @property
    def location(self) -> str:
        return str(self.path)

    def agent(self, program: Program) -> dict[str, object]:
        found: dict[str, object] = {
            "Label": LABEL,
            "ProgramArguments": program.arguments(),
            "WorkingDirectory": str(program.home),
            "RunAtLoad": True,
            "KeepAlive": {"SuccessfulExit": False},  # started again after an error; a deliberate stop stays a stop
            "ThrottleInterval": RESTART_SECONDS,
            "Umask": 0o077,  # written in decimal, as launchd wants: what the service creates is the user's alone
            "StandardOutPath": str(program.output),
            "StandardErrorPath": str(program.output),
            "EnvironmentVariables": {"PATH": "/usr/bin:/bin:/usr/sbin:/sbin"},
        }
        if packaged_app(program.python):
            found["ProgramArguments"] = guarded(program.arguments(), self.path, self._target)
            # The job runs /bin/sh: this names the app the system's list of background items shows it under (macOS 13+).
            found["AssociatedBundleIdentifiers"] = [BUNDLE_ID]
        return found

    def install(self, program: Program) -> None:
        self.path.parent.mkdir(parents=True, exist_ok=True)
        if self._loaded():
            self._run(["launchctl", "bootout", self._target])  # the older agent stops first
        self.path.write_bytes(plistlib.dumps(self.agent(program)))
        self._bootstrap()

    def refresh(self) -> bool:
        """The agent written again in this version's shape for the program it registers, where an older version wrote
        it otherwise (a packaged app's agent from before its guard): launchd reads it at the next login, and the job
        loaded now goes on as it is. Whether it was written."""
        found = self.registered()
        if found is None:
            return False
        wanted = plistlib.dumps(self.agent(found))
        if self.path.read_bytes() == wanted:
            return False
        replace_private(self.path, wanted.decode("utf-8"))  # never half a file for launchd to read
        return True

    def uninstall(self) -> bool:
        if not self.path.exists():
            return False
        if self._loaded():
            self._run(["launchctl", "bootout", self._target])
        self.path.unlink()  # the agent file this program wrote, not a document
        return True

    def unregister(self) -> bool:
        if not self.path.exists():
            return False
        self.path.unlink()  # the agent file this program wrote; launchd forgets the job at logout
        return True

    def installed(self) -> bool:
        return self.path.exists()

    def registered(self) -> Program | None:
        try:
            agent: object = plistlib.loads(self.path.read_bytes())
        except (OSError, plistlib.InvalidFileException, ValueError):  # none, or not one this program wrote
            return None
        if not isinstance(agent, dict):
            return None
        arguments = cast(dict[str, object], agent).get("ProgramArguments")
        return _program_in([str(a) for a in cast(list[object], arguments)]) if isinstance(arguments, list) else None

    def restart(self) -> None:
        if not self._loaded():  # stopped for this session: load it again
            self._bootstrap()
            return
        done = self._run(["launchctl", "kickstart", "-k", self._target])
        if done.code != 0:
            raise ManagerError(f"launchctl kickstart başarısız: {done.reason}")

    def restart_after(self, pid: int) -> None:
        """launchd starts an unsuccessful exit again by itself (KeepAlive)."""

    @property
    def _target(self) -> str:
        return f"{self._domain}/{LABEL}"

    def _loaded(self) -> bool:
        return self._run(["launchctl", "print", self._target]).code == 0

    def _bootstrap(self) -> None:
        done = self._run(["launchctl", "bootstrap", self._domain, str(self.path)])
        if done.code != 0:
            raise ManagerError(f"launchctl bootstrap başarısız: {done.reason}")


def _unit_value(text: str) -> str:
    return text.replace("%", "%%")  # systemd expands %-specifiers in unit files


def _unit_arg(text: str) -> str:
    """One ExecStart argument, quoted when it holds a space, a quote or a backslash."""
    value = _unit_value(text)
    if not re.search(r"[\s\"'\\]", value):
        return value
    return '"' + value.replace("\\", "\\\\").replace('"', '\\"') + '"'


class Systemd:
    """Linux: a systemd user unit, started with the user's session."""

    def __init__(
        self, user_home: Path | None = None, run: Run | None = None, env: Mapping[str, str] | None = None
    ) -> None:
        env = os.environ if env is None else env
        config = Path(env.get("XDG_CONFIG_HOME") or (user_home or Path.home()) / ".config")
        self.path = config / "systemd" / "user" / f"{UNIT}.service"
        self._run = run or run_tool

    @property
    def name(self) -> str:
        return "systemd"

    @property
    def location(self) -> str:
        return str(self.path)

    def unit(self, program: Program) -> str:
        command = " ".join(_unit_arg(a) for a in program.arguments())
        output = _unit_value(str(program.output))
        return (
            f"[Unit]\nDescription={DESCRIPTION}\n\n"
            f"[Service]\nType=simple\nWorkingDirectory={_unit_value(str(program.home))}\nExecStart={command}\n"
            f"Restart=on-failure\nRestartSec={RESTART_SECONDS}\nUMask=0077\n"
            f"StandardOutput=append:{output}\nStandardError=append:{output}\n\n"
            "[Install]\nWantedBy=default.target\n"
        )

    def install(self, program: Program) -> None:
        self.path.parent.mkdir(parents=True, exist_ok=True)
        self.path.write_text(self.unit(program), encoding="utf-8")
        for args in (["daemon-reload"], ["enable", f"{UNIT}.service"], ["restart", f"{UNIT}.service"]):
            self._systemctl(*args)

    def retarget(self, program: Program) -> None:
        """The unit starts program from its next start on; the running service is left alone. The service that
        installs an update of itself does this, then ends with the code that has systemd start it again (ADR-0022)."""
        self.path.parent.mkdir(parents=True, exist_ok=True)
        self.path.write_text(self.unit(program), encoding="utf-8")
        self._systemctl("daemon-reload")

    def uninstall(self) -> bool:
        if not self.path.exists():
            return False
        self._run(["systemctl", "--user", "disable", "--now", f"{UNIT}.service"])
        self.path.unlink()  # the unit file this program wrote
        self._run(["systemctl", "--user", "daemon-reload"])
        return True

    def unregister(self) -> bool:
        if not self.path.exists():
            return False
        self._run(["systemctl", "--user", "disable", f"{UNIT}.service"])  # no --now: the service ends by itself
        self.path.unlink()  # the unit file this program wrote
        self._run(["systemctl", "--user", "daemon-reload"])
        return True

    def installed(self) -> bool:
        return self.path.exists()

    def registered(self) -> Program | None:
        try:
            text = self.path.read_text(encoding="utf-8")
        except (OSError, UnicodeDecodeError):
            return None
        for line in text.splitlines():
            if line.startswith("ExecStart="):  # the command line, as unit() quotes it
                try:
                    return _program_in([a.replace("%%", "%") for a in shlex.split(line.removeprefix("ExecStart="))])
                except ValueError:  # quoting this program did not write
                    return None
        return None

    def restart(self) -> None:
        self._systemctl("restart", f"{UNIT}.service")

    def restart_after(self, pid: int) -> None:
        """systemd starts an unsuccessful exit again by itself (Restart=on-failure)."""

    def _systemctl(self, *args: str) -> None:
        done = self._run(["systemctl", "--user", *args])
        if done.code != 0:
            raise ManagerError(f"systemctl --user {' '.join(args)} başarısız: {done.reason}")


class TaskScheduler:
    """Windows: a Task Scheduler task of the signed-in user, started at logon. It runs pythonw, so no console window
    opens; the service writes its own log. Task Scheduler starts a task again only when it could not start, never
    when it ended with an error code: a restart asked from the interface comes back through a helper (restart_after).

    schtasks writes the task back in the console's code page, where a letter the code page lacks (the İ of "İplikçi
    Nedim" on an English Windows, the ş of a user's folder) comes back as another one. What the task was registered
    with is also kept in a file of the app's own (`record`) and read from there while the task still matches it."""

    def __init__(
        self,
        run: Run | None = None,
        env: Mapping[str, str] | None = None,
        record: Path | None = None,
        *,
        spawn: Spawn | None = None,
        ended: Ended | None = None,
        sleep: Callable[[float], None] = time.sleep,
        clock: Callable[[], float] = time.monotonic,
    ) -> None:
        self._run = run or run_tool
        self._env = os.environ if env is None else env
        local = Path(self._env.get("LOCALAPPDATA") or Path.home() / "AppData" / "Local")
        self.record = record or local / "iplikci-servis" / "gorev.json"
        self._spawn = spawn or spawn_detached
        self._ended = ended or process_ended
        self._sleep = sleep
        self._clock = clock

    @property
    def name(self) -> str:
        return "Görev Zamanlayıcı"

    @property
    def location(self) -> str:
        return f"{self.name} › {UNIT}"

    @staticmethod
    def command(program: Program) -> Path:
        """What the task runs: pythonw beside the Python where there is one, so no console window opens."""
        quiet = program.python.with_name("pythonw.exe")
        return quiet if quiet.exists() else program.python

    def task_xml(self, program: Program) -> str:
        _, *args = program.arguments()
        command = str(self.command(program))
        arguments = subprocess.list2cmdline(args)  # Windows quoting rules
        domain, user = self._env.get("USERDOMAIN"), self._env.get("USERNAME") or getpass.getuser()
        who = escape(f"{domain}\\{user}" if domain else user)
        return f"""<?xml version="1.0" encoding="UTF-16"?>
<Task version="1.2" xmlns="http://schemas.microsoft.com/windows/2004/02/mit/task">
  <RegistrationInfo>
    <Description>{escape(DESCRIPTION)}</Description>
  </RegistrationInfo>
  <Triggers>
    <LogonTrigger>
      <Enabled>true</Enabled>
      <UserId>{who}</UserId>
    </LogonTrigger>
  </Triggers>
  <Principals>
    <Principal id="Author">
      <UserId>{who}</UserId>
      <LogonType>InteractiveToken</LogonType>
      <RunLevel>LeastPrivilege</RunLevel>
    </Principal>
  </Principals>
  <Settings>
    <MultipleInstancesPolicy>IgnoreNew</MultipleInstancesPolicy>
    <DisallowStartIfOnBatteries>false</DisallowStartIfOnBatteries>
    <StopIfGoingOnBatteries>false</StopIfGoingOnBatteries>
    <StartWhenAvailable>true</StartWhenAvailable>
    <IdleSettings>
      <StopOnIdleEnd>false</StopOnIdleEnd>
      <RestartOnIdle>false</RestartOnIdle>
    </IdleSettings>
    <Enabled>true</Enabled>
    <ExecutionTimeLimit>PT0S</ExecutionTimeLimit>
    <Priority>7</Priority>
    <RestartOnFailure>
      <Interval>PT1M</Interval>
      <Count>999</Count>
    </RestartOnFailure>
  </Settings>
  <Actions Context="Author">
    <Exec>
      <Command>{escape(command)}</Command>
      <Arguments>{escape(arguments)}</Arguments>
      <WorkingDirectory>{escape(str(program.home))}</WorkingDirectory>
    </Exec>
  </Actions>
</Task>
"""

    def install(self, program: Program) -> None:
        run = Layout(program.home).run
        run.mkdir(parents=True, exist_ok=True)
        definition = run / ".gorev.xml"
        definition.write_text(self.task_xml(program), encoding="utf-16")  # what schtasks reads, with a BOM
        try:
            self._schtasks("/Create", "/TN", UNIT, "/XML", str(definition), "/F")
        finally:
            definition.unlink(missing_ok=True)  # our own temporary file
        self.record.parent.mkdir(parents=True, exist_ok=True)
        replace_private(self.record, json.dumps({"command": str(self.command(program)), "home": str(program.home)}))
        self.restart()

    def uninstall(self) -> bool:
        if not self.installed():
            self.record.unlink(missing_ok=True)  # the app's own note of a task that is gone
            return False
        self._run(["schtasks", "/End", "/TN", UNIT])
        self._schtasks("/Delete", "/TN", UNIT, "/F")
        self.record.unlink(missing_ok=True)
        return True

    def unregister(self) -> bool:
        if not self.installed():
            self.record.unlink(missing_ok=True)
            return False
        self._schtasks("/Delete", "/TN", UNIT, "/F")  # a running task's process goes on until it ends
        self.record.unlink(missing_ok=True)
        return True

    def installed(self) -> bool:
        return self._run(["schtasks", "/Query", "/TN", UNIT]).code == 0

    def registered(self) -> Program | None:
        """What the task runs: as the app's own record says it, exactly, while the task as schtasks writes it back
        still matches the record; else as schtasks writes it (a task registered by a copy that kept no record)."""
        done = self._run(["schtasks", "/Query", "/TN", UNIT, "/XML"])
        if done.code != 0:
            return None
        shown = _task_program(done.out)
        kept = self._kept()
        if kept is not None and (shown is None or _shown_as(kept, shown)):
            return kept
        return shown

    def _kept(self) -> Program | None:
        try:
            found = json.loads(self.record.read_text(encoding="utf-8"))
            return Program(Path(str(found["command"])), Path(str(found["home"])))
        except (OSError, ValueError, KeyError, TypeError):  # none, or not one this program wrote
            return None

    def restart(self) -> None:
        self._run(["schtasks", "/End", "/TN", UNIT])  # fails harmlessly when it is not running
        self.start()

    def restart_after(self, pid: int) -> None:
        """A helper outside the task waits for the service `pid` to end, then runs the task again (service/respawn):
        the RESTART exit alone would leave the service stopped until the next logon."""
        self._spawn([sys.executable, "-I", "-X", "utf8", "-m", "iplikci.service.respawn", str(pid)])

    def start_after(self, pid: int) -> None:
        """The helper's own part: the task again once the process pid has ended, or after PID_WAIT seconds."""
        self._ended(pid, PID_WAIT)
        self.start()

    def start(self) -> None:
        """Run the task once no instance of it runs: one still ending would make Task Scheduler ignore the start
        (MultipleInstancesPolicy IgnoreNew). The wait is bounded, and the start is asked for either way."""
        deadline = self._clock() + STOP_WAIT
        while self.running() and self._clock() < deadline:
            self._sleep(0.25)
        self._schtasks("/Run", "/TN", UNIT)

    def running(self) -> bool:
        """Whether an instance of the task runs now, by its last result (its status is in the system's language)."""
        done = self._run(["schtasks", "/Query", "/TN", UNIT, "/V", "/FO", "CSV", "/NH"])
        if done.code != 0:
            return False
        rows = csv.reader(done.out.splitlines())
        return any(len(row) > _LAST_RESULT and row[_LAST_RESULT].strip() == str(TASK_RUNNING) for row in rows)

    def _schtasks(self, *args: str) -> None:
        done = self._run(["schtasks", *args])
        if done.code != 0:
            raise ManagerError(f"schtasks {args[0]} başarısız: {done.reason}")


def _task_program(xml: str) -> Program | None:
    """The Python (pythonw where there is one) and the data folder of the task task_xml() wrote, as schtasks shows
    them."""
    command = re.search(r"<Command>([^<]*)</Command>", xml)
    home = re.search(r"<WorkingDirectory>([^<]*)</WorkingDirectory>", xml)
    if command is None or home is None:
        return None
    return Program(Path(unescape(command.group(1))), Path(unescape(home.group(1))))


def _shown_as(kept: Program, shown: Program) -> bool:
    """Whether the task schtasks shows is the recorded one, written in the console's code page."""
    return _same_but_lost(str(kept.python), str(shown.python)) and _same_but_lost(str(kept.home), str(shown.home))


def _same_but_lost(exact: str, shown: str) -> bool:
    """A code page that lacks a letter writes another letter or "?" for it, one for one; Windows paths ignore case."""
    if len(exact) != len(shown):
        return False
    return all(a.lower() == b.lower() or not a.isascii() for a, b in zip(exact, shown, strict=True))


def for_platform(platform: str | None = None) -> ServiceManager:
    platform = platform or sys.platform
    if platform == "darwin":
        return Launchd()
    if platform.startswith("linux"):
        return Systemd()
    if platform == "win32":
        return TaskScheduler()
    raise ManagerError(f"bu işletim sisteminde ({platform}) arka plan servisi kurulamıyor")
