import unittest
from datetime import date

from backend.services.auth import AuthError, issue_token, verify_token
from backend.services.validators import (ValidationError, is_strong_password, is_valid_email,
                                         validate_donor_profile, validate_register,
                                         validate_request)

GOOD_PROFILE = dict(blood_group="O+", age=28, weight_kg=64, donor_type="blood", city="Bengaluru",
                    lat=12.97, lng=77.59)
GOOD_REQUEST = dict(patient_ref="PT-1001", kind="blood", blood_group="A+", urgency=4,
                    units_needed=2, city="Bengaluru", lat=12.97, lng=77.59)


class FieldValidationTests(unittest.TestCase):
    def test_invalid_email_formats(self):
        for bad in ("plainaddress", "a@b", "@x.com", "a b@x.com", None, 42):
            self.assertFalse(is_valid_email(bad), bad)

    def test_valid_email(self):
        self.assertTrue(is_valid_email("nurse@city-hospital.org"))

    def test_password_strength(self):
        self.assertFalse(is_strong_password("short1"))
        self.assertFalse(is_strong_password("onlyletters"))
        self.assertFalse(is_strong_password("12345678"))
        self.assertTrue(is_strong_password("Strong123"))

    def test_register_rejects_admin_role(self):
        with self.assertRaises(ValidationError) as ctx:
            validate_register(dict(name="X", email="x@y.com", password="Passw0rd!", role="admin"))
        self.assertIn("role", ctx.exception.errors)

    def test_register_normalises_email(self):
        clean = validate_register(dict(name=" Ana ", email="ANA@Mail.com", password="Passw0rd!", role="donor"))
        self.assertEqual((clean["name"], clean["email"]), ("Ana", "ana@mail.com"))


class ProfileValidationTests(unittest.TestCase):
    def test_valid_profile(self):
        clean = validate_donor_profile(GOOD_PROFILE, today=date(2026, 10, 27))
        self.assertEqual(clean["blood_group"], "O+")

    def test_bad_group_and_age(self):
        with self.assertRaises(ValidationError) as ctx:
            validate_donor_profile({**GOOD_PROFILE, "blood_group": "Z+", "age": 12})
        self.assertEqual(set(ctx.exception.errors), {"blood_group", "age"})

    def test_organ_donor_must_pick_organs(self):
        with self.assertRaises(ValidationError) as ctx:
            validate_donor_profile({**GOOD_PROFILE, "donor_type": "organ"})
        self.assertIn("organs_pledged", ctx.exception.errors)

    def test_future_donation_date_rejected(self):
        with self.assertRaises(ValidationError):
            validate_donor_profile({**GOOD_PROFILE, "last_donation_date": "2030-01-01"},
                                   today=date(2026, 10, 27))


class RequestValidationTests(unittest.TestCase):
    def test_valid_blood_request(self):
        self.assertEqual(validate_request(GOOD_REQUEST)["units_needed"], 2)

    def test_missing_fields_reported(self):
        with self.assertRaises(ValidationError) as ctx:
            validate_request({"kind": "blood"})
        for field in ("patient_ref", "blood_group", "urgency", "city", "lat", "lng"):
            self.assertIn(field, ctx.exception.errors)

    def test_urgency_out_of_range(self):
        with self.assertRaises(ValidationError):
            validate_request({**GOOD_REQUEST, "urgency": 9})

    def test_organ_request_requires_known_organ(self):
        with self.assertRaises(ValidationError) as ctx:
            validate_request({**GOOD_REQUEST, "kind": "organ", "organ": "spleen"})
        self.assertIn("organ", ctx.exception.errors)


class TokenTests(unittest.TestCase):
    def test_round_trip(self):
        token = issue_token(7, "donor", "k", 60, now=1000)
        self.assertEqual(verify_token(token, "k", now=1010)["uid"], 7)

    def test_expired_token(self):
        token = issue_token(7, "donor", "k", 60, now=1000)
        with self.assertRaises(AuthError):
            verify_token(token, "k", now=2000)

    def test_tampered_token(self):
        token = issue_token(7, "donor", "k", 60, now=1000)
        with self.assertRaises(AuthError):
            verify_token(token[:-2] + "xx", "k", now=1010)

    def test_wrong_secret(self):
        token = issue_token(7, "donor", "k", 60, now=1000)
        with self.assertRaises(AuthError):
            verify_token(token, "other", now=1010)


if __name__ == "__main__":
    unittest.main()
