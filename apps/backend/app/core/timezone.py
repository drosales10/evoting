"""Application timezone helpers. Storage remains UTC; display uses APP_TIMEZONE."""

from __future__ import annotations

from datetime import UTC, datetime
from zoneinfo import ZoneInfo

from app.core.config import settings


def app_zone() -> ZoneInfo:
    try:
        return ZoneInfo(settings.app_timezone)
    except Exception:
        return ZoneInfo("America/Caracas")


def now_utc() -> datetime:
    return datetime.now(UTC)


def to_app_tz(value: datetime) -> datetime:
    if value.tzinfo is None:
        value = value.replace(tzinfo=UTC)
    return value.astimezone(app_zone())


def format_app_datetime(value: datetime, *, with_seconds: bool = False) -> str:
    local = to_app_tz(value)
    pattern = "%d/%m/%Y %H:%M:%S" if with_seconds else "%d/%m/%Y %H:%M"
    return f"{local.strftime(pattern)} ({settings.app_timezone})"
