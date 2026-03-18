from sqlalchemy import Column, Integer, String, Float, JSON, ForeignKey, Enum
from sqlalchemy.orm import relationship
from sqlalchemy.dialects.postgresql import JSONB
from .database import Base
import enum

class Position(str, enum.Enum):
    SB = "SB"
    BB = "BB"
    UTG = "UTG"
    MP = "MP"
    CO = "CO"
    BTN = "BTN"

class Solution(Base):
    __tablename__ = "solutions"

    id = Column(Integer, primary_key=True, index=True)
    name = Column(String, index=True)
    rake = Column(Float, nullable=True)
    stack_depth = Column(Integer, nullable=True)
    description = Column(String, nullable=True)
    config = Column(JSONB, nullable=True)  # Store solver config

    nodes = relationship("StrategyNode", back_populates="solution")

class StrategyNode(Base):
    __tablename__ = "strategy_nodes"

    id = Column(Integer, primary_key=True, index=True)
    solution_id = Column(Integer, ForeignKey("solutions.id"))
    path = Column(String, index=True)  # Path like 'root/bet/call'
    hand = Column(String, index=True)  # Hand like 'AA' or 'AhKh'
    
    # Store actions as JSONB: {"fold": 0.0, "call": 0.3, "raise_33": 0.7}
    actions = Column(JSONB)
    
    ev = Column(Float, nullable=True)
    equity = Column(Float, nullable=True)

    solution = relationship("Solution", back_populates="nodes")
