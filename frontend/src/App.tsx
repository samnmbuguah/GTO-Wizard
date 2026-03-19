import { lazy, Suspense } from 'react'
import { BrowserRouter, Routes, Route, Navigate, useLocation } from 'react-router-dom'
import { SolutionProvider } from './contexts/SolutionContext'
import { DashboardLayout } from './components/DashboardLayout'

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

import { useEffect } from 'react'
import { useNavigate } from 'react-router-dom'

const DashboardRedirect = () => {
  const navigate = useNavigate();

  useEffect(() => {
    navigate('/dashboard', { replace: true });
  }, [navigate]);

  return <LoadingSpinner />;
};

function App() {
  return (
    <BrowserRouter>
      <Suspense fallback={<LoadingSpinner />}>
        <Routes>
          <Route path="/login" element={<LoginView />} />

          <Route
            element={
              <AuthGuard>
                <SolutionProvider>
                  <DashboardLayout />
                </SolutionProvider>
              </AuthGuard>
            }
          >
            <Route index element={<DashboardRedirect />} />
            <Route path="dashboard" element={<DashboardView />} />
            <Route path="dashboard/:solutionId" element={<DashboardView />} />
            <Route path="library" element={<LibraryView />} />
            <Route path="reports" element={<ReportsView />} />
            <Route path="study/:solutionId" element={<StudyView />} />
            <Route path="account" element={<AccountView />} />
            <Route path="settings" element={<SettingsView />} />
          </Route>
        </Routes>
      </Suspense>
    </BrowserRouter>
  )
}

export default App
