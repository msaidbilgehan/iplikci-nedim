"""The background service in the system's service manager (architecture §19): what is registered on each system,
which commands run, one service per data folder, and the service's own log. launchctl, systemctl and schtasks are
stand-ins here; nothing reaches the real service manager."""

import json
import logging
import logging.handlers
import plistlib
import subprocess
import sys
import threading
import xml.etree.ElementTree as ET
from collections.abc import Sequence
from pathlib import Path

import pytest

from iplikci import cli
from iplikci.service import instance, logs, manager

TASK = "{http://schemas.microsoft.com/windows/2004/02/mit/task}"


class Tools:
    """launchctl, systemctl and schtasks as stand-ins: each command is recorded and answered with the exit code given
    for its first words (0 otherwise)."""

    def __init__(self, codes: dict[tuple[str, ...], int] | None = None) -> None:
        self.calls: list[list[str]] = []
        self.codes = codes or {}

    def __call__(self, args: Sequence[str]) -> manager.Completed:
        self.calls.append(list(args))
        for prefix, code in self.codes.items():
            if tuple(args[: len(prefix)]) == prefix:
                return manager.Completed(code, "", "hata ayrıntısı" if code else "")
        return manager.Completed(0, "", "")


@pytest.fixture
def program(tmp_path) -> manager.Program:
    return manager.Program(tmp_path / "araç" / "bin" / "python", tmp_path / "Uygulama Verisi" / "iplikci")


def test_the_service_runs_isolated_for_its_data_folder(program):
    assert program.arguments() == [
        str(program.python), "-I", "-X", "utf8", "-m", "iplikci", "servis", "calistir", "--ev", str(program.home)
    ]  # fmt: skip
    assert program.output == program.home / "logs" / "servis-cikti.log"


def test_launchd_keeps_the_agent_alive_and_starts_it_at_login(tmp_path, program):
    tools = Tools({("launchctl", "print"): 113})  # not loaded yet
    launchd = manager.Launchd(tmp_path / "ev", run=tools, uid=501)
    launchd.install(program)
    agent = plistlib.loads(launchd.path.read_bytes())
    assert launchd.path == tmp_path / "ev" / "Library" / "LaunchAgents" / "com.iplikci.service.plist"
    assert agent["Label"] == "com.iplikci.service" and agent["ProgramArguments"] == program.arguments()
    assert agent["RunAtLoad"] is True and agent["KeepAlive"] == {"SuccessfulExit": False}
    assert agent["Umask"] == 0o077 and agent["StandardErrorPath"] == str(program.output)
    assert tools.calls == [
        ["launchctl", "print", "gui/501/com.iplikci.service"],
        ["launchctl", "bootstrap", "gui/501", str(launchd.path)],
    ]
    assert launchd.installed()


def test_launchd_replaces_a_loaded_agent_and_restarts_it_in_place(tmp_path, program):
    tools = Tools()
    launchd = manager.Launchd(tmp_path, run=tools, uid=501)
    launchd.install(program)
    assert ["launchctl", "bootout", "gui/501/com.iplikci.service"] in tools.calls  # the old one stops first
    tools.calls.clear()
    launchd.restart()
    assert tools.calls[-1] == ["launchctl", "kickstart", "-k", "gui/501/com.iplikci.service"]


def test_launchd_says_why_it_refused(tmp_path, program):
    launchd = manager.Launchd(tmp_path, run=Tools({("launchctl", "print"): 113, ("launchctl", "bootstrap"): 5}))
    with pytest.raises(manager.ManagerError, match="launchctl bootstrap başarısız: hata ayrıntısı"):
        launchd.install(program)


def test_removing_the_agent_stops_it_and_deletes_only_its_own_file(tmp_path, program):
    tools = Tools()
    launchd = manager.Launchd(tmp_path, run=tools, uid=501)
    assert not launchd.uninstall()  # nothing to remove
    launchd.install(program)
    assert launchd.uninstall()
    assert not launchd.path.exists() and tools.calls[-1] == ["launchctl", "bootout", "gui/501/com.iplikci.service"]


def test_systemd_runs_a_user_unit_restarted_on_failure(tmp_path):
    odd = manager.Program(tmp_path / "ara ç" / "python", tmp_path / "veri %u")
    tools = Tools()
    systemd = manager.Systemd(tmp_path, run=tools, env={"XDG_CONFIG_HOME": str(tmp_path / "ayar")})
    systemd.install(odd)
    unit = systemd.path.read_text(encoding="utf-8")
    assert systemd.path == tmp_path / "ayar" / "systemd" / "user" / "iplikci.service"
    assert f'ExecStart="{tmp_path / "ara ç" / "python"}" -I -X utf8 -m iplikci servis calistir --ev ' in unit
    assert f'"{tmp_path}/veri %%u"' in unit  # quoted for the space, %% so systemd does not expand it
    assert "Restart=on-failure" in unit and "UMask=0077" in unit and "WantedBy=default.target" in unit
    assert tools.calls == [
        ["systemctl", "--user", "daemon-reload"],
        ["systemctl", "--user", "enable", "iplikci.service"],
        ["systemctl", "--user", "restart", "iplikci.service"],
    ]
    assert systemd.uninstall() and not systemd.path.exists()
    assert ["systemctl", "--user", "disable", "--now", "iplikci.service"] in tools.calls


def test_systemd_says_which_step_failed(tmp_path, program):
    systemd = manager.Systemd(tmp_path, run=Tools({("systemctl", "--user", "enable"): 1}), env={})
    with pytest.raises(manager.ManagerError, match="systemctl --user enable iplikci.service başarısız"):
        systemd.install(program)


def test_the_windows_task_starts_at_logon_without_a_time_limit_and_restarts_after_an_error(tmp_path):
    python = tmp_path / "Python" / "python.exe"
    python.parent.mkdir()
    (python.parent / "pythonw.exe").write_bytes(b"")
    program = manager.Program(python, tmp_path / "Veri Klasörü")
    scheduler = manager.TaskScheduler(run=Tools(), env={"USERDOMAIN": "EV", "USERNAME": "deneme"})
    task = ET.fromstring(scheduler.task_xml(program).split("\n", 1)[1])  # the declaration names UTF-16
    assert task.findtext(f"{TASK}Triggers/{TASK}LogonTrigger/{TASK}UserId") == "EV\\deneme"
    assert task.findtext(f"{TASK}Settings/{TASK}ExecutionTimeLimit") == "PT0S"
    assert task.findtext(f"{TASK}Settings/{TASK}RestartOnFailure/{TASK}Interval") == "PT1M"
    assert task.findtext(f"{TASK}Actions/{TASK}Exec/{TASK}Command") == str(python.parent / "pythonw.exe")
    arguments = task.findtext(f"{TASK}Actions/{TASK}Exec/{TASK}Arguments")
    assert arguments == subprocess.list2cmdline(program.arguments()[1:])


def test_the_windows_task_is_created_from_a_definition_that_does_not_stay_behind(tmp_path, program):
    seen: list[str] = []
    tools = Tools()

    def run(args: Sequence[str]) -> manager.Completed:
        if "/XML" in args:
            seen.append(Path(args[args.index("/XML") + 1]).read_text(encoding="utf-16"))
        return tools(args)

    manager.TaskScheduler(run=run, env={"USERNAME": "deneme"}).install(program)
    assert "<LogonTrigger>" in seen[0]
    assert [c[1] for c in tools.calls] == ["/Create", "/End", "/Run"]
    assert not list((program.home / "run").iterdir())


def test_each_system_has_its_service_manager():
    assert isinstance(manager.for_platform("darwin"), manager.Launchd)
    assert isinstance(manager.for_platform("linux"), manager.Systemd)
    assert isinstance(manager.for_platform("win32"), manager.TaskScheduler)
    with pytest.raises(manager.ManagerError, match="kurulamıyor"):
        manager.for_platform("plan9")


def test_a_development_folder_is_recognised_and_an_installed_copy_is_not(tmp_path):
    repo = tmp_path / "depo"
    (repo / "src" / "iplikci" / "service").mkdir(parents=True)
    (repo / "pyproject.toml").write_text("[project]\n", encoding="utf-8")
    assert manager.development_folder(repo / "src" / "iplikci" / "service" / "manager.py") == repo
    installed = tmp_path / "lib" / "python3.13" / "site-packages" / "iplikci" / "service" / "manager.py"
    assert manager.development_folder(installed) is None


def test_the_service_is_never_registered_from_a_development_folder(ws, monkeypatch, capsys):
    tools = Tools()
    monkeypatch.setattr(manager, "for_platform", lambda: manager.Launchd(ws.home, run=tools, uid=501))
    monkeypatch.setattr(manager, "development_folder", lambda: Path("/depo"))
    assert cli.main(["servis", "kur"]) == 1
    assert "geliştirme klasöründen kurulmaz: bu iplikci /depo klasöründen" in capsys.readouterr().err
    assert tools.calls == []


def test_the_command_line_registers_the_installed_copy_for_its_data_folder(ws, monkeypatch, capsys):
    tools = Tools({("launchctl", "print"): 113})
    launchd = manager.Launchd(ws.home, run=tools, uid=501)
    monkeypatch.setattr(manager, "for_platform", lambda: launchd)
    monkeypatch.setattr(manager, "development_folder", lambda: None)
    monkeypatch.setenv("IPLIKCI_HOME", str(ws.home))
    assert cli.main(["servis", "kur"]) == 0
    assert plistlib.loads(launchd.path.read_bytes())["ProgramArguments"][-2:] == ["--ev", str(ws.home)]
    assert "Arka plan servisi kuruldu (launchd)" in capsys.readouterr().out
    assert cli.main(["servis", "kaldir"]) == 0 and not launchd.path.exists()
    assert cli.main(["servis", "yeniden-baslat"]) == 1
    assert "kurulu değil" in capsys.readouterr().err


def test_one_service_per_data_folder(tmp_path):
    first = instance.Holder(111, 8643, "2026-11-01T10:00:00+00:00", "0.4.0")
    assert instance.current(tmp_path) is None
    second = instance.Holder(222, 8643, "", "0.4.0")
    with instance.held(tmp_path, first):
        assert instance.current(tmp_path) == first
        refused = pytest.raises(instance.AlreadyRunning, match=r"zaten çalışıyor \(süreç 111, http://127.0.0.1:8643\)")
        with refused, instance.held(tmp_path, second, wait=0):
            pass
    assert instance.current(tmp_path) is None
    assert not (tmp_path / instance.HOLDER_NAME).exists()


def test_a_service_that_dies_leaves_no_lock_behind(tmp_path):
    holder = (
        "import sys, time\nfrom pathlib import Path\nfrom iplikci.service import instance\n"
        "with instance.held(Path(sys.argv[1]), instance.Holder(42, 8643, '', '')):\n"
        "    print('hazir', flush=True)\n    time.sleep(60)\n"
    )
    child = subprocess.Popen([sys.executable, "-I", "-c", holder, str(tmp_path)], stdout=subprocess.PIPE, text=True)
    try:
        assert child.stdout is not None and child.stdout.readline().strip() == "hazir"
        assert instance.current(tmp_path) == instance.Holder(42, 8643, "", "")
    finally:
        child.kill()
        child.wait(timeout=10)
    assert instance.current(tmp_path) is None  # the system freed the lock with the process


def test_the_command_line_refuses_a_second_service_for_the_same_folder(ws, monkeypatch, capsys):
    monkeypatch.setenv("IPLIKCI_HOME", str(ws.home))
    monkeypatch.setattr(instance, "WAIT_SECONDS", 0.0)
    with instance.held(ws.run, instance.Holder(111, ws.port, "", "0.4.0")):
        assert cli.main(["servis", "calistir"]) == 1
    assert "Bu veri klasörünün servisi zaten çalışıyor (süreç 111" in capsys.readouterr().err


def test_the_status_says_when_the_service_is_not_running(ws, monkeypatch, capsys):
    monkeypatch.setenv("IPLIKCI_HOME", str(ws.home))
    monkeypatch.setattr(manager, "for_platform", lambda: manager.Launchd(ws.home, run=Tools(), uid=501))
    assert cli.main(["servis", "durum"]) == 1
    out = capsys.readouterr().out
    assert "Servis çalışmıyor." in out and "Arka plan servisi: kurulu değil" in out
    assert str(ws.logs / "servis.log") in out


def test_the_service_log_is_json_lines_with_ids_and_numbers(tmp_path):
    with logs.kept(tmp_path):
        logging.getLogger("iplikci.jobs").info("job %d (%s) done", 7, "refresh")
        logging.getLogger("iplikci.jobs").debug("not kept")
        try:
            raise ValueError("bozuk")
        except ValueError:
            logging.getLogger("iplikci.jobs").exception("job %d failed", 8)
    first, second = (json.loads(line) for line in (tmp_path / "servis.log").read_text(encoding="utf-8").splitlines())
    assert (first["level"], first["logger"], first["message"]) == ("info", "iplikci.jobs", "job 7 (refresh) done")
    assert second["message"] == "job 8 failed" and "ValueError: bozuk" in second["traceback"]
    assert not any(isinstance(h, logging.handlers.RotatingFileHandler) for h in logging.getLogger().handlers)


def test_a_thread_that_dies_leaves_its_error_in_the_log(tmp_path):
    def die() -> None:
        raise RuntimeError("beklenmedik")

    with logs.kept(tmp_path):
        thread = threading.Thread(target=die, name="iplikci-deneme")
        thread.start()
        thread.join()
    [entry] = (json.loads(line) for line in (tmp_path / "servis.log").read_text(encoding="utf-8").splitlines())
    assert entry["message"] == "thread iplikci-deneme stopped on an error"
    assert "RuntimeError: beklenmedik" in entry["traceback"]


def test_what_the_process_printed_is_kept_to_one_older_file(tmp_path, monkeypatch):
    monkeypatch.setattr(logs, "MAX_BYTES", 10)
    output = tmp_path / logs.OUTPUT_NAME
    output.write_text("x" * 20, encoding="utf-8")
    logs.trim(output)
    assert not output.exists() and (tmp_path / "servis-cikti.log.1").read_text(encoding="utf-8") == "x" * 20
