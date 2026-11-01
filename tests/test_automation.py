"""The automatic run (e-mail first, then the inbox) and its background job on each operating system."""

import plistlib
import subprocess
import xml.etree.ElementTree as ET
from datetime import date
from pathlib import Path

import pytest

from iplikci import automation, email_fetch
from iplikci.app.workspace import Workspace
from iplikci.fakes import teb
from iplikci.storage import documents

from conftest import JANUARY, add, bank_mail, put

NAME = "2026-01-01 - 2026-01-31 TEB Vadesiz TL 123456789 Hesap Hareketleri.xls"
TASK = "{http://schemas.microsoft.com/windows/2004/02/mit/task}"


def kept(ws: Workspace) -> list[str]:
    with ws.db() as db:
        return [d.display_name for d in documents.every(db)]


@pytest.fixture
def calls(monkeypatch) -> list[list[str]]:
    """The scheduler commands the job would run (launchctl, systemctl, schtasks), all answered with success."""
    seen = []

    def run(args):
        seen.append(args)
        if "/XML" in args:  # schtasks reads the task definition while it is there
            seen.append(Path(args[args.index("/XML") + 1]).read_text(encoding="utf-16"))
        return subprocess.CompletedProcess(args, 0, "", "")

    monkeypatch.setattr(automation, "_run", run)
    return seen


def test_automatic_run_takes_the_inbox_into_the_vault(ws):
    assert automation.run(ws, notify=False, quiet=0).message == "gelen kutusu boş"
    put(ws.inbox / "TEBHareket.xls", teb.account_export(JANUARY))
    out = automation.run(ws, notify=False, quiet=0)
    assert (out.filed, out.trashed, out.unreadable) == (1, 0, 0)
    assert out.message.startswith("1 yeni belge arşive alındı (1 hesap dökümü)")
    assert kept(ws) == [NAME] and not any(ws.inbox.iterdir())
    assert (ws.exports / "gider_raporu.html").exists()


def test_automatic_run_fetches_the_bank_e_mails_first(ws, mail, monkeypatch):
    told = []
    monkeypatch.setattr(automation, "show_notification", lambda title, text: told.append(text))
    mail.messages[101] = bank_mail(teb.account_export(JANUARY))
    out = automation.run(ws, quiet=0)
    assert out.message == "E-postadan 1 yeni belge arşive alındı."
    assert told == [out.message]  # straight into the vault, not through the inbox: still told
    assert kept(ws) == [NAME] and (ws.exports / "gider_raporu.html").exists()


def test_the_mailbox_is_read_at_most_every_quarter_hour(ws, mail, monkeypatch):
    told = []
    monkeypatch.setattr(automation, "show_notification", lambda title, text: told.append(text))
    first = automation.run(ws, quiet=0)
    assert (first.message, first.mail_log) == ("gelen kutusu boş", "e-posta: yeni banka e-postası yok")
    assert told == []  # a check that found nothing is logged, not notified
    mail.commands.clear()
    second = automation.run(ws, quiet=0)  # e.g. started again by a file dropped into the inbox
    assert mail.commands == [] and second.mail_log == ""


def test_a_mail_problem_is_told_once(ws, mail, monkeypatch):
    told = []
    monkeypatch.setattr(automation, "show_notification", lambda title, text: told.append(text))
    monkeypatch.setattr(automation, "MAIL_EVERY", 0)

    def offline(acc):
        raise OSError("ağ yok")

    monkeypatch.setattr(email_fetch, "connect", offline)
    first = automation.run(ws, quiet=0)
    automation.run(ws, quiet=0)
    assert first.message.startswith("E-posta alınamadı: imap.gmail.com sunucusuna bağlanılamadı")
    assert len(told) == 1  # not again every hour while the problem lasts


def test_launchd_agent_watches_the_inbox(ws, tmp_path, calls):
    job = automation.Launchd(home=tmp_path)
    agent = plistlib.loads(Path(job.install(ws)).read_bytes())
    assert agent["WatchPaths"] == [str(ws.inbox)] and agent["WorkingDirectory"] == str(ws.home)
    assert agent["ProgramArguments"][1:] == ["-I", "-m", "iplikci", "otomatik", "--ev", str(ws.home)]
    assert agent["StandardOutPath"] == str(ws.logs / automation.LOG_NAME)
    assert agent["StartInterval"] == 3600 and calls[-1][:2] == ["launchctl", "bootstrap"]
    assert job.uninstall() and not job.path.exists()


def test_systemd_units_watch_the_inbox_and_run_hourly(tmp_path, calls, monkeypatch):
    monkeypatch.delenv("XDG_CONFIG_HOME", raising=False)
    ws = Workspace.load(tmp_path / "Veri %50")  # a space and a systemd specifier sign in the path
    job = automation.Systemd(home=tmp_path)
    job.install(ws)
    service, path, timer = (job.files[k].read_text(encoding="utf-8") for k in ("service", "path", "timer"))
    assert f"WorkingDirectory={tmp_path}/Veri %%50\n" in service
    assert (
        service.split("ExecStart=")[1].split("\n")[0].endswith(f' -I -m iplikci otomatik --ev "{tmp_path}/Veri %%50"')
    )
    assert f"PathChanged={tmp_path}/Veri %%50/inbox\n" in path
    assert "OnUnitActiveSec=1h" in timer and "Type=oneshot" in service
    assert ["systemctl", "--user", "enable", "--now", "iplikci.path", "iplikci.timer"] in calls
    assert job.uninstall() and not any(p.exists() for p in job.files.values())


def test_windows_task_runs_hourly_without_a_console_window(ws, tmp_path, calls, monkeypatch):
    python = put(tmp_path / "venv" / "Scripts" / "python.exe", "")
    put(python.with_name("pythonw.exe"), "")
    monkeypatch.setattr(automation.sys, "executable", str(python))
    monkeypatch.setenv("USERDOMAIN", "MASAUSTU")
    monkeypatch.setenv("USERNAME", "kullanici")
    automation.TaskScheduler().install(ws)
    create, definition = calls[0], calls[1]
    assert create[:3] == ["schtasks", "/Create", "/TN"] and not (ws.run / ".gorev.xml").exists()
    task = ET.fromstring(definition.encode("utf-16"))
    command = task.find(f"{TASK}Actions/{TASK}Exec/{TASK}Command").text
    arguments = task.find(f"{TASK}Actions/{TASK}Exec/{TASK}Arguments").text
    assert command.endswith("pythonw.exe")
    assert arguments.startswith("-I -m iplikci otomatik --ev ")
    assert str(ws.home) in arguments and str(ws.logs / automation.LOG_NAME) in arguments
    assert task.find(f"{TASK}Actions/{TASK}Exec/{TASK}WorkingDirectory").text == str(ws.home)
    assert task.find(f".//{TASK}Repetition/{TASK}Interval").text == "PT1H"
    assert task.find(f".//{TASK}Principal/{TASK}UserId").text == "MASAUSTU\\kullanici"
    assert task.find(f".//{TASK}Principal/{TASK}LogonType").text == "InteractiveToken"


@pytest.mark.parametrize(
    "platform, kind",
    [("darwin", automation.Launchd), ("linux", automation.Systemd), ("win32", automation.TaskScheduler)],
)
def test_each_system_gets_its_own_scheduler(platform, kind):
    assert isinstance(automation.scheduler(platform), kind)


def test_an_unknown_system_is_told_to_use_its_own_scheduler():
    with pytest.raises(RuntimeError, match="kendi zamanlayıcınızla"):
        automation.scheduler("sunos5")


def test_the_user_hears_once_when_a_month_ended_and_when_it_closed(ws):
    add(ws, "ocak.xls", teb.account_export(JANUARY, period="01/01/2026 - 25/01/2026"))
    assert automation.month_news(ws, None, today=date(2026, 1, 20)) == ""  # the first look only takes note
    assert automation.month_news(ws, None, today=date(2026, 1, 28)) == ""
    assert automation.month_news(ws, None, today=date(2026, 2, 2)) == (
        "Ocak 2026 bitti, ay sonu raporu hazır (ekstre bekleniyor)."
    )
    assert automation.month_news(ws, None, today=date(2026, 2, 3)) == ""  # told once
    assert (ws.exports / "ay-sonu" / "2026-01.html").exists()
    # The list for the rest of January comes (through the panel, say): January closes.
    add(ws, "subat.xls", teb.account_export([], period="26/01/2026 - 28/02/2026"))
    assert automation.month_news(ws, None, today=date(2026, 2, 4)) == (
        "Ocak 2026 kapandı: bütün ekstreler geldi ve tutarlı."
    )
