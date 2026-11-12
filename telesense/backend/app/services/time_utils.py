"""Indian Standard Time (IST, Asia/Kolkata, UTC+05:30) formatting utilities."""

from datetime import datetime, timedelta, timezone
from typing import Optional

IST = timezone(timedelta(hours=5, minutes=30), name="IST")


def to_ist(dt: Optional[datetime] = None) -> datetime:
    """Converts a UTC or naive datetime (treated as UTC) to IST (UTC+05:30)."""
    if dt is None:
        return datetime.now(timezone.utc).astimezone(IST)
    if dt.tzinfo is None:
        dt = dt.replace(tzinfo=timezone.utc)
    return dt.astimezone(IST)


def format_ist_datetime(dt: Optional[datetime] = None) -> str:
    """Returns 'DD MMM YYYY, HH:MM IST'."""
    return to_ist(dt).strftime("%d %b %Y, %H:%M IST")


def format_ist_timestamp(dt: Optional[datetime] = None) -> str:
    """Returns 'HH:MM:SS IST'."""
    return to_ist(dt).strftime("%H:%M:%S IST")


def format_ist_short(dt: Optional[datetime] = None) -> str:
    """Returns 'HH:MM IST'."""
    return to_ist(dt).strftime("%H:%M IST")

