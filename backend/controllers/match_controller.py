"""Donor responses and fulfilment."""
from datetime import date

from flask import g, jsonify, request

from ..models import repo
from ..models.db import get_db
from ..services import audit


def respond(match_id):
    decision = (request.get_json(silent=True) or {}).get("decision")
    if decision not in ("accept", "decline"):
        return jsonify(error="decision must be 'accept' or 'decline'", errors={"decision": "invalid"}), 400
    db = get_db()
    match = repo.match_by_id(db, match_id)
    donor = repo.donor_by_user(db, g.user["id"])
    if match is None or donor is None or match["donor_id"] != donor["id"]:
        return jsonify(error="Offer not found"), 404
    if match["status"] != "proposed":
        return jsonify(error=f"Offer already {match['status']}"), 409
    status = "accepted" if decision == "accept" else "declined"
    repo.set_match_status(db, match_id, status)
    audit.append(db, f"user:{g.user['id']}", f"match.{status}",
                 {"match": match_id, "request": match["request_id"]})
    db.commit()
    return jsonify(match={"id": match_id, "status": status})


def fulfil(match_id):
    db = get_db()
    match = repo.match_by_id(db, match_id)
    req = repo.request_by_id(db, match["request_id"]) if match else None
    if req is None or (g.user["role"] == "hospital" and req["hospital_id"] != g.user["id"]):
        return jsonify(error="Match not found"), 404
    if match["status"] != "accepted":
        return jsonify(error="Only accepted offers can be fulfilled"), 409
    repo.set_match_status(db, match_id, "fulfilled")
    donor = repo.donor_by_id(db, match["donor_id"])
    if req["kind"] == "blood":
        # Start the mandatory rest period so the same donor is not matched again.
        donor.update(last_donation_date=date.today().isoformat())
    else:
        donor.update(available=False)
    repo.save_donor(db, donor["user_id"], donor)
    done = repo.count_fulfilled(db, req["id"])
    needed = req["units_needed"] if req["kind"] == "blood" else 1
    if done >= needed:
        repo.set_request_status(db, req["id"], "fulfilled")
    audit.append(db, f"user:{g.user['id']}", "match.fulfilled",
                 {"match": match_id, "request": req["id"]})
    db.commit()
    return jsonify(match={"id": match_id, "status": "fulfilled"}, request_done=done >= needed)
