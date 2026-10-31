"""Account movement exports of Garanti BBVA, İş Bankası, TEB and Vakıfbank."""

import re

from ..models import Account, ParseResult
from ..tables import cells, decode_html, html_rows, key_values, read_xls, read_xlsx, sniff, to_date, to_number
from ..textutil import fold, parse_dmy, title_tr
from .common import BUSINESS_REASON, Skipped, is_business
from .hesap import Movement, bank_from_iban, build_statement, receiver_after_bank, sender_after_bank

NAME = "Hesap hareketleri"


def bank_account(bank: str, number: str, currency: str, kind: str = "") -> Account:
    """The account as every document of that bank names it: lists, receipts and passbooks share its id."""
    if currency == "GR":
        type_, word = "Altın hesabı", "Altın"
    elif currency != "TL":
        type_, word = "Döviz hesabı", f"Vadesiz {currency}"
    else:
        type_ = kind or "Vadesiz hesap"
        word = {"Ek hesap (KMH)": "Ek Hesap", "Vadeli hesap": "Vadeli TL"}.get(type_, "Vadesiz TL")
    slug = {"Garanti BBVA": "garanti", "İş Bankası": "isbank", "TEB": "teb", "Vakıfbank": "vakifbank", "QNB": "qnb"}[
        bank
    ]
    shown = number if len(number) <= 12 else "…" + number[-6:]
    return Account(
        id=f"{slug}-{number}",
        label=f"{bank} {word} {shown}",
        bank=bank,
        type=type_,
        currency=currency,
        number=number,
    )


def _period(text: str):
    found = re.findall(r"(\d{2}[./]\d{2}[./]\d{4})", text)
    if len(found) >= 2:
        return parse_dmy(found[0]), parse_dmy(found[1])
    return None, None


def parse(doc) -> ParseResult:
    kind = sniff(doc.data)
    if kind == "xls":
        rows = read_xls(doc.data)
        head = fold(" ".join(" ".join(cells(r)) for r in rows[:16]))
        if "GARANTI BANKASI" in head:
            return _garanti(doc, rows)
        if "HESAP OZETI" in head and "URUN-DOVIZ TIPI" in head:
            return _isbank(doc, rows)
    elif kind == "xlsx":
        rows = read_xlsx(doc.data)
        head = fold(" ".join(" ".join(cells(r)) for r in rows[:10]))
        if "VB MUSTERI NO" in head:
            return _vakifbank(doc, rows)
    elif kind == "html":
        rows = html_rows(doc.data)
        info = key_values(r for r in rows[:20] if len(r) == 2)
        # Older TEB exports have no IBAN; their holder still marks company accounts.
        if is_business(info.get("Hesap Sahibi", "")):
            raise Skipped(BUSINESS_REASON, business=True)
        if bank_from_iban(info.get("IBAN", "")) == "TEB":
            return _teb(doc, rows, info, decode_html(doc.data))
    raise Skipped("tanınmayan tablo")


# --- Garanti BBVA -------------------------------------------------------------


def _garanti_counterparty(desc: str, label: str) -> str:
    if fold(label) != "PARA TRANSFERI":
        return ""
    text = re.sub(r"^FAST\d+-", "", desc.strip())
    if "Havale" in text:
        return text.split("Havale")[0].strip()
    return text.split("-")[0].strip()


def _garanti(doc, rows) -> ParseResult:
    header = next((i for i, r in enumerate(rows) if cells(r)[:3] == ["Tarih", "Açıklama", "Etiket"]), None)
    if header is None:
        raise Skipped("Garanti tablo başlığı yok")
    info = key_values(rows[:header])
    m = re.match(r"(\d+)\s*-\s*(\d+)\s+(\w+)", info.get("Hesap", ""))
    if not m:
        raise ValueError("Garanti hesap numarası okunamadı")
    account = bank_account("Garanti BBVA", m[2], m[3].upper())
    cols = {name: i for i, name in enumerate(str(v).strip() for v in rows[header])}
    moves = []
    for r in rows[header + 1 :]:
        d = to_date(r[cols["Tarih"]])
        amount = to_number(r[cols["Tutar"]])
        if not d or amount is None:
            continue
        desc, label = str(r[cols["Açıklama"]]).strip(), str(r[cols["Etiket"]]).strip()
        moves.append(Movement(d, desc, amount, to_number(r[cols["Bakiye"]]), label, _garanti_counterparty(desc, label)))
    start, end = parse_dmy(info.get("Başlangıç", "")), parse_dmy(info.get("Bitiş", ""))
    stmt = build_statement(doc, account, moves, start, end, oldest_first=False)
    # Company accounts carry "Şirket Ünvanı" instead of "Ad Soyad".
    holder = info.get("Ad Soyad") or info.get("Şirket Ünvanı", "")
    return ParseResult(parser=NAME, accounts=[account], statements=[stmt], holder=holder)


# --- İş Bankası ---------------------------------------------------------------


def _isbank(doc, rows) -> ParseResult:
    header = next((i for i, r in enumerate(rows) if str(r[0]).strip().startswith("Tarih/Saat")), None)
    if header is None:
        raise Skipped("İş Bankası tablo başlığı yok")
    info = key_values(rows[:header])
    holder = next(
        (c[0].replace("Sayın", "").strip() for c in map(cells, rows[:header]) if c and c[0].startswith("Sayın")), ""
    )
    digits = re.sub(r"\D", "", info.get("IBAN", ""))
    branch_account = re.search(r"(\d{4})(\d{7})$", digits)  # IBAN ends with branch (4) + account (7)
    number = f"{branch_account[1]}-{branch_account[2]}" if branch_account else digits[-11:]
    currency = "TL"
    balance_text = info.get("Mevcut Bakiye", "")
    for cur in ("USD", "EUR", "GBP"):
        if cur in balance_text:
            currency = cur
    account = bank_account("İş Bankası", number, currency)
    names = [str(v).strip() for v in rows[header]]
    col = {n: i for i, n in enumerate(names) if n}
    desc_start, desc_end = col["Açıklama"], col.get("Referans", len(names))
    moves = []
    for r in rows[header + 1 :]:
        d = to_date(str(r[0]))
        amount = to_number(r[col["İşlem Tutarı*"]])
        if not d or amount is None:
            continue
        desc = " ".join(str(v).strip() for v in r[desc_start:desc_end] if str(v).strip())
        label = str(r[col["İşlem Tipi"]]).strip()
        counterparty = desc.split("*")[0].strip() if label in ("FAST", "EFT", "Havale") and "*" in desc else ""
        moves.append(Movement(d, desc, amount, to_number(r[col["Bakiye"]]), label, counterparty))
    start, end = _period(info.get("Sorgulama Kriterleri", ""))
    stmt = build_statement(doc, account, moves, start, end, oldest_first=False)
    return ParseResult(parser=NAME, accounts=[account], statements=[stmt], holder=holder)


# --- TEB (CEPTETEB "Hesap Hareketlerim", HTML saved as .xls) -------------------


def _teb(doc, rows, info: dict, html: str) -> ParseResult:
    number = info.get("Hesap", "")
    kind = fold(info.get("Hesap Türü", ""))
    currency = "GR" if kind.endswith("GR") else "TL"
    moves = []
    for r in rows:
        if len(r) != 7 or not re.match(r"\d{2}/\d{2}/\d{4}$", r[0]):
            continue
        amount = to_number(r[4])
        if amount is None:
            continue
        desc = r[3]
        sender = re.match(r"(.+?)\s+den gelen", desc)
        moves.append(Movement(parse_dmy(r[0]), desc, amount, to_number(r[5]), "", sender[1] if sender else ""))
    if not number:
        raise Skipped("TEB hesap bilgisi yok")
    # A TL account that runs below zero is the overdraft (KMH) account.
    overdraft = currency == "TL" and any((m.balance or 0) < -1 for m in moves)
    account = bank_account("TEB", number, currency, "Ek hesap (KMH)" if overdraft else "")
    period = re.search(r"\d{2}/\d{2}/\d{4}\s*-\s*\d{2}/\d{2}/\d{4}(?=\s*tarihleri)", html)
    start, end = _period(period[0] if period else "")
    stmt = build_statement(doc, account, moves, start, end, oldest_first=False)
    return ParseResult(parser=NAME, accounts=[account], statements=[stmt], holder=info.get("Hesap Sahibi", ""))


# --- Vakıfbank ------------------------------------------------------------------


def _vakifbank(doc, rows) -> ParseResult:
    header = next((i for i, r in enumerate(rows) if "HESAP NO" in cells(r) and "İŞLEM" in cells(r)), None)
    if header is None:
        raise Skipped("Vakıfbank tablo başlığı yok")
    info = key_values(rows[:header])
    iban = re.sub(r"\s", "", info.get("IBAN", ""))
    number = iban[-16:] if iban else ""
    currency = (
        "TL" if fold(info.get("HESAP TÜRÜ", "")).endswith("TL") else info.get("HESAP TÜRÜ", "").split()[-1].upper()
    )
    account = bank_account("Vakıfbank", number, currency)
    nickname = info.get("RUMUZ", "")
    if nickname:
        account.label += f" ({nickname})"
    col = {str(v).strip(): i for i, v in enumerate(rows[header]) if v is not None}
    moves = []
    for r in rows[header + 1 :]:
        d = to_date(r[col["İŞLEM TARİHİ"]])
        amount = to_number(r[col["TUTAR"]])
        if not d or amount is None:
            continue
        label = str(r[col["İŞLEM"]] or "").strip()
        desc = str(r[col["AÇIKLAMA"]] or "").strip()
        if amount < 0:
            counterparty = receiver_after_bank(desc)
        else:
            counterparty = sender_after_bank(desc)
            salary = re.search(r"\(\d+_\d+_(.+?)\)", desc)
            if salary:
                counterparty = title_tr(salary[1])
            company = re.search(r"sorgu numaralı (.+?) tarafından", desc)
            if company:
                counterparty = company[1]
        moves.append(
            Movement(d, f"{label}: {desc}" if label else desc, amount, to_number(r[col["BAKİYE"]]), label, counterparty)
        )
    start, end = _period(info.get("TARİH ARALIĞI", ""))
    stmt = build_statement(doc, account, moves, start, end, oldest_first=True)
    return ParseResult(parser=NAME, accounts=[account], statements=[stmt], holder=info.get("HESAP SAHİBİ", ""))
