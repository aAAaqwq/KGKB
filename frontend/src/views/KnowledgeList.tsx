/**
 * KnowledgeList - Browse and manage knowledge entries
 *
 * Features:
 * - Text search bar with debounce
 * - Tag filter chips (fetched from API)
 * - Offset-based pagination
 * - Responsive card grid (1-col mobile, 2-col md, 3-col lg)
 * - Click card to expand/collapse details
 * - Delete with confirmation
 * - Empty state and loading indicator
 */

import React, { useState, useEffect, useCallback, useRef } from 'react'
import { api, KnowledgeEntry, PaginatedKnowledgeResponse } from '../api/client'

const PAGE_SIZE = 12

/** Truncate text to maxLen characters, adding ellipsis if needed. */
function truncate(text: string, maxLen: number): string {
  if (text.length <= maxLen) return text
  return text.slice(0, maxLen).trimEnd() + '…'
}

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

/** Tag color palette — deterministic color for each tag string. */
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

export function KnowledgeList() {
  // --- Data ---
  const [entries, setEntries] = useState<KnowledgeEntry[]>([])
  const [total, setTotal] = useState(0)
  const [allTags, setAllTags] = useState<string[]>([])

  // --- UI state ---
  const [loading, setLoading] = useState(true)
  const [searchText, setSearchText] = useState('')
  const [activeTag, setActiveTag] = useState<string | null>(null)
  const [offset, setOffset] = useState(0)
  const [expandedId, setExpandedId] = useState<string | null>(null)
  const [deletingId, setDeletingId] = useState<string | null>(null)

  // Debounce timer for search
  const debounceRef = useRef<ReturnType<typeof setTimeout> | null>(null)

  // --- Fetch tags once on mount ---
  useEffect(() => {
    api.listTags().then(setAllTags).catch(() => {})
  }, [])

  // --- Fetch entries whenever filters or page changes ---
  const loadEntries = useCallback(async () => {
    try {
      setLoading(true)

      // If there's search text, use the search endpoint for text search
      if (searchText.trim()) {
        const res = await api.searchKnowledge({
          q: searchText.trim(),
          mode: 'text',
          limit: PAGE_SIZE,
        })
        // Map search results to KnowledgeEntry shape
        const items: KnowledgeEntry[] = res.results.map(r => ({
          id: r.id,
          title: r.title,
          content: r.content,
          content_type: 'text',
          tags: r.tags,
          source: r.source,
          created_at: r.created_at,
          updated_at: r.created_at,
        }))
        // Apply tag filter client-side on search results
        const filtered = activeTag
          ? items.filter(e => e.tags.includes(activeTag))
          : items
        setEntries(filtered)
        setTotal(filtered.length)
      } else {
        const data: PaginatedKnowledgeResponse = await api.listKnowledge({
          tag: activeTag || undefined,
          limit: PAGE_SIZE,
          offset,
        })
        setEntries(data.items)
        setTotal(data.total)
      }
    } catch (err) {
      console.error('Failed to load entries:', err)
      setEntries([])
      setTotal(0)
    } finally {
      setLoading(false)
    }
  }, [searchText, activeTag, offset])

  useEffect(() => {
    loadEntries()
  }, [loadEntries])

  // --- Handlers ---

  /** Debounced search input handler */
  const handleSearchChange = (value: string) => {
    setSearchText(value)
    setOffset(0)
    if (debounceRef.current) clearTimeout(debounceRef.current)
    debounceRef.current = setTimeout(() => {
      // loadEntries is triggered by dependency change
    }, 300)
  }

  /** Toggle tag filter chip */
  const handleTagClick = (tag: string) => {
    setActiveTag(prev => (prev === tag ? null : tag))
    setOffset(0)
  }

  /** Clear all filters */
  const clearFilters = () => {
    setSearchText('')
    setActiveTag(null)
    setOffset(0)
  }

  /** Expand / collapse a card */
  const toggleExpand = (id: string) => {
    setExpandedId(prev => (prev === id ? null : id))
  }

  /** Delete entry with animated removal */
  const handleDelete = async (id: string) => {
    setDeletingId(id)
    try {
      await api.deleteKnowledge(id)
      setEntries(prev => prev.filter(e => e.id !== id))
      setTotal(prev => prev - 1)
      if (expandedId === id) setExpandedId(null)
      // Refresh tags in case a tag is now unused
      api.listTags().then(setAllTags).catch(() => {})
    } catch (err) {
      console.error('Failed to delete:', err)
      alert('Failed to delete entry. Please try again.')
    } finally {
      setDeletingId(null)
    }
  }

  // --- Pagination ---
  const totalPages = Math.max(1, Math.ceil(total / PAGE_SIZE))
  const currentPage = Math.floor(offset / PAGE_SIZE) + 1
  const hasPrev = offset > 0
  const hasNext = offset + PAGE_SIZE < total

  const hasActiveFilters = searchText.trim() !== '' || activeTag !== null

  return (
    <div className="space-y-6">
      {/* Header */}
      <div className="flex flex-col sm:flex-row sm:items-center sm:justify-between gap-4">
        <div>
          <h1 className="text-2xl font-bold">📋 Knowledge Base</h1>
          <p className="text-sm text-gray-400 mt-1">
            {total} {total === 1 ? 'entry' : 'entries'}
            {hasActiveFilters && ' (filtered)'}
          </p>
        </div>

        {/* Search bar */}
        <div className="relative w-full sm:w-80">
          <svg
            className="absolute left-3 top-1/2 -translate-y-1/2 w-4 h-4 text-gray-500"
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
            type="text"
            placeholder="Search knowledge…"
            value={searchText}
            onChange={e => handleSearchChange(e.target.value)}
            className="w-full bg-gray-800 border border-gray-700 rounded-lg pl-10 pr-4 py-2.5 text-sm
                       focus:outline-none focus:border-blue-500 focus:ring-1 focus:ring-blue-500/30
                       placeholder-gray-500 transition"
          />
          {searchText && (
            <button
              onClick={() => handleSearchChange('')}
              className="absolute right-3 top-1/2 -translate-y-1/2 text-gray-500 hover:text-gray-300"
            >
              ✕
            </button>
          )}
        </div>
      </div>

      {/* Tag filter chips */}
      {allTags.length > 0 && (
        <div className="flex flex-wrap gap-2 items-center">
          <span className="text-xs text-gray-500 uppercase tracking-wider mr-1">Tags:</span>
          {allTags.map(tag => (
            <button
              key={tag}
              onClick={() => handleTagClick(tag)}
              className={`px-3 py-1 text-xs rounded-full border transition cursor-pointer
                ${
                  activeTag === tag
                    ? 'bg-blue-600 text-white border-blue-500 shadow-lg shadow-blue-500/20'
                    : tagColor(tag) + ' hover:opacity-80'
                }`}
            >
              {tag}
            </button>
          ))}
          {hasActiveFilters && (
            <button
              onClick={clearFilters}
              className="px-3 py-1 text-xs rounded-full border border-gray-600 text-gray-400
                         hover:text-white hover:border-gray-400 transition ml-1"
            >
              Clear all
            </button>
          )}
        </div>
      )}

      {/* Content */}
      {loading ? (
        <div className="flex items-center justify-center py-16">
          <div className="flex flex-col items-center gap-3">
            <div className="w-8 h-8 border-2 border-blue-500 border-t-transparent rounded-full animate-spin" />
            <span className="text-sm text-gray-400">Loading…</span>
          </div>
        </div>
      ) : entries.length === 0 ? (
        <div className="text-center py-16">
          <p className="text-5xl mb-4">{hasActiveFilters ? '🔍' : '📭'}</p>
          <p className="text-gray-400 text-lg mb-2">
            {hasActiveFilters ? 'No matching entries found' : 'No knowledge entries yet'}
          </p>
          <p className="text-gray-500 text-sm">
            {hasActiveFilters ? (
              <button onClick={clearFilters} className="text-blue-400 hover:underline">
                Clear filters
              </button>
            ) : (
              <>
                Use <code className="bg-gray-800 px-2 py-0.5 rounded text-xs">kgkb add</code> or the{' '}
                <a href="/add" className="text-blue-400 hover:underline">
                  Add page
                </a>{' '}
                to get started.
              </>
            )}
          </p>
        </div>
      ) : (
        <>
          {/* Card grid */}
          <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-4">
            {entries.map(entry => {
              const isExpanded = expandedId === entry.id
              const isDeleting = deletingId === entry.id
              const displayTitle = entry.title || truncate(entry.content, 60)

              return (
                <div
                  key={entry.id}
                  className={`bg-gray-800 rounded-lg border transition-all duration-200
                    ${isExpanded ? 'border-blue-500/50 shadow-lg shadow-blue-500/5 md:col-span-2 lg:col-span-3' : 'border-gray-700 hover:border-gray-600'}
                    ${isDeleting ? 'opacity-50 pointer-events-none' : ''}`}
                >
                  {/* Card header — always visible */}
                  <div
                    className="p-4 cursor-pointer select-none"
                    onClick={() => toggleExpand(entry.id)}
                  >
                    <div className="flex justify-between items-start gap-3">
                      <div className="flex-1 min-w-0">
                        <h3 className="font-medium text-gray-100 truncate">{displayTitle}</h3>
                        {!isExpanded && (
                          <p className="text-sm text-gray-400 mt-1 line-clamp-2">
                            {truncate(entry.content, 150)}
                          </p>
                        )}
                      </div>
                      <div className="flex items-center gap-2 flex-shrink-0">
                        <span className="text-xs text-gray-500 hidden sm:inline">
                          {fmtDate(entry.created_at)}
                        </span>
                        <svg
                          className={`w-4 h-4 text-gray-500 transition-transform duration-200 ${isExpanded ? 'rotate-180' : ''}`}
                          fill="none"
                          stroke="currentColor"
                          viewBox="0 0 24 24"
                        >
                          <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M19 9l-7 7-7-7" />
                        </svg>
                      </div>
                    </div>

                    {/* Tags — always visible */}
                    {entry.tags.length > 0 && (
                      <div className="flex flex-wrap gap-1.5 mt-2.5">
                        {entry.tags.map(tag => (
                          <span
                            key={tag}
                            onClick={e => {
                              e.stopPropagation()
                              handleTagClick(tag)
                            }}
                            className={`px-2 py-0.5 text-xs rounded-full border cursor-pointer
                              transition hover:opacity-80 ${tagColor(tag)}`}
                          >
                            {tag}
                          </span>
                        ))}
                      </div>
                    )}
                  </div>

                  {/* Expanded detail */}
                  {isExpanded && (
                    <div className="border-t border-gray-700 p-4 space-y-3 animate-in">
                      {/* Full content */}
                      <div className="bg-gray-900/50 rounded-lg p-4 max-h-80 overflow-y-auto">
                        <pre className="text-sm text-gray-300 whitespace-pre-wrap font-sans leading-relaxed">
                          {entry.content}
                        </pre>
                      </div>

                      {/* Metadata */}
                      <div className="flex flex-wrap items-center gap-x-4 gap-y-1 text-xs text-gray-500">
                        <span title="Entry ID">
                          🆔 {entry.id.slice(0, 8)}
                        </span>
                        <span title="Content type">
                          📄 {entry.content_type}
                        </span>
                        <span title="Created">
                          📅 {fmtDate(entry.created_at)}
                        </span>
                        {entry.updated_at !== entry.created_at && (
                          <span title="Updated">
                            ✏️ {fmtDate(entry.updated_at)}
                          </span>
                        )}
                        {entry.source && (
                          <a
                            href={entry.source}
                            target="_blank"
                            rel="noreferrer"
                            className="text-blue-400 hover:underline"
                            onClick={e => e.stopPropagation()}
                          >
                            🔗 Source ↗
                          </a>
                        )}
                      </div>

                      {/* Actions */}
                      <div className="flex items-center gap-3 pt-1">
                        <button
                          onClick={e => {
                            e.stopPropagation()
                            if (confirm(`Delete "${displayTitle}"?\n\nThis cannot be undone.`)) {
                              handleDelete(entry.id)
                            }
                          }}
                          className="px-3 py-1.5 text-xs rounded-md border border-red-800/50 text-red-400
                                     hover:bg-red-900/30 hover:border-red-700 transition"
                        >
                          🗑 Delete
                        </button>
                        <button
                          onClick={e => {
                            e.stopPropagation()
                            navigator.clipboard.writeText(entry.id)
                          }}
                          className="px-3 py-1.5 text-xs rounded-md border border-gray-700 text-gray-400
                                     hover:bg-gray-700 hover:text-gray-200 transition"
                        >
                          📋 Copy ID
                        </button>
                      </div>
                    </div>
                  )}
                </div>
              )
            })}
          </div>

          {/* Pagination */}
          {totalPages > 1 && !searchText.trim() && (
            <div className="flex items-center justify-center gap-4 pt-4">
              <button
                onClick={() => setOffset(Math.max(0, offset - PAGE_SIZE))}
                disabled={!hasPrev}
                className="px-4 py-2 text-sm rounded-lg border border-gray-700 text-gray-300
                           hover:bg-gray-800 transition disabled:opacity-30 disabled:cursor-not-allowed"
              >
                ← Prev
              </button>
              <span className="text-sm text-gray-400">
                Page {currentPage} of {totalPages}
              </span>
              <button
                onClick={() => setOffset(offset + PAGE_SIZE)}
                disabled={!hasNext}
                className="px-4 py-2 text-sm rounded-lg border border-gray-700 text-gray-300
                           hover:bg-gray-800 transition disabled:opacity-30 disabled:cursor-not-allowed"
              >
                Next →
              </button>
            </div>
          )}
        </>
      )}
    </div>
  )
}
