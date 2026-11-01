"""The mailbox's inventory: kept e-mails counted by sender domain and subject template (Phase 4)."""

from email.message import EmailMessage

from iplikci.app import mail, reading
from iplikci.app.inventory import mail_coverage, mail_inventory, subject_template, write_csv
from iplikci.fakes import vakifbank
from iplikci.parsers.common import MESSAGE_REASON, set_business_names
from iplikci.settings.config import BANK_SENDERS

from conftest import ADDRESS, FEBRUARY, bank_mail


def notice(subject: str, sender: str, day: str = "Mon, 02 Feb 2026 10:00:00 +0300") -> bytes:
    domain = sender.rpartition("@")[2]
    msg = EmailMessage()
    msg["Authentication-Results"] = f"mx.google.com; dmarc=pass (p=REJECT) header.from={domain}"
    msg["From"] = f"Banka <{sender}>"
    msg["To"] = ADDRESS
    msg["Subject"] = subject
    msg["Date"] = day
    msg.set_content(f"{subject}: bu bir deneme iletisidir.")
    return msg.as_bytes()


def test_a_subject_template_masks_numbers_and_month_names():
    assert subject_template("1234 **** **** 5678 - Ocak 2026 Maximum Kredi Kartı Hesap Özeti") == (
        "# **** **** # - <ay> # Maximum Kredi Kartı Hesap Özeti"
    )
    assert subject_template("  Şubat'ta   %5 bonus!  ") == "<ay>'ta %# bonus!"
    assert subject_template("Mart 2026, AĞUSTOS: ekstre") == "<ay> #, <ay>: ekstre"
    assert subject_template("Kasımpaşa şubesi") == "Kasımpaşa şubesi"  # only a whole word is a month


def test_the_kept_e_mails_are_counted_by_sender_and_template(ws, tmp_path):
    senders = ("teb.com.tr", "banka.example")
    for raw in (
        notice("Ocak 2026 Hisse Senedi Ekstreniz", "ekstre@banka.example"),
        notice("Şubat 2026 Hisse Senedi Ekstreniz", "ekstre@banka.example", "Mon, 02 Mar 2026 10:00:00 +0300"),
        notice("Size özel %5 bonus!", "kampanya@banka.example"),
        bank_mail(FEBRUARY),
    ):
        assert mail.take(ws, raw, senders).taken is mail.Taken.STORED
    kinds = mail_inventory(ws)
    found = {(k.domain, k.template): k for k in kinds}
    shares = found[("banka.example", "<ay> # Hisse Senedi Ekstreniz")]
    assert (shares.count, shares.first_day, shares.last_day, shares.with_files) == (2, "2026-02-02", "2026-03-02", 0)
    assert shares.states == {f"işlenmedi: {MESSAGE_REASON}": 2}
    statement = found[("teb.com.tr", "Hesap hareketleriniz")]
    assert (statement.count, statement.with_files) == (1, 1)  # the list came attached
    assert [k.domain for k in kinds] == ["banka.example", "banka.example", "teb.com.tr"]  # by domain, most first
    target = tmp_path / "envanter.csv"
    write_csv(kinds, target)
    lines = target.read_text(encoding="utf-8").splitlines()
    assert lines[0] == "Gönderen,Konu kalıbı,İleti,İlk,Son,Ekli,Ne oldu"
    assert lines[1].startswith("banka.example,<ay> # Hisse Senedi Ekstreniz,2,2026-02-02,2026-03-02,0,")


def test_the_coverage_counts_the_bank_messages_read_or_knowingly_classified(ws):
    taken = [
        mail.take(ws, vakifbank.fast_in(), BANK_SENDERS),  # a notice its reader reads
        mail.take(ws, bank_mail(FEBRUARY), BANK_SENDERS),  # read through the statement it carries
        mail.take(ws, notice("Size özel %5 bonus!", "firsat@kampanya.garantibbva.com.tr"), BANK_SENDERS),
        mail.take(ws, notice("Haftası Ödeme Bilgileriniz", "bilgi@ileti.isbank.com.tr"), BANK_SENDERS),
        mail.take(ws, notice("ÖRNEK TEKNOLOJİ hesap bilgileri", "bilgi@isbank.com.tr"), BANK_SENDERS),
    ]
    assert all(t.taken is mail.Taken.STORED for t in taken)
    set_business_names(["Örnek Teknoloji A.Ş."])  # the last one turns out to be the company's
    with ws.db() as db:
        reading.read_pending(ws, db)
        found = mail_coverage(db, BANK_SENDERS)
    assert (found.read, found.attached, found.no_money, found.business, found.unknown) == (1, 1, 1, 1, 1)
    assert (found.total, found.share) == (5, 0.8)
    assert found.left == {("ileti.isbank.com.tr", "Haftası Ödeme Bilgileriniz"): 1}
    with ws.db() as db:
        assert mail_coverage(db, ("teb.com.tr",)).total == 1  # only the bank senders' messages count
