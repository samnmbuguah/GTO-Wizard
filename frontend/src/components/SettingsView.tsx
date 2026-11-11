import React, { useState } from 'react';
import { 
  Bell, 
  Globe, 
  Eye, 
  Sliders,
  Zap,
  Save,
  Settings
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
    <div className="min-h-full bg-[#00140f] p-6 lg:p-8 space-y-6 animate-in text-[#ccdbdc]">
      <div className="max-w-4xl mx-auto space-y-6">
        <div className="border-b border-[#2d393b] pb-4">
          <div className="flex items-center gap-3">
            <div className="w-9 h-9 bg-[#182628] border border-[#2d393b] rounded-[4px] flex items-center justify-center text-[#7aa6da]">
              <Settings className="w-5 h-5" />
            </div>
            <h2 className="text-2xl font-black uppercase tracking-wider text-white">System & Solver Settings</h2>
          </div>
          <p className="text-[#a1b4d9] text-xs mt-1 font-mono">
            Configure live depth-limited CFR solver engine parameters, rake structure, and workstation defaults
          </p>
        </div>

        <div className="space-y-4">
          {/* Real-time Solver Engine Preferences */}
          <section className="bg-[#182628] rounded-[6px] border border-[#2d393b] overflow-hidden shadow-xl">
            <div className="p-4 border-b border-[#2d393b] bg-[#00140f]/60 font-bold text-xs uppercase tracking-wider text-[#7aa6da] flex items-center justify-between font-mono">
              <span className="flex items-center gap-2">
                <Sliders className="w-4 h-4" /> Live DCFR Solver Parameters
              </span>
              <span className="flex items-center gap-1 text-[10px] text-[#64ffda] bg-[#64ffda]/10 px-2 py-0.5 rounded-[3px] border border-[#64ffda]/30">
                <Zap className="w-3 h-3" /> Sub-30ms DCFR Engine
              </span>
            </div>

            <div className="p-5 space-y-4">
              <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
                <div>
                  <label className="block text-xs font-bold text-[#8b9ea0] uppercase tracking-wider mb-1 font-mono">
                    Default Rake Percentage (%)
                  </label>
                  <input 
                    type="number"
                    step="0.1"
                    min="0"
                    max="15"
                    value={rakePercent}
                    onChange={(e) => setRakePercent(parseFloat(e.target.value) || 0)}
                    className="w-full bg-[#00140f] border border-[#2d393b] rounded-[4px] px-3 py-2 text-sm text-white focus:outline-none focus:border-[#7aa6da] font-mono"
                  />
                  <p className="text-[11px] text-[#8b9ea0] mt-1">Calibrates pot elasticity and preflop baseline ranges.</p>
                </div>

                <div>
                  <label className="block text-xs font-bold text-[#8b9ea0] uppercase tracking-wider mb-1 font-mono">
                    Default Rake Cap (Big Blinds)
                  </label>
                  <input 
                    type="number"
                    step="0.1"
                    min="0"
                    max="10"
                    value={rakeCap}
                    onChange={(e) => setRakeCap(parseFloat(e.target.value) || 0)}
                    className="w-full bg-[#00140f] border border-[#2d393b] rounded-[4px] px-3 py-2 text-sm text-white focus:outline-none focus:border-[#7aa6da] font-mono"
                  />
                  <p className="text-[11px] text-[#8b9ea0] mt-1">Maximum rake extracted per spot in deep stack play.</p>
                </div>
              </div>

              <div>
                <label className="block text-xs font-bold text-[#8b9ea0] uppercase tracking-wider mb-1 font-mono">
                  Candidate Bet Sizing Grid (Pot Fractions)
                </label>
                <input 
                  type="text"
                  value={preferredSizes}
                  onChange={(e) => setPreferredSizes(e.target.value)}
                  placeholder="0.33, 0.5, 0.75"
                  className="w-full bg-[#00140f] border border-[#2d393b] rounded-[4px] px-3 py-2 text-sm text-white focus:outline-none focus:border-[#7aa6da] font-mono"
                />
                <p className="text-[11px] text-[#8b9ea0] mt-1">Single-size pruning algorithm dynamically selects the highest EV sizing.</p>
              </div>

              <div className="flex justify-end pt-2 border-t border-[#2d393b]">
                <button
                  onClick={handleSaveSolverSettings}
                  className="flex items-center gap-2 bg-[#7aa6da] hover:bg-[#6894c7] text-[#00140f] font-black px-4 py-2 rounded-[4px] text-xs uppercase tracking-wider transition-all cursor-pointer shadow-md active:scale-95"
                >
                  <Save className="w-3.5 h-3.5" />
                  {saveSuccess ? 'Saved Settings!' : 'Save Solver Defaults'}
                </button>
              </div>
            </div>
          </section>

          <section className="bg-[#182628] rounded-[6px] border border-[#2d393b] overflow-hidden shadow-xl">
            <div className="p-4 border-b border-[#2d393b] bg-[#00140f]/60 font-bold text-xs uppercase tracking-wider text-[#8b9ea0] font-mono">
              Workstation Preferences
            </div>
            
            <div className="divide-y divide-[#2d393b]">
              <div className="p-4 flex items-center justify-between hover:bg-[#00140f]/40 transition-colors">
                <div className="flex items-center gap-3">
                  <Globe className="w-4 h-4 text-[#7aa6da]" />
                  <div>
                    <p className="text-xs font-bold text-white font-mono">Deck Theme</p>
                    <p className="text-[11px] text-[#8b9ea0]">4-Color Standard (♥ Red, ♦ Blue, ♣ Green, ♠ Dark)</p>
                  </div>
                </div>
                <span className="text-[10px] font-mono font-bold text-[#64ffda] bg-[#64ffda]/10 px-2 py-0.5 rounded-[3px] border border-[#64ffda]/30">
                  Active
                </span>
              </div>

              <div className="p-4 flex items-center justify-between hover:bg-[#00140f]/40 transition-colors">
                <div className="flex items-center gap-3">
                  <Bell className="w-4 h-4 text-[#7aa6da]" />
                  <div>
                    <p className="text-xs font-bold text-white font-mono">Convergence Telemetry</p>
                    <p className="text-[11px] text-[#8b9ea0]">Display live solver latency, dEV, and OOP/IP counterfactual values</p>
                  </div>
                </div>
                <span className="text-[10px] font-mono font-bold text-[#64ffda] bg-[#64ffda]/10 px-2 py-0.5 rounded-[3px] border border-[#64ffda]/30">
                  Enabled
                </span>
              </div>

              <div className="p-4 flex items-center justify-between hover:bg-[#00140f]/40 transition-colors">
                <div className="flex items-center gap-3">
                  <Eye className="w-4 h-4 text-[#7aa6da]" />
                  <div>
                    <p className="text-xs font-bold text-white font-mono">Cell Hover EV Inspector</p>
                    <p className="text-[11px] text-[#8b9ea0]">Highlight action frequencies and EV overlay on mouseover in 13x13 matrix</p>
                  </div>
                </div>
                <span className="text-[10px] font-mono font-bold text-[#64ffda] bg-[#64ffda]/10 px-2 py-0.5 rounded-[3px] border border-[#64ffda]/30">
                  Enabled
                </span>
              </div>
            </div>
          </section>
        </div>
      </div>
    </div>
  );
};

export default SettingsView;
