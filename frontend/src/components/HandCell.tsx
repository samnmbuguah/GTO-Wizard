import React from 'react';
import type { ActionFrequencies } from '../types/poker';

interface HandCellProps {
  hand: string;
  strategy?: ActionFrequencies;
  isSelected?: boolean;
  onClick?: () => void;
}

const HandCell: React.FC<HandCellProps> = ({ hand, strategy, isSelected, onClick }) => {
  // Simple action mapping for colors (Red = Bet, Green = Check/Fold)
  // In a real app, this would be dynamic based on the action names
  const renderBackground = () => {
    if (!strategy) return <div className="w-full h-full bg-slate-800" />;
    
    // Calculate cumulative widths for the gradient
    let cumulative = 0;
    const gradientParts: string[] = [];
    const colors: Record<string, string> = {
      'fold': '#475569', // Gray
      'check': '#10b981', // Green
      'call': '#10b981', // Green
      'bet': '#f43f5e',   // Red
      'raise': '#f43f5e', // Red
    };

    const sortedActions = Object.entries(strategy).sort();
    
    for (const [action, freq] of sortedActions) {
      const color = colors[action.toLowerCase()] || '#c084fc';
      const start = cumulative * 100;
      cumulative += freq;
      const end = cumulative * 100;
      gradientParts.push(`${color} ${start}% ${end}%`);
    }

    return (
      <div 
        className="w-full h-full flex items-center justify-center text-[10px] font-bold text-white shadow-inner"
        style={{ background: `linear-gradient(to right, ${gradientParts.join(', ')})` }}
      >
        {hand}
      </div>
    );
  };

  return (
    <div 
      onClick={onClick}
      className={`relative aspect-square cursor-pointer border-[0.5px] border-black/20 hover:scale-110 hover:z-10 transition-transform duration-200 ${isSelected ? 'ring-2 ring-white z-20' : ''}`}
    >
      {renderBackground()}
    </div>
  );
};

export default React.memo(HandCell);
