import React, { useState, useEffect } from 'react';
import { HandMatrix } from '@holdem-poker-tools/hand-matrix';
import type { StrategyNode } from '../types/poker';
import { Maximize2, Minimize2, Lock, Unlock } from 'lucide-react';

interface StrategyMatrixProps {
  nodes: StrategyNode[];
  onHandSelect?: (hand: string) => void;
}

interface NodeLock {
  id?: number;
  node: number;
  locked_actions: Record<string, number>;
  hand: string;
}

const StrategyMatrix: React.FC<StrategyMatrixProps> = ({ nodes, onHandSelect }) => {
  const [matrixSize, setMatrixSize] = useState(600);
  const [locks, setLocks] = useState<Record<string, NodeLock>>({});

  useEffect(() => {
    const fetchLocks = async () => {
      try {
        const res = await fetch('http://213.199.50.129:8000/api/locks/');
        const data = await res.json();
        const lockMap: Record<string, NodeLock> = {};
        data.forEach((lock: any) => {
          // We find the hand for this node
          const node = nodes.find(n => n.id === lock.node);
          if (node) lockMap[node.hand] = { ...lock, hand: node.hand };
        });
        setLocks(lockMap);
      } catch (e) {
        console.error('Failed to fetch locks:', e);
      }
    };
    if (nodes.length > 0) fetchLocks();
  }, [nodes]);

  const toggleLock = async (hand: string, node: StrategyNode) => {
    const isLocked = !!locks[hand];
    try {
      if (isLocked) {
        // Delete lock
        const lockId = locks[hand].id;
        await fetch(`http://213.199.50.129:8000/api/locks/${lockId}/`, { method: 'DELETE' });
        const newLocks = { ...locks };
        delete newLocks[hand];
        setLocks(newLocks);
      } else {
        // Create lock (locking current state)
        const res = await fetch('http://213.199.50.129:8000/api/locks/', {
          method: 'POST',
          headers: { 'Content-Type': 'application/json' },
          body: JSON.stringify({
            node: node.id,
            locked_actions: node.actions
          })
        });
        const newLock = await res.json();
        setLocks({ ...locks, [hand]: { ...newLock, hand } });
      }
    } catch (e) {
      console.error('Lock toggle failed:', e);
    }
  };

  const [selectedHand, setSelectedHand] = useState<string | null>(null);

  const combos = nodes.map(node => {
    const isRaise = (node.actions['raise'] || 0) > 0.5;
    const isCall = (node.actions['call'] || 0) > 0.2;
    const isDark = document.documentElement.classList.contains('dark');
    const foldColor = isDark ? '#1e293b' : '#f1f5f9';
    
    return {
      combo: node.hand,
      color: isRaise ? '#f43f5e' : isCall ? '#10b981' : foldColor,
    };
  });

  const selectedNode = nodes.find(n => n.hand === selectedHand);
  const isLocked = selectedHand ? !!locks[selectedHand] : false;

  return (
    <div className="bg-card p-4 md:p-6 rounded-3xl border border-border shadow-2xl backdrop-blur-md transition-all">
      <div className="flex flex-col md:flex-row md:items-center justify-between gap-4 mb-8 pb-6 border-b border-border">
        <div className="flex items-center gap-3">
          <div className="w-1.5 h-6 bg-indigo-500 rounded-full shadow-lg shadow-indigo-500/20"></div>
          <h2 className="text-sm font-bold uppercase tracking-widest text-muted">Range Matrix</h2>
        </div>
        
        <div className="flex flex-wrap items-center gap-4 md:gap-6">
          <div className="flex items-center gap-3 bg-background/50 px-3 py-1.5 rounded-xl border border-border">
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
            <div className="flex items-center gap-1.5"><div className="w-3 h-3 bg-[#f43f5e] rounded-sm"></div><span className="text-muted">Raise</span></div>
            <div className="flex items-center gap-1.5"><div className="w-3 h-3 bg-[#10b981] rounded-sm"></div><span className="text-muted">Call</span></div>
            <div className="flex items-center gap-1.5"><div className="w-3 h-3 bg-card border border-border rounded-sm"></div><span className="text-muted">Fold</span></div>
          </div>
        </div>
      </div>
      
      <div className="grid grid-cols-1 xl:grid-cols-12 gap-8">
        <div className="xl:col-span-8 flex items-center justify-center">
          <div 
            className="filter drop-shadow-[0_0_40px_rgba(0,0,0,0.1)] transition-all flex items-center justify-center p-2 md:p-6 bg-background/40 rounded-3xl relative"
            style={{ width: '100%', maxWidth: `${matrixSize}px`, aspectRatio: '1/1' }}
          >
            <div className="w-full h-full relative custom-hand-matrix grayscale-0">
              <HandMatrix
                combos={combos}
                onSelect={(hand) => {
                  setSelectedHand(hand);
                  if (onHandSelect) onHandSelect(hand);
                }}
              />
            </div>
          </div>
        </div>

        <div className="xl:col-span-4 space-y-6">
          {selectedHand && selectedNode ? (
             <div className="p-6 bg-background/50 rounded-3xl border border-border animate-in">
                <div className="flex items-center justify-between mb-6">
                  <h3 className="text-2xl font-black">{selectedHand}</h3>
                  <button 
                    onClick={() => toggleLock(selectedHand, selectedNode)}
                    className={`p-2 rounded-xl transition-all ${isLocked ? 'bg-amber-500 text-white shadow-lg shadow-amber-500/30' : 'bg-muted/10 text-muted hover:bg-muted/20'}`}
                    title={isLocked ? 'Unlock Strategy' : 'Lock Strategy'}
                  >
                    {isLocked ? <Lock className="w-5 h-5" /> : <Unlock className="w-5 h-5" />}
                  </button>
                </div>

                <div className="space-y-3">
                  {Object.entries(selectedNode.actions).map(([action, freq]) => (
                    <div key={action} className="space-y-1">
                      <div className="flex justify-between text-[10px] font-bold uppercase tracking-wider">
                        <span>{action}</span>
                        <span>{(freq * 100).toFixed(1)}%</span>
                      </div>
                      <div className="h-1.5 w-full bg-background rounded-full overflow-hidden">
                        <div 
                          className={`h-full rounded-full ${action === 'raise' ? 'bg-[#f43f5e]' : action === 'call' ? 'bg-[#10b981]' : 'bg-muted'}`}
                          style={{ width: `${freq * 100}%` }}
                        ></div>
                      </div>
                    </div>
                  ))}
                </div>

                {isLocked && (
                  <div className="mt-6 p-3 bg-amber-500/10 border border-amber-500/20 rounded-xl flex items-start gap-2">
                    <Lock className="w-3 h-3 text-amber-500 mt-0.5" />
                    <p className="text-[10px] text-amber-600 font-medium">This strategy is locked for solving.</p>
                  </div>
                )}
             </div>
          ) : (
            <div className="h-full flex flex-col items-center justify-center p-8 text-center bg-background/20 rounded-3xl border border-dashed border-border/50">
               <div className="w-12 h-12 bg-muted/10 rounded-full flex items-center justify-center mb-4">
                 <Maximize2 className="w-6 h-6 text-muted/40" />
               </div>
               <p className="text-xs text-muted font-medium">Select a hand to view strategy and toggle node locking</p>
            </div>
          )}
        </div>
      </div>

      <div className="mt-8 flex flex-wrap gap-4">
        {Object.keys(locks).length > 0 && (
          <div className="flex items-center gap-2 px-3 py-1.5 bg-amber-500/10 border border-amber-500/20 rounded-xl text-amber-500 text-xs font-bold">
            <Lock className="w-3 h-3" />
            <span>{Object.keys(locks).length} Locked Strategies</span>
          </div>
        )}
      </div>
      
      <div className="mt-8 grid grid-cols-1 sm:grid-cols-3 gap-6">
        <div className="p-5 bg-background/40 rounded-2xl border border-border shadow-sm group hover:border-indigo-500/30 transition-all">
          <p className="text-[10px] text-muted uppercase font-bold mb-1 tracking-widest group-hover:text-indigo-500 transition-colors">Total Weight</p>
          <p className="text-2xl font-black">14.2%</p>
        </div>
        <div className="p-5 bg-background/40 rounded-2xl border border-border shadow-sm group hover:border-indigo-500/30 transition-all">
          <p className="text-[10px] text-muted uppercase font-bold mb-1 tracking-widest group-hover:text-indigo-500 transition-colors">Combos</p>
          <p className="text-2xl font-black">188.5</p>
        </div>
        <div className="p-5 bg-background/40 rounded-2xl border border-border shadow-sm group hover:border-emerald-500/30 transition-all">
          <p className="text-[10px] text-muted uppercase font-bold mb-1 tracking-widest group-hover:text-emerald-500 transition-colors">Expected Value</p>
          <p className="text-2xl font-black text-emerald-500">+5.24 BB</p>
        </div>
      </div>
    </div>
  );
};

export default StrategyMatrix;
