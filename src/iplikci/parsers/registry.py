"""The readers there are (ADR-0005): the ones the app ships and those installed packages add, and their versions.

A package adds readers through the `iplikci.parsers` entry-point group; each entry names a reader object (or a
class to make one from). Two readers with the same id are an error, never a silent choice.

A reading keeps the version of the reader that read it: when a reader's version goes up only its documents are read
again. A document no reader took keeps the signature of all of them and is shown to the readers again whenever one
comes, goes or changes.
"""

import hashlib
from functools import cache
from importlib.metadata import entry_points

from ..domain.codes import DocumentKind
from . import messages
from .contract import Parser
from .garanti import account_xls as garanti_account_xls
from .garanti import bonus_card as garanti_bonus_card
from .garanti import brokerage as garanti_brokerage
from .garanti import paracard as garanti_paracard
from .garanti import receipt as garanti_receipt
from .garanti.notice import transfer as garanti_notice_transfer
from .isbank import account_xls as isbank_account_xls
from .isbank import maximum_card as isbank_maximum_card
from .isbank import passbook as isbank_passbook
from .isbank import receipt as isbank_receipt
from .qnb import account_pdf as qnb_account_pdf
from .qnb import card_pdf as qnb_card_pdf
from .qnb import edekont as qnb_edekont
from .teb import account_html as teb_account_html
from .teb import bonus_card as teb_bonus_card
from .teb import card_payment_receipt as teb_card_payment_receipt
from .vakifbank import account_xlsx as vakifbank_account_xlsx
from .vakifbank import passbook as vakifbank_passbook
from .vakifbank.notice import transfer as vakifbank_notice_transfer

GROUP = "iplikci.parsers"
# Raise when choosing the reader itself changes (what the selector looks at, the checks before the readers): every
# document is then read again.
SELECTION = 1
BUILTIN: tuple[Parser, ...] = (
    garanti_bonus_card.PARSER,
    garanti_paracard.PARSER,
    garanti_account_xls.PARSER,
    garanti_receipt.PARSER,
    garanti_brokerage.PARSER,
    garanti_notice_transfer.PARSER,
    isbank_maximum_card.PARSER,
    isbank_account_xls.PARSER,
    isbank_receipt.PARSER,
    isbank_passbook.PARSER,
    teb_bonus_card.PARSER,
    teb_card_payment_receipt.PARSER,
    teb_account_html.PARSER,
    qnb_card_pdf.PARSER,
    qnb_account_pdf.PARSER,
    qnb_edekont.PARSER,
    vakifbank_account_xlsx.PARSER,
    vakifbank_passbook.PARSER,
    vakifbank_notice_transfer.PARSER,
)


class RegistryError(Exception):
    """The readers cannot be told apart, or an installed one does not keep the contract."""


def _installed() -> list[Parser]:
    found: list[Parser] = []
    for entry in entry_points(group=GROUP):
        obj = entry.load()
        reader = obj() if isinstance(obj, type) else obj
        if not isinstance(reader, Parser):
            raise RegistryError(f"{entry.name} ({entry.value}) okuyucu sözleşmesini karşılamıyor")
        found.append(reader)
    return found


def check(found: tuple[Parser, ...]) -> tuple[Parser, ...]:
    """found as it is, or an error naming the first id two readers share."""
    seen: set[str] = set()
    for reader in found:
        if reader.id in seen:
            raise RegistryError(f"iki okuyucunun kimliği aynı: {reader.id}")
        seen.add(reader.id)
    return found


@cache
def readers() -> tuple[Parser, ...]:
    """Every reader: the shipped ones first, then those of installed packages."""
    return check((*BUILTIN, *_installed()))


def find(parser_id: str) -> Parser | None:
    return next((r for r in readers() if r.id == parser_id), None)


def version_of(reader: Parser) -> str:
    """The version a reading by reader keeps."""
    return f"{SELECTION}.{reader.version}"


def signature() -> str:
    """The version a reading no reader took keeps: it changes whenever a reader comes, goes or changes its version,
    the selection changes, or the rules that say what an e-mail no reader took is (messages.py)."""
    parts = [
        f"selection={SELECTION}",
        f"messages={messages.VERSION}",
        *sorted(f"{r.id}={r.version}" for r in readers()),
    ]
    return hashlib.sha256("\n".join(parts).encode()).hexdigest()[:16]


def current(parser_id: str, parser_version: str) -> bool:
    """Whether a stored reading is what the readers would make of its document now."""
    if not parser_id:
        return parser_version == signature()
    reader = find(parser_id)
    return reader is not None and parser_version == version_of(reader)


def label(parser_id: str) -> str:
    """What a reader reads, for people; the id itself for a reader that is gone."""
    reader = find(parser_id)
    return reader.name if reader else parser_id


def document_type(parser_id: str) -> DocumentKind | None:
    """The kind of document a reader reads; None for a reader that is gone."""
    reader = find(parser_id)
    return reader.document_type if reader else None
