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
const ReportsView = lazy(() => import('./components/ReportsView'))
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

import { apiClient } from './api/client'

function App() {
  const [nodes, setNodes] = useState<StrategyNode[]>([])
  const [loading, setLoading] = useState(true)
  const [isAuthenticated] = useState(!!localStorage.getItem('gto_token'))

  const fetchData = useCallback(async () => {
    const token = localStorage.getItem('gto_token');
    if (!token) {
      setLoading(false);
      return;
    }

    try {
      setLoading(true)
      const solutions = await apiClient.get<any[]>('/solutions/')
      
      if (Array.isArray(solutions) && solutions.length > 0) {
        const firstSol = solutions[0]
        const nodesData = await apiClient.get<StrategyNode[]>(`/nodes/`, {
          solution_id: firstSol.id,
          path: 'root'
        })
        setNodes(nodesData)
      }
    } catch (error) {
      console.error('Failed to fetch data:', error)
      // If 401, apiClient already handles token removal and redirect
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
                    <Route path="/reports" element={<ReportsView />} />
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
