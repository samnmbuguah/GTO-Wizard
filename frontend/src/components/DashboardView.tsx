import React, { useState, useEffect, useMemo } from 'react';
import { useParams } from 'react-router-dom';
import StrategyMatrix from './StrategyMatrix';
import BoardSelector from './BoardSelector';
import CardBadge from './common/CardBadge';
import SummaryStats from './SummaryStats';
import DecisionTree from './DecisionTree';
import { 
  Loader2,
  AlertCircle,
  RefreshCw,
  Database,
  Calculator,
  Zap,
  Clock
} from 'lucide-react';
import { apiClient } from '../api/client';
import type { StrategyNode, Solution } from '../types/poker';

interface TabCategory {
  name?: string;
  positions: string[];
}

interface TabConfig {
  categories: TabCategory[];
}

/**
 * 6-max seat order (UTG first). Preflop card bunching depends on which seats
 * folded: in a 6-max cash game every seat except the two players in the hand
 * folded, which is where the "4 folded players" default comes from. The
 * backend derives a seat-aware dead-card profile from these seats.
 */
const SIX_MAX_SEATS = ['UTG', 'MP', 'CO', 'BTN', 'SB', 'BB'];

export const foldedSeatsFor = (position: string, headsUp = false): string[] => {
  if (headsUp) return [];
  const parts = position.split(' vs ').map((s) => s.trim());
  if (parts.length !== 2) return [];
  const [oop, ip] = parts;
  if (!SIX_MAX_SEATS.includes(oop) || !SIX_MAX_SEATS.includes(ip)) return [];
  return SIX_MAX_SEATS.filter((seat) => seat !== oop && seat !== ip);
};

const TAB_CONFIG: Record<string, Record<string, TabConfig>> = {
  '100': {
    'SRP': {
      categories: [{ positions: ['SB vs BB', 'BTN vs BB', 'CO vs BB', 'MP vs BB', 'UTG vs BB', 'MP vs BTN', 'UTG vs BTN'] }]
    },
    '3 BET': {
      categories: [
        { positions: ['BB vs SB', 'BB vs BTN', 'BB vs CO', 'BB vs MP', 'BB vs UTG', 'SB vs BTN', 'SB vs CO', 'SB vs MP', 'SB vs UTG', 'BTN vs CO', 'BTN vs MP', 'BTN vs UTG', 'CO vs MP', 'CO vs UTG', 'MP vs UTG'] },
        { name: 'SQUEEZE', positions: ['BB vs BTN', 'BB vs MP', 'SB vs BTN', 'SB vs MP'] }
      ]
    },
    '4 BET': {
      categories: [
        { positions: ['SB vs BB', 'BTN vs BB', 'BTN vs SB', 'CO vs BB', 'CO vs SB', 'CO vs BTN', 'MP vs BB', 'MP vs SB', 'MP vs BTN', 'MP vs CO', 'UTG vs BTN', 'UTG vs CO'] },
        { name: 'COLD 4 BET', positions: ['BB vs SB', 'BB vs BTN', 'BB vs CO', 'BTN vs CO'] }
      ]
    },
    'HU': {
      categories: [{ positions: ['SRP', '3 BET', '4 BET'] }]
    }
  },
  '150': {
    'SRP': {
      categories: [] // Empty as per 150bb reference
    },
    '3 BET': {
      categories: [
        { positions: ['BB vs SB', 'BB vs BTN', 'BB vs CO', 'BB vs MP', 'BB vs UTG', 'SB vs BTN', 'SB vs CO', 'SB vs MP', 'SB vs UTG', 'BTN vs CO', 'BTN vs MP', 'BTN vs UTG', 'CO vs MP', 'CO vs UTG', 'MP vs UTG'] }
      ]
    },
    '4 BET': {
      categories: [
        { positions: ['SB vs BB', 'BTN vs BB', 'BTN vs SB', 'CO vs BB', 'CO vs SB', 'CO vs BTN', 'MP vs BB', 'MP vs SB', 'MP vs BTN', 'MP vs CO', 'UTG vs BTN', 'UTG vs CO'] },
        { name: 'COLD 4 BET', positions: ['BB vs SB', 'BB vs BTN', 'BB vs CO', 'BTN vs CO'] }
      ]
    },
    'HU': {
      categories: [{ positions: ['3 BET', '4 BET'] }]
    }
  }
};

const CANONICAL_PRESETS = [
  { id: 'dry_ace', label: 'Dry Ace-High', cards: ['Ah', 'Kd', '2c'], desc: 'High range advantage' },
  { id: 'wet_connected', label: 'Wet Connected', cards: ['9s', '8h', '7d'], desc: 'Dynamic texture' },
  { id: 'paired', label: 'Paired Board', cards: ['8s', '8h', '2c'], desc: 'Trips never fold' },
  { id: 'monotone', label: 'Monotone', cards: ['As', 'Ks', 'Ts'], desc: 'Flush risk texture' },
  { id: 'low_disc', label: 'Low Disconnected', cards: ['7s', '4d', '2c'], desc: 'OOP retainment' },
];

const DashboardView: React.FC = () => {
  const { solutionId } = useParams<{ solutionId: string }>();
  const [resolvedSolutionId, setResolvedSolutionId] = useState<string | null>(null);
  const [nodes, setNodes] = useState<StrategyNode[]>([]);
  const [loading, setLoading] = useState(true);
  const [fetchingData, setFetchingData] = useState(false);
  const [board, setBoard] = useState<string[]>([]);
  
  // Left Nav State - Best Working Defaults for Live Demo
  const [activeTab, setActiveTab] = useState('SRP');
  const [activeStack, setActiveStack] = useState('100');
  const [activePosition, setActivePosition] = useState('SB vs BB');
  const [useAnte, setUseAnte] = useState(false);
  const [gameType] = useState('6-Max');
  const [error, setError] = useState<string | null>(null);
  
  // Dynamic Sizing & Live Solving State
  const [solverLoading, setSolverLoading] = useState(false);
  const [solverResult, setSolverResult] = useState<any>(null);
  const [customSizes, setCustomSizes] = useState(() => localStorage.getItem('gto_default_sizes') || '0.33, 0.5, 0.75');
  const [rakePreset, setRakePreset] = useState<'NL500' | 'NL50' | 'MTT' | 'Custom'>('NL500');
  const [customRake, setCustomRake] = useState(() => parseFloat(localStorage.getItem('gto_default_rake_percent') || '5.0'));
  const [customCap, setCustomCap] = useState(() => parseFloat(localStorage.getItem('gto_default_rake_cap') || '0.6'));
  const [customPot, setCustomPot] = useState(5.5);
  const [customStack, setCustomStack] = useState(100.0);
  const [anteBb, setAnteBb] = useState<number>(0);
  const [useBunching, setUseBunching] = useState<boolean>(true);
  const [openSize, setOpenSize] = useState(2.5);
  const [liveMode, setLiveMode] = useState(true);
  const [liveSolveStats, setLiveSolveStats] = useState<{
    solveTimeMs: number;
    exploitability?: number;
    exploitabilityPctPot?: number;
    exploitabilityBb?: number;
    iterations?: number;
    converged?: boolean;
    engine: string;
    oopEv?: number;
    ipEv?: number;
    overallFrequencies?: { fold: number; call: number; raise: number };
  } | null>(null);

  const getFlopTexture = (cards: string[]) => {
    if (cards.length < 3) return '';
    const ranks = cards.map(c => c[0]);
    if (new Set(ranks).size < ranks.length) return 'Paired';
    const isHigh = cards.some(c => ['A','K','Q','J','T'].includes(c[0]));
    const isMonotone = cards.every(c => c.slice(-1) === cards[0].slice(-1));
    if (isMonotone) return 'Monotone';
    return isHigh ? 'High' : 'Low';
  };

  // Handle Initial Load (solutionId or default) vs Dynamic Nav Clicks
  useEffect(() => {
    const resolveId = async () => {
      // Always query backend using current active state
      const queryParams = new URLSearchParams();
      queryParams.append('stack_depth', activeStack);
      if (useAnte) {
        queryParams.append('ante__gt', '0');
      } else {
        queryParams.append('ante', '0');
      }
      queryParams.append('game_type', gameType);

      if (activePosition) {
        queryParams.append('name', activePosition.split(' vs ')[0]); 
      }

      queryParams.append('flop_texture', getFlopTexture(board));
      
      try {
        const solutions = await apiClient.get<Solution[]>(`/solutions/?${queryParams.toString()}`);
        if (solutions && solutions.length > 0) {
          setResolvedSolutionId(String(solutions[0].id));
          localStorage.setItem('gto_active_solution', String(solutions[0].id));
        } else if (solutionId) {
          // fallback to URL id if filters returned nothing but we have an explicit ID
          setResolvedSolutionId(solutionId);
        } else {
          setResolvedSolutionId(null);
        }
      } catch (err) {
        setResolvedSolutionId(null);
      }
    };

    resolveId();
  }, [activeStack, activePosition, activeTab, solutionId, useAnte, gameType, board]);

  // Global Hotkey 'G'
  useEffect(() => {
    const handleKeyDown = (e: KeyboardEvent) => {
      if (e.key.toLowerCase() === 'g' && !['INPUT', 'TEXTAREA'].includes((e.target as HTMLElement).tagName)) {
        handlePreflopClick();
      }
    };
    window.addEventListener('keydown', handleKeyDown);
    return () => window.removeEventListener('keydown', handleKeyDown);
  }, []);

  // Live Solve Calculation Function
  const triggerLiveSolve = async (currentBoard: string[]) => {
    if (currentBoard.length < 3) return;
    setFetchingData(true);
    setError(null);
    try {
      const payload = {
        board: currentBoard,
        spot: `${activePosition.replace(' vs ', '_vs_')}_${activeTab.replace(' ', '')}`,
        pot: customPot,
        effective_stack: customStack,
        ante_bb: anteBb,
        rake_percent: customRake,
        rake_cap: customCap,
        num_folded_players: useBunching ? 4 : 0,
        use_bunching: useBunching,
        folded_positions: useBunching ? foldedSeatsFor(activePosition, activeTab === 'HU') : [],
        open_size: openSize
      };
      const res = await apiClient.post<any>('/solutions/live-solve/', payload);
      if (res && res.strategy) {
        // Map solved 13x13 strategy matrix into StrategyNode format for the matrix view.
        // Prefer the engine's real action labels (Check / Bet 33% / All-in / ...).
        // Only fall back to the fold/call/raise buckets if they are unavailable.
        const generatedNodes: StrategyNode[] = Object.entries(res.strategy).map(([hand, acts]: [string, any], idx) => {
          const detail = res.strategy_detail?.[hand];
          const actions =
            detail && Object.keys(detail).length > 0
              ? detail
              : { Fold: acts.fold, Call: acts.call, Raise: acts.raise };
          return {
            id: idx + 1,
            path: 'root',
            hand: hand,
            actions,
            ev: res.hand_ev?.[hand] ?? 0.0,
            equity: 0.5,
          };
        });
        setNodes(generatedNodes);
        setLiveSolveStats({
          solveTimeMs: res.solve_time_ms,
          exploitability: res.exploitability ?? undefined,
          exploitabilityPctPot: res.exploitability_pct_pot ?? undefined,
          exploitabilityBb: res.exploitability_bb ?? undefined,
          iterations: res.iterations,
          converged: res.converged,
          engine: res.engine || 'Rust DCFR Engine',
          oopEv: res.oop_ev ?? undefined,
          ipEv: res.ip_ev ?? undefined,
          overallFrequencies: res.overall_frequencies
        });
        setResolvedSolutionId('live_solution');
      }
    } catch (err: any) {
      console.error('Live solve error:', err);
    } finally {
      setFetchingData(false);
      setLoading(false);
    }
  };

  useEffect(() => {
    if (liveMode && board.length >= 3) {
      triggerLiveSolve(board);
      return;
    }

    const fetchData = async () => {
      if (!resolvedSolutionId || resolvedSolutionId === 'live_solution') {
        setNodes([]);
        setLoading(false);
        return;
      }
      try {
        setFetchingData(true);
        setError(null);
        const [_, nodesData] = await Promise.all([
          apiClient.get<Solution>(`/solutions/${resolvedSolutionId}/`),
          apiClient.get<StrategyNode[]>('/nodes/', { solution_id: resolvedSolutionId, path: 'root' })
        ]);
        setNodes(nodesData);
      } catch (err) {
        console.error('Failed to fetch dashboard data:', err);
        setError('Failed to load strategy data. Please check your connection or try again.');
      } finally {
        setFetchingData(false);
        setLoading(false);
      }
    };
    fetchData();
  }, [resolvedSolutionId, board, liveMode, customRake, customCap, customPot, customStack, anteBb, useBunching, activePosition]);

  const handleRetry = () => {
    // Re-trigger the resolveId by toggling a hidden state or just re-resolving
    // Actually, setting error to null will re-trigger effects if we set it up right, 
    // but better to just re-fetch.
    setResolvedSolutionId(prev => (prev ? prev : null)); // Simple nudge
    localStorage.removeItem('gto_active_solution'); // Force a fresh start
    window.location.reload(); // Simple brute force for now as requested for "graceful" but quick
  };

  const tabs = useMemo(() => Object.keys(TAB_CONFIG['100']), []);
  const stacks = ['100', '150'];
  
  const currentTabConfig = useMemo(() => TAB_CONFIG[activeStack]?.[activeTab] || { categories: [] }, [activeTab, activeStack]);

  const handleTabChange = (tab: string) => {
    setActiveTab(tab);
    const config = TAB_CONFIG[activeStack]?.[tab];
    if (config && config.categories.length > 0) {
      setActivePosition(config.categories[0].positions[0]);
    } else {
      setActivePosition('');
    }
  };

  const handleStackChange = (stack: string) => {
    setActiveStack(stack);
    const config = TAB_CONFIG[stack]?.[activeTab];
    if (config && config.categories.length > 0) {
      const allPositions = config.categories.flatMap(c => c.positions);
      if (!allPositions.includes(activePosition)) {
        setActivePosition(allPositions[0]);
      }
    } else {
      setActivePosition('');
    }
  };

  const handleCardToggle = (card: string) => {
    setBoard(prev => {
      const next = prev.includes(card) 
        ? prev.filter(c => c !== card) 
        : (prev.length < 3 ? [...prev, card] : [prev[0], prev[1], card]);
      if (liveMode && next.length >= 3) {
        triggerLiveSolve(next);
      }
      return next;
    });
  };

  const handleReset = () => {
    setBoard([]);
  };

  const handlePreflopClick = () => {
    handleReset();
    setActiveTab('SRP');
    setActivePosition('SB vs BB');
    localStorage.removeItem('gto_active_solution');
  };

  const runDynamicSolve = async () => {
    if (!resolvedSolutionId) return;
    setSolverLoading(true);
    try {
      const sizes = customSizes.split(',').map(s => parseFloat(s.trim())).filter(s => !isNaN(s));
      const result = await apiClient.post('/solutions/dynamic-sizing/', {
        solution_id: resolvedSolutionId,
        path: 'root', // Dynamic solving from current path
        board_texture: getFlopTexture(board),
        sizes: sizes
      });
      setSolverResult(result);
    } catch (err) {
      console.error('Solver error:', err);
    } finally {
      setSolverLoading(false);
    }
  };

  if (loading) {
    return (
      <div className="flex flex-col items-center justify-center h-[60vh] gap-4 bg-[#00140f]">
        <div className="w-12 h-12 border-4 border-[#7aa6da] border-t-transparent rounded-full animate-spin"></div>
        <p className="text-[#7aa6da] font-bold animate-pulse">Loading Solver Workspace...</p>
      </div>
    );
  }

  return (
    <div className="h-[calc(100vh-50px)] grid grid-cols-[18vw_1fr] bg-[#00140f] overflow-hidden">
      {/* Left Sidebar */}
      <div className="flex flex-col bg-[#182628] border-r border-[#2d393b] pt-2">
        {/* Tabs */}
        <div className="flex w-full mb-4 px-2">
          {tabs.map((tab) => (
            <button 
              key={tab} 
              aria-label={`${tab} tab`}
              onClick={() => handleTabChange(tab)}
              className={`flex-1 pb-2 text-sm font-bold text-center border-b-2 transition-colors 
                ${activeTab === tab ? 'text-white border-[#7aa6da]' : 'text-[#a1b4d9] border-transparent hover:text-white'}`}
            >
              {tab}
            </button>
          ))}
        </div>
        
        {/* Constraints / Positions Content */}
        <div className="flex w-full gap-3 px-3 h-full overflow-y-auto pb-4">
          {/* Stack Sizes */}
          <div className="flex flex-col gap-2 w-[35px]">
            {stacks.map((stack) => (
              <button 
                key={stack} 
                onClick={() => handleStackChange(stack)}
                className={`flex flex-col items-center justify-center rounded py-2 transition-colors text-xs font-bold gap-0.5
                  ${activeStack === stack ? 'bg-[#7aa6da] text-[#182628]' : 'bg-[#2d393b] text-[#7aa6da] hover:bg-[#465f61] hover:text-white'}`}
              >
                {stack.split('').map((char, j) => <span key={j}>{char}</span>)}
              </button>
            ))}
          </div>
          
          {/* Ante Toggle */}
          <div className="flex flex-col gap-2 w-[35px]">
            <button 
              aria-label="Toggle Ante"
              onClick={() => setUseAnte(!useAnte)}
              className={`flex flex-col items-center justify-center rounded py-2 transition-colors text-[10px] font-black
                ${useAnte ? 'bg-[#7aa6da] text-[#182628]' : 'bg-[#182628] text-[#7aa6da] border border-[#7aa6da]/20 hover:bg-[#7aa6da]/10'}`}
            >
              <span>A</span><span>N</span><span>T</span><span>E</span>
            </button>
          </div>
          
          {/* Positions */}
          <div className="flex-1 flex flex-col gap-[7px]">
            {currentTabConfig.categories.map((category, i) => (
              <React.Fragment key={category.name || i}>
                {category.name && (
                  <div className="text-[10px] font-black text-[#7aa6da] text-center uppercase tracking-[0.2em] py-2 mt-2 border-y border-[#7aa6da]/10 bg-[#0d1f1f]/50">
                    {category.name}
                  </div>
                )}
                <div className="flex flex-col gap-[7px]">
                  {category.positions.map((pos) => (
                    <button 
                      key={pos} 
                      onClick={() => setActivePosition(pos)}
                      className={`w-full py-2 px-3 rounded text-[11px] font-bold text-center transition-all border-l-[3px] shadow-sm
                        ${activePosition === pos 
                          ? 'bg-[#465f61] text-white border-[#7aa6da] scale-[1.02]' 
                          : 'bg-[#2d393b] text-[#ccdbdc] hover:bg-[#465f61] border-transparent hover:border-[#7aa6da]/30'}`}
                    >
                      {pos}
                    </button>
                  ))}
                </div>
              </React.Fragment>
            ))}
          </div>
        </div>
      </div>
      
      {/* Center Panel */}
      <div className="flex flex-col items-center w-full px-3 py-2 overflow-y-auto bg-[#00140f]">
        
        {/* Top Toolbar */}
        <div className="flex w-full justify-between items-center pb-3 px-1">
          <div className="flex items-center gap-2">
            {/* Removed root button to match reference */}
          </div>

          <div className="flex items-center bg-[#2a0a0a] rounded-md px-3 py-1.5 border border-red-900/30 gap-4">
            <div className="flex flex-col items-start leading-none">
              <button 
                onClick={handlePreflopClick}
                className="text-red-500 font-black text-sm hover:text-red-400 transition-colors uppercase tracking-tight"
              >
                PREFLOP
              </button>
              <span className="text-[9px] font-bold text-red-500/60 uppercase tracking-tighter mt-0.5">SRP • 2.5 BB</span>
            </div>
            <div className="w-[1px] h-6 bg-red-900/30"></div>
            <span className="text-red-500 font-black text-sm uppercase">{activePosition.split(' vs ')[0] || 'UTG'}</span>
          </div>
          
          <div className="flex items-center gap-3">
             {/* Selected Cards display */}
             <div className="flex gap-1.5 h-[30px] items-center px-2 bg-[#0d1f1f] rounded-[4px] border border-[#182628]">
                {board.map((card, idx) => (
                  <CardBadge key={idx} card={card} size="sm" />
                ))}
                {board.length === 0 && <span className="text-[10px] text-[#7aa6da]/30 font-bold italic">No Board</span>}
             </div>
             
             <button 
               onClick={handleReset}
               className="bg-[#465f61] text-white font-black px-5 py-1.5 rounded-[3px] hover:bg-[#003249] transition-colors text-xs uppercase tracking-wider"
             >
               RESET
             </button>
          </div>
        </div>

        {/* Live Solver Telemetry Bar */}
        <div className="flex flex-wrap items-center justify-between bg-[#1f2b2d] border border-[#2d393b] rounded-[5px] px-3 py-2 mb-2 text-xs">
          <div className="flex items-center gap-3">
            <button
              onClick={() => {
                const next = !liveMode;
                setLiveMode(next);
                if (next && board.length >= 3) triggerLiveSolve(board);
              }}
              className={`flex items-center gap-1.5 px-2.5 py-1 rounded text-[11px] font-bold uppercase transition-all ${
                liveMode ? 'bg-green-600/20 text-green-400 border border-green-500/30' : 'bg-[#2d393b] text-[#a1b4d9]'
              }`}
            >
              <Zap className={`w-3.5 h-3.5 ${liveMode ? 'text-green-400 animate-pulse' : 'text-gray-400'}`} />
              {liveMode ? 'Live DCFR Engine: ON' : 'Live Solve: OFF'}
            </button>

            {liveSolveStats && liveMode && (
              <div className="flex flex-wrap items-center gap-3 font-mono text-[11px]">
                <div className="flex items-center gap-1 text-[#7aa6da]">
                  <Clock className="w-3.5 h-3.5" />
                  <span>{liveSolveStats.solveTimeMs}ms</span>
                </div>
                {liveSolveStats.exploitabilityPctPot !== undefined ? (
                  <div
                    className={`flex items-center gap-1 ${
                      liveSolveStats.converged ? 'text-emerald-400' : 'text-amber-400'
                    }`}
                    title={`NashConv/2 of the solved game: ${liveSolveStats.exploitabilityBb?.toFixed(4)} bb`}
                  >
                    <span>
                      dEV: {liveSolveStats.exploitabilityPctPot.toFixed(3)}% pot
                      {liveSolveStats.exploitabilityBb !== undefined &&
                        ` (${liveSolveStats.exploitabilityBb.toFixed(4)} bb)`}
                    </span>
                    <span className="text-[9px] uppercase">
                      {liveSolveStats.converged ? 'converged' : 'partial'}
                    </span>
                  </div>
                ) : liveSolveStats.exploitability !== undefined ? (
                  <div className="flex items-center gap-1 text-emerald-400">
                    <span>dEV: {liveSolveStats.exploitability}</span>
                  </div>
                ) : null}
                {liveSolveStats.iterations !== undefined && (
                  <span className="text-[#a1b4d9]">{liveSolveStats.iterations} iters</span>
                )}
                {liveSolveStats.oopEv !== undefined && (
                  <div className="flex items-center gap-2 text-sky-300">
                    <span>OOP: {liveSolveStats.oopEv.toFixed(2)}bb</span>
                    <span>IP: {liveSolveStats.ipEv?.toFixed(2)}bb</span>
                  </div>
                )}
                <span className="text-[10px] text-[#a1b4d9] uppercase bg-[#182628] px-1.5 py-0.5 rounded border border-[#2d393b]">
                  {liveSolveStats.engine}
                </span>
              </div>
            )}
          </div>

          <div className="flex flex-wrap items-center gap-2 mt-2 sm:mt-0">
            <span className="text-[9.5px] font-mono font-bold text-[#64ffda] bg-[#64ffda]/10 px-1.5 py-0.5 rounded border border-[#64ffda]/30 uppercase">
              6-Max NL500
            </span>
            <div className="flex items-center gap-1">
              <span className="text-[10px] text-[#a1b4d9] uppercase font-bold">Open:</span>
              <input
                type="number"
                step="0.5"
                min="2.0"
                max="5.0"
                value={openSize}
                onChange={(e) => {
                  const val = parseFloat(e.target.value) || 2.5;
                  setOpenSize(val);
                  setCustomPot(val * 2 + 0.5);
                }}
                className="w-11 bg-[#0d1f1f] border border-[#2d393b] rounded px-1.5 py-0.5 text-white text-[11px] font-mono text-center focus:outline-none focus:border-[#7aa6da]"
              />
              <span className="text-[10px] text-[#a1b4d9]">bb</span>
            </div>
            <div className="flex items-center gap-1">
              <span className="text-[10px] text-[#a1b4d9] uppercase font-bold">Pot:</span>
              <input
                type="number"
                step="0.5"
                min="1"
                max="100"
                value={customPot}
                onChange={(e) => setCustomPot(parseFloat(e.target.value) || 5.5)}
                className="w-12 bg-[#0d1f1f] border border-[#2d393b] rounded px-1.5 py-0.5 text-white text-[11px] font-mono text-center focus:outline-none focus:border-[#7aa6da]"
              />
              <span className="text-[10px] text-[#a1b4d9]">bb</span>
            </div>
            <div className="flex items-center gap-1">
              <span className="text-[10px] text-[#a1b4d9] uppercase font-bold">Stack:</span>
              <select
                aria-label="Stack Depth Preset"
                value={[20, 40, 60, 100].includes(customStack) ? String(customStack) : 'custom'}
                onChange={(e) => {
                  const v = e.target.value;
                  if (v !== 'custom') {
                    const num = parseFloat(v);
                    setCustomStack(num);
                    setActiveStack(String(num));
                  }
                }}
                className="bg-[#0d1f1f] border border-[#2d393b] rounded px-1 py-0.5 text-white text-[11px] font-mono focus:outline-none focus:border-[#7aa6da]"
              >
                <option value="20">20bb</option>
                <option value="40">40bb</option>
                <option value="60">60bb</option>
                <option value="100">100bb</option>
                <option value="custom">Custom</option>
              </select>
              <input
                type="number"
                step="5"
                min="10"
                max="300"
                value={customStack}
                onChange={(e) => setCustomStack(parseFloat(e.target.value) || 100.0)}
                className="w-12 bg-[#0d1f1f] border border-[#2d393b] rounded px-1 py-0.5 text-white text-[11px] font-mono text-center focus:outline-none focus:border-[#7aa6da]"
              />
            </div>
            <div className="flex items-center gap-1">
              <span className="text-[10px] text-[#a1b4d9] uppercase font-bold">Ante:</span>
              <select
                aria-label="Ante Size"
                value={String(anteBb)}
                onChange={(e) => {
                  const val = parseFloat(e.target.value) || 0;
                  setAnteBb(val);
                  setUseAnte(val > 0);
                  setCustomPot(val > 0 ? Number((openSize * 2 + 0.5 + val * 8).toFixed(2)) : openSize * 2 + 0.5);
                }}
                className="bg-[#0d1f1f] border border-[#2d393b] rounded px-1 py-0.5 text-white text-[11px] font-mono focus:outline-none focus:border-[#7aa6da]"
              >
                <option value="0">None</option>
                <option value="0.12">0.12bb</option>
                <option value="0.25">0.25bb</option>
              </select>
            </div>
            <div className="flex items-center gap-1">
              <span className="text-[10px] text-[#a1b4d9] uppercase font-bold">Rake:</span>
              <select
                aria-label="Rake Preset"
                value={rakePreset}
                onChange={(e) => {
                  const p = e.target.value as 'NL500' | 'NL50' | 'MTT' | 'Custom';
                  setRakePreset(p);
                  if (p === 'NL500') { setCustomRake(5.0); setCustomCap(0.6); }
                  else if (p === 'NL50') { setCustomRake(5.0); setCustomCap(4.0); }
                  else if (p === 'MTT') { setCustomRake(0.0); setCustomCap(0.0); }
                }}
                className="bg-[#0d1f1f] border border-[#2d393b] rounded px-1 py-0.5 text-white text-[11px] font-mono focus:outline-none focus:border-[#7aa6da]"
              >
                <option value="NL500">NL500</option>
                <option value="NL50">NL50</option>
                <option value="MTT">None/MTT</option>
                <option value="Custom">Custom</option>
              </select>
              <input
                type="number"
                step="0.5"
                min="0"
                max="10"
                value={customRake}
                onChange={(e) => { setRakePreset('Custom'); setCustomRake(parseFloat(e.target.value) || 0); }}
                className="w-11 bg-[#0d1f1f] border border-[#2d393b] rounded px-1 py-0.5 text-white text-[11px] font-mono text-center focus:outline-none focus:border-[#7aa6da]"
              />
              <span className="text-[10px] text-[#a1b4d9]">%</span>
            </div>
            <div className="flex items-center gap-1">
              <span className="text-[10px] text-[#a1b4d9] uppercase font-bold">Cap:</span>
              <input
                type="number"
                step="0.5"
                min="0"
                max="5"
                value={customCap}
                onChange={(e) => { setRakePreset('Custom'); setCustomCap(parseFloat(e.target.value) || 0); }}
                className="w-11 bg-[#0d1f1f] border border-[#2d393b] rounded px-1 py-0.5 text-white text-[11px] font-mono text-center focus:outline-none focus:border-[#7aa6da]"
              />
              <span className="text-[10px] text-[#a1b4d9]">bb</span>
            </div>
            <button
              type="button"
              onClick={() => setUseBunching(!useBunching)}
              title="6-Max Preflop Card Bunching (4 folded players)"
              className={`px-2 py-0.5 rounded text-[10px] font-bold uppercase border transition-colors ${
                useBunching
                  ? 'bg-[#2d393b] text-[#7aa6da] border-[#7aa6da]/50'
                  : 'bg-[#0d1f1f] text-[#a1b4d9] border-[#2d393b]'
              }`}
            >
              Bunching: {useBunching ? 'ON' : 'OFF'}
            </button>
            <button
              onClick={() => board.length >= 3 && triggerLiveSolve(board)}
              disabled={fetchingData || board.length < 3}
              className="px-2.5 py-1 bg-[#7aa6da] hover:bg-[#5a86ba] text-[#182628] rounded font-bold text-[10px] uppercase transition-all disabled:opacity-40"
            >
              Re-Solve
            </button>
          </div>
        </div>

        {/* Canonical Texture Presets */}
        <div className="flex flex-wrap items-center gap-1.5 w-full mb-2 px-1">
          <span className="text-[10px] font-black uppercase tracking-wider text-[#a1b4d9] mr-1 flex items-center gap-1">
            <Zap className="w-3 h-3 text-[#7aa6da]" />
            Presets:
          </span>
          {CANONICAL_PRESETS.map((preset) => {
            const isActive = board.length === 3 && preset.cards.every((c, i) => board[i] === c);
            return (
              <button
                key={preset.id}
                onClick={() => {
                  setBoard(preset.cards);
                  if (liveMode) triggerLiveSolve(preset.cards);
                }}
                className={`px-2 py-1 rounded-[4px] text-[10.5px] font-bold transition-all flex items-center gap-1.5 border shadow-sm ${
                  isActive
                    ? 'bg-[#7aa6da] text-[#182628] border-white/40 scale-[1.02]'
                    : 'bg-[#182628] text-[#ccdbdc] hover:bg-[#2d393b] hover:text-white border-[#2d393b]'
                }`}
              >
                <span>{preset.label}</span>
                <span className="flex gap-0.5">
                  {preset.cards.map((c) => (
                    <CardBadge key={c} card={c} size="xs" />
                  ))}
                </span>
              </button>
            );
          })}
        </div>

        {/* Board Selector */}
        <BoardSelector
          board={board}
          onReset={handleReset}
          onCardToggle={handleCardToggle}
        />

        {/* Decision Tree / Street Action Navigator */}
        <div className="w-full mt-2 mb-1">
          <DecisionTree
            path={['Preflop', 'Flop', board.length >= 3 ? board.join(' ') : 'Flop Decision']}
            actions={['Fold', 'Call', 'Raise (33% Pot)']}
            frequencies={liveSolveStats?.overallFrequencies}
            onActionClick={(action) => console.log('Action selected:', action)}
            onBreadcrumbClick={(index) => {
              if (index === 0) handlePreflopClick();
            }}
          />
        </div>

        {/* Strategy Matrix Wrapper */}
        <div className="w-full flex-1 min-h-[500px] bg-[#2d393b] rounded-[5px] p-2 mt-3 flex flex-col relative shadow-lg overflow-hidden">
          {fetchingData && (
            <div className="absolute inset-0 z-10 bg-[#182628]/70 backdrop-blur-[4px] flex flex-col items-center justify-center gap-3">
              <Loader2 className="w-10 h-10 text-[#7aa6da] animate-spin" />
              <p className="text-[13px] font-black uppercase tracking-widest text-[#7aa6da]">
                Solving GTO Tree via Rust DCFR Engine (&lt; 500ms)...
              </p>
            </div>
          )}

          {error && (
            <div className="absolute inset-0 z-20 bg-[#182628]/95 backdrop-blur-[8px] flex flex-col items-center justify-center p-8 text-center gap-6">
              <AlertCircle className="w-16 h-16 text-red-500 mb-2" />
              <div className="space-y-2">
                <h3 className="text-xl font-black text-white uppercase tracking-tight">Data Sync Error</h3>
                <p className="text-[#a1b4d9] text-sm max-w-xs mx-auto">{error}</p>
              </div>
              <button 
                onClick={handleRetry}
                className="flex items-center gap-2 bg-[#7aa6da] hover:bg-[#5a86ba] text-[#182628] font-black px-6 py-3 rounded-[4px] transition-all transform hover:scale-105 active:scale-95 shadow-lg uppercase text-xs tracking-widest"
              >
                <RefreshCw className="w-4 h-4" />
                Reload Workspace
              </button>
            </div>
          )}
          
          {!resolvedSolutionId && !fetchingData && !error ? (
            <div className="flex-1 flex flex-col items-center justify-center p-8 text-center bg-[#0d1f1f]/30 rounded-[5px] border border-dashed border-[#7aa6da]/20">
              <Database className="w-16 h-16 text-[#7aa6da]/20 mb-4" />
              <h3 className="text-xl font-black text-white uppercase tracking-tight mb-2">No Solution Found</h3>
              <p className="text-[#a1b4d9] text-sm max-w-sm mx-auto leading-relaxed">
                We couldn't find a matching solver solution for <strong>{activeStack}BB {activeTab}</strong> in the <strong>{activePosition}</strong> spot.
              </p>
              <div className="mt-6 flex gap-4">
                <button 
                  onClick={() => setActiveStack('100')}
                  className="px-4 py-2 bg-[#182628] text-[#7aa6da] font-bold text-[10px] uppercase rounded hover:bg-[#2d393b] transition-colors"
                >
                  Try 100BB
                </button>
                <button 
                  onClick={() => setActiveTab('SRP')}
                  className="px-4 py-2 bg-[#182628] text-[#7aa6da] font-bold text-[10px] uppercase rounded hover:bg-[#2d393b] transition-colors"
                >
                  Try SRP
                </button>
              </div>
            </div>
          ) : (
            <>
              <SummaryStats nodes={nodes} />
              <div className="w-full flex-1 overflow-hidden rounded">
                 <StrategyMatrix nodes={nodes} onHandSelect={(hand) => console.log('Selected:', hand)} />
              </div>
            </>
          )}
          <div className="absolute bottom-1 right-2">
            <button className="text-[#a1b4d9] hover:text-white transition-colors p-2 bg-transparent pointer-cursor border-none">
              <i className="fa-solid fa-gear text-[20px]"></i>
            </button>
          </div>
        </div>

        {/* Dynamic Solver Panel */}
        <div className="w-full mt-4 bg-[#182628] rounded-[5px] border border-[#2d393b] p-4 shadow-xl">
          <div className="flex items-center justify-between mb-4">
            <div className="flex items-center gap-2 text-[#7aa6da]">
              <Calculator className="w-5 h-5" />
              <h3 className="font-black uppercase tracking-widest text-xs">Dynamic Solver (Fast Mode)</h3>
            </div>
            <div className="flex items-center gap-2 bg-[#0d1f1f] px-2 py-1 rounded border border-[#2d393b]">
              <Zap className="w-3 h-3 text-yellow-500" />
              <span className="text-[10px] font-bold text-yellow-500/80 uppercase">Depth-Limited &lt; 2s</span>
            </div>
          </div>

          <div className="grid grid-cols-[1fr_auto] gap-4 mb-4">
            <div className="flex flex-col gap-1">
              <label className="text-[10px] font-bold text-[#a1b4d9] uppercase mb-1">Candidate Sizes (Pot %)</label>
              <input 
                type="text" 
                value={customSizes}
                onChange={(e) => setCustomSizes(e.target.value)}
                className="bg-[#0d1f1f] border border-[#2d393b] rounded px-3 py-2 text-white text-xs font-bold focus:outline-none focus:border-[#7aa6da] transition-colors"
                placeholder="e.g. 0.33, 0.5, 0.75"
              />
            </div>
            <button 
              onClick={runDynamicSolve}
              disabled={solverLoading || !resolvedSolutionId}
              className={`mt-5 flex items-center justify-center gap-2 bg-[#7aa6da] hover:bg-[#5a86ba] text-[#182628] font-black px-6 py-2 rounded-[3px] transition-all
                ${(solverLoading || !resolvedSolutionId) ? 'opacity-50 cursor-not-allowed' : 'hover:scale-[1.02] shadow-lg'}`}
            >
              {solverLoading ? <Loader2 className="w-4 h-4 animate-spin" /> : <Calculator className="w-4 h-4" />}
              <span className="uppercase text-[11px] tracking-wider">Solve Stream</span>
            </button>
          </div>

          {solverResult && (
            <div className="grid grid-cols-2 gap-4 animate-in fade-in slide-in-from-top-2 duration-300">
              <div className="bg-[#0d1f1f] p-3 rounded border border-[#2d393b]">
                <p className="text-[9px] font-medium text-[#7aa6da] uppercase mb-1">Optimal Sizing</p>
                <p className="text-xl font-black text-white">{(solverResult.optimal_size * 100).toFixed(0)}% Pot</p>
                <div className="flex items-center gap-1 mt-1">
                  <Clock className="w-3 h-3 text-[#a1b4d9]" />
                  <span className="text-[10px] font-bold text-[#a1b4d9]">{solverResult.calc_time_ms}ms</span>
                </div>
                <div className="mt-2 flex items-center gap-1.5 bg-[#0d1f1f] px-2 py-0.5 rounded border border-[#2d393b] w-fit">
                   <Database className={`w-2.5 h-2.5 ${solverResult.mode?.includes('API') ? 'text-green-500' : 'text-[#7aa6da]'}`} />
                   <span className={`text-[8px] font-black uppercase tracking-tighter ${solverResult.mode?.includes('API') ? 'text-green-500' : 'text-[#7aa6da]'}`}>
                     {solverResult.mode || 'Simulated'}
                   </span>
                </div>
              </div>
              <div className="bg-[#0d1f1f] p-3 rounded border border-[#2d393b] overflow-hidden">
                <p className="text-[9px] font-medium text-[#7aa6da] uppercase mb-2">EV Distribution</p>
                <div className="flex items-end gap-1.5 h-[30px]">
                  {solverResult.ev_distribution?.map((d: any, i: number) => (
                    <div 
                      key={i} 
                      title={`${d.size * 100}%: ${d.ev} EV`}
                      className={`flex-1 rounded-t-sm transition-all duration-500
                        ${d.size === solverResult.optimal_size ? 'bg-[#7aa6da]' : 'bg-[#465f61]/40'}`}
                      style={{ height: `${Math.max(10, d.ev * 40)}%` }}
                    ></div>
                  ))}
                </div>
              </div>
            </div>
          )}
        </div>
        
      </div>
    </div>
  );
};

export default DashboardView;

