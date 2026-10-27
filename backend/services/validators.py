"""Input validation. Every function raises ValidationError with a field -> message map."""
import re
from datetime import date

from .compatibility import BLOOD_GROUPS, ORGAN_WINDOWS_H
from .scoring import parse_date

EMAIL_RE = re.compile(r"^[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Za-z]{2,}$")


class ValidationError(Exception):
    def __init__(self, errors):
        super().__init__("Validation failed")
        self.errors = errors


def is_valid_email(value):
    return isinstance(value, str) and len(value) <= 120 and bool(EMAIL_RE.match(value))


def is_strong_password(value):
    return (isinstance(value, str) and len(value) >= 8
            and any(c.isalpha() for c in value) and any(c.isdigit() for c in value))


def _number(data, key, errors, low, high, integer=False):
    value = data.get(key)
    if isinstance(value, bool) or not isinstance(value, (int, float)):
        errors[key] = "must be a number"
        return None
    if integer and int(value) != value:
        errors[key] = "must be a whole number"
        return None
    if not low <= value <= high:
        errors[key] = f"must be between {low} and {high}"
        return None
    return int(value) if integer else float(value)


def _text(data, key, errors, max_len=80):
    value = data.get(key)
    if not isinstance(value, str) or not value.strip():
        errors[key] = "is required"
        return None
    if len(value.strip()) > max_len:
        errors[key] = f"must be at most {max_len} characters"
        return None
    return value.strip()


def _choice(data, key, errors, options):
    value = data.get(key)
    if value not in options:
        errors[key] = f"must be one of {', '.join(options)}"
        return None
    return value


def _finish(errors, clean):
    if errors:
        raise ValidationError(errors)
    return clean


def validate_register(data):
    errors, clean = {}, {}
    clean["name"] = _text(data, "name", errors, 60)
    if not is_valid_email(data.get("email")):
        errors["email"] = "must be a valid email address"
    clean["email"] = (data.get("email") or "").strip().lower()
    if not is_strong_password(data.get("password")):
        errors["password"] = "needs 8+ characters with letters and digits"
    clean["password"] = data.get("password")
    clean["role"] = _choice(data, "role", errors, ("hospital", "donor"))
    return _finish(errors, clean)


def _location(data, errors, clean):
    clean["city"] = _text(data, "city", errors, 60)
    clean["lat"] = _number(data, "lat", errors, -90, 90)
    clean["lng"] = _number(data, "lng", errors, -180, 180)


def validate_donor_profile(data, today=None):
    errors, clean = {}, {}
    today = today or date.today()
    clean["blood_group"] = _choice(data, "blood_group", errors, BLOOD_GROUPS)
    clean["age"] = _number(data, "age", errors, 18, 80, integer=True)
    clean["weight_kg"] = _number(data, "weight_kg", errors, 30, 200)
    clean["donor_type"] = _choice(data, "donor_type", errors, ("blood", "organ", "both"))
    _location(data, errors, clean)
    organs = data.get("organs_pledged") or []
    if not isinstance(organs, list) or any(o not in ORGAN_WINDOWS_H for o in organs):
        errors["organs_pledged"] = f"must be a list from {', '.join(ORGAN_WINDOWS_H)}"
    elif clean["donor_type"] in ("organ", "both") and not organs:
        errors["organs_pledged"] = "select at least one organ"
    clean["organs_pledged"] = organs
    clean["hla"] = str(data.get("hla") or "")[:60]
    last = data.get("last_donation_date") or None
    try:
        if last and parse_date(last) > today:
            errors["last_donation_date"] = "cannot be in the future"
    except ValueError:
        errors["last_donation_date"] = "must be YYYY-MM-DD"
    clean["last_donation_date"] = last
    clean["available"] = bool(data.get("available", True))
    return _finish(errors, clean)


def validate_request(data):
    errors, clean = {}, {}
    clean["patient_ref"] = _text(data, "patient_ref", errors, 40)
    clean["kind"] = _choice(data, "kind", errors, ("blood", "organ"))
    clean["blood_group"] = _choice(data, "blood_group", errors, BLOOD_GROUPS)
    clean["urgency"] = _number(data, "urgency", errors, 1, 5, integer=True)
    _location(data, errors, clean)
    clean["organ"], clean["units_needed"], clean["patient_age"] = None, 1, None
    if clean["kind"] == "organ":
        clean["organ"] = _choice(data, "organ", errors, tuple(ORGAN_WINDOWS_H))
        clean["hla"] = str(data.get("hla") or "")[:60]
        if data.get("patient_age") not in (None, ""):
            clean["patient_age"] = _number(data, "patient_age", errors, 0, 100, integer=True)
    elif clean["kind"] == "blood":
        clean["units_needed"] = _number(data, "units_needed", errors, 1, 10, integer=True)
        clean["hla"] = ""
    return _finish(errors, clean)
