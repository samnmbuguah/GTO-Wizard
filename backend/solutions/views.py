from rest_framework import viewsets, permissions
from rest_framework.views import APIView
from rest_framework.response import Response
from django.db.models import Avg, Sum
from .models import Solution, StrategyNode, StrategyLock
from .serializers import SolutionSerializer, StrategyNodeSerializer, StrategyLockSerializer

class AggregateReportView(APIView):
    def get(self, request):
        textures = [t[0] for t in Solution._meta.get_field('flop_texture').choices]
        report = []
        
        for texture in textures:
            solutions = Solution.objects.filter(flop_texture=texture)
            if not solutions.exists():
                continue
            
            # Get root nodes for these solutions
            root_nodes = StrategyNode.objects.filter(solution__in=solutions, path='root')
            
            total_fold = 0
            total_call = 0
            total_raise = 0
            count = root_nodes.count()
            
            if count > 0:
                for node in root_nodes:
                    strat = node.actions or {}
                    total_fold += strat.get('Fold', strat.get('fold', 0))
                    total_call += strat.get('Call', strat.get('call', 0))
                    total_raise += strat.get('Raise', strat.get('raise', 0))
                
                report.append({
                    'texture': texture,
                    'avg_fold': total_fold / count,
                    'avg_call': total_call / count,
                    'avg_raise': total_raise / count,
                    'sample_size': count
                })
        
        return Response(report)

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
