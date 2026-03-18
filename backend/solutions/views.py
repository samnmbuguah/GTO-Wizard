from rest_framework import viewsets, permissions
from .models import Solution, StrategyNode, StrategyLock
from .serializers import SolutionSerializer, StrategyNodeSerializer, StrategyLockSerializer

class SolutionViewSet(viewsets.ModelViewSet):
    queryset = Solution.objects.all()
    serializer_class = SolutionSerializer
    permission_classes = [permissions.IsAuthenticatedOrReadOnly]

    def get_queryset(self):
        queryset = Solution.objects.all()
        rake = self.request.query_params.get('rake')
        stack_depth = self.request.query_params.get('stack_depth')
        if rake is not None:
            queryset = queryset.filter(rake=rake)
        if stack_depth is not None:
            queryset = queryset.filter(stack_depth=stack_depth)
        return queryset

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

class StrategyLockViewSet(viewsets.ModelViewSet):
    serializer_class = StrategyLockSerializer
    permission_classes = [permissions.IsAuthenticated]

    def get_queryset(self):
        return StrategyLock.objects.filter(user=self.request.user)

    def perform_create(self, serializer):
        serializer.save(user=self.request.user)
