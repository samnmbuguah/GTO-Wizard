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

  // Sync with URL if we are in a dashboard or study route
  useEffect(() => {
    const parts = location.pathname.split('/');
    if ((parts[1] === 'dashboard' || parts[1] === 'study') && parts[2]) {
      const id = parts[2];
      setActiveSolutionId(id);
      localStorage.setItem('gto_active_solution', id);
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
