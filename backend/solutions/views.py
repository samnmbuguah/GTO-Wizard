from rest_framework import viewsets, permissions
from rest_framework.views import APIView
from rest_framework.response import Response
from django.db.models import Avg, Sum
from .models import SolverConfig, Solution, StrategyNode, StrategyLock, StudySession
from .serializers import SolverConfigSerializer, SolutionSerializer, StrategyNodeSerializer, StrategyLockSerializer, StudySessionSerializer
from .utils import process_sif_upload
from .solver import SolverService, rta_solver_queue
import asyncio
import json
from rest_framework.decorators import action
from rest_framework.parsers import MultiPartParser

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
        name = self.request.query_params.get('name')
        ante = self.request.query_params.get('ante')
        ante_gt = self.request.query_params.get('ante__gt')
        game_type = self.request.query_params.get('game_type')
        flop_texture = self.request.query_params.get('flop_texture')

        if rake is not None:
            queryset = queryset.filter(rake=rake)
        if stack_depth is not None:
            queryset = queryset.filter(stack_depth=stack_depth)
        if flop_texture is not None:
            queryset = queryset.filter(flop_texture=flop_texture)
        if name is not None:
            queryset = queryset.filter(name__icontains=name)
        if ante is not None:
            queryset = queryset.filter(ante=ante)
        if ante_gt is not None:
            queryset = queryset.filter(ante__gt=ante_gt)
        if game_type is not None:
            queryset = queryset.filter(game_type=game_type)
        return queryset

    @action(detail=False, methods=['post'], parser_classes=[MultiPartParser])
    def upload(self, request):
        file_obj = request.FILES.get('file')
        if not file_obj:
            return Response({"error": "No file uploaded"}, status=400)
        
        try:
            solution, node_count = process_sif_upload(file_obj)
            return Response({
                "message": "Successfully imported solution",
                "solution_id": solution.id,
                "node_count": node_count
            })
        except Exception as e:
            return Response({"error": str(e)}, status=400)

class SolverConfigViewSet(viewsets.ModelViewSet):
    queryset = SolverConfig.objects.all()
    serializer_class = SolverConfigSerializer
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

class StrategyLockViewSet(viewsets.ModelViewSet):
    serializer_class = StrategyLockSerializer
    permission_classes = [permissions.IsAuthenticated]

    def get_queryset(self):
        return StrategyLock.objects.filter(user=self.request.user)

    def perform_create(self, serializer):
        serializer.save(user=self.request.user)
class EquityDistributionView(APIView):
    def get(self, request, pk):
        try:
            solution = Solution.objects.get(pk=pk)
            texture = solution.flop_texture
            
            # Base distribution (Simulation)
            # In a real app, this would be computed by a solver engine or pre-calculated
            if texture in ['High', 'Paired']:
                # Hero (SB) has more range advantage
                hero_data = [2, 5, 8, 12, 18, 25, 35, 45, 60, 80]
                villain_data = [1, 3, 6, 10, 15, 20, 30, 40, 50, 65]
            elif texture in ['Low', 'Monotone']:
                # Villain (BB) has more advantage on dynamic/low boards
                hero_data = [1, 3, 5, 10, 15, 22, 30, 40, 55, 75]
                villain_data = [2, 6, 12, 18, 25, 35, 45, 60, 75, 90]
            else:
                hero_data = [2, 5, 10, 15, 20, 30, 40, 55, 70, 85]
                villain_data = [2, 5, 12, 18, 25, 35, 48, 62, 75, 88]
                
            labels = ["0-10%", "10-20%", "20-30%", "30-40%", "40-50%", "50-60%", "60-70%", "70-80%", "80-90%", "90-100%"]
            
            data = [
                {"bin": label, "hero": h, "villain": v}
                for label, h, v in zip(labels, hero_data, villain_data)
            ]
            
            return Response(data)
        except Solution.DoesNotExist:
            return Response({"error": "Solution not found"}, status=404)

class DynamicSizingView(APIView):
    permission_classes = [permissions.IsAuthenticated]

    def post(self, request):
        solution_id = request.data.get('solution_id')
        current_path = request.data.get('path', 'root')
        board_texture = request.data.get('board_texture', 'Rainbow')
        candidate_sizes = request.data.get('sizes', [0.33, 0.5, 0.75])

        if not solution_id:
            return Response({"error": "solution_id is required"}, status=400)

        # Run via the async queue to manage concurrency
        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)
        
        try:
            result = loop.run_until_complete(
                rta_solver_queue.add_task(
                    SolverService.simulate_dynamic_sizing(
                        solution_id, current_path, board_texture, candidate_sizes
                    )
                )
            )
            return Response(result)
        except Solution.DoesNotExist:
            return Response({"error": "Solution not found"}, status=404)
        except Exception as e:
            return Response({"error": str(e)}, status=400)
        finally:
            loop.close()

class StudySessionViewSet(viewsets.ModelViewSet):
    serializer_class = StudySessionSerializer
    permission_classes = [permissions.IsAuthenticated]

    def get_queryset(self):
        return StudySession.objects.filter(user=self.request.user)

    def perform_create(self, serializer):
        serializer.save(user=self.request.user)
