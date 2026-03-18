import React from 'react';
import StrategyMatrix from './StrategyMatrix';
import EquityChart from './EquityChart';
import type { StrategyNode } from '../types/poker';

interface DashboardViewProps {
  nodes: StrategyNode[];
  onHandSelect: (hand: string) => void;
}

const DashboardView: React.FC<DashboardViewProps> = ({ nodes, onHandSelect }) => {
  return (
    <div className="space-y-8 animate-in">
      <div className="grid grid-cols-1 lg:grid-cols-12 gap-8">
        <div className="lg:col-span-8">
          <StrategyMatrix nodes={nodes} onHandSelect={onHandSelect} />
        </div>
        
        <div className="lg:col-span-4 space-y-6">
          <div className="bg-card p-6 rounded-2xl border border-border shadow-xl h-[320px]">
            <EquityChart />
          </div>

          <div className="bg-card p-6 rounded-2xl border border-border shadow-xl">
            <h3 className="text-sm font-bold uppercase tracking-widest text-muted mb-4">Spot Details</h3>
            <div className="space-y-4">
              <div className="flex justify-between items-center py-2 border-b border-border/50">
                <span className="text-xs text-muted">Scenario</span>
                <span className="text-xs font-semibold">SB Open vs BB</span>
              </div>
              <div className="flex justify-between items-center py-2 border-b border-border/50">
                <span className="text-xs text-muted">Stack Depth</span>
                <span className="text-xs font-semibold">100bb</span>
              </div>
              <div className="flex justify-between items-center py-2">
                <span className="text-xs text-muted">Rake</span>
                <span className="text-xs font-semibold">5% (CAP 3bb)</span>
              </div>
            </div>
            <button className="w-full mt-6 py-3 bg-indigo-600 hover:bg-indigo-500 text-white rounded-xl text-xs font-bold transition-all shadow-lg shadow-indigo-600/20 active:scale-95">
              Change Scenario
            </button>
          </div>

          <div className="bg-gradient-to-br from-indigo-600 to-violet-700 p-6 rounded-2xl text-white shadow-xl">
            <h3 className="text-sm font-bold uppercase tracking-widest opacity-80 mb-2">Pro Tip</h3>
            <p className="text-xs leading-relaxed opacity-90">
              When playing from the SB, you should maintain a polar range with frequent small raises to pressure the BB.
            </p>
          </div>
        </div>
      </div>
    </div>
  );
};

export default DashboardView;
