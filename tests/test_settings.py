"""The data folder, settings.toml and the secrets (architecture §9, §20). Nothing here touches the real data
folder or the system keyring: the keyring is a fake module and every folder is a temporary one."""

import stat
import sys
import threading
import time
import types
from datetime import date
from pathlib import Path

import pytest

from iplikci.settings import config, locks, secrets
from iplikci.settings.paths import HOME_ENV, Layout, data_dir

# --- the data folder ----------------------------------------------------------------------------------


def test_iplikci_home_overrides_the_platform_folder(tmp_path):
    assert data_dir({HOME_ENV: str(tmp_path)}, "darwin") == tmp_path
    assert data_dir({HOME_ENV: "  "}, "darwin") == Path.home() / "Library" / "Application Support" / "iplikci"


def test_each_platform_has_its_own_data_folder(tmp_path):
    assert data_dir({}, "darwin") == Path.home() / "Library" / "Application Support" / "iplikci"
    assert data_dir({"XDG_DATA_HOME": str(tmp_path)}, "linux") == tmp_path / "iplikci"
    assert data_dir({}, "linux") == Path.home() / ".local" / "share" / "iplikci"
    assert data_dir({"LOCALAPPDATA": str(tmp_path)}, "win32") == tmp_path / "iplikci"


@pytest.mark.skipif(sys.platform == "win32", reason="POSIX permissions")
def test_the_data_folder_is_private_and_leaves_the_mvp_archive_alone(tmp_path):
    layout = Layout(tmp_path / "iplikci")
    layout.ensure()
    for folder in (layout.home, layout.vault, layout.objects, layout.staging, layout.rules, layout.inbox, layout.run):
        assert folder.is_dir()
        assert stat.S_IMODE(folder.stat().st_mode) == 0o700, folder
    assert not (layout.home / "archive").exists()
    layout.ensure()  # again: nothing changes, nothing fails


def test_the_layout_follows_the_architecture(tmp_path):
    layout = Layout(tmp_path)
    assert layout.settings == tmp_path / "settings.toml"
    assert layout.database == tmp_path / "iplikci.db"
    assert layout.objects == tmp_path / "vault" / "objects"
    assert layout.personal_rules == tmp_path / "rules" / "personal.yaml"
    assert layout.rules_history == tmp_path / "rules" / "history"


# --- settings.toml ------------------------------------------------------------------------------------

FULL = """\
[identity]
names = ["Örnek Kullanıcı"]
business_names = ["ÖRNEK TEKNOLOJİ A.Ş."]

[server]
port = 9000
remote = "tailscale"

[mail]
address = "kullanici@example.com"
connector = "browser_bridge"
folder = "auto"
start_day = 2024-01-01
bank_senders = ["Banka.com.tr", "@ikinci.com.tr", "banka.com.tr"]

[notify]
quiet_hours = ""
detail = {telegram = "minimal"}

[fx]
providers = ["document", "tcmb"]

[privacy]
mcp_masking = "accounts"

[backup]
keep_days = 30
"""


def settings_from(text: str, tmp_path: Path) -> config.Settings:
    path = tmp_path / "settings.toml"
    path.write_text(text, encoding="utf-8")
    return config.load(path)


def test_a_missing_settings_file_means_the_defaults(tmp_path):
    s = config.load(tmp_path / "settings.toml")
    assert s == config.Settings()
    assert s.server.port == config.DEFAULT_PORT
    assert s.identity.business_names == ()
    assert "teb.com.tr" in s.mail.bank_senders


def test_every_section_is_read(tmp_path):
    s = settings_from(FULL, tmp_path)
    assert s.identity.names == ("Örnek Kullanıcı",)
    assert s.identity.business_names == ("ÖRNEK TEKNOLOJİ A.Ş.",)
    assert (s.server.port, s.server.remote) == (9000, "tailscale")
    assert s.mail.connector == "browser_bridge"
    assert s.mail.start_day == date(2024, 1, 1)
    assert s.mail.bank_senders == ("banka.com.tr", "ikinci.com.tr")
    assert s.notify.quiet_hours == ""
    assert s.notify.detail == {"email": "full", "telegram": "minimal", "desktop": "summary"}
    assert s.fx.providers == ("document", "tcmb")
    assert s.privacy.mcp_masking == "accounts"
    assert s.backup.keep_days == 30


@pytest.mark.parametrize(
    ("text", "message"),
    [
        ("[identiy]\nnames = []\n", "bilinmeyen bölüm"),
        ("[identity]\nbussiness_names = []\n", "bilinmeyen ayar 'bussiness_names'"),
        ('[identity]\nbusiness_names = "ŞİRKET"\n', "bir ad listesi olmalı"),
        ("[identity]\nbusiness_names = [1]\n", "bir ad listesi olmalı"),
        ("[server]\nport = 70000\n", "1 ile 65535"),
        ('[server]\nremote = "on"\n', "off, tailscale"),
        ('[mail]\nbank_senders = ["banka com"]\n', "geçersiz alan adı"),
        ("[mail]\nstart_day = 2024-01-01T10:00:00\n", "bir tarih olmalı"),
        ('[mail]\naddress = "bir adres"\n', "e-posta adresi"),
        ('[notify]\nquiet_hours = "23-08"\n', "SS:DD-SS:DD"),
        ('[notify]\ndetail = {sms = "full"}\n', "kanal"),
        ("[backup]\nkeep_days = 0\n", "pozitif"),
        ("identity = 1\n", "bir tablo olmalı"),
        ("[identity\n", "okunamadı"),
    ],
)
def test_a_wrong_setting_is_an_error_that_names_it(tmp_path, text, message):
    with pytest.raises(config.SettingsError, match=message):
        settings_from(text, tmp_path)


CHANGES = [
    ("identity", {"business_names": ("Örnek Teknoloji A.Ş.",)}),
    ("backup", {"keep_days": 30}),
    ("mail", {"start_day": date(2026, 1, 1)}),
    ("privacy", {"mcp_masking": "accounts"}),
]


def _all_at_once(path: Path) -> list[Exception]:
    """Every change of CHANGES made at the same moment, each from a thread of its own; the ones that failed."""
    start = threading.Barrier(len(CHANGES))
    failed: list[Exception] = []

    def change(section: str, values: dict[str, object]) -> None:
        start.wait()
        try:
            config.update(path, section, values)
        except (OSError, config.SettingsError, locks.LockTimeout) as exc:
            failed.append(exc)

    threads = [threading.Thread(target=change, args=c) for c in CHANGES]
    for t in threads:
        t.start()
    for t in threads:
        t.join()
    return failed


def test_changes_made_at_the_same_moment_are_all_kept_and_the_file_stays_whole(tmp_path, monkeypatch):
    path = tmp_path / "settings.toml"
    parse = config.tomlkit.parse

    def slow(text: str):  # a wider window between reading the file and writing it back
        time.sleep(0.005)
        return parse(text)

    monkeypatch.setattr(config.tomlkit, "parse", slow)
    for _ in range(10):
        path.write_text("# kendi notum\n", encoding="utf-8")
        assert _all_at_once(path) == []
        saved = config.load(path)
        assert (saved.identity.business_names, saved.backup.keep_days) == (("Örnek Teknoloji A.Ş.",), 30)
        assert (saved.mail.start_day, saved.privacy.mcp_masking) == (date(2026, 1, 1), "accounts")
        assert path.read_text(encoding="utf-8").startswith("# kendi notum")
    assert sorted(p.name for p in tmp_path.iterdir()) == [".settings.toml.kilit", "settings.toml"]


# --- secrets ------------------------------------------------------------------------------------------


class FakeKeyring(types.SimpleNamespace):
    """What secrets.py uses of the keyring module, over a dict; available=False acts like a system without one."""

    class errors:  # mirrors keyring.errors
        class KeyringError(Exception):
            pass

        class NoKeyringError(KeyringError):
            pass

        class PasswordDeleteError(KeyringError):
            pass

    def __init__(self, available: bool = True):
        super().__init__(entries={}, available=available)

    def _check(self):
        if not self.available:
            raise self.errors.NoKeyringError("no backend")

    def get_password(self, service, account):
        self._check()
        return self.entries.get((service, account))

    def set_password(self, service, account, value):
        self._check()
        self.entries[(service, account)] = value

    def delete_password(self, service, account):
        self._check()
        if (service, account) not in self.entries:
            raise self.errors.PasswordDeleteError("none")
        del self.entries[(service, account)]


@pytest.fixture
def fake_keyring(monkeypatch) -> FakeKeyring:
    ring = FakeKeyring()
    monkeypatch.setattr(secrets, "_keyring", lambda: ring)
    monkeypatch.delenv("IPLIKCI_MAIL_PASSWORD", raising=False)
    return ring


def test_a_secret_lives_under_the_iplikci_service(fake_keyring):
    secret = secrets.mail("kullanici@example.com")
    assert secrets.store(secret, "abcd efgh")
    assert fake_keyring.entries == {("iplikci", "mail:kullanici@example.com"): "abcd efgh"}
    assert secrets.load(secret) == "abcd efgh"
    secrets.delete(secret)
    assert secrets.load(secret) is None
    secrets.delete(secret)  # forgetting twice is fine


def test_the_environment_variable_comes_first(fake_keyring, monkeypatch):
    secrets.store(secrets.TELEGRAM_BOT, "kayitli")
    monkeypatch.setenv("IPLIKCI_TELEGRAM_TOKEN", "ortamdan")
    assert secrets.load(secrets.TELEGRAM_BOT) == "ortamdan"


def test_a_system_without_a_keyring_falls_back_to_the_environment(monkeypatch):
    ring = FakeKeyring(available=False)
    monkeypatch.setattr(secrets, "_keyring", lambda: ring)
    monkeypatch.delenv("IPLIKCI_API_TOKEN", raising=False)
    assert secrets.store(secrets.API_TOKEN, "x") is False
    assert secrets.load(secrets.API_TOKEN) is None
    monkeypatch.setenv("IPLIKCI_API_TOKEN", "ortamdan")
    assert secrets.load(secrets.API_TOKEN) == "ortamdan"


def test_a_broken_keyring_is_reported_with_the_way_out(monkeypatch):
    ring = FakeKeyring()

    def broken(service, account):
        raise ring.errors.KeyringError("kilitli")

    ring.get_password = broken
    monkeypatch.setattr(secrets, "_keyring", lambda: ring)
    monkeypatch.delenv("IPLIKCI_EVDS_KEY", raising=False)
    with pytest.raises(secrets.SecretError, match="IPLIKCI_EVDS_KEY"):
        secrets.load(secrets.EVDS)
