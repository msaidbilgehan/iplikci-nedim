"""The API's answers (pydantic at the boundary). Amounts, when they come, are minor units with their currency."""

from typing import Any, Literal

from pydantic import BaseModel


class LoginLink(BaseModel):
    url: str


class ReaderHealthOut(BaseModel):
    parser: str
    name: str
    version: str
    documents: int
    statements: int
    verified: int
    last_read: str
    alarms: int


class DiskOut(BaseModel):
    vault: int
    database: int
    free: int


class ServiceOut(BaseModel):
    version: str
    started_at: str
    pid: int
    home: str


class FailedJobOut(BaseModel):
    id: int
    kind: str
    attempts: int
    finished_at: str
    error: str


class QueueOut(BaseModel):
    counts: dict[str, int]
    next_run: str
    failures: list[FailedJobOut]


class RefusedMailOut(BaseModel):
    taken: Literal["unlisted", "unverified", "business"]
    reason: str  # what the trust rule saw: no-dmarc, dmarc:fail, header-from:…
    domain: str  # the sender's domain; "" for a sender on no list
    count: int
    label: str  # why, in Turkish


class MailOut(BaseModel):
    connector: Literal["imap", "browser_bridge"]
    configured: bool
    last_run: str
    last_error: str
    stopped: bool
    start_day: str  # where the history begins
    history_due: bool  # the extension has not scanned Gmail for this start day and these senders yet
    refused: list[RefusedMailOut]  # messages the extension delivered that were not kept, by why; most first


class BackupHealthOut(BaseModel):
    last: str
    next: str
    count: int
    size: int
    rehearsal: str
    rehearsal_ok: bool | None


class SystemOut(BaseModel):
    service: ServiceOut
    documents: dict[str, int]
    readers: list[ReaderHealthOut]
    disk: DiskOut
    queue: QueueOut
    mail: MailOut
    backup: BackupHealthOut


class BackupOut(BaseModel):
    name: str
    created_at: str
    reason: str
    app: str
    documents: int
    annotations: int
    size: int  # bytes of its own files; the originals live in the shared store
    damaged: int  # originals left out because their bytes no longer matched their names


class EventOut(BaseModel):
    id: int
    at: str
    kind: str
    target: str
    detail: dict[str, Any]
