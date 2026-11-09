"""Delivery window arithmetic. The only module allowed to convert time zones."""

from __future__ import annotations

from datetime import datetime, timedelta
from zoneinfo import ZoneInfo

MIN_WINDOW = timedelta(hours=2)


def to_customer_zone(moment: datetime, iana_zone: str) -> datetime:
    """Render a stored UTC instant in the customer's zone (ADR-0005)."""
    return moment.astimezone(ZoneInfo(iana_zone))


def windows_overlap(a_start: datetime, a_end: datetime,
                    b_start: datetime, b_end: datetime) -> bool:
    return a_start < b_end and b_start < a_end
