"""Tests for attribution window logic: conversions outside setting window are not assigned."""
from datetime import date

from packages.attribution.src.windows import (
    is_conversion_in_window,
    parse_attribution_setting,
)


def test_parse_attribution_setting():
    click_d, view_d = parse_attribution_setting("7d_click_1d_view")
    assert click_d == 7
    assert view_d == 1
    click_d2, view_d2 = parse_attribution_setting(None)
    assert click_d2 == 30 and view_d2 == 1


def test_conversion_in_window_within():
    touch = date(2025, 1, 1)
    conv = date(2025, 1, 5)
    assert is_conversion_in_window(touch, conv, window_days=7) is True


def test_conversion_outside_window_not_assigned():
    touch = date(2025, 1, 1)
    conv = date(2025, 1, 15)
    assert is_conversion_in_window(touch, conv, window_days=7) is False
