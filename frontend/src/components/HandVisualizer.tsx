import React from 'react';
import CardBadge from './common/CardBadge';

interface HandVisualizerProps {
  hand: string; // 'AA', 'AKs', 'AhKs'
}

const HandVisualizer: React.FC<HandVisualizerProps> = ({ hand }) => {
  // Parsing logic for 'AhKs' or 'AKs' (simplified for 'AhKs' format)
  // For 'AKs' or 'AKo', we'll show 'A' and 'K' with appropriate suits
  const parseHand = (h: string) => {
    if (h.length === 4) { // 'AhKs'
      return [
        { rank: h[0], suit: h[1] },
        { rank: h[2], suit: h[3] },
      ];
    }
    // Fallback for 'AA', 'AKs', etc.
    return [
      { rank: h[0], suit: h.endsWith('s') ? 's' : 'h' },
      { rank: h[1], suit: h.endsWith('s') ? 's' : 'c' },
    ];
  };

  const cards = parseHand(hand);

  return (
    <div className="flex gap-4 justify-center">
      {cards.map((c, i) => (
        <CardBadge key={i} rank={c.rank} suit={c.suit} size="lg" />
      ))}
    </div>
  );
};

export default HandVisualizer;
