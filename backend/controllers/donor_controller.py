"""Donor profile and offer handling."""
from flask import g, jsonify, request

from ..models import repo
from ..models.db import get_db
from ..services import audit
from ..services.validators import validate_donor_profile


def get_profile():
    donor = repo.donor_by_user(get_db(), g.user["id"])
    if donor is None:
        return jsonify(error="No donor profile yet"), 404
    return jsonify(donor=donor)


def save_profile():
    profile = validate_donor_profile(request.get_json(silent=True) or {})
    db = get_db()
    donor = repo.save_donor(db, g.user["id"], profile)
    audit.append(db, f"user:{g.user['id']}", "donor.profile_saved",
                 {"donor": repo.donor_code(donor["id"]), "type": donor["donor_type"]})
    db.commit()
    return jsonify(donor=donor)


def list_donors():
    """Anonymised registry view for hospitals and admins (no names, no contact data)."""
    rows = repo.all_donors(get_db())
    return jsonify(donors=[{
        "code": repo.donor_code(d["id"]), "blood_group": d["blood_group"], "city": d["city"],
        "donor_type": d["donor_type"], "organs_pledged": d["organs_pledged"],
        "available": d["available"],
    } for d in rows])


def my_offers():
    db = get_db()
    donor = repo.donor_by_user(db, g.user["id"])
    if donor is None:
        return jsonify(offers=[])
    return jsonify(offers=repo.offers_for_donor(db, donor["id"]))
