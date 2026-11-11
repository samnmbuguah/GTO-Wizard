import React from 'react';

export interface CardBadgeProps {
  card?: string; // e.g. 'Ah', 'Kd', 'Ts', '2c'
  rank?: string;
  suit?: string;
  size?: 'xs' | 'sm' | 'md' | 'lg';
  selected?: boolean;
  onClick?: () => void;
  className?: string;
  'data-testid'?: string;
}

export const SUIT_MAP: Record<string, { symbol: string; bg: string; name: string }> = {
  h: { symbol: '♥', bg: 'bg-[#B80F0A]', name: 'Hearts' },
  d: { symbol: '♦', bg: 'bg-[#457B9D]', name: 'Diamonds' },
  s: { symbol: '♠', bg: 'bg-[#182628]', name: 'Spades' },
  c: { symbol: '♣', bg: 'bg-[#327A00]', name: 'Clubs' },
};

export const CardBadge: React.FC<CardBadgeProps> = ({
  card,
  rank: propRank,
  suit: propSuit,
  size = 'sm',
  selected = false,
  onClick,
  className = '',
  'data-testid': testId,
}) => {
  let rank = propRank || '';
  let suit = propSuit || '';

  if (card && card.length >= 2) {
    rank = card.slice(0, -1).toUpperCase();
    suit = card.slice(-1).toLowerCase();
  }

  const suitConfig = SUIT_MAP[suit] || { symbol: suit, bg: 'bg-zinc-800', name: 'Unknown' };

  if (size === 'lg') {
    return (
      <div
        data-testid={testId}
        onClick={onClick}
        className={`w-16 h-24 md:w-20 md:h-28 ${suitConfig.bg} text-white border-2 border-white/20 rounded-xl shadow-xl flex flex-col items-center justify-between p-2 md:p-3 transition-transform hover:scale-105 select-none ${
          selected ? 'ring-4 ring-[#64ffda] brightness-125' : ''
        } ${onClick ? 'cursor-pointer' : ''} ${className}`}
      >
        <span className="text-xl md:text-2xl font-black self-start drop-shadow-md">{rank}</span>
        <span className="text-3xl md:text-4xl drop-shadow-lg">{suitConfig.symbol}</span>
        <span className="text-xl md:text-2xl font-black self-end rotate-180 drop-shadow-md">{rank}</span>
      </div>
    );
  }

  const sizeClasses = {
    xs: 'h-[18px] min-w-[18px] px-1 text-[9.5px] rounded-[2px]',
    sm: 'h-[24px] min-w-[24px] px-1.5 text-[11px] rounded-[3px]',
    md: 'h-[32px] min-w-[32px] px-2 text-[14px] rounded-[4px]',
  }[size];

  if (onClick) {
    return (
      <button
        type="button"
        data-testid={testId}
        onClick={onClick}
        className={`inline-flex items-center justify-center font-black text-white ${suitConfig.bg} ${sizeClasses} shadow-sm border border-white/10 transition-all select-none cursor-pointer hover:brightness-110 active:scale-95 ${
          selected ? 'brightness-125 ring-2 ring-white ring-offset-1 ring-offset-[#00140f] z-10' : ''
        } ${className}`}
      >
        <span className="mr-0.5 tracking-tight drop-shadow-sm">{rank}</span>
        <span className="text-[1.05em] leading-none drop-shadow-sm">{suitConfig.symbol}</span>
      </button>
    );
  }

  return (
    <span
      data-testid={testId}
      className={`inline-flex items-center justify-center font-black text-white ${suitConfig.bg} ${sizeClasses} shadow-sm border border-white/10 select-none ${
        selected ? 'brightness-125 ring-2 ring-white ring-offset-1 ring-offset-[#00140f] z-10' : ''
      } ${className}`}
    >
      <span className="mr-0.5 tracking-tight drop-shadow-sm">{rank}</span>
      <span className="text-[1.05em] leading-none drop-shadow-sm">{suitConfig.symbol}</span>
    </span>
  );
};

export default CardBadge;
