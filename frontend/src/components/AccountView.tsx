import React from 'react';
import { Shield, CreditCard, Mail, User } from 'lucide-react';

const AccountView: React.FC = () => {
  return (
    <div className="min-h-full bg-[#00140f] p-6 lg:p-8 space-y-6 animate-in text-[#ccdbdc]">
      <div className="max-w-4xl mx-auto space-y-6">
        <div className="border-b border-[#2d393b] pb-4">
          <div className="flex items-center gap-3">
            <div className="w-9 h-9 bg-[#182628] border border-[#2d393b] rounded-[4px] flex items-center justify-center text-[#7aa6da]">
              <User className="w-5 h-5" />
            </div>
            <h2 className="text-2xl font-black uppercase tracking-wider text-white">Account Profile</h2>
          </div>
          <p className="text-[#a1b4d9] text-xs mt-1 font-mono">
            Manage your solver access credentials and subscription tier
          </p>
        </div>

        <div className="grid grid-cols-1 md:grid-cols-3 gap-6">
          <div className="md:col-span-2 space-y-4">
            <section className="bg-[#182628] p-6 rounded-[6px] border border-[#2d393b] shadow-xl space-y-5">
              <div className="flex items-center gap-4 pb-5 border-b border-[#2d393b]">
                <div className="w-14 h-14 rounded-[4px] bg-[#00140f] border border-[#2d393b] flex items-center justify-center text-lg font-black font-mono text-[#7aa6da] shrink-0">
                  SM
                </div>
                <div>
                  <h3 className="font-black text-white text-base">Samuel Mbugua</h3>
                  <p className="text-xs text-[#8b9ea0] font-mono">Enterprise Solver License (Active)</p>
                </div>
                <button
                  onClick={() => alert('Profile updates are synchronized with your active authentication session.')}
                  className="ml-auto px-3 py-1.5 bg-[#00140f] border border-[#2d393b] hover:border-[#7aa6da] rounded-[4px] text-xs font-bold text-[#ccdbdc] hover:text-white transition-all cursor-pointer hidden sm:block"
                >
                  Edit Profile
                </button>
              </div>

              <div className="grid grid-cols-1 sm:grid-cols-2 gap-4">
                <div className="space-y-1 bg-[#00140f] p-3 rounded-[4px] border border-[#2d393b]">
                  <label className="text-[10px] font-bold text-[#8b9ea0] uppercase tracking-wider font-mono">
                    Email Address
                  </label>
                  <div className="flex items-center gap-2 text-xs text-white font-mono">
                    <Mail className="w-3.5 h-3.5 text-[#7aa6da]" />
                    <span>samuel@example.com</span>
                  </div>
                </div>
                <div className="space-y-1 bg-[#00140f] p-3 rounded-[4px] border border-[#2d393b]">
                  <label className="text-[10px] font-bold text-[#8b9ea0] uppercase tracking-wider font-mono">
                    Security Layer
                  </label>
                  <div className="flex items-center gap-2 text-xs font-mono">
                    <Shield className="w-3.5 h-3.5 text-[#10b981]" />
                    <span className="text-[#10b981] font-bold">Token Auth Validated</span>
                  </div>
                </div>
              </div>
            </section>

            <section className="bg-[#182628] p-6 rounded-[6px] border border-[#2d393b] shadow-xl">
              <div className="flex items-center justify-between mb-4">
                <h3 className="font-black text-white text-sm uppercase tracking-wider font-mono">
                  Subscription Status
                </h3>
                <span className="px-2 py-0.5 bg-emerald-500/10 text-emerald-400 text-[10px] font-mono font-bold border border-emerald-500/20 rounded-[3px] uppercase">
                  UNLIMITED DAEMON
                </span>
              </div>
              <div className="flex items-center gap-3 p-3.5 bg-[#00140f] rounded-[4px] border border-[#2d393b]">
                <CreditCard className="w-5 h-5 text-[#7aa6da]" />
                <div className="flex-1">
                  <p className="text-xs font-bold text-white font-mono">GTO Pro Suite — Sub-500ms CFR Engine</p>
                  <p className="text-[11px] text-[#8b9ea0]">Dedicated VM Daemon (port 9998)</p>
                </div>
                <span className="text-xs font-mono font-bold text-[#64ffda]">Active</span>
              </div>
            </section>
          </div>

          <div className="space-y-4">
            <div className="bg-[#182628] p-5 rounded-[6px] border border-[#2d393b] shadow-xl">
              <h4 className="font-black text-sm uppercase tracking-wider text-white mb-2 font-mono">
                Engine Capabilities
              </h4>
              <p className="text-xs text-[#8b9ea0] leading-relaxed mb-4">
                Direct access to high-performance Rust DCFR solver daemon, custom rake formulas, and batch leaf generation.
              </p>
              <div className="space-y-2 font-mono text-[11px]">
                <div className="flex justify-between text-[#8b9ea0]">
                  <span>Solve Latency</span>
                  <span className="text-[#64ffda] font-bold">&lt; 30ms</span>
                </div>
                <div className="flex justify-between text-[#8b9ea0]">
                  <span>Preflop Ranges</span>
                  <span className="text-white font-bold">100bb / 150bb</span>
                </div>
                <div className="flex justify-between text-[#8b9ea0]">
                  <span>Tree Geometry</span>
                  <span className="text-white font-bold">1-size Pruned</span>
                </div>
              </div>
            </div>
          </div>
        </div>
      </div>
    </div>
  );
};

export default AccountView;
