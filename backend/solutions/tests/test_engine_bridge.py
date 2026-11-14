"""
backend/solutions/tests/test_engine_bridge.py

Unit tests for EngineBridge service adapter and standardized data contracts.
"""

from django.test import SimpleTestCase
import asyncio
from unittest.mock import patch, MagicMock

from solutions.services.engine_bridge import EngineBridge, engine_bridge


class EngineBridgeDataContractTests(SimpleTestCase):

    def setUp(self):
        self.bridge = EngineBridge(host="127.0.0.1", port=9998, timeout_sec=1.0)
        self.valid_payload = {
            "board": ["Ah", "Kd", "2c"],
            "oop_range": {"AA": 1.0, "KK": 1.0, "AKs": 1.0},
            "ip_range": {"QQ": 1.0, "JJ": 1.0, "AQs": 1.0},
            "pot": 6.5,
            "effective_stack": 97.0,
            "rake_percent": 5.0,
            "rake_cap": 3.0,
            "max_bets_per_node": 1
        }

    def test_normalize_request_payload_valid(self):
        norm = self.bridge.normalize_request_payload(self.valid_payload)
        self.assertEqual(norm["board"], ["Ah", "Kd", "2c"])
        self.assertEqual(norm["pot"], 6.5)
        self.assertEqual(norm["effective_stack"], 97.0)
        self.assertEqual(norm["rake_percent"], 5.0)
        self.assertEqual(norm["rake_cap"], 3.0)
        self.assertEqual(norm["max_bets_per_node"], 1)
        self.assertIn("AA", norm["oop_range"])
        self.assertIn("QQ", norm["ip_range"])

    def test_normalize_request_payload_invalid_board(self):
        invalid_payload = {"board": ["Ah", "Kd"]}
        with self.assertRaises(ValueError):
            self.bridge.normalize_request_payload(invalid_payload)

    def test_bunching_weights_are_passed_through(self):
        payload = dict(self.valid_payload)
        payload["bunching_weights"] = [1.0] * 13
        norm = self.bridge.normalize_request_payload(payload)
        self.assertEqual(len(norm["bunching_weights"]), 13)

    def test_bunching_weights_are_derived_from_folded_positions(self):
        payload = dict(self.valid_payload)
        payload["folded_positions"] = ["UTG", "MP", "CO"]
        norm = self.bridge.normalize_request_payload(payload)
        self.assertEqual(len(norm["bunching_weights"]), 13)
        self.assertEqual(norm["num_folded_players"], 3)
        # Low cards are deader than aces when early positions fold.
        self.assertLess(norm["bunching_weights"][0], norm["bunching_weights"][12])

    def test_invalid_bunching_weights_are_rejected(self):
        payload = dict(self.valid_payload)
        payload["bunching_weights"] = [1.0, 2.0]
        with self.assertRaises(ValueError):
            self.bridge.normalize_request_payload(payload)

    def test_solve_fallback_when_daemon_unreachable(self):
        # Point to an unreachable port to test local fallback
        offline_bridge = EngineBridge(host="127.0.0.1", port=49151, timeout_sec=0.2)
        loop = asyncio.new_event_loop()
        try:
            res = loop.run_until_complete(offline_bridge.solve(self.valid_payload))
            self.assertIn("exploitability", res)
            self.assertIn("solve_time_ms", res)
            self.assertIn("strategy", res)
            self.assertIn("overall_frequencies", res)
            self.assertIn("optimal_sizing", res)
            self.assertIn("heuristic-preview", res["engine"])
            self.assertLess(res["solve_time_ms"], 2000)
            self.assertIn("AA", res["strategy"])
            self.assertEqual(set(res["strategy"]["AA"].keys()), {"fold", "call", "raise"})
        finally:
            loop.close()

    def test_solve_flop_wrapper(self):
        loop = asyncio.new_event_loop()
        try:
            res = loop.run_until_complete(
                self.bridge.solve_flop(
                    board=["Kh", "Qc", "Jd"],
                    oop_range={"AA": 1.0},
                    ip_range={"KK": 1.0},
                    pot=10.0,
                    effective_stack=90.0,
                    rake_percent=5.0,
                    rake_cap=3.0,
                    max_bets_per_node=1
                )
            )
            self.assertIn("strategy", res)
            self.assertIn("optimal_sizing", res)
            self.assertLess(res["solve_time_ms"], 2000)
        finally:
            loop.close()

    def test_action_sequence_and_formation_ranges(self):
        from solutions.services.range_service import PreflopRangeService

        norm = self.bridge.normalize_request_payload({
            **self.valid_payload,
            "action_sequence": ["Check", "Bet 33%", "Call"],
        })
        self.assertEqual(norm["action_sequence"], ["Check", "Bet 33%", "Call"])

        parsed = PreflopRangeService.parse_range_input("AA:1.0, KK:0.8, AKs, AQo:0.5")
        self.assertEqual(parsed["AA"], 1.0)
        self.assertEqual(parsed["KK"], 0.8)
        self.assertEqual(parsed["AKs"], 1.0)
        self.assertEqual(parsed["AQo"], 0.5)

        for spot in (
            "UTG_vs_BB_SRP", "MP_vs_BB_SRP", "CO_vs_BB_SRP", "BTN_vs_BB_SRP", "SB_vs_BB_SRP",
            "BTN_vs_SB_3BET", "BTN_vs_BB_3BET", "CO_vs_BTN_3BET", "SB_vs_BB_3BET",
            "BTN_vs_BB_4BET", "CO_vs_BTN_4BET",
        ):
            oop_r, ip_r = PreflopRangeService.get_spot_ranges(spot, rake_percent=5.0, rake_cap=0.6)
            meta = PreflopRangeService.get_spot_metadata(spot)
            self.assertGreater(len(oop_r), 0, spot)
            self.assertGreater(len(ip_r), 0, spot)
            self.assertEqual(len(meta["folded_positions"]), 4, spot)
