import React from 'react';
import { HandMatrix } from '@holdem-poker-tools/hand-matrix';
import type { StrategyNode } from '../types/poker';

interface StrategyMatrixProps {
  nodes: StrategyNode[];
  onHandSelect?: (hand: string) => void;
}

const StrategyMatrix: React.FC<StrategyMatrixProps> = ({ nodes, onHandSelect }) => {
  // Map our node data to the library's expected format
  const combos = nodes.map(node => ({
    combo: node.hand, // Library expects "AA", "AKs", "AKo"
    color: '#6366f1', // Base color
    label: '', // We can customize labels later
    // The library allows custom cell rendering, but let's start with basic color mapping
  }));

  const handleCellClick = (hand: string) => {
    if (onHandSelect) onHandSelect(hand);
  };

  return (
    <div className="bg-slate-900/50 p-6 rounded-2xl border border-slate-800 shadow-2xl overflow-hidden backdrop-blur-sm">
      <div className="flex items-center justify-between mb-6">
        <h2 className="text-sm font-bold uppercase tracking-widest text-slate-500 px-1 border-l-4 border-indigo-500">Range Matrix</h2>
        <div className="flex gap-4 text-[10px]">
          <div className="flex items-center gap-1"><div className="w-2 h-2 bg-indigo-500 rounded-full"></div> <span>Raise (80%)</span></div>
          <div className="flex items-center gap-1"><div className="w-2 h-2 bg-indigo-400 rounded-full opacity-50"></div> <span>Call (20%)</span></div>
        </div>
      </div>
      
      <div className="aspect-square w-full max-w-[600px] mx-auto filter drop-shadow-[0_0_15px_rgba(99,102,241,0.1)]">
        <HandMatrix
          combos={combos}
          onSelect={handleCellClick}
          // The library should take care of the 13x13 grid logic
          // and proper hand label positioning
        />
      </div>
      
      <div className="mt-8 grid grid-cols-3 gap-4">
        <div className="p-4 bg-slate-800/40 rounded-xl border border-slate-700/50">
          <p className="text-[10px] text-slate-500 uppercase font-bold mb-1">Total Weight</p>
          <p className="text-xl font-bold">14.2%</p>
        </div>
        <div className="p-4 bg-slate-800/40 rounded-xl border border-slate-700/50">
          <p className="text-[10px] text-slate-500 uppercase font-bold mb-1">Combos Selected</p>
          <p className="text-xl font-bold">188.5</p>
        </div>
        <div className="p-4 bg-slate-800/40 rounded-xl border border-slate-700/50">
          <p className="text-[10px] text-slate-500 uppercase font-bold mb-1">Expected Value</p>
          <p className="text-xl font-bold text-emerald-400">+5.24 BB</p>
        </div>
      </div>
    </div>
  );
};

export default StrategyMatrix;
