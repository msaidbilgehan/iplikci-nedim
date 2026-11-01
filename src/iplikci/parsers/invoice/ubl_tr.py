"""Turkish e-invoices as UBL-TR XML (e-Fatura and e-Arşiv Fatura, GİB's UBL-TR 1.2): what non-bank senders attach to
their e-mails, or a user uploads (F14).

An invoice names its seller (AccountingSupplierParty) and its buyer (AccountingCustomerParty), its number (ID) and
date (IssueDate), what is to pay (LegalMonetaryTotal/PayableAmount, in the currency its currencyID names) and its
lines (InvoiceLine: the item's name, the quantity, the amount before tax and the line's taxes). A bill prints its due
date (PaymentMeans/PaymentDueDate); an invoice of a purchase paid at once prints none, and is a receipt. A return
(InvoiceTypeCode IADE) gives money back: its total is below zero.

Company documents stay out (CLAUDE.md). An invoice to a company names its buyer by a tax number (VKN, ten digits); a
person is named by an identity number (TCKN, eleven digits). The user's company names are looked for as the buyer and
as the seller.

The XML is untrusted input. A document type declaration is refused before parsing: UBL-TR never carries one, and
entities are what an XML bomb is made of. The XSLT view and embedded files (AdditionalDocumentReference) are ignored.
"""

import re
from datetime import date
from decimal import Decimal, InvalidOperation
from xml.etree import ElementTree
from xml.etree.ElementTree import Element

from ...domain.codes import DocumentKind, InvoiceKind
from ...domain.models import Invoice, InvoiceLine, ParseResult, SourceRef
from ...domain.money import round_half_up
from ..common import BUSINESS_REASON, Skipped, currency_code, is_business
from ..contract import Detection, Format, Probe, SourceDocument

ID = "invoice.ubl_tr"
_ROOT = "urn:oasis:names:specification:ubl:schema:xsd:Invoice-2"
_NS = {
    "cac": "urn:oasis:names:specification:ubl:schema:xsd:CommonAggregateComponents-2",
    "cbc": "urn:oasis:names:specification:ubl:schema:xsd:CommonBasicComponents-2",
}
# GİB's profiles: the customisation every Turkish e-invoice declares, and the kinds of invoice it allows.
_PROFILES = ("TEMELFATURA", "TICARIFATURA", "EARSIVFATURA", "IHRACAT", "YOLCUBERABERFATURA", "KAMU", "HKS")
_DTD = re.compile(r"<!\s*(?:DOCTYPE|ENTITY)", re.IGNORECASE)
_PAYABLE = re.compile(r"<(?:\w+:)?PayableAmount\b[^>]*>\s*([^<]*?)\s*<")
_TAX_NUMBER = 10  # the digits of a company's tax number (VKN); a person's identity number (TCKN) has eleven


def _text(element: Element | None, path: str) -> str:
    found = element.find(path, _NS) if element is not None else None
    return (found.text or "").strip() if found is not None else ""


def _amount(element: Element, path: str) -> tuple[Decimal, str] | None:
    """An amount and its currency (currencyID); None when the document has no such element."""
    found = element.find(path, _NS)
    if found is None or not (found.text or "").strip():
        return None
    try:
        value = Decimal((found.text or "").strip())
    except InvalidOperation as exc:
        raise ValueError(f"e-faturada tutar okunamadı: {path}") from exc
    if not value.is_finite():
        raise ValueError(f"e-faturada tutar okunamadı: {path}")
    return round_half_up(value), found.get("currencyID", "")


def _date(text: str) -> date | None:
    try:
        return date.fromisoformat(text[:10]) if text else None
    except ValueError:
        return None


def _party(root: Element, role: str) -> tuple[str, str, str]:
    """A party's name, its tax or identity number, and which of the two it is ("VKN", "TCKN" or "")."""
    party = root.find(f"cac:{role}/cac:Party", _NS)
    if party is None:
        return "", "", ""
    name = _text(party, "cac:PartyName/cbc:Name")
    if not name:  # a person: first and family name
        parts = (_text(party, "cac:Person/cbc:FirstName"), _text(party, "cac:Person/cbc:FamilyName"))
        name = " ".join(p for p in parts if p)
    for identification in party.findall("cac:PartyIdentification/cbc:ID", _NS):
        scheme = identification.get("schemeID", "").upper()
        if scheme in ("VKN", "TCKN"):
            return name, (identification.text or "").strip(), scheme
    return name, "", ""


def _lines(root: Element, sign: int) -> list[InvoiceLine]:
    """The invoice's lines, each with its taxes."""
    found: list[InvoiceLine] = []
    for line in root.findall("cac:InvoiceLine", _NS):
        base = _amount(line, "cbc:LineExtensionAmount")
        if base is None:
            continue
        tax = _amount(line, "cac:TaxTotal/cbc:TaxAmount")
        name = _text(line, "cac:Item/cbc:Name") or _text(line, "cac:Item/cbc:Description")
        quantity = _text(line, "cbc:InvoicedQuantity")
        try:
            count = Decimal(quantity) if quantity else None
        except InvalidOperation:
            count = None
        amount = base[0] + (tax[0] if tax else Decimal(0))
        found.append(InvoiceLine(name, sign * amount, count if count is None or count.is_finite() else None))
    return found


def _span(text: str) -> tuple[int, int] | None:
    """Where the total is written in the document's text."""
    found = _PAYABLE.search(text)
    return found.span(1) if found else None


def read(doc: SourceDocument) -> ParseResult:
    text = doc.xml
    if _DTD.search(text):
        raise ValueError("e-faturada belge türü tanımı (DTD) var: UBL-TR'de olmaz, okunmadı")
    root = ElementTree.fromstring(doc.data)
    seller, seller_id, _ = _party(root, "AccountingSupplierParty")
    buyer, buyer_id, scheme = _party(root, "AccountingCustomerParty")
    to_company = scheme == "VKN" or (len(buyer_id) == _TAX_NUMBER and buyer_id.isdigit())
    if to_company or is_business(buyer) or is_business(seller):
        raise Skipped(BUSINESS_REASON, business=True)
    issued = _date(_text(root, "cbc:IssueDate"))
    payable = _amount(root, "cac:LegalMonetaryTotal/cbc:PayableAmount")
    if issued is None or payable is None or not seller:
        raise ValueError("e-faturada satıcı, tarih ya da ödenecek tutar bulunamadı")
    sign = -1 if _text(root, "cbc:InvoiceTypeCode").upper() == "IADE" else 1
    due = _date(_text(root, "cac:PaymentMeans/cbc:PaymentDueDate")) or _date(_text(root, "cbc:DueDate"))
    currency = currency_code(payable[1] or _text(root, "cbc:DocumentCurrencyCode"))
    number = _text(root, "cbc:ID")
    invoice = Invoice(
        kind=InvoiceKind.BILL if due else InvoiceKind.RECEIPT,
        seller=seller,
        issued=issued,
        total=sign * payable[0],
        currency=currency,
        number=number,
        due=due,
        seller_id=seller_id,
        lines=_lines(root, sign),
        ref=SourceRef(span=_span(text)),
    )
    # A second copy of the invoice (its XML zipped, mailed again) is known by its seller and number.
    key = f"efatura-{seller_id}-{number}" if seller_id and number else ""
    return ParseResult(parser=ID, receipt_key=key, title=seller, invoices=[invoice])


class UblInvoice:
    id = ID
    version = 1
    bank = "e-Fatura"
    name = "e-Fatura ve e-Arşiv faturası (UBL-TR XML)"
    document_type = DocumentKind.INVOICE
    formats = frozenset({Format.XML})

    def detect(self, probe: Probe) -> Detection | None:
        text = probe.text
        if _ROOT in text and ("TR1.2" in text or any(p in text for p in _PROFILES)):
            return Detection(1.0, "UBL-TR faturası: Invoice-2 kök öğesi ve GİB profili")
        return None

    def parse(self, doc: SourceDocument) -> ParseResult:
        return read(doc)


PARSER = UblInvoice()
