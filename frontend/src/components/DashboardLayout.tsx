import React from 'react';
import { 
  LayoutDashboard, 
  Database, 
  Settings, 
  User, 
  ChevronRight,
  Search,
  Sword,
  BookOpen
} from 'lucide-react';

interface SidebarItemProps {
  icon: React.ReactNode;
  label: string;
  active?: boolean;
}

const SidebarItem = ({ icon, label, active }: SidebarItemProps) => (
  <div className={`flex items-center gap-3 px-4 py-3 cursor-pointer transition-all duration-200 group ${
    active ? 'bg-indigo-600/10 text-indigo-400 border-r-2 border-indigo-500' : 'text-slate-400 hover:bg-slate-800/50 hover:text-slate-200'
  }`}>
    {icon}
    <span className="font-medium">{label}</span>
    {active && <ChevronRight className="ml-auto w-4 h-4" />}
  </div>
);

export const DashboardLayout = ({ children }: { children: React.ReactNode }) => {
  return (
    <div className="flex h-screen bg-[#0f172a] text-slate-100 overflow-hidden font-sans">
      {/* Sidebar */}
      <aside className="w-64 border-r border-slate-800 flex flex-col bg-[#1e293b]/50 backdrop-blur-xl">
        <div className="p-6 mb-4">
          <div className="flex items-center gap-2 mb-8">
            <div className="w-8 h-8 bg-indigo-500 rounded-lg flex items-center justify-center shadow-lg shadow-indigo-500/20">
              <Sword className="w-5 h-5 text-white" />
            </div>
            <span className="text-xl font-bold tracking-tight">GTO<span className="text-indigo-400">Wiz</span></span>
          </div>
          
          <div className="relative">
            <Search className="absolute left-3 top-1/2 -translate-y-1/2 w-4 h-4 text-slate-500" />
            <input 
              type="text" 
              placeholder="Search spots..." 
              className="w-full bg-slate-900/50 border border-slate-700/50 rounded-md py-2 pl-10 pr-4 text-sm focus:outline-none focus:ring-1 focus:ring-indigo-500/50 transition-all"
            />
          </div>
        </div>

        <nav className="flex-1">
          <SidebarItem icon={<LayoutDashboard className="w-5 h-5" />} label="Dashboard" active />
          <SidebarItem icon={<Database className="w-5 h-5" />} label="Library" />
          <SidebarItem icon={<BookOpen className="w-5 h-5" />} label="Study" />
          <div className="mt-8 mb-2 px-6 text-[10px] font-bold text-slate-500 uppercase tracking-widest">System</div>
          <SidebarItem icon={<User className="w-5 h-5" />} label="Account" />
          <SidebarItem icon={<Settings className="w-5 h-5" />} label="Settings" />
        </nav>

        <div className="p-4 border-t border-slate-800">
          <div className="flex items-center gap-3 p-2 rounded-lg bg-slate-900/40">
            <div className="w-8 h-8 rounded-full bg-indigo-500/20 flex items-center justify-center text-indigo-400 text-xs font-bold">JD</div>
            <div className="flex-1 overflow-hidden">
              <p className="text-xs font-semibold truncate">Samuel Mbugua</p>
              <p className="text-[10px] text-slate-500 truncate">Premium Member</p>
            </div>
          </div>
        </div>
      </aside>

      {/* Main Content */}
      <main className="flex-1 overflow-y-auto relative bg-[radial-gradient(circle_at_top_right,rgba(99,102,241,0.05),transparent)]">
        <header className="sticky top-0 z-10 flex items-center justify-between px-8 py-4 border-b border-slate-800 bg-[#0f172a]/80 backdrop-blur-md">
          <div className="flex items-center gap-4">
            <h1 className="text-lg font-semibold">Current Spot: 6-Max Cash 100bb Open SB</h1>
            <span className="px-2 py-1 text-[10px] font-bold bg-emerald-500/10 text-emerald-400 border border-emerald-500/20 rounded">LIVE</span>
          </div>
          <div className="flex items-center gap-4">
            <button className="px-4 py-2 text-sm font-medium bg-indigo-600 hover:bg-indigo-500 text-white rounded-md transition-colors shadow-lg shadow-indigo-600/20">
              Upgrade Plan
            </button>
          </div>
        </header>

        <div className="p-8">
          {children}
        </div>
      </main>
    </div>
  );
};
