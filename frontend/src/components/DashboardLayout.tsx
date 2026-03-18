import React, { useState, useEffect } from 'react';
import { NavLink, useLocation } from 'react-router-dom';
import { 
  LayoutDashboard, 
  Search,
  Settings, 
  User, 
  ChevronRight,
  ChevronLeft,
  Menu,
  X,
  Sword,
  TrendingUp,
  LogOut,
  BarChart,
  Sun,
  Moon
} from 'lucide-react';
import { useSolution } from '../contexts/SolutionContext';

interface SidebarItemProps {
  to: string;
  icon: React.ReactNode;
  label: string;
  collapsed?: boolean;
  onClick?: (_e: React.MouseEvent) => void;
}

const SidebarItem = ({ to, icon, label, collapsed, onClick }: SidebarItemProps) => (
  <NavLink
    to={to}
    onClick={onClick}
    className={({ isActive }) => `
      flex items-center gap-3 px-4 py-3 cursor-pointer transition-all duration-200 group relative
      ${isActive 
        ? 'bg-indigo-600/10 text-indigo-500 font-bold border-r-2 border-indigo-500' 
        : 'text-muted hover:bg-card/80 hover:text-foreground'
      }
      ${collapsed ? 'justify-center px-0' : ''}
    `}
  >
    <div className={`${collapsed ? 'scale-110' : ''} transition-transform`}>{icon}</div>
    {!collapsed && <span className="text-sm truncate">{label}</span>}
    {!collapsed && <ChevronRight className="ml-auto w-3 h-3 opacity-0 group-hover:opacity-100 transition-opacity" />}
    
    {collapsed && (
      <div className="absolute left-full ml-2 px-2 py-1 bg-slate-900 text-white text-[10px] rounded opacity-0 group-hover:opacity-100 pointer-events-none z-50 whitespace-nowrap shadow-xl">
        {label}
      </div>
    )}
  </NavLink>
);

export const DashboardLayout = ({ children }: { children: React.ReactNode }) => {
  const [isDark, setIsDark] = useState(false);
  const [isCollapsed, setIsCollapsed] = useState(false);
  const [isMobileMenuOpen, setIsMobileMenuOpen] = useState(false);
  const location = useLocation();
  const { activeSolutionId } = useSolution();

  useEffect(() => {
    if (isDark) document.documentElement.classList.add('dark');
    else document.documentElement.classList.remove('dark');
  }, [isDark]);

  useEffect(() => {
    setIsMobileMenuOpen(false);
  }, [location]);

  return (
    <div className="flex h-screen bg-background text-foreground overflow-hidden font-sans transition-colors duration-300">
      
      {isMobileMenuOpen && (
        <div 
          className="fixed inset-0 bg-black/60 backdrop-blur-sm z-40 lg:hidden"
          onClick={() => setIsMobileMenuOpen(false)}
        />
      )}

      <aside className={`
        fixed lg:relative z-50 h-full border-r border-border bg-card/60 lg:bg-card/40 backdrop-blur-xl flex flex-col transition-all duration-300
        ${isMobileMenuOpen ? 'translate-x-0' : '-translate-x-full lg:translate-x-0'}
        ${isCollapsed ? 'w-20' : 'w-64'}
      `}>
        <div className={`p-6 mb-2 flex items-center ${isCollapsed ? 'justify-center' : 'justify-between'}`}>
          <div className="flex items-center gap-2">
            <div className="w-8 h-8 bg-indigo-500 rounded-lg flex items-center justify-center shadow-lg shadow-indigo-500/20 shrink-0">
              <Sword className="text-white w-5 h-5" />
            </div>
            {!isCollapsed && <span className="text-lg font-black tracking-tighter italic">GTO<span className="text-indigo-500">Wiz</span></span>}
          </div>
          <button 
            onClick={() => setIsCollapsed(!isCollapsed)}
            className="hidden lg:flex p-1.5 hover:bg-background rounded-lg border border-border/50 text-muted transition-colors"
          >
            {isCollapsed ? <ChevronRight className="w-4 h-4" /> : <ChevronLeft className="w-4 h-4" />}
          </button>
          <button 
            onClick={() => setIsMobileMenuOpen(false)}
            className="lg:hidden p-1.5 hover:bg-background rounded-lg text-muted"
          >
            <X className="w-5 h-5" />
          </button>
        </div>

        <nav className="flex-1 overflow-y-auto py-4 space-y-1">
          <SidebarItem 
            to={activeSolutionId ? `/dashboard/${activeSolutionId}` : '/library'} 
            icon={<LayoutDashboard className="w-5 h-5" />} 
            label="Dashboard" 
            collapsed={isCollapsed} 
          />
          <SidebarItem to="/library" icon={<Search className="w-5 h-5" />} label="Library" collapsed={isCollapsed} />
          <SidebarItem to="/reports" icon={<BarChart className="w-5 h-5" />} label="Reports" collapsed={isCollapsed} />
          <SidebarItem 
            to={activeSolutionId ? `/study/${activeSolutionId}` : '/library'} 
            icon={<TrendingUp className="w-5 h-5" />} 
            label="Trainer" 
            collapsed={isCollapsed} 
          />
          
          <div className={`mt-8 mb-2 px-6 text-[10px] font-bold text-muted uppercase tracking-widest ${isCollapsed ? 'hidden' : ''}`}>Theme</div>
          <SidebarItem 
            to="#"
            icon={isDark ? <Sun className="w-5 h-5" /> : <Moon className="w-5 h-5" />} 
            label={isDark ? "Light Mode" : "Dark Mode"} 
            collapsed={isCollapsed}
            onClick={(e) => { e.preventDefault(); setIsDark(!isDark); }}
          />

          <div className={`mt-8 mb-2 px-6 text-[10px] font-bold text-muted uppercase tracking-widest ${isCollapsed ? 'hidden' : ''}`}>System</div>
          <SidebarItem to="/account" icon={<User className="w-5 h-5" />} label="Account" collapsed={isCollapsed} />
          <SidebarItem to="/settings" icon={<Settings className="w-5 h-5" />} label="Settings" collapsed={isCollapsed} />
      
      <div className={`mt-auto mb-2 px-6 text-[10px] font-bold text-muted uppercase tracking-widest ${isCollapsed ? 'hidden' : ''}`}>Session</div>
      <SidebarItem 
        to="/login" 
        icon={<LogOut className="w-5 h-5 text-rose-500" />} 
        label="Logout" 
        collapsed={isCollapsed} 
        onClick={() => {
          localStorage.removeItem('gto_token');
          localStorage.removeItem('gto_user');
        }}
      />
    </nav>

        <div className="p-4 border-t border-border">
          <div className={`flex items-center gap-3 p-2 rounded-xl bg-background/40 ${isCollapsed ? 'justify-center' : ''}`}>
            <div className="w-8 h-8 rounded-full bg-indigo-500/20 flex items-center justify-center text-indigo-400 text-xs font-bold shrink-0">SM</div>
            {!isCollapsed && (
              <div className="flex-1 overflow-hidden">
                <p className="text-[11px] font-bold truncate">Samuel Mbugua</p>
                <p className="text-[10px] text-muted truncate">Premium</p>
              </div>
            )}
          </div>
        </div>
      </aside>

      <div className="flex-1 flex flex-col min-w-0">
        <header className="lg:hidden flex items-center justify-between px-6 py-4 border-b border-border bg-background/80 backdrop-blur-md sticky top-0 z-30">
          <div className="flex items-center gap-2">
            <Sword className="text-indigo-500 w-6 h-6" />
            <span className="text-lg font-black tracking-tighter">GTO<span className="text-indigo-500">Wiz</span></span>
          </div>
          <button 
            onClick={() => setIsMobileMenuOpen(true)}
            className="p-2 bg-card border border-border rounded-lg"
          >
            <Menu className="w-6 h-6" />
          </button>
        </header>

        <header className="hidden lg:flex sticky top-0 z-10 items-center justify-between px-8 py-4 border-b border-border bg-background/80 backdrop-blur-md">
          <div className="flex items-center gap-4">
            <h1 className="text-sm font-bold opacity-80 capitalize">{location.pathname.replace('/', '') || 'Dashboard'}</h1>
            <span className="px-2 py-0.5 text-[9px] font-black bg-indigo-500/10 text-indigo-500 border border-indigo-500/10 rounded uppercase">Live Solver</span>
          </div>
          <div className="flex items-center gap-4">
            {localStorage.getItem('gto_user') === 'admin' ? (
              <span className="px-4 py-1.5 bg-emerald-500/10 text-emerald-500 text-xs font-bold rounded-lg border border-emerald-500/20">
                Premium Active
              </span>
            ) : (
              <button className="px-4 py-1.5 bg-indigo-600 hover:bg-indigo-500 text-white text-xs font-bold rounded-lg transition-all shadow-lg shadow-indigo-600/20">
                Upgrade Plan
              </button>
            )}
          </div>
        </header>

        <main className="flex-1 overflow-y-auto relative p-4 md:p-6 lg:p-10 bg-[radial-gradient(circle_at_top_right,rgba(99,102,241,0.03),transparent)]">
          {children}
        </main>
      </div>
    </div>
  );
};
