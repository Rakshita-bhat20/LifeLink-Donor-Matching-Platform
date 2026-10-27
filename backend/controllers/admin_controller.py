"""Dashboard statistics and audit trail."""
from flask import jsonify

from ..models import repo
from ..models.db import get_db
from ..services import audit


def stats():
    return jsonify(stats=repo.stats(get_db()))


def audit_log():
    return jsonify(entries=repo.audit_rows(get_db()))


def audit_verify():
    valid, count, bad_id = audit.verify(get_db())
    return jsonify(valid=valid, entries=count, first_bad_entry=bad_id)
