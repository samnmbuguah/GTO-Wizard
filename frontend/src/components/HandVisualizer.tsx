import React from 'react';

interface CardProps {
  rank: string;
  suit: string;
}

const Card: React.FC<CardProps> = ({ rank, suit }) => {
  const isRed = suit === 'h' || suit === 'd';
  const suitIcon = {
    'h': '♥',
    'd': '♦',
    's': '♠',
    'c': '♣'
  }[suit] || suit;

  return (
    <div className={`w-16 h-24 md:w-20 md:h-28 bg-white border-2 border-slate-200 rounded-xl shadow-lg flex flex-col items-center justify-between p-2 md:p-3 transition-transform hover:scale-105 select-none ${isRed ? 'text-red-600' : 'text-slate-900'}`}>
      <span className="text-xl md:text-2xl font-black self-start">{rank}</span>
      <span className="text-3xl md:text-4xl">{suitIcon}</span>
      <span className="text-xl md:text-2xl font-black self-end rotate-180">{rank}</span>
    </div>
  );
};

interface HandVisualizerProps {
  hand: string; // 'AA', 'AKs', 'AhKs'
}

const HandVisualizer: React.FC<HandVisualizerProps> = ({ hand }) => {
  // Parsing logic for 'AhKs' or 'AKs' (simplified for 'AhKs' format)
  // For 'AKs' or 'AKo', we'll just show 'A' and 'K' with generic suits
  const parseHand = (h: string) => {
    if (h.length === 4) { // 'AhKs'
       return [
         { rank: h[0], suit: h[1] },
         { rank: h[2], suit: h[3] }
       ];
    }
    // Fallback for 'AA', 'AKs', etc.
    return [
      { rank: h[0], suit: h.endsWith('s') ? 's' : 'h' },
      { rank: h[1], suit: h.endsWith('s') ? 's' : 'c' }
    ];
  };

  const cards = parseHand(hand);

  return (
    <div className="flex gap-4 justify-center">
      {cards.map((c, i) => (
        <Card key={i} rank={c.rank} suit={c.suit} />
      ))}
    </div>
  );
};

export default HandVisualizer;
