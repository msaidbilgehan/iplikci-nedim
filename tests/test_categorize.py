from datetime import date

import pytest

from iplikci.categorize import (
    DEFAULT_RULES,
    OTHER_INCOME,
    TO_PEOPLE,
    Categorizer,
    RuleSet,
    clean_description,
    display_name,
)
from iplikci.domain.codes import AccountType, CategoryReason, Necessity, TransactionKind
from iplikci.domain.models import Account, Transaction

from conftest import PEOPLE_RULES

CARD = Account(id="a", label="Test Kart", bank="İş Bankası", type=AccountType.CREDIT_CARD)
OVERDRAFT = Account(id="b", label="Test Ek Hesap", bank="QNB", type=AccountType.OVERDRAFT)


@pytest.fixture(scope="module")
def cat():
    return Categorizer(DEFAULT_RULES)


def categorize(cat, description, kind=TransactionKind.PURCHASE, bank_category="", amount=100.0, account=CARD):
    t = Transaction(
        date=date(2025, 1, 1),
        description=description,
        amount=amount,
        kind=kind,
        account=account.id,
        bank_category=bank_category,
    )
    cat.apply(t, account)
    return t


@pytest.mark.parametrize(
    "description, category, merchant",
    [
        ("MIGROS MJET ORNEK SUBE ISTANBUL TR KAZANILAN MAXİPUAN:0,10", "Market & Gıda", "Migros"),
        ("SBX ORNEK CLUB ISTANBUL", "Kafe & Kahve", "Starbucks"),  # a named merchant beats the keyword CLUB
        ("PARAM*GETIR ARAC ISTANBUL", "Toplu Taşıma & Taksi", "Getir Araç"),
        ("PARAM. /GETIR", "Market & Gıda", "Getir"),
        ("ORNEKVERGIDAIRESIISTANBULTR", "Vergi & Resmi İşlemler", None),  # printed without spaces
        ("ÖRNEK PETROL MARKET", "Akaryakıt", None),  # earliest keyword wins
        ("ORNEK GIDA LOKANTA TARIM", "Restoran & Yemek", None),  # weak "GIDA" loses
        ("IYZICO*AMAZON TURKEY PE ISTANBUL TR", "Dijital Abonelikler", "Amazon Prime"),
        ("ORNEK ELEKTROMARKET", "Elektronik", None),
        ("UBER EATS YEMEK", "Restoran & Yemek", "Uber Eats"),  # food delivery, not a ride
        ("UBER *TRIP HELP.UBER.COM", "Toplu Taşıma & Taksi", "Uber"),
        ("IYZICO/SAHIBINDEN.COM ISTANBUL TR", "Online Alışveriş", "sahibinden.com"),
        ("ORNEK MALI MUSAVIRLIK ANONISTANBUL TR", "Muhasebe & Şirket Hizmetleri", None),
    ],
)
def test_rules(cat, description, category, merchant):
    t = categorize(cat, description)
    assert t.category == category
    if merchant:
        assert t.merchant == merchant


@pytest.mark.parametrize(
    "description",
    [
        "ORNEK KISI 2024 SUBAT KIRA ODEMESI",
        "EV KİRASI ARALIK",
        "ARALIK AYI KİRAYI GÖNDERDİM",
        "2 AYLIK KİRALARI",
        "KİRADAN KALAN",  # any ending: the rules list the words that are not rent, not the ones that are
        "KİRALIK DAİRE EKİM KİRASI",  # a later match still counts
    ],
)
def test_rent_is_kira_with_any_ending(cat, description):
    assert categorize(cat, description).category == "Kira"


@pytest.mark.parametrize(
    "description, category",
    [
        ("ORNEK KIRAATHANESİ İSTANBUL TR", "Kafe & Kahve"),  # a coffeehouse
        ("KİRALAMA ORNEK FİRMA", "Diğer Harcamalar"),  # renting a car or a thing, not a home
        ("KİRAZ ORNEK BUTİK", "Diğer Harcamalar"),
    ],
)
def test_words_the_shipped_rules_except_are_not_rent(cat, description, category):
    assert categorize(cat, description).category == category


EXCEPT_RULES = """
Ev:
  Kira:
    Ev Sahibi: [ORNEK EMLAK]
    _: [KIRA]
    _hariç: [KIRAATHANE, ORNEK EMLAKCI]
"""


@pytest.mark.parametrize(
    "description, matched",
    [
        ("ORNEK KIRAATHANESI", None),
        ("KIRAATHANE YANI KIRA ODEMESI", "KIRA"),  # the excepted word is passed over, the later KIRA counts
        ("ORNEK EMLAK EKIM", "ORNEK EMLAK"),
        ("ORNEK EMLAKCI KOMISYON", None),  # a named rule's match is passed over as well
        ("ORNEKEMLAKCIKOMISYON", None),  # and a multi-word one's squashed match
    ],
)
def test_an_excepted_word_is_passed_over(description, matched):
    rules = Categorizer.from_layers(RuleSet.parse(EXCEPT_RULES, "kurallar.yaml"))
    rule = rules.match(description)
    assert (rule.pattern if rule else None) == matched


def test_a_personal_exception_adds_to_the_shipped_ones(tmp_path, cat):
    personal = tmp_path / "personal.yaml"
    personal.write_text("Ev & Faturalar:\n  Kira:\n    _hariç: [KIRAÇ]  # a place in İstanbul\n", encoding="utf-8")
    layered = Categorizer.layered(personal)
    assert categorize(cat, "QWERTY LTD KIRAÇ ESENYURT").category == "Kira"
    assert categorize(layered, "QWERTY LTD KIRAÇ ESENYURT").category == "Diğer Harcamalar"
    assert categorize(layered, "ORNEK KIRAATHANESİ").category == "Kafe & Kahve"  # the shipped ones still hold
    assert categorize(layered, "EKİM KİRASI").category == "Kira"


@pytest.mark.parametrize(
    "category, amount, kind",
    [
        ("Hesaplar Arası Transfer", 500, TransactionKind.OWN_TRANSFER),  # a category the program keeps for a kind
        ("Döviz & Altın Alım-Satımı", -500, TransactionKind.OWN_TRANSFER),
        ("Nakit Avans & Çekim", 500, TransactionKind.CASH_ADVANCE),
        ("Kredi & Borç Anapara", 500, TransactionKind.LOAN_PRINCIPAL),
        ("Kredi Kartı Faizi", 500, TransactionKind.INTEREST_FEE),
        ("Kişilere Gönderilen", 500, TransactionKind.P2P_TRANSFER),  # by its `_tür` and the money's way
        ("Kişilere Gönderilen", -500, TransactionKind.INCOME),
        ("Kira", 500, TransactionKind.PURCHASE),
        ("Kira", -500, TransactionKind.REFUND),
    ],
)
def test_a_transfer_in_a_category_takes_the_kind_it_stands_for(cat, category, amount, kind):
    assert cat.kind_for(category, amount) == kind


def test_bank_category_beats_weak_keyword(cat):
    t = categorize(cat, "ORNEK GIDA", bank_category="Fast Food")
    assert t.category == "Restoran & Yemek"


def test_unmatched_falls_back(cat):
    t = categorize(cat, "XYZ QWERTY LTD ISTANBUL TR")
    assert (t.category, t.group, t.merchant, t.necessity) == (
        "Diğer Harcamalar",
        "Diğer",
        "Xyz Qwerty Ltd",
        Necessity.UNKNOWN,
    )


def test_fees_split_by_cause(cat):
    t = categorize(cat, "FAIZ TUTARI FZ:1.00 VR/FN:0.30", kind=TransactionKind.INTEREST_FEE)
    assert (t.category, t.group, t.merchant) == ("Kredi Kartı Faizi", "Banka & Finans", "İş Bankası faiz & ücretleri")
    assert (
        categorize(cat, "YILLIK UYELIK UCRETI", kind=TransactionKind.INTEREST_FEE).category == "Kart Aidatı & Ücretleri"
    )
    assert (
        categorize(
            cat, "Mevduat İşlemleri - Faiz Tahakkuku", kind=TransactionKind.INTEREST_FEE, account=OVERDRAFT
        ).category
        == "Ek Hesap (KMH) Faizi"
    )
    assert (
        categorize(cat, "FAST Ücreti", kind=TransactionKind.INTEREST_FEE, account=OVERDRAFT).category
        == "Transfer & İşlem Ücretleri"
    )


def test_other_kinds_get_finance_categories(cat):
    t = categorize(cat, "9999-123456 HESAPTAN AKTARIM", kind=TransactionKind.CARD_PAYMENT, amount=-500)
    assert (t.category, t.necessity) == ("Kart Borcu Ödemeleri", None)
    t = categorize(cat, "DOVIZ ALIS EUR", kind=TransactionKind.OWN_TRANSFER)
    assert t.category == "Döviz & Altın Alım-Satımı"


@pytest.mark.parametrize(
    "description, kind, level",
    [
        ("MIGROS ORNEK SUBE", TransactionKind.PURCHASE, Necessity.REQUIRED),
        ("STEAMGAMES.COM 1234567", TransactionKind.PURCHASE, Necessity.OPTIONAL),
        ("FAIZ TUTARI", TransactionKind.INTEREST_FEE, Necessity.UNNECESSARY),
        ("XYZ QWERTY", TransactionKind.PURCHASE, Necessity.UNKNOWN),
    ],
)
def test_necessity_levels(cat, description, kind, level):
    assert categorize(cat, description, kind=kind).necessity == level


def test_a_merchant_necessity_beats_its_category(tmp_path):
    rules = tmp_path / "k.yaml"
    rules.write_text(
        "Yeme & İçme:\n  Market & Gıda:\n    Örnek Market: [ORNEK MARKET]\n    _: [MARKET]\n"
        "_gereklilik:\n  Gerekli: [Market & Gıda]\n_gereklilik_işyeri:\n  Örnek Market: İsteğe bağlı\n",
        encoding="utf-8",
    )
    c = Categorizer(rules)
    assert categorize(c, "ORNEK MARKET ISTANBUL TR").necessity == Necessity.OPTIONAL
    assert categorize(c, "BASKA MARKET").necessity == Necessity.REQUIRED


def test_category_type_decides_transfer_kind(tmp_path):
    rules = tmp_path / "kategoriler.yaml"
    rules.write_text(PEOPLE_RULES, encoding="utf-8")
    cat = Categorizer(rules)

    def candidate(description, amount, counterparty=""):
        return Transaction(
            date=date(2025, 1, 1),
            description=description,
            amount=amount,
            kind="aday",
            account="b",
            counterparty=counterparty,
        )

    rent = candidate("FAST", 15000.0, "VELİ ÖRNEKSOY")
    assert cat.resolve_kind(rent) and (rent.kind, rent.category) == (TransactionKind.PURCHASE, "Kira")
    family_out, family_in = candidate("FAST", 500.0, "Ayşe Soyadoğlu"), candidate("FAST", -500.0, "Ayşe Soyadoğlu")
    assert cat.resolve_kind(family_out) and family_out.kind == TransactionKind.P2P_TRANSFER
    assert cat.resolve_kind(family_in) and family_in.kind == TransactionKind.INCOME
    debt = candidate("Ayşe Soyadoğlu borç iade", 1000.0)  # a named purpose beats the person
    assert cat.resolve_kind(debt) and debt.kind == TransactionKind.LOAN_PRINCIPAL
    pension = candidate("ANADOLU HAYAT EMEKLILIK", 750.0)
    assert cat.resolve_kind(pension) and pension.kind == TransactionKind.INVESTMENT
    assert not cat.resolve_kind(candidate("FAST", 300.0, "Tanımadığım Kişi"))


def test_groups_keep_file_order_and_other_last(cat):
    assert cat.groups[0] == "Yeme & İçme"
    assert cat.groups[-1] == "Diğer"
    assert "Banka & Finans" in cat.groups


def test_custom_rules_file(tmp_path):
    rules = tmp_path / "k.yaml"
    rules.write_text(
        "Ev:\n  Kira:\n    Ev sahibi: [MEHMET YILMAZ]\n  Market:\n    _: [MARKET]\n    _zayıf: [GIDA]\n"
        "_gereklilik:\n  Gerekli: [Kira]\n",
        encoding="utf-8",
    )
    c = Categorizer(rules)
    t = Transaction(
        date=date(2025, 1, 1), description="Mehmet Yılmaz kira", amount=10, kind=TransactionKind.PURCHASE, account="a"
    )
    c.apply(t, None)
    assert (t.group, t.category, t.merchant, t.necessity) == ("Ev", "Kira", "Ev sahibi", Necessity.REQUIRED)
    assert c.groups == ["Ev", "Banka & Finans", "Diğer"]


def test_unknown_necessity_level_is_reported(tmp_path):
    rules = tmp_path / "k.yaml"
    rules.write_text("_gereklilik:\n  Lüks: [Kira]\n", encoding="utf-8")
    with pytest.raises(ValueError, match="bilinmeyen gereklilik"):
        Categorizer(rules)


def test_clean_description():
    assert clean_description("ORNEK GIDA NAKLIYAT TISTANBUL TR") == "ORNEK GIDA NAKLIYAT T"
    assert clean_description("0001234567 MILLENICOM TELE FAT.ÖDE.") == "MILLENICOM TELE"
    assert display_name("ORNEK COFFEE İSTANBUL TR KAZANILAN MAXİPUAN:0,01") == "Ornek Coffee"


@pytest.mark.parametrize(
    "description, cleaned",
    [
        ("ORNEK KAFE VAN TR", "ORNEK KAFE"),  # any province, however short
        ("ORNEK BUFEESKISEHIR TR", "ORNEK BUFE"),  # glued to the name
        ("ORNEK KARAVAN", "ORNEK KARAVAN"),  # a short province name never cuts a word
        ("MEHMET AYDIN", "MEHMET AYDIN"),  # a surname that is also a province stays
        ("ORNEK LTD GUNAYDIN", "ORNEK LTD GUNAYDIN"),
    ],
)
def test_clean_description_cuts_the_place_but_not_a_name(description, cleaned):
    assert clean_description(description) == cleaned


def test_ended_payments_and_regular_categories(tmp_path):
    rules = tmp_path / "k.yaml"
    rules.write_text(
        "Abonelik:\n  Dijital Abonelikler:\n    Örnek Dergi: [ORNEK DERGI]\n"
        "_düzenli:\n  - Dijital Abonelikler\n"
        "_biten:\n  Örnek Dergi: 2025-10\n  Örnek Kulüp: 2025-01-21\n",  # YAML reads the second one as a date
        encoding="utf-8",
    )
    c = Categorizer(rules)
    assert c.ended == {"ORNEK DERGI": "2025-10", "ORNEK KULUP": "2025-01"}
    assert c.regular == {"Dijital Abonelikler"}


def test_ended_payment_needs_a_month(tmp_path):
    rules = tmp_path / "k.yaml"
    rules.write_text("_biten:\n  Örnek Dergi: geçen ay\n", encoding="utf-8")
    with pytest.raises(ValueError, match="YYYY-AA"):
        Categorizer(rules)


def test_shipped_rules_hold_no_personal_decisions(cat):
    # Payees of rent and dues, family, employers, ended payments and a merchant's necessity are the user's own.
    assert (cat.ended, cat.merchant_necessity) == ({}, {})
    assert not {"Gelir", "Aile & Kişiler"} & set(cat.groups)
    assert {c: t for c, t in cat.types.items() if t != "yatirim"} == {OTHER_INCOME: "gelir", TO_PEOPLE: "kisi"}


def test_shipped_rules_name_the_commitment_categories(cat):
    assert {"Kira", "Elektrik, Su & Doğalgaz", "Dijital Abonelikler"} <= cat.regular <= set(cat.categories)
    assert set(cat.necessity) <= set(cat.categories)


# --- layers: the user's rules over the defaults ---------------------------------------------------------

PERSONAL = """\
Yeme & İçme:
  Restoran & Yemek:
    Ofis Kantini: [MIGROS JET OFIS]
Kendi Grubum:
  Kulüp Aidatı:
    _: [MARKET KULUBU]
_gereklilik:
  Gereksiz: [Kafe & Kahve]
_biten:
  Starbucks: 2026-09
_banka_kategorileri:
  MARKET: Restoran & Yemek
"""


@pytest.fixture
def layered(tmp_path):
    personal = tmp_path / "personal.yaml"
    personal.write_text(PERSONAL, encoding="utf-8")
    return Categorizer.layered(personal)


def test_a_personal_rule_comes_before_the_defaults(layered):
    # The defaults' named Migros rule would take it; the user's rule is tried first.
    assert categorize(layered, "MIGROS JET OFIS ISTANBUL").category == "Restoran & Yemek"
    # Even a personal keyword beats a default named merchant: the whole personal layer goes first.
    assert categorize(layered, "MIGROS MARKET KULUBU").category == "Kulüp Aidatı"
    # Where no personal rule matches, the defaults decide as before.
    assert categorize(layered, "MIGROS ORNEK SUBE").merchant == "Migros"


def test_the_defaults_keep_their_group_order_and_colours(layered, cat):
    shared = [g for g in cat.groups if g != "Diğer"]
    assert layered.groups[: len(shared)] == shared
    assert layered.groups[-2:] == ["Kendi Grubum", "Diğer"]


def test_personal_decisions_override_the_defaults(layered, cat):
    assert cat.necessity["Kafe & Kahve"] != Necessity.UNNECESSARY
    assert layered.necessity["Kafe & Kahve"] == Necessity.UNNECESSARY
    assert layered.ended == {"STARBUCKS": "2026-09"}
    assert layered.regular == cat.regular  # the commitments of the defaults stay


def test_a_personal_bank_heading_wins(layered):
    assert categorize(layered, "ORNEK DUKKAN", bank_category="MARKET ALISVERISI").category == "Restoran & Yemek"


def test_without_a_personal_file_the_defaults_alone_decide(tmp_path, cat):
    alone = Categorizer.layered(tmp_path / "yok.yaml")
    assert alone.groups == cat.groups and alone.categories == cat.categories
    assert categorize(alone, "SBX ORNEK").merchant == "Starbucks"


def test_a_row_says_which_rule_of_which_file_named_it(layered):
    own = categorize(layered, "MIGROS JET OFIS ISTANBUL").reason
    assert (own.category, own.rule, own.layer) == (CategoryReason.RULE, "MIGROS JET OFIS", "personal.yaml")
    shipped = categorize(layered, "MIGROS ORNEK SUBE").reason
    assert (shipped.category, shipped.layer) == (CategoryReason.RULE, "default.yaml") and shipped.rule
    heading = categorize(layered, "ORNEK DUKKAN", bank_category="MARKET ALISVERISI").reason
    assert (heading.category, heading.rule) == (CategoryReason.BANK_CATEGORY, "")


def test_a_row_no_rule_names_and_a_fee_say_so(cat):
    assert categorize(cat, "XYZ QWERTY LTD ISTANBUL TR").reason.category is CategoryReason.UNCATEGORIZED
    assert categorize(cat, "ORNEK GIDA").reason.category is CategoryReason.WEAK_RULE
    fee = categorize(cat, "FAIZ TUTARI FZ:1.00 VR/FN:0.30", kind=TransactionKind.INTEREST_FEE)
    assert fee.reason.category is CategoryReason.FEE
    paid = categorize(cat, "9999-123456 HESAPTAN AKTARIM", kind=TransactionKind.CARD_PAYMENT, amount=-500)
    assert paid.reason.category is CategoryReason.KIND
