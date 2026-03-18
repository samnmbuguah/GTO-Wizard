import { useState, useEffect } from 'react';
import { DashboardLayout } from './components/DashboardLayout';
import StrategyMatrix from './components/StrategyMatrix';
import type { StrategyNode } from './types/poker';

function App() {
  const [nodes, setNodes] = useState<StrategyNode[]>([]);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    // Fetch test data from Django backend
    const fetchNodes = async () => {
      try {
        const response = await fetch('http://localhost:8000/api/nodes/?solution_id=1&path=root');
        const data = await response.json();
        setNodes(data);
      } catch (error) {
        console.error("Failed to fetch nodes:", error);
      } finally {
        setLoading(false);
      }
    };
    fetchNodes();
  }, []);

  return (
    <DashboardLayout>
      <div className="max-w-6xl mx-auto space-y-8 animate-in fade-in duration-700">
        <div className="grid grid-cols-1 lg:grid-cols-12 gap-8 items-start">
          <div className="lg:col-span-12">
            {loading ? (
              <div className="flex items-center justify-center p-20">
                <div className="w-12 h-12 border-4 border-indigo-500/30 border-t-indigo-500 rounded-full animate-spin"></div>
              </div>
            ) : (
              <StrategyMatrix nodes={nodes} onHandSelect={(hand) => console.log("Selected hand:", hand)} />
            )}
          </div>
        </div>
      </div>
    </DashboardLayout>
  );
}

export default App;
