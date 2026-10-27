"""Explainable donor-recipient scoring.

Each evaluate_* function returns a dict:
    eligible   - True when the donor passes every hard rule
    reasons    - why the donor was rejected (empty when eligible)
    score      - 0-100 (only meaningful when eligible)
    breakdown  - list of {label, points, max} so the UI can explain the score
    distance_km, transport_h (organ only)
"""
from datetime import date, datetime

from .clock import utcnow
from .compatibility import ORGAN_WINDOWS_H, abo_of, can_donate_blood, can_donate_organ
from .geo import haversine_km, transport_hours

BLOOD_MIN_AGE, BLOOD_MAX_AGE = 18, 65
BLOOD_MIN_WEIGHT_KG = 45
BLOOD_GAP_DAYS = 90
BLOOD_MAX_KM = 250.0
ORGAN_MIN_AGE, ORGAN_MAX_AGE = 18, 75


def parse_date(value):
    if not value:
        return None
    if isinstance(value, date):
        return value
    return datetime.strptime(value, "%Y-%m-%d").date()


def parse_hla(text):
    """'a2, A24,b7' -> {'A2', 'A24', 'B7'} (at most six antigens)."""
    if not text:
        return set()
    items = {part.strip().upper() for part in text.split(",") if part.strip()}
    return set(sorted(items)[:6])


def hla_matches(a, b):
    return len(parse_hla(a) & parse_hla(b))


def days_since(last_donation, today):
    last = parse_date(last_donation)
    return None if last is None else (today - last).days


def request_priority(urgency, created_at, now=None):
    """Triage index for hospital requests: urgency dominates, waiting time breaks ties."""
    now = now or utcnow()
    created = datetime.fromisoformat(created_at)
    waited_days = max(0, (now - created).days)
    return urgency * 20 + min(waited_days, 30)


def _rejected(*reasons):
    return {"eligible": False, "reasons": list(reasons), "score": 0, "breakdown": []}


def evaluate_blood(request, donor, today=None):
    today = today or date.today()
    if not donor["available"]:
        return _rejected("Donor marked unavailable")
    if donor["donor_type"] not in ("blood", "both"):
        return _rejected("Donor has not pledged blood")
    if not BLOOD_MIN_AGE <= donor["age"] <= BLOOD_MAX_AGE:
        return _rejected("Age outside 18-65")
    if donor["weight_kg"] < BLOOD_MIN_WEIGHT_KG:
        return _rejected("Weight below 45 kg")
    if not can_donate_blood(donor["blood_group"], request["blood_group"]):
        return _rejected("Blood group incompatible")
    gap = days_since(donor["last_donation_date"], today)
    if gap is not None and gap < BLOOD_GAP_DAYS:
        return _rejected(f"Donated less than {BLOOD_GAP_DAYS} days ago")
    dist = haversine_km(request["lat"], request["lng"], donor["lat"], donor["lng"])
    if dist > BLOOD_MAX_KM:
        return _rejected("Too far away")

    exact = donor["blood_group"] == request["blood_group"]
    compat_pts = 40 if exact else 25
    # Higher urgency punishes distance harder (exponent grows with urgency).
    exponent = 0.5 + request["urgency"] / 4
    prox_pts = 45 * (max(0.0, 1 - dist / BLOOD_MAX_KM) ** exponent)
    if gap is None or gap >= 180:
        ready_pts = 15
    else:
        ready_pts = 8 + 7 * (gap - BLOOD_GAP_DAYS) / (180 - BLOOD_GAP_DAYS)
    breakdown = [
        {"label": "Exact group" if exact else "Compatible group", "points": compat_pts, "max": 40},
        {"label": f"Proximity ({dist:.0f} km)", "points": round(prox_pts, 1), "max": 45},
        {"label": "Donation readiness", "points": round(ready_pts, 1), "max": 15},
    ]
    score = compat_pts + prox_pts + ready_pts
    return {"eligible": True, "reasons": [], "score": round(score, 1),
            "breakdown": breakdown, "distance_km": round(dist, 1)}


def evaluate_organ(request, donor):
    organ = request["organ"]
    if not donor["available"]:
        return _rejected("Donor marked unavailable")
    if donor["donor_type"] not in ("organ", "both"):
        return _rejected("Donor has not pledged organs")
    if organ not in donor["organs_pledged"]:
        return _rejected(f"{organ.title()} not pledged")
    if not ORGAN_MIN_AGE <= donor["age"] <= ORGAN_MAX_AGE:
        return _rejected("Age outside 18-75")
    if not can_donate_organ(donor["blood_group"], request["blood_group"]):
        return _rejected("ABO incompatible")
    dist = haversine_km(request["lat"], request["lng"], donor["lat"], donor["lng"])
    total_h = transport_hours(dist)
    window = ORGAN_WINDOWS_H[organ]
    if total_h > window:
        return _rejected(f"Transport {total_h:.1f} h exceeds {window} h viability window")

    identical = abo_of(donor["blood_group"]) == abo_of(request["blood_group"])
    abo_pts = 20 if identical else 12
    via_pts = 35 * (1 - total_h / window)
    hla_weight = 25 if organ == "kidney" else 15
    n_hla = hla_matches(donor["hla"], request.get("hla"))
    hla_pts = hla_weight * n_hla / 6
    patient_age = request.get("patient_age")
    age_pts = 10 * max(0.0, 1 - abs(donor["age"] - patient_age) / 40) if patient_age else 5.0
    max_pts = 20 + 35 + hla_weight + 10
    raw = abo_pts + via_pts + hla_pts + age_pts
    breakdown = [
        {"label": "ABO identical" if identical else "ABO compatible", "points": abo_pts, "max": 20},
        {"label": f"Viability margin ({total_h:.1f}/{window} h)", "points": round(via_pts, 1), "max": 35},
        {"label": f"HLA match ({n_hla}/6)", "points": round(hla_pts, 1), "max": hla_weight},
        {"label": "Age proximity", "points": round(age_pts, 1), "max": 10},
    ]
    return {"eligible": True, "reasons": [], "score": round(100 * raw / max_pts, 1),
            "breakdown": breakdown, "distance_km": round(dist, 1),
            "transport_h": round(total_h, 1)}


def evaluate(request, donor, today=None):
    if request["kind"] == "blood":
        return evaluate_blood(request, donor, today)
    return evaluate_organ(request, donor)


def rank_donors(request, donors, limit=10, today=None):
    """Return (ranked eligible candidates, {reason: count} for the rejected)."""
    ranked, rejected = [], {}
    for donor in donors:
        result = evaluate(request, donor, today)
        if result["eligible"]:
            ranked.append({"donor": donor, **result})
        else:
            for reason in result["reasons"]:
                key = reason.split("(")[0].strip()
                rejected[key] = rejected.get(key, 0) + 1
    ranked.sort(key=lambda r: (-r["score"], r["distance_km"], r["donor"]["id"]))
    return ranked[:limit], rejected
