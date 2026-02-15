"""Date helpers used across packages."""
from datetime import date, timedelta
from typing import Optional, Tuple


def parse_date_range(
    start: Optional[date] = None,
    end: Optional[date] = None,
    default_days: int = 90,
) -> Tuple[date, date]:
    """Return (start_date, end_date). If either is None, use default_days from today."""
    today = date.today()
    if end is None:
        end = today
    if start is None:
        start = end - timedelta(days=default_days)
    if start > end:
        start, end = end, start
    return start, end


def business_days_between(start: date, end: date) -> int:
    """Approximate business days (exclude weekends)."""
    if start > end:
        start, end = end, start
    days = 0
    d = start
    while d <= end:
        if d.weekday() < 5:  # Mon=0 .. Fri=4
            days += 1
        d += timedelta(days=1)
    return days
