import React, { useState, useEffect } from 'react';
import { useParams } from 'react-router-dom';
import StrategyMatrix from './StrategyMatrix';
import BoardSelector from './BoardSelector';
import { apiClient } from '../api/client';
import type { StrategyNode, Solution } from '../types/poker';

const DashboardView: React.FC = () => {
  const { solutionId } = useParams<{ solutionId: string }>();
  const [resolvedSolutionId, setResolvedSolutionId] = useState<string | null>(null);
  const [nodes, setNodes] = useState<StrategyNode[]>([]);
  const [loading, setLoading] = useState(true);
  const [board, setBoard] = useState<string[]>([]);
  
  // Left Nav State
  const [activeTab, setActiveTab] = useState('SRP');
  const [activeStack, setActiveStack] = useState('100');
  const [activePosition, setActivePosition] = useState('SB vs BB');

  // Handle Initial Load (solutionId or default) vs Dynamic Nav Clicks
  useEffect(() => {
    const resolveId = async () => {
      // Always query backend using current active state
      const queryParams = new URLSearchParams();
      queryParams.append('stack_depth', activeStack);
      if (activePosition) {
        // use URL encoded mapping just in case
        queryParams.append('name', activePosition.split(' vs ')[0]); // simplified to "SB" etc.
      }
      
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
  }, [activeStack, activePosition, activeTab, solutionId]);

  useEffect(() => {
    const fetchData = async () => {
      if (!resolvedSolutionId) {
        setNodes([]);
        setLoading(false);
        return;
      }
      try {
        setLoading(true);
        const [_, nodesData] = await Promise.all([
          apiClient.get<Solution>(`/solutions/${resolvedSolutionId}/`),
          apiClient.get<StrategyNode[]>('/nodes/', { solution_id: resolvedSolutionId, path: 'root' })
        ]);
        setNodes(nodesData);
      } catch (err) {
        console.error('Failed to fetch dashboard data:', err);
      } finally {
        setLoading(false);
      }
    };
    fetchData();
  }, [resolvedSolutionId]);

  if (loading) {
    return (
      <div className="flex flex-col items-center justify-center h-[60vh] gap-4 bg-[#00140f]">
        <div className="w-12 h-12 border-4 border-[#7aa6da] border-t-transparent rounded-full animate-spin"></div>
        <p className="text-[#7aa6da] font-bold animate-pulse">Loading Solver Workspace...</p>
      </div>
    );
  }

  const handleCardToggle = (card: string) => {
    setBoard(prev => 
      prev.includes(card) 
        ? prev.filter(c => c !== card) 
        : (prev.length < 3 ? [...prev, card] : prev)
    );
  };

  const handleReset = () => {
    setBoard([]);
    // Optionally reset filters to defaults if reset should affect everything
    // setActiveTab('SRP');
    // setActiveStack('100');
    // setActivePosition('SB vs BB');
  };

  const tabs = ['SRP', '3 BET', '4 BET', 'HU'];
  const stacks = ['100', '150'];
  const positions = ['SB vs BB', 'BTN vs BB', 'CO vs BB', 'MP vs BB', 'UTG vs BB', 'MP vs BTN', 'UTG vs BTN'];

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
              onClick={() => setActiveTab(tab)}
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
                onClick={() => setActiveStack(stack)}
                className={`flex flex-col items-center justify-center rounded py-2 transition-colors text-xs font-bold gap-0.5
                  ${activeStack === stack ? 'bg-[#7aa6da] text-[#182628]' : 'bg-[#2d393b] text-[#7aa6da] hover:bg-[#465f61] hover:text-white'}`}
              >
                {stack.split('').map((char, j) => <span key={j}>{char}</span>)}
              </button>
            ))}
          </div>
          
          {/* Positions */}
          <div className="flex-1 flex flex-col gap-[7px]">
            {positions.map((pos) => (
              <button 
                key={pos} 
                onClick={() => setActivePosition(pos)}
                className={`w-full py-2 px-3 rounded text-sm font-bold text-center transition-colors border-l-[3px]
                  ${activePosition === pos ? 'bg-[#465f61] text-white border-[#7aa6da]' : 'bg-[#2d393b] text-[#ccdbdc] hover:bg-[#465f61] border-transparent'}`}
              >
                {pos}
              </button>
            ))}
          </div>
        </div>
      </div>
      
      {/* Center Panel */}
      <div className="flex flex-col items-center w-full px-3 py-2 overflow-y-auto bg-[#00140f]">
        
        {/* Top Toolbar */}
        <div className="flex w-full justify-between items-center pb-3 px-1">
          <div className="flex items-center gap-2">
            <button className="bg-[#2d393b] text-[#ccdbdc] font-bold px-3 py-1 rounded-[3px] text-xs hover:bg-[#465f61] transition-colors border border-[#182628]">
              root
            </button>
          </div>

          <div className="flex flex-col items-center gap-0">
            <div className="flex items-center gap-2">
              <span className="bg-[#0d1f1f] text-[#7aa6da] px-2 py-0.5 rounded text-[10px] font-black tracking-widest uppercase border border-[#7aa6da]/20">PREFLOP</span>
              <span className="bg-[#003249] text-white px-3 py-0.5 rounded text-xs font-black uppercase">BTN</span>
            </div>
            <span className="text-[10px] font-bold text-[#7aa6da]/80 mt-0.5 tracking-tight">3BET = 7.5 BB</span>
          </div>
          
          <div className="flex items-center gap-3">
             <div className="w-[140px] h-[30px] bg-[#0d1f1f] rounded-[4px] border border-[#182628]"></div>
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
        <div className="w-full flex-1 min-h-[500px] bg-[#2d393b] rounded-[5px] p-2 mt-3 flex flex-col relative shadow-lg">
          <div className="w-full flex-1 overflow-hidden rounded">
             <StrategyMatrix nodes={nodes} onHandSelect={(hand) => console.log('Selected:', hand)} />
          </div>
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

