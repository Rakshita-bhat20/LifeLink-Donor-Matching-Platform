"""URL map: every endpoint, its allowed roles and the controller that serves it."""
from flask import Blueprint, jsonify

from ..controllers import (admin_controller, auth_controller, donor_controller,
                           match_controller, request_controller)
from ..middleware.auth import require_auth

api = Blueprint("api", __name__, url_prefix="/api")

HOSPITAL = ("hospital", "admin")


@api.get("/health")
def health():
    return jsonify(status="ok")


# auth
api.post("/auth/register")(auth_controller.register)
api.post("/auth/login")(auth_controller.login)
api.get("/auth/me")(require_auth()(auth_controller.me))

# donors
api.get("/donors/me")(require_auth("donor")(donor_controller.get_profile))
api.put("/donors/me")(require_auth("donor")(donor_controller.save_profile))
api.get("/donors/me/offers")(require_auth("donor")(donor_controller.my_offers))
api.get("/donors")(require_auth(*HOSPITAL)(donor_controller.list_donors))

# requests and matching
api.post("/requests")(require_auth("hospital")(request_controller.create))
api.get("/requests")(require_auth(*HOSPITAL)(request_controller.list_all))
api.get("/requests/<int:request_id>")(require_auth(*HOSPITAL)(request_controller.detail))
api.post("/requests/<int:request_id>/match")(require_auth(*HOSPITAL)(request_controller.run_match))
api.get("/requests/<int:request_id>/matches")(require_auth(*HOSPITAL)(request_controller.list_matches))

# match lifecycle
api.post("/matches/<int:match_id>/respond")(require_auth("donor")(match_controller.respond))
api.post("/matches/<int:match_id>/fulfil")(require_auth(*HOSPITAL)(match_controller.fulfil))

# dashboard and audit
api.get("/stats")(require_auth()(admin_controller.stats))
api.get("/audit")(require_auth("admin")(admin_controller.audit_log))
api.get("/audit/verify")(require_auth("admin")(admin_controller.audit_verify))
