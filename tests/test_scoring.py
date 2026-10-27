import unittest
from datetime import date, datetime

from backend.services.geo import haversine_km, transport_hours
from backend.services.scoring import (evaluate_blood, evaluate_organ, hla_matches, rank_donors,
                                      request_priority)

TODAY = date(2026, 10, 27)
BLR = (12.9716, 77.5946)
MYS = (12.2958, 76.6394)
DEL = (28.6139, 77.2090)


def donor(**kw):
    base = dict(id=1, blood_group="O+", age=30, weight_kg=70, donor_type="both",
                organs_pledged=["kidney", "liver", "heart"], hla="A2,A24,B7,B8,DR3,DR4",
                lat=BLR[0], lng=BLR[1], last_donation_date=None, available=True)
    base.update(kw)
    return base


def blood_req(**kw):
    base = dict(kind="blood", blood_group="A+", urgency=3, lat=BLR[0], lng=BLR[1])
    base.update(kw)
    return base


def organ_req(**kw):
    base = dict(kind="organ", organ="kidney", blood_group="O+", urgency=4, patient_age=35,
                hla="A2,A24,B7,B8,DR3,DR4", lat=BLR[0], lng=BLR[1])
    base.update(kw)
    return base


class GeoTests(unittest.TestCase):
    def test_bengaluru_to_mysuru_distance(self):
        self.assertAlmostEqual(haversine_km(*BLR, *MYS), 126, delta=6)

    def test_same_point_is_zero(self):
        self.assertEqual(haversine_km(*BLR, *BLR), 0)

    def test_transport_includes_retrieval_buffer(self):
        self.assertAlmostEqual(transport_hours(0), 1.0)
        self.assertAlmostEqual(transport_hours(100), 3.0)


class BloodScoringTests(unittest.TestCase):
    def test_exact_group_scores_above_compatible(self):
        exact = evaluate_blood(blood_req(), donor(blood_group="A+"), TODAY)
        compat = evaluate_blood(blood_req(), donor(blood_group="O-"), TODAY)
        self.assertGreater(exact["score"], compat["score"])

    def test_recent_donor_is_rejected(self):
        result = evaluate_blood(blood_req(), donor(last_donation_date="2026-09-15"), TODAY)
        self.assertFalse(result["eligible"])
        self.assertIn("Donated", result["reasons"][0])

    def test_donor_after_90_days_is_accepted(self):
        result = evaluate_blood(blood_req(), donor(last_donation_date="2026-07-01"), TODAY)
        self.assertTrue(result["eligible"])

    def test_underweight_and_underage_rejected(self):
        self.assertFalse(evaluate_blood(blood_req(), donor(weight_kg=40), TODAY)["eligible"])
        self.assertFalse(evaluate_blood(blood_req(), donor(age=17), TODAY)["eligible"])

    def test_far_donor_rejected(self):
        far = donor(lat=DEL[0], lng=DEL[1])
        self.assertFalse(evaluate_blood(blood_req(), far, TODAY)["eligible"])

    def test_urgency_penalises_distance_harder(self):
        near, far = donor(), donor(lat=MYS[0], lng=MYS[1])
        gap_low = (evaluate_blood(blood_req(urgency=1), near, TODAY)["score"]
                   - evaluate_blood(blood_req(urgency=1), far, TODAY)["score"])
        gap_high = (evaluate_blood(blood_req(urgency=5), near, TODAY)["score"]
                    - evaluate_blood(blood_req(urgency=5), far, TODAY)["score"])
        self.assertGreater(gap_high, gap_low)

    def test_breakdown_adds_up_to_score(self):
        result = evaluate_blood(blood_req(), donor(), TODAY)
        self.assertAlmostEqual(sum(b["points"] for b in result["breakdown"]), result["score"], delta=0.3)


class OrganScoringTests(unittest.TestCase):
    def test_hla_match_counting(self):
        self.assertEqual(hla_matches("A2,B7,DR3", "a2, b7 ,DR4"), 2)
        self.assertEqual(hla_matches("", "A2"), 0)

    def test_better_hla_scores_higher(self):
        full = evaluate_organ(organ_req(), donor())
        none = evaluate_organ(organ_req(), donor(hla="A1,B5,DR1,A3,B9,DR2"))
        self.assertGreater(full["score"], none["score"])

    def test_heart_too_far_is_not_viable(self):
        far = donor(lat=DEL[0], lng=DEL[1])
        result = evaluate_organ(organ_req(organ="heart"), far)
        self.assertFalse(result["eligible"])
        self.assertIn("viability", result["reasons"][0])

    def test_kidney_survives_long_transport(self):
        far = donor(lat=DEL[0], lng=DEL[1])
        self.assertTrue(evaluate_organ(organ_req(organ="kidney"), far)["eligible"])

    def test_unpledged_organ_rejected(self):
        result = evaluate_organ(organ_req(organ="lung"), donor())
        self.assertFalse(result["eligible"])

    def test_abo_incompatible_rejected(self):
        result = evaluate_organ(organ_req(blood_group="O+"), donor(blood_group="A+"))
        self.assertFalse(result["eligible"])


class RankingTests(unittest.TestCase):
    def test_ranking_is_sorted_and_counts_rejections(self):
        pool = [donor(id=1), donor(id=2, lat=MYS[0], lng=MYS[1]), donor(id=3, available=False),
                donor(id=4, blood_group="B+")]
        ranked, rejected = rank_donors(blood_req(blood_group="O+"), pool, today=TODAY)
        self.assertEqual([r["donor"]["id"] for r in ranked], [1, 2])
        self.assertEqual(rejected["Donor marked unavailable"], 1)
        self.assertEqual(rejected["Blood group incompatible"], 1)

    def test_limit_applies(self):
        pool = [donor(id=i) for i in range(1, 8)]
        ranked, _ = rank_donors(blood_req(blood_group="O+"), pool, limit=3, today=TODAY)
        self.assertEqual(len(ranked), 3)


class PriorityTests(unittest.TestCase):
    def test_urgency_dominates_waiting_time(self):
        now = datetime(2026, 10, 27)
        urgent_new = request_priority(5, "2026-10-27T00:00:00", now)
        mild_old = request_priority(3, "2026-08-01T00:00:00", now)
        self.assertGreater(urgent_new, mild_old)

    def test_waiting_time_is_capped(self):
        now = datetime(2026, 10, 27)
        self.assertEqual(request_priority(1, "2020-01-01T00:00:00", now), 20 + 30)


if __name__ == "__main__":
    unittest.main()
