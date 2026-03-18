import { useState, useEffect, useCallback } from 'react'
import { BrowserRouter, Routes, Route, Navigate, useLocation } from 'react-router-dom'
import { DashboardLayout } from './components/DashboardLayout'
import DashboardView from './components/DashboardView'
import LibraryView from './components/LibraryView'
import AccountView from './components/AccountView'
import SettingsView from './components/SettingsView'
import StudyView from './components/StudyView'
import LoginView from './components/LoginView'
import type { StrategyNode } from './types/poker'

// Auth Guard Component
const AuthGuard = ({ children }: { children: React.ReactNode }) => {
  const token = localStorage.getItem('gto_token');
  const location = useLocation();

  if (!token) {
    return <Navigate to="/login" state={{ from: location }} replace />;
  }

  return <>{children}</>;
};

function App() {
  const [nodes, setNodes] = useState<StrategyNode[]>([])
  const [loading, setLoading] = useState(true)
  const [isAuthenticated, setIsAuthenticated] = useState(!!localStorage.getItem('gto_token'))

  const fetchData = useCallback(async () => {
    const token = localStorage.getItem('gto_token');
    if (!token) {
      setLoading(false);
      return;
    }

    try {
      setLoading(true)
      const solRes = await fetch('http://213.199.50.129:8000/api/solutions/', {
        headers: { 'Authorization': `Token ${token}` }
      })
      
      if (solRes.status === 401) {
        localStorage.removeItem('gto_token');
        setIsAuthenticated(false);
        setLoading(false);
        return;
      }

      const solutions = await solRes.json()
      if (Array.isArray(solutions) && solutions.length > 0) {
        const firstSol = solutions[0]
        const nodeRes = await fetch(`http://213.199.50.129:8000/api/nodes/?solution_id=${firstSol.id}&path=root`, {
          headers: { 'Authorization': `Token ${token}` }
        })
        const nodesData = await nodeRes.json()
        setNodes(nodesData)
      }
    } catch (error) {
      console.error('Failed to fetch data:', error)
    } finally {
      setLoading(false)
    }
  }, [])

  useEffect(() => {
    fetchData()
  }, [fetchData])

  const handleHandSelect = (hand: string) => {
    console.log('Selected hand:', hand)
  }

  if (loading && isAuthenticated) {
    return (
      <div className="min-h-screen bg-background flex items-center justify-center">
        <div className="flex flex-col items-center gap-4">
          <div className="w-12 h-12 border-4 border-indigo-500 border-t-transparent rounded-full animate-spin"></div>
          <p className="text-indigo-500 text-sm font-bold animate-pulse">Initializing GTO Data...</p>
        </div>
      </div>
    )
  }

  return (
    <BrowserRouter>
      <Routes>
        <Route path="/login" element={<LoginView />} />
        
        <Route 
          path="/*" 
          element={
            <AuthGuard>
              <DashboardLayout>
                <Routes>
                  <Route path="/" element={<Navigate to="/dashboard" replace />} />
                  <Route path="/dashboard" element={<DashboardView nodes={nodes} onHandSelect={handleHandSelect} />} />
                  <Route path="/library" element={<LibraryView />} />
                  <Route path="/study" element={<StudyView nodes={nodes} />} />
                  <Route path="/account" element={<AccountView />} />
                  <Route path="/settings" element={<SettingsView />} />
                </Routes>
              </DashboardLayout>
            </AuthGuard>
          } 
        />
      </Routes>
    </BrowserRouter>
  )
}

export default App
