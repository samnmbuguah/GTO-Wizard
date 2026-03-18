import { useState, useMemo } from 'react'
import StrategyMatrix from './components/StrategyMatrix'
import DecisionTree from './components/DecisionTree'
import type { StrategyNode } from './types/poker'
import './App.css'

// Mock generator for demonstration
const generateMockData = (): StrategyNode[] => {
  const RANKS = ['A', 'K', 'Q', 'J', 'T', '9', '8', '7', '6', '5', '4', '3', '2'];
  const nodes: StrategyNode[] = [];
  
  for (let r1 = 0; r1 < 13; r1++) {
    for (let r2 = 0; r2 < 13; r2++) {
      const rank1 = RANKS[r1];
      const rank2 = RANKS[r2];
      let hand = '';
      if (r1 < r2) hand = `${rank1}${rank2}s`;
      else if (r1 > r2) hand = `${rank2}${rank1}o`;
      else hand = `${rank1}${rank2}`;

      const rand = Math.random();
      nodes.push({
        path: 'root',
        hand,
        actions: {
          'fold': rand * 0.4,
          'call': rand * 0.3,
          'raise': 1 - (rand * 0.4 + rand * 0.3)
        },
        ev: Math.random() * 10,
        equity: Math.random() * 100
      });
    }
  }
  return nodes;
};

function App() {
  const [path, setPath] = useState(['Preflop', 'BTN Open']);
  const [selectedHand, setSelectedHand] = useState<string | undefined>();
  const [isLiveSolver, setIsLiveSolver] = useState(false);
  const mockNodes = useMemo(() => generateMockData(), []);

  return (
    <div className="min-h-screen bg-poker-dark text-slate-200 p-8 flex flex-col items-center gap-8">
      <header className="w-full max-w-6xl flex justify-between items-center bg-glass p-6 rounded-2xl border border-white/10 shadow-2xl backdrop-blur-xl">
        <h1 className="text-3xl font-extrabold bg-gradient-to-r from-poker-accent to-poker-red bg-clip-text text-transparent">
          Private GTO Wizard
        </h1>
        <div className="flex gap-4 items-center">
          <button 
            onClick={() => setIsLiveSolver(!isLiveSolver)}
            className={`px-4 py-2 rounded-lg text-xs font-bold transition-all ${isLiveSolver ? 'bg-poker-green text-poker-dark' : 'bg-slate-700 text-slate-300'}`}
          >
            {isLiveSolver ? 'LIVE SOLVER ACTIVE' : 'USE LIVE SOLVER'}
          </button>
          <div className="px-4 py-2 bg-slate-800 rounded-lg border border-slate-700 text-xs font-mono">
            Rake: 5% | 100BB
          </div>
        </div>
      </header>

      <main className="w-full max-w-6xl grid grid-cols-1 lg:grid-cols-12 gap-8 h-fit">
        <div className="lg:col-span-7 flex flex-col gap-6">
          <section className="bg-glass p-4 rounded-2xl border border-white/5 shadow-xl">
            <StrategyMatrix 
              nodes={mockNodes} 
              onHandSelect={setSelectedHand}
              selectedHand={selectedHand}
            />
          </section>
        </div>

        <div className="lg:col-span-5 flex flex-col gap-6">
          <DecisionTree 
            path={path}
            actions={['Fold', 'Call', 'Raise 3x', 'Raise 5x', 'All-In']}
            onActionClick={(action) => setPath([...path, action])}
            onBreadcrumbClick={(idx) => setPath(path.slice(0, idx + 1))}
          />

          <section className="bg-glass p-6 rounded-2xl border border-white/5 shadow-xl flex-1 min-h-[300px]">
            <h2 className="text-xl font-bold mb-4 text-slate-400">Hand Strategy</h2>
            {selectedHand ? (
              <div className="flex flex-col gap-6">
                <div className="text-4xl font-mono font-bold text-white">{selectedHand}</div>
                <div className="grid grid-cols-2 gap-4">
                  <div className="p-4 bg-slate-800/50 rounded-xl border border-slate-700">
                    <div className="text-xs text-slate-500 uppercase mb-1">EV</div>
                    <div className="text-2xl font-mono text-poker-gold font-bold">+4.52</div>
                  </div>
                  <div className="p-4 bg-slate-800/50 rounded-xl border border-slate-700">
                    <div className="text-xs text-slate-500 uppercase mb-1">Equity</div>
                    <div className="text-2xl font-mono text-poker-green font-bold">52.4%</div>
                  </div>
                </div>
                <div className="space-y-3">
                  {Object.entries(mockNodes.find(n => n.hand === selectedHand)?.actions || {}).map(([action, freq]) => (
                    <div key={action} className="relative h-10 bg-slate-900 rounded-lg overflow-hidden border border-slate-800">
                      <div 
                        className="absolute inset-y-0 left-0 bg-poker-accent opacity-30 transition-all duration-500"
                        style={{ width: `${freq * 100}%` }}
                      />
                      <div className="relative h-full flex justify-between items-center px-4 font-bold text-sm">
                        <span className="uppercase">{action}</span>
                        <span className="font-mono">{(freq * 100).toFixed(1)}%</span>
                      </div>
                    </div>
                  ))}
                </div>
              </div>
            ) : (
              <div className="h-full flex items-center justify-center text-slate-500 text-center italic">
                Select a hand from the matrix to see strategy details
              </div>
            )}
          </section>
        </div>
      </main>

      <footer className="w-full max-w-6xl mt-auto py-8 text-center text-slate-600 text-xs border-t border-slate-800">
        &copy; 2024 Private GTO Wizard | Powered by postflop-solver WASM
      </footer>
    </div>
  )
}

export default App
