from rest_framework import viewsets, permissions
from .models import Solution, StrategyNode
from .serializers import SolutionSerializer, StrategyNodeSerializer

class SolutionViewSet(viewsets.ModelViewSet):
    queryset = Solution.objects.all()
    serializer_class = SolutionSerializer
    permission_classes = [permissions.IsAuthenticatedOrReadOnly]

class StrategyNodeViewSet(viewsets.ModelViewSet):
    queryset = StrategyNode.objects.all()
    serializer_class = StrategyNodeSerializer
    permission_classes = [permissions.IsAuthenticatedOrReadOnly]

    def get_queryset(self):
        queryset = StrategyNode.objects.all()
        solution_id = self.request.query_params.get('solution_id')
        path = self.request.query_params.get('path')
        if solution_id:
            queryset = queryset.filter(solution_id=solution_id)
        if path:
            queryset = queryset.filter(path=path)
        return queryset
