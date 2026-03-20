import React, { useState, useEffect } from 'react';
import { NavLink, Outlet, useNavigate } from 'react-router-dom';
import { useSolution } from '../contexts/SolutionContext';
import { Database, ChevronDown, Check } from 'lucide-react';
import { apiClient } from '../api/client';
import type { Solution } from '../types/poker';

export const DashboardLayout = ({ children }: { children?: React.ReactNode }) => {
  const [isDark] = useState(() => {
    const saved = localStorage.getItem('gto_theme');
    return saved ? saved === 'dark' : true; // Default to dark (teal)
  });
  const [isMobileMenuOpen, setIsMobileMenuOpen] = useState(false);
  const { activeSolutionId, setActiveSolutionId } = useSolution();
  const [solutions, setSolutions] = useState<Solution[]>([]);
  const [isLibraryOpen, setIsLibraryOpen] = useState(false);
  const navigate = useNavigate();

  useEffect(() => {
    const fetchSolutions = async () => {
      try {
        const data = await apiClient.get<Solution[]>('/solutions/');
        setSolutions(data);
      } catch (err) {
        console.error('Failed to fetch solutions for navbar:', err);
      }
    };
    fetchSolutions();
  }, []);

  // Use the variables to avoid TypeScript errors
  useEffect(() => {
    // Prevent unused variable warnings
    void isDark;
    void isMobileMenuOpen;
    void setIsMobileMenuOpen;
    void activeSolutionId;
  }, [isDark, isMobileMenuOpen, activeSolutionId, setIsMobileMenuOpen]);

  useEffect(() => {
    if (isDark) {
      document.documentElement.classList.add('dark');
      localStorage.setItem('gto_theme', 'dark');
    } else {
      document.documentElement.classList.remove('dark');
      localStorage.setItem('gto_theme', 'light');
    }
  }, [isDark]);

  return (
    <div className="flex flex-col h-screen bg-poker-dark text-poker-light overflow-hidden font-sans transition-colors duration-300">
      <header className="flex items-center justify-between px-6 bg-[#182628] border-b border-[#ccdbdc] h-[4vh] text-[12px] navBar">
        <div className="flex items-center gap-6 h-full">
          <NavLink to="/dashboard" className={({ isActive }) => `flex items-center h-full uppercase tracking-wider font-bold ${isActive ? 'text-[#ccdbdc] border-b-2 border-[#ccdbdc]' : 'text-[#a1b4d9] hover:text-[#ccdbdc]'} transition-colors`}>
            Dashboard
          </NavLink>
          <NavLink to="/library" className={({ isActive }) => `flex items-center h-full uppercase tracking-wider font-bold ${isActive ? 'text-[#ccdbdc] border-b-2 border-[#ccdbdc]' : 'text-[#a1b4d9] hover:text-[#ccdbdc]'} transition-colors`}>
            Library
          </NavLink>
          <NavLink to="/reports" className={({ isActive }) => `flex items-center h-full uppercase tracking-wider font-bold ${isActive ? 'text-[#ccdbdc] border-b-2 border-[#ccdbdc]' : 'text-[#a1b4d9] hover:text-[#ccdbdc]'} transition-colors`}>
            Reports
          </NavLink>
          <NavLink
            to={activeSolutionId ? `/study/${activeSolutionId}` : '/study/1'}
            className={({ isActive }) => `flex items-center h-full uppercase tracking-wider font-bold ${isActive ? 'text-[#ccdbdc] border-b-2 border-[#ccdbdc]' : 'text-[#a1b4d9] hover:text-[#ccdbdc]'} transition-colors`}
          >
            Study
          </NavLink>
          <NavLink to="/account" className={({ isActive }) => `flex items-center h-full uppercase tracking-wider font-bold ${isActive ? 'text-[#ccdbdc] border-b-2 border-[#ccdbdc]' : 'text-[#a1b4d9] hover:text-[#ccdbdc]'} transition-colors`}>
            Account
          </NavLink>
          <NavLink to="/settings" className={({ isActive }) => `flex items-center h-full uppercase tracking-wider font-bold ${isActive ? 'text-[#ccdbdc] border-b-2 border-[#ccdbdc]' : 'text-[#a1b4d9] hover:text-[#ccdbdc]'} transition-colors`}>
            Settings
          </NavLink>

          {/* Library Selection Dropdown */}
          <div className="relative h-full flex items-center ml-2">
            <button 
              onClick={() => setIsLibraryOpen(!isLibraryOpen)}
              className={`flex items-center gap-2 px-3 py-1 rounded transition-all ${isLibraryOpen ? 'bg-[#ccdbdc]/10 text-white' : 'text-[#a1b4d9] hover:text-[#ccdbdc]'}`}
            >
              <Database className="w-3 h-3 text-[#7aa6da]" />
              <span className="uppercase tracking-widest font-black text-[10px] max-w-[200px] truncate">
                {solutions.find(s => String(s.id) === String(activeSolutionId))?.name || "Select Library"}
              </span>
              <ChevronDown className={`w-3 h-3 transition-transform ${isLibraryOpen ? 'rotate-180' : ''}`} />
            </button>

            {isLibraryOpen && (
              <div className="absolute top-[100%] left-0 w-64 mt-1 bg-[#182628] border border-[#ccdbdc]/20 shadow-2xl rounded-[4px] py-1 z-50 animate-in fade-in slide-in-from-top-2">
                <div className="px-3 py-2 border-b border-[#ccdbdc]/10 bg-[#ccdbdc]/5">
                   <p className="text-[9px] font-black uppercase tracking-widest text-[#7aa6da]">Available Solutions</p>
                </div>
                <div className="max-h-64 overflow-y-auto custom-scrollbar">
                  {solutions.length > 0 ? (
                    solutions.map((sol) => (
                      <button
                        key={sol.id}
                        onClick={() => {
                          setActiveSolutionId(sol.id.toString());
                          setIsLibraryOpen(false);
                          navigate(`/dashboard/${sol.id}`);
                        }}
                        className={`w-full flex items-center justify-between px-3 py-2.5 text-left hover:bg-[#ccdbdc]/10 transition-colors group ${String(activeSolutionId) === String(sol.id) ? 'bg-[#7aa6da]/20' : ''}`}
                      >
                        <div className="flex flex-col gap-0.5">
                          <span className={`text-[11px] font-bold ${String(activeSolutionId) === String(sol.id) ? 'text-white' : 'text-[#ccdbdc]'}`}>{sol.name}</span>
                          <span className="text-[9px] text-[#a1b4d9] uppercase tracking-tighter">{sol.stack_depth}BB • {(sol.rake || 0) * 100}% Rake</span>
                        </div>
                        {String(activeSolutionId) === String(sol.id) && (
                          <Check className="w-3 h-3 text-[#7aa6da]" />
                        )}
                      </button>
                    ))
                  ) : (
                    <div className="px-3 py-4 text-center">
                      <p className="text-[10px] text-muted italic">No solutions found</p>
                    </div>
                  )}
                </div>
              </div>
            )}
          </div>
        </div>

        <button
          onClick={() => {
            localStorage.removeItem('gto_token');
            navigate('/login');
          }}
          className="uppercase tracking-wider font-bold text-[#a1b4d9] hover:text-[#ccdbdc] transition-colors"
        >
          Sign Out
        </button>
      </header>

      <main className="flex-1 overflow-y-auto relative bg-poker-dark">
        {children ?? <Outlet />}
      </main>
    </div>
  );
};
