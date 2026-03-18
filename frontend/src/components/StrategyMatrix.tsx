import React, { useState, useEffect } from 'react';
import type { StrategyNode } from '../types/poker';
import { 
  Maximize2, 
  Minimize2, 
  Lock, 
  Unlock, 
  Edit2, 
  Check, 
  X,
  Shuffle,
  RefreshCw,
  Settings as SettingsIcon
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
  green: 'rgba(50, 122, 0, 0.6)',
  blue: 'rgba(69, 123, 157, 0.6)',
  gray: 'rgb(87, 97, 98)',
  text: 'rgb(204, 219, 220)'
};

const StrategyMatrix: React.FC<StrategyMatrixProps> = ({ nodes, onHandSelect }) => {
  const [matrixSize, setMatrixSize] = useState(800);
  const [locks, setLocks] = useState<Record<string, StrategyLock>>({});
  const [selectedHand, setSelectedHand] = useState<string | null>(null);
  const [isEditing, setIsEditing] = useState(false);
  const [editedActions, setEditedActions] = useState<Record<string, number> | null>(null);

  const handleFrequencyChange = (actionToChange: string, newValue: number) => {
    if (!editedActions) return;
    const newActions = { ...editedActions };
    const oldValue = newActions[actionToChange];
    const diff = newValue - oldValue;
    newActions[actionToChange] = newValue;
    const otherActions = Object.keys(newActions).filter(a => a !== actionToChange);
    const totalOther = otherActions.reduce((sum, a) => sum + newActions[a], 0);
    if (totalOther > 0) {
      otherActions.forEach(a => {
        newActions[a] = Math.max(0, newActions[a] - (diff * (newActions[a] / totalOther)));
      });
    } else if (otherActions.length > 0) {
      otherActions.forEach(a => {
        newActions[a] = Math.max(0, (1 - newValue) / otherActions.length);
      });
    }
    const finalSum = Object.values(newActions).reduce((a, b) => a + b, 0);
    if (finalSum > 0) {
      Object.keys(newActions).forEach(a => newActions[a] /= finalSum);
    }
    setEditedActions(newActions);
  };

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
    let backgroundStyle = '';
    let textColor = 'inherit';
    
    const foldFreq = actions.fold || 0;
    const callFreq = actions.call || 0;
    const raiseFreq = actions.raise || 0;
    
    if (foldFreq >= 0.5) {
      // Mostly fold - solid gray
      backgroundStyle = `background: linear-gradient(to right, ${COLORS.gray} 50%, ${COLORS.gray} 100%)`;
      textColor = 'inherit';
    } else if (callFreq > 0 && raiseFreq > 0) {
      // Mixed actions - gradient
      const callPercentage = callFreq / (callFreq + raiseFreq) * 100;
      backgroundStyle = `background: linear-gradient(to right, ${COLORS.green} ${callPercentage}%, ${COLORS.blue} ${callPercentage}%, ${COLORS.blue} 100%)`;
      textColor = COLORS.text;
    } else if (callFreq > 0.5) {
      // Mostly call - solid green
      backgroundStyle = `background: linear-gradient(to right, ${COLORS.green} 50%, ${COLORS.green} 100%)`;
      textColor = COLORS.text;
    } else if (raiseFreq > 0.5) {
      // Mostly raise - solid blue
      backgroundStyle = `background: linear-gradient(to right, ${COLORS.blue} 50%, ${COLORS.blue} 100%)`;
      textColor = COLORS.text;
    }
    
    // Calculate tooltip text
    let tooltipText = 'No folds';
    if (foldFreq > 0) {
      const totalFreq = foldFreq + callFreq + raiseFreq;
      if (totalFreq > 0) {
        const foldPercentage = (foldFreq / totalFreq * 100).toFixed(2);
        tooltipText = `${foldPercentage}`;
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
          relative w-full aspect-square border-l border-t border-poker-gray overflow-hidden flex flex-col group
          highLevelHandSolution p-button p-component
          ${isSelected ? 'ring-2 ring-poker-accent z-10' : ''}
          ${handIsLocked ? 'ring-1 ring-yellow-500 z-10' : ''}
        `}
        style={{ background: backgroundStyle, color: textColor }}
        title={tooltipText}
      >
        <span className="relative z-10 w-full text-center text-[9px] font-black uppercase tracking-tighter pt-1 pointer-events-none">
          {hand}
        </span>
        
        {handIsLocked && (
          <div className="absolute right-0.5 bottom-0.5 z-10">
            <Lock className="w-2 h-2 text-white" />
          </div>
        )}
      </button>
    );
  };

  return (
    <div className="strategy-container">
      <div className="strategy-header">
        <div className="flex items-center justify-between mb-4">
          <div className="flex items-center gap-2">
            <button className="p-1.5 bg-poker-gray hover:bg-poker-darkgray rounded text-poker-light hover:text-white transition-all">
              <Shuffle className="w-3 h-3" />
            </button>
            <button className="p-1.5 bg-poker-gray hover:bg-poker-darkgray rounded text-poker-light hover:text-white transition-all">
              <RefreshCw className="w-3 h-3" />
            </button>
          </div>
          
          <div className="flex items-center gap-2">
            <div className="flex items-center gap-1">
              <Minimize2 className="w-3 h-3 text-poker-light" />
              <input 
                type="range" 
                min="280" 
                max="1200" 
                value={matrixSize} 
                onChange={(e) => setMatrixSize(parseInt(e.target.value))}
                className="w-24 accent-poker-accent h-1 cursor-pointer"
              />
              <Maximize2 className="w-3 h-3 text-poker-light" />
            </div>
          </div>
          
          <button className="p-1.5 bg-poker-gray hover:bg-poker-darkgray rounded text-poker-light hover:text-white transition-all">
            <SettingsIcon className="w-3 h-3" />
          </button>
        </div>
      </div>
      
      <div className="strategy-content">
        <div className="range-visualizer">
          <div 
            className="solutionGrid"
            style={{ width: '100%', maxWidth: `${matrixSize}px`, aspectRatio: '1/1' }}
          >
            <div className="solutionGrid-row">
              {ranks.map(rankRow => (
                <div key={rankRow} className="solutionGrid-row-handButton">
                  {ranks.map(rankCol => renderCell(rankRow, rankCol))}
                </div>
              ))}
            </div>
          </div>
        </div>

        <div className="strategy-details">
          {selectedHand && selectedNode ? (
            <div className="p-4 bg-poker-gray rounded-lg">
              <div className="flex items-center justify-between mb-4">
                <h3 className="text-lg font-black text-white">{selectedHand}</h3>
                <div className="flex items-center gap-2">
                  {!isEditing && (
                    <button 
                      onClick={() => {
                        setIsEditing(true);
                        setEditedActions({ ...selectedNode.actions });
                      }}
                      className="p-1.5 rounded bg-poker-accent/20 text-poker-accent hover:bg-poker-accent/30 transition-all"
                    >
                      <Edit2 className="w-3 h-3" />
                    </button>
                  )}
                  {isEditing ? (
                    <>
                      <button onClick={() => { setIsEditing(false); setEditedActions(null); }} className="p-1.5 rounded bg-poker-red/20 text-poker-red hover:bg-poker-red/30">
                        <X className="w-3 h-3" />
                      </button>
                      <button onClick={() => { toggleLock(selectedHand, selectedNode, editedActions); setIsEditing(false); setEditedActions(null); }} className="p-1.5 rounded bg-poker-green/20 text-poker-green hover:bg-poker-green/30">
                        <Check className="w-3 h-3" />
                      </button>
                    </>
                  ) : (
                    <button 
                      onClick={() => toggleLock(selectedHand, selectedNode)}
                      className={`p-1.5 rounded transition-all ${isLocked ? 'bg-yellow-500 text-black' : 'bg-poker-gray/20 text-poker-light hover:bg-poker-gray/30'}`}
                    >
                      {isLocked ? <Lock className="w-3 h-3" /> : <Unlock className="w-3 h-3" />}
                    </button>
                  )}
                </div>
              </div>

              <div className="space-y-3">
                {(editedActions || selectedNode.actions) && Object.entries(editedActions || selectedNode.actions).map(([action, freq]) => (
                  <div key={action} className="space-y-1">
                    <div className="flex justify-between text-xs font-bold uppercase">
                      <span className={isEditing ? 'text-poker-accent' : 'text-poker-light'}>{action}</span>
                      <span className="font-black text-white">{(freq * 100).toFixed(1)}%</span>
                    </div>
                    {isEditing ? (
                      <input type="range" min="0" max="1" step="0.01" value={freq} onChange={(e) => handleFrequencyChange(action, parseFloat(e.target.value))} className="w-full h-1 rounded-full appearance-none cursor-pointer bg-poker-gray accent-poker-accent"/>
                    ) : (
                      <div className="h-1 w-full bg-poker-darkgray rounded-full overflow-hidden">
                        <div 
                          className="h-full rounded-full"
                          style={{ width: `${(freq || 0) * 100}%`, backgroundColor: action === 'raise' ? COLORS.blue : action === 'call' ? COLORS.green : COLORS.gray }}
                        />
                      </div>
                    )}
                  </div>
                ))}
              </div>
            </div>
          ) : (
            <div className="p-8 text-center bg-poker-gray rounded-lg">
              <Maximize2 className="w-6 h-6 text-poker-light/40 mx-auto mb-3" />
              <p className="text-xs text-poker-light font-medium">Select a hand to view strategy</p>
            </div>
          )}
          
          <div className="grid grid-cols-2 gap-3 mt-4">
            <div className="p-3 bg-poker-gray rounded-lg">
              <p className="text-xs text-poker-light uppercase font-bold mb-1">Weighting</p>
              <p className="text-sm font-black text-white">14.2%</p>
            </div>
            <div className="p-3 bg-poker-gray rounded-lg">
              <p className="text-xs text-poker-light uppercase font-bold mb-1">EV</p>
              <p className="text-sm font-black text-poker-green">+5.24 BB</p>
            </div>
          </div>
        </div>
      </div>
      
      <div className="strategy-footer">
        <button className="strategy-settingsButton">
          <SettingsIcon className="strategy-settingsButtonIcon" />
        </button>
      </div>
    </div>
  );
};

export default StrategyMatrix;
