import React from 'react';

interface BoardSelectorProps {
  board?: string[]; // e.g. ['Kh', 'Qd', 'Ts']
  onReset?: () => void;
  onCardToggle?: (card: string) => void;
}

const BoardSelector: React.FC<BoardSelectorProps> = ({ board = [], onCardToggle }) => {
  const suits = [
    { id: 'h', symbol: '♥', color: '#B80F0A', bgClass: 'bg-[#B80F0A]' },
    { id: 'd', symbol: '♦', color: '#457B9D', bgClass: 'bg-[#457B9D]' },
    { id: 's', symbol: '♠', color: '#182628', bgClass: 'bg-[#182628]' },
    { id: 'c', symbol: '♣', color: '#327A00', bgClass: 'bg-[#327A00]' },
  ];
  
  const ranks = ['A', 'K', 'Q', 'J', 'T', '9', '8', '7', '6', '5', '4', '3', '2'];

  return (
    <div className="flex flex-col bg-[#2d393b] p-1.5 rounded-[5px] w-full gap-[3px]">
      {suits.map((suit) => (
        <div key={suit.id} className="flex w-full gap-[3px]">
          {ranks.map((rank) => {
            const card = `${rank}${suit.id}`;
            const isSelected = board.includes(card);
            
            return (
              <button
                key={card}
                onClick={() => onCardToggle && onCardToggle(card)}
                className={`
                  flex-1 flex items-center justify-center rounded-[2px] h-[32px] text-[15px] text-white font-bold transition-all cursor-pointer border-none
                  ${suit.bgClass}
                  ${isSelected ? 'brightness-150 ring-2 ring-white z-10' : 'hover:brightness-110'}
                `}
              >
                <span className="mr-0.5 drop-shadow-md">{rank}</span>
                <span className="text-[14px] drop-shadow-md">{suit.symbol}</span>
              </button>
            )
          })}
        </div>
      ))}
    </div>
  );
};

export default BoardSelector;
