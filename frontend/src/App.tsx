import { useState, useEffect, useCallback, lazy, Suspense } from 'react'
import { BrowserRouter, Routes, Route, Navigate, useLocation } from 'react-router-dom'
import { DashboardLayout } from './components/DashboardLayout'
import type { StrategyNode } from './types/poker'

// Lazy load views for code splitting
const DashboardView = lazy(() => import('./components/DashboardView'))
const LibraryView = lazy(() => import('./components/LibraryView'))
const AccountView = lazy(() => import('./components/AccountView'))
const SettingsView = lazy(() => import('./components/SettingsView'))
const StudyView = lazy(() => import('./components/StudyView'))
const LoginView = lazy(() => import('./components/LoginView'))

// Auth Guard Component
const AuthGuard = ({ children }: { children: React.ReactNode }) => {
  const token = localStorage.getItem('gto_token');
  const location = useLocation();

  if (!token) {
    return <Navigate to="/login" state={{ from: location }} replace />;
  }

  return <>{children}</>;
};

// Loading component
const LoadingSpinner = () => (
  <div className="min-h-screen bg-background flex items-center justify-center">
    <div className="flex flex-col items-center gap-4">
      <div className="w-12 h-12 border-4 border-indigo-500 border-t-transparent rounded-full animate-spin"></div>
      <p className="text-indigo-500 text-sm font-bold animate-pulse">Initializing Terminal...</p>
    </div>
  </div>
);

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
    return <LoadingSpinner />;
  }

  return (
    <BrowserRouter>
      <Suspense fallback={<LoadingSpinner />}>
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
      </Suspense>
    </BrowserRouter>
  )
}

export default App
