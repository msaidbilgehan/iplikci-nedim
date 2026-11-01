"""Garanti BBVA card statements: the Bonus credit card's and the Paracard debit card's, read the same way."""

import re
from decimal import Decimal

from ...domain.codes import AccountType, TransactionKind
from ...domain.models import TRY, Account, ParseResult, Statement, Transaction
from ...domain.money import round_half_up
from ...domain.text import fold
from ..common import agreed, classify_kind, installment_label, pair_deferrals
from ..contract import SourceDocument
from ..pdf import find_header, find_word, page_lines, page_text, take_amount
from ..text import parse_tr_amount, parse_tr_words_date, squash

BONUS_ID, PARACARD_ID = "garanti.bonus_card", "garanti.paracard"

# Section headings Garanti prints above groups of purchases that are not categories.
_NON_CATEGORY_SECTIONS = ("BONUS PROGRAM", "DIGER HARCAMALARINIZ", "YURT DISI HARCAMALARINIZ", "HARCAMALARINIZ")
_FOREIGN = re.compile(r"([\d.]+,\d{2})\s*(USD|EUR|GBP)")
# A Bonus statement's due date, spelled with the month's name, in its heading ("… Bilgileriniz Son Ödeme Tarihi:
# 15 Ağustos 2026") and again in the summary. The sentence under the summary names the next statement's ("… ve son
# ödemeniz 15 Eylül 2026 Pazartesi 'dir").
_DUE = re.compile(r"SON ODEME TARIHI:? ?(\d{1,2}) (\w+) (\d{4})")
# The card's limit, between the customer's limit and the cash advance limit.
_LIMIT = re.compile(r"\bKART LIMITI ([\d.]+,\d{2})")


def read_statement(doc: SourceDocument) -> ParseResult:
    pdf = doc.pdf
    first = page_text(pdf.pages[0])
    f = fold(first)
    paracard = "PARACARD" in squash(first)
    if paracard:
        card = re.search(r"KART NO ?: ?(\d{4}) ?(\d{2})\*\* \*\*\*\* (\d{4})", f)
        cut = re.search(r"HESAP KESIM TARIHINIZ (\d{1,2}) (\w+) (\d{4})", f)
        purchases = re.search(r"TOPLAM ALISVERIS TUTARINIZ ([\d.]+,\d{2})", f)
        cash = re.search(r"TOPLAM NAKIT CEKIM TUTARINIZ ([\d.]+,\d{2})", f)
        total = None
        if purchases:
            total = round_half_up(parse_tr_amount(purchases[1]) + (parse_tr_amount(cash[1]) if cash else Decimal(0)))
    else:
        card = re.search(r"KART NUMARASI (\d{4}) ?(\d{2})\*\* \*\*\*\* (\d{4})", f)
        cut = re.search(r"HESAP KESIM TARIHI (\d{1,2}) (\w+) (\d{4})", f)
        total = re.search(r"DONEM BORCUNUZ ([\d.]+,\d{2})", f)
        total = parse_tr_amount(total[1]) if total else None
    if not (card and cut):
        raise ValueError("kart numarası / hesap kesim tarihi bulunamadı")
    last4 = card[3]
    if paracard:
        account = Account(
            id=f"garanti-{last4}",
            label=f"Garanti Paracard •{last4}",
            bank="Garanti BBVA",
            type=AccountType.DEBIT_CARD,
            number=last4,
        )
    else:
        product = "Bonus"
        account = Account(
            id=f"garanti-{last4}",
            label=f"Garanti {product} •{last4}",
            bank="Garanti BBVA",
            type=AccountType.CREDIT_CARD,
            number=last4,
        )
    cut_date = parse_tr_words_date(cut[1], cut[2], cut[3])
    stmt = Statement(
        account=account.id,
        cut_date=cut_date,
        currency=TRY,
        source=doc.name,
        previous=None if paracard else Decimal(0),
        total=total,
        total_is_sum=paracard,
        # A debit card has neither, and the Paracard reader's readings stay as they were. A Bonus statement prints no
        # minimum payment on the pages read here.
        due_date=None if paracard else agreed(parse_tr_words_date(*m) for m in _DUE.findall(f)),
        credit_limit=None if paracard else agreed(parse_tr_amount(m) for m in _LIMIT.findall(f)),
    )

    section = ""
    for page in pdf.pages:
        lines = page_lines(page)
        h = find_header(lines, "ISLEM", "TUTAR", "BONUS")
        if h is None:
            continue
        header = lines[h]
        section = ""
        tutar = find_word(header, "TUTAR")
        tutar_right = next((w.x1 for w in header.words if w.x0 > tutar.x0 and w.text == "(TL)"), tutar.x1)
        bonus = find_word(header, "BONUS")
        donem = find_word(header, "DONEM")
        kalan = find_word(header, "KALAN")
        extra_left = kalan.x0 - 2 if kalan else bonus.x0 - 2
        for line in lines[h + 1 :]:
            w = line.words
            amount, used = take_amount(line, tutar_right)
            date = None
            if len(w) >= 3 and w[0].text.isdigit():
                date = parse_tr_words_date(w[0].text, w[1].text, w[2].text)
            desc_words = [x for x in w[3 if date else 0 :] if x not in used and x.x1 < extra_left]
            desc = " ".join(x.text for x in desc_words if x.x0 >= donem.x0 - 3 or not date)
            extra = " ".join(x.text for x in w if x not in used and extra_left <= x.x0 < bonus.x0 - 2)
            fd = fold(desc)
            if date is None:
                if amount is None:
                    if fd and not any(c.isdigit() for c in fd):
                        section = "" if any(s in fd for s in _NON_CATEGORY_SECTIONS) else desc
                    continue
                if "DEVIR" in fd:
                    stmt.previous = amount
                    continue
                if fd.startswith("TOPLAM"):
                    continue
                date = cut_date  # undated period charges: DÖNEM FAİZİ, KKDF + BSMV
            if not amount:
                continue  # missing or 0,00 (e.g. a "bonus bedava alışveriş" points line)
            original = ""
            m = _FOREIGN.search(extra)
            if m:
                original = f"{m[1]} {m[2]}"
            kind = classify_kind(desc, amount)
            # "NAKİT ÇEKİM" on debit cards, "NAKİT AVANS BİLGİLERİ" on credit cards: ATM lines
            # print only the machine's location ("İBB ÖRNEK METROBÜS").
            in_cash_section = any(k in fold(section) for k in ("NAKIT CEKIM", "NAKIT AVANS"))
            if in_cash_section and kind == TransactionKind.PURCHASE:
                kind = TransactionKind.CASH_ADVANCE  # debit-card ATM withdrawal
            stmt.transactions.append(
                Transaction(
                    date=date,
                    description=desc,
                    amount=amount,
                    kind=kind,
                    account=account.id,
                    original=original,
                    installment=installment_label(extra),
                    bank_category="" if in_cash_section else section,
                    source=doc.name,
                    ref=line.ref,
                )
            )

    pair_deferrals(stmt.transactions)
    return ParseResult(parser=PARACARD_ID if paracard else BONUS_ID, accounts=[account], statements=[stmt])
