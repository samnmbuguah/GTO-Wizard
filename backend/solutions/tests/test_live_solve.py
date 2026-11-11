from django.test import TestCase
from rest_framework.test import APIClient
from rest_framework import status
from solutions.services.range_service import PreflopRangeService
from solutions.services.engine_client import engine_client
import asyncio

class LiveSolverTests(TestCase):
    def setUp(self):
        self.client = APIClient()

    def test_preflop_range_interpolation(self):
        # High rake should reduce offsuit connectivity and marginal calls
        low_rake = PreflopRangeService.get_interpolated_range("BB_DEFENSE", rake_percent=1.0, rake_cap=1.0)
        high_rake = PreflopRangeService.get_interpolated_range("BB_DEFENSE", rake_percent=9.0, rake_cap=5.0)

        # 98o should have lower frequency under higher rake
        if "98o" in low_rake and "98o" in high_rake:
            self.assertGreater(low_rake["98o"], high_rake["98o"])

        # AA and KK should remain 1.0
        self.assertEqual(low_rake.get("AA"), 1.0)
        self.assertEqual(high_rake.get("AA"), 1.0)

    def test_live_solve_endpoint(self):
        payload = {
            "board": ["Kh", "7d", "2c"],
            "spot": "BTN_vs_BB_SRP",
            "pot": 6.5,
            "effective_stack": 97.0,
            "rake_percent": 5.0,
            "rake_cap": 3.0
        }
        response = self.client.post('/api/solutions/live-solve/', payload, format='json')
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        data = response.json()
        self.assertIn("strategy", data)
        self.assertIn("solve_time_ms", data)
        self.assertIn("exploitability", data)
        self.assertIn("optimal_sizing", data)
        self.assertLess(data["solve_time_ms"], 2000)
