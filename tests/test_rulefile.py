"""Editing the user's rule file as text: the user's comments and layout survive every change."""

import pytest
import yaml

from iplikci import rulefile

from conftest import RULES


def test_new_merchant_goes_above_the_keywords_and_keeps_comments():
    text = rulefile.add_merchant_rule(RULES, "kafe & kahve", "Kahve Durağı", ["KAHVE DURAGI", "re:\\bKDURAK\\b"])
    lines = text.splitlines()
    i = lines.index('    Kahve Durağı: [KAHVE DURAGI, "re:\\\\bKDURAK\\\\b"]')
    assert lines[i + 1].startswith("    _: [KAHVE]")  # named rules first, as in the rest of the file
    assert "# Deneme kuralları" in text and "# isimli işletme" in text
    data = yaml.safe_load(text)
    assert data["Yeme & İçme"]["Kafe & Kahve"]["Kahve Durağı"] == ["KAHVE DURAGI", "re:\\bKDURAK\\b"]


def test_known_merchant_gets_more_patterns_and_keeps_its_comment():
    text = rulefile.add_merchant_rule(RULES, "Kafe & Kahve", "örnek kahve", ["ORNEKKAHVE", "ORNEK KAHVE"])
    assert "    Örnek Kahve: [ORNEK KAHVE, ORNEKKAHVE]  # isimli işletme\n" in text


def test_empty_category_gets_its_first_merchant():
    text = rulefile.add_merchant_rule(RULES, "Boş Kategori", "Yes", ["5555"])
    assert yaml.safe_load(text)["Yeme & İçme"]["Boş Kategori"] == {"Yes": ["5555"]}  # quoted: no bool, no int


def test_unknown_category_is_refused():
    with pytest.raises(ValueError, match="kategori yok"):
        rulefile.add_merchant_rule(RULES, "Gerekli", "X", ["X"])  # a necessity level, not a category


def test_ended_payment_is_added_updated_and_created():
    text = rulefile.add_ended(RULES, "Örnek Dergi", "2026-10", "kullanıcı iptal etti")
    assert "  Eski Abonelik: 2025-01  # örnek not\n  Örnek Dergi: 2026-10  # kullanıcı iptal etti\n" in text
    text = rulefile.add_ended(text, "eski abonelik", "2025-03")
    assert "  Eski Abonelik: 2025-03  # örnek not\n" in text  # same entry, old note kept
    fresh = rulefile.add_ended("Diğer:\n  Diğer Harcamalar: {}\n", "Örnek Müzik", "2026-09")
    assert yaml.safe_load(fresh)["_biten"] == {"Örnek Müzik": "2026-09"}
    with pytest.raises(ValueError):
        rulefile.add_ended(RULES, "Örnek Dergi", "2026-13")


def test_validate_reads_the_rules_like_the_program():
    rulefile.validate(RULES)
    rulefile.validate("")  # an empty personal file: the defaults alone
    with pytest.raises(ValueError, match="YAML"):
        rulefile.validate("Yeme: [")
    with pytest.raises(ValueError, match="gereklilik"):
        rulefile.validate("_gereklilik:\n  Şart: [Kira]\n")
    with pytest.raises(ValueError, match="kurallar okunamadı"):
        rulefile.validate('Grup:\n  Kategori:\n    İşyeri: ["re:("]\n')
    with pytest.raises(ValueError, match="eşlemelerinden"):
        rulefile.validate("- bir liste\n")


def test_a_rule_can_go_to_a_category_only_the_defaults_have():
    homes = {"Restoran & Yemek": "Yeme & İçme", "Akaryakıt": "Ulaşım & Araç"}
    text = rulefile.add_merchant_rule(RULES, "restoran & yemek", "Ofis Kantini", ["OFIS KANTIN"], homes)
    assert yaml.safe_load(text)["Yeme & İçme"]["Restoran & Yemek"] == {"Ofis Kantini": ["OFIS KANTIN"]}
    assert "# Deneme kuralları" in text  # the rest of the file is untouched
    text = rulefile.add_merchant_rule("", "Akaryakıt", "Ornek Petrol", ["ORNEK PETROL"], homes)
    assert text == "Ulaşım & Araç:\n  Akaryakıt:\n    Ornek Petrol: [ORNEK PETROL]\n"
    with pytest.raises(ValueError, match="kategori yok"):
        rulefile.add_merchant_rule("", "Uydurma", "X", ["X"], homes)


def test_replace_keeps_the_previous_file_in_the_history(tmp_path):
    rules = tmp_path / "personal.yaml"
    rules.write_text(RULES, encoding="utf-8")
    backup = rulefile.replace(rules, RULES + "\n# yeni\n", tmp_path / "history")
    assert backup is not None and backup.name.startswith("personal ")
    assert backup.read_text(encoding="utf-8") == RULES and rules.read_text(encoding="utf-8").endswith("# yeni\n")
    assert sorted(p.name for p in tmp_path.iterdir()) == ["history", "personal.yaml"]  # no temp file left


def test_the_first_personal_file_has_nothing_to_keep(tmp_path):
    rules = tmp_path / "rules" / "personal.yaml"
    assert rulefile.replace(rules, RULES, tmp_path / "rules" / "history") is None
    assert rules.read_text(encoding="utf-8") == RULES
    assert not (tmp_path / "rules" / "history").exists()
