import React from 'react';
import { 
  Bell, 
  Globe, 
  Eye, 
} from 'lucide-react';

const SettingsView: React.FC = () => {
  return (
    <div className="max-w-4xl mx-auto space-y-8 animate-in">
      <div>
        <h2 className="text-2xl font-bold tracking-tight">System Settings</h2>
        <p className="text-muted text-sm mt-1">Configure your application preferences and security.</p>
      </div>

      <div className="space-y-6">
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
