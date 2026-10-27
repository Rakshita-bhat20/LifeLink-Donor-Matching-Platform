"""SQLite schema for LifeLink."""

SCHEMA = """
CREATE TABLE IF NOT EXISTS users (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    name TEXT NOT NULL,
    email TEXT NOT NULL UNIQUE,
    password_hash TEXT NOT NULL,
    role TEXT NOT NULL CHECK (role IN ('hospital', 'donor', 'admin')),
    created_at TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS donors (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    user_id INTEGER NOT NULL UNIQUE REFERENCES users(id),
    blood_group TEXT NOT NULL,
    age INTEGER NOT NULL,
    weight_kg REAL NOT NULL,
    donor_type TEXT NOT NULL CHECK (donor_type IN ('blood', 'organ', 'both')),
    organs_pledged TEXT NOT NULL DEFAULT '[]',
    hla TEXT NOT NULL DEFAULT '',
    city TEXT NOT NULL,
    lat REAL NOT NULL,
    lng REAL NOT NULL,
    last_donation_date TEXT,
    available INTEGER NOT NULL DEFAULT 1
);

CREATE TABLE IF NOT EXISTS requests (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    hospital_id INTEGER NOT NULL REFERENCES users(id),
    patient_ref TEXT NOT NULL,
    kind TEXT NOT NULL CHECK (kind IN ('blood', 'organ')),
    organ TEXT,
    blood_group TEXT NOT NULL,
    urgency INTEGER NOT NULL CHECK (urgency BETWEEN 1 AND 5),
    units_needed INTEGER NOT NULL DEFAULT 1,
    patient_age INTEGER,
    hla TEXT NOT NULL DEFAULT '',
    city TEXT NOT NULL,
    lat REAL NOT NULL,
    lng REAL NOT NULL,
    status TEXT NOT NULL DEFAULT 'open'
        CHECK (status IN ('open', 'matched', 'fulfilled', 'cancelled')),
    created_at TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS matches (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    request_id INTEGER NOT NULL REFERENCES requests(id),
    donor_id INTEGER NOT NULL REFERENCES donors(id),
    score REAL NOT NULL,
    breakdown TEXT NOT NULL,
    distance_km REAL NOT NULL,
    transport_h REAL,
    status TEXT NOT NULL DEFAULT 'proposed'
        CHECK (status IN ('proposed', 'accepted', 'declined', 'fulfilled')),
    created_at TEXT NOT NULL,
    UNIQUE (request_id, donor_id)
);

CREATE TABLE IF NOT EXISTS audit_log (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    ts TEXT NOT NULL,
    actor TEXT NOT NULL,
    action TEXT NOT NULL,
    payload TEXT NOT NULL,
    prev_hash TEXT NOT NULL,
    hash TEXT NOT NULL
);
"""
