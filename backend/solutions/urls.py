from django.urls import path, include
from rest_framework.routers import DefaultRouter
from .views import (
    SolverConfigViewSet, SolutionViewSet, StrategyNodeViewSet, 
    StrategyLockViewSet, AggregateReportView, EquityDistributionView, 
    StudySessionViewSet, DynamicSizingView
)

router = DefaultRouter()
router.register(r'solver-configs', SolverConfigViewSet)
router.register(r'solutions', SolutionViewSet)
router.register(r'nodes', StrategyNodeViewSet)
router.register(r'locks', StrategyLockViewSet, basename='locks')
router.register(r'sessions', StudySessionViewSet, basename='sessions')

urlpatterns = [
    path('reports/aggregate/', AggregateReportView.as_view(), name='aggregate-report'),
    path('solutions/<int:pk>/equity/', EquityDistributionView.as_view(), name='solution-equity'),
    path('solutions/dynamic-sizing/', DynamicSizingView.as_view(), name='solution-dynamic-sizing'),
    path('', include(router.urls)),
]
