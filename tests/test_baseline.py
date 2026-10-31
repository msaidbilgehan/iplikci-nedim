"""The verification baseline: the demo workspace's golden file, the regression rules and the commands.

After a deliberate change to the demo or the analysis, rewrite the golden file and review its diff:
    IPLIKCI_UPDATE_GOLDEN=1 uv run pytest tests/test_baseline.py
"""

import copy
import json
import os
from pathlib import Path

import pytest

from iplikci import baseline, demo, duzenle
from iplikci.cli import main
from iplikci.workspace import HOME_ENV, Workspace, analyze

GOLDEN = Path(__file__).parent / "golden" / "demo_baseline.json"


@pytest.fixture(scope="module")
def demo_baseline(tmp_path_factory) -> dict:
    ws = Workspace.load(demo.build(tmp_path_factory.mktemp("demo")))
    a = analyze(ws, use_cache=False, today=demo.AS_OF)
    return baseline.take(a.dataset, a.stats, a.months, demo.AS_OF)


def test_the_demo_workspace_keeps_its_golden_baseline(demo_baseline):
    text = baseline.dumps(demo_baseline)
    if os.environ.get("IPLIKCI_UPDATE_GOLDEN"):
        GOLDEN.parent.mkdir(exist_ok=True)
        GOLDEN.write_text(text, encoding="utf-8")
    assert text == GOLDEN.read_text(encoding="utf-8")


def test_the_demo_documents_are_already_where_the_organizer_files_them(tmp_path):
    ws = Workspace.load(demo.build(tmp_path))
    items = duzenle.plan([ws.documents], ws.documents, None)
    assert items and all(it.action == duzenle.KEEP and it.target == it.path for it in items)


def test_the_demo_is_built_only_into_an_empty_folder(tmp_path):
    (tmp_path / "not.txt").write_text("kullanıcının dosyası", encoding="utf-8")
    with pytest.raises(FileExistsError):
        demo.build(tmp_path)
    assert [p.name for p in tmp_path.iterdir()] == ["not.txt"]


# --- comparing two baselines -------------------------------------------------------------------------


def changed(demo_baseline: dict, edit) -> list[baseline.Change]:
    after = copy.deepcopy(demo_baseline)
    edit(after)
    return baseline.compare(demo_baseline, after)


def test_an_unchanged_baseline_reports_nothing(demo_baseline):
    assert baseline.compare(demo_baseline, copy.deepcopy(demo_baseline)) == []


def test_fewer_verified_lists_are_a_regression(demo_baseline):
    def lose_one(b):
        b["statements"]["lists"]["verified"] -= 1
        b["statements"]["unverified"] = ["TEB Vadesiz TL 123456789 2026-06-30: bakiye 40/41 (liste.xls)"]

    changes = changed(demo_baseline, lose_one)
    assert [(c.label, c.regression) for c in changes] == [
        ("Hesap dökümleri: doğrulanan", True),
        ("Doğrulanamayan ekstre", True),
    ]


def test_a_new_unreadable_document_is_a_regression(demo_baseline):
    def break_one(b):
        b["documents"]["by_status"]["hata"] = 1
        b["documents"]["unreadable"] = ["belge.pdf: şifreli PDF"]

    assert all(c.regression for c in changed(demo_baseline, break_one))


def test_a_closed_month_reopening_is_a_regression_unless_new_documents_came(demo_baseline):
    def reopen(b):
        b["months"]["2026-03"] = "eksik"

    [change] = changed(demo_baseline, reopen)
    assert (change.label, change.before, change.after, change.regression) == (
        "Mart 2026",
        "Kapandı",
        "Belge eksik",
        True,
    )

    def reopen_with_a_new_document(b):
        reopen(b)
        b["documents"]["unique"] += 1

    assert not any(c.regression for c in changed(demo_baseline, reopen_with_a_new_document))


def test_more_spending_is_reported_but_is_no_regression(demo_baseline):
    def spend(b):
        b["expenses"]["total"] = "999999.00"

    [change] = changed(demo_baseline, spend)
    assert (change.label, change.regression) == ("Son 12 ay gider", False)


# --- the commands -----------------------------------------------------------------------------------


@pytest.fixture
def demo_home(tmp_path, monkeypatch) -> Path:
    home = tmp_path / "demo"
    assert main(["dev", "demo", str(home)]) == 0
    monkeypatch.setenv(HOME_ENV, str(home))
    return home


VERIFY = ["dogrula", "--taban", "--tarih", demo.AS_OF.isoformat()]


def test_the_first_baseline_is_saved_and_a_second_run_finds_no_change(demo_home, capsys):
    assert main(VERIFY) == 0
    saved = demo_home / "cikti" / baseline.FILE
    assert json.loads(saved.read_text(encoding="utf-8"))["statements"]["lists"] == {
        "verified": 7,
        "total": 7,
        "by_account_type": {"Vadesiz hesap": 2, "Yatırım hesabı": 5},
    }
    assert main(VERIFY) == 0
    assert "Kayıtlı tabanla aynı." in capsys.readouterr().out


def test_a_regression_fails_and_keeps_the_saved_baseline_until_accepted(demo_home, capsys):
    assert main(VERIFY) == 0
    saved = demo_home / "cikti" / baseline.FILE
    better = json.loads(saved.read_text(encoding="utf-8"))
    better["statements"]["lists"]["verified"] += 1  # as if one more list had verified before
    saved.write_text(baseline.dumps(better), encoding="utf-8")
    assert main(VERIFY) == 1
    assert json.loads(saved.read_text(encoding="utf-8")) == better
    assert "1 gerileme var" in capsys.readouterr().err
    assert main([*VERIFY, "--kabul"]) == 0
    assert json.loads(saved.read_text(encoding="utf-8"))["statements"]["lists"]["verified"] == 7


def test_verify_needs_to_be_told_what_to_check(demo_home):
    with pytest.raises(SystemExit) as stop:
        main(["dogrula"])
    assert stop.value.code == 2


def test_the_demo_command_needs_a_folder(monkeypatch):
    monkeypatch.delenv(HOME_ENV, raising=False)
    with pytest.raises(SystemExit) as stop:
        main(["dev", "demo"])
    assert stop.value.code == 2


def test_the_demo_command_refuses_a_folder_in_use(demo_home):
    with pytest.raises(SystemExit) as stop:
        main(["dev", "demo", str(demo_home)])
    assert stop.value.code == 2
