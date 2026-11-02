"""The exports (F20): the single-file report, the rows as CSV and as an Excel workbook, and the month-end pages.
The service writes them into the data dir's exports folder with every analysis it makes (a refresh, after new
documents and every night); the interface lists them and downloads one, the month-end pages zipped together. Only
these files are served, under names the service gives them: nothing else in the folder, and no path a request makes
up."""

import io
import zipfile
from dataclasses import dataclass
from datetime import UTC, datetime
from enum import StrEnum
from pathlib import Path

from .. import month_end
from .workspace import Workspace


class ExportKind(StrEnum):
    REPORT = "report"  # the MVP's single-file HTML report; its own CSP lets nothing in from outside
    CSV = "csv"  # the rows: ';' between the fields, a decimal comma; Turkish Excel opens it as it is
    XLSX = "xlsx"  # the workbook with the MVP's sheets
    MONTH_END = "month_end"  # the month-end pages, script-free HTML, in one zip


# What the analysis writes for each kind (app.analysis.write_outputs), and how it downloads.
FILES = {ExportKind.REPORT: "gider_raporu.html", ExportKind.CSV: "islemler.csv", ExportKind.XLSX: "islemler.xlsx"}
MEDIA = {
    ExportKind.REPORT: "text/html; charset=utf-8",
    ExportKind.CSV: "text/csv; charset=utf-8",
    ExportKind.XLSX: "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
    ExportKind.MONTH_END: "application/zip",
}
_NAMES = {
    ExportKind.REPORT: "iplikci-rapor-{day}.html",
    ExportKind.CSV: "iplikci-islemler-{day}.csv",
    ExportKind.XLSX: "iplikci-islemler-{day}.xlsx",
    ExportKind.MONTH_END: "iplikci-ay-sonu-{day}.zip",
}


class Missing(LookupError):
    """The analysis has not written this export yet."""


@dataclass(frozen=True)
class Export:
    kind: ExportKind
    name: str  # the name it downloads under, with the day it was made
    size: int  # bytes; the month-end pages: their files together, before zipping
    made_at: str  # when the analysis wrote it, ISO in UTC


@dataclass(frozen=True)
class Download:
    name: str
    media_type: str
    content: bytes


def _files(ws: Workspace, kind: ExportKind) -> list[Path]:
    """The files an export is made of; a link someone put in the folder is never one of them."""
    if kind is ExportKind.MONTH_END:
        folder = ws.exports / month_end.FOLDER
        if not folder.is_dir() or folder.is_symlink():
            return []
        return sorted(p for p in folder.iterdir() if p.is_file() and not p.is_symlink())
    path = ws.exports / FILES[kind]
    return [path] if path.is_file() and not path.is_symlink() else []


def _export(kind: ExportKind, files: list[Path]) -> Export:
    stats = [p.stat() for p in files]
    made = datetime.fromtimestamp(max(s.st_mtime for s in stats), UTC)
    day = made.astimezone().date().isoformat()  # the user's own calendar day
    return Export(kind, _NAMES[kind].format(day=day), sum(s.st_size for s in stats), made.isoformat(timespec="seconds"))


def every(ws: Workspace) -> list[Export]:
    """The exports the analysis has written, in a fixed order; none before the first analysis."""
    found: list[Export] = []
    for kind in ExportKind:
        files = _files(ws, kind)
        if files:
            found.append(_export(kind, files))
    return found


def download(ws: Workspace, kind: ExportKind) -> Download:
    """An export's bytes and the name it downloads under; Missing when the analysis has not written it."""
    files = _files(ws, kind)
    if not files:
        raise Missing(kind.value)
    name = _export(kind, files).name
    if kind is not ExportKind.MONTH_END:
        return Download(name, MEDIA[kind], files[0].read_bytes())
    buffer = io.BytesIO()
    with zipfile.ZipFile(buffer, "w", zipfile.ZIP_DEFLATED) as archive:
        for path in files:
            archive.write(path, f"{month_end.FOLDER}/{path.name}")
    return Download(name, MEDIA[kind], buffer.getvalue())
