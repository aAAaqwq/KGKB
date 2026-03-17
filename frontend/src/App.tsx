import React, { useState, useEffect } from 'react'
import { BrowserRouter, Routes, Route, Link, useLocation } from 'react-router-dom'
import { KnowledgeGraph } from './views/KnowledgeGraph'
import { KnowledgeList } from './views/KnowledgeList'
import { SearchView } from './views/SearchView'
import { AddKnowledge } from './views/AddKnowledge'
import { KnowledgeDetail } from './views/KnowledgeDetail'
import { api } from './api/client'
import './App.css'

// ─── Page title mapping ────────────────────────────────────────────────────

const PAGE_TITLES: Record<string, string> = {
  '/': 'Graph — KGKB',
  '/list': 'Knowledge Base — KGKB',
  '/search': 'Search — KGKB',
  '/add': 'Add Knowledge — KGKB',
}

/**
 * Sync document.title with current route.
 */
function usePageTitle() {
  const location = useLocation()
  useEffect(() => {
    const base = PAGE_TITLES[location.pathname]
    if (base) {
      document.title = base
    } else if (location.pathname.startsWith('/knowledge/')) {
      document.title = 'Knowledge Detail — KGKB'
    } else {
      document.title = 'KGKB — Knowledge Graph Knowledge Base'
    }
  }, [location.pathname])
}

// ─── Connection Banner ─────────────────────────────────────────────────────

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
    <div className="bg-amber-900/40 border-b border-amber-700/50 px-4 py-2.5
                    flex items-center justify-between text-sm animate-fade-in">
      <div className="flex items-center gap-2 text-amber-300">
        <span>⚠️</span>
        <span>
          {errorMsg || 'Backend unavailable'} — start the backend with{' '}
          <code className="bg-amber-800/50 px-1.5 py-0.5 rounded text-xs font-mono">
            python backend/run.py
          </code>
        </span>
      </div>
      <button
        onClick={() => setDismissed(true)}
        className="text-amber-400/60 hover:text-amber-300 transition ml-4 p-1"
        aria-label="Dismiss"
      >
        ✕
      </button>
    </div>
  )
}

// ─── Navigation ────────────────────────────────────────────────────────────

/** Navigation items */
const NAV_ITEMS = [
  { to: '/', label: 'Graph', icon: '🕸️' },
  { to: '/list', label: 'List', icon: '📋' },
  { to: '/search', label: 'Search', icon: '🔍' },
  { to: '/add', label: 'Add', icon: '➕' },
]

/**
 * Navigation link with active state highlighting.
 */
function NavLink({
  to,
  icon,
  children,
  onClick,
}: {
  to: string
  icon: string
  children: React.ReactNode
  onClick?: () => void
}) {
  const location = useLocation()
  const isActive = location.pathname === to

  return (
    <Link
      to={to}
      onClick={onClick}
      className={`flex items-center gap-2 px-3 py-2 rounded-lg text-sm font-medium
                  transition-all duration-200
                  ${isActive
                    ? 'bg-blue-600/20 text-blue-400'
                    : 'text-gray-400 hover:text-gray-200 hover:bg-gray-700/50'
                  }`}
    >
      <span className="text-base">{icon}</span>
      <span>{children}</span>
    </Link>
  )
}

/**
 * Hamburger menu icon with animated transition.
 */
function HamburgerIcon({ open }: { open: boolean }) {
  return (
    <div className="w-5 h-5 flex flex-col justify-center items-center gap-[5px] transition-all">
      <span
        className={`block h-[2px] w-5 bg-gray-300 rounded transition-all duration-200
                    ${open ? 'rotate-45 translate-y-[7px]' : ''}`}
      />
      <span
        className={`block h-[2px] w-5 bg-gray-300 rounded transition-all duration-200
                    ${open ? 'opacity-0 scale-0' : ''}`}
      />
      <span
        className={`block h-[2px] w-5 bg-gray-300 rounded transition-all duration-200
                    ${open ? '-rotate-45 -translate-y-[7px]' : ''}`}
      />
    </div>
  )
}

// ─── App Content ───────────────────────────────────────────────────────────

function AppContent() {
  const [mobileMenuOpen, setMobileMenuOpen] = useState(false)
  const location = useLocation()

  // Update page title on route change
  usePageTitle()

  // Close mobile menu on route change
  useEffect(() => {
    setMobileMenuOpen(false)
  }, [location.pathname])

  // Close mobile menu on Escape
  useEffect(() => {
    const handler = (e: KeyboardEvent) => {
      if (e.key === 'Escape') setMobileMenuOpen(false)
    }
    window.addEventListener('keydown', handler)
    return () => window.removeEventListener('keydown', handler)
  }, [])

  return (
    <div className="min-h-screen bg-gray-900 text-gray-100">
      <ConnectionBanner />

      {/* ── Navigation Bar ── */}
      <nav className="sticky top-0 z-40 bg-gray-900/80 backdrop-blur-lg border-b border-gray-800
                      supports-[backdrop-filter]:bg-gray-900/70">
        <div className="max-w-7xl mx-auto px-4 sm:px-6">
          <div className="flex items-center justify-between h-14 sm:h-16">
            {/* Logo */}
            <Link
              to="/"
              className="flex items-center gap-2 text-lg sm:text-xl font-bold
                         text-blue-400 hover:text-blue-300 transition-colors shrink-0"
            >
              <span className="text-xl sm:text-2xl">🧠</span>
              <span>KGKB</span>
            </Link>

            {/* Desktop nav */}
            <div className="hidden sm:flex items-center gap-1">
              {NAV_ITEMS.map(item => (
                <NavLink key={item.to} to={item.to} icon={item.icon}>
                  {item.label}
                </NavLink>
              ))}
            </div>

            {/* Mobile hamburger */}
            <button
              className="sm:hidden p-2 -mr-2 rounded-lg text-gray-400 hover:text-gray-200
                         hover:bg-gray-800 transition"
              onClick={() => setMobileMenuOpen(prev => !prev)}
              aria-label="Toggle navigation menu"
              aria-expanded={mobileMenuOpen}
            >
              <HamburgerIcon open={mobileMenuOpen} />
            </button>
          </div>
        </div>

        {/* Mobile menu dropdown */}
        {mobileMenuOpen && (
          <div className="sm:hidden border-t border-gray-800 animate-slide-down">
            <div className="px-4 py-3 space-y-1">
              {NAV_ITEMS.map(item => (
                <NavLink
                  key={item.to}
                  to={item.to}
                  icon={item.icon}
                  onClick={() => setMobileMenuOpen(false)}
                >
                  {item.label}
                </NavLink>
              ))}
            </div>
          </div>
        )}
      </nav>

      {/* ── Main Content ── */}
      <main className="max-w-7xl mx-auto px-4 sm:px-6 py-6 sm:py-8">
        <Routes>
          <Route path="/" element={<KnowledgeGraph />} />
          <Route path="/list" element={<KnowledgeList />} />
          <Route path="/search" element={<SearchView />} />
          <Route path="/add" element={<AddKnowledge />} />
          <Route path="/knowledge/:id" element={<KnowledgeDetail />} />
        </Routes>
      </main>

      {/* ── Footer ── */}
      <footer className="border-t border-gray-800/50 mt-auto">
        <div className="max-w-7xl mx-auto px-4 sm:px-6 py-6 text-center">
          <p className="text-xs text-gray-600">
            🧠 KGKB — Knowledge Graph Knowledge Base
          </p>
        </div>
      </footer>
    </div>
  )
}

// ─── Root App ──────────────────────────────────────────────────────────────

export function App() {
  return (
    <BrowserRouter>
      <AppContent />
    </BrowserRouter>
  )
}
