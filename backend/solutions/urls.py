from django.urls import path, include
from rest_framework.routers import DefaultRouter
from .views import SolutionViewSet, StrategyNodeViewSet, StrategyLockViewSet, AggregateReportView, EquityDistributionView, StudySessionViewSet

router = DefaultRouter()
router.register(r'solutions', SolutionViewSet)
router.register(r'nodes', StrategyNodeViewSet)
router.register(r'locks', StrategyLockViewSet, basename='locks')
router.register(r'sessions', StudySessionViewSet, basename='sessions')

urlpatterns = [
    path('', include(router.urls)),
    path('reports/aggregate/', AggregateReportView.as_view(), name='aggregate-report'),
    path('solutions/<int:pk>/equity/', EquityDistributionView.as_view(), name='solution-equity'),
]
