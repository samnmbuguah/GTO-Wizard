import React from 'react';
import { Shield, CreditCard, Mail } from 'lucide-react';

const AccountView: React.FC = () => {
  return (
    <div className="max-w-4xl mx-auto space-y-8 animate-in">
      <div>
        <h2 className="text-2xl font-bold tracking-tight">Account Settings</h2>
        <p className="text-muted text-sm mt-1">Manage your profile and subscription details.</p>
      </div>

      <div className="grid grid-cols-1 md:grid-cols-3 gap-8">
        <div className="md:col-span-2 space-y-6">
          <section className="bg-card p-6 md:p-8 rounded-2xl border border-border shadow-xl space-y-6">
            <div className="flex items-center gap-4 pb-6 border-b border-border">
              <div className="w-16 h-16 rounded-full bg-indigo-500 flex items-center justify-center text-2xl font-bold text-white shadow-lg shadow-indigo-500/20 shrink-0">
                JD
              </div>
              <div>
                <h3 className="font-bold text-lg">Samuel Mbugua</h3>
                <p className="text-sm text-muted">Premium Member since Oct 2025</p>
              </div>
              <button className="ml-auto px-4 py-2 border border-border rounded-lg text-xs font-bold hover:bg-background transition-colors hidden sm:block">
                Edit Profile
              </button>
            </div>

            <div className="grid grid-cols-1 sm:grid-cols-2 gap-6">
              <div className="space-y-1">
                <label className="text-[10px] font-bold text-muted uppercase tracking-widest">Email Address</label>
                <div className="flex items-center gap-2 text-sm">
                  <Mail className="w-4 h-4 text-muted" />
                  <span>samuel@example.com</span>
                </div>
              </div>
              <div className="space-y-1">
                <label className="text-[10px] font-bold text-muted uppercase tracking-widest">Security</label>
                <div className="flex items-center gap-2 text-sm">
                  <Shield className="w-4 h-4 text-emerald-500" />
                  <span className="text-emerald-500 font-medium">2FA Enabled</span>
                </div>
              </div>
            </div>
          </section>

          <section className="bg-card p-6 md:p-8 rounded-2xl border border-border shadow-xl">
             <div className="flex items-center justify-between mb-6">
                <h3 className="font-bold">Subscription Plan</h3>
                <span className="px-2 py-1 bg-indigo-500/10 text-indigo-400 text-[10px] font-bold border border-indigo-500/20 rounded uppercase">Active</span>
             </div>
             <div className="flex items-center gap-4 p-4 bg-background/50 rounded-xl border border-border">
                <CreditCard className="w-5 h-5 text-indigo-400" />
                <div className="flex-1">
                  <p className="text-sm font-bold">GTO Wiz Premium - Yearly</p>
                  <p className="text-xs text-muted">Next billing date: Oct 12, 2026</p>
                </div>
                <button className="text-xs font-bold text-indigo-400 hover:underline">Manage</button>
             </div>
          </section>
        </div>

        <div className="space-y-6">
          <div className="bg-indigo-600 p-6 rounded-2xl text-white shadow-xl shadow-indigo-600/10">
            <h4 className="font-bold mb-2">Upgrade to Elite</h4>
            <p className="text-xs opacity-90 leading-relaxed mb-4">Get access to custom solver uploads and advanced node locking features.</p>
            <button className="w-full py-2 bg-white text-indigo-600 rounded-lg text-xs font-bold shadow-lg active:scale-95 transition-all">
              Learn More
            </button>
          </div>
        </div>
      </div>
    </div>
  );
};

export default AccountView;
