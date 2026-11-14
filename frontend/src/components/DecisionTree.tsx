import React from 'react';
import { GitCommit, ChevronRight } from 'lucide-react';

interface DecisionTreeProps {
  path: string[];
  actions: string[];
  frequencies?: Record<string, number>;
  actingPlayer?: string;
  streetClosed?: boolean;
  terminalFold?: boolean;
  nextStreetPot?: number;
  nextStreetLabel?: string;
  onActionClick: (action: string) => void;
  onBreadcrumbClick: (index: number) => void;
}

const getActionBadgeColor = (action: string) => {
  const lower = action.toLowerCase();
  if (lower.includes('fold')) return 'bg-[#457B9D] hover:bg-[#34607c] text-white border-blue-400/30';
  if (lower.includes('call') || lower.includes('check')) return 'bg-[#327A00] hover:bg-[#265e00] text-white border-green-500/30';
  if (lower.includes('raise') || lower.includes('bet') || lower.includes('all-in')) return 'bg-[#B80F0A] hover:bg-[#8f0c08] text-white border-red-500/30';
  return 'bg-[#2d393b] hover:bg-[#465f61] text-[#ccdbdc] border-slate-600';
};

const DecisionTree: React.FC<DecisionTreeProps> = ({ 
  path, 
  actions, 
  frequencies, 
  actingPlayer,
  streetClosed,
  terminalFold,
  nextStreetPot,
  nextStreetLabel,
  onActionClick, 
  onBreadcrumbClick 
}) => {
  return (
    <div className="flex flex-col sm:flex-row items-center justify-between gap-3 px-3 py-2 bg-[#182628] rounded-[5px] border border-[#2d393b] shadow-md w-full">
      {/* Breadcrumb Tree Path */}
      <div className="flex items-center gap-1.5 text-xs text-[#a1b4d9] font-mono overflow-x-auto w-full sm:w-auto">
        <GitCommit className="w-3.5 h-3.5 text-[#7aa6da] flex-shrink-0" />
        {path.map((item, index) => {
          const isLast = index === path.length - 1;
          return (
            <React.Fragment key={index}>
              <button 
                onClick={() => onBreadcrumbClick(index)}
                className={`transition-colors font-bold uppercase tracking-tight text-[11px] px-1.5 py-0.5 rounded whitespace-nowrap
                  ${isLast ? 'text-white bg-[#0d1f1f] border border-[#7aa6da]/30' : 'text-[#7aa6da] hover:text-white hover:bg-[#2d393b]'}`}
              >
                {item}
              </button>
              {!isLast && <ChevronRight className="w-3 h-3 text-[#2d393b] flex-shrink-0" />}
            </React.Fragment>
          );
        })}
      </div>
      
      {/* Action Buttons with Live GTO Frequencies */}
      <div className="flex flex-wrap items-center gap-1.5">
        {actingPlayer && !streetClosed && !terminalFold && (
          <span className="text-[10px] font-black uppercase px-1.5 py-0.5 rounded bg-[#0d1f1f] text-[#7aa6da] border border-[#7aa6da]/20 mr-1">
            {actingPlayer} to act
          </span>
        )}
        {streetClosed && (
          <span className="text-[10.5px] font-bold text-[#64ffda] bg-[#64ffda]/10 px-2 py-1 rounded border border-[#64ffda]/30">
            Street Closed (Pot {nextStreetPot?.toFixed(1)}bb)
            {nextStreetLabel ? ` — Pick ${nextStreetLabel} card above` : ' — Showdown'}
          </span>
        )}
        {terminalFold && (
          <span className="text-[10.5px] font-bold text-amber-400 bg-amber-500/10 px-2 py-1 rounded border border-amber-500/30">
            Hand Ended by Fold
          </span>
        )}
        {!streetClosed && !terminalFold && actions.map(action => {
          // Prefer exact key match, then prefix match
          let freqLabel = '';
          if (frequencies) {
            const exactKey = Object.keys(frequencies).find(k => k.toLowerCase() === action.toLowerCase());
            const prefixKey = Object.keys(frequencies).find(k => k.toLowerCase() === action.toLowerCase().split(' ')[0]);
            const resolvedKey = exactKey ?? prefixKey;
            if (resolvedKey !== undefined && frequencies[resolvedKey] !== undefined) {
              freqLabel = ` ${(frequencies[resolvedKey] * 100).toFixed(1)}%`;
            }
          }

          return (
            <button
              key={action}
              onClick={() => onActionClick(action)}
              className={`px-3 py-1 rounded-[3px] transition-all active:scale-95 border text-[11px] font-black uppercase tracking-wider shadow-sm flex items-center gap-1 ${getActionBadgeColor(action)}`}
            >
              <span>{action}</span>
              {freqLabel && <span className="opacity-90 font-mono text-[10px] ml-1 bg-black/20 px-1 rounded">{freqLabel}</span>}
            </button>
          );
        })}
      </div>
    </div>
  );
};

export default DecisionTree;
