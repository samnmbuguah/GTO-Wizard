import React, { useState } from 'react';
import { 
  Bell, 
  Globe, 
  Eye, 
  Sliders,
  Zap,
  Save
} from 'lucide-react';

const SettingsView: React.FC = () => {
  const [rakePercent, setRakePercent] = useState<number>(() => {
    return parseFloat(localStorage.getItem('gto_default_rake_percent') || '5.0');
  });
  const [rakeCap, setRakeCap] = useState<number>(() => {
    return parseFloat(localStorage.getItem('gto_default_rake_cap') || '3.0');
  });
  const [preferredSizes, setPreferredSizes] = useState<string>(() => {
    return localStorage.getItem('gto_default_sizes') || '0.33, 0.5, 0.75';
  });
  const [saveSuccess, setSaveSuccess] = useState(false);

  const handleSaveSolverSettings = () => {
    localStorage.setItem('gto_default_rake_percent', rakePercent.toString());
    localStorage.setItem('gto_default_rake_cap', rakeCap.toString());
    localStorage.setItem('gto_default_sizes', preferredSizes);
    setSaveSuccess(true);
    setTimeout(() => setSaveSuccess(false), 2000);
  };

  return (
    <div className="max-w-4xl mx-auto space-y-8 animate-in">
      <div>
        <h2 className="text-2xl font-bold tracking-tight">System & Solver Settings</h2>
        <p className="text-muted text-sm mt-1">Configure your live depth-limited CFR solver engine parameters, rake structure, and UI preferences.</p>
      </div>

      <div className="space-y-6">
        {/* Real-time Solver Engine Preferences */}
        <section className="bg-card rounded-2xl border border-border overflow-hidden shadow-xl">
          <div className="p-6 border-b border-border bg-background/20 font-bold text-xs uppercase tracking-widest text-[#7aa6da] flex items-center justify-between">
            <span className="flex items-center gap-2">
              <Sliders className="w-4 h-4" /> Live Solver Parameters
            </span>
            <span className="flex items-center gap-1 text-[10px] text-yellow-400 bg-yellow-400/10 px-2 py-0.5 rounded border border-yellow-400/20">
              <Zap className="w-3 h-3" /> Sub-2s DLS Engine
            </span>
          </div>

          <div className="p-6 space-y-4">
            <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
              <div>
                <label className="block text-xs font-bold text-muted uppercase tracking-wider mb-1">
                  Default Rake Percentage (%)
                </label>
                <input 
                  type="number"
                  step="0.1"
                  min="0"
                  max="15"
                  value={rakePercent}
                  onChange={(e) => setRakePercent(parseFloat(e.target.value) || 0)}
                  className="w-full bg-background border border-border rounded-lg px-3 py-2 text-sm text-foreground focus:outline-none focus:border-indigo-500 font-mono"
                />
                <p className="text-[11px] text-muted mt-1">Morphes baseline preflop ranges and postflop pot elasticity.</p>
              </div>

              <div>
                <label className="block text-xs font-bold text-muted uppercase tracking-wider mb-1">
                  Default Rake Cap (Big Blinds)
                </label>
                <input 
                  type="number"
                  step="0.1"
                  min="0"
                  max="10"
                  value={rakeCap}
                  onChange={(e) => setRakeCap(parseFloat(e.target.value) || 0)}
                  className="w-full bg-background border border-border rounded-lg px-3 py-2 text-sm text-foreground focus:outline-none focus:border-indigo-500 font-mono"
                />
                <p className="text-[11px] text-muted mt-1">Cap constraint on max rake extracted per hand.</p>
              </div>
            </div>

            <div>
              <label className="block text-xs font-bold text-muted uppercase tracking-wider mb-1">
                Candidate Bet Sizing Grid (Pot Fractions)
              </label>
              <input 
                type="text"
                value={preferredSizes}
                onChange={(e) => setPreferredSizes(e.target.value)}
                placeholder="0.33, 0.5, 0.75"
                className="w-full bg-background border border-border rounded-lg px-3 py-2 text-sm text-foreground focus:outline-none focus:border-indigo-500 font-mono"
              />
              <p className="text-[11px] text-muted mt-1">Pruned to 1 optimal sizing during live depth-limited convergence.</p>
            </div>

            <div className="flex justify-end pt-2">
              <button
                onClick={handleSaveSolverSettings}
                className="flex items-center gap-2 bg-[#7aa6da] hover:bg-[#5a86ba] text-[#182628] font-black px-5 py-2.5 rounded-lg text-xs uppercase tracking-wider transition-all transform hover:scale-[1.02]"
              >
                <Save className="w-4 h-4" />
                {saveSuccess ? 'Saved Settings!' : 'Save Solver Defaults'}
              </button>
            </div>
          </div>
        </section>

        <section className="bg-card rounded-2xl border border-border overflow-hidden shadow-xl">
          <div className="p-6 border-b border-border bg-background/20 font-bold text-xs uppercase tracking-widest text-muted">Preferences</div>
          
          <div className="divide-y divide-border/50">
            <div className="p-6 flex items-center justify-between hover:bg-background/40 transition-colors cursor-pointer">
              <div className="flex items-center gap-4">
                <Globe className="w-5 h-5 text-muted" />
                <div>
                  <p className="text-sm font-semibold">Language</p>
                  <p className="text-xs text-muted">English (United States)</p>
                </div>
              </div>
              <button className="text-xs font-bold text-indigo-400">Change</button>
            </div>

            <div className="p-6 flex items-center justify-between hover:bg-background/40 transition-colors cursor-pointer">
              <div className="flex items-center gap-4">
                <Bell className="w-5 h-5 text-muted" />
                <div>
                  <p className="text-sm font-semibold">Notifications</p>
                  <p className="text-xs text-muted">Email and Desktop push notifications</p>
                </div>
              </div>
              <div className="flex items-center gap-2">
                 <div className="w-8 h-4 bg-indigo-500 rounded-full relative">
                    <div className="absolute right-0.5 top-0.5 w-3 h-3 bg-white rounded-full shadow-sm"></div>
                 </div>
              </div>
            </div>

            <div className="p-6 flex items-center justify-between hover:bg-background/40 transition-colors cursor-pointer">
              <div className="flex items-center gap-4">
                <Eye className="w-5 h-5 text-muted" />
                <div>
                  <p className="text-sm font-semibold">Privacy Mode</p>
                  <p className="text-xs text-muted">Hide stack sizes and names in solver shared links</p>
                </div>
              </div>
              <div className="flex items-center gap-2">
                 <div className="w-8 h-4 bg-muted/40 rounded-full relative">
                    <div className="absolute left-0.5 top-0.5 w-3 h-3 bg-white rounded-full shadow-sm"></div>
                 </div>
              </div>
            </div>
          </div>
        </section>

        <section className="bg-card rounded-2xl border border-border overflow-hidden shadow-xl">
          <div className="p-6 border-b border-border bg-background/20 font-bold text-xs uppercase tracking-widest text-red-500/80">Danger Zone</div>
          <div className="p-6 flex items-center justify-between">
            <div>
              <p className="text-sm font-semibold text-foreground">Delete Account</p>
              <p className="text-xs text-muted">Permanently delete your account and all associated data</p>
            </div>
            <button className="px-4 py-2 bg-red-500/10 text-red-500 border border-red-500/20 rounded-lg text-xs font-bold hover:bg-red-500 hover:text-white transition-all">
              Delete Account
            </button>
          </div>
        </section>
      </div>
    </div>
  );
};

export default SettingsView;

