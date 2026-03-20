import React, { useMemo } from 'react';
import type { StrategyNode } from '../types/poker';
import { getActionColor } from './StrategyMatrix';

interface SummaryStatsProps {
  nodes: StrategyNode[];
}

const SummaryStats: React.FC<SummaryStatsProps> = ({ nodes }) => {
  const stats = useMemo(() => {
    if (!nodes || nodes.length === 0) return null;

    const aggregateFrequencies: Record<string, number> = {};
    const aggregateEVs: Record<string, number> = {};
    const totalNodes = nodes.length;

    nodes.forEach(node => {
      if (!node.actions) return;
      Object.entries(node.actions).forEach(([action, freq]) => {
        aggregateFrequencies[action] = (aggregateFrequencies[action] || 0) + freq;
        if (node.ev) {
          aggregateEVs[action] = (aggregateEVs[action] || 0) + (node.ev * freq);
        }
      });
    });

    const results = Object.keys(aggregateFrequencies).map(action => {
      const avgFreq = aggregateFrequencies[action] / totalNodes;
      const totalFreqForEV = aggregateFrequencies[action];
      const avgEV = totalFreqForEV > 0 ? (aggregateEVs[action] || 0) / totalFreqForEV : 0;
      
      return {
        action,
        frequency: avgFreq,
        ev: avgEV
      };
    });

    return results.sort((a, b) => b.frequency - a.frequency);
  }, [nodes]);

  if (!stats) return null;

  return (
    <div className="w-full flex gap-1 h-14 mb-2">
      {stats.map((stat, i) => (
        <div 
          key={i} 
          className="flex-1 flex flex-col justify-center items-center rounded-sm transition-all border-b-4 border-black/20"
          style={{ 
            flexGrow: stat.frequency,
            backgroundColor: getActionColor(stat.action)
          }}
        >
          <div className="text-[10px] font-black text-white/90 uppercase tracking-tighter line-clamp-1">
            {stat.action} {(stat.frequency * 100).toFixed(2)}%
          </div>
          <div className="flex gap-2 mt-0.5">
            <span className="text-[9px] font-bold text-white/60">Freq: {(stat.frequency * 100).toFixed(0)}%</span>
            <span className="text-[9px] font-bold text-white/80">EV: {stat.ev.toFixed(2)}</span>
          </div>
        </div>
      ))}
    </div>
  );
};

export default SummaryStats;
