import React from 'react';
import { RotateCcw } from 'lucide-react';

interface BoardSelectorProps {
  board?: string[]; // e.g. ['6h', '6c', 'Ts']
  onReset?: () => void;
}

const BoardSelector: React.FC<BoardSelectorProps> = ({ board = ['6h', '6c', 'Ts'], onReset }) => {
  const getSuitColor = (suit: string) => {
    switch (suit) {
      case 'h': return 'text-rose-500';
      case 'd': return 'text-blue-500';
      case 'c': return 'text-emerald-500';
      case 's': return 'text-white';
      default: return 'text-muted';
    }
  };

  const getSuitSymbol = (suit: string) => {
    switch (suit) {
      case 'h': return '♥';
      case 'd': return '♦';
      case 'c': return '♣';
      case 's': return '♠';
      default: return '';
    }
  };

  return (
    <div className="flex items-center gap-4">
      <div className="flex items-center gap-1 bg-black/40 p-2 rounded-xl border border-white/5 shadow-inner">
        {board.map((card, idx) => {
          const rank = card.slice(0, -1);
          const suit = card.slice(-1);
          return (
            <div 
              key={idx}
              className="w-12 h-16 bg-zinc-900 border border-white/10 rounded-lg flex flex-col items-center justify-center relative shadow-lg group hover:scale-105 transition-transform cursor-pointer"
            >
              <span className="text-sm font-black text-white">{rank}</span>
              <span className={`text-lg leading-none ${getSuitColor(suit)}`}>
                {getSuitSymbol(suit)}
              </span>
            </div>
          );
        })}
      </div>
      
      <button 
        onClick={onReset}
        className="px-4 py-2 bg-zinc-800 hover:bg-zinc-700 text-[10px] font-black uppercase tracking-widest text-muted hover:text-white rounded-xl border border-white/5 transition-all flex items-center gap-2"
      >
        <RotateCcw className="w-3 h-3" />
        <span>Reset</span>
      </button>
    </div>
  );
};

export default BoardSelector;
