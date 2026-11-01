"""The archive of originals (ADR-0003): kept once by content, read-only, never replaced, removed only to the
Trash. The Trash here is the private folder conftest gives every test."""

import os
import stat
import sys
from datetime import date

import pytest

from iplikci.models import Account, ParseResult, Statement, Transaction
from iplikci.settings.paths import Layout
from iplikci.vault.names import display_name, display_path
from iplikci.vault.store import Vault, VaultError, sha256_of


@pytest.fixture
def vault(tmp_path) -> Vault:
    layout = Layout(tmp_path / "iplikci")
    layout.ensure()
    return Vault(layout)


def make_writable(path):
    os.chmod(path, 0o600)


def test_a_document_is_kept_once_under_its_sha256(vault):
    sha = vault.put(b"%PDF-1.4 ekstre")
    assert sha == sha256_of(b"%PDF-1.4 ekstre")
    path = vault.path(sha)
    assert path.relative_to(vault.layout.objects).parts == (sha[:2], sha[2:4], sha)
    assert vault.put(b"%PDF-1.4 ekstre") == sha
    assert list(vault.objects()) == [sha]
    assert vault.read(sha) == b"%PDF-1.4 ekstre"
    assert not list(vault.layout.staging.iterdir())  # no temporary file left behind


@pytest.mark.skipif(sys.platform == "win32", reason="POSIX permissions")
def test_an_object_is_read_only(vault):
    sha = vault.put(b"degismez")
    assert stat.S_IMODE(vault.path(sha).stat().st_mode) == 0o400


def test_a_file_is_copied_in_and_stays_where_it_was(vault, tmp_path):
    source = tmp_path / "liste.xls"
    source.write_bytes(b"<html>liste</html>")
    sha = vault.put_file(source)
    assert vault.read(sha) == b"<html>liste</html>"
    assert source.read_bytes() == b"<html>liste</html>"
    assert vault.put_file(source) == sha


def test_a_damaged_object_is_reported_and_never_replaced(vault):
    sha = vault.put(b"asil")
    make_writable(vault.path(sha))
    vault.path(sha).write_bytes(b"bozuk")
    with pytest.raises(VaultError, match="bozulmuş"):
        vault.read(sha)
    with pytest.raises(VaultError, match="bozulmuş"):
        vault.put(b"asil")
    assert vault.path(sha).read_bytes() == b"bozuk"  # the evidence stays for a look
    report = vault.verify()
    assert report.corrupt == [sha]
    assert not report.ok


def test_the_integrity_check_finds_what_does_not_belong(vault):
    good = vault.put(b"iyi")
    other = sha256_of(b"yanlis yer")
    misplaced = vault.layout.objects / "00" / "00" / other
    misplaced.parent.mkdir(parents=True)
    misplaced.write_bytes(b"yanlis yer")
    stray = vault.layout.objects / good[:2] / ".nesne-yarim"
    stray.write_bytes(b"yarim")
    report = vault.verify()
    assert (report.checked, report.misplaced, report.strays) == (1, [misplaced], [stray])
    assert not report.ok


@pytest.mark.skipif(sys.platform == "win32", reason="POSIX permissions")
def test_a_writable_object_is_noted_but_still_sound(vault):
    sha = vault.put(b"yazilabilir")
    make_writable(vault.path(sha))
    report = vault.verify()
    assert report.ok and report.writable == [sha]


def test_a_removed_object_goes_to_the_trash(vault, private_trash):
    sha = vault.put(b"kaldirilacak")
    where = vault.remove(sha)
    assert not vault.has(sha)
    assert where.is_relative_to(private_trash) and where.read_bytes() == b"kaldirilacak"
    with pytest.raises(VaultError):
        vault.remove(sha)


def test_staging_is_emptied_after_reading(vault):
    with vault.staging() as folder:
        (folder / "okunuyor.pdf").write_bytes(b"x")
        assert folder.parent == vault.layout.staging
    assert not folder.exists()


def test_derived_data_can_be_made_again(vault):
    sha = vault.put(b"sayfa")
    (vault.derived(sha) / "1.png").write_bytes(b"png")
    vault.drop_derived(sha)
    assert not (vault.layout.derived / sha).exists()
    assert vault.has(sha)


def test_an_invalid_name_is_never_a_path(vault):
    with pytest.raises(ValueError):
        vault.path("../../etc/passwd")


# --- readable names -------------------------------------------------------------------------------


def test_documents_are_named_after_the_organizer_scheme():
    card = Account("garanti-bonus-4321", "Garanti BBVA Bonus •4321", "Garanti BBVA", "Kredi kartı", "TL", "4321")
    statement = Statement(card.id, date(2026, 10, 5), "TL", "x.pdf", 0.0, 0.0)
    result = ParseResult("garanti", [card], [statement])
    assert str(display_path(result, ".pdf")) == (
        "Garanti BBVA/Bonus Kredi Kartı 4321/2026-10-05 Garanti Bonus 4321 Ekstre.pdf"
    )
    teb = Account("teb-123456789", "TEB Vadesiz TL 123456789", "TEB", "Vadesiz hesap", "TL", "123456789")
    receipt = Transaction(date(2026, 2, 14), "AİDAT", 1250.0, "aday", teb.id)
    assert display_name(ParseResult("teb", [teb], transactions=[receipt], title="Giden/FAST"), ".pdf") == (
        "2026-02-14 TEB Giden-FAST Dekont.pdf"
    )
