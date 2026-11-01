"""The API's answers (pydantic at the boundary). Amounts, when they come, are minor units with their currency."""

from typing import Any

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


class MailOut(BaseModel):
    connector: str
    configured: bool
    last_run: str
    last_error: str
    stopped: bool


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
