import React from 'react';
import { 
  AreaChart, 
  Area, 
  XAxis, 
  YAxis, 
  CartesianGrid, 
  Tooltip, 
  ResponsiveContainer 
} from 'recharts';

const data = [
  { equity: 0, frequency: 5 },
  { equity: 10, frequency: 8 },
  { equity: 20, frequency: 15 },
  { equity: 30, frequency: 45 },
  { equity: 40, frequency: 60 },
  { equity: 50, frequency: 55 },
  { equity: 60, frequency: 30 },
  { equity: 70, frequency: 12 },
  { equity: 80, frequency: 8 },
  { equity: 90, frequency: 4 },
  { equity: 100, frequency: 2 },
];

const EquityChart: React.FC = () => {
  return (
    <div className="bg-card p-6 rounded-3xl border border-border shadow-xl backdrop-blur-sm animate-in">
      <div className="flex items-center gap-3 mb-6 pb-4 border-b border-border">
        <div className="w-1.5 h-6 bg-emerald-500 rounded-full shadow-lg shadow-emerald-500/20"></div>
        <h2 className="text-sm font-bold uppercase tracking-widest text-muted">Equity Distribution</h2>
      </div>

      <div className="h-[250px] min-h-[250px] w-full relative">
        <ResponsiveContainer width="100%" height="100%">
          <AreaChart
            data={data}
            margin={{ top: 10, right: 10, left: 0, bottom: 0 }}
          >
            <defs>
              <linearGradient id="colorEquity" x1="0" y1="0" x2="0" y2="1">
                <stop offset="5%" stopColor="#6366f1" stopOpacity={0.3}/>
                <stop offset="95%" stopColor="#6366f1" stopOpacity={0}/>
              </linearGradient>
            </defs>
            <CartesianGrid strokeDasharray="3 3" vertical={false} stroke="#334155" opacity={0.1} />
            <XAxis 
              dataKey="equity" 
              stroke="#94a3b8" 
              fontSize={10} 
              tickFormatter={(val) => `${val}%`}
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
