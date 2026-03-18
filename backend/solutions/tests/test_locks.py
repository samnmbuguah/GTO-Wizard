from django.urls import reverse
from rest_framework import status
from rest_framework.test import APITestCase
from django.contrib.auth.models import User
from solutions.models import Solution, StrategyNode, StrategyLock

class StrategyLockTests(APITestCase):
    def setUp(self):
        self.user = User.objects.create_superuser(username='admin', email='a@b.com', password='password123')
        self.client.login(username='admin', password='password123')
        
        self.solution = Solution.objects.create(name="Test Spot", rake=0.05, stack_depth=100)
        self.node = StrategyNode.objects.create(
            solution=self.solution,
            path="root",
            hand="AA",
            actions={"fold": 0.0, "call": 0.0, "raise": 1.0}
        )

    def test_create_lock(self):
        url = reverse('locks-list')
        data = {
            "node": self.node.id,
            "user": self.user.id,
            "locked_actions": {"fold": 0.0, "call": 0.5, "raise": 0.5}
        }
        response = self.client.post(url, data, format='json')
        self.assertEqual(response.status_code, status.HTTP_201_CREATED)
        self.assertEqual(StrategyLock.objects.count(), 1)
        self.assertEqual(StrategyLock.objects.first().locked_actions["call"], 0.5)

    def test_delete_lock(self):
        lock = StrategyLock.objects.create(user=self.user, node=self.node, locked_actions={"fold": 1.0})
        url = reverse('locks-detail', args=[lock.id])
        response = self.client.delete(url)
        self.assertEqual(response.status_code, status.HTTP_204_NO_CONTENT)
        self.assertEqual(StrategyLock.objects.count(), 0)

    def test_get_locks_for_node(self):
        StrategyLock.objects.create(user=self.user, node=self.node, locked_actions={"fold": 1.0})
        url = reverse('locks-list')
        response = self.client.get(url, {'node_id': self.node.id})
        self.assertEqual(len(response.data), 1)
        self.assertEqual(response.data[0]['locked_actions']['fold'], 1.0)
