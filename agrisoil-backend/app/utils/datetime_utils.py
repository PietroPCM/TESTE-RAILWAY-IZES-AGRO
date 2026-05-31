from __future__ import annotations

from datetime import datetime, timezone
from typing import Any


def utc_iso(dt: datetime | None) -> str | None:
    if dt is None:
        return None

    if dt.tzinfo is None:
        dt = dt.replace(tzinfo=timezone.utc)

    return dt.astimezone(timezone.utc).isoformat().replace("+00:00", "Z")


def serialize_utc_payload(value: Any) -> Any:
    if isinstance(value, datetime):
        return utc_iso(value)
    if isinstance(value, dict):
        return {key: serialize_utc_payload(item) for key, item in value.items()}
    if isinstance(value, list):
        return [serialize_utc_payload(item) for item in value]
    if isinstance(value, tuple):
        return [serialize_utc_payload(item) for item in value]
    return value
