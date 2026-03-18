import React from 'react';
import { RotateCcw } from 'lucide-react';

interface BoardSelectorProps {
  board?: string[]; // e.g. ['6h', '6c', 'Ts']
  onReset?: () => void;
  onCardToggle?: (card: string) => void;
}

const BoardSelector: React.FC<BoardSelectorProps> = ({ board = [], onReset, onCardToggle }) => {
  const suits = [
    { id: 'h', symbol: '♥', color: 'text-poker-red', bg: 'bg-poker-red/20' },
    { id: 'd', symbol: '♦', color: 'text-poker-red', bg: 'bg-poker-red/20' },
    { id: 's', symbol: '♠', color: 'text-poker-light', bg: 'bg-poker-green/20' },
    { id: 'c', symbol: '♣', color: 'text-poker-light', bg: 'bg-poker-green/20' },
  ];
  
  const ranks = ['A', 'K', 'Q', 'J', 'T', '9', '8', '7', '6', '5', '4', '3', '2'];

  return (
    <div className="space-y-4">
      {/* Selected Cards Display */}
      <div className="flex items-center justify-between">
        <div className="flex items-center gap-2">
          <h3 className="text-xs font-black uppercase tracking-wider text-poker-light">Board Selection</h3>
          <div className="flex gap-1">
            {board.map((card) => {
              const s = card.slice(-1);
              const r = card.slice(0, -1);
              const suitObj = suits.find(obj => obj.id === s);
              return (
                <div key={card} className="px-2 py-1 bg-poker-gray border border-poker-gray rounded flex items-center gap-1.5 min-w-[32px] justify-center">
                  <span className="text-xs font-bold text-white">{r}</span>
                  <span className={`text-xs ${suitObj?.color}`}>{suitObj?.symbol}</span>
                </div>
              );
            })}
          </div>
        </div>
        <button 
          onClick={onReset}
          className="p-2 hover:bg-poker-gray text-poker-light hover:text-white rounded-lg transition-all"
          title="Clear Board"
        >
          <RotateCcw className="w-4 h-4" />
        </button>
      </div>

      {/* Card Grid */}
      <div className="grid grid-cols-13 gap-px bg-poker-gray p-2 rounded">
        {suits.map((suit) => (
          ranks.map((rank) => {
            const card = `${rank}${suit.id}`;
            const isSelected = board.includes(card);
            
            return (
              <button
                key={card}
                onClick={() => onCardToggle && onCardToggle(card)}
                className={`
                  aspect-square flex flex-col items-center justify-center transition-all duration-150 text-xs font-black
                  ${isSelected 
                    ? `bg-poker-accent text-white scale-105 z-10` 
                    : suit.id === 'h' || suit.id === 'd'
                    ? `bg-poker-red/30 text-poker-red hover:bg-poker-red/50`
                    : `bg-poker-green/30 text-poker-light hover:bg-poker-green/50`
                  }
                `}
              >
                <span className="text-xs font-bold leading-none">{rank}</span>
                <span className="text-lg leading-none mt-0.5">{suit.symbol}</span>
              </button>
            )
          })
        ))}
      </div>
    </div>
  );
};

export default BoardSelector;
