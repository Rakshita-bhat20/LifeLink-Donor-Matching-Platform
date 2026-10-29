# LifeLink: Blood and Organ Donor-Recipient Matching Network

A three-tier web application that matches blood and organ requests from hospitals with
registered donors, and explains every match.
> The medical rules are simplified. It is not a clinical system. Do not enter real patient data.

## What makes it different

| Feature | Why it matters |
|---|---|
| Viability-aware organ matching | Each organ has a cold-ischemia window (heart 4 h, lung 6 h, liver and pancreas 12 h, kidney 36 h). Donors whose road or air transit time would exceed the window are excluded automatically. |
| Explainable score (0-100) | Every match shows its breakdown (compatibility, proximity or viability, HLA, readiness, age), and the hospital sees why other donors were excluded. |
| Urgency-aware ranking | Higher urgency penalises distance harder, so critical requests favour nearby donors. |
| Privacy by design | Hospitals see anonymous donor codes. A donor's name is revealed only after they accept. Patients are referenced by code, never by name. |
| Donation rest rule | Recording a blood donation starts the 90-day rest period and removes the donor from matching. |
| Tamper-evident audit trail | Every action goes into a SHA-256 hash chain. An admin can verify it and any edit to history is detected. |

## Architecture

    Presentation   frontend/   Single-page client (HTML, CSS, vanilla JS)
    Application    backend/    Flask REST API: routes -> controllers -> services
    Data           SQLite      users, donors, requests, matches, audit_log

## Run it

    python -m venv .venv
    source .venv/bin/activate          # Windows: .venv\Scripts\activate
    pip install -r requirements.txt
    python -m backend.seed             # demo users, donors and requests
    python -m backend.app              # open http://127.0.0.1:5000

Demo logins: hospital@lifelink.test / Hospital@123, donor@lifelink.test / Donor@1234,
admin@lifelink.test / Admin@1234. Set LIFELINK_SECRET to your own value before sharing the app.

## Test and analyse

    python -m unittest discover -s tests -t . -v     # unit and API tests
    python tools/static_check.py                     # exits 1 on any critical issue
    pip install pylint bandit pytest                 # optional industry tools
    pylint backend && bandit -r backend && pytest -q

## API summary

| Method | Endpoint | Role |
|---|---|---|
| POST | /api/auth/register, /api/auth/login | public |
| GET, PUT | /api/donors/me | donor |
| GET | /api/donors/me/offers | donor |
| POST | /api/matches/{id}/respond | donor |
| POST, GET | /api/requests | hospital |
| POST | /api/requests/{id}/match | hospital |
| GET | /api/requests/{id}/matches | hospital |
| POST | /api/matches/{id}/fulfil | hospital |
| GET | /api/stats | any logged-in user |
| GET | /api/audit, /api/audit/verify | admin |
