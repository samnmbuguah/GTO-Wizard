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
  const [feedback, setFeedback] = useState<{ type: 'correct' | 'wrong' | 'marginal'; message: string } | null>(null);
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
          apiClient.get<StrategyNode[]>('/nodes/', { solution_id: solutionId, path: 'root' }),
        ]);
        setSolution(solData);
        setNodes(nodesData);

        // Create initial session
        const session = await apiClient.post<any>('/sessions/', {
          solution: solutionId,
          correct_hands: 0,
          total_hands: 0,
          streak: 0,
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
      message = `Optimal! ${action} is the primary GTO play (${(freq * 100).toFixed(0)}%).`;
      setScore((s) => ({ ...s, correct: s.correct + 1 }));
      setStreak((s) => s + 1);
    } else if (freq > 0.1) {
      type = 'marginal';
      message = `Marginal. ${action} is mixed at ${(freq * 100).toFixed(1)}% frequency.`;
      setScore((s) => ({ ...s, correct: s.correct + 0.5 })); // Partial credit
      setStreak((s) => s + 1);
    } else {
      setStreak(0);
    }

    setScore((s) => ({ ...s, total: s.total + 1 }));
    setFeedback({ type, message });
  };

  const [showMatrix, setShowMatrix] = useState(false);

  const syncSession = async (newScore: { correct: number; total: number }, newStreak: number) => {
    if (!sessionId) return;
    try {
      await apiClient.patch(`/sessions/${sessionId}/`, {
        correct_hands: newScore.correct,
        total_hands: newScore.total,
        streak: newStreak,
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
      <div className="flex flex-col items-center justify-center h-[60vh] gap-3">
        <div className="w-8 h-8 border-2 border-[#7aa6da] border-t-transparent rounded-full animate-spin"></div>
        <p className="text-[#7aa6da] text-xs font-mono font-bold animate-pulse uppercase tracking-wider">
          Prepping Trainer Session...
        </p>
      </div>
    );
  }

  if (!currentHand) return null;

  return (
    <div className="min-h-full bg-[#00140f] p-6 lg:p-8 space-y-6 animate-in text-[#ccdbdc]">
      <div className="max-w-4xl mx-auto space-y-6">
        {/* HUD / Stats Bar */}
        <div className="grid grid-cols-2 md:grid-cols-4 gap-3">
          <div className="bg-[#182628] p-3.5 rounded-[6px] border border-[#2d393b] flex items-center gap-3">
            <div className="w-9 h-9 bg-[#00140f] rounded-[4px] border border-[#2d393b] flex items-center justify-center text-[#7aa6da]">
              <Trophy className="w-4 h-4" />
            </div>
            <div>
              <p className="text-[10px] uppercase font-bold text-[#8b9ea0] tracking-wider">Accuracy</p>
              <p className="text-lg font-black font-mono text-white">
                {score.total > 0 ? ((score.correct / score.total) * 100).toFixed(1) : 0}%
              </p>
            </div>
          </div>
          <div className="bg-[#182628] p-3.5 rounded-[6px] border border-[#2d393b] flex items-center gap-3">
            <div className="w-9 h-9 bg-[#00140f] rounded-[4px] border border-[#2d393b] flex items-center justify-center text-amber-400">
              <Flame className="w-4 h-4" />
            </div>
            <div>
              <p className="text-[10px] uppercase font-bold text-[#8b9ea0] tracking-wider">Streak</p>
              <p className="text-lg font-black font-mono text-white">{streak}</p>
            </div>
          </div>
          <div className="bg-[#182628] p-3.5 rounded-[6px] border border-[#2d393b] flex items-center gap-3">
            <div>
              <p className="text-[10px] uppercase font-bold text-[#8b9ea0] tracking-wider">Hands Tested</p>
              <p className="text-lg font-black font-mono text-white">{score.total}</p>
            </div>
          </div>
          <div className="bg-[#182628] p-3.5 rounded-[6px] border border-[#2d393b] flex items-center justify-end">
            <button
              onClick={() => setShowMatrix(!showMatrix)}
              className="px-3 py-1.5 bg-[#00140f] border border-[#2d393b] hover:border-[#7aa6da] rounded-[4px] text-[10px] font-bold text-[#7aa6da] hover:text-white transition-all uppercase tracking-wider flex items-center gap-1.5 cursor-pointer"
            >
              <AlertCircle className="w-3.5 h-3.5" />
              <span>{showMatrix ? 'Hide Range' : 'Review Range'}</span>
            </button>
          </div>
        </div>

        {/* Training Canvas */}
        <div className="bg-[#182628] p-6 md:p-8 rounded-[6px] border border-[#2d393b] shadow-xl relative">
          {/* Scenario Info */}
          <div className="flex items-center justify-between mb-8 border-b border-[#2d393b] pb-4">
            <div className="space-y-0.5">
              <p className="text-[10px] uppercase font-black text-[#7aa6da] tracking-wider font-mono">
                GTO Drill Trainer
              </p>
              <h2 className="text-xl font-black text-white uppercase tracking-tight">
                {solution?.name || 'SB Open vs BB'}
              </h2>
            </div>
            <span className="text-[10px] font-mono text-[#8b9ea0] bg-[#00140f] px-2.5 py-1 rounded-[3px] border border-[#2d393b]">
              Spot #{solutionId}
            </span>
          </div>

          {showMatrix ? (
            <div className="animate-in fade-in duration-300 max-h-[550px] overflow-y-auto">
              <StrategyMatrix nodes={nodes} />
            </div>
          ) : (
            <>
              {/* Hand Display */}
              <div className="py-6 flex justify-center">
                <HandVisualizer hand={currentHand.hand} />
              </div>

              {/* Actions or Feedback */}
              <div className="mt-8">
                {!feedback ? (
                  <div className="grid grid-cols-1 sm:grid-cols-3 gap-3">
                    {['Fold', 'Call', 'Raise'].map((action) => (
                      <button
                        key={action}
                        onClick={() => handleAction(action)}
                        className={`py-4 rounded-[4px] text-xs font-black uppercase tracking-wider transition-all shadow-md active:scale-95 cursor-pointer ${
                          action === 'Raise'
                            ? 'bg-[#f43f5e] hover:bg-[#e11d48] text-white shadow-[#f43f5e]/20'
                            : action === 'Call'
                            ? 'bg-[#10b981] hover:bg-[#059669] text-white shadow-[#10b981]/20'
                            : 'bg-[#00140f] hover:bg-[#1f2b2d] text-[#ccdbdc] border border-[#2d393b]'
                        }`}
                      >
                        {action}
                      </button>
                    ))}
                  </div>
                ) : (
                  <div
                    className={`p-6 rounded-[6px] border animate-in flex flex-col items-center gap-6 ${
                      feedback.type === 'correct'
                        ? 'bg-emerald-500/10 border-emerald-500/30'
                        : feedback.type === 'marginal'
                        ? 'bg-amber-500/10 border-amber-500/30'
                        : 'bg-rose-500/10 border-rose-500/30'
                    }`}
                  >
                    <div className="text-center space-y-1">
                      <div
                        className={`w-10 h-10 mx-auto rounded-full flex items-center justify-center mb-2 ${
                          feedback.type === 'correct'
                            ? 'bg-emerald-500 text-white'
                            : feedback.type === 'marginal'
                            ? 'bg-amber-500 text-white'
                            : 'bg-rose-500 text-white'
                        }`}
                      >
                        {feedback.type === 'correct' ? (
                          <CheckCircle2 className="w-5 h-5" />
                        ) : (
                          <AlertCircle className="w-5 h-5" />
                        )}
                      </div>
                      <p
                        className={`text-base font-black uppercase tracking-wide ${
                          feedback.type === 'correct'
                            ? 'text-emerald-400'
                            : feedback.type === 'marginal'
                            ? 'text-amber-400'
                            : 'text-rose-400'
                        }`}
                      >
                        {feedback.message}
                      </p>
                    </div>

                    <div className="w-full max-w-sm bg-[#00140f] p-4 rounded-[4px] border border-[#2d393b] space-y-3">
                      <p className="text-[10px] font-bold uppercase tracking-wider text-[#7aa6da] text-center flex items-center justify-center gap-2">
                        <RefreshCw className="w-3 h-3" />
                        GTO Action Frequencies
                      </p>
                      {Object.entries(currentHand.actions).map(([action, freq]) => (
                        <div key={action} className="space-y-1">
                          <div className="flex justify-between items-center px-1 font-mono">
                            <span className="text-[10px] font-bold uppercase text-[#8b9ea0]">{action}</span>
                            <span className="text-xs font-black text-white">{(freq * 100).toFixed(0)}%</span>
                          </div>
                          <div className="h-1.5 w-full bg-[#182628] rounded-full overflow-hidden border border-[#2d393b]">
                            <div
                              className={`h-full transition-all duration-700 ${
                                action === 'raise'
                                  ? 'bg-[#f43f5e]'
                                  : action === 'call'
                                  ? 'bg-[#10b981]'
                                  : 'bg-[#2d393b]'
                              }`}
                              style={{ width: `${(freq || 0) * 100}%` }}
                            ></div>
                          </div>
                        </div>
                      ))}
                    </div>

                    <button
                      onClick={dealNewHand}
                      className="flex items-center gap-2 px-6 py-2.5 bg-[#7aa6da] hover:bg-[#6894c7] text-[#00140f] rounded-[4px] text-xs font-black uppercase tracking-wider transition-all shadow-md active:scale-95 cursor-pointer"
                    >
                      <span>Next Hand</span>
                      <ChevronRight className="w-4 h-4" />
                    </button>
                  </div>
                )}
              </div>
            </>
          )}
        </div>
      </div>
    </div>
  );
};

export default StudyView;
