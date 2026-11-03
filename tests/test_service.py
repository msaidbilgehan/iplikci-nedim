"""The running service and the command line as its client: a real server on 127.0.0.1, in a thread."""

import os
import socket
import threading
import time

import pytest
import uvicorn

from iplikci import cli
from iplikci.api.app import create_app
from iplikci.app.workspace import Workspace
from iplikci.cli import service as service_cli
from iplikci.service import instance, manager, runner

TOKEN = "deneme-belirteci"


def free_port() -> int:
    with socket.socket() as s:
        s.bind(("127.0.0.1", 0))
        return int(s.getsockname()[1])


@pytest.fixture
def served(tmp_path, monkeypatch) -> Workspace:
    """A data folder whose service runs on a free port for the test."""
    home = tmp_path / "iplikci"
    home.mkdir()
    (home / "settings.toml").write_text(f"[server]\nport = {free_port()}\n", encoding="utf-8")
    monkeypatch.setenv("IPLIKCI_HOME", str(home))
    monkeypatch.setenv("IPLIKCI_API_TOKEN", TOKEN)
    ws = Workspace.load(home)
    server = uvicorn.Server(
        uvicorn.Config(create_app(runner.context(ws)), host="127.0.0.1", port=ws.port, log_level="warning")
    )
    thread = threading.Thread(target=server.run, daemon=True)
    thread.start()
    deadline = time.monotonic() + 10
    while not server.started:
        assert time.monotonic() < deadline, "the service did not start"
        time.sleep(0.02)
    yield ws
    server.should_exit = True
    thread.join(timeout=10)


def test_the_command_line_gets_a_login_link_from_the_running_service(served, capsys):
    assert cli.main(["ac", "--yazdir"]) == 0
    url = capsys.readouterr().out.strip()
    assert url.startswith(f"http://127.0.0.1:{served.port}/giris?anahtar=")


def test_the_status_reads_the_running_service(served, monkeypatch, capsys):
    monkeypatch.setattr(manager, "for_platform", lambda: manager.Launchd(served.home, uid=501))
    holder = instance.Holder(os.getpid(), served.port, "2026-11-01T07:30:00+00:00", "0.4.0")
    with instance.held(served.run, holder):
        assert cli.main(["servis", "durum"]) == 0
    out = capsys.readouterr().out
    assert f"Servis çalışıyor: http://127.0.0.1:{served.port} · süreç {os.getpid()}" in out and "sürüm 0.4.0" in out
    assert "Arka plan servisi: kurulu değil" in out
    assert "Kuyruk: 0 bekleyen, 0 başarısız iş" in out and "E-posta (IMAP): kurulu değil" in out
    assert "E-posta kapsamı: henüz banka iletisi yok" in out
    assert "Kurlar: henüz kur yok · geçmiş kurlar ilk belge gelince çekilir" in out
    assert "Disk: arşiv 0 B" in out and "Dikkat" not in out  # the service of this very data folder
    assert "Bildirimler: Masaüstü " in out and "Telegram açık, hazır değil" in out and "henüz bildirim yok" in out


def test_the_status_names_the_notification_channels_and_how_the_notifications_went():
    line = service_cli._notify_line(
        {
            "channels": [
                {"channel": "in_app", "on": True, "ready": True},
                {"channel": "desktop", "on": True, "ready": True},
                {"channel": "telegram", "on": True, "ready": False},
                {"channel": "email", "on": False, "ready": False},
            ],
            "counts": {"sent": 12, "failed": 1, "held": 0, "pending": 0, "digested": 2},
        }
    )
    assert line == (
        "Bildirimler: Masaüstü hazır, Telegram açık, hazır değil, E-posta kapalı · gönderildi 12, gönderilemedi 1, "
        "özetle gönderildi 2"
    )


def test_the_status_says_how_much_of_the_bank_mail_was_read_or_classified():
    line = service_cli._coverage_line({"total": 200, "unknown": 18})
    assert line == (
        "E-posta kapsamı: 200 banka iletisinin %91'i işlendi ya da bilerek sınıflandı; 18 tanesi henüz tanınmıyor"
    )
    # 89.9% stays below the target of 90%, as the System screen shows it.
    assert "%89'u" in service_cli._coverage_line({"total": 1000, "unknown": 101})


def test_the_command_line_says_when_the_service_is_not_running(tmp_path, monkeypatch, capsys):
    home = tmp_path / "bos"
    home.mkdir()
    (home / "settings.toml").write_text(f"[server]\nport = {free_port()}\n", encoding="utf-8")
    monkeypatch.setenv("IPLIKCI_HOME", str(home))
    monkeypatch.setenv("IPLIKCI_API_TOKEN", TOKEN)
    assert cli.main(["ac"]) == 1
    assert "yanıt vermiyor" in capsys.readouterr().err


def test_the_service_context_uses_the_token_it_finds_and_forgets_expired_sessions(ws, monkeypatch):
    monkeypatch.setenv("IPLIKCI_API_TOKEN", TOKEN)
    with ws.db() as db:
        db.execute(
            "INSERT INTO sessions VALUES (?, '2020-01-01T00:00:00+00:00', '2020-01-01T00:00:00+00:00', "
            "'2020-03-31T00:00:00+00:00')",
            ("0" * 64,),
        )
    context = runner.context(ws)
    assert context.token == TOKEN
    with ws.db() as db:
        assert db.scalar("SELECT count(*) FROM sessions") == 0
