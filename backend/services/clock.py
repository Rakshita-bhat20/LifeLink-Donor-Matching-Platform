"""Single place for the current UTC time (naive, so it compares with stored ISO strings)."""
from datetime import datetime, timezone


def utcnow():
    return datetime.now(timezone.utc).replace(tzinfo=None)
