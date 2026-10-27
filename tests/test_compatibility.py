import unittest

from backend.services.compatibility import (BLOOD_GROUPS, can_donate_blood, can_donate_organ,
                                            check_group)


class BloodCompatibilityTests(unittest.TestCase):
    def test_o_negative_is_universal_donor(self):
        for recipient in BLOOD_GROUPS:
            self.assertTrue(can_donate_blood("O-", recipient))

    def test_ab_positive_is_universal_recipient(self):
        for donor in BLOOD_GROUPS:
            self.assertTrue(can_donate_blood(donor, "AB+"))

    def test_rh_positive_cannot_give_to_rh_negative(self):
        self.assertFalse(can_donate_blood("A+", "A-"))
        self.assertFalse(can_donate_blood("O+", "O-"))

    def test_a_cannot_give_to_b(self):
        self.assertFalse(can_donate_blood("A+", "B+"))
        self.assertFalse(can_donate_blood("B-", "A-"))

    def test_unknown_group_rejected(self):
        with self.assertRaises(ValueError):
            check_group("C+")


class OrganCompatibilityTests(unittest.TestCase):
    def test_rh_is_ignored_for_organs(self):
        self.assertTrue(can_donate_organ("O+", "A-"))

    def test_abo_mismatch_blocked(self):
        self.assertFalse(can_donate_organ("A+", "O+"))
        self.assertFalse(can_donate_organ("AB-", "B+"))

    def test_identical_abo_allowed(self):
        self.assertTrue(can_donate_organ("B-", "B+"))


if __name__ == "__main__":
    unittest.main()
