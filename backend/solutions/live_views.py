"""
Live Solver View & API Endpoints.
Handles real-time depth-limited solves (<2s) with custom rake interpolation and dynamic sizing.
"""
import asyncio
import logging
import time
from rest_framework.views import APIView
from rest_framework.response import Response
from rest_framework import permissions, status

from .services.engine_bridge import engine_bridge
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
        pot = float(request.data.get("pot", 5.5))
        effective_stack = float(request.data.get("effective_stack", 100.0))
        ante_bb = float(request.data.get("ante_bb", 0.0))
        rake_percent = float(request.data.get("rake_percent", 5.0))
        rake_cap = float(request.data.get("rake_cap", 0.6))
        num_folded_players = int(request.data.get("num_folded_players", 4))
        use_bunching = bool(request.data.get("use_bunching", True))
        open_size = float(request.data.get("open_size", 2.5))

        # Validate board
        if not isinstance(board, list) or len(board) < 3:
            return Response({"error": "Board must contain at least 3 flop cards."}, status=status.HTTP_400_BAD_REQUEST)

        # 1. Morph / Interpolate Preflop Ranges
        oop_range = request.data.get("oop_range")
        ip_range = request.data.get("ip_range")
        if not oop_range or not ip_range:
            pos_oop = request.data.get("position_oop")
            pos_ip = request.data.get("position_ip")
            if pos_oop and pos_ip:
                derived_oop, derived_ip = PreflopRangeService.get_morphed_preflop_range(
                    position_oop=pos_oop,
                    position_ip=pos_ip,
                    stack_bb=effective_stack,
                    rake_pct=rake_percent,
                    rake_cap=rake_cap
                )
            else:
                derived_oop, derived_ip = PreflopRangeService.get_spot_ranges(
                    spot=spot,
                    rake_percent=rake_percent,
                    rake_cap=rake_cap
                )
            oop_range = oop_range or derived_oop
            ip_range = ip_range or derived_ip

        # 2. Run solve via Engine Bridge
        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)
        try:
            result = loop.run_until_complete(
                engine_bridge.solve_flop(
                    board=board,
                    oop_range=oop_range,
                    ip_range=ip_range,
                    pot=pot,
                    effective_stack=effective_stack,
                    ante_bb=ante_bb,
                    rake_percent=rake_percent,
                    rake_cap=rake_cap,
                    num_folded_players=num_folded_players,
                    use_bunching=use_bunching,
                    max_bets_per_node=1
                )
            )
            return Response(result)
        except Exception as e:
            logger.error("Error running live solve: %s", str(e))
            try:
                result = loop.run_until_complete(
                    engine_bridge._run_local_dls_solve({
                        "board": board,
                        "oop_range": oop_range,
                        "ip_range": ip_range,
                        "pot": pot,
                        "effective_stack": effective_stack,
                        "rake_percent": rake_percent,
                        "rake_cap": rake_cap,
                        "max_bets_per_node": 1,
                    }, time.time())
                )
                return Response(result)
            except Exception as fb_err:
                return Response({"error": f"{str(e)} (fallback failed: {str(fb_err)})"}, status=status.HTTP_500_INTERNAL_SERVER_ERROR)
        finally:
            loop.close()
