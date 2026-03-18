import { useState, useEffect } from 'react'
import { BrowserRouter, Routes, Route, Navigate } from 'react-router-dom'
import { DashboardLayout } from './components/DashboardLayout'
import DashboardView from './components/DashboardView'
import LibraryView from './components/LibraryView'
import AccountView from './components/AccountView'
import SettingsView from './components/SettingsView'
import StudyView from './components/StudyView'
import type { StrategyNode } from './types/poker'

function App() {
  const [nodes, setNodes] = useState<StrategyNode[]>([])
  const [loading, setLoading] = useState(true)

  useEffect(() => {
    const fetchData = async () => {
      try {
        setLoading(true)
        const solRes = await fetch('http://213.199.50.129:8000/api/solutions/')
        const solutions = await solRes.json()
        if (solutions.length > 0) {
          const firstSol = solutions[0]
          const nodeRes = await fetch(`http://213.199.50.129:8000/api/nodes/?solution_id=${firstSol.id}&path=root`)
          const nodesData = await nodeRes.json()
          setNodes(nodesData)
        }
      } catch (error) {
        console.error('Failed to fetch data:', error)
      } finally {
        setLoading(false)
      }
    }
    fetchData()
  }, [])

  const handleHandSelect = (hand: string) => {
    console.log('Selected hand:', hand)
  }

  if (loading) {
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
    </BrowserRouter>
  )
}

export default App
