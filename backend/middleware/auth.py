"""Authentication and role-based access control decorators."""
from functools import wraps

from flask import current_app, g, jsonify, request

from ..models import repo
from ..models.db import get_db
from ..services.auth import AuthError, verify_token


def require_auth(*roles):
    """Require a valid bearer token, and optionally one of the given roles."""
    def decorator(view):
        @wraps(view)
        def wrapper(*args, **kwargs):
            header = request.headers.get("Authorization", "")
            if not header.startswith("Bearer "):
                return jsonify(error="Authentication required"), 401
            try:
                payload = verify_token(header[7:], current_app.config["SECRET_KEY"])
            except AuthError as exc:
                return jsonify(error=str(exc)), 401
            user = repo.user_by_id(get_db(), payload["uid"])
            if user is None:
                return jsonify(error="Unknown user"), 401
            if roles and user["role"] not in roles:
                return jsonify(error="You do not have permission for this action"), 403
            g.user = dict(user)
            return view(*args, **kwargs)
        return wrapper
    return decorator
