"""Developer tools for the readers (ADR-0005), behind `iplikci dev parser`: what the selection sees in a document and
what every reader says of it (probe), what the reader that takes it reads, row by row (debug), and whether the
readers still read their fake documents as they must (test). They read in this process, so that a reader's error
shows its traceback; what they print is Turkish lines for the terminal.
"""

import traceback

from .. import parsers
from ..domain.labels import currency_label, format_amount, label
from ..domain.models import Invoice, ParseResult, SourceRef, Statement, Transaction
from . import Skipped, Unreadable, choose, mail_probe, parse_document, registry, without_reader, xml_probe
from .common import is_business
from .contract import Document, Format, Probe, SourceDocument
from .mail import read_mail
from .pdf import ocr_available, page_text


def probe(doc: Document) -> list[str]:
    """What the selection shows the readers of doc's format, stage by stage, and what each of them says."""
    lines = [f"{doc.name}: {len(doc.data)} bayt"]
    if is_business(doc.name):
        return [*lines, "Şirket belgesi (dosya adındaki işaret): okuyuculara gösterilmez."]
    source = SourceDocument(doc)
    try:
        stages = _stages(source)
    except Exception as exc:  # a document that cannot even be opened  # noqa: BLE001
        return [*lines, f"Açılamadı: {type(exc).__name__}: {exc}"]
    finally:
        source.close()
    if not stages:
        return [*lines, "Okuyucuların okuduğu bir dosya türü değil."]
    for title, seen in stages:
        lines += ["", title, *_excerpt(seen)]
        if seen.format is Format.EMAIL and is_business(seen.subject):
            lines.append("Şirket belgesi (konudaki işaret): okuyuculara gösterilmez.")
            continue
        lines.append("Okuyucular:")
        for reader in parsers.readers():  # the readers the selection asks
            if seen.format not in reader.formats:
                continue
            found = reader.detect(seen)
            if found is None:
                lines.append(f"  · {reader.id}: tanımadı")
            else:
                sure = f"{found.confidence:.2f}".replace(".", ",")
                lines.append(f"  {'✓' if found.confidence >= 0.5 else '?'} {reader.id} (güven {sure}): {found.reason}")
        try:
            chosen = choose(seen)
        except Unreadable as exc:
            lines.append(f"Okuyamaz: {exc}")
        else:
            lines.append(f"Okuyacak: {chosen.id} — {chosen.name}" if chosen else "Okuyacak: hiçbiri")
            if chosen is None and seen.format is Format.EMAIL:
                reason, business = without_reader(read_mail(doc.data))
                lines.append(
                    "Şirket belgesi (selamlamadaki muhatap ya da işveren primi)" if business else f"İleti: {reason}"
                )
    return lines


def _stages(source: SourceDocument) -> list[tuple[str, Probe]]:
    """The probes the selection shows the readers, in its order (parsers.parse_document)."""
    if source.ext == ".eml":
        seen = mail_probe(source)
        return [(f"E-posta: gönderen {seen.sender or '?'}, konu {seen.subject!r}: gövdesinin metni", seen)]
    if source.ext == ".xml":
        return [("XML: belgenin başı", xml_probe(source))]
    if source.kind in ("xls", "xlsx") or (source.kind == "html" and source.ext in (".xls", ".xlsx")):
        rows = source.rows[:20]
        return [
            (
                f"Tablo ({source.kind}), sayfa {source.sheet_name!r}",
                Probe(source.name, Format.SHEET, rows=rows, sheet=source.kind),
            )
        ]
    if source.ext in (".html", ".htm") or source.kind == "html":
        return [("HTML", Probe(source.name, Format.HTML, text=source.text))]
    if source.ext != ".pdf":
        return []
    pages = source.pdf.pages
    first = page_text(pages[0]) if pages else ""
    stages = [(f"PDF, {len(pages)} sayfa: ilk sayfanın metni", Probe(source.name, Format.PDF, text=first))]
    if len(first.strip()) < 80 and any(p.images for p in pages):
        if ocr_available():
            text = "\n".join(line.text for page in source.ocr_pages for line in page)
            stages.append(("Sayfa görüntüsü: OCR'ın okuduğu metin", Probe(source.name, Format.SCAN, text=text)))
        else:
            stages.append(("Sayfa görüntüsü, ama bu sistemde OCR yok", Probe(source.name, Format.SCAN)))
    return stages


def _excerpt(seen: Probe) -> list[str]:
    if seen.format is Format.SHEET:
        return [f"  {' | '.join(str(c) for c in row if c not in (None, ''))}" for row in seen.rows[:8]]
    text = " ".join(seen.text.split())
    return [f"  {text[:400]}{'…' if len(text) > 400 else ''}"] if text else ["  (metin yok)"]


def debug(doc: Document) -> list[str]:
    """What the reader that takes doc reads, row by row with where each row is printed; why nothing is read
    otherwise, with the traceback of a reader's error."""
    try:
        result = parse_document(doc)
    except Skipped as exc:
        who = f" ({exc.parser} tanıdı)" if exc.parser else ""
        return [f"{doc.name}{who}: {exc}" if exc.business else f"{doc.name}: işlenmedi{who}: {exc}"]
    except Unreadable as exc:
        who = f" ({exc.parser} tanıdı)" if exc.parser else ""
        lines = [f"{doc.name}: okunamadı{who}: {exc}"]
        if exc.__cause__ is not None:
            lines += "".join(traceback.format_exception(exc.__cause__)).rstrip().splitlines()
        return lines
    return _result(doc.name, result)


def _result(name: str, result: ParseResult) -> list[str]:
    reader = registry.find(result.parser)
    lines = [f"{name} → {result.parser} (sürüm {registry.version_of(reader) if reader else '?'})"]
    lines += [f"{what}: {value}" for what, value in (("Sahibi", result.holder), ("Başlık", result.title)) if value]
    lines += [f"Dekont anahtarı: {result.receipt_key}"] if result.receipt_key else []
    lines += [f"Hesap {a.id}: {a.label} ({label(a.type)}, {currency_label(a.currency)})" for a in result.accounts]
    for s in result.statements:
        lines += ["", _statement(s), *_terms(s), *(_row(t) for t in s.transactions)]
    if result.transactions:
        lines += ["", "Ekstresiz satırlar:", *(_row(t) for t in result.transactions)]
    for invoice in result.invoices:
        lines += ["", *_invoice(invoice)]
    return lines


def _invoice(i: Invoice) -> list[str]:
    """A bill or a receipt: its seller, number, dates and total, then its lines."""
    due = f", son ödeme {i.due}" if i.due else ""
    head = f"{label(i.kind)}: {i.seller} {i.number} {i.issued}{due} — {format_amount(i.total)} {currency_label(i.currency)}"
    lines = [head + f"  [{where(i.ref)}]"]
    for line in i.lines:
        quantity = f"{line.quantity:g} × " if line.quantity is not None else ""
        lines.append(f"  {quantity}{line.description}: {format_amount(line.amount)}")
    return lines


def _statement(s: Statement) -> str:
    period = f"{s.start} – {s.cut_date}" if s.start else f"kesim {s.cut_date}"
    if s.is_account:
        check = f"bakiye denetimi {s.checks_ok}/{s.checks_total}"
    else:
        printed = format_amount(s.total) if s.total is not None else "yazmıyor"
        check = f"bankanın toplamı {printed}, satırlarla {format_amount(s.computed_total)}"
    verdict = "doğrulandı" if s.verified else "DOĞRULANMADI"
    return f"{s.account} {period}: {check} — {verdict} ({len(s.transactions)} satır)"


def _terms(s: Statement) -> list[str]:
    """What a card statement prints for paying it, as much of it as it prints."""
    terms = [f"son ödeme {s.due_date}"] if s.due_date else []
    terms += [f"asgari tutar {format_amount(s.minimum_payment)}"] if s.minimum_payment is not None else []
    terms += [f"kart limiti {format_amount(s.credit_limit)}"] if s.credit_limit is not None else []
    terms += [f"sonraki kesim {s.next_cut}"] if s.next_cut else []
    return [f"Ödeme: {', '.join(terms)}"] if terms else []


def _row(t: Transaction) -> str:
    balance = f"bakiye {format_amount(t.balance)}" if t.balance is not None else ""
    extra = " ".join(x for x in (t.installment and f"taksit {t.installment}", t.original, t.counterparty, balance) if x)
    return (
        f"  {t.date}  {format_amount(t.amount):>12}  {label(t.kind)}: {t.description}"
        + (f" ({extra})" if extra else "")
        + f"  [{where(t.ref)}]"
    )


def where(ref: SourceRef | None) -> str:
    """A row's place in its document, in Turkish."""
    if ref is None:
        return "yeri yok"
    parts = [f"s.{ref.page}"] if ref.page is not None else []
    if ref.box is not None:
        x0, top, x1, bottom = ref.box
        parts.append(f"kutu {x0:g},{top:g}–{x1:g},{bottom:g}")
    if ref.line is not None:
        parts.append(f"satır {ref.line}")
    if ref.sheet is not None:
        parts.append(f"sayfa {ref.sheet!r}" if ref.sheet else "tablo")
    if ref.row is not None:
        parts.append(f"satır {ref.row}")
    if ref.span is not None:
        parts.append(f"metin {ref.span[0]}–{ref.span[1]}")
    return " ".join(parts)


def test(reader_id: str | None = None) -> tuple[bool, list[str]]:
    """Read every fake document, or reader_id's, and check it (fakes.check); whether all read as they must."""
    from ..fakes import check, specimens  # the fake documents import the readers

    if reader_id is not None and registry.find(reader_id) is None:
        return False, [f"Böyle bir okuyucu yok: {reader_id}"]
    chosen = [s for s in specimens() if reader_id in (None, s.reader)]
    if not chosen:
        return False, [f"{reader_id} okuyucusunun sahte belgesi yok."]
    lines: list[str] = []
    failed = 0
    for reader in dict.fromkeys(s.reader for s in chosen):
        lines.append(f"{reader} — {registry.label(reader)}")
        for specimen in (s for s in chosen if s.reader == reader):
            problems = check(specimen)
            failed += bool(problems)
            said = "; ".join(problems) if problems else f"{specimen.rows} satır, yerleriyle; ekstreler doğrulandı"
            lines.append(f"  {'✗' if problems else '✓'} {specimen.name}: {said}")
    if reader_id is None:
        missing = [r.id for r in registry.readers() if r.id not in {s.reader for s in chosen}]
        lines += [f"Sahte belgesi olmayan okuyucular: {', '.join(missing)}"] if missing else []
    lines.append(f"Sahte belgeler: {len(chosen)} · sorunlu: {failed}")
    return failed == 0, lines
