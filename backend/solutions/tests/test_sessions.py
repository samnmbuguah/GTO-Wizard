from django.urls import reverse
from rest_framework import status
from rest_framework.test import APITestCase
from django.contrib.auth.models import User
from solutions.models import Solution, StudySession

class StudySessionTests(APITestCase):
    def setUp(self):
        self.user = User.objects.create_user(username='player', password='password123')
        self.client.login(username='player', password='password123')
        self.solution = Solution.objects.create(name="Trainer Spot", rake=0.05, stack_depth=100)

    def test_create_session(self):
        url = reverse('sessions-list')
        data = {
            "solution": self.solution.id,
            "correct_hands": 0,
            "total_hands": 0,
            "streak": 0
        }
        response = self.client.post(url, data, format='json')
        self.assertEqual(response.status_code, status.HTTP_201_CREATED)
        self.assertEqual(StudySession.objects.count(), 1)

    def test_update_score(self):
        session = StudySession.objects.create(
            user=self.user, 
            solution=self.solution,
            correct_hands=5,
            total_hands=10,
            streak=2
        )
        url = reverse('sessions-detail', args=[session.id])
        data = {"correct_hands": 6, "total_hands": 11, "streak": 3}
        response = self.client.patch(url, data, format='json')
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        session.refresh_from_db()
        self.assertEqual(session.correct_hands, 6)
        self.assertEqual(session.streak, 3)
