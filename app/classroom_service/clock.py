"""UTC and teacher-timezone clock helpers, injectable for deterministic tests."""

from __future__ import annotations

from datetime import datetime, timezone, timedelta, tzinfo
import os
import time
from zoneinfo import ZoneInfo, ZoneInfoNotFoundError


def teacher_zone(timezone_name: str) -> tzinfo:
    """Load IANA tzdata, with fixed-offset fallbacks for a minimal runtime.

    The portable classroom package ships tzdata.  The fallback keeps the
    dependency-free development tests usable on a bare Windows Python for UTC
    and the common Asia/Shanghai teacher setting; unknown zones fail closed.
    """
    try:
        return ZoneInfo(timezone_name)
    except ZoneInfoNotFoundError:
        offsets = {"UTC": 0, "Etc/UTC": 0, "Asia/Shanghai": 8, "Asia/Chongqing": 8, "Asia/Harbin": 8}
        if timezone_name in offsets:
            return timezone(timedelta(hours=offsets[timezone_name]), name=timezone_name)
        raise


def detect_teacher_timezone() -> str:
    """Return the teacher computer's IANA zone, never a browser/student zone."""
    try:
        from tzlocal import get_localzone_name
        return get_localzone_name()
    except Exception as exc:
        explicit = os.environ.get("CLASSROOM_TIMEZONE")
        if explicit:
            teacher_zone(explicit)
            return explicit
        raise RuntimeError("teacher timezone could not be detected; configure CLASSROOM_TIMEZONE explicitly") from exc


def utc_now() -> datetime:
    return datetime.now(timezone.utc)


def iso(value: datetime) -> str:
    if value.tzinfo is None:
        value = value.replace(tzinfo=timezone.utc)
    return value.astimezone(timezone.utc).isoformat(timespec="milliseconds")


def parse_iso(value: str) -> datetime:
    parsed = datetime.fromisoformat(value)
    if parsed.tzinfo is None:
        parsed = parsed.replace(tzinfo=timezone.utc)
    return parsed.astimezone(timezone.utc)


class Clock:
    """Clock interface; production uses system time and tests use a fixed clock."""

    def now(self) -> datetime:
        return utc_now()


class FixedClock(Clock):
    def __init__(self, value: datetime, timezone_name: str = "Asia/Shanghai"):
        self.value = value.astimezone(timezone.utc) if value.tzinfo else value.replace(tzinfo=timezone.utc)
        self.timezone_name = timezone_name

    def now(self) -> datetime:
        return self.value

    def set(self, value: datetime) -> None:
        self.value = value.astimezone(timezone.utc) if value.tzinfo else value.replace(tzinfo=timezone.utc)


def local_date_and_next_midnight(value: datetime, timezone_name: str) -> tuple[str, datetime]:
    zone = teacher_zone(timezone_name)
    local = value.astimezone(zone)
    date_text = local.date().isoformat()
    next_local = datetime.combine(local.date(), datetime.min.time(), tzinfo=zone)
    # The next calendar date is intentionally computed in local time so DST
    # days are 23/25 hours rather than a fixed 24-hour duration.
    from datetime import timedelta
    next_local = next_local + timedelta(days=1)
    return date_text, next_local.astimezone(timezone.utc)
