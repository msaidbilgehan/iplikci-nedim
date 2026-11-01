"""Browser sessions (ADR-0007): the SHA-256 of each session token, with its expiry. Times are ISO 8601 in UTC."""

from dataclasses import dataclass

from .db import Database


@dataclass(frozen=True, slots=True)
class Session:
    token_hash: str
    created_at: str
    renewed_at: str
    expires_at: str


def add(db: Database, token_hash: str, at: str, expires_at: str) -> None:
    with db.transaction():
        db.execute(
            "INSERT INTO sessions (token_hash, created_at, renewed_at, expires_at) VALUES (?, ?, ?, ?)",
            (token_hash, at, at, expires_at),
        )


def find(db: Database, token_hash: str) -> Session | None:
    row = db.one("SELECT * FROM sessions WHERE token_hash = ?", (token_hash,))
    return None if row is None else Session(row["token_hash"], row["created_at"], row["renewed_at"], row["expires_at"])


def renew(db: Database, token_hash: str, at: str, expires_at: str) -> None:
    with db.transaction():
        db.execute(
            "UPDATE sessions SET renewed_at = ?, expires_at = ? WHERE token_hash = ?", (at, expires_at, token_hash)
        )


def remove(db: Database, token_hash: str) -> None:
    with db.transaction():
        db.execute("DELETE FROM sessions WHERE token_hash = ?", (token_hash,))


def purge(db: Database, at: str) -> int:
    """Forget the sessions that expired before at; how many."""
    with db.transaction():
        return db.execute("DELETE FROM sessions WHERE expires_at <= ?", (at,)).rowcount
