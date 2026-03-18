from django.urls import reverse
from rest_framework import status
from rest_framework.test import APITestCase
from django.contrib.auth.models import User
from solutions.models import Solution, StrategyNode

class SolutionAPITests(APITestCase):
    def setUp(self):
        self.user = User.objects.create_superuser(username='admin', email='a@b.com', password='password123')
        self.client.login(username='admin', password='password123')
        
        self.sol1 = Solution.objects.create(name="Sol 5% Rake", rake=0.05, stack_depth=100)
        self.sol2 = Solution.objects.create(name="Sol 0% Rake", rake=0.0, stack_depth=40)

    def test_get_solutions_list(self):
        url = reverse('solution-list')
        response = self.client.get(url)
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(len(response.data), 2)

    def test_filter_by_rake(self):
        url = reverse('solution-list')
        response = self.client.get(url, {'rake': 0.05})
        self.assertEqual(len(response.data), 1)
        self.assertEqual(response.data[0]['name'], "Sol 5% Rake")

    def test_filter_by_stack_depth(self):
        url = reverse('solution-list')
        response = self.client.get(url, {'stack_depth': 40})
        self.assertEqual(len(response.data), 1)
        self.assertEqual(response.data[0]['name'], "Sol 0% Rake")
