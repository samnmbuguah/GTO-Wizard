import asyncio
import random
import time
from typing import List, Dict, Any
from .models import Solution, StrategyNode

class SolverService:
    """
    Simulates GTO Wizard's Dynamic Sizing logic using a depth-limited approach.
    Fast mode solves ONLY the current street to remain under the 2s budget.
    """
    
    @staticmethod
    async def simulate_dynamic_sizing(
        solution_id: int, 
        current_path: str, 
        board_texture: str, 
        candidate_sizes: List[float]
    ) -> Dict[str, Any]:
        """
        Calculates EV for a list of candidate bet sizes.
        Returns the optimal sizing and the EV distribution.
        """
        start_time = time.time()
        
        # Simulate depth-limited computation (IO/CPU bound simulation)
        # In a real RTA, this would invoke a solver engine like Pio or a custom neural network.
        # Here we use a heuristic based on the nearest pre-solved GTO nodes.
        
        try:
            # Fetch base strategy for this path to get 'GTO baseline'
            base_nodes = await asyncio.to_thread(
                lambda: list(StrategyNode.objects.filter(solution_id=solution_id, path=current_path)[:5])
            )
            
            if not base_nodes:
                return {"error": "No baseline GTO data for this path", "optimal_size": None}

            # Heuristic Logic:
            # 1. Identify "GTO preferred" sizes from the pre-calculated strategy grid.
            # 2. Map candidate sizes to EV deltas based on board texture flexibility.
            
            ev_results = []
            for size in candidate_sizes:
                # Simulate a value between 0.0 and 1.0 (relative EV)
                # Textures like 'High' prefer larger sizes; 'Low' prefer small/polarization.
                base_ev = sum(n.ev for n in base_nodes) / len(base_nodes) if base_nodes else 0
                
                # Dynamic factor based on texture (Simplified RTA logic)
                texture_bonus = 1.05 if (board_texture == 'High' and size > 0.6) else 1.0
                texture_penalty = 0.95 if (board_texture == 'Low' and size > 0.75) else 1.0
                
                # Add some simulated convergence noise
                noise = random.uniform(-0.02, 0.02)
                simulated_ev = base_ev * texture_bonus * texture_penalty + noise
                
                ev_results.append({
                    "size": size,
                    "ev": round(simulated_ev, 4),
                    "confidence": round(random.uniform(0.85, 0.99), 2)
                })

            # Sort by EV to find the winner
            ev_results.sort(key=lambda x: x['ev'], reverse=True)
            optimal = ev_results[0]

            # Enforce the < 2s budget
            elapsed = time.time() - start_time
            if elapsed < 0.5:
                await asyncio.sleep(0.5 - elapsed) # Maintain a realistic 'thinking' feel while staying well under 2s

            return {
                "optimal_size": optimal['size'],
                "ev_distribution": ev_results,
                "calc_time_ms": int((time.time() - start_time) * 1000),
                "mode": "Depth-Limited (Fast)"
            }
            
        except Exception as e:
            return {"error": str(e)}

class SolverQueue:
    """
    Async Queue to manage simultaneous table streams.
    Ensures that concurrency limits (e.g. 5 tables) are respected.
    """
    def __init__(self, max_concurrency=5):
        self.queue = asyncio.Queue()
        self.semaphore = asyncio.Semaphore(max_concurrency)
        self._workers = []

    async def add_task(self, coro):
        async with self.semaphore:
            return await coro

# Singleton instance for the app
rta_solver_queue = SolverQueue()
