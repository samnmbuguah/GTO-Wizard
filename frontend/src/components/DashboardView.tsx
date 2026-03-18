import React, { useState, useEffect } from 'react';
import { useParams } from 'react-router-dom';
import StrategyMatrix from './StrategyMatrix';
import BoardSelector from './BoardSelector';
import { apiClient } from '../api/client';
import type { StrategyNode, Solution } from '../types/poker';

const DashboardView: React.FC = () => {
  const { solutionId } = useParams<{ solutionId: string }>();
  const [nodes, setNodes] = useState<StrategyNode[]>([]);
  const [solution, setSolution] = useState<Solution | null>(null);
  const [loading, setLoading] = useState(true);
  const [activeCategory, setActiveCategory] = useState('SRP');
  const [activeDepth, setActiveDepth] = useState('100');

  useEffect(() => {
    const fetchData = async () => {
      if (!solutionId) return;
      try {
        setLoading(true);
        const [solData, nodesData] = await Promise.all([
          apiClient.get<Solution>(`/solutions/${solutionId}/`),
          apiClient.get<StrategyNode[]>('/nodes/', { solution_id: solutionId, path: 'root' })
        ]);
        setSolution(solData);
        setNodes(nodesData);
        if (solData.stack_depth) setActiveDepth(solData.stack_depth.toString());
      } catch (err) {
        console.error('Failed to fetch dashboard data:', err);
      } finally {
        setLoading(false);
      }
    };
    fetchData();
  }, [solutionId]);

  if (loading) {
    return (
      <div className="flex flex-col items-center justify-center h-[60vh] gap-4">
        <div className="w-12 h-12 border-4 border-indigo-500 border-t-transparent rounded-full animate-spin"></div>
        <p className="text-indigo-500 font-bold animate-pulse">Loading Solver Workspace...</p>
      </div>
    );
  }

  const categories = ['SRP', '3 BET', '4 BET', 'HU'];
  const depths = ['100', '150', '200'];
  const scenarios = [
    'SB vs BB', 'BTN vs BB', 'CO vs BB', 'MP vs BB', 'UTG vs BB', 'MP vs BTN', 'UTG vs BTN'
  ];

  return (
    <div className="h-full flex flex-col gap-4 animate-in">
      {/* Top Header Bar */}
      <div className="flex items-center justify-between bg-zinc-900/40 border border-white/5 p-2 rounded-2xl">
        <div className="flex items-center gap-1">
          {categories.map(cat => (
            <button
              key={cat}
              onClick={() => setActiveCategory(cat)}
              className={`px-6 py-2 rounded-xl text-[10px] font-black uppercase tracking-widest transition-all ${
                activeCategory === cat 
                  ? 'bg-zinc-800 text-white border border-white/10 shadow-lg' 
                  : 'text-muted hover:text-white'
              }`}
            >
              {cat}
            </button>
          ))}
        </div>

        <div className="flex items-center gap-4 pr-2">
          <BoardSelector onReset={() => console.log('Board Reset')} />
        </div>
      </div>

      <div className="flex flex-1 gap-4 min-h-0">
        {/* Left Sidebar Stack + Scenarios */}
        <div className="flex gap-4">
          {/* Depth Column */}
          <div className="w-12 bg-zinc-900/40 border border-white/5 rounded-2xl flex flex-col py-4 gap-4 items-center">
            {depths.map(d => (
              <button
                key={d}
                onClick={() => setActiveDepth(d)}
                className={`flex flex-col items-center gap-1 transition-all ${
                  activeDepth === d ? 'text-indigo-500' : 'text-muted hover:text-white'
                }`}
              >
                <span className="text-[10px] font-black">{d[0]}</span>
                <span className="text-[10px] font-black">{d[1]}</span>
                <span className="text-[10px] font-black">{d[2]}</span>
                {activeDepth === d && <div className="w-4 h-0.5 bg-indigo-500 mt-1 rounded-full" />}
              </button>
            ))}
          </div>

          {/* Scenario List */}
          <div className="w-48 bg-zinc-900/40 border border-white/5 rounded-2xl p-3 flex flex-col gap-2 overflow-y-auto">
            {scenarios.map(sc => (
              <button
                key={sc}
                className={`py-3 px-4 rounded-xl text-[10px] font-bold uppercase tracking-widest text-left transition-all ${
                  solution?.name.includes(sc.split(' ')[0]) && solution?.name.includes(sc.split(' ')[2])
                    ? 'bg-zinc-800 text-white border border-white/10 shadow-md'
                    : 'text-muted hover:bg-white/5'
                }`}
              >
                {sc}
              </button>
            ))}
          </div>
        </div>

        {/* Main Interaction Area */}
        <div className="flex-1 flex flex-col gap-4 min-h-0 overflow-y-auto">
          {/* Action Header Panel */}
          <div className="bg-zinc-900/40 border border-white/5 rounded-2xl overflow-hidden flex flex-col">
            <div className="bg-zinc-950/40 px-6 py-2 border-b border-white/5 flex items-center justify-between">
               <div className="flex items-center gap-6">
                 <button className="px-3 py-1 bg-zinc-800 rounded-lg text-[10px] font-black text-indigo-400 border border-white/10 uppercase">root</button>
                 <div className="flex items-center gap-2">
                   <span className="text-sm font-black text-rose-500">BB</span>
                   <span className="text-[10px] text-muted font-bold opacity-60">EV: 20.41</span>
                 </div>
               </div>
               <div className="flex items-center gap-4">
                  <div className="flex items-center gap-2">
                    <div className="w-2 h-2 rounded-full bg-emerald-500" />
                    <span className="text-[10px] font-bold text-muted uppercase">CHECK (CALL)</span>
                  </div>
                  <span className="text-[10px] font-black text-white">FREQ: 100%</span>
               </div>
            </div>
            <div className="h-1.5 w-full bg-emerald-500/80" />
          </div>

          {/* Large Strategy Matrix */}
          <div className="flex-1 bg-zinc-900/40 border border-white/5 rounded-[2.5rem] p-8 shadow-2xl relative overflow-hidden flex items-center justify-center">
             <div className="relative z-10 w-full max-w-4xl mx-auto">
               <StrategyMatrix nodes={nodes} onHandSelect={(hand) => console.log('Selected:', hand)} />
             </div>
             
             {/* Decorative radial blur for premium depth */}
             <div className="absolute top-1/2 left-1/2 -translate-x-1/2 -translate-y-1/2 w-[120%] h-[120%] bg-indigo-500/5 blur-[120px] pointer-events-none rounded-full" />
          </div>
        </div>
      </div>
    </div>
  );
};

export default DashboardView;
