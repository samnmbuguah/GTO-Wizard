import pandas as pd
import json
from typing import List, Dict, Any
from sqlalchemy.orm import Session
from ..models import Solution, StrategyNode

class PioParser:
    def __init__(self, db: Session):
        self.db = db

    def parse_csv(self, file_path: str, solution_id: int):
        """
        Parses a PioSolver CSV export and stores it in the database.
        Pio CSVs typically have columns: Hand, Weight, EV, Equity, and actions.
        """
        df = pd.read_csv(file_path)
        
        # Example Pio CSV structure:
        # Hand,Weight,EV,Equity,Fold,Call,Raise...
        
        nodes = []
        for _, row in df.iterrows():
            hand = row['Hand']
            ev = row.get('EV', 0.0)
            equity = row.get('Equity', 0.0)
            
            # Actions are everything else except metadata columns
            metadata_cols = ['Hand', 'Weight', 'EV', 'Equity']
            actions = {col: float(row[col]) for col in df.columns if col not in metadata_cols}
            
            node = StrategyNode(
                solution_id=solution_id,
                path="root",  # This should be derived from the export context
                hand=hand,
                actions=actions,
                ev=ev,
                equity=equity
            )
            nodes.append(node)
        
        self.db.add_all(nodes)
        self.db.commit()
        return len(nodes)

def ingest_pio_csv(db: Session, file_path: str, name: str):
    solution = Solution(name=name)
    db.add(solution)
    db.commit()
    db.refresh(solution)
    
    parser = PioParser(db)
    count = parser.parse_csv(file_path, solution.id)
    return solution.id, count
