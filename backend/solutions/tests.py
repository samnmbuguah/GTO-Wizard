from django.urls import reverse
from rest_framework import status
from rest_framework.test import APITestCase
from .models import Solution, StrategyNode

class SolutionTests(APITestCase):
    def setUp(self):
        self.solution = Solution.objects.create(name="Test Solution", rake=0.05, stack_depth=100)
        self.node = StrategyNode.objects.create(
            solution=self.solution,
            path="root",
            hand="AA",
            actions={"raise": 1.0}
        )

    def test_get_solutions(self):
        url = reverse('solution-list')
        response = self.client.get(url)
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(len(response.data), 1)

    def test_get_nodes(self):
        url = reverse('strategynode-list')
        response = self.client.get(url, {'solution_id': self.solution.id, 'path': 'root'})
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        # DRF DefaultRouter uses 'strategynode-list' for views registered as 'nodes'
        # Let's verify the URL name
