/**
 * GraphFilters - Tag filter panel and search-in-graph for KnowledgeGraph
 *
 * Features:
 * - Colored tag chips that toggle node visibility by tag
 * - "All" / "None" quick-select buttons
 * - Search-in-graph input to highlight matching nodes by label/content
 * - Tag legend with color mapping
 * - Active filter indicator showing visible/total node counts
 */

import React, { useMemo, useCallback } from 'react'

/** Tag color palette — must mirror KnowledgeGraph.tsx and NodeDetailPanel.tsx */
const TAG_COLORS: Record<string, string> = {
  AI: '#3b82f6',
  tech: '#10b981',
  finance: '#f59e0b',
  research: '#8b5cf6',
  project: '#ef4444',
  idea: '#ec4899',
  science: '#14b8a6',
  code: '#06b6d4',
  note: '#a3a3a3',
}

function getTagColor(tag: string): string {
  const lower = tag.toLowerCase()
  for (const [key, color] of Object.entries(TAG_COLORS)) {
    if (lower === key.toLowerCase()) return color
  }
  return '#6b7280'
}

/** Count of nodes per tag (a node with multiple tags counts for each). */
export interface TagCount {
  tag: string
  count: number
}

export interface GraphFiltersProps {
  /** All unique tags present in the current graph data, with counts. */
  tagCounts: TagCount[]
  /** Currently active (visible) tags. Empty set = show all. */
  activeTags: Set<string>
  /** Toggle a single tag on/off. */
  onToggleTag: (tag: string) => void
  /** Select all tags (clear filter). */
  onSelectAll: () => void
  /** Deselect all tags (hide everything). */
  onSelectNone: () => void
  /** Current search query for in-graph highlight. */
  searchQuery: string
  /** Update search query. */
  onSearchChange: (query: string) => void
  /** Number of nodes currently visible after filter. */
  visibleNodeCount: number
  /** Total number of nodes. */
  totalNodeCount: number
  /** Number of edges currently visible after filter. */
  visibleEdgeCount: number
  /** Total number of edges. */
  totalEdgeCount: number
  /** Number of nodes matching the search query. */
  searchMatchCount: number
}

export function GraphFilters({
  tagCounts,
  activeTags,
  onToggleTag,
  onSelectAll,
  onSelectNone,
  searchQuery,
  onSearchChange,
  visibleNodeCount,
  totalNodeCount,
  visibleEdgeCount,
  totalEdgeCount,
  searchMatchCount,
}: GraphFiltersProps) {
  const isFiltering = activeTags.size > 0 && activeTags.size < tagCounts.length
  const isSearching = searchQuery.trim().length > 0

  /** Sort tags by count descending, then alphabetically. */
  const sortedTags = useMemo(() => {
    return [...tagCounts].sort((a, b) => b.count - a.count || a.tag.localeCompare(b.tag))
  }, [tagCounts])

  return (
    <div className="bg-gray-800/60 rounded-lg border border-gray-700/50 px-4 py-3 mb-4 space-y-3">
      {/* Top row: search + counts */}
      <div className="flex items-center gap-4 flex-wrap">
        {/* Search in graph */}
        <div className="relative flex-1 min-w-[200px] max-w-sm">
          <span className="absolute left-2.5 top-1/2 -translate-y-1/2 text-gray-500 text-sm pointer-events-none">
            🔍
          </span>
          <input
            type="text"
            value={searchQuery}
            onChange={(e) => onSearchChange(e.target.value)}
            placeholder="Search in graph..."
            className="w-full pl-8 pr-8 py-1.5 text-sm bg-gray-900/60 border border-gray-700
                       rounded-md text-gray-200 placeholder-gray-500
                       focus:outline-none focus:border-blue-500/50 focus:ring-1 focus:ring-blue-500/30
                       transition"
          />
          {isSearching && (
            <button
              onClick={() => onSearchChange('')}
              className="absolute right-2 top-1/2 -translate-y-1/2 text-gray-500
                         hover:text-gray-300 text-sm transition"
              title="Clear search"
            >
              ✕
            </button>
          )}
        </div>

        {/* Search match indicator */}
        {isSearching && (
          <span className="text-xs text-blue-400 bg-blue-500/10 px-2 py-1 rounded-md">
            {searchMatchCount} match{searchMatchCount !== 1 ? 'es' : ''}
          </span>
        )}

        {/* Counts */}
        <div className="flex items-center gap-3 text-xs text-gray-500 ml-auto">
          {isFiltering ? (
            <>
              <span className="text-yellow-400/80">
                {visibleNodeCount}/{totalNodeCount} nodes
              </span>
              <span>·</span>
              <span className="text-yellow-400/80">
                {visibleEdgeCount}/{totalEdgeCount} edges
              </span>
            </>
          ) : (
            <>
              <span>{totalNodeCount} nodes</span>
              <span>·</span>
              <span>{totalEdgeCount} edges</span>
            </>
          )}
        </div>
      </div>

      {/* Tag filter chips */}
      {sortedTags.length > 0 && (
        <div className="flex items-center gap-2 flex-wrap">
          <span className="text-xs text-gray-500 mr-1 flex-shrink-0">Filter:</span>

          {/* All / None quick buttons */}
          <button
            onClick={onSelectAll}
            className={`px-2 py-0.5 text-xs rounded-md border transition
              ${!isFiltering
                ? 'bg-gray-600/40 border-gray-500/50 text-gray-300'
                : 'bg-transparent border-gray-700 text-gray-500 hover:text-gray-300 hover:border-gray-500'
              }`}
          >
            All
          </button>
          <button
            onClick={onSelectNone}
            className="px-2 py-0.5 text-xs rounded-md border border-gray-700
                       text-gray-500 hover:text-gray-300 hover:border-gray-500 transition"
          >
            None
          </button>

          <span className="w-px h-4 bg-gray-700 mx-1" />

          {/* Tag chips */}
          {sortedTags.map(({ tag, count }) => {
            const color = getTagColor(tag)
            const isActive = activeTags.size === 0 || activeTags.has(tag)
            return (
              <button
                key={tag}
                onClick={() => onToggleTag(tag)}
                className={`inline-flex items-center gap-1.5 px-2.5 py-1 text-xs rounded-full
                           border transition-all duration-150 select-none
                           ${isActive
                    ? 'opacity-100'
                    : 'opacity-30 hover:opacity-60'
                  }`}
                style={{
                  backgroundColor: isActive ? color + '22' : 'transparent',
                  borderColor: isActive ? color + '66' : '#374151',
                  color: isActive ? color : '#6b7280',
                }}
                title={`${tag}: ${count} node${count !== 1 ? 's' : ''}${isActive ? ' (visible)' : ' (hidden)'}`}
              >
                <span
                  className="w-2.5 h-2.5 rounded-full flex-shrink-0"
                  style={{ backgroundColor: color, opacity: isActive ? 1 : 0.3 }}
                />
                {tag}
                <span
                  className="text-[10px] opacity-60"
                  style={{ color: isActive ? color : '#6b7280' }}
                >
                  {count}
                </span>
              </button>
            )
          })}
        </div>
      )}
    </div>
  )
}
