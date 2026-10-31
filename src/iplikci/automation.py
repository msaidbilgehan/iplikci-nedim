"""File new documents without anyone at the keyboard.

    iplikci otomatik            fetch the bank e-mails, file what waits in the inbox, rebuild the report
    iplikci otomatik --kur      do that whenever something lands in the inbox and once an hour
    iplikci otomatik --kaldir   stop doing it

Whatever puts files into the inbox (the panel, the e-mail fetch, a file manager, a browser saving
there) gets them filed exactly as the panel does. Installing the job is the user's consent to apply
the plan without showing it first; everything set aside still goes to the Trash and into the
organizer's log. The job is a launchd agent on macOS, systemd user units on Linux and a Task
Scheduler task on Windows (no folder trigger there: it runs once an hour).

It also tells the user when a month ended (its month-end page is ready, still waiting for statements)
and when the statements closed it, once each.
"""

import getpass
import hashlib
import json
import os
import plistlib
import re
import shutil
import subprocess
import sys
import tempfile
import time
from dataclasses import dataclass
from datetime import date, datetime
from pathlib import Path
from xml.sax.saxutils import escape

from . import duzenle, email_fetch, month_end
from .insights import month_of, shift
from .workspace import Analysis, Busy, StalePlan, Workspace, analyze, apply, inbox_files, plan_inbox

LABEL = "com.iplikci.gelen"
UNIT = "iplikci"  # systemd units and the Windows task
LOG_NAME = "otomatik.log"
MONTHS_NAME = ".ay-sonu.json"  # each month's closing status when the user last heard of it
EMPTY = "gelen kutusu boş"
QUIET_SECONDS = 20  # a file still being copied or saved keeps changing: wait until the inbox is still
MAIL_EVERY = 15 * 60  # an inbox change starts the job too; the mailbox is read at most this often
_WAIT_LIMIT = 300
_LOG_LIMIT = 1 << 20


@dataclass
class Outcome:
    message: str
    filed: int = 0
    unreadable: int = 0
    trashed: int = 0
    trash: Path | None = None
    log: Path | None = None
    mail: str = ""  # what the e-mail fetch brought or why it failed: part of the message and the notification
    mail_log: str = ""  # what the e-mail fetch did, for the log, also when it found nothing
    months: str = ""  # a month that ended or closed since the last run


def _last_change(ws: Workspace) -> float:
    # ctime as well as mtime: a copy keeps the original's modification time.
    latest = 0.0
    for folder, dirs, files in os.walk(ws.inbox):
        for name in (".", *dirs, *files):
            try:
                st = os.stat(os.path.join(folder, name))
            except FileNotFoundError:
                continue
            latest = max(latest, st.st_mtime, st.st_ctime)
    return latest


def wait_until_quiet(ws: Workspace, quiet: float = QUIET_SECONDS, limit: float = _WAIT_LIMIT, sleep=time.sleep) -> bool:
    deadline = time.time() + limit
    while time.time() - _last_change(ws) < quiet:
        if time.time() > deadline:
            return False
        sleep(2)
    return True


def _message(out: Outcome, kinds: dict[str, int], unverified: int) -> str:
    parts = []
    if out.filed:
        labels = {"ekstre": "kart ekstresi", "hesap": "hesap dökümü", "dekont": "dekont"}
        detail = ", ".join(f"{n} {labels[k]}" for k, n in kinds.items() if n)
        parts.append(f"{out.filed} yeni belge yerleştirildi" + (f" ({detail})" if detail else ""))
    if out.unreadable:
        parts.append(f"{out.unreadable} belge okunamadı, {duzenle.UNREADABLE_FOLDER} klasörüne taşındı")
    if out.trashed:
        parts.append(f"{out.trashed} dosya çöp kutusuna taşındı (kopya, şirket belgesi ya da banka belgesi değil)")
    text = ". ".join(parts) + ". Rapor güncellendi."
    if unverified:
        text += f" Dikkat: {unverified} belge bankanın toplamıyla tutmuyor."
    return text


def _fetch_mail(ws: Workspace) -> tuple[str, bool, str]:
    """(what the e-mail fetch brought, whether the user must hear it, the log line). An error is told
    once, not on every run; a fetch that found nothing is only logged."""
    if not email_fetch.configured(ws) or not email_fetch.due(ws, MAIL_EVERY):
        return "", False, ""
    before = email_fetch.last_error(ws)
    try:
        got = email_fetch.fetch(ws, wait=5)
    except Busy:  # the panel or the command line is reading the mailbox right now
        return "", False, "e-posta: şu anda başka bir işlem alıyor, bu kez atlandı"
    except email_fetch.MailError as exc:
        return f"E-posta alınamadı: {exc}", str(exc) != before, f"e-posta alınamadı: {exc}"
    return (f"E-postadan {len(got.copied)} yeni belge alındı" if got.copied else ""), False, f"e-posta: {got.message}"


def _file_inbox(ws: Workspace, quiet: float) -> tuple[Outcome, Analysis | None]:
    if not inbox_files(ws):
        return Outcome(EMPTY), None
    if not wait_until_quiet(ws, quiet):
        return Outcome("gelen kutusu hâlâ değişiyor; bir sonraki çalışmada denenecek"), None
    try:
        done = apply(ws, plan_inbox(ws))
    except (Busy, StalePlan) as exc:  # the panel or another run is at it; the next trigger tries again
        return Outcome(str(exc)), None
    out = Outcome("", trash=done.trash, log=done.log)
    kinds = {"ekstre": 0, "hesap": 0, "dekont": 0}
    for it in done.items:
        if it.action == duzenle.KEEP:
            out.filed += 1
            if it.result and it.result.statements:
                kinds["hesap" if it.result.statements[0].is_account else "ekstre"] += 1
            else:
                kinds["dekont"] += 1
        elif it.action == duzenle.FAILED and it.target is not None:
            out.unreadable += 1
        elif it.action in (duzenle.DUPLICATE, duzenle.BUSINESS, duzenle.UNUSED) and it.path is not None:
            out.trashed += 1
    if not done.items:
        out.message = "yerleştirilecek belge yok"
        return out, None
    a = analyze(ws, write=True)
    out.message = _message(out, kinds, sum(not s.verified for s in a.dataset.statements))
    return out, a


def _month_state(ws: Workspace) -> dict:
    """{"month": the month of the last look, "documents": their fingerprint then, "months": month -> status}."""
    try:
        value = json.loads((ws.output / MONTHS_NAME).read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return {}
    return value if isinstance(value, dict) and isinstance(value.get("months"), dict) else {}


def _save_month_state(ws: Workspace, state: dict) -> None:
    fd, tmp = tempfile.mkstemp(prefix=".ay-sonu-", dir=ws.output)
    try:
        with os.fdopen(fd, "w", encoding="utf-8") as f:
            json.dump(state, f)
        os.replace(tmp, ws.output / MONTHS_NAME)
    except BaseException:
        Path(tmp).unlink(missing_ok=True)
        raise


def _fingerprint(ws: Workspace) -> str:
    return hashlib.sha256(repr(ws.signature()).encode()).hexdigest()


def month_news(ws: Workspace, a: Analysis | None, today: date | None = None) -> str:
    """What changed in the month-end closing since the user last heard: the month that just ended has
    its page (still waiting for its statements), or the statements closed a month. Once each; the first
    run only takes note. Without new documents filed here it looks again only when a month ended or the
    documents changed otherwise (the panel, the command line)."""
    today = today or date.today()
    state = _month_state(ws)
    known: dict[str, str] = state.get("months", {})
    if a is None and state and state.get("month") == month_of(today) and state.get("documents") == _fingerprint(ws):
        return ""
    if a is None:
        try:
            a = analyze(ws, write=True, today=today)
        except Busy:
            return ""
    ended = shift(month_of(today), -1)
    news = []
    for me in a.months[-3:] if state else []:
        before = known.get(me.month)
        if me.month == ended and before in (None, month_end.RUNNING) and me.status != month_end.CLOSED:
            news.append(f"{me.name} bitti, ay sonu raporu hazır ({me.label.lower()}).")
        elif me.status == month_end.CLOSED and before != month_end.CLOSED:
            news.append(f"{me.name} kapandı: bütün ekstreler geldi ve tutarlı.")
        elif me.status == month_end.CHECK and before != month_end.CHECK:
            news.append(f"{me.name} kapanışında kontrol gerekli: ay sonu raporuna bakın.")
    _save_month_state(
        ws,
        {"month": month_of(today), "documents": _fingerprint(ws), "months": {me.month: me.status for me in a.months}},
    )
    return " ".join(news)


def run(ws: Workspace, notify: bool = True, quiet: float = QUIET_SECONDS) -> Outcome:
    """Fetch the bank e-mails (when set up and due), file the inbox now (the plan is applied without
    being shown), rebuild the report, tell what changed in the month-end closing, notify."""
    _trim_log(ws)
    mail, alert, mail_log = _fetch_mail(ws)
    out, analysis = _file_inbox(ws, quiet)
    out.mail, out.mail_log = mail, mail_log
    out.months = month_news(ws, analysis)
    changed = out.filed or out.unreadable or out.trashed
    if mail:
        out.message = f"{mail}." if out.message == EMPTY else f"{mail}. {out.message}"
    if out.months:
        out.message = out.months if out.message == EMPTY else f"{out.message} {out.months}"
    if notify and (changed or alert or out.months):
        show_notification("İplikçi Nedim", out.message)
    return out


def show_notification(title: str, message: str) -> None:
    """A desktop notification (macOS, or Linux with notify-send). The text is passed as arguments,
    never pasted into a script."""
    if sys.platform == "darwin":
        script = [
            "-e",
            "on run argv",
            "-e",
            "display notification (item 1 of argv) with title (item 2 of argv)",
            "-e",
            "end run",
        ]
        subprocess.run(["/usr/bin/osascript", *script, message, title], capture_output=True, timeout=15, check=False)
    elif (notify_send := shutil.which("notify-send")) is not None:
        subprocess.run([notify_send, "--app-name", title, title, message], capture_output=True, timeout=15, check=False)


def _trim_log(ws: Workspace) -> None:
    log = ws.output / LOG_NAME
    if log.exists() and log.stat().st_size > _LOG_LIMIT:
        log.replace(log.with_name(LOG_NAME + ".1"))  # one older log is kept


# --- the background job, per operating system ------------------------------------------------------


def _command(python: Path, *extra: str) -> list[str]:
    # -I: the job reads untrusted documents, so nothing from the working folder is importable.
    return [str(python), "-I", "-m", "iplikci", "otomatik", *extra]


def _run(args: list[str]) -> subprocess.CompletedProcess:
    done = subprocess.run(args, capture_output=True, check=False)
    encoding = "oem" if os.name == "nt" else "utf-8"  # Windows tools answer in the console's code page
    return subprocess.CompletedProcess(
        args,
        done.returncode,
        done.stdout.decode(encoding, errors="replace"),
        done.stderr.decode(encoding, errors="replace"),
    )


class Launchd:
    """macOS: a launchd agent woken by a change in the inbox, at login and once an hour."""

    name = "launchd"

    def __init__(self, home: Path | None = None):
        self.path = (home or Path.home()) / "Library" / "LaunchAgents" / f"{LABEL}.plist"

    def _domain(self) -> str:
        return f"gui/{os.getuid()}"

    def install(self, ws: Workspace) -> str:
        log = ws.output / LOG_NAME
        agent = {
            "Label": LABEL,
            "ProgramArguments": _command(Path(sys.executable)),
            "WorkingDirectory": str(ws.base),
            "WatchPaths": [str(ws.inbox)],
            "RunAtLoad": True,
            "StartInterval": 3600,  # files dropped into a subfolder do not wake WatchPaths; e-mail is checked too
            "ThrottleInterval": 30,
            "ProcessType": "Background",
            "LowPriorityIO": True,
            "StandardOutPath": str(log),
            "StandardErrorPath": str(log),
            "EnvironmentVariables": {"PATH": "/usr/bin:/bin:/usr/sbin:/sbin"},
        }
        self.path.parent.mkdir(parents=True, exist_ok=True)
        if self.path.exists():
            _run(["launchctl", "bootout", f"{self._domain()}/{LABEL}"])
        self.path.write_bytes(plistlib.dumps(agent))
        done = _run(["launchctl", "bootstrap", self._domain(), str(self.path)])
        if done.returncode != 0:
            raise RuntimeError(f"launchctl bootstrap başarısız: {done.stderr.strip() or done.returncode}")
        return str(self.path)

    def uninstall(self) -> bool:
        if not self.path.exists():
            return False
        _run(["launchctl", "bootout", f"{self._domain()}/{LABEL}"])
        self.path.unlink()  # the agent file this program wrote, not a document
        return True

    def state(self) -> tuple[bool, bool]:
        installed = self.path.exists()
        return installed, installed and _run(["launchctl", "print", f"{self._domain()}/{LABEL}"]).returncode == 0


def _unit_value(text: str) -> str:
    return text.replace("%", "%%")  # systemd expands %-specifiers in unit files


def _unit_arg(text: str) -> str:
    """One ExecStart argument, quoted when it holds a space, a quote or a backslash."""
    value = _unit_value(text)
    if not re.search(r"[\s\"'\\]", value):
        return value
    return '"' + value.replace("\\", "\\\\").replace('"', '\\"') + '"'


class Systemd:
    """Linux: systemd user units: a path unit watching the inbox and a timer (at login, then hourly)
    start a oneshot service."""

    name = "systemd"

    def __init__(self, home: Path | None = None):
        config = Path(os.environ.get("XDG_CONFIG_HOME") or (home or Path.home()) / ".config")
        self.folder = config / "systemd" / "user"
        self.files = {kind: self.folder / f"{UNIT}.{kind}" for kind in ("service", "path", "timer")}

    def units(self, ws: Workspace) -> dict[str, str]:
        log = _unit_value(str(ws.output / LOG_NAME))
        command = " ".join(_unit_arg(a) for a in _command(Path(sys.executable)))
        return {
            "service": (
                "[Unit]\nDescription=İplikçi Nedim: yeni belgeleri e-postadan ve gelen kutusundan alıp yerleştirir\n\n"
                f"[Service]\nType=oneshot\nWorkingDirectory={_unit_value(str(ws.base))}\nExecStart={command}\n"
                # Where the system has no keyring, the e-mail password can be given in this file.
                f"EnvironmentFile=-%h/.config/{UNIT}/ortam\n"
                f"StandardOutput=append:{log}\nStandardError=append:{log}\nNice=10\nIOSchedulingClass=idle\n"
            ),
            "path": (
                "[Unit]\nDescription=İplikçi Nedim: gelen kutusunu izler\n\n"
                f"[Path]\nPathChanged={_unit_value(str(ws.inbox))}\nUnit={UNIT}.service\n\n"
                "[Install]\nWantedBy=default.target\n"
            ),
            "timer": (
                "[Unit]\nDescription=İplikçi Nedim: saatte bir e-postaya ve gelen kutusuna bakar\n\n"
                f"[Timer]\nOnStartupSec=2min\nOnUnitActiveSec=1h\nUnit={UNIT}.service\n\n"
                "[Install]\nWantedBy=timers.target\n"
            ),
        }

    def install(self, ws: Workspace) -> str:
        self.folder.mkdir(parents=True, exist_ok=True)
        for kind, text in self.units(ws).items():
            self.files[kind].write_text(text, encoding="utf-8")
        for args in (["daemon-reload"], ["enable", "--now", f"{UNIT}.path", f"{UNIT}.timer"]):
            done = _run(["systemctl", "--user", *args])
            if done.returncode != 0:
                reason = done.stderr.strip() or done.returncode
                raise RuntimeError(f"systemctl --user {' '.join(args)} başarısız: {reason}")
        return str(self.folder / f"{UNIT}.{{service,path,timer}}")

    def uninstall(self) -> bool:
        if not any(p.exists() for p in self.files.values()):
            return False
        _run(["systemctl", "--user", "disable", "--now", f"{UNIT}.path", f"{UNIT}.timer"])
        for path in self.files.values():
            path.unlink(missing_ok=True)  # unit files this program wrote
        _run(["systemctl", "--user", "daemon-reload"])
        return True

    def state(self) -> tuple[bool, bool]:
        installed = self.files["service"].exists()
        active = installed and _run(["systemctl", "--user", "is-active", "--quiet", f"{UNIT}.timer"]).returncode == 0
        return installed, active


class TaskScheduler:
    """Windows: a Task Scheduler task for the signed-in user, once an hour (and as soon as possible
    after a missed hour). It runs pythonw, so no console window opens, and writes its own log."""

    name = "Görev Zamanlayıcı"

    def task_xml(self, ws: Workspace, now: datetime | None = None) -> str:
        exe = Path(sys.executable)
        quiet = exe.with_name("pythonw.exe")
        command, *args = _command(quiet if quiet.exists() else exe, "--kayit", str(ws.output / LOG_NAME))
        arguments = subprocess.list2cmdline(args)  # Windows quoting rules
        domain, user = os.environ.get("USERDOMAIN"), os.environ.get("USERNAME") or getpass.getuser()
        who = f"{domain}\\{user}" if domain else user
        user_id = f"<UserId>{escape(who)}</UserId>" if user else ""  # the task belongs to this user only
        start = (now or datetime.now()).replace(microsecond=0)
        return f"""<?xml version="1.0" encoding="UTF-16"?>
<Task version="1.2" xmlns="http://schemas.microsoft.com/windows/2004/02/mit/task">
  <RegistrationInfo>
    <Description>İplikçi Nedim: yeni belgeleri e-postadan ve gelen kutusundan alıp yerleştirir</Description>
  </RegistrationInfo>
  <Triggers>
    <TimeTrigger>
      <Repetition><Interval>PT1H</Interval><StopAtDurationEnd>false</StopAtDurationEnd></Repetition>
      <StartBoundary>{start.isoformat()}</StartBoundary>
      <Enabled>true</Enabled>
    </TimeTrigger>
  </Triggers>
  <Principals>
    <Principal id="Author">
      {user_id}<LogonType>InteractiveToken</LogonType><RunLevel>LeastPrivilege</RunLevel>
    </Principal>
  </Principals>
  <Settings>
    <MultipleInstancesPolicy>IgnoreNew</MultipleInstancesPolicy>
    <DisallowStartIfOnBatteries>false</DisallowStartIfOnBatteries>
    <StopIfGoingOnBatteries>false</StopIfGoingOnBatteries>
    <StartWhenAvailable>true</StartWhenAvailable>
    <Enabled>true</Enabled>
    <ExecutionTimeLimit>PT1H</ExecutionTimeLimit>
    <Priority>7</Priority>
  </Settings>
  <Actions Context="Author">
    <Exec>
      <Command>{escape(command)}</Command>
      <Arguments>{escape(arguments)}</Arguments>
      <WorkingDirectory>{escape(str(ws.base))}</WorkingDirectory>
    </Exec>
  </Actions>
</Task>
"""

    def install(self, ws: Workspace) -> str:
        ws.output.mkdir(parents=True, exist_ok=True)
        definition = ws.output / ".gorev.xml"
        definition.write_text(self.task_xml(ws), encoding="utf-16")  # what schtasks reads, with a BOM
        try:
            done = _run(["schtasks", "/Create", "/TN", UNIT, "/XML", str(definition), "/F"])
        finally:
            definition.unlink(missing_ok=True)
        if done.returncode != 0:
            raise RuntimeError(f"schtasks /Create başarısız: {(done.stderr or done.stdout).strip() or done.returncode}")
        return f"{self.name} › {UNIT}"

    def uninstall(self) -> bool:
        if not self.state()[0]:
            return False
        _run(["schtasks", "/Delete", "/TN", UNIT, "/F"])
        return True

    def state(self) -> tuple[bool, bool]:
        installed = _run(["schtasks", "/Query", "/TN", UNIT]).returncode == 0
        return installed, installed


def scheduler(platform: str | None = None):
    platform = platform or sys.platform
    if platform == "darwin":
        return Launchd()
    if platform.startswith("linux"):
        return Systemd()
    if platform == "win32":
        return TaskScheduler()
    raise RuntimeError(
        f"bu işletim sisteminde ({platform}) arka plan görevi kurulamıyor; "
        "'iplikci otomatik' komutunu kendi zamanlayıcınızla çalıştırın"
    )


def install(ws: Workspace) -> str:
    """Install the background job (replacing an older one); returns where it is."""
    ws.inbox.mkdir(parents=True, exist_ok=True)
    ws.output.mkdir(parents=True, exist_ok=True)
    return scheduler().install(ws)


def uninstall() -> bool:
    return scheduler().uninstall()


def status(ws: Workspace) -> dict:
    try:
        job = scheduler()
    except RuntimeError as exc:
        return {"installed": False, "running": False, "scheduler": None, "note": str(exc)}
    installed, running = job.state()
    log = ws.output / LOG_NAME
    return {
        "installed": installed,
        "running": running,
        "scheduler": job.name,
        "inbox": str(ws.inbox),
        "log": str(log),
        "lastRun": datetime.fromtimestamp(log.stat().st_mtime).isoformat(timespec="seconds") if log.exists() else None,
    }
