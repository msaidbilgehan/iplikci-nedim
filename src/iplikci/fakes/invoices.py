"""Non-bank senders' documents: Turkish e-invoices as UBL-TR XML, laid out as GİB's UBL-TR 1.2 writes them."""

from collections.abc import Sequence
from dataclasses import dataclass
from datetime import date
from decimal import Decimal
from xml.sax.saxutils import escape

from . import Specimen

SELLER = "ÖRNEKCELL İLETİŞİM HİZMETLERİ A.Ş."
SELLER_VKN = "1000000001"
BUYER = ("ÖRNEK", "KULLANICI")
BUYER_TCKN = "10000000146"


@dataclass(frozen=True)
class Item:
    name: str
    quantity: Decimal
    base: Decimal  # before tax
    rate: int = 20  # KDV, percent


MONTHLY = (Item("Aylık 20 GB paket", Decimal(1), Decimal("344.08")), Item("Ek hizmet", Decimal(1), Decimal("25.00")))


def _money(value: Decimal) -> str:
    return f"{value:.2f}"


def _line(n: int, item: Item, currency: str) -> str:
    tax = (item.base * item.rate / 100).quantize(Decimal("0.01"))
    return (
        f"<cac:InvoiceLine><cbc:ID>{n}</cbc:ID>"
        f'<cbc:InvoicedQuantity unitCode="C62">{item.quantity}</cbc:InvoicedQuantity>'
        f'<cbc:LineExtensionAmount currencyID="{currency}">{_money(item.base)}</cbc:LineExtensionAmount>'
        f'<cac:TaxTotal><cbc:TaxAmount currencyID="{currency}">{_money(tax)}</cbc:TaxAmount>'
        f'<cac:TaxSubtotal><cbc:TaxableAmount currencyID="{currency}">{_money(item.base)}</cbc:TaxableAmount>'
        f'<cbc:TaxAmount currencyID="{currency}">{_money(tax)}</cbc:TaxAmount><cbc:Percent>{item.rate}</cbc:Percent>'
        "<cac:TaxCategory><cac:TaxScheme><cbc:Name>KDV</cbc:Name><cbc:TaxTypeCode>0015</cbc:TaxTypeCode>"
        "</cac:TaxScheme></cac:TaxCategory></cac:TaxSubtotal></cac:TaxTotal>"
        f"<cac:Item><cbc:Name>{escape(item.name)}</cbc:Name></cac:Item>"
        f'<cac:Price><cbc:PriceAmount currencyID="{currency}">{_money(item.base)}</cbc:PriceAmount></cac:Price>'
        "</cac:InvoiceLine>"
    )


def _buyer(name: tuple[str, str] | str, number: str, scheme: str) -> str:
    who = (
        f"<cac:PartyName><cbc:Name>{escape(name)}</cbc:Name></cac:PartyName>"
        if isinstance(name, str)
        else f"<cac:Person><cbc:FirstName>{escape(name[0])}</cbc:FirstName>"
        f"<cbc:FamilyName>{escape(name[1])}</cbc:FamilyName></cac:Person>"
    )
    return (
        "<cac:AccountingCustomerParty><cac:Party>"
        f'<cac:PartyIdentification><cbc:ID schemeID="{scheme}">{number}</cbc:ID></cac:PartyIdentification>'
        f"{who if isinstance(name, str) else ''}"
        "<cac:PostalAddress><cbc:CityName>İSTANBUL</cbc:CityName><cac:Country><cbc:Name>Türkiye</cbc:Name>"
        f"</cac:Country></cac:PostalAddress>{'' if isinstance(name, str) else who}"
        "</cac:Party></cac:AccountingCustomerParty>"
    )


def ubl_invoice(
    items: Sequence[Item] = MONTHLY,
    issued: date = date(2026, 10, 3),
    due: date | None = date(2026, 10, 20),
    number: str = "OCE2026000000101",
    seller: str = SELLER,
    buyer: tuple[str, str] | str = BUYER,
    buyer_id: tuple[str, str] = (BUYER_TCKN, "TCKN"),
    kind: str = "SATIS",
    profile: str = "EARSIVFATURA",
    currency: str = "TRY",
    doctype: str = "",
) -> bytes:
    """A UBL-TR invoice of items: a bill when it prints a due date, else a receipt of a purchase paid at once. kind is
    its InvoiceTypeCode (SATIS, IADE); doctype puts a document type declaration in front of it, as no real one has."""
    base = sum((i.base for i in items), Decimal(0))
    tax = sum(((i.base * i.rate / 100).quantize(Decimal("0.01")) for i in items), Decimal(0))
    payment = (
        f"<cac:PaymentMeans><cbc:PaymentMeansCode>1</cbc:PaymentMeansCode>"
        f"<cbc:PaymentDueDate>{due.isoformat()}</cbc:PaymentDueDate></cac:PaymentMeans>"
        if due
        else ""
    )
    xml = (
        '<?xml version="1.0" encoding="UTF-8"?>'
        f"{doctype}"
        '<Invoice xmlns="urn:oasis:names:specification:ubl:schema:xsd:Invoice-2" '
        'xmlns:cac="urn:oasis:names:specification:ubl:schema:xsd:CommonAggregateComponents-2" '
        'xmlns:cbc="urn:oasis:names:specification:ubl:schema:xsd:CommonBasicComponents-2" '
        'xmlns:ext="urn:oasis:names:specification:ubl:schema:xsd:CommonExtensionComponents-2">'
        "<ext:UBLExtensions><ext:UBLExtension><ext:ExtensionContent/></ext:UBLExtension></ext:UBLExtensions>"
        "<cbc:UBLVersionID>2.1</cbc:UBLVersionID><cbc:CustomizationID>TR1.2</cbc:CustomizationID>"
        f"<cbc:ProfileID>{profile}</cbc:ProfileID><cbc:ID>{number}</cbc:ID><cbc:CopyIndicator>false</cbc:CopyIndicator>"
        "<cbc:UUID>00000000-0000-4000-8000-000000000001</cbc:UUID>"
        f"<cbc:IssueDate>{issued.isoformat()}</cbc:IssueDate><cbc:IssueTime>10:15:00</cbc:IssueTime>"
        f"<cbc:InvoiceTypeCode>{kind}</cbc:InvoiceTypeCode><cbc:DocumentCurrencyCode>{currency}</cbc:DocumentCurrencyCode>"
        f"<cbc:LineCountNumeric>{len(items)}</cbc:LineCountNumeric>"
        "<cac:AdditionalDocumentReference><cbc:ID>FATURA.xslt</cbc:ID><cbc:IssueDate>2026-01-01</cbc:IssueDate>"
        '<cac:Attachment><cbc:EmbeddedDocumentBinaryObject mimeCode="application/xml" encodingCode="Base64" '
        'filename="FATURA.xslt">PHhzbDpzdHlsZXNoZWV0Lz4=</cbc:EmbeddedDocumentBinaryObject></cac:Attachment>'
        "</cac:AdditionalDocumentReference>"
        "<cac:AccountingSupplierParty><cac:Party>"
        f'<cac:PartyIdentification><cbc:ID schemeID="VKN">{SELLER_VKN}</cbc:ID></cac:PartyIdentification>'
        f"<cac:PartyName><cbc:Name>{escape(seller)}</cbc:Name></cac:PartyName>"
        "<cac:PostalAddress><cbc:CityName>İSTANBUL</cbc:CityName><cac:Country><cbc:Name>Türkiye</cbc:Name>"
        "</cac:Country></cac:PostalAddress>"
        "<cac:PartyTaxScheme><cac:TaxScheme><cbc:Name>ÖRNEK VERGİ DAİRESİ</cbc:Name></cac:TaxScheme></cac:PartyTaxScheme>"
        "</cac:Party></cac:AccountingSupplierParty>"
        f"{_buyer(buyer, *buyer_id)}{payment}"
        f'<cac:TaxTotal><cbc:TaxAmount currencyID="{currency}">{_money(tax)}</cbc:TaxAmount></cac:TaxTotal>'
        "<cac:LegalMonetaryTotal>"
        f'<cbc:LineExtensionAmount currencyID="{currency}">{_money(base)}</cbc:LineExtensionAmount>'
        f'<cbc:TaxExclusiveAmount currencyID="{currency}">{_money(base)}</cbc:TaxExclusiveAmount>'
        f'<cbc:TaxInclusiveAmount currencyID="{currency}">{_money(base + tax)}</cbc:TaxInclusiveAmount>'
        f'<cbc:PayableAmount currencyID="{currency}">{_money(base + tax)}</cbc:PayableAmount>'
        "</cac:LegalMonetaryTotal>"
        f"{''.join(_line(n, item, currency) for n, item in enumerate(items, 1))}"
        "</Invoice>"
    )
    return xml.encode()


def specimens() -> list[Specimen]:
    reader = "invoice.ubl_tr"
    purchase = (Item("Kablosuz kulaklık", Decimal(1), Decimal("1249.17")),)
    return [
        Specimen("e-fatura-fatura.xml", ubl_invoice(), reader, "", 1),
        Specimen("e-arsiv-alisveris.xml", ubl_invoice(purchase, due=None, number="ORN2026000004567"), reader, "", 1),
    ]
