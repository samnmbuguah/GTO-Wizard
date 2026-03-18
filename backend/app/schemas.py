from pydantic import BaseModel
from typing import Dict, List, Optional

class SolutionBase(BaseModel):
    name: str
    rake: Optional[float] = None
    stack_depth: Optional[int] = None
    description: Optional[str] = None

class SolutionCreate(SolutionBase):
    pass

class Solution(SolutionBase):
    id: int
    class Config:
        from_attributes = True

class StrategyNodeBase(BaseModel):
    path: str
    hand: str
    actions: Dict[str, float]
    ev: Optional[float] = None
    equity: Optional[float] = None

class StrategyNode(StrategyNodeBase):
    id: int
    solution_id: int
    class Config:
        from_attributes = True

class IngestionRequest(BaseModel):
    file_path: str
    name: str
    format: str # pio_csv, texas_json
