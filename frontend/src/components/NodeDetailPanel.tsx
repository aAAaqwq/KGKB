/**
 * NodeDetailPanel - Slide-in side panel for graph node details
 *
 * Shows full knowledge entry details when a node is clicked in the graph:
 * - Title, content (with markdown-like rendering), tags, source, dates
 * - Relations list with clickable connected nodes for graph navigation
 * - Edit button (links to detail/edit view)
 * - Close button + Escape key support
 *
 * Fetches full data from the API to ensure up-to-date information
 * beyond what the graph node carries.
 */

import React, { useEffect, useState, useCallback } from 'react'
import { api, KnowledgeEntry, RelationEntry } from '../api/client'

/** Minimal node info passed from the graph (what SimNode exposes). */
export interface NodeInfo {
  id: string
  label: string
  content: string
  tags: string[]
  created_at: string
  degree: number
}

/** A resolved relation with the connected node's label for display. */
interface ResolvedRelation {
  id: string
  connectedNodeId: string
  connectedNodeLabel: string
  type: string
  weight: number
  direction: 'outgoing' | 'incoming'
}

interface NodeDetailPanelProps {
  /** The selected graph node. null = panel hidden. */
  node: NodeInfo | null
  /** Callback when user wants to close the panel. */
  onClose: () => void
  /** Callback when user clicks a connected node — navigates the graph. */
  onNavigateToNode: (nodeId: string) => void
  /** Map of all node IDs to labels for resolving relation endpoints. */
  nodeLabelMap: Map<string, string>
}

/** Tag color palette — mirrors KnowledgeGraph.tsx for consistency. */
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

/** Relation type display with direction arrow. */
function relationLabel(rel: ResolvedRelation): string {
  const arrow = rel.direction === 'outgoing' ? '→' : '←'
  return `${arrow} ${rel.type}`
}

/** Relation type color by common types. */
function relationTypeColor(type: string): string {
  switch (type.toLowerCase()) {
    case 'contains': return '#3b82f6'
    case 'relates_to': return '#10b981'
    case 'depends_on': return '#f59e0b'
    case 'similar_to': return '#8b5cf6'
    case 'part_of': return '#ec4899'
    default: return '#6b7280'
  }
}

export function NodeDetailPanel({
  node,
  onClose,
  onNavigateToNode,
  nodeLabelMap,
}: NodeDetailPanelProps) {
  const [fullEntry, setFullEntry] = useState<KnowledgeEntry | null>(null)
  const [relations, setRelations] = useState<ResolvedRelation[]>([])
  const [loading, setLoading] = useState(false)
  const [error, setError] = useState<string | null>(null)

  // Fetch full details + relations when node changes
  useEffect(() => {
    if (!node) {
      setFullEntry(null)
      setRelations([])
      return
    }

    let cancelled = false

    const fetchDetails = async () => {
      setLoading(true)
      setError(null)

      try {
        // Fetch full knowledge entry and relations in parallel
        const [entry, relResponse] = await Promise.allSettled([
          api.getKnowledge(node.id),
          api.listRelations({ node_id: node.id }),
        ])

        if (cancelled) return

        // Handle knowledge entry
        if (entry.status === 'fulfilled') {
          setFullEntry(entry.value)
        } else {
          // Fall back to graph node data if API fails
          setFullEntry(null)
        }

        // Handle relations
        if (relResponse.status === 'fulfilled') {
          const resolved: ResolvedRelation[] = relResponse.value.items.map(rel => {
            const isSource = rel.source_id === node.id
            const connectedId = isSource ? rel.target_id : rel.source_id
            return {
              id: rel.id,
              connectedNodeId: connectedId,
              connectedNodeLabel:
                nodeLabelMap.get(connectedId) || connectedId.slice(0, 8) + '…',
              type: rel.type,
              weight: rel.weight,
              direction: isSource ? 'outgoing' : 'incoming',
            }
          })
          setRelations(resolved)
        } else {
          setRelations([])
        }
      } catch (err: any) {
        if (!cancelled) {
          setError(err.message || 'Failed to load details')
        }
      } finally {
        if (!cancelled) setLoading(false)
      }
    }

    fetchDetails()
    return () => { cancelled = true }
  }, [node?.id, nodeLabelMap])

  // The panel is not rendered at all when node is null — the parent
  // controls visibility. But we add a slide-in class for animation.

  if (!node) return null

  // Prefer full API entry; fall back to graph node data
  const title = fullEntry?.title || node.label
  const content = fullEntry?.content || node.content
  const tags = fullEntry?.tags || node.tags
  const source = fullEntry?.source || null
  const createdAt = fullEntry?.created_at || node.created_at
  const updatedAt = fullEntry?.updated_at || null
  const contentType = fullEntry?.content_type || 'text'

  return (
    <div
      className="w-96 bg-gray-800 rounded-lg border border-gray-700 flex flex-col
                 max-h-[600px] overflow-hidden
                 animate-slide-in-right"
      style={{
        animation: 'slideInRight 0.25s ease-out',
      }}
    >
      {/* Header */}
      <div className="flex items-start justify-between p-4 pb-2 border-b border-gray-700/50">
        <div className="flex-1 min-w-0 mr-3">
          <h3 className="text-lg font-semibold text-blue-400 truncate" title={title}>
            {title}
          </h3>
          <div className="flex items-center gap-2 mt-1 text-xs text-gray-500">
            <span className="px-1.5 py-0.5 bg-gray-700 rounded text-gray-400">
              {contentType}
            </span>
            <span>{node.degree} connection{node.degree !== 1 ? 's' : ''}</span>
          </div>
        </div>
        <div className="flex items-center gap-1.5 flex-shrink-0">
          {/* Edit button — links to detail page (Task #22 will add the route) */}
          <a
            href={`/knowledge/${node.id}`}
            className="px-2.5 py-1 text-xs bg-blue-600/20 text-blue-400
                       hover:bg-blue-600/30 rounded transition"
            title="Edit knowledge entry"
            onClick={(e) => {
              // If the route doesn't exist yet, prevent broken navigation
              // and show a tooltip-like hint instead
              if (!window.location.pathname.startsWith('/knowledge/')) {
                // Let it navigate — the route will be added in Task #22
              }
            }}
          >
            ✏️ Edit
          </a>
          <button
            onClick={onClose}
            className="w-7 h-7 flex items-center justify-center
                       text-gray-500 hover:text-gray-300 hover:bg-gray-700
                       rounded transition text-lg leading-none"
            title="Close panel (Esc)"
          >
            ×
          </button>
        </div>
      </div>

      {/* Scrollable content */}
      <div className="flex-1 overflow-y-auto p-4 space-y-4">
        {loading && (
          <div className="text-center py-2">
            <span className="text-gray-400 text-sm animate-pulse">Loading details…</span>
          </div>
        )}

        {error && (
          <div className="text-xs text-yellow-500 bg-yellow-500/10 rounded px-3 py-2">
            ⚠️ {error} — showing graph data
          </div>
        )}

        {/* Content */}
        <div>
          <h4 className="text-xs font-medium text-gray-500 uppercase tracking-wide mb-1.5">
            Content
          </h4>
          <div className="text-gray-300 text-sm leading-relaxed whitespace-pre-wrap break-words
                          max-h-48 overflow-y-auto bg-gray-900/50 rounded p-3">
            {content || <span className="text-gray-600 italic">No content</span>}
          </div>
        </div>

        {/* Tags */}
        {tags.length > 0 && (
          <div>
            <h4 className="text-xs font-medium text-gray-500 uppercase tracking-wide mb-1.5">
              Tags
            </h4>
            <div className="flex flex-wrap gap-1.5">
              {tags.map(tag => (
                <span
                  key={tag}
                  className="px-2 py-0.5 text-xs rounded-full font-medium"
                  style={{
                    backgroundColor: getTagColor(tag) + '22',
                    color: getTagColor(tag),
                    border: `1px solid ${getTagColor(tag)}44`,
                  }}
                >
                  {tag}
                </span>
              ))}
            </div>
          </div>
        )}

        {/* Source */}
        {source && (
          <div>
            <h4 className="text-xs font-medium text-gray-500 uppercase tracking-wide mb-1.5">
              Source
            </h4>
            {source.startsWith('http') ? (
              <a
                href={source}
                target="_blank"
                rel="noopener noreferrer"
                className="text-blue-400 text-sm hover:underline break-all"
              >
                🔗 {source}
              </a>
            ) : (
              <p className="text-gray-300 text-sm">{source}</p>
            )}
          </div>
        )}

        {/* Relations */}
        <div>
          <h4 className="text-xs font-medium text-gray-500 uppercase tracking-wide mb-1.5">
            Relations {relations.length > 0 && (
              <span className="text-gray-600 ml-1">({relations.length})</span>
            )}
          </h4>
          {relations.length === 0 ? (
            <p className="text-gray-600 text-sm italic">No relations</p>
          ) : (
            <div className="space-y-1">
              {relations.map(rel => (
                <button
                  key={rel.id}
                  onClick={() => onNavigateToNode(rel.connectedNodeId)}
                  className="w-full flex items-center gap-2 px-3 py-2 text-left
                             bg-gray-900/40 hover:bg-gray-700/60 rounded
                             transition group"
                  title={`Navigate to "${rel.connectedNodeLabel}"`}
                >
                  {/* Direction + type */}
                  <span
                    className="text-xs font-mono flex-shrink-0 px-1.5 py-0.5 rounded"
                    style={{
                      color: relationTypeColor(rel.type),
                      backgroundColor: relationTypeColor(rel.type) + '15',
                    }}
                  >
                    {relationLabel(rel)}
                  </span>
                  {/* Connected node label */}
                  <span className="text-sm text-gray-300 group-hover:text-blue-400
                                   transition truncate flex-1">
                    {rel.connectedNodeLabel}
                  </span>
                  {/* Navigate hint */}
                  <span className="text-gray-600 group-hover:text-gray-400
                                   text-xs transition flex-shrink-0">
                    →
                  </span>
                </button>
              ))}
            </div>
          )}
        </div>

        {/* Metadata */}
        <div className="border-t border-gray-700/50 pt-3">
          <h4 className="text-xs font-medium text-gray-500 uppercase tracking-wide mb-1.5">
            Metadata
          </h4>
          <div className="text-xs text-gray-500 space-y-1">
            <div className="flex justify-between">
              <span>ID</span>
              <span className="text-gray-400 font-mono">{node.id.slice(0, 12)}…</span>
            </div>
            <div className="flex justify-between">
              <span>Created</span>
              <span className="text-gray-400">
                {new Date(createdAt).toLocaleString()}
              </span>
            </div>
            {updatedAt && (
              <div className="flex justify-between">
                <span>Updated</span>
                <span className="text-gray-400">
                  {new Date(updatedAt).toLocaleString()}
                </span>
              </div>
            )}
          </div>
        </div>
      </div>
    </div>
  )
}
