"""Registration and login."""
from flask import current_app, g, jsonify, request
from sqlite3 import IntegrityError
from werkzeug.security import check_password_hash, generate_password_hash

from ..models import repo
from ..models.db import get_db
from ..services import audit
from ..services.auth import issue_token
from ..services.validators import validate_register


def _public(user):
    return {"id": user["id"], "name": user["name"], "email": user["email"], "role": user["role"]}


def _token_for(user):
    cfg = current_app.config
    return issue_token(user["id"], user["role"], cfg["SECRET_KEY"], cfg["TOKEN_TTL_SECONDS"])


def register():
    data = validate_register(request.get_json(silent=True) or {})
    db = get_db()
    try:
        user_id = repo.create_user(db, data["name"], data["email"],
                                   generate_password_hash(data["password"]), data["role"])
    except IntegrityError:
        return jsonify(error="Email already registered"), 409
    audit.append(db, f"user:{user_id}", "user.registered", {"role": data["role"]})
    db.commit()
    user = repo.user_by_id(db, user_id)
    return jsonify(token=_token_for(user), user=_public(user)), 201


def login():
    body = request.get_json(silent=True) or {}
    db = get_db()
    user = repo.user_by_email(db, str(body.get("email", "")).strip().lower())
    if user is None or not check_password_hash(user["password_hash"], str(body.get("password", ""))):
        return jsonify(error="Invalid email or password"), 401
    audit.append(db, f"user:{user['id']}", "user.login", {})
    db.commit()
    return jsonify(token=_token_for(user), user=_public(user))


def me():
    return jsonify(user=_public(g.user))
