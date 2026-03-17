import React, { useState, useEffect } from 'react'
import { BrowserRouter, Routes, Route, Link, useLocation } from 'react-router-dom'
import { KnowledgeGraph } from './views/KnowledgeGraph'
import { KnowledgeList } from './views/KnowledgeList'
import { SearchView } from './views/SearchView'
import { AddKnowledge } from './views/AddKnowledge'
import { KnowledgeDetail } from './views/KnowledgeDetail'
import { api } from './api/client'
import './App.css'

/**
 * Connection status banner — checks backend health on mount.
 * Shows a dismissible warning when the backend is unreachable.
 */
function ConnectionBanner() {
  const [status, setStatus] = useState<'checking' | 'ok' | 'error'>('checking')
  const [dismissed, setDismissed] = useState(false)
  const [errorMsg, setErrorMsg] = useState('')

  useEffect(() => {
    let cancelled = false

    const check = async () => {
      try {
        const health = await api.health()
        if (!cancelled) {
          setStatus(health.status === 'healthy' ? 'ok' : 'error')
        }
      } catch (err: any) {
        if (!cancelled) {
          setStatus('error')
          setErrorMsg(
            err.code === 'ECONNABORTED'
              ? 'Backend timed out'
              : err.message?.includes('Network')
              ? 'Cannot reach backend'
              : 'Backend unavailable'
          )
        }
      }
    }

    check()
    return () => { cancelled = true }
  }, [])

  if (status !== 'error' || dismissed) return null

  return (
    <div className="bg-amber-900/40 border-b border-amber-700/50 px-4 py-2 flex items-center justify-between text-sm">
      <div className="flex items-center gap-2 text-amber-300">
        <span>⚠️</span>
        <span>
          {errorMsg || 'Backend unavailable'} — start the backend with{' '}
          <code className="bg-amber-800/50 px-1.5 py-0.5 rounded text-xs">
            python backend/run.py
          </code>
        </span>
      </div>
      <button
        onClick={() => setDismissed(true)}
        className="text-amber-400/60 hover:text-amber-300 transition ml-4"
      >
        ✕
      </button>
    </div>
  )
}

/**
 * Navigation link with active state highlighting.
 */
function NavLink({ to, children }: { to: string; children: React.ReactNode }) {
  const location = useLocation()
  const isActive = location.pathname === to

  return (
    <Link
      to={to}
      className={`transition font-medium ${
        isActive
          ? 'text-blue-400'
          : 'text-gray-300 hover:text-blue-400'
      }`}
    >
      {children}
    </Link>
  )
}

function AppContent() {
  return (
    <div className="min-h-screen bg-gray-900 text-white">
      <ConnectionBanner />

      <nav className="bg-gray-800 border-b border-gray-700 px-6 py-4">
        <div className="flex items-center justify-between max-w-7xl mx-auto">
          <Link to="/" className="text-xl font-bold text-blue-400 hover:text-blue-300 transition">
            🧠 KGKB
          </Link>
          <div className="flex gap-6">
            <NavLink to="/">Graph</NavLink>
            <NavLink to="/list">List</NavLink>
            <NavLink to="/search">Search</NavLink>
            <NavLink to="/add">Add</NavLink>
          </div>
        </div>
      </nav>

      <main className="max-w-7xl mx-auto px-6 py-8">
        <Routes>
          <Route path="/" element={<KnowledgeGraph />} />
          <Route path="/list" element={<KnowledgeList />} />
          <Route path="/search" element={<SearchView />} />
          <Route path="/add" element={<AddKnowledge />} />
          <Route path="/knowledge/:id" element={<KnowledgeDetail />} />
        </Routes>
      </main>
    </div>
  )
}

export function App() {
  return (
    <BrowserRouter>
      <AppContent />
    </BrowserRouter>
  )
}
