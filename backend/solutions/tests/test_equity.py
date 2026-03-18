from django.urls import reverse
from rest_framework import status
from rest_framework.test import APITestCase
from solutions.models import Solution

class EquityDistributionTests(APITestCase):
    def setUp(self):
        from django.contrib.auth.models import User
        self.user = User.objects.create_superuser(username='admin', email='a@b.com', password='password123')
        self.client.login(username='admin', password='password123')
        self.solution = Solution.objects.create(name="Equity Test", rake=0.05, stack_depth=100)

    def test_get_equity_distribution(self):
        url = reverse('solution-equity', args=[self.solution.id])
        response = self.client.get(url)
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        # Verify structure: should be a list of bins
        self.assertIsInstance(response.data, list)
        self.assertEqual(len(response.data), 10) # 10 bins (0-10% to 90-100%)
        
        # Verify first bin data
        first_bin = response.data[0]
        self.assertIn('bin', first_bin)
        self.assertIn('hero', first_bin)
        self.assertIn('villain', first_bin)
        self.assertEqual(first_bin['bin'], '0-10%')
