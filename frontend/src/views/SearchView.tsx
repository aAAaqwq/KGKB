/**
 * SearchView - Semantic, text, and hybrid search interface
 *
 * Features:
 * - Search bar with mode toggle (text / semantic / hybrid)
 * - Results as cards with relevance score badges
 * - Highlighted matching text in results
 * - Click result to expand full details
 * - 'No results' empty state with tips
 * - Animated loading spinner during search
 * - Keyboard shortcut: Enter to search
 * - Debounced input option + explicit submit
 */

import React, { useState, useCallback, useRef, useEffect } from 'react'
import {
  api,
  SearchResultItem,
  SearchMode,
  getErrorMessage,
} from '../api/client'

// ─── Constants ───────────────────────────────────────────────────────────────

/** Available search modes with labels and descriptions. */
const SEARCH_MODES: { value: SearchMode; label: string; icon: string; desc: string }[] = [
  { value: 'text', label: 'Text', icon: '📝', desc: 'Keyword match in content' },
  { value: 'semantic', label: 'Semantic', icon: '🧠', desc: 'Meaning-based via embeddings' },
  { value: 'hybrid', label: 'Hybrid', icon: '⚡', desc: 'Combined text + semantic' },
]

const RESULTS_PER_PAGE = 20

// ─── Tag colors (shared with KnowledgeList) ──────────────────────────────────

const TAG_COLORS = [
  'bg-blue-900/60 text-blue-300 border-blue-700/50',
  'bg-emerald-900/60 text-emerald-300 border-emerald-700/50',
  'bg-purple-900/60 text-purple-300 border-purple-700/50',
  'bg-amber-900/60 text-amber-300 border-amber-700/50',
  'bg-rose-900/60 text-rose-300 border-rose-700/50',
  'bg-cyan-900/60 text-cyan-300 border-cyan-700/50',
  'bg-orange-900/60 text-orange-300 border-orange-700/50',
  'bg-indigo-900/60 text-indigo-300 border-indigo-700/50',
]

function tagColor(tag: string): string {
  let hash = 0
  for (let i = 0; i < tag.length; i++) {
    hash = ((hash << 5) - hash + tag.charCodeAt(i)) | 0
  }
  return TAG_COLORS[Math.abs(hash) % TAG_COLORS.length]
}

// ─── Helpers ─────────────────────────────────────────────────────────────────

/** Format an ISO date string to a human-readable locale string. */
function fmtDate(iso: string): string {
  try {
    return new Date(iso).toLocaleDateString(undefined, {
      year: 'numeric',
      month: 'short',
      day: 'numeric',
    })
  } catch {
    return iso
  }
}

/**
 * Score color and label based on relevance.
 * Returns Tailwind classes for badge styling.
 */
function scoreStyle(score: number): { bg: string; text: string; label: string } {
  if (score >= 0.8) return { bg: 'bg-green-900/60', text: 'text-green-300', label: 'Excellent' }
  if (score >= 0.6) return { bg: 'bg-blue-900/60', text: 'text-blue-300', label: 'Good' }
  if (score >= 0.4) return { bg: 'bg-amber-900/60', text: 'text-amber-300', label: 'Fair' }
  return { bg: 'bg-gray-700/60', text: 'text-gray-400', label: 'Low' }
}

/**
 * Highlight occurrences of query terms in text.
 * Returns an array of React elements with matched portions wrapped in <mark>.
 */
function highlightText(text: string, query: string): React.ReactNode {
  if (!query.trim()) return text

  // Split query into individual terms (ignore very short ones)
  const terms = query
    .trim()
    .split(/\s+/)
    .filter(t => t.length >= 2)

  if (terms.length === 0) return text

  // Build a regex matching any of the terms (case-insensitive)
  const escaped = terms.map(t => t.replace(/[.*+?^${}()|[\]\\]/g, '\\$&'))
  const regex = new RegExp(`(${escaped.join('|')})`, 'gi')

  const parts = text.split(regex)

  return parts.map((part, i) => {
    if (regex.test(part)) {
      // Reset lastIndex since we're using `g` flag
      regex.lastIndex = 0
      return (
        <mark
          key={i}
          className="bg-yellow-500/30 text-yellow-200 rounded px-0.5"
        >
          {part}
        </mark>
      )
    }
    return part
  })
}

/**
 * Truncate content and try to center around the first matching term.
 * Returns a snippet of ~maxLen characters with the match visible.
 */
function getSnippet(content: string, query: string, maxLen = 300): string {
  if (content.length <= maxLen) return content

  const terms = query.trim().split(/\s+/).filter(t => t.length >= 2)
  if (terms.length === 0) return content.slice(0, maxLen) + '…'

  // Find the first occurrence of any term
  const lower = content.toLowerCase()
  let firstIdx = -1
  for (const term of terms) {
    const idx = lower.indexOf(term.toLowerCase())
    if (idx !== -1 && (firstIdx === -1 || idx < firstIdx)) {
      firstIdx = idx
    }
  }

  if (firstIdx === -1) return content.slice(0, maxLen) + '…'

  // Center the snippet around the match
  const halfLen = Math.floor(maxLen / 2)
  let start = Math.max(0, firstIdx - halfLen)
  let end = Math.min(content.length, start + maxLen)

  // Adjust if we're near the beginning
  if (start === 0) end = Math.min(content.length, maxLen)

  let snippet = content.slice(start, end)
  if (start > 0) snippet = '…' + snippet
  if (end < content.length) snippet += '…'

  return snippet
}

// ─── Component ───────────────────────────────────────────────────────────────

export function SearchView() {
  // Search state
  const [query, setQuery] = useState('')
  const [mode, setMode] = useState<SearchMode>('text')
  const [results, setResults] = useState<SearchResultItem[]>([])
  const [totalResults, setTotalResults] = useState(0)
  const [searching, setSearching] = useState(false)
  const [searched, setSearched] = useState(false)
  const [error, setError] = useState<string | null>(null)
  const [lastQuery, setLastQuery] = useState('')
  const [lastMode, setLastMode] = useState<SearchMode>('text')

  // UI state
  const [expandedId, setExpandedId] = useState<string | null>(null)

  // Refs
  const inputRef = useRef<HTMLInputElement>(null)

  // Auto-focus search input on mount
  useEffect(() => {
    inputRef.current?.focus()
  }, [])

  /** Execute the search against the API. */
  const executeSearch = useCallback(async () => {
    const q = query.trim()
    if (!q) return

    try {
      setSearching(true)
      setSearched(true)
      setError(null)
      setExpandedId(null)

      const data = await api.searchKnowledge({
        q,
        mode,
        limit: RESULTS_PER_PAGE,
      })

      setResults(data.results)
      setTotalResults(data.total)
      setLastQuery(q)
      setLastMode(mode)
    } catch (err) {
      console.error('Search failed:', err)
      setError(getErrorMessage(err))
      setResults([])
      setTotalResults(0)
    } finally {
      setSearching(false)
    }
  }, [query, mode])

  /** Handle form submission. */
  const handleSubmit = (e: React.FormEvent) => {
    e.preventDefault()
    executeSearch()
  }

  /** Toggle expanded state for a result card. */
  const toggleExpand = (id: string) => {
    setExpandedId(prev => (prev === id ? null : id))
  }

  return (
    <div className="space-y-6">
      {/* Header */}
      <div>
        <h1 className="text-2xl font-bold">🔍 Search Knowledge</h1>
        <p className="text-sm text-gray-400 mt-1">
          Find knowledge entries using text keywords, semantic meaning, or both
        </p>
      </div>

      {/* Search form */}
      <form onSubmit={handleSubmit} className="space-y-4">
        {/* Search input + button */}
        <div className="flex gap-3">
          <div className="relative flex-1">
            <svg
              className="absolute left-4 top-1/2 -translate-y-1/2 w-5 h-5 text-gray-500"
              fill="none"
              stroke="currentColor"
              viewBox="0 0 24 24"
            >
              <path
                strokeLinecap="round"
                strokeLinejoin="round"
                strokeWidth={2}
                d="M21 21l-6-6m2-5a7 7 0 11-14 0 7 7 0 0114 0z"
              />
            </svg>
            <input
              ref={inputRef}
              type="text"
              placeholder="Search your knowledge base…"
              value={query}
              onChange={e => setQuery(e.target.value)}
              className="w-full bg-gray-800 border border-gray-700 rounded-lg pl-12 pr-4 py-3.5 text-lg
                         focus:outline-none focus:border-blue-500 focus:ring-1 focus:ring-blue-500/30
                         placeholder-gray-500 transition"
            />
            {query && (
              <button
                type="button"
                onClick={() => {
                  setQuery('')
                  inputRef.current?.focus()
                }}
                className="absolute right-4 top-1/2 -translate-y-1/2 text-gray-500 hover:text-gray-300
                           transition p-1"
              >
                ✕
              </button>
            )}
          </div>
          <button
            type="submit"
            disabled={searching || !query.trim()}
            className="bg-blue-600 hover:bg-blue-700 active:bg-blue-800 px-8 py-3.5 rounded-lg font-medium
                       transition disabled:opacity-40 disabled:cursor-not-allowed flex items-center gap-2
                       shadow-lg shadow-blue-600/20"
          >
            {searching ? (
              <>
                <div className="w-4 h-4 border-2 border-white border-t-transparent rounded-full animate-spin" />
                <span>Searching</span>
              </>
            ) : (
              'Search'
            )}
          </button>
        </div>

        {/* Mode toggle */}
        <div className="flex items-center gap-2">
          <span className="text-xs text-gray-500 uppercase tracking-wider mr-1">Mode:</span>
          {SEARCH_MODES.map(m => (
            <button
              key={m.value}
              type="button"
              onClick={() => setMode(m.value)}
              title={m.desc}
              className={`px-4 py-2 text-sm rounded-lg border transition flex items-center gap-1.5
                ${
                  mode === m.value
                    ? 'bg-blue-600/20 text-blue-300 border-blue-500/50 shadow-sm shadow-blue-500/10'
                    : 'bg-gray-800 text-gray-400 border-gray-700 hover:border-gray-600 hover:text-gray-300'
                }`}
            >
              <span>{m.icon}</span>
              <span>{m.label}</span>
            </button>
          ))}
        </div>
      </form>

      {/* Error message */}
      {error && (
        <div className="bg-red-900/30 border border-red-700/50 rounded-lg px-4 py-3 flex items-start gap-3">
          <span className="text-red-400 text-lg flex-shrink-0">⚠️</span>
          <div>
            <p className="text-red-300 text-sm font-medium">Search failed</p>
            <p className="text-red-400/80 text-sm mt-0.5">{error}</p>
            {mode === 'semantic' && (
              <p className="text-red-400/60 text-xs mt-1">
                Tip: Semantic search requires a running embedding service. Try "Text" mode instead.
              </p>
            )}
          </div>
        </div>
      )}

      {/* Loading spinner */}
      {searching && (
        <div className="flex items-center justify-center py-16">
          <div className="flex flex-col items-center gap-4">
            <div className="relative">
              <div className="w-12 h-12 border-2 border-blue-500/30 rounded-full" />
              <div className="absolute inset-0 w-12 h-12 border-2 border-blue-500 border-t-transparent rounded-full animate-spin" />
            </div>
            <div className="text-center">
              <p className="text-gray-300 text-sm">
                Searching with <strong>{SEARCH_MODES.find(m => m.value === mode)?.label}</strong> mode…
              </p>
              <p className="text-gray-500 text-xs mt-1">"{query}"</p>
            </div>
          </div>
        </div>
      )}

      {/* Results */}
      {!searching && searched && !error && (
        <>
          {results.length > 0 ? (
            <div className="space-y-4">
              {/* Results header */}
              <div className="flex items-center justify-between">
                <p className="text-sm text-gray-400">
                  <span className="text-gray-200 font-medium">{totalResults}</span>{' '}
                  {totalResults === 1 ? 'result' : 'results'} for{' '}
                  <span className="text-blue-400">"{lastQuery}"</span>
                  <span className="text-gray-600 ml-2">
                    ({SEARCH_MODES.find(m => m.value === lastMode)?.label} mode)
                  </span>
                </p>
              </div>

              {/* Result cards */}
              <div className="space-y-3">
                {results.map((result, index) => {
                  const isExpanded = expandedId === result.id
                  const style = scoreStyle(result.score)
                  const snippet = getSnippet(result.content, lastQuery)
                  const displayTitle = result.title || snippet.slice(0, 60)

                  return (
                    <div
                      key={result.id}
                      onClick={() => toggleExpand(result.id)}
                      className={`bg-gray-800 rounded-lg border transition-all duration-200 cursor-pointer
                        ${
                          isExpanded
                            ? 'border-blue-500/50 shadow-lg shadow-blue-500/5'
                            : 'border-gray-700 hover:border-gray-600'
                        }`}
                    >
                      {/* Card header */}
                      <div className="p-4">
                        <div className="flex items-start gap-3">
                          {/* Rank number */}
                          <span className="text-gray-600 text-sm font-mono mt-0.5 w-6 text-right flex-shrink-0">
                            {index + 1}
                          </span>

                          {/* Content */}
                          <div className="flex-1 min-w-0">
                            {/* Title row with score badge */}
                            <div className="flex items-start justify-between gap-3">
                              <h3 className="font-medium text-gray-100 leading-snug">
                                {highlightText(displayTitle, lastQuery)}
                              </h3>
                              {/* Score badge */}
                              <div
                                className={`flex-shrink-0 px-2.5 py-1 rounded-full text-xs font-medium border
                                  ${style.bg} ${style.text} border-current/20`}
                                title={`Relevance: ${(result.score * 100).toFixed(1)}%`}
                              >
                                {(result.score * 100).toFixed(0)}%
                              </div>
                            </div>

                            {/* Content snippet with highlighting */}
                            {!isExpanded && (
                              <p className="text-sm text-gray-400 mt-1.5 leading-relaxed line-clamp-3">
                                {highlightText(snippet, lastQuery)}
                              </p>
                            )}

                            {/* Tags */}
                            {result.tags && result.tags.length > 0 && (
                              <div className="flex flex-wrap gap-1.5 mt-2.5">
                                {result.tags.map(tag => (
                                  <span
                                    key={tag}
                                    className={`px-2 py-0.5 text-xs rounded-full border ${tagColor(tag)}`}
                                  >
                                    {tag}
                                  </span>
                                ))}
                              </div>
                            )}
                          </div>

                          {/* Expand indicator */}
                          <svg
                            className={`w-4 h-4 text-gray-500 transition-transform duration-200 flex-shrink-0 mt-1
                              ${isExpanded ? 'rotate-180' : ''}`}
                            fill="none"
                            stroke="currentColor"
                            viewBox="0 0 24 24"
                          >
                            <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M19 9l-7 7-7-7" />
                          </svg>
                        </div>
                      </div>

                      {/* Expanded detail panel */}
                      {isExpanded && (
                        <div className="border-t border-gray-700 p-4 space-y-3">
                          {/* Full content */}
                          <div className="bg-gray-900/50 rounded-lg p-4 max-h-96 overflow-y-auto">
                            <pre className="text-sm text-gray-300 whitespace-pre-wrap font-sans leading-relaxed">
                              {highlightText(result.content, lastQuery)}
                            </pre>
                          </div>

                          {/* Metadata row */}
                          <div className="flex flex-wrap items-center gap-x-4 gap-y-1 text-xs text-gray-500">
                            <span title="Entry ID">🆔 {result.id.slice(0, 8)}</span>
                            <span title="Created">📅 {fmtDate(result.created_at)}</span>
                            {result.source && (
                              <a
                                href={result.source}
                                target="_blank"
                                rel="noreferrer"
                                className="text-blue-400 hover:underline"
                                onClick={e => e.stopPropagation()}
                              >
                                🔗 Source ↗
                              </a>
                            )}
                            <span title="Relevance score" className={style.text}>
                              📊 Score: {result.score.toFixed(4)} ({style.label})
                            </span>
                          </div>

                          {/* Actions */}
                          <div className="flex items-center gap-3 pt-1">
                            <button
                              onClick={e => {
                                e.stopPropagation()
                                navigator.clipboard.writeText(result.id)
                              }}
                              className="px-3 py-1.5 text-xs rounded-md border border-gray-700 text-gray-400
                                         hover:bg-gray-700 hover:text-gray-200 transition"
                            >
                              📋 Copy ID
                            </button>
                            <button
                              onClick={e => {
                                e.stopPropagation()
                                navigator.clipboard.writeText(result.content)
                              }}
                              className="px-3 py-1.5 text-xs rounded-md border border-gray-700 text-gray-400
                                         hover:bg-gray-700 hover:text-gray-200 transition"
                            >
                              📄 Copy Content
                            </button>
                          </div>
                        </div>
                      )}
                    </div>
                  )
                })}
              </div>
            </div>
          ) : (
            /* Empty state */
            <div className="text-center py-16">
              <p className="text-5xl mb-4">🔍</p>
              <p className="text-gray-300 text-lg mb-2">No results found</p>
              <p className="text-gray-500 text-sm mb-4">
                Nothing matched <span className="text-gray-400">"{lastQuery}"</span> in{' '}
                <span className="text-gray-400">
                  {SEARCH_MODES.find(m => m.value === lastMode)?.label}
                </span>{' '}
                mode
              </p>
              <div className="max-w-md mx-auto text-left bg-gray-800/50 rounded-lg border border-gray-700 p-4">
                <p className="text-xs text-gray-500 uppercase tracking-wider mb-2">Suggestions</p>
                <ul className="text-sm text-gray-400 space-y-1.5">
                  <li>• Try different keywords or broader terms</li>
                  <li>• Switch to <strong>Text</strong> mode for exact keyword matching</li>
                  <li>• Switch to <strong>Semantic</strong> mode to search by meaning</li>
                  <li>• Use <strong>Hybrid</strong> mode for the best of both</li>
                  {lastMode === 'semantic' && (
                    <li className="text-amber-400/80">
                      • Make sure the embedding service is running for semantic search
                    </li>
                  )}
                </ul>
              </div>
            </div>
          )}
        </>
      )}

      {/* Initial state — before any search */}
      {!searching && !searched && (
        <div className="text-center py-16">
          <p className="text-5xl mb-4">🧠</p>
          <p className="text-gray-400 text-lg mb-2">Search your knowledge graph</p>
          <p className="text-gray-500 text-sm">
            Type a query and press <kbd className="px-1.5 py-0.5 bg-gray-800 rounded border border-gray-700 text-xs font-mono">Enter</kbd> to search
          </p>
          <div className="flex justify-center gap-6 mt-6 text-sm text-gray-600">
            {SEARCH_MODES.map(m => (
              <div key={m.value} className="flex items-center gap-1.5">
                <span>{m.icon}</span>
                <span>{m.label}:</span>
                <span className="text-gray-500">{m.desc}</span>
              </div>
            ))}
          </div>
        </div>
      )}
    </div>
  )
}
