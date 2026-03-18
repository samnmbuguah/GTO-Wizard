import React, { useState } from 'react';
import { HandMatrix } from '@holdem-poker-tools/hand-matrix';
import type { StrategyNode } from '../types/poker';
import { Maximize2, Minimize2 } from 'lucide-react';

interface StrategyMatrixProps {
  nodes: StrategyNode[];
  onHandSelect?: (hand: string) => void;
}

const StrategyMatrix: React.FC<StrategyMatrixProps> = ({ nodes, onHandSelect }) => {
  const [matrixSize, setMatrixSize] = useState(600);

  // Map our node data to the library's expected format
  const combos = nodes.map(node => {
    const isRaise = (node.actions['raise'] || 0) > 0.5;
    const isCall = (node.actions['call'] || 0) > 0.2;
    
    return {
      combo: node.hand,
      color: isRaise ? '#6366f1' : isCall ? '#818cf8' : '#e2e8f0',
    };
  });

  const handleCellClick = (hand: string) => {
    if (onHandSelect) onHandSelect(hand);
  };

  return (
    <div className="bg-card p-6 rounded-2xl border border-border shadow-2xl overflow-hidden backdrop-blur-sm transition-all duration-300">
      <div className="flex items-center justify-between mb-8 pb-6 border-b border-border">
        <div className="flex items-center gap-3">
          <div className="w-1 h-6 bg-indigo-500 rounded-full"></div>
          <h2 className="text-sm font-bold uppercase tracking-widest text-muted">Range Matrix</h2>
        </div>
        
        <div className="flex items-center gap-6">
          <div className="flex items-center gap-3 bg-background/50 px-3 py-1.5 rounded-lg border border-border">
            <Minimize2 className="w-3.5 h-3.5 text-muted" />
            <input 
              type="range" 
              min="300" 
              max="900" 
              value={matrixSize} 
              onChange={(e) => setMatrixSize(parseInt(e.target.value))}
              className="w-32 accent-indigo-500 h-1 cursor-pointer"
            />
            <Maximize2 className="w-3.5 h-3.5 text-muted" />
          </div>
          
          <div className="flex gap-4 text-[10px] font-medium uppercase tracking-wider text-muted">
            <div className="flex items-center gap-1.5">
              <div className="w-2.5 h-2.5 bg-[#6366f1] rounded-sm"></div> 
              <span>Raise</span>
            </div>
            <div className="flex items-center gap-1.5">
              <div className="w-2.5 h-2.5 bg-[#818cf8] rounded-sm"></div> 
              <span>Call</span>
            </div>
          </div>
        </div>
      </div>
      
      <div 
        className="mx-auto filter drop-shadow-[0_0_20px_rgba(99,102,241,0.08)] transition-all duration-300 flex items-center justify-center p-4 bg-background/20 rounded-xl"
        style={{ width: `${matrixSize}px`, height: `${matrixSize}px` }}
      >
        <div className="w-full h-full relative custom-hand-matrix transition-all">
          <HandMatrix
            combos={combos}
            onSelect={handleCellClick}
          />
        </div>
      </div>

      
      <div className="mt-12 grid grid-cols-3 gap-6">
        <div className="p-5 bg-background/40 rounded-2xl border border-border transition-colors">
          <p className="text-[10px] text-muted uppercase font-bold mb-2 tracking-widest">Total Weight</p>
          <p className="text-2xl font-bold tracking-tight">14.2%</p>
        </div>
        <div className="p-5 bg-background/40 rounded-2xl border border-border transition-colors">
          <p className="text-[10px] text-muted uppercase font-bold mb-2 tracking-widest">Combos Selected</p>
          <p className="text-2xl font-bold tracking-tight">188.5</p>
        </div>
        <div className="p-5 bg-background/40 rounded-2xl border border-border transition-colors">
          <p className="text-[10px] text-muted uppercase font-bold mb-2 tracking-widest">Expected Value</p>
          <p className="text-2xl font-bold tracking-tight text-emerald-500">+5.24 BB</p>
        </div>
      </div>
    </div>
  );
};


export default StrategyMatrix;
