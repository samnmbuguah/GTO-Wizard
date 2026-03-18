import React, { createContext, useContext, useState, useEffect } from 'react';
import { useLocation } from 'react-router-dom';

interface SolutionContextType {
  activeSolutionId: string | null;
  setActiveSolutionId: (id: string | null) => void;
}

const SolutionContext = createContext<SolutionContextType | undefined>(undefined);

export const SolutionProvider: React.FC<{ children: React.ReactNode }> = ({ children }) => {
  const [activeSolutionId, setActiveSolutionId] = useState<string | null>(() => {
    return localStorage.getItem('gto_active_solution');
  });
  const location = useLocation();

  // Persistence effect
  useEffect(() => {
    if (activeSolutionId) {
      localStorage.setItem('gto_active_solution', activeSolutionId);
    } else {
      localStorage.removeItem('gto_active_solution');
    }
  }, [activeSolutionId]);

  // Sync with URL
  useEffect(() => {
    const parts = location.pathname.split('/');
    if ((parts[1] === 'dashboard' || parts[1] === 'study') && parts[2]) {
      setActiveSolutionId(parts[2]);
    }
  }, [location.pathname]);

  return (
    <SolutionContext.Provider value={{ activeSolutionId, setActiveSolutionId }}>
      {children}
    </SolutionContext.Provider>
  );
};

export const useSolution = () => {
  const context = useContext(SolutionContext);
  if (context === undefined) {
    throw new Error('useSolution must be used within a SolutionProvider');
  }
  return context;
};
