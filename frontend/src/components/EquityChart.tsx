import { useState, useEffect } from 'react';
import { 
  AreaChart, 
  Area, 
  XAxis, 
  YAxis, 
  CartesianGrid, 
  Tooltip, 
  ResponsiveContainer 
} from 'recharts';
import { apiClient } from '../api/client';

interface EquityChartProps {
  solutionId?: string;
}

const EquityChart: React.FC<EquityChartProps> = ({ solutionId }) => {
  const [chartData, setChartData] = useState<any[]>([]);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    const fetchEquity = async () => {
      if (!solutionId) return;
      try {
        setLoading(true);
        const data = await apiClient.get<any[]>(`/solutions/${solutionId}/equity/`);
        setChartData(data);
      } catch (err) {
        console.error('Failed to fetch equity:', err);
      } finally {
        setLoading(false);
      }
    };
    fetchEquity();
  }, [solutionId]);

  if (loading) {
    return (
      <div className="h-[350px] flex items-center justify-center bg-card rounded-3xl border border-border">
         <div className="w-8 h-8 border-3 border-indigo-500 border-t-transparent rounded-full animate-spin"></div>
      </div>
    );
  }
  return (
    <div className="bg-card p-6 rounded-3xl border border-border shadow-xl backdrop-blur-sm animate-in">
      <div className="flex items-center gap-3 mb-6 pb-4 border-b border-border">
        <div className="w-1.5 h-6 bg-emerald-500 rounded-full shadow-lg shadow-emerald-500/20"></div>
        <h2 className="text-sm font-bold uppercase tracking-widest text-muted">Equity Distribution</h2>
      </div>

      <div className="h-full w-full min-h-[240px] relative">
        <ResponsiveContainer width="100%" height="100%">
          <AreaChart
            data={chartData}
            margin={{ top: 10, right: 10, left: -20, bottom: 0 }}
          >
            <defs>
              <linearGradient id="colorHero" x1="0" y1="0" x2="0" y2="1">
                <stop offset="5%" stopColor="#6366f1" stopOpacity={0.3}/>
                <stop offset="95%" stopColor="#6366f1" stopOpacity={0}/>
              </linearGradient>
              <linearGradient id="colorVillain" x1="0" y1="0" x2="0" y2="1">
                <stop offset="5%" stopColor="#ec4899" stopOpacity={0.2}/>
                <stop offset="95%" stopColor="#ec4899" stopOpacity={0}/>
              </linearGradient>
            </defs>
            <CartesianGrid strokeDasharray="3 3" vertical={false} stroke="#334155" opacity={0.1} />
            <XAxis 
              dataKey="bin" 
              stroke="#94a3b8" 
              fontSize={10} 
              axisLine={false}
              tickLine={false}
            />
            <YAxis 
              stroke="#94a3b8" 
              fontSize={10} 
              axisLine={false}
              tickLine={false}
              hide
            />
            <Tooltip 
              contentStyle={{ 
                backgroundColor: '#1e293b', 
                border: 'none', 
                borderRadius: '12px',
                fontSize: '12px',
                color: '#fff'
              }}
              cursor={{ stroke: '#6366f1', strokeWidth: 2 }}
            />
            <Area 
              type="monotone" 
              dataKey="frequency" 
              stroke="#6366f1" 
              strokeWidth={3}
              fillOpacity={1} 
              fill="url(#colorEquity)" 
            />
          </AreaChart>
        </ResponsiveContainer>
      </div>

      <div className="mt-6 grid grid-cols-2 gap-4">
        <div className="p-4 bg-background/50 rounded-2xl border border-border">
          <p className="text-[10px] text-muted uppercase font-bold mb-1">Mean Equity</p>
          <p className="text-lg font-black text-indigo-500">42.8%</p>
        </div>
        <div className="p-4 bg-background/50 rounded-2xl border border-border">
          <p className="text-[10px] text-muted uppercase font-bold mb-1">Equity Realization</p>
          <p className="text-lg font-black text-emerald-500">92%</p>
        </div>
      </div>
    </div>
  );
};

export default EquityChart;
