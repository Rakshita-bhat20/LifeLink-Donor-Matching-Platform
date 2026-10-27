"""Data-access helpers. All SQL is parameterised; controllers never build SQL strings."""
import json
from ..services.clock import utcnow


def now_iso():
    return utcnow().isoformat(timespec="seconds")


def donor_dict(row):
    data = dict(row)
    data["organs_pledged"] = json.loads(data["organs_pledged"])
    data["available"] = bool(data["available"])
    return data


def donor_code(donor_id):
    return f"D-{donor_id:04d}"


# ---- users -----------------------------------------------------------------
def create_user(db, name, email, password_hash, role):
    cur = db.execute(
        "INSERT INTO users (name, email, password_hash, role, created_at) VALUES (?,?,?,?,?)",
        (name, email, password_hash, role, now_iso()),
    )
    return cur.lastrowid


def user_by_email(db, email):
    return db.execute("SELECT * FROM users WHERE email = ?", (email,)).fetchone()


def user_by_id(db, user_id):
    return db.execute("SELECT * FROM users WHERE id = ?", (user_id,)).fetchone()


# ---- donors ----------------------------------------------------------------
def donor_by_user(db, user_id):
    row = db.execute("SELECT * FROM donors WHERE user_id = ?", (user_id,)).fetchone()
    return donor_dict(row) if row else None


def donor_by_id(db, donor_id):
    row = db.execute("SELECT * FROM donors WHERE id = ?", (donor_id,)).fetchone()
    return donor_dict(row) if row else None


def all_donors(db):
    return [donor_dict(r) for r in db.execute("SELECT * FROM donors ORDER BY id")]


def save_donor(db, user_id, profile):
    values = (
        profile["blood_group"], profile["age"], profile["weight_kg"], profile["donor_type"],
        json.dumps(profile["organs_pledged"]), profile["hla"], profile["city"],
        profile["lat"], profile["lng"], profile["last_donation_date"], int(profile["available"]),
    )
    if donor_by_user(db, user_id):
        db.execute(
            "UPDATE donors SET blood_group=?, age=?, weight_kg=?, donor_type=?, organs_pledged=?,"
            " hla=?, city=?, lat=?, lng=?, last_donation_date=?, available=? WHERE user_id=?",
            values + (user_id,),
        )
    else:
        db.execute(
            "INSERT INTO donors (blood_group, age, weight_kg, donor_type, organs_pledged, hla,"
            " city, lat, lng, last_donation_date, available, user_id) VALUES (?,?,?,?,?,?,?,?,?,?,?,?)",
            values + (user_id,),
        )
    return donor_by_user(db, user_id)


# ---- requests --------------------------------------------------------------
def create_request(db, hospital_id, data):
    cur = db.execute(
        "INSERT INTO requests (hospital_id, patient_ref, kind, organ, blood_group, urgency,"
        " units_needed, patient_age, hla, city, lat, lng, created_at) VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?)",
        (hospital_id, data["patient_ref"], data["kind"], data["organ"], data["blood_group"],
         data["urgency"], data["units_needed"], data["patient_age"], data["hla"],
         data["city"], data["lat"], data["lng"], now_iso()),
    )
    return request_by_id(db, cur.lastrowid)


def request_by_id(db, request_id):
    row = db.execute("SELECT * FROM requests WHERE id = ?", (request_id,)).fetchone()
    return dict(row) if row else None


def list_requests(db, hospital_id=None):
    if hospital_id is None:
        rows = db.execute("SELECT * FROM requests ORDER BY id DESC")
    else:
        rows = db.execute("SELECT * FROM requests WHERE hospital_id = ? ORDER BY id DESC", (hospital_id,))
    return [dict(r) for r in rows]


def set_request_status(db, request_id, status):
    db.execute("UPDATE requests SET status = ? WHERE id = ?", (status, request_id))


# ---- matches ---------------------------------------------------------------
def replace_proposals(db, request_id, candidates):
    """Drop stale 'proposed' rows and insert fresh ones, skipping donors who already answered."""
    db.execute("DELETE FROM matches WHERE request_id = ? AND status = 'proposed'", (request_id,))
    answered = {r["donor_id"] for r in db.execute(
        "SELECT donor_id FROM matches WHERE request_id = ?", (request_id,))}
    created = 0
    for cand in candidates:
        if cand["donor"]["id"] in answered:
            continue
        db.execute(
            "INSERT INTO matches (request_id, donor_id, score, breakdown, distance_km, transport_h,"
            " created_at) VALUES (?,?,?,?,?,?,?)",
            (request_id, cand["donor"]["id"], cand["score"], json.dumps(cand["breakdown"]),
             cand["distance_km"], cand.get("transport_h"), now_iso()),
        )
        created += 1
    return created


def match_by_id(db, match_id):
    row = db.execute("SELECT * FROM matches WHERE id = ?", (match_id,)).fetchone()
    return dict(row) if row else None


def matches_for_request(db, request_id):
    return [dict(r) for r in db.execute(
        "SELECT m.*, d.blood_group AS donor_group, d.city AS donor_city, u.name AS donor_name"
        " FROM matches m JOIN donors d ON d.id = m.donor_id JOIN users u ON u.id = d.user_id"
        " WHERE m.request_id = ? ORDER BY m.score DESC, m.id", (request_id,))]


def offers_for_donor(db, donor_id):
    return [dict(r) for r in db.execute(
        "SELECT m.id, m.score, m.distance_km, m.status, m.created_at, r.kind, r.organ,"
        " r.blood_group, r.urgency, r.units_needed, r.city, u.name AS hospital"
        " FROM matches m JOIN requests r ON r.id = m.request_id JOIN users u ON u.id = r.hospital_id"
        " WHERE m.donor_id = ? ORDER BY m.id DESC", (donor_id,))]


def set_match_status(db, match_id, status):
    db.execute("UPDATE matches SET status = ? WHERE id = ?", (status, match_id))


def count_fulfilled(db, request_id):
    return db.execute(
        "SELECT COUNT(*) FROM matches WHERE request_id = ? AND status = 'fulfilled'",
        (request_id,)).fetchone()[0]


# ---- stats / audit ---------------------------------------------------------
def stats(db):
    one = lambda sql: db.execute(sql).fetchone()[0]  # noqa: E731
    groups = {r["blood_group"]: r["n"] for r in db.execute(
        "SELECT blood_group, COUNT(*) AS n FROM donors WHERE available = 1 GROUP BY blood_group")}
    return {
        "donors": one("SELECT COUNT(*) FROM donors"),
        "available_donors": one("SELECT COUNT(*) FROM donors WHERE available = 1"),
        "open_requests": one("SELECT COUNT(*) FROM requests WHERE status IN ('open','matched')"),
        "fulfilled_requests": one("SELECT COUNT(*) FROM requests WHERE status = 'fulfilled'"),
        "lives_touched": one("SELECT COUNT(*) FROM matches WHERE status = 'fulfilled'"),
        "donors_by_group": groups,
    }


def audit_rows(db, limit=50):
    return [dict(r) for r in db.execute("SELECT * FROM audit_log ORDER BY id DESC LIMIT ?", (limit,))]
