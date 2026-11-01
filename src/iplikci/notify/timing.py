"""When a notification may go out (ADR-0010): not in the quiet hours, not above its channel's rate, and after a
failed attempt only once its wait is over. What was kept back goes out as one digest when it may."""

from datetime import datetime, time, timedelta

from ..domain.codes import Channel

MAX_ATTEMPTS = 8  # a notification that failed this often is given up (after about three hours)
RATE_WINDOW = timedelta(hours=1)
# Messages per channel in RATE_WINDOW; what comes beyond waits for the digest. The interface's box has no limit.
RATE: dict[Channel, int] = {Channel.DESKTOP: 10, Channel.TELEGRAM: 10, Channel.EMAIL: 4}
DIGEST_EVERY = timedelta(hours=1)  # at most one digest per channel this often


def backoff(attempts: int) -> timedelta:
    """How long a notification waits after its n-th failed attempt: a minute, then twice as long each time, an hour
    at most."""
    return timedelta(seconds=min(60 * 2 ** (attempts - 1), 3600))


def _clock(text: str) -> time:
    hours, minutes = text.split(":")
    return time(int(hours), int(minutes))


def quiet(hours: str, at: datetime) -> bool:
    """Whether a local time falls in the quiet hours ("23:00-08:00", over midnight or not; "" for none)."""
    if not hours:
        return False
    start, end = (_clock(part) for part in hours.split("-"))
    now = at.time().replace(second=0, microsecond=0)
    if start == end:
        return False
    return start <= now < end if start < end else now >= start or now < end
