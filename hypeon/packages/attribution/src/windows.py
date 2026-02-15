"""Attribution window helpers: conversions only count if within platform window (e.g. 7d click, 1d view)."""
import re
from datetime import date


def parse_attribution_setting(setting: str | None) -> tuple[int, int]:
    """
    Parse e.g. '7d_click_1d_view' into (click_window_days, view_window_days).
    Returns (7, 1). If invalid or None, returns (30, 1) as default.
    """
    if not setting:
        return (30, 1)
    parts = setting.lower().replace("-", "_").split("_")
    click_d, view_d = 30, 1
    i = 0
    while i < len(parts):
        s = parts[i]
        m = re.match(r"^(\d+)d?$", s)
        if m and i + 1 < len(parts):
            n = int(m.group(1))
            if "click" in parts[i + 1]:
                click_d = n
            elif "view" in parts[i + 1]:
                view_d = n
            i += 2
        else:
            i += 1
    return (click_d, view_d)


def is_conversion_in_window(
    touch_date: date,
    conversion_date: date,
    window_days: int,
    is_click: bool = True,
) -> bool:
    """True if conversion_date is within window_days of touch_date (inclusive)."""
    if conversion_date < touch_date:
        return False
    delta = (conversion_date - touch_date).days
    return delta <= window_days
