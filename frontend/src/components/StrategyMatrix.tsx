import React from 'react';
import HandCell from './HandCell';
import type { StrategyNode } from '../types/poker';

const RANKS = ['A', 'K', 'Q', 'J', 'T', '9', '8', '7', '6', '5', '4', '3', '2'];

interface StrategyMatrixProps {
  nodes: StrategyNode[];
  onHandSelect?: (hand: string) => void;
  selectedHand?: string;
}

const StrategyMatrix: React.FC<StrategyMatrixProps> = ({ nodes, onHandSelect, selectedHand }) => {
  const nodeMap = React.useMemo(() => {
    const map: Record<string, StrategyNode> = {};
    nodes.forEach(node => {
      map[node.hand] = node;
    });
    return map;
  }, [nodes]);

  const renderGrid = () => {
    const grid = [];
    for (let r1 = 0; r1 < 13; r1++) {
      for (let r2 = 0; r2 < 13; r2++) {
        const rank1 = RANKS[r1];
        const rank2 = RANKS[r2];
        let hand = '';
        
        if (r1 < r2) {
          hand = `${rank1}${rank2}s`;
        } else if (r1 > r2) {
          hand = `${rank2}${rank1}o`;
        } else {
          hand = `${rank1}${rank2}`;
        }

        grid.push(
          <HandCell 
            key={hand}
            hand={hand}
            strategy={nodeMap[hand]?.actions}
            isSelected={selectedHand === hand}
            onClick={() => onHandSelect?.(hand)}
          />
        );
      }
    }
    return grid;
  };

  return (
    <div className="grid grid-cols-13 gap-0 w-full max-w-2xl aspect-square bg-slate-900 p-1 rounded-lg shadow-2xl overflow-hidden border border-slate-700">
      {renderGrid()}
    </div>
  );
};

export default StrategyMatrix;
