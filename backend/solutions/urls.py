from django.urls import path, include
from rest_framework.routers import DefaultRouter
from .views import SolutionViewSet, StrategyNodeViewSet, StrategyLockViewSet

router = DefaultRouter()
router.register(r'solutions', SolutionViewSet)
router.register(r'nodes', StrategyNodeViewSet)
router.register(r'locks', StrategyLockViewSet, basename='locks')

urlpatterns = [
    path('', include(router.urls)),
]
