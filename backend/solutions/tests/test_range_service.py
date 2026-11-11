"""
backend/solutions/tests/test_range_service.py

Unit tests for PreflopRangeService dynamic rake and stack depth morphing.
"""

from django.test import SimpleTestCase
from solutions.services.range_service import PreflopRangeService


class PreflopRangeServiceTests(SimpleTestCase):

    def test_get_morphed_preflop_range_structure(self):
        oop_range, ip_range = PreflopRangeService.get_morphed_preflop_range(
            position_oop="BB",
            position_ip="BTN",
            stack_bb=100.0,
            rake_pct=5.0,
            rake_cap=3.0
        )
        self.assertIsInstance(oop_range, dict)
        self.assertIsInstance(ip_range, dict)
        self.assertIn("AA", oop_range)
        self.assertIn("AA", ip_range)
        self.assertEqual(oop_range["AA"], 1.0)
        self.assertEqual(ip_range["AA"], 1.0)

    def test_rake_elasticity_tightens_marginal_defense(self):
        # Compare 0% rake vs 5% rake vs 10% rake for BB defense vs BTN
        oop_0, _ = PreflopRangeService.get_morphed_preflop_range(
            position_oop="BB", position_ip="BTN", stack_bb=100.0, rake_pct=0.0, rake_cap=0.0
        )
        oop_5, _ = PreflopRangeService.get_morphed_preflop_range(
            position_oop="BB", position_ip="BTN", stack_bb=100.0, rake_pct=5.0, rake_cap=3.0
        )
        oop_10, _ = PreflopRangeService.get_morphed_preflop_range(
            position_oop="BB", position_ip="BTN", stack_bb=100.0, rake_pct=10.0, rake_cap=5.0
        )

        # Marginal offsuit / flatting hand should be strictly looser at 0% rake than 10% rake
        marginal_hands = ["T8o", "98o", "87o", "Q9o", "K8o"]
        for hand in marginal_hands:
            w0 = oop_0.get(hand, 0.0)
            w5 = oop_5.get(hand, 0.0)
            w10 = oop_10.get(hand, 0.0)
            self.assertGreaterEqual(w0, w5, f"{hand} at 0% rake should be >= 5% rake")
            self.assertGreaterEqual(w5, w10, f"{hand} at 5% rake should be >= 10% rake")

    def test_stack_depth_scaling(self):
        # 150bb vs 40bb
        _, ip_150 = PreflopRangeService.get_morphed_preflop_range(
            position_oop="BB", position_ip="BTN", stack_bb=150.0, rake_pct=5.0, rake_cap=3.0
        )
        _, ip_40 = PreflopRangeService.get_morphed_preflop_range(
            position_oop="BB", position_ip="BTN", stack_bb=40.0, rake_pct=5.0, rake_cap=3.0
        )

        # Speculative suited connectors like 76s, 65s, 54s should have higher playability at 150bb than 40bb
        for hand in ["76s", "65s", "54s"]:
            self.assertGreaterEqual(ip_150.get(hand, 0.0), ip_40.get(hand, 0.0))

    def test_backward_compatibility(self):
        oop, ip = PreflopRangeService.get_spot_ranges("BTN_vs_BB_SRP", rake_percent=5.0, rake_cap=3.0)
        self.assertIn("AA", oop)
        self.assertIn("AA", ip)
        interpolated = PreflopRangeService.get_interpolated_range("BTN_OPEN", rake_percent=5.0, rake_cap=3.0)
        self.assertIn("AKs", interpolated)
