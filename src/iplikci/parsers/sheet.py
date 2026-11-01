"""Read spreadsheet-like bank exports (real XLS, XLSX, or HTML saved as .xls) into rows."""

import io
from datetime import date, datetime
from decimal import Decimal

from bs4 import BeautifulSoup

from ..domain.money import round_half_up, to_decimal
from .text import parse_dmy, parse_tr_amount, parse_us_amount

XLS_MAGIC = b"\xd0\xcf\x11\xe0"
XLSX_MAGIC = b"PK\x03\x04"


def sniff(data: bytes) -> str:
    if data.startswith(XLS_MAGIC):
        return "xls"
    if data.startswith(XLSX_MAGIC):
        return "xlsx"
    head = data.lstrip()[:4096].lower()  # some banks pad the HTML with blank lines
    if head.startswith((b"<html", b"<!doctype", b"<table", b"<meta", b"<head", b"<?xml")) or b"<table" in head:
        return "html"
    return ""


def read_xls(data: bytes) -> list[list]:
    import xlrd

    sheet = xlrd.open_workbook(file_contents=data).sheet_by_index(0)
    return [[sheet.cell_value(r, c) for c in range(sheet.ncols)] for r in range(sheet.nrows)]


def read_xlsx(data: bytes) -> list[list]:
    import openpyxl

    wb = openpyxl.load_workbook(io.BytesIO(data), read_only=True, data_only=True)
    try:
        return [list(r) for r in wb.worksheets[0].iter_rows(values_only=True)]
    finally:
        wb.close()


def decode_html(data: bytes) -> str:
    for enc in ("utf-8", "windows-1254"):
        try:
            return data.decode(enc)
        except UnicodeDecodeError:
            continue
    return data.decode("latin-1")


def html_rows(data: bytes) -> list[list[str]]:
    """Innermost table rows (rows of nested layout tables are skipped)."""
    soup = BeautifulSoup(decode_html(data), "html.parser")
    rows = []
    for tr in soup.find_all("tr"):
        if tr.find("table"):
            continue
        rows.append([td.get_text(" ", strip=True) for td in tr.find_all(["td", "th"], recursive=False)])
    return rows


def cells(row) -> list[str]:
    """Non-empty cells of a row as stripped strings."""
    return [str(v).strip() for v in row if v is not None and str(v).strip()]


def key_values(rows) -> dict[str, str]:
    """Label/value pairs from header rows such as ['IBAN', 'TR..', 'Şube', '..']."""
    out: dict[str, str] = {}
    for row in rows:
        c = cells(row)
        for i in range(0, len(c) - 1, 2):
            out.setdefault(c[i].rstrip(":").strip(), c[i + 1])
    return out


def to_date(value) -> date | None:
    if isinstance(value, datetime):
        return value.date()
    if isinstance(value, date):
        return value
    return parse_dmy(str(value or "").strip()[:10]) if value else None


def to_number(value) -> Decimal | None:
    """Spreadsheet number, or a Turkish ("1.234,56") / US ("1,234.56") formatted string; two decimals."""
    if value is None or value == "":
        return None
    if isinstance(value, (int, float)):
        return round_half_up(to_decimal(float(value)))
    text = str(value).strip().replace(" ", "")
    if not text:
        return None
    sign = -1 if text.startswith("-") else 1
    body = text.lstrip("+-")
    parsed = parse_tr_amount(body) if "," in body and body.rfind(",") > body.rfind(".") else parse_us_amount(body)
    if parsed is None:
        parsed = parse_tr_amount(body)
    return None if parsed is None else sign * abs(parsed)
