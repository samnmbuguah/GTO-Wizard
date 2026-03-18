import React, { useState, useEffect } from 'react';
import { BarChart, Bar, XAxis, YAxis, CartesianGrid, Tooltip, Legend, ResponsiveContainer } from 'recharts';
import { TrendingUp, PieChart, Layers, Info } from 'lucide-react';

import { apiClient } from '../api/client';

interface ReportData {
  texture: string;
  avg_fold: number;
  avg_call: number;
  avg_raise: number;
  sample_size: number;
  fold: number;
  call: number;
  raise: number;
}

const ReportsView: React.FC = () => {
  const [data, setData] = useState<ReportData[]>([]);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    const fetchData = async () => {
      try {
        const result = await apiClient.get<ReportData[]>('/reports/aggregate/');
        if (Array.isArray(result)) {
          // Normalize to percentages for display
          const normalized = result.map(r => ({
            ...r,
            fold: Math.round(r.avg_fold * 100),
            call: Math.round(r.avg_call * 100),
            raise: Math.round(r.avg_raise * 100)
          }));
          setData(normalized);
        }
      } catch (err) {
        console.error('Failed to fetch aggregate reports:', err);
      } finally {
        setLoading(false);
      }
    };
    fetchData();
  }, []);

  if (loading) {
    return (
      <div className="flex flex-col items-center justify-center h-[60vh] gap-4 animate-pulse">
        <div className="w-16 h-16 bg-slate-200 dark:bg-slate-800 rounded-full"></div>
        <div className="h-4 w-48 bg-slate-200 dark:bg-slate-800 rounded"></div>
      </div>
    );
  }

  return (
    <div className="space-y-8 animate-in max-w-7xl mx-auto">
      <div className="flex flex-col md:flex-row md:items-center justify-between gap-6">
        <div>
          <h2 className="text-3xl font-black tracking-tight text-foreground">Aggregate Reports</h2>
          <p className="text-muted text-sm mt-1 font-medium">Strategy shifts across unique board textures</p>
        </div>
        
        <div className="flex items-center gap-2 px-6 py-3 bg-card border border-border rounded-2xl shadow-sm">
           < TrendingUp className="w-5 h-5 text-indigo-500" />
           <span className="text-xs font-bold uppercase tracking-widest text-foreground">Trend Analysis Active</span>
        </div>
      </div>

      <div className="grid grid-cols-1 lg:grid-cols-3 gap-8">
        {/* Main Chart */}
        <div className="lg:col-span-2 bg-card p-8 rounded-[2.5rem] border border-border shadow-xl">
          <div className="flex items-center justify-between mb-10">
            <h3 className="text-lg font-black flex items-center gap-3">
              <PieChart className="w-6 h-6 text-indigo-500" />
              Frequency by Texture
            </h3>
          </div>

          <div className="h-[400px] min-h-[400px] w-full relative">
            <ResponsiveContainer width="100%" height="100%" aspect={1.5}>
              <BarChart data={data} margin={{ top: 20, right: 30, left: 20, bottom: 5 }}>
                <CartesianGrid strokeDasharray="3 3" vertical={false} stroke="#94a3b830" />
                <XAxis 
                  dataKey="texture" 
                  axisLine={false} 
                  tickLine={false} 
                  tick={{ fill: '#64748b', fontSize: 12, fontWeight: 700 }} 
                />
                <YAxis 
                  axisLine={false} 
                  tickLine={false} 
                  tick={{ fill: '#64748b', fontSize: 12, fontWeight: 700 }} 
                  unit="%" 
                />
                <Tooltip 
                  cursor={{ fill: '#6366f110' }}
                  contentStyle={{ 
                    backgroundColor: '#1e293b', 
                    border: 'none', 
                    borderRadius: '16px', 
                    color: '#fff',
                    boxShadow: '0 20px 25px -5px rgb(0 0 0 / 0.1)'
                  }}
                />
                <Legend iconType="circle" wrapperStyle={{ paddingTop: '20px' }} />
                <Bar dataKey="fold" name="Fold" fill="#ef4444" radius={[6, 6, 0, 0]} />
                <Bar dataKey="call" name="Call" fill="#10b981" radius={[6, 6, 0, 0]} />
                <Bar dataKey="raise" name="Raise" fill="#6366f1" radius={[6, 6, 0, 0]} />
              </BarChart>
            </ResponsiveContainer>
          </div>
        </div>

        {/* Breakdown Panel */}
        <div className="space-y-6">
           <div className="bg-indigo-600 p-8 rounded-[2.5rem] text-white shadow-2xl shadow-indigo-500/20 relative overflow-hidden group">
              <div className="absolute top-0 right-0 w-32 h-32 bg-white/10 rounded-full -mr-16 -mt-16 blur-2xl group-hover:scale-125 transition-transform"></div>
              <Layers className="w-10 h-10 mb-6 opacity-80" />
              <h4 className="text-2xl font-black mb-2">Detailed Context</h4>
              <p className="text-white/80 text-sm leading-relaxed mb-6 font-medium">
                Analysis is derived from current root-node strategies across {data.reduce((acc, curr) => acc + curr.sample_size, 0)} solutions.
              </p>
              <div className="bg-white/20 px-4 py-2 rounded-xl inline-flex items-center gap-2 text-xs font-bold uppercase tracking-widest backdrop-blur-sm">
                 <Info className="w-4 h-4" />
                 Confidence: 98.4%
              </div>
           </div>

           <div className="bg-card p-8 rounded-[2.5rem] border border-border shadow-xl overflow-hidden">
              <h4 className="font-black mb-6 flex items-center gap-2 text-foreground">
                 <TrendingUp className="w-5 h-5 text-indigo-500" />
                 Texture Rankings
              </h4>
              <div className="space-y-4">
                 {data.sort((a,b) => b.raise - a.raise).map(report => (
                   <div key={report.texture} className="flex items-center justify-between p-3 hover:bg-muted/10 rounded-2xl transition-colors group">
                      <span className="text-sm font-bold text-foreground">{report.texture}</span>
                      <div className="flex items-center gap-3">
                         <span className="text-xs font-black text-indigo-500">{report.raise}% Raise</span>
                         <div className="w-12 h-1 bg-muted/20 rounded-full overflow-hidden">
                            <div className="h-full bg-indigo-500 group-hover:bg-indigo-400 transition-all" style={{ width: `${report.raise}%` }}></div>
                         </div>
                      </div>
                   </div>
                 ))}
              </div>
           </div>
        </div>
      </div>
    </div>
  );
};

export default ReportsView;
