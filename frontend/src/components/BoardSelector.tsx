import React from 'react';

interface BoardSelectorProps {
  board?: string[]; // e.g. ['Kh', 'Qd', 'Ts']
  onReset?: () => void;
  onCardToggle?: (card: string) => void;
}

const BoardSelector: React.FC<BoardSelectorProps> = ({ board = [], onCardToggle }) => {
  const suits = [
    { id: 'h', symbol: '♥', bgClass: 'bg-[rgba(184,15,10,0.6)] hover:bg-[rgb(184,15,10)] border-[rgba(184,15,10,0.6)]' },
    { id: 'd', symbol: '♦', bgClass: 'bg-[rgba(0,50,73,0.6)] hover:bg-[#003249] border-[#003249]' },
    { id: 'c', symbol: '♣', bgClass: 'bg-[#204f00] hover:bg-[#204f00] border-[#204f00]' },
    { id: 's', symbol: '♠', bgClass: 'bg-[#070b0b] hover:bg-[#070b0b] border-[#070b0b]' },
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
                  flex-1 flex items-center justify-center rounded-[3px] h-[30px] text-[16px] text-[#ccdbdc] font-sans font-[500] transition-colors cursor-pointer border-none
                  ${suit.bgClass}
                  ${isSelected ? 'opacity-50 ring-1 ring-white' : ''}
                `}
              >
                <span className="mr-0.5">{rank}</span>
                <span className="text-[12px]">{suit.symbol}</span>
              </button>
            )
          })}
        </div>
      ))}
    </div>
  );
};

export default BoardSelector;
