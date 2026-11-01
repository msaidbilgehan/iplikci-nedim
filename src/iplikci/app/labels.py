"""The Turkish labels of the codes, for the interface: the codes travel in the data, their labels come from the one
mapping that holds them (ADR-0006)."""

from ..domain.labels import TABLES
from . import kinds


def tables() -> dict[str, dict[str, str]]:
    """Every code type's labels by code, e.g. {"DocumentStatus": {"processed": "İşlendi", …}, …}, and the kinds of
    background jobs as JobKind."""
    found = {kind.__name__: {code.value: text for code, text in table.items()} for kind, table in TABLES.items()}
    return found | {"JobKind": dict(kinds.LABELS)}
