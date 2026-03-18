import React, { useState, useEffect } from 'react';
import { useParams } from 'react-router-dom';
import type { StrategyNode, Solution } from '../types/poker';
import HandVisualizer from './HandVisualizer';
import { apiClient } from '../api/client';
import { Trophy, Flame, ChevronRight, RefreshCw, AlertCircle, CheckCircle2 } from 'lucide-react';

const StudyView: React.FC = () => {
  const { solutionId } = useParams<{ solutionId: string }>();
  const [nodes, setNodes] = useState<StrategyNode[]>([]);
  const [solution, setSolution] = useState<Solution | null>(null);
  const [loading, setLoading] = useState(true);
  const [currentHand, setCurrentHand] = useState<StrategyNode | null>(null);
  const [feedback, setFeedback] = useState<{ type: 'correct' | 'wrong' | 'marginal', message: string } | null>(null);
  const [score, setScore] = useState({ correct: 0, total: 0 });
  const [streak, setStreak] = useState(0);

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
        console.error('Failed to fetch study data:', err);
      } finally {
        setLoading(false);
      }
    };
    fetchData();
  }, [solutionId]);

  const dealNewHand = () => {
    if (nodes.length === 0) return;
    const randomHand = nodes[Math.floor(Math.random() * nodes.length)];
    setCurrentHand(randomHand);
    setFeedback(null);
  };

  useEffect(() => {
    if (nodes.length > 0) {
      dealNewHand();
    }
  }, [nodes]);

  const handleAction = (action: string) => {
    if (!currentHand || feedback) return;

    const frequencies = currentHand.actions;
    const freq = frequencies[action.toLowerCase()] || 0;
    
    // Determine if action is correct (> 0.5), marginal (> 0.1), or wrong
    let type: 'correct' | 'wrong' | 'marginal' = 'wrong';
    let message = `Blunder. ${action} was only ${(freq * 100).toFixed(1)}% weight.`;

    if (freq > 0.5) {
      type = 'correct';
      message = `Perfect! ${action} is the standard GTO play.`;
      setScore(s => ({ ...s, correct: s.correct + 1 }));
      setStreak(s => s + 1);
    } else if (freq > 0.1) {
      type = 'marginal';
      message = `Marginal. ${action} is played ${(freq * 100).toFixed(1)}% of the time.`;
      setScore(s => ({ ...s, correct: s.correct + 0.5 })); // Partial credit
      setStreak(s => s + 1);
    } else {
      setStreak(0);
    }

    setScore(s => ({ ...s, total: s.total + 1 }));
    setFeedback({ type, message });
  };

  if (loading) {
    return (
      <div className="flex flex-col items-center justify-center h-[60vh] gap-4">
        <div className="w-12 h-12 border-4 border-indigo-500 border-t-transparent rounded-full animate-spin"></div>
        <p className="text-indigo-500 font-bold animate-pulse">Prepping Trainer Session...</p>
      </div>
    );
  }

  if (!currentHand) return null;

  return (
    <div className="max-w-4xl mx-auto space-y-8 animate-in mt-8">
      {/* HUD / Stats Bar */}
      <div className="grid grid-cols-2 md:grid-cols-4 gap-4">
        <div className="bg-card p-4 rounded-3xl border border-border shadow-md flex items-center gap-4">
          <div className="w-10 h-10 bg-indigo-500/10 rounded-full flex items-center justify-center text-indigo-500">
            <Trophy className="w-5 h-5" />
          </div>
          <div>
            <p className="text-[10px] uppercase font-bold text-muted tracking-widest">Accuracy</p>
            <p className="text-xl font-black">{score.total > 0 ? ((score.correct / score.total) * 100).toFixed(1) : 0}%</p>
          </div>
        </div>
        <div className="bg-card p-4 rounded-3xl border border-border shadow-md flex items-center gap-4">
          <div className="w-10 h-10 bg-orange-500/10 rounded-full flex items-center justify-center text-orange-500">
            <Flame className="w-5 h-5" />
          </div>
          <div>
            <p className="text-[10px] uppercase font-bold text-muted tracking-widest">Streak</p>
            <p className="text-xl font-black">{streak}</p>
          </div>
        </div>
      </div>

      <div className="bg-card p-8 md:p-12 rounded-[3.5rem] border border-border shadow-2xl relative overflow-hidden backdrop-blur-md">
        <div className="absolute top-0 right-0 w-64 h-64 bg-indigo-500/5 rounded-full -mr-32 -mt-32 blur-3xl"></div>
        
        {/* Scenario Info */}
        <div className="text-center space-y-2 mb-12">
          <p className="text-[10px] uppercase font-bold text-indigo-500 tracking-[0.2em]">Current Spot</p>
          <h2 className="text-3xl font-black tracking-tight">{solution?.name || 'SB Open vs BB'}</h2>
          <div className="inline-flex items-center gap-2 px-3 py-1 bg-muted/10 rounded-full text-[10px] font-bold text-muted uppercase">
            <span>{solution?.stack_depth}bb Effective</span>
          </div>
        </div>

        {/* Hand Display */}
        <div className="py-8 transform transition-all hover:scale-105 cursor-default">
          <HandVisualizer hand={currentHand.hand} />
        </div>

        {/* Actions or Feedback */}
        <div className="mt-12">
          {!feedback ? (
            <div className="grid grid-cols-1 sm:grid-cols-3 gap-4">
              {['Fold', 'Call', 'Raise'].map((action) => (
                <button
                  key={action}
                  onClick={() => handleAction(action)}
                  className={`py-5 rounded-2xl text-base font-black uppercase tracking-widest transition-all shadow-lg active:scale-95 ${
                    action === 'Raise' ? 'bg-rose-600 hover:bg-rose-500 text-white shadow-rose-600/20' :
                    action === 'Call' ? 'bg-emerald-600 hover:bg-emerald-500 text-white shadow-emerald-600/20' :
                    'bg-slate-200 hover:bg-slate-300 text-slate-800 dark:bg-slate-800 dark:hover:bg-slate-700 dark:text-white'
                  }`}
                >
                  {action}
                </button>
              ))}
            </div>
          ) : (
            <div className={`p-8 rounded-3xl border animate-in flex flex-col items-center gap-6 ${
              feedback.type === 'correct' ? 'bg-emerald-500/10 border-emerald-500/20 text-emerald-500' :
              feedback.type === 'marginal' ? 'bg-amber-500/10 border-amber-500/20 text-amber-500' :
              'bg-rose-500/10 border-rose-500/20 text-rose-500'
            }`}>
              <div className="flex items-center gap-4">
                {feedback.type === 'correct' ? <CheckCircle2 className="w-8 h-8" /> : <AlertCircle className="w-8 h-8" />}
                <p className="text-xl font-black uppercase tracking-tight">{feedback.message}</p>
              </div>

              <div className="w-full max-w-md bg-background/50 p-4 rounded-2xl space-y-3">
                 <p className="text-[10px] font-bold uppercase tracking-widest text-muted mb-2 text-center">Solver Strategy</p>
                 {Object.entries(currentHand.actions).map(([action, freq]) => (
                   <div key={action} className="flex items-center gap-4">
                     <span className="w-12 text-[10px] font-bold uppercase text-muted">{action}</span>
                     <div className="h-1.5 flex-1 bg-background rounded-full overflow-hidden">
                        <div 
                          className={`h-full ${action === 'raise' ? 'bg-rose-500' : action === 'call' ? 'bg-emerald-500' : 'bg-slate-400'}`}
                          style={{ width: `${(freq || 0) * 100}%` }}
                        ></div>
                     </div>
                     <span className="text-[10px] font-bold">{(freq * 100).toFixed(0)}%</span>
                   </div>
                 ))}
              </div>

              <button 
                onClick={dealNewHand}
                className="flex items-center gap-2 px-8 py-3 bg-indigo-600 text-white rounded-xl text-xs font-bold hover:bg-indigo-500 transition-all shadow-lg active:scale-95"
              >
                <span>Next Hand</span>
                <ChevronRight className="w-4 h-4" />
              </button>
            </div>
          )}
        </div>
      </div>

      <div className="flex justify-center gap-4">
        <button 
          onClick={() => setScore({ correct: 0, total: 0 })}
          className="flex items-center gap-2 px-4 py-2 text-[10px] font-bold uppercase tracking-widest text-muted hover:text-rose-500 transition-colors"
        >
          <RefreshCw className="w-3 h-3" />
          <span>Reset Session</span>
        </button>
      </div>
    </div>
  );
};

export default StudyView;
