"""Amounts as QNB's PDF exports print them: US format, a leading minus for money out."""

from decimal import Decimal

from ..text import parse_us_amount

US_AMOUNT = r"-?[\d,]+\.\d{2}"


def us_signed(text: str) -> Decimal:
    value = parse_us_amount(text.lstrip("-"))
    return -value if text.startswith("-") else value
