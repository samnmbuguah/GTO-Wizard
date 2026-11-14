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
        meta = PreflopRangeService.get_spot_metadata(spot)
        pot = float(request.data.get("pot", meta["default_pot"]))
        effective_stack = float(request.data.get("effective_stack", meta["default_stack"]))
        ante_bb = float(request.data.get("ante_bb", 0.0))
        rake_percent = float(request.data.get("rake_percent", 5.0))
        rake_cap = float(request.data.get("rake_cap", 0.6))
        use_bunching = bool(request.data.get("use_bunching", True))
        folded_positions = request.data.get("folded_positions") or (
            meta["folded_positions"] if use_bunching else []
        )
        num_folded_players = int(
            request.data.get("num_folded_players", len(folded_positions) if use_bunching else 0)
        )
        bunching_weights = request.data.get("bunching_weights") or []
        if bunching_weights and len(bunching_weights) != 13:
            return Response(
                {"error": "bunching_weights must contain 13 rank weights (2..A)."},
                status=status.HTTP_400_BAD_REQUEST,
            )
        action_sequence = [str(a) for a in (request.data.get("action_sequence") or [])]
        flop_actions = [str(a) for a in (request.data.get("flop_actions") or [])]
        turn_actions = [str(a) for a in (request.data.get("turn_actions") or [])]

        # Validate board
        if not isinstance(board, list) or len(board) < 3 or len(board) > 5:
            return Response(
                {"error": "Board must contain 3 to 5 cards."},
                status=status.HTTP_400_BAD_REQUEST,
            )

        # 1. Morph / Interpolate or Parse Custom Preflop Ranges
        raw_oop = request.data.get("oop_range")
        raw_ip = request.data.get("ip_range")
        oop_range = PreflopRangeService.parse_range_input(raw_oop) if raw_oop else {}
        ip_range = PreflopRangeService.parse_range_input(raw_ip) if raw_ip else {}
        if not oop_range or not ip_range:
            pos_oop = request.data.get("position_oop")
            pos_ip = request.data.get("position_ip")
            if pos_oop and pos_ip:
                derived_oop, derived_ip = PreflopRangeService.get_morphed_preflop_range(
                    position_oop=pos_oop,
                    position_ip=pos_ip,
                    stack_bb=effective_stack,
                    rake_pct=rake_percent,
                    rake_cap=rake_cap,
                )
            else:
                derived_oop, derived_ip = PreflopRangeService.get_spot_ranges(
                    spot=spot,
                    rake_percent=rake_percent,
                    rake_cap=rake_cap,
                    stack_bb=effective_stack,
                )
            oop_range = oop_range or derived_oop
            ip_range = ip_range or derived_ip

        common_kwargs = {
            "ante_bb": ante_bb,
            "rake_percent": rake_percent,
            "rake_cap": rake_cap,
            "num_folded_players": num_folded_players,
            "use_bunching": use_bunching,
            "bunching_weights": [float(w) for w in bunching_weights],
            "folded_positions": [str(p) for p in folded_positions],
            "max_bets_per_node": 1,
        }

        # 2. Run solve via Engine Bridge (chaining Flop -> Turn -> River when flop_actions/turn_actions supplied)
        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)
        try:
            async def _execute() -> dict:
                cur_oop = oop_range
                cur_ip = ip_range
                cur_pot = pot
                cur_stack = effective_stack

                if len(board) >= 4 and flop_actions:
                    flop_res = await engine_bridge.solve_flop(
                        board=board[:3],
                        oop_range=cur_oop,
                        ip_range=cur_ip,
                        pot=cur_pot,
                        effective_stack=cur_stack,
                        action_sequence=flop_actions,
                        **common_kwargs,
                    )
                    cur_oop = flop_res.get("posterior_oop_range") or cur_oop
                    cur_ip = flop_res.get("posterior_ip_range") or cur_ip
                    cur_pot = float(flop_res.get("next_street_pot", cur_pot))
                    cur_stack = float(flop_res.get("next_street_stack", cur_stack))

                if len(board) == 5 and turn_actions:
                    turn_res = await engine_bridge.solve_flop(
                        board=board[:4],
                        oop_range=cur_oop,
                        ip_range=cur_ip,
                        pot=cur_pot,
                        effective_stack=cur_stack,
                        action_sequence=turn_actions,
                        **common_kwargs,
                    )
                    cur_oop = turn_res.get("posterior_oop_range") or cur_oop
                    cur_ip = turn_res.get("posterior_ip_range") or cur_ip
                    cur_pot = float(turn_res.get("next_street_pot", cur_pot))
                    cur_stack = float(turn_res.get("next_street_stack", cur_stack))

                res = await engine_bridge.solve_flop(
                    board=board,
                    oop_range=cur_oop,
                    ip_range=cur_ip,
                    pot=cur_pot,
                    effective_stack=cur_stack,
                    action_sequence=action_sequence,
                    **common_kwargs,
                )
                res["starting_oop_range"] = oop_range
                res["starting_ip_range"] = ip_range
                res["spot_metadata"] = meta
                return res

            result = loop.run_until_complete(_execute())
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
                        "action_sequence": action_sequence,
                    }, time.time())
                )
                return Response(result)
            except Exception as fb_err:
                return Response({"error": f"{str(e)} (fallback failed: {str(fb_err)})"}, status=status.HTTP_500_INTERNAL_SERVER_ERROR)
        finally:
            loop.close()


class FormationRangesView(APIView):
    """GET /api/solutions/formation-ranges/?spot=BTN_vs_BB_SRP&stack=100&rake_percent=5&rake_cap=0.6"""
    permission_classes = [permissions.AllowAny]

    def get(self, request):
        spot = request.query_params.get("spot", "BTN_vs_BB_SRP")
        stack_bb = float(request.query_params.get("stack", 100.0))
        rake_percent = float(request.query_params.get("rake_percent", 5.0))
        rake_cap = float(request.query_params.get("rake_cap", 0.6))
        meta = PreflopRangeService.get_spot_metadata(spot)
        oop_range, ip_range = PreflopRangeService.get_spot_ranges(
            spot=spot,
            rake_percent=rake_percent,
            rake_cap=rake_cap,
            stack_bb=stack_bb,
        )
        return Response({
            "spot": spot,
            "metadata": meta,
            "oop_range": oop_range,
            "ip_range": ip_range,
        })
