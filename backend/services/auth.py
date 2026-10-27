"""Stateless signed tokens (HMAC-SHA256) so the API needs no external JWT library."""
import base64
import hashlib
import hmac
import json
import time


class AuthError(Exception):
    """Raised when a token is missing, malformed, tampered with or expired."""


def _b64(data):
    return base64.urlsafe_b64encode(data).rstrip(b"=").decode()


def _unb64(text):
    return base64.urlsafe_b64decode(text + "=" * (-len(text) % 4))


def _sign(body, secret):
    return _b64(hmac.new(secret.encode(), body.encode(), hashlib.sha256).digest())


def issue_token(user_id, role, secret, ttl, now=None):
    now = int(now if now is not None else time.time())
    body = _b64(json.dumps({"uid": user_id, "role": role, "exp": now + ttl}).encode())
    return f"{body}.{_sign(body, secret)}"


def verify_token(token, secret, now=None):
    try:
        body, signature = token.split(".")
    except (ValueError, AttributeError) as exc:
        raise AuthError("Malformed token") from exc
    if not hmac.compare_digest(signature, _sign(body, secret)):
        raise AuthError("Bad signature")
    try:
        payload = json.loads(_unb64(body))
    except ValueError as exc:
        raise AuthError("Malformed token") from exc
    if payload["exp"] < (now if now is not None else time.time()):
        raise AuthError("Token expired")
    return payload
