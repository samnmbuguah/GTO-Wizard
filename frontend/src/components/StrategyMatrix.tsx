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
    
    // Using poker standard high-visibility colors
    // Raise: Red/Pink (#f43f5e)
    // Call: Green/Emerald (#10b981)
    // Fold: Gray (#94a3b8)
    return {
      combo: node.hand,
      color: isRaise ? '#f43f5e' : isCall ? '#10b981' : '#f1f5f9',
    };
  });

  const handleCellClick = (hand: string) => {
    if (onHandSelect) onHandSelect(hand);
  };

  return (
    <div className="bg-card p-4 md:p-6 rounded-2xl border border-border shadow-2xl overflow-hidden backdrop-blur-sm transition-all duration-300">
      <div className="flex flex-col md:flex-row md:items-center justify-between gap-4 mb-8 pb-6 border-b border-border">
        <div className="flex items-center gap-3">
          <div className="w-1 h-6 bg-indigo-500 rounded-full"></div>
          <h2 className="text-sm font-bold uppercase tracking-widest text-muted">Range Matrix</h2>
        </div>
        
        <div className="flex flex-wrap items-center gap-4 md:gap-6">
          <div className="flex items-center gap-3 bg-background px-3 py-1.5 rounded-lg border border-border">
            <Minimize2 className="w-3.5 h-3.5 text-muted" />
            <input 
              type="range" 
              min="280" 
              max="1000" 
              value={matrixSize} 
              onChange={(e) => setMatrixSize(parseInt(e.target.value))}
              className="w-24 md:w-32 accent-indigo-500 h-1 cursor-pointer"
            />
            <Maximize2 className="w-3.5 h-3.5 text-muted" />
          </div>
          
          <div className="flex gap-4 text-[10px] font-bold uppercase tracking-wider">
            <div className="flex items-center gap-1.5">
              <div className="w-3 h-3 bg-[#f43f5e] rounded-sm"></div> 
              <span className="text-muted">Raise</span>
            </div>
            <div className="flex items-center gap-1.5">
              <div className="w-3 h-3 bg-[#10b981] rounded-sm"></div> 
              <span className="text-muted">Call</span>
            </div>
            <div className="flex items-center gap-1.5">
              <div className="w-3 h-3 bg-[#f1f5f9] border border-border rounded-sm"></div> 
              <span className="text-muted">Fold</span>
            </div>
          </div>
        </div>
      </div>
      
      <div 
        className="mx-auto filter drop-shadow-[0_0_30px_rgba(0,0,0,0.1)] transition-all duration-300 flex items-center justify-center p-2 md:p-4 bg-background/40 rounded-xl"
        style={{ width: '100%', maxWidth: `${matrixSize}px`, aspectRatio: '1/1' }}
      >
        <div className="w-full h-full relative custom-hand-matrix">
          <HandMatrix
            combos={combos}
            onSelect={handleCellClick}
          />
        </div>
      </div>
      
      <div className="mt-8 grid grid-cols-1 sm:grid-cols-3 gap-4 md:gap-6">
        <div className="p-4 bg-background/40 rounded-2xl border border-border">
          <p className="text-[10px] text-muted uppercase font-bold mb-1 tracking-widest">Total Weight</p>
          <p className="text-xl font-bold">14.2%</p>
        </div>
        <div className="p-4 bg-background/40 rounded-2xl border border-border">
          <p className="text-[10px] text-muted uppercase font-bold mb-1 tracking-widest">Combos</p>
          <p className="text-xl font-bold">188.5</p>
        </div>
        <div className="p-4 bg-background/40 rounded-2xl border border-border">
          <p className="text-[10px] text-muted uppercase font-bold mb-1 tracking-widest">Expected Value</p>
          <p className="text-xl font-bold text-emerald-500">+5.24 BB</p>
        </div>
      </div>
    </div>
  );
};

export default StrategyMatrix;
