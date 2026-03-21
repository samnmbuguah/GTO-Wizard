import httpx
import logging
from django.conf import settings
from typing import List, Dict, Any, Optional

logger = logging.getLogger(__name__)

class GTOWizardClient:
    """
    Custom async client for interacting with the GTO Wizard Researcher API.
    Provides real, depth-limited solving data.
    """
    
    BASE_URL = "https://researcher.gtowizard.com"
    
    def __init__(self, api_key: Optional[str] = None):
        self.api_key = api_key or getattr(settings, 'GTOWIZARD_API_KEY', None)
        self.headers = {
            "X-API-KEY": self.api_key,
            "Content-Type": "application/json"
        }

    async def get_strategy(self, action_history: str, board_cards: List[str]) -> Dict[str, Any]:
        """
        Calls POST /strategy to fetch the strategy and EV for a given node.
        """
        if not self.api_key:
            return {"error": "API Key not configured"}
            
        # Format board cards: ["Ah", "Kd", "Qs"] -> "AhKdQs"
        board_str = "".join(board_cards)
        
        payload = {
            "action_history": action_history,
            "board_cards": board_str
        }
        
        async with httpx.AsyncClient(timeout=10.0) as client:
            try:
                response = await client.post(
                    f"{self.BASE_URL}/strategy",
                    json=payload,
                    headers=self.headers
                )
                response.raise_for_status()
                return response.json()
            except httpx.HTTPStatusError as e:
                logger.error(f"GTO Wizard API error: {e.response.status_code} - {e.response.text}")
                return {"error": f"API Error: {e.response.status_code}"}
            except Exception as e:
                logger.error(f"GTO Wizard connection error: {str(e)}")
                return {"error": f"Connection Error: {str(e)}"}

    @staticmethod
    def translate_path_to_history(path: str) -> str:
        """
        Translates internal path format (root:c:r) to GTO Wizard's action_history format.
        Example: root:c:r -> "k_b2.5" (Heuristic translation)
        """
        if path == 'root' or not path:
            return ""
            
        parts = path.split(':')
        history = []
        
        for p in parts:
            if p == 'root': continue
            if p == 'c':
                # Map 'c' to 'k' (check) if early in move, or 'c' (call) if after bet
                # Simplified: use 'k' for first action, 'c' for others
                history.append('k' if not history else 'c')
            elif p == 'r':
                # Map 'r' to 'b2.5' (bet) or 'r3x' (raise)
                # Simplified: default to 2.5bb bet or 3x raise
                history.append('b2.5' if not history else 'r3')
        
        return "".join(history)

# Singleton instance
gto_client = GTOWizardClient()
