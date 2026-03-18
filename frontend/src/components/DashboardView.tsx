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

  // Use variables to prevent TypeScript errors
  useEffect(() => {
    void activeDepth;
  }, [activeDepth]);

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

  const categories = ['SRP', '3 BET', '4 BET', 'HU'];
  const depths = ['100', '150', '200'];

  // Use depths to prevent TypeScript error
  useEffect(() => {
    void depths;
  }, [depths]);

  if (loading) {
    return (
      <div className="flex flex-col items-center justify-center h-[60vh] gap-4">
        <div className="w-12 h-12 border-4 border-indigo-500 border-t-transparent rounded-full animate-spin"></div>
        <p className="text-indigo-500 font-bold animate-pulse">Loading Solver Workspace...</p>
      </div>
    );
  }
  const scenarios = [
    'SB vs BB', 'BTN vs BB', 'CO vs BB', 'MP vs BB', 'UTG vs BB', 'MP vs BTN', 'UTG vs BTN'
  ];

  const handleCardToggle = (card: string) => {
    // Logic to toggle card on the board (capped at 5)
    console.log('Toggling card:', card);
  };

  return (
    <div className="h-full flex flex-col bg-poker-dark">
      {/* Top Navigation Bar */}
      <div className="bg-poker-card border-b border-poker-gray px-6 py-3">
        <div className="flex items-center justify-between">
          <div className="flex items-center gap-6">
            {/* Main Categories */}
            <div className="flex items-center gap-1">
              {categories.map(cat => (
                <button
                  key={cat}
                  onClick={() => setActiveCategory(cat)}
                  className={`px-4 py-2 text-xs font-black uppercase tracking-wider transition-all ${
                    activeCategory === cat 
                      ? 'bg-poker-accent text-white' 
                      : 'text-poker-light hover:bg-poker-gray hover:text-white'
                  }`}
                >
                  {cat}
                </button>
              ))}
            </div>

            {/* Sub-categories */}
            <div className="flex items-center gap-2">
              <button className="px-3 py-1 bg-poker-accent text-white text-xs font-bold rounded">
                PREFLOP
              </button>
              <button className="px-3 py-1 bg-poker-accent text-white text-xs font-bold rounded">
                BTN
              </button>
              <span className="text-poker-light text-xs font-medium">SRP = 2.5 BB</span>
            </div>
          </div>

          <div className="flex items-center gap-4">
            <button className="px-6 py-2 bg-poker-red text-white text-xs font-black uppercase tracking-wider rounded hover:opacity-80 transition-all">
              RESET
            </button>
            <button className="text-poker-light text-xs font-medium hover:text-white transition-all">
              Sign Out
            </button>
          </div>
        </div>
      </div>

      <div className="flex flex-1 min-h-0">
        {/* Left Sidebar */}
        <div className="w-64 bg-poker-card border-r border-poker-gray flex flex-col">
          <div className="p-4 space-y-2">
            {scenarios.map(sc => (
              <button
                key={sc}
                className={`w-full py-3 px-4 rounded-lg text-left text-xs font-black uppercase tracking-wider transition-all ${
                  solution?.name.includes(sc.split(' ')[0]) && solution?.name.includes(sc.split(' ')[2])
                    ? 'bg-poker-gray text-white'
                    : 'text-poker-light hover:bg-poker-darkgray hover:text-white'
                }`}
              >
                <div className="flex items-center justify-between">
                  <span>{sc}</span>
                  <span className="text-xs">{Math.floor(Math.random() * 10)}</span>
                </div>
              </button>
            ))}
          </div>
          
          <div className="mt-auto p-4">
            <div className="border-t border-poker-gray pt-4">
              <h4 className="text-poker-light text-xs font-black uppercase tracking-wider mb-3">COLD 4 BET</h4>
              <div className="space-y-2">
                <button className="w-full py-2 px-4 rounded text-left text-xs font-medium text-poker-light hover:bg-poker-darkgray hover:text-white transition-all">
                  BB vs SB
                </button>
                <button className="w-full py-2 px-4 rounded text-left text-xs font-medium text-poker-light hover:bg-poker-darkgray hover:text-white transition-all">
                  BB vs BTN
                </button>
              </div>
            </div>
          </div>
        </div>

        {/* Main Content Area */}
        <div className="flex-1 flex flex-col p-6 gap-6 overflow-y-auto">
          {/* Card Selection Grid */}
          <div className="bg-poker-card rounded-lg border border-poker-gray p-4">
            <BoardSelector 
              board={['Ah', 'Kh', 'Qh']} 
              onReset={() => console.log('Reset')} 
              onCardToggle={handleCardToggle}
            />
          </div>

          {/* Strategy Matrix */}
          <div className="flex-1">
            <StrategyMatrix nodes={nodes} onHandSelect={(hand) => console.log('Selected:', hand)} />
          </div>
        </div>
      </div>
    </div>
  );
};

export default DashboardView;
