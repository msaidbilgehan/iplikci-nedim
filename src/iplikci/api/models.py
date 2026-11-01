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


class SystemOut(BaseModel):
    service: ServiceOut
    documents: dict[str, int]
    readers: list[ReaderHealthOut]
    disk: DiskOut
    queue: QueueOut


class EventOut(BaseModel):
    id: int
    at: str
    kind: str
    target: str
    detail: dict[str, Any]
