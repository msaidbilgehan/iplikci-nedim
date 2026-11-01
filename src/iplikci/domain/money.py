"""Money and quantities (ADR-0006).

Amounts are exact decimals in the domain and integers in the smallest unit (kuruş, cent) in the database. A
document prints two decimals; an amount read from one is rounded half up to them. Anything computed from
amounts (a currency conversion, an average) keeps its full precision until it is rounded on purpose.
"""

from collections.abc import Iterable
from dataclasses import dataclass
from decimal import ROUND_HALF_UP, Decimal
from enum import StrEnum
from functools import total_ordering
from typing import Self

# Decimal places of each currency's smallest unit (ISO 4217). Banks print no other currencies; one missing
# here is refused rather than guessed.
MINOR_DIGITS: dict[str, int] = {"TRY": 2, "EUR": 2, "USD": 2, "GBP": 2, "CHF": 2}
CENT = Decimal("0.01")
# A card statement verifies when its lines and the total it prints differ by at most this much: the same
# verdict as the MVP's 0.015 threshold over amounts with two decimals.
TOLERANCE = CENT


def to_decimal(value: Decimal | str | float) -> Decimal:
    """value as an exact Decimal. A float goes through its shortest repr, so 0.1 stays 0.1 instead of
    becoming 0.1000000000000000055511151231257827."""
    if isinstance(value, Decimal):
        result = value
    elif isinstance(value, float):
        result = Decimal(repr(value))
    else:
        result = Decimal(value)
    if not result.is_finite():
        raise ValueError(f"tutar sonlu bir sayı olmalı: {value!r}")
    return result


def round_half_up(value: Decimal, digits: int = 2) -> Decimal:
    """value with digits decimals, halves rounded away from zero (2,675 → 2,68) as banks round."""
    return value.quantize(Decimal(1).scaleb(-digits), rounding=ROUND_HALF_UP)


def minor_digits(currency: str) -> int:
    try:
        return MINOR_DIGITS[currency]
    except KeyError:
        raise ValueError(f"bilinmeyen para birimi: {currency!r}") from None


@total_ordering
@dataclass(frozen=True, slots=True)
class Money:
    """An amount in one currency. Adding or comparing two currencies is an error, never a silent mix."""

    amount: Decimal
    currency: str

    def __post_init__(self) -> None:
        # Callers outside the typed modules still hand over floats now and then; refuse them loudly.
        if not isinstance(self.amount, Decimal):  # pyright: ignore[reportUnnecessaryIsInstance]
            raise TypeError(f"Money tutarı Decimal olmalı, {type(self.amount).__name__} verildi")
        if not self.amount.is_finite():
            raise ValueError(f"tutar sonlu bir sayı olmalı: {self.amount!r}")
        minor_digits(self.currency)

    @classmethod
    def zero(cls, currency: str) -> Self:
        return cls(Decimal(0), currency)

    @classmethod
    def of(cls, value: Decimal | str | float, currency: str) -> Self:
        return cls(to_decimal(value), currency)

    @classmethod
    def from_minor(cls, units: int, currency: str) -> Self:
        """The amount a database row holds: 123456 kuruş → 1234,56 TRY."""
        return cls(Decimal(units).scaleb(-minor_digits(currency)), currency)

    @staticmethod
    def total(items: Iterable["Money"], currency: str) -> "Money":
        """The sum of items, zero in currency when there are none."""
        result = Money.zero(currency)
        for item in items:
            result = result + item
        return result

    def to_minor(self) -> int:
        """The amount in the smallest unit, for the database. An amount with more decimals than the currency
        has (an unrounded conversion) is a bug upstream: it is refused instead of rounded here."""
        scaled = self.amount.scaleb(minor_digits(self.currency))
        if scaled != scaled.to_integral_value():
            raise ValueError(f"{self} en küçük birime tam bölünmüyor; önce yuvarlanmalı")
        return int(scaled)

    def rounded(self) -> Self:
        return type(self)(round_half_up(self.amount, minor_digits(self.currency)), self.currency)

    def convert(self, rate: Decimal, currency: str) -> "Money":
        """This amount in another currency at rate (units of currency per unit of this one), rounded half up."""
        return Money(self.amount * rate, currency).rounded()

    def ratio(self, other: "Money") -> Decimal:
        self._same(other)
        return self.amount / other.amount

    @property
    def is_zero(self) -> bool:
        return self.amount == 0

    @property
    def is_positive(self) -> bool:
        return self.amount > 0

    @property
    def is_negative(self) -> bool:
        return self.amount < 0

    def _same(self, other: "Money") -> None:
        if self.currency != other.currency:
            raise ValueError(f"farklı para birimleri birleştirilemez: {self.currency} ve {other.currency}")

    def __add__(self, other: "Money") -> "Money":
        self._same(other)
        return Money(self.amount + other.amount, self.currency)

    def __radd__(self, other: int) -> "Money":
        # sum() starts from the integer 0; nothing else may be added to an amount without a currency.
        if other != 0:
            return NotImplemented
        return self

    def __sub__(self, other: "Money") -> "Money":
        self._same(other)
        return Money(self.amount - other.amount, self.currency)

    def __neg__(self) -> "Money":
        return Money(-self.amount, self.currency)

    def __abs__(self) -> "Money":
        return Money(abs(self.amount), self.currency)

    def __mul__(self, factor: Decimal | int) -> "Money":
        if isinstance(factor, float):  # pyright: ignore[reportUnnecessaryIsInstance] - see __post_init__
            raise TypeError("tutar float ile çarpılmaz; Decimal kullanın")
        return Money(self.amount * factor, self.currency)

    __rmul__ = __mul__

    def __truediv__(self, divisor: Decimal | int) -> "Money":
        if isinstance(divisor, float):  # pyright: ignore[reportUnnecessaryIsInstance] - see __post_init__
            raise TypeError("tutar float ile bölünmez; Decimal kullanın")
        return Money(self.amount / divisor, self.currency)

    def __lt__(self, other: "Money") -> bool:
        self._same(other)
        return self.amount < other.amount

    def __str__(self) -> str:
        return f"{self.amount} {self.currency}"


class Unit(StrEnum):
    """What a Quantity counts."""

    GRAM = "gram"  # gold
    SHARE = "share"  # securities and fund units


@dataclass(frozen=True, slots=True)
class Quantity:
    """A count of something that is not money (gold grams, shares), kept as Decimal text in the database."""

    amount: Decimal
    unit: Unit

    def __post_init__(self) -> None:
        if not isinstance(self.amount, Decimal):  # pyright: ignore[reportUnnecessaryIsInstance] - see Money
            raise TypeError(f"Quantity miktarı Decimal olmalı, {type(self.amount).__name__} verildi")
        if not self.amount.is_finite():
            raise ValueError(f"miktar sonlu bir sayı olmalı: {self.amount!r}")

    @classmethod
    def from_text(cls, text: str, unit: Unit) -> Self:
        return cls(to_decimal(text), unit)

    def to_text(self) -> str:
        return format(self.amount, "f")

    def __add__(self, other: "Quantity") -> "Quantity":
        if self.unit != other.unit:
            raise ValueError(f"farklı birimler birleştirilemez: {self.unit} ve {other.unit}")
        return Quantity(self.amount + other.amount, self.unit)

    def __sub__(self, other: "Quantity") -> "Quantity":
        return self + Quantity(-other.amount, other.unit)
