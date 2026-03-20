import React, { useState, useEffect, useMemo } from 'react';
import { useParams } from 'react-router-dom';
import StrategyMatrix from './StrategyMatrix';
import BoardSelector from './BoardSelector';
import SummaryStats from './SummaryStats';
import { 
  Loader2,
  AlertCircle,
  RefreshCw,
  Database
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

const DashboardView: React.FC = () => {
  const { solutionId } = useParams<{ solutionId: string }>();
  const [resolvedSolutionId, setResolvedSolutionId] = useState<string | null>(null);
  const [nodes, setNodes] = useState<StrategyNode[]>([]);
  const [loading, setLoading] = useState(true);
  const [fetchingData, setFetchingData] = useState(false);
  const [board, setBoard] = useState<string[]>([]);
  
  // Left Nav State
  const [activeTab, setActiveTab] = useState('SRP');
  const [activeStack, setActiveStack] = useState('100');
  const [activePosition, setActivePosition] = useState('SB vs BB');
  const [useAnte, setUseAnte] = useState(false);
  const [gameType] = useState('6-Max');
  const [error, setError] = useState<string | null>(null);

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

  useEffect(() => {
    const fetchData = async () => {
      if (!resolvedSolutionId) {
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
  }, [resolvedSolutionId]);

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
    setBoard(prev => 
      prev.includes(card) 
        ? prev.filter(c => c !== card) 
        : (prev.length < 3 ? [...prev, card] : prev)
    );
  };

  const handleReset = () => {
    setBoard([]);
  };

  const handlePreflopClick = () => {
    handleReset();
    // Return to root preflop state
    localStorage.removeItem('gto_active_solution');
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
             <div className="flex gap-1 h-[30px] items-center px-2 bg-[#0d1f1f] rounded-[4px] border border-[#182628]">
                {board.map((card, idx) => {
                  const suit = card.slice(-1);
                  const rank = card.slice(0, -1);
                  const isRed = ['h', 'd'].includes(suit.toLowerCase());
                  return (
                    <div key={idx} className={`flex items-center justify-center bg-white rounded-sm px-1 min-w-[24px] h-[22px] font-black text-[11px] ${isRed ? 'text-red-600' : 'text-black'}`}>
                      {rank.toUpperCase()}{suit.toLowerCase() === 'h' ? '♥' : suit.toLowerCase() === 'd' ? '♦' : suit.toLowerCase() === 's' ? '♠' : '♣'}
                    </div>
                  );
                })}
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

        {/* Board Selector */}
        <BoardSelector
          board={board}
          onReset={handleReset}
          onCardToggle={handleCardToggle}
        />

        {/* Strategy Matrix Wrapper */}
        <div className="w-full flex-1 min-h-[500px] bg-[#2d393b] rounded-[5px] p-2 mt-3 flex flex-col relative shadow-lg overflow-hidden">
          {fetchingData && (
            <div className="absolute inset-0 z-10 bg-[#182628]/60 backdrop-blur-[4px] flex flex-col items-center justify-center gap-4">
              <Loader2 className="w-10 h-10 text-[#7aa6da] animate-spin" />
              <p className="text-[13px] font-black uppercase tracking-widest text-[#7aa6da]">Syncing Solved Data...</p>
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
        
      </div>
    </div>
  );
};

export default DashboardView;

