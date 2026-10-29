"""API and integration tests using Flask's test client and a throw-away SQLite file."""
import os
import tempfile
import unittest
from datetime import date

from backend.app import create_app
from backend.models import repo
from backend.models.db import get_db
from werkzeug.security import generate_password_hash

PROFILE = dict(blood_group="O+", age=29, weight_kg=68, donor_type="both", organs_pledged=["kidney"],
               hla="A2,A24,B7,B8,DR3,DR4", city="Bengaluru", lat=12.9716, lng=77.5946)
BLOOD_REQ = dict(patient_ref="PT-2001", kind="blood", blood_group="A+", urgency=5, units_needed=1,
                 city="Bengaluru", lat=12.9352, lng=77.6245)


class ApiTestCase(unittest.TestCase):
    def setUp(self):
        fd, self.path = tempfile.mkstemp(suffix=".db")
        os.close(fd)
        self.app = create_app({"DATABASE": self.path, "TESTING": True, "SECRET_KEY": "test"})
        self.client = self.app.test_client()

    def tearDown(self):
        try:
            os.remove(self.path)
        except PermissionError:
            pass

    # helpers
    def register(self, role, email=None, name="Tester"):
        email = email or f"{role}@test.com"
        res = self.client.post("/api/auth/register", json=dict(
            name=name, email=email, password="Passw0rd1", role=role))
        self.assertEqual(res.status_code, 201, res.get_json())
        return {"Authorization": "Bearer " + res.get_json()["token"]}

    def make_admin(self):
        with self.app.app_context():
            db = get_db()
            repo.create_user(db, "Admin", "admin@test.com", generate_password_hash("Passw0rd1"), "admin")
            db.commit()
        res = self.client.post("/api/auth/login", json=dict(email="admin@test.com", password="Passw0rd1"))
        return {"Authorization": "Bearer " + res.get_json()["token"]}


class AuthApiTests(ApiTestCase):
    def test_register_then_login_returns_token(self):          # TC-03
        self.register("hospital")
        res = self.client.post("/api/auth/login", json=dict(email="hospital@test.com", password="Passw0rd1"))
        self.assertEqual(res.status_code, 200)
        self.assertIn("token", res.get_json())

    def test_wrong_password_is_401(self):
        self.register("donor")
        res = self.client.post("/api/auth/login", json=dict(email="donor@test.com", password="nope12345"))
        self.assertEqual(res.status_code, 401)

    def test_duplicate_email_is_409(self):
        self.register("donor")
        res = self.client.post("/api/auth/register", json=dict(
            name="B", email="donor@test.com", password="Passw0rd1", role="donor"))
        self.assertEqual(res.status_code, 409)

    def test_weak_password_is_400(self):
        res = self.client.post("/api/auth/register", json=dict(
            name="B", email="b@test.com", password="abc", role="donor"))
        self.assertEqual(res.status_code, 400)
        self.assertIn("password", res.get_json()["errors"])

    def test_protected_route_requires_token(self):
        self.assertEqual(self.client.get("/api/stats").status_code, 401)
        res = self.client.get("/api/stats", headers={"Authorization": "Bearer junk"})
        self.assertEqual(res.status_code, 401)


class AccessControlTests(ApiTestCase):
    def test_donor_cannot_create_request(self):
        res = self.client.post("/api/requests", json=BLOOD_REQ, headers=self.register("donor"))
        self.assertEqual(res.status_code, 403)

    def test_hospital_cannot_see_audit_log(self):
        res = self.client.get("/api/audit", headers=self.register("hospital"))
        self.assertEqual(res.status_code, 403)

    def test_hospital_cannot_open_another_hospitals_request(self):
        owner = self.register("hospital", "h1@test.com")
        other = self.register("hospital", "h2@test.com")
        rid = self.client.post("/api/requests", json=BLOOD_REQ, headers=owner).get_json()["request"]["id"]
        self.assertEqual(self.client.get(f"/api/requests/{rid}", headers=other).status_code, 403)


class RequestApiTests(ApiTestCase):
    def test_create_request_missing_fields_is_400(self):       # TC-05
        res = self.client.post("/api/requests", json={"kind": "blood"}, headers=self.register("hospital"))
        self.assertEqual(res.status_code, 400)
        self.assertIn("patient_ref", res.get_json()["errors"])

    def test_list_requests_is_sorted_by_priority(self):        # TC-04
        h = self.register("hospital")
        for ref, urgency in (("PT-A", 2), ("PT-B", 5), ("PT-C", 3)):
            self.client.post("/api/requests", json={**BLOOD_REQ, "patient_ref": ref, "urgency": urgency}, headers=h)
        rows = self.client.get("/api/requests", headers=h).get_json()["requests"]
        self.assertEqual([r["patient_ref"] for r in rows], ["PT-B", "PT-C", "PT-A"])

    def test_unknown_request_is_404(self):
        self.assertEqual(self.client.get("/api/requests/999", headers=self.register("hospital")).status_code, 404)


class EndToEndTests(ApiTestCase):
    def test_full_matching_lifecycle(self):
        donor_h, hosp_h, admin_h = self.register("donor"), self.register("hospital"), self.make_admin()
        self.assertEqual(self.client.put("/api/donors/me", json=PROFILE, headers=donor_h).status_code, 200)

        rid = self.client.post("/api/requests", json=BLOOD_REQ, headers=hosp_h).get_json()["request"]["id"]
        run = self.client.post(f"/api/requests/{rid}/match", headers=hosp_h).get_json()
        self.assertEqual(run["proposals_created"], 1)
        match = run["matches"][0]
        self.assertIsNone(match["name"], "donor identity must stay hidden before acceptance")
        self.assertGreater(match["score"], 50)

        offers = self.client.get("/api/donors/me/offers", headers=donor_h).get_json()["offers"]
        self.assertEqual(len(offers), 1)
        self.assertNotIn("patient_ref", offers[0])
        res = self.client.post(f"/api/matches/{match['id']}/respond", json={"decision": "accept"}, headers=donor_h)
        self.assertEqual(res.get_json()["match"]["status"], "accepted")

        listed = self.client.get(f"/api/requests/{rid}/matches", headers=hosp_h).get_json()["matches"]
        self.assertEqual(listed[0]["name"], "Tester")
        done = self.client.post(f"/api/matches/{match['id']}/fulfil", headers=hosp_h).get_json()
        self.assertTrue(done["request_done"])

        profile = self.client.get("/api/donors/me", headers=donor_h).get_json()["donor"]
        self.assertEqual(profile["last_donation_date"], date.today().isoformat())
        again = self.client.post(f"/api/requests/{rid}/match", headers=hosp_h)
        self.assertEqual(again.status_code, 409)
        stats = self.client.get("/api/stats", headers=hosp_h).get_json()["stats"]
        self.assertEqual(stats["lives_touched"], 1)

        verify = self.client.get("/api/audit/verify", headers=admin_h).get_json()
        self.assertTrue(verify["valid"])
        self.assertGreaterEqual(verify["entries"], 7)

    def test_recently_donated_donor_not_matched(self):
        donor_h, hosp_h = self.register("donor"), self.register("hospital")
        recent = {**PROFILE, "last_donation_date": date.today().isoformat()}
        self.client.put("/api/donors/me", json=recent, headers=donor_h)
        rid = self.client.post("/api/requests", json=BLOOD_REQ, headers=hosp_h).get_json()["request"]["id"]
        run = self.client.post(f"/api/requests/{rid}/match", headers=hosp_h).get_json()
        self.assertEqual(run["candidates"], 0)

    def test_declined_donor_is_not_proposed_again(self):
        donor_h, hosp_h = self.register("donor"), self.register("hospital")
        self.client.put("/api/donors/me", json=PROFILE, headers=donor_h)
        rid = self.client.post("/api/requests", json=BLOOD_REQ, headers=hosp_h).get_json()["request"]["id"]
        mid = self.client.post(f"/api/requests/{rid}/match", headers=hosp_h).get_json()["matches"][0]["id"]
        self.client.post(f"/api/matches/{mid}/respond", json={"decision": "decline"}, headers=donor_h)
        rerun = self.client.post(f"/api/requests/{rid}/match", headers=hosp_h).get_json()
        self.assertEqual(rerun["proposals_created"], 0)

    def test_organ_request_respects_viability(self):
        donor_h, hosp_h = self.register("donor"), self.register("hospital")
        self.client.put("/api/donors/me", json={**PROFILE, "organs_pledged": ["heart"]}, headers=donor_h)
        delhi = dict(patient_ref="PT-3001", kind="organ", organ="heart", blood_group="O+", urgency=5,
                     city="New Delhi", lat=28.6139, lng=77.2090)
        rid = self.client.post("/api/requests", json=delhi, headers=hosp_h).get_json()["request"]["id"]
        run = self.client.post(f"/api/requests/{rid}/match", headers=hosp_h).get_json()
        self.assertEqual(run["candidates"], 0)
        self.assertEqual(sum(run["rejected"].values()), 1)

    def test_double_response_is_conflict(self):
        donor_h, hosp_h = self.register("donor"), self.register("hospital")
        self.client.put("/api/donors/me", json=PROFILE, headers=donor_h)
        rid = self.client.post("/api/requests", json=BLOOD_REQ, headers=hosp_h).get_json()["request"]["id"]
        mid = self.client.post(f"/api/requests/{rid}/match", headers=hosp_h).get_json()["matches"][0]["id"]
        self.client.post(f"/api/matches/{mid}/respond", json={"decision": "accept"}, headers=donor_h)
        res = self.client.post(f"/api/matches/{mid}/respond", json={"decision": "decline"}, headers=donor_h)
        self.assertEqual(res.status_code, 409)


class AuditTrailTests(ApiTestCase):
    def test_tampering_is_detected(self):
        self.register("donor")
        self.register("hospital")
        admin = self.make_admin()
        self.assertTrue(self.client.get("/api/audit/verify", headers=admin).get_json()["valid"])
        with self.app.app_context():
            db = get_db()
            db.execute("UPDATE audit_log SET actor = 'user:999' WHERE id = 1")
            db.commit()
        result = self.client.get("/api/audit/verify", headers=admin).get_json()
        self.assertFalse(result["valid"])
        self.assertEqual(result["first_bad_entry"], 1)


class HealthTests(ApiTestCase):
    def test_health_and_security_headers(self):
        res = self.client.get("/api/health")
        self.assertEqual(res.status_code, 200)
        self.assertEqual(res.headers["X-Content-Type-Options"], "nosniff")

    def test_unknown_route_returns_json_404(self):
        res = self.client.get("/api/nothing")
        self.assertEqual(res.status_code, 404)
        self.assertEqual(res.get_json()["error"], "Not found")


if __name__ == "__main__":
    unittest.main()
