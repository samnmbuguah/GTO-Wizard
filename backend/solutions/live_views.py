"""
Live Solver View & API Endpoints.
Handles real-time depth-limited solves (<2s) with custom rake interpolation and dynamic sizing.
"""
import asyncio
import logging
from rest_framework.views import APIView
from rest_framework.response import Response
from rest_framework import permissions, status

from .services.engine_client import engine_client
from .services.range_service import PreflopRangeService

logger = logging.getLogger(__name__)

class LiveSolveView(APIView):
    """
    POST /api/solutions/live-solve/
    Accepts:
    {
        "board": ["Ah", "Kd", "2c"],
        "spot": "BTN_vs_BB_SRP",
        "pot": 6.5,
        "effective_stack": 97.0,
        "rake_percent": 5.0,
        "rake_cap": 3.0,
        "oop_range": {...},  # optional override
        "ip_range": {...}    # optional override
    }
    Returns:
    {
        "exploitability": 0.0045,
        "solve_time_ms": 142,
        "strategy": { "AA": {"fold": 0.0, "call": 0.2, "raise": 0.8}, ... },
        "overall_frequencies": {"fold": 0.32, "call": 0.44, "raise": 0.24},
        "optimal_sizing": 0.33,
        "engine": "Rust DCFR Depth-Limited Engine"
    }
    """
    permission_classes = [permissions.AllowAny]

    def post(self, request):
        board = request.data.get("board", ["Ah", "Kd", "2c"])
        spot = request.data.get("spot", "BTN_vs_BB_SRP")
        pot = float(request.data.get("pot", 6.5))
        effective_stack = float(request.data.get("effective_stack", 97.0))
        rake_percent = float(request.data.get("rake_percent", 5.0))
        rake_cap = float(request.data.get("rake_cap", 3.0))

        # Validate board
        if not isinstance(board, list) or len(board) < 3:
            return Response({"error": "Board must contain at least 3 flop cards."}, status=status.HTTP_400_BAD_REQUEST)

        # 1. Morph / Interpolate Preflop Ranges
        oop_range = request.data.get("oop_range")
        ip_range = request.data.get("ip_range")
        if not oop_range or not ip_range:
            derived_oop, derived_ip = PreflopRangeService.get_spot_ranges(
                spot=spot,
                rake_percent=rake_percent,
                rake_cap=rake_cap
            )
            oop_range = oop_range or derived_oop
            ip_range = ip_range or derived_ip

        # 2. Run solve via Engine Client
        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)
        try:
            result = loop.run_until_complete(
                engine_client.solve_flop(
                    board=board,
                    oop_range=oop_range,
                    ip_range=ip_range,
                    pot=pot,
                    effective_stack=effective_stack,
                    rake_percent=rake_percent,
                    rake_cap=rake_cap,
                    max_sizes_per_node=1
                )
            )
            return Response(result)
        except Exception as e:
            logger.error("Error running live solve: %s", str(e))
            return Response({"error": str(e)}, status=status.HTTP_500_INTERNAL_SERVER_ERROR)
        finally:
            loop.close()
