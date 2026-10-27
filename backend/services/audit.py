"""Tamper-evident audit trail.

Every row stores the SHA-256 of (previous hash + its own content), so editing
or deleting any historical row breaks every hash after it.
"""
import hashlib
import json

from .clock import utcnow

GENESIS = "0" * 64


def _digest(prev_hash, ts, actor, action, payload):
    raw = "|".join([prev_hash, ts, actor, action, payload])
    return hashlib.sha256(raw.encode()).hexdigest()


def append(db, actor, action, details=None):
    row = db.execute("SELECT hash FROM audit_log ORDER BY id DESC LIMIT 1").fetchone()
    prev_hash = row["hash"] if row else GENESIS
    ts = utcnow().isoformat(timespec="seconds")
    payload = json.dumps(details or {}, sort_keys=True)
    new_hash = _digest(prev_hash, ts, actor, action, payload)
    db.execute(
        "INSERT INTO audit_log (ts, actor, action, payload, prev_hash, hash) VALUES (?,?,?,?,?,?)",
        (ts, actor, action, payload, prev_hash, new_hash),
    )
    return new_hash


def verify(db):
    """Return (is_valid, number_of_rows, id_of_first_bad_row_or_None)."""
    prev_hash, count = GENESIS, 0
    for row in db.execute("SELECT * FROM audit_log ORDER BY id"):
        count += 1
        expected = _digest(prev_hash, row["ts"], row["actor"], row["action"], row["payload"])
        if row["prev_hash"] != prev_hash or row["hash"] != expected:
            return False, count, row["id"]
        prev_hash = row["hash"]
    return True, count, None
