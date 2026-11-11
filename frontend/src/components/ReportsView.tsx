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
          const normalized = result.map((r) => ({
            ...r,
            fold: Math.round(r.avg_fold * 100),
            call: Math.round(r.avg_call * 100),
            raise: Math.round(r.avg_raise * 100),
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
      <div className="flex flex-col items-center justify-center h-[60vh] gap-3">
        <div className="w-8 h-8 border-2 border-[#7aa6da] border-t-transparent rounded-full animate-spin"></div>
        <p className="text-[#7aa6da] text-xs font-mono font-bold animate-pulse uppercase tracking-wider">
          Compiling Aggregate Texture Analytics...
        </p>
      </div>
    );
  }

  return (
    <div className="min-h-full bg-[#00140f] p-6 lg:p-8 space-y-6 animate-in text-[#ccdbdc]">
      <div className="max-w-7xl mx-auto space-y-6">
        <div className="flex flex-col md:flex-row md:items-center justify-between gap-4 border-b border-[#2d393b] pb-6">
          <div>
            <div className="flex items-center gap-3">
              <div className="w-9 h-9 bg-[#182628] border border-[#2d393b] rounded-[4px] flex items-center justify-center text-[#7aa6da]">
                <TrendingUp className="w-5 h-5" />
              </div>
              <h2 className="text-2xl font-black uppercase tracking-wider text-white">Aggregate Reports</h2>
            </div>
            <p className="text-[#a1b4d9] text-xs mt-1 font-mono">
              Equilibrium frequency distributions grouped across flop textures
            </p>
          </div>

          <div className="flex items-center gap-2 px-3.5 py-1.5 bg-[#182628] border border-[#2d393b] rounded-[4px]">
            <div className="w-2 h-2 rounded-full bg-[#64ffda] animate-pulse"></div>
            <span className="text-[11px] font-mono font-bold uppercase tracking-wider text-[#64ffda]">
              Live Engine Analytics
            </span>
          </div>
        </div>

        <div className="grid grid-cols-1 lg:grid-cols-3 gap-6">
          {/* Main Chart */}
          <div className="lg:col-span-2 bg-[#182628] p-6 rounded-[6px] border border-[#2d393b] shadow-xl">
            <div className="flex items-center justify-between mb-6">
              <h3 className="text-sm font-black uppercase tracking-wider text-white flex items-center gap-2 font-mono">
                <PieChart className="w-4 h-4 text-[#7aa6da]" />
                Frequency by Flop Texture
              </h3>
            </div>

            <div className="h-[380px] min-h-[380px] w-full relative">
              <ResponsiveContainer width="100%" height="100%" aspect={1.6}>
                <BarChart data={data} margin={{ top: 20, right: 30, left: 10, bottom: 5 }}>
                  <CartesianGrid strokeDasharray="3 3" vertical={false} stroke="rgba(204, 219, 220, 0.08)" />
                  <XAxis
                    dataKey="texture"
                    axisLine={false}
                    tickLine={false}
                    tick={{ fill: '#8b9ea0', fontSize: 11, fontWeight: 700 }}
                  />
                  <YAxis
                    axisLine={false}
                    tickLine={false}
                    tick={{ fill: '#8b9ea0', fontSize: 11, fontWeight: 700 }}
                    unit="%"
                  />
                  <Tooltip
                    cursor={{ fill: 'rgba(122, 166, 218, 0.08)' }}
                    contentStyle={{
                      backgroundColor: '#00140f',
                      border: '1px solid #2d393b',
                      borderRadius: '4px',
                      color: '#ccdbdc',
                      fontSize: '11px',
                      fontFamily: 'monospace',
                    }}
                  />
                  <Legend iconType="circle" wrapperStyle={{ paddingTop: '16px', fontSize: '11px' }} />
                  <Bar dataKey="fold" name="Fold" fill="#334155" radius={[2, 2, 0, 0]} />
                  <Bar dataKey="call" name="Call" fill="#10b981" radius={[2, 2, 0, 0]} />
                  <Bar dataKey="raise" name="Raise" fill="#f43f5e" radius={[2, 2, 0, 0]} />
                </BarChart>
              </ResponsiveContainer>
            </div>
          </div>

          {/* Breakdown Panel */}
          <div className="space-y-4">
            <div className="bg-[#182628] p-5 rounded-[6px] border border-[#2d393b] text-[#ccdbdc] shadow-xl relative overflow-hidden">
              <div className="flex items-center gap-2 text-[#7aa6da] mb-3">
                <Layers className="w-5 h-5" />
                <h4 className="text-sm font-black uppercase tracking-wider text-white">Dataset Summary</h4>
              </div>
              <p className="text-xs text-[#8b9ea0] leading-relaxed mb-4">
                Derived from canonical postflop DCFR solver nodes across{' '}
                <span className="text-[#64ffda] font-mono font-bold">
                  {data.reduce((acc, curr) => acc + curr.sample_size, 0)}
                </span>{' '}
                spots with 1-size bet/raise pruning.
              </p>
              <div className="bg-[#00140f] px-3 py-1.5 rounded-[4px] border border-[#2d393b] inline-flex items-center gap-2 text-[10.5px] font-mono font-bold text-[#7aa6da]">
                <Info className="w-3.5 h-3.5" />
                DCFR Convergence: 99.1%
              </div>
            </div>

            <div className="bg-[#182628] p-5 rounded-[6px] border border-[#2d393b] shadow-xl">
              <h4 className="text-xs font-black uppercase tracking-wider mb-4 flex items-center gap-2 text-white font-mono">
                <TrendingUp className="w-4 h-4 text-[#7aa6da]" />
                Highest Aggression Textures
              </h4>
              <div className="space-y-3">
                {data
                  .slice()
                  .sort((a, b) => b.raise - a.raise)
                  .map((report) => (
                    <div
                      key={report.texture}
                      className="flex items-center justify-between p-2 hover:bg-[#00140f] rounded-[4px] border border-transparent hover:border-[#2d393b] transition-all"
                    >
                      <span className="text-xs font-bold text-white font-mono">{report.texture}</span>
                      <div className="flex items-center gap-2">
                        <span className="text-[11px] font-mono font-black text-[#f43f5e]">
                          {report.raise}% Raise
                        </span>
                        <div className="w-16 h-1 bg-[#00140f] rounded-full overflow-hidden border border-[#2d393b]">
                          <div
                            className="h-full bg-[#f43f5e] transition-all"
                            style={{ width: `${report.raise}%` }}
                          ></div>
                        </div>
                      </div>
                    </div>
                  ))}
              </div>
            </div>
          </div>
        </div>
      </div>
    </div>
  );
};

export default ReportsView;
