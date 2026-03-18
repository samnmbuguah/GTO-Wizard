from django.urls import path, include
from rest_framework.routers import DefaultRouter
from .views import SolutionViewSet, StrategyNodeViewSet

router = DefaultRouter()
router.register(r'solutions', SolutionViewSet)
router.register(r'nodes', StrategyNodeViewSet)

urlpatterns = [
    path('', include(router.urls)),
]
