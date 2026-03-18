import React, { useState, useEffect } from 'react';
import { useParams, useNavigate } from 'react-router-dom';
import StrategyMatrix from './StrategyMatrix';
import EquityChart from './EquityChart';
import { apiClient } from '../api/client';
import type { StrategyNode, Solution } from '../types/poker';

const DashboardView: React.FC = () => {
  const { solutionId } = useParams<{ solutionId: string }>();
  const navigate = useNavigate();
  const [nodes, setNodes] = useState<StrategyNode[]>([]);
  const [solution, setSolution] = useState<Solution | null>(null);
  const [loading, setLoading] = useState(true);

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
        <p className="text-indigo-500 font-bold animate-pulse">Loading Solution Data...</p>
      </div>
    );
  }
  return (
    <div className="space-y-8 animate-in">
      <div className="grid grid-cols-1 lg:grid-cols-12 gap-8">
        <div className="lg:col-span-8">
          <StrategyMatrix nodes={nodes} onHandSelect={(hand) => console.log('Selected:', hand)} />
        </div>
        
        <div className="lg:col-span-4 space-y-6">
          <div className="bg-card p-6 rounded-2xl border border-border shadow-xl h-[320px]">
            <EquityChart solutionId={solutionId} />
          </div>

          <div className="bg-card p-6 rounded-2xl border border-border shadow-xl">
            <h3 className="text-sm font-bold uppercase tracking-widest text-muted mb-4">Spot Details</h3>
            <div className="space-y-4">
              <div className="flex justify-between items-center py-2 border-b border-border/50">
                <span className="text-xs text-muted">Scenario</span>
                <span className="text-xs font-semibold">{solution?.name || 'Loading...'}</span>
              </div>
              <div className="flex justify-between items-center py-2 border-b border-border/50">
                <span className="text-xs text-muted">Stack Depth</span>
                <span className="text-xs font-semibold">{solution?.stack_depth}bb</span>
              </div>
              <div className="flex justify-between items-center py-2">
                <span className="text-xs text-muted">Rake</span>
                <span className="text-xs font-semibold">{((solution?.rake || 0) * 100).toFixed(1)}%</span>
              </div>
            </div>
            {localStorage.getItem('gto_user') === 'admin' ? (
              <div className="w-full mt-6 py-3 bg-emerald-500/10 text-emerald-500 rounded-xl text-xs font-bold text-center border border-emerald-500/20">
                Premium Access
              </div>
            ) : (
              <button 
                onClick={() => navigate('/library')}
                className="w-full mt-6 py-3 bg-indigo-600 hover:bg-indigo-500 text-white rounded-xl text-xs font-bold transition-all shadow-lg shadow-indigo-600/20 active:scale-95"
              >
                Change Scenario
              </button>
            )}
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
