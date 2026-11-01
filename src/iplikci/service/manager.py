"""The background service in the system's service manager (architecture §19, ADR-0017): a launchd agent on macOS, a
systemd user unit on Linux and a Task Scheduler task on Windows. Each starts the service for one data folder when the
user logs in and starts it again when it stops on an error; a deliberate stop stays a stop.

The service runs an installed copy of the program, never a development folder: a branch checked out or a file half
edited would otherwise reach the real data at the next restart. Until the installer of Phase 6, a developer installs
a fixed copy with `uv tool install` and registers the service from it."""

import getpass
import os
import plistlib
import re
import subprocess
import sys
from collections.abc import Callable, Mapping, Sequence
from dataclasses import dataclass
from pathlib import Path
from typing import Protocol
from xml.sax.saxutils import escape

from ..settings.paths import Layout
from .logs import OUTPUT_NAME

LABEL = "com.iplikci.service"
UNIT = "iplikci"
DESCRIPTION = "İplikçi Nedim: kişisel finans asistanının arka plan servisi"
RESTART_SECONDS = 30


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


def run_tool(args: Sequence[str]) -> Completed:
    done = subprocess.run(list(args), capture_output=True, check=False)
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


def installed_program(home: Path) -> Program:
    """The Python running this program, for the data folder at home; DevelopmentCopy when it runs a development
    folder."""
    source = development_folder()
    if source is not None:
        raise DevelopmentCopy(
            f"Servis geliştirme klasöründen kurulmaz: bu iplikci {source} klasöründen çalışıyor ve servis bir dal "
            "değişince ya da bir dosya yarım kalınca o kodu gerçek veriyle çalıştırırdı. Sabit bir kopya kurup servisi "
            f"onunla kurun: uv tool install --reinstall {source} ve ardından ~/.local/bin/iplikci servis kur. "
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

    def installed(self) -> bool: ...

    def restart(self) -> None: ...


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
        return {
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

    def install(self, program: Program) -> None:
        self.path.parent.mkdir(parents=True, exist_ok=True)
        if self._loaded():
            self._run(["launchctl", "bootout", self._target])  # the older agent stops first
        self.path.write_bytes(plistlib.dumps(self.agent(program)))
        self._bootstrap()

    def uninstall(self) -> bool:
        if not self.path.exists():
            return False
        if self._loaded():
            self._run(["launchctl", "bootout", self._target])
        self.path.unlink()  # the agent file this program wrote, not a document
        return True

    def installed(self) -> bool:
        return self.path.exists()

    def restart(self) -> None:
        if not self._loaded():  # stopped for this session: load it again
            self._bootstrap()
            return
        done = self._run(["launchctl", "kickstart", "-k", self._target])
        if done.code != 0:
            raise ManagerError(f"launchctl kickstart başarısız: {done.reason}")

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

    def uninstall(self) -> bool:
        if not self.path.exists():
            return False
        self._run(["systemctl", "--user", "disable", "--now", f"{UNIT}.service"])
        self.path.unlink()  # the unit file this program wrote
        self._run(["systemctl", "--user", "daemon-reload"])
        return True

    def installed(self) -> bool:
        return self.path.exists()

    def restart(self) -> None:
        self._systemctl("restart", f"{UNIT}.service")

    def _systemctl(self, *args: str) -> None:
        done = self._run(["systemctl", "--user", *args])
        if done.code != 0:
            raise ManagerError(f"systemctl --user {' '.join(args)} başarısız: {done.reason}")


class TaskScheduler:
    """Windows: a Task Scheduler task of the signed-in user, started at logon and again a minute after an error. It
    runs pythonw, so no console window opens; the service writes its own log."""

    def __init__(self, run: Run | None = None, env: Mapping[str, str] | None = None) -> None:
        self._run = run or run_tool
        self._env = os.environ if env is None else env

    @property
    def name(self) -> str:
        return "Görev Zamanlayıcı"

    @property
    def location(self) -> str:
        return f"{self.name} › {UNIT}"

    def task_xml(self, program: Program) -> str:
        python, *args = program.arguments()
        quiet = program.python.with_name("pythonw.exe")
        command = str(quiet) if quiet.exists() else python
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
        self.restart()

    def uninstall(self) -> bool:
        if not self.installed():
            return False
        self._run(["schtasks", "/End", "/TN", UNIT])
        self._schtasks("/Delete", "/TN", UNIT, "/F")
        return True

    def installed(self) -> bool:
        return self._run(["schtasks", "/Query", "/TN", UNIT]).code == 0

    def restart(self) -> None:
        self._run(["schtasks", "/End", "/TN", UNIT])  # fails harmlessly when it is not running
        self._schtasks("/Run", "/TN", UNIT)

    def _schtasks(self, *args: str) -> None:
        done = self._run(["schtasks", *args])
        if done.code != 0:
            raise ManagerError(f"schtasks {args[0]} başarısız: {done.reason}")


def for_platform(platform: str | None = None) -> ServiceManager:
    platform = platform or sys.platform
    if platform == "darwin":
        return Launchd()
    if platform.startswith("linux"):
        return Systemd()
    if platform == "win32":
        return TaskScheduler()
    raise ManagerError(f"bu işletim sisteminde ({platform}) arka plan servisi kurulamıyor")
