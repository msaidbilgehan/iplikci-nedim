"""Claude's memory (K30, ADR-0023): the notes kept across conversations, under their handles, within their bounds, every
change in the audit log by the note's name and never its text."""

import pytest

from iplikci.app import memory
from iplikci.domain.codes import Actor, MemoryKind
from iplikci.storage import audit, memories

USER, FEEDBACK, PROJECT = MemoryKind.USER, MemoryKind.FEEDBACK, MemoryKind.PROJECT


def note(ws, name: str, kind: MemoryKind = USER, description: str = "bir satır", body: str = "metin") -> memory.Written:
    return memory.write(ws, name, Actor.MCP, kind=kind, description=description, body=body)


def test_a_note_is_kept_under_its_name_and_the_index_lists_who_the_user_is_first(ws):
    note(ws, "tasarruf-hedefi", PROJECT, "Aralık sonuna kadar acil durum fonu", "Neden: ...")
    note(ws, "ozet-bicimi", FEEDBACK, "Özetleri tabloyla ister", "Nasıl: ...")
    written = note(ws, "meslek", USER, "Serbest çalışıyor, geliri düzensiz", "Ayda bir ya da iki ödeme alır.")
    assert written.saved == "created" and written.count == 3
    assert written.memory.created_at == written.memory.updated_at and written.memory.actor is Actor.MCP
    assert [m.name for m in memory.notes(ws)] == ["meslek", "ozet-bicimi", "tasarruf-hedefi"]


def test_writing_again_changes_what_is_given_and_keeps_the_rest_and_the_first_time(ws, monkeypatch):
    first = note(ws, "kira", description="Kira ayın 5'inde", body="Ev sahibine havale.").memory
    monkeypatch.setattr(memories, "now", lambda: "2026-12-01T09:00:00+00:00")
    again = memory.write(ws, "kira", Actor.USER, body="Ev sahibine FAST ile.")
    assert again.saved == "updated" and again.count == 1
    kept = again.memory
    assert (kept.description, kept.body, kept.kind) == ("Kira ayın 5'inde", "Ev sahibine FAST ile.", USER)
    assert (kept.created_at, kept.updated_at, kept.actor) == (first.created_at, "2026-12-01T09:00:00+00:00", Actor.USER)


def test_the_same_note_written_again_changes_nothing_and_records_nothing(ws):
    first = note(ws, "kira", body="Ev sahibine havale.")
    same = memory.write(ws, "kira", Actor.MCP, kind=USER, description=" bir   satır ", body="Ev sahibine havale.\n")
    assert same.saved == "unchanged" and same.memory == first.memory
    with ws.db() as db:
        assert [(e.action, e.target) for e in audit.entries(db)] == [(memories.WRITTEN, "kira")]


def test_a_new_note_needs_its_kind_line_and_text_and_a_kept_one_something_to_change(ws):
    with pytest.raises(memory.Refused, match="şunlar da gerekir: kind, body"):
        memory.write(ws, "kira", Actor.MCP, description="satır")
    note(ws, "kira")
    with pytest.raises(memory.Refused, match="Neyin değişeceğini"):
        memory.write(ws, "kira", Actor.MCP)


@pytest.mark.parametrize("name", ["Kira", "kira odemesi", "kira_odemesi", "kira-ödemesi", "-kira", "kira--x", "a" * 65])
def test_a_name_is_a_short_kebab_case_handle(ws, name):
    with pytest.raises(memory.Refused, match="küçük harf, rakam ve tire"):
        note(ws, name)


def test_the_line_is_one_line_and_the_text_is_never_empty_or_too_long(ws):
    kept = note(ws, "kira", description="Kira\n  ayın 5'inde", body="  Ev sahibine havale.  ").memory
    assert (kept.description, kept.body) == ("Kira ayın 5'inde", "Ev sahibine havale.")
    for given, said in (
        ({"description": " \n "}, "description boş olamaz"),
        ({"description": "x" * (memory.DESCRIPTION_LONGEST + 1)}, "description en çok 200"),
        ({"body": "\n"}, "body boş olamaz"),
        ({"body": "x" * (memory.BODY_LONGEST + 1)}, "body en çok 4000"),
    ):
        with pytest.raises(memory.Refused, match=said):
            memory.write(ws, "kira", Actor.MCP, **given)


def test_no_more_notes_than_the_index_can_hold_but_a_kept_one_still_changes(ws, monkeypatch):
    monkeypatch.setattr(memory, "MOST", 2)
    note(ws, "bir")
    note(ws, "iki")
    with pytest.raises(memory.Refused, match="en çok 2 not"):
        note(ws, "uc")
    assert memory.write(ws, "iki", Actor.MCP, body="yeni metin").saved == "updated"


def test_the_notes_named_come_in_their_order_with_the_names_no_note_has(ws):
    note(ws, "kira")
    note(ws, "meslek")
    found, missing = memory.read(ws, ["meslek", "yok", "kira", "meslek"])
    assert [m.name for m in found] == ["meslek", "kira"] and missing == ["yok"]


def test_a_search_finds_the_notes_of_any_part_in_their_name_line_or_text_the_newest_first(ws, monkeypatch):
    times = iter(["2026-11-01T10:00:00+00:00", "2026-11-02T10:00:00+00:00", "2026-11-03T10:00:00+00:00"])
    monkeypatch.setattr(memories, "now", lambda: next(times))
    note(ws, "kira-odemesi", description="Kira", body="Ev sahibine her ay havale.")
    note(ws, "market", description="Haftalık market alışverişi", body="Cumartesi günleri.")
    note(ws, "araba", description="Arabanın sigortası", body="KASKO Mart'ta yenilenir.")
    assert [m.name for m in memory.search(ws, "ÖDEMESİ")] == ["kira-odemesi"]  # folded, in the name
    assert [m.name for m in memory.search(ws, "kasko, market")] == ["araba", "market"]
    assert [m.name for m in memory.search(ws, "her ay")] == ["kira-odemesi"]  # both words, anywhere
    assert memory.search(ws, "yat") == []
    with pytest.raises(memory.Refused, match="Aranacak"):
        memory.search(ws, " , ")


def test_a_note_taken_away_is_gone_and_the_log_names_it_never_its_text(ws):
    note(ws, "kira", description="Gizli satır", body="Gizli metin")
    gone = memory.remove(ws, "kira", Actor.USER)
    assert gone.body == "Gizli metin" and memory.notes(ws) == [] and memory.count(ws) == 0
    with pytest.raises(memory.NotFound):
        memory.remove(ws, "kira", Actor.USER)
    with ws.db() as db:
        entries = audit.entries(db)
    assert [(e.actor, e.action, e.target) for e in entries] == [
        (Actor.MCP, memories.WRITTEN, "kira"),
        (Actor.USER, memories.REMOVED, "kira"),
    ]
    assert entries[0].detail == {"created": True}
    assert "Gizli" not in repr([e.detail for e in entries])
