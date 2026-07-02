from datetime import UTC, datetime


def utc_now() -> datetime:
    return datetime.now(UTC)


def require_utc(value: datetime) -> datetime:
    if value.tzinfo is None:
        msg = "timestamp must be timezone-aware"
        raise ValueError(msg)
    return value.astimezone(UTC)
