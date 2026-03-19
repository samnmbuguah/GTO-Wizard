import React, { useState, useEffect } from 'react';
import { NavLink, Outlet, useNavigate } from 'react-router-dom';
import { useSolution } from '../contexts/SolutionContext';

export const DashboardLayout = ({ children }: { children?: React.ReactNode }) => {
  const [isDark] = useState(() => {
    const saved = localStorage.getItem('gto_theme');
    return saved ? saved === 'dark' : true; // Default to dark (teal)
  });
  const [isMobileMenuOpen, setIsMobileMenuOpen] = useState(false);
  const { activeSolutionId } = useSolution();
  const navigate = useNavigate();

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
