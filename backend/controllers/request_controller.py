"""Hospital requests: create, list, view, run matching engine."""
import json

from flask import current_app, g, jsonify, request

from ..models import repo
from ..models.db import get_db
from ..services import audit
from ..services.scoring import rank_donors, request_priority
from ..services.validators import validate_request


def _owned_request(db, request_id):
    """Return (request, error_response). Hospitals only see their own requests."""
    req = repo.request_by_id(db, request_id)
    if req is None:
        return None, (jsonify(error="Request not found"), 404)
    if g.user["role"] == "hospital" and req["hospital_id"] != g.user["id"]:
        return None, (jsonify(error="You do not have permission for this request"), 403)
    return req, None


def _decorate(req):
    req["priority"] = request_priority(req["urgency"], req["created_at"])
    return req


def create():
    data = validate_request(request.get_json(silent=True) or {})
    db = get_db()
    req = repo.create_request(db, g.user["id"], data)
    audit.append(db, f"user:{g.user['id']}", "request.created",
                 {"request": req["id"], "kind": req["kind"], "urgency": req["urgency"]})
    db.commit()
    return jsonify(request=_decorate(req)), 201


def list_all():
    hospital_id = g.user["id"] if g.user["role"] == "hospital" else None
    rows = [_decorate(r) for r in repo.list_requests(get_db(), hospital_id)]
    rows.sort(key=lambda r: (-r["priority"], r["id"]))
    return jsonify(requests=rows)


def detail(request_id):
    req, error = _owned_request(get_db(), request_id)
    return error or jsonify(request=_decorate(req))


def run_match(request_id):
    db = get_db()
    req, error = _owned_request(db, request_id)
    if error:
        return error
    if req["status"] in ("fulfilled", "cancelled"):
        return jsonify(error=f"Request is already {req['status']}"), 409
    ranked, rejected = rank_donors(req, repo.all_donors(db), current_app.config["MAX_MATCH_RESULTS"])
    created = repo.replace_proposals(db, request_id, ranked)
    if created:
        repo.set_request_status(db, request_id, "matched")
    audit.append(db, f"user:{g.user['id']}", "match.run",
                 {"request": request_id, "candidates": len(ranked), "rejected": sum(rejected.values())})
    db.commit()
    return jsonify(candidates=len(ranked), proposals_created=created, rejected=rejected,
                   matches=_matches_view(db, request_id))


def _matches_view(db, request_id):
    """Donor identity stays hidden until the donor accepts."""
    out = []
    for m in repo.matches_for_request(db, request_id):
        revealed = m["status"] in ("accepted", "fulfilled")
        out.append({
            "id": m["id"], "code": repo.donor_code(m["donor_id"]),
            "name": m["donor_name"] if revealed else None,
            "blood_group": m["donor_group"], "city": m["donor_city"], "score": m["score"],
            "distance_km": m["distance_km"], "transport_h": m["transport_h"],
            "status": m["status"], "breakdown": json.loads(m["breakdown"]),
        })
    return out


def list_matches(request_id):
    db = get_db()
    _req, error = _owned_request(db, request_id)
    return error or jsonify(matches=_matches_view(db, request_id))
