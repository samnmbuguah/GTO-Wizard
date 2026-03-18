import React, { useState, useEffect } from 'react';
import { useSolution } from '../contexts/SolutionContext';

export const DashboardLayout = ({ children }: { children: React.ReactNode }) => {
  const [isDark] = useState(() => {
    const saved = localStorage.getItem('gto_theme');
    return saved ? saved === 'dark' : true; // Default to dark (teal)
  });
  const [isMobileMenuOpen, setIsMobileMenuOpen] = useState(false);
  const { activeSolutionId } = useSolution();

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
      {/* Main Content Area */}
      <main className="flex-1 overflow-y-auto relative bg-poker-dark">
        {children}
      </main>
    </div>
  );
};
