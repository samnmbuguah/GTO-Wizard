import React from 'react';
import { Database, Search } from 'lucide-react';

const LibraryView: React.FC = () => {
  const spots = [
    { name: '6-Max Cash 100bb', categories: ['Preflop', 'Postflop'], solutions: 1240 },
    { name: 'MTT 40bb-60bb', categories: ['Preflop', 'Push/Fold'], solutions: 850 },
    { name: 'Heads Up 100bb', categories: ['Simplified', 'GTO'], solutions: 420 },
  ];

  return (
    <div className="space-y-8 animate-in mx-auto max-w-7xl">
      <div className="flex flex-col md:flex-row md:items-center justify-between gap-4">
        <div>
          <h2 className="text-2xl font-bold tracking-tight">Solution Library</h2>
          <p className="text-muted text-sm mt-1">Explore and analyze thousands of GTO solutions.</p>
        </div>
        <div className="relative">
          <Search className="absolute left-3 top-1/2 -translate-y-1/2 w-4 h-4 text-muted" />
          <input 
            type="text" 
            placeholder="Search spots..." 
            className="pl-10 pr-4 py-2 bg-card border border-border rounded-xl text-sm focus:ring-2 focus:ring-indigo-500 outline-none transition-all w-full md:w-64"
          />
        </div>
      </div>

      <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-3 gap-6">
        {spots.map((spot, i) => (
          <div key={i} className="group bg-card p-6 rounded-2xl border border-border hover:border-indigo-500/50 shadow-xl transition-all hover:-translate-y-1 cursor-pointer">
            <div className="w-10 h-10 bg-indigo-500/10 rounded-lg flex items-center justify-center text-indigo-400 mb-4 group-hover:bg-indigo-500 group-hover:text-white transition-all">
              <Database className="w-5 h-5" />
            </div>
            <h3 className="font-bold mb-2">{spot.name}</h3>
            <div className="flex flex-wrap gap-2 mb-4">
              {spot.categories.map(cat => (
                <span key={cat} className="px-2 py-0.5 bg-background text-[10px] font-bold text-muted rounded uppercase border border-border">
                  {cat}
                </span>
              ))}
            </div>
            <div className="flex justify-between items-center text-xs text-muted border-t border-border/50 pt-4">
              <span>{spot.solutions} Solutions</span>
              <span className="text-indigo-400 font-semibold group-hover:underline">Browse →</span>
            </div>
          </div>
        ))}
      </div>
    </div>
  );
};

export default LibraryView;
