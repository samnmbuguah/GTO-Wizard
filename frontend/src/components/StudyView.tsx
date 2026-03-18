import React, { useState, useEffect } from 'react';
import { useParams } from 'react-router-dom';
import type { StrategyNode, Solution } from '../types/poker';
import HandVisualizer from './HandVisualizer';
import StrategyMatrix from './StrategyMatrix';
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
  const [sessionId, setSessionId] = useState<number | null>(null);

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
        
        // Create initial session
        const session = await apiClient.post<any>('/sessions/', {
          solution: solutionId,
          correct_hands: 0,
          total_hands: 0,
          streak: 0
        });
        setSessionId(session.id);
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

  const [showMatrix, setShowMatrix] = useState(false);

  const syncSession = async (newScore: { correct: number, total: number }, newStreak: number) => {
    if (!sessionId) return;
    try {
      await apiClient.patch(`/sessions/${sessionId}/`, {
        correct_hands: newScore.correct,
        total_hands: newScore.total,
        streak: newStreak
      });
    } catch (err) {
      console.error('Failed to sync session:', err);
    }
  };

  useEffect(() => {
    if (score.total > 0) {
      syncSession(score, streak);
    }
  }, [score, streak]);

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
            <p className="text-xl font-black text-foreground">{score.total > 0 ? ((score.correct / score.total) * 100).toFixed(1) : 0}%</p>
          </div>
        </div>
        <div className="bg-card p-4 rounded-3xl border border-border shadow-md flex items-center gap-4">
          <div className="w-10 h-10 bg-orange-500/10 rounded-full flex items-center justify-center text-orange-500">
            <Flame className="w-5 h-5" />
          </div>
          <div>
            <p className="text-[10px] uppercase font-bold text-muted tracking-widest">Streak</p>
            <p className="text-xl font-black text-foreground">{streak}</p>
          </div>
        </div>
      </div>

      <div className="bg-card p-8 md:p-12 rounded-[3.5rem] border border-border shadow-2xl relative overflow-hidden">
        <div className="absolute top-0 right-0 w-64 h-64 bg-indigo-500/5 rounded-full -mr-32 -mt-32 blur-3xl"></div>
        
        {/* Scenario Info */}
        <div className="flex items-center justify-between mb-12">
          <div className="space-y-1">
            <p className="text-[10px] uppercase font-bold text-indigo-500 tracking-[0.2em]">Trainer Mode</p>
            <h2 className="text-2xl font-black text-foreground tracking-tight">{solution?.name || 'SB Open vs BB'}</h2>
          </div>
          <button 
            onClick={() => setShowMatrix(!showMatrix)}
            className="px-4 py-2 bg-zinc-900 border border-border rounded-xl text-[10px] font-bold text-muted hover:text-foreground transition-all uppercase tracking-widest flex items-center gap-2"
          >
            <AlertCircle className="w-4 h-4" />
            <span>{showMatrix ? 'Hide Range' : 'Review Range'}</span>
          </button>
        </div>

        {showMatrix ? (
          <div className="animate-in fade-in slide-in-from-bottom-4 duration-500 max-h-[600px] overflow-y-auto">
            <StrategyMatrix nodes={nodes} />
          </div>
        ) : (
          <>
            {/* Hand Display */}
            <div className="py-8 transform transition-all hover:scale-105 cursor-default relative">
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
                      className={`py-6 rounded-[2rem] text-sm font-black uppercase tracking-widest transition-all shadow-xl active:scale-95 group ${
                        action === 'Raise' ? 'bg-rose-600 hover:bg-rose-500 text-white shadow-rose-600/20' :
                        action === 'Call' ? 'bg-emerald-600 hover:bg-emerald-500 text-white shadow-emerald-600/20' :
                        'bg-zinc-900 hover:bg-zinc-800 text-white border border-border'
                      }`}
                    >
                      {action}
                    </button>
                  ))}
                </div>
              ) : (
                <div className={`p-8 rounded-[2.5rem] border animate-in flex flex-col items-center gap-8 ${
                  feedback.type === 'correct' ? 'bg-emerald-500/5 border-emerald-500/20' :
                  feedback.type === 'marginal' ? 'bg-amber-500/5 border-amber-500/20' :
                  'bg-rose-500/5 border-rose-500/20'
                }`}>
                  <div className="text-center space-y-2">
                    <div className={`w-12 h-12 mx-auto rounded-full flex items-center justify-center mb-4 ${
                      feedback.type === 'correct' ? 'bg-emerald-500 text-white' :
                      feedback.type === 'marginal' ? 'bg-amber-500 text-white' :
                      'bg-rose-500 text-white'
                    }`}>
                      {feedback.type === 'correct' ? <CheckCircle2 className="w-6 h-6" /> : <AlertCircle className="w-6 h-6" />}
                    </div>
                    <p className={`text-xl font-black uppercase tracking-tight ${
                       feedback.type === 'correct' ? 'text-emerald-500' :
                       feedback.type === 'marginal' ? 'text-amber-500' :
                       'text-rose-500'
                    }`}>{feedback.message}</p>
                  </div>

                  <div className="w-full max-w-sm bg-card p-6 rounded-3xl border border-border shadow-lg space-y-4">
                     <p className="text-[10px] font-bold uppercase tracking-widest text-muted text-center flex items-center justify-center gap-2">
                        <RefreshCw className="w-3 h-3 animate-spin" />
                        GTO Strategy Breakdown
                     </p>
                     {Object.entries(currentHand.actions).map(([action, freq]) => (
                       <div key={action} className="space-y-1">
                         <div className="flex justify-between items-center px-1">
                            <span className="text-[10px] font-bold uppercase text-muted">{action}</span>
                            <span className="text-xs font-black text-foreground">{(freq * 100).toFixed(0)}%</span>
                         </div>
                         <div className="h-2 w-full bg-zinc-900 rounded-full overflow-hidden border border-border/50">
                            <div 
                              className={`h-full transition-all duration-1000 ${
                                action === 'raise' ? 'bg-rose-500' : 
                                action === 'call' ? 'bg-emerald-500' : 
                                'bg-zinc-600'
                              }`}
                              style={{ width: `${(freq || 0) * 100}%` }}
                            ></div>
                         </div>
                       </div>
                     ))}
                  </div>

                  <button 
                    onClick={dealNewHand}
                    className="group flex items-center gap-3 px-10 py-4 bg-indigo-600 text-white rounded-2xl text-sm font-black uppercase tracking-widest hover:bg-indigo-500 transition-all shadow-xl shadow-indigo-600/20 active:scale-95"
                  >
                    <span>Next Hand</span>
                    <ChevronRight className="w-5 h-5 group-hover:translate-x-1 transition-transform" />
                  </button>
                </div>
              )}
            </div>
          </>
        )}
      </div>

      <div className="flex justify-center gap-4">
        <button 
          onClick={async () => {
             if (window.confirm('Are you sure you want to reset your session score?')) {
                setScore({ correct: 0, total: 0 });
                setStreak(0);
                if (solutionId) {
                   const session = await apiClient.post<any>('/sessions/', {
                     solution: solutionId,
                     correct_hands: 0,
                     total_hands: 0,
                     streak: 0
                   });
                   setSessionId(session.id);
                }
             }
          }}
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
