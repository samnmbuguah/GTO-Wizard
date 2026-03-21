import asyncio
from django.urls import reverse
from rest_framework import status
from rest_framework.test import APITestCase
from unittest.mock import patch
from solutions.models import Solution, StrategyNode, SolverConfig
from solutions.solver import SolverService, rta_solver_queue
from django.contrib.auth.models import User

class SolverServiceTests(APITestCase):
    def setUp(self):
        self.config = SolverConfig.objects.create(name="Standard")
        self.solution = Solution.objects.create(
            name="Test Solution",
            solver_config=self.config,
            stack_depth=100,
            flop_texture="High"
        )

    @patch('solutions.solver.StrategyNode.objects.filter')
    def test_solver_service_logic(self, mock_filter):
        # Mock the DB response to avoid locks in SQLite
        mock_node = StrategyNode(id=1, path="root", ev=10.0, actions={"Bet": 1.0}, hand="AA")
        mock_filter.return_value = [mock_node]
        
        solution_id = self.solution.id
        path = "root"
        texture = "High"
        sizes = [0.33, 0.75]
        
        result = asyncio.run(SolverService.simulate_dynamic_sizing(solution_id, path, texture, sizes))
        
        self.assertIn("optimal_size", result)
        self.assertEqual(len(result["ev_distribution"]), 2)
        self.assertLess(result["calc_time_ms"], 2000)
        self.assertEqual(result["mode"], "Depth-Limited (Fast)")

    def test_solver_queue_concurrency(self):
        queue = rta_solver_queue
        
        async def mock_task():
            await asyncio.sleep(0.01)
            return True
        
        async def run_concurrent():
            tasks = [queue.add_task(mock_task()) for _ in range(5)]
            return await asyncio.gather(*tasks)
            
        results = asyncio.run(run_concurrent())
        self.assertTrue(all(results))

class RTASolverAPITests(APITestCase):
    def setUp(self):
        self.user = User.objects.create_user(username='solveruser', password='password')
        self.config = SolverConfig.objects.create(name="Standard")
        self.solution = Solution.objects.create(
            name="Test Solution",
            solver_config=self.config,
            stack_depth=100,
            flop_texture="High"
        )
        self.client.force_authenticate(user=self.user)

    @patch('solutions.solver.SolverService.simulate_dynamic_sizing')
    def test_dynamic_sizing_endpoint(self, mock_solve):
        mock_solve.return_value = {"optimal_size": 0.75, "calc_time_ms": 500}
        
        url = reverse('solution-dynamic-sizing')
        data = {
            "solution_id": self.solution.id,
            "path": "root",
            "board_texture": "High",
            "sizes": [0.33, 0.75]
        }
        
        response = self.client.post(url, data, format='json')
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(response.data['optimal_size'], 0.75)
