"""The accounts as the screens see them (F05, F06, F07): how far each one's documents reach, and which accounts are
closed. An account whose documents stopped more than 180 days before the newest document is closed or no longer
followed: the screens list it apart and leave it out of every total (F07)."""

from datetime import date

from ..analysis import ACTIVE_DAYS, Dataset


def last_seen(ds: Dataset) -> dict[str, date]:
    """Each account's newest day its documents reach: a statement's or a list's last day, a receipt's or a bank
    notice's row."""
    seen: dict[str, date] = {}
    for s in ds.statements:
        seen[s.account] = max(seen.get(s.account, s.cut_date), s.cut_date)
    for line in ds.receipts:
        account, day = line.txn.account, line.txn.date
        seen[account] = max(seen.get(account, day), day)
    return seen


def closed(seen: dict[str, date]) -> set[str]:
    """The accounts whose documents stopped more than ACTIVE_DAYS before the newest document."""
    if not seen:
        return set()
    newest = max(seen.values())
    return {account for account, day in seen.items() if (newest - day).days > ACTIVE_DAYS}
