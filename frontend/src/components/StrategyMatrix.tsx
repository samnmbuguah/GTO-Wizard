import React, { useState, useEffect } from 'react';
import type { StrategyNode } from '../types/poker';
import { 
  Maximize2, 
  Lock, 
  Unlock, 
  Settings as SettingsIcon,
  Shuffle,
  ArrowLeftRight,
  Dice5,
  RotateCcw,
  MoreHorizontal
} from 'lucide-react';
import { apiClient } from '../api/client';

interface StrategyLock {
  id: number;
  node: number;
  locked_actions: any;
  is_active: boolean;
}

interface StrategyMatrixProps {
  nodes: StrategyNode[];
  onHandSelect?: (hand: string) => void;
}

const ranks = ['A', 'K', 'Q', 'J', 'T', '9', '8', '7', '6', '5', '4', '3', '2'];

// Color constants from reference
const COLORS = {
  green: '#327A00', // Call
  blue: '#457B9D', // Fold
  red: '#B80F0A', // Raise
  gray: 'rgb(87, 97, 98)',
  text: 'rgb(204, 219, 220)'
};

const StrategyMatrix: React.FC<StrategyMatrixProps> = ({ nodes, onHandSelect }) => {
  const [locks, setLocks] = useState<Record<string, StrategyLock>>({});
  const [selectedHand, setSelectedHand] = useState<string | null>(null);

  useEffect(() => {
    const fetchLocks = async () => {
      try {
        const data = await apiClient.get<StrategyLock[]>('/locks/');
        if (Array.isArray(data)) {
          const lockMap: Record<string, StrategyLock> = {};
          data.forEach(lock => {
            const node = nodes.find(n => n.id === lock.node);
            if (node) lockMap[node.hand] = lock;
          });
          setLocks(lockMap);
        }
      } catch (err) {
        console.error('Failed to fetch locks:', err);
      }
    };
    if (nodes.length > 0) fetchLocks();
  }, [nodes]);

  const toggleLock = async (hand: string, node: StrategyNode, customActions?: any) => {
    const isLocked = !!locks[hand];
    try {
      if (isLocked) {
        await apiClient.delete(`/locks/${locks[hand].id}/`);
        const newLocks = { ...locks };
        delete newLocks[hand];
        setLocks(newLocks);
      } else {
        const newLock = await apiClient.post<StrategyLock>('/locks/', {
          node: node.id,
          locked_actions: customActions || node.actions,
          is_active: true
        });
        setLocks({ ...locks, [hand]: newLock });
      }
    } catch (err) {
      console.error('Failed to toggle lock:', err);
    }
  };

  const selectedNode = nodes.find(n => n.hand === selectedHand);
  const isLocked = selectedHand ? !!locks[selectedHand] : false;

  const renderCell = (rankRow: string, rankCol: string) => {
    const isPair = rankRow === rankCol;
    const isSuited = ranks.indexOf(rankRow) < ranks.indexOf(rankCol);
    const hand = isPair ? `${rankRow}${rankCol}` : (isSuited ? `${rankRow}${rankCol}s` : `${rankCol}${rankRow}o`);
    
    const node = nodes.find(n => n.hand === hand);
    const isSelected = selectedHand === hand;
    const handIsLocked = !!locks[hand];
    
    // Default actions if no GTO data
    const actions = node?.actions || { fold: 1.0 };
    
    // Calculate gradient based on action frequencies
    const foldFreq = (actions.fold ?? actions.Fold) || 0;
    const callFreq = (actions.call ?? actions.Call) || 0;
    const raiseFreq = (actions.raise ?? actions.Raise) || 0;
    
    const foldPct = foldFreq * 100;
    const callPct = callFreq * 100;
    const raisePct = raiseFreq * 100;

    let gradientStops: string[] = [];
    let currentPct = 0;
    if (raisePct > 0) {
      gradientStops.push(`${COLORS.red} ${currentPct}%`, `${COLORS.red} ${currentPct + raisePct}%`);
      currentPct += raisePct;
    }
    if (callPct > 0) {
      gradientStops.push(`${COLORS.green} ${currentPct}%`, `${COLORS.green} ${currentPct + callPct}%`);
      currentPct += callPct;
    }
    if (foldPct > 0) {
      gradientStops.push(`${COLORS.blue} ${currentPct}%`, `${COLORS.blue} ${currentPct + foldPct}%`);
    }

    const backgroundStyle = gradientStops.length > 0 
      ? `linear-gradient(to right, ${gradientStops.join(', ')})`
      : COLORS.gray;
    
    // Calculate tooltip text
    let tooltipText = 'No folds';
    if (foldFreq > 0) {
      const totalFreq = foldFreq + callFreq + raiseFreq;
      if (totalFreq > 0) {
        const foldPercentage = (foldFreq / totalFreq * 100).toFixed(2);
        tooltipText = `${foldPercentage}% fold`;
      }
    }
    
    return (
      <button
        key={hand}
        onClick={() => {
          setSelectedHand(hand);
          if (onHandSelect) onHandSelect(hand);
        }}
        className={`
          relative w-full aspect-square border-[0.5px] border-[#182628] overflow-hidden flex flex-col group
          highLevelHandSolution p-button p-component hover:opacity-80 transition-opacity
          ${isSelected ? 'ring-2 ring-white z-10' : ''}
          ${handIsLocked ? 'ring-2 ring-yellow-500 z-10' : ''}
        `}
        style={{ background: backgroundStyle, color: COLORS.text }}
        title={tooltipText}
      >
        <span className="absolute inset-0 flex items-center justify-center z-10 w-full text-center text-[9px] sm:text-[10px] md:text-[11.5px] font-black uppercase tracking-tighter pointer-events-none drop-shadow-md leading-none">
          {hand}
        </span>
        
        {handIsLocked && (
          <div className="absolute right-0.5 bottom-0.5 z-10">
            <Lock className="w-2 h-2 text-white drop-shadow-md" />
          </div>
        )}
      </button>
    );
  };

  return (
    <div className="flex w-full h-full text-[#ccdbdc]">
      <div className="flex-[2] mr-4 relative min-w-0 flex flex-col">
        {/* Grid Icons Toolbar */}
        <div className="flex justify-between items-center mb-1.5 px-0.5">
          <Shuffle className="w-3.5 h-3.5 text-[#7aa6da] cursor-pointer hover:text-white" />
          <div className="flex gap-2">
            <ArrowLeftRight className="w-3.5 h-3.5 text-[#7aa6da] cursor-pointer hover:text-white" />
            <Dice5 className="w-3.5 h-3.5 text-[#7aa6da] cursor-pointer hover:text-white" />
          </div>
        </div>
        
        <div className="w-full flex-1 relative">
          <div className="grid grid-cols-13 w-full h-full border border-[#182628]">
            {ranks.map(rankRow => (
              <React.Fragment key={rankRow}>
                {ranks.map(rankCol => renderCell(rankRow, rankCol))}
              </React.Fragment>
            ))}
          </div>
        </div>
      </div>

      <div className="flex-1 min-w-[200px] flex flex-col items-center justify-center p-4 bg-[#0d1f1f] rounded text-[#ccdbdc] h-full shadow-inner relative border border-[#182628]">
        {selectedHand && selectedNode ? (
          <div className="w-full flex-1 flex flex-col h-full">
            <div className="flex items-center justify-center mb-10 mt-6 relative w-full">
              <Maximize2 className="w-6 h-6 absolute left-0 top-0 cursor-pointer hover:text-white" />
              <h3 className="text-xl font-bold">{selectedHand} strategy</h3>
               <div className="absolute right-0 top-0 flex gap-2 items-center">
                 <RotateCcw className="w-4 h-4 cursor-pointer hover:text-white mr-1" />
                 <button onClick={() => toggleLock(selectedHand, selectedNode)} className="cursor-pointer hover:text-white p-0 bg-transparent border-none">
                    {isLocked ? <Lock className="w-4 h-4 text-yellow-500" /> : <Unlock className="w-4 h-4 text-yellow-500" />}
                 </button>
                 <SettingsIcon className="w-4 h-4 cursor-pointer hover:text-white" />
                 <MoreHorizontal className="w-4 h-4 cursor-pointer hover:text-white ml-1" />
              </div>
            </div>

            <div className="grid grid-cols-2 gap-8 mt-10 w-full text-center">
              <div>
                <p className="text-[14px] font-bold uppercase tracking-wider mb-2">Weighting</p>
                <p className="text-xl font-black">14.2%</p>
              </div>
              <div>
                <p className="text-[14px] font-bold uppercase tracking-wider mb-2">EV</p>
                <p className="text-xl font-black">+5.24 BB</p>
              </div>
            </div>
            
            <div className="space-y-4 mt-12 w-full px-4">
              {Object.entries(selectedNode.actions || {}).map(([action, freq]) => (
                <div key={action} className="space-y-1 w-full">
                  <div className="flex justify-between text-xs font-bold uppercase border-b border-[#2d393b] pb-1">
                    <span>{action}</span>
                    <span className="font-black text-white">{(freq * 100).toFixed(1)}%</span>
                  </div>
                </div>
              ))}
            </div>
          </div>
        ) : (
          <div className="flex flex-col items-center justify-center h-full text-[#7aa6da] w-full gap-4 opacity-50">
             <Maximize2 className="w-10 h-10 transform rotate-45" />
             <p className="text-[13px] font-bold uppercase tracking-widest text-center">Select a hand to view strategy</p>
          </div>
        )}
        
        <button className="absolute bottom-4 right-4 bg-transparent border border-[#2d393b] rounded p-2 hover:bg-[#2d393b] hover:text-white transition-colors cursor-pointer">
          <SettingsIcon className="w-4 h-4" />
        </button>
      </div>
    </div>
  );
};

export default StrategyMatrix;
