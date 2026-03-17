/**
 * KnowledgeDetail - Full knowledge entry view with inline editing
 *
 * Features:
 * - Show all fields: title, content (rendered), tags, source, dates, relations
 * - Toggle edit mode for inline editing of title, content (markdown), tags
 * - Save calls PUT /api/knowledge/:id
 * - Delete with confirmation dialog
 * - Relations list with clickable links to related entries
 * - Back button to previous page
 * - Route: /knowledge/:id
 */

import React, { useState, useEffect, useCallback, useRef } from 'react'
import { useParams, useNavigate, Link } from 'react-router-dom'
import {
  api,
  KnowledgeEntry,
  RelationEntry,
  KnowledgeUpdatePayload,
  getErrorMessage,
} from '../api/client'
import { LoadingSpinner } from '../components/LoadingSpinner'
import { EmptyState } from '../components/EmptyState'
import { useToast } from '../components/Toast'

// ---- Helpers ----

/** Format ISO date to locale string. */
function fmtDate(iso: string): string {
  try {
    return new Date(iso).toLocaleString(undefined, {
      year: 'numeric',
      month: 'short',
      day: 'numeric',
      hour: '2-digit',
      minute: '2-digit',
    })
  } catch {
    return iso
  }
}

/** Tag color palette — deterministic color for each tag. */
const TAG_COLORS = [
  { bg: 'bg-blue-900/60', text: 'text-blue-300', border: 'border-blue-700/50' },
  { bg: 'bg-emerald-900/60', text: 'text-emerald-300', border: 'border-emerald-700/50' },
  { bg: 'bg-purple-900/60', text: 'text-purple-300', border: 'border-purple-700/50' },
  { bg: 'bg-amber-900/60', text: 'text-amber-300', border: 'border-amber-700/50' },
  { bg: 'bg-rose-900/60', text: 'text-rose-300', border: 'border-rose-700/50' },
  { bg: 'bg-cyan-900/60', text: 'text-cyan-300', border: 'border-cyan-700/50' },
  { bg: 'bg-orange-900/60', text: 'text-orange-300', border: 'border-orange-700/50' },
  { bg: 'bg-indigo-900/60', text: 'text-indigo-300', border: 'border-indigo-700/50' },
]

function tagColorClass(tag: string): string {
  let hash = 0
  for (let i = 0; i < tag.length; i++) {
    hash = ((hash << 5) - hash + tag.charCodeAt(i)) | 0
  }
  const c = TAG_COLORS[Math.abs(hash) % TAG_COLORS.length]
  return `${c.bg} ${c.text} ${c.border}`
}

/** Simple markdown-to-HTML renderer for content preview. */
function renderMarkdown(text: string): string {
  return text
    .replace(/&/g, '&amp;')
    .replace(/</g, '&lt;')
    .replace(/>/g, '&gt;')
    // Headers
    .replace(/^### (.+)$/gm, '<h3 class="text-lg font-semibold mt-3 mb-1 text-gray-200">$1</h3>')
    .replace(/^## (.+)$/gm, '<h2 class="text-xl font-semibold mt-4 mb-1 text-gray-100">$1</h2>')
    .replace(/^# (.+)$/gm, '<h1 class="text-2xl font-bold mt-4 mb-2 text-white">$1</h1>')
    // Bold and italic
    .replace(/\*\*(.+?)\*\*/g, '<strong>$1</strong>')
    .replace(/\*(.+?)\*/g, '<em>$1</em>')
    // Inline code
    .replace(/`(.+?)`/g, '<code class="bg-gray-700 px-1 rounded text-sm text-green-300">$1</code>')
    // Code blocks
    .replace(/```[\s\S]*?```/g, (match) => {
      const code = match.replace(/```\w*\n?/, '').replace(/\n?```$/, '')
      return `<pre class="bg-gray-800 border border-gray-700 p-3 rounded-lg my-2 overflow-x-auto text-sm text-green-300"><code>${code}</code></pre>`
    })
    // Links
    .replace(
      /\[(.+?)\]\((.+?)\)/g,
      '<a href="$2" class="text-blue-400 underline hover:text-blue-300" target="_blank" rel="noopener">$1</a>'
    )
    // Unordered lists
    .replace(/^- (.+)$/gm, '<li class="ml-4 list-disc text-gray-300">$1</li>')
    // Paragraphs
    .replace(/\n\n/g, '</p><p class="mt-2">')
    .replace(/\n/g, '<br/>')
}

/** Resolved relation with connected node info. */
interface ResolvedRelation {
  id: string
  connectedNodeId: string
  connectedNodeTitle: string
  type: string
  weight: number
  direction: 'outgoing' | 'incoming'
}

// ---- Content Type Options ----

const CONTENT_TYPES = [
  { value: 'text', label: '📝 Text' },
  { value: 'markdown', label: '📄 Markdown' },
  { value: 'url', label: '🔗 URL' },
] as const

type ContentType = (typeof CONTENT_TYPES)[number]['value']

// ---- Component ----

export function KnowledgeDetail() {
  const { id } = useParams<{ id: string }>()
  const navigate = useNavigate()

  // Data
  const [entry, setEntry] = useState<KnowledgeEntry | null>(null)
  const [relations, setRelations] = useState<ResolvedRelation[]>([])

  // UI state
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState<string | null>(null)
  const [editing, setEditing] = useState(false)
  const [saving, setSaving] = useState(false)
  const [deleting, setDeleting] = useState(false)
  const [showDeleteConfirm, setShowDeleteConfirm] = useState(false)
  const toast = useToast()

  // Edit form state
  const [editTitle, setEditTitle] = useState('')
  const [editContent, setEditContent] = useState('')
  const [editContentType, setEditContentType] = useState<ContentType>('text')
  const [editTags, setEditTags] = useState<string[]>([])
  const [editTagInput, setEditTagInput] = useState('')
  const [editSource, setEditSource] = useState('')

  const tagInputRef = useRef<HTMLInputElement>(null)

  // ---- Fetch data ----

  const fetchEntry = useCallback(async () => {
    if (!id) return
    setLoading(true)
    setError(null)

    try {
      const [entryResult, relResult] = await Promise.allSettled([
        api.getKnowledge(id),
        api.listRelations({ node_id: id }),
      ])

      if (entryResult.status === 'fulfilled') {
        setEntry(entryResult.value)
      } else {
        setError('Knowledge entry not found')
        return
      }

      // Resolve relations — fetch connected node titles
      if (relResult.status === 'fulfilled' && relResult.value.items.length > 0) {
        const resolved: ResolvedRelation[] = []

        for (const rel of relResult.value.items) {
          const isSource = rel.source_id === id
          const connectedId = isSource ? rel.target_id : rel.source_id

          // Try to fetch connected node title
          let connectedTitle = connectedId.slice(0, 8) + '…'
          try {
            const connected = await api.getKnowledge(connectedId)
            connectedTitle = connected.title || connected.content.slice(0, 50)
          } catch {
            // Keep truncated ID as fallback
          }

          resolved.push({
            id: rel.id,
            connectedNodeId: connectedId,
            connectedNodeTitle: connectedTitle,
            type: rel.type,
            weight: rel.weight,
            direction: isSource ? 'outgoing' : 'incoming',
          })
        }

        setRelations(resolved)
      } else {
        setRelations([])
      }
    } catch (err) {
      setError(getErrorMessage(err))
    } finally {
      setLoading(false)
    }
  }, [id])

  useEffect(() => {
    fetchEntry()
  }, [fetchEntry])

  // ---- Enter edit mode ----

  const startEditing = () => {
    if (!entry) return
    setEditTitle(entry.title || '')
    setEditContent(entry.content)
    setEditContentType((entry.content_type as ContentType) || 'text')
    setEditTags([...entry.tags])
    setEditTagInput('')
    setEditSource(entry.source || '')
    setEditing(true)
  }

  const cancelEditing = () => {
    setEditing(false)
    setEditTagInput('')
  }

  // ---- Tag management in edit mode ----

  const addTag = (raw: string) => {
    const tag = raw.trim().toLowerCase()
    if (!tag || editTags.includes(tag)) return
    setEditTags(prev => [...prev, tag])
    setEditTagInput('')
  }

  const removeTag = (index: number) => {
    setEditTags(prev => prev.filter((_, i) => i !== index))
  }

  const handleTagKeyDown = (e: React.KeyboardEvent<HTMLInputElement>) => {
    if (e.key === 'Enter' || e.key === ',') {
      e.preventDefault()
      addTag(editTagInput)
    } else if (e.key === 'Backspace' && !editTagInput && editTags.length > 0) {
      removeTag(editTags.length - 1)
    }
  }

  // ---- Save ----

  const handleSave = async () => {
    if (!entry || !id) return

    const payload: KnowledgeUpdatePayload = {}
    if (editTitle !== (entry.title || '')) payload.title = editTitle || undefined
    if (editContent !== entry.content) payload.content = editContent
    if (editContentType !== entry.content_type) payload.content_type = editContentType
    if (JSON.stringify(editTags) !== JSON.stringify(entry.tags)) payload.tags = editTags
    if (editSource !== (entry.source || '')) payload.source = editSource || undefined

    // Nothing changed
    if (Object.keys(payload).length === 0) {
      setEditing(false)
      return
    }

    try {
      setSaving(true)
      const updated = await api.updateKnowledge(id, payload)
      setEntry(updated)
      setEditing(false)
      toast.success('Changes saved successfully')
    } catch (err) {
      toast.error(getErrorMessage(err))
    } finally {
      setSaving(false)
    }
  }

  // ---- Delete ----

  const handleDelete = async () => {
    if (!id) return
    try {
      setDeleting(true)
      await api.deleteKnowledge(id)
      toast.success('Entry deleted')
      // Navigate back after short delay so toast is visible
      setTimeout(() => navigate('/list'), 500)
    } catch (err) {
      toast.error(getErrorMessage(err))
      setDeleting(false)
      setShowDeleteConfirm(false)
    }
  }

  // ---- Loading state ----

  if (loading) {
    return <LoadingSpinner size="md" label="Loading knowledge entry…" />
  }

  // ---- Error state ----

  if (error || !entry) {
    return (
      <EmptyState
        variant="error"
        title={error || 'Entry not found'}
        actionLabel="← Go back"
        onAction={() => navigate(-1)}
        className="max-w-2xl mx-auto"
      />
    )
  }

  const displayTitle = entry.title || entry.content.slice(0, 60) + (entry.content.length > 60 ? '…' : '')

  // ---- Render ----

  return (
    <div className="max-w-3xl mx-auto space-y-6">
      {/* Breadcrumb / back button */}
      <div className="flex items-center justify-between">
        <button
          onClick={() => navigate(-1)}
          className="text-gray-400 hover:text-gray-200 text-sm inline-flex items-center gap-1.5 transition"
        >
          <svg className="w-4 h-4" fill="none" stroke="currentColor" viewBox="0 0 24 24">
            <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M15 19l-7-7 7-7" />
          </svg>
          Back
        </button>

        <div className="flex items-center gap-2">
          {!editing ? (
            <>
              <button
                onClick={startEditing}
                className="px-4 py-2 text-sm bg-blue-600/20 text-blue-400 border border-blue-600/30
                           hover:bg-blue-600/30 rounded-lg transition inline-flex items-center gap-1.5"
              >
                ✏️ Edit
              </button>
              <button
                onClick={() => setShowDeleteConfirm(true)}
                className="px-4 py-2 text-sm text-red-400 border border-red-800/50
                           hover:bg-red-900/30 hover:border-red-700 rounded-lg transition inline-flex items-center gap-1.5"
              >
                🗑 Delete
              </button>
            </>
          ) : (
            <>
              <button
                onClick={handleSave}
                disabled={saving || !editContent.trim()}
                className="px-4 py-2 text-sm bg-green-600 hover:bg-green-700 text-white
                           rounded-lg transition disabled:opacity-50 disabled:cursor-not-allowed
                           inline-flex items-center gap-1.5"
              >
                {saving ? (
                  <>
                    <svg className="animate-spin h-4 w-4" viewBox="0 0 24 24">
                      <circle className="opacity-25" cx="12" cy="12" r="10" stroke="currentColor" strokeWidth="4" fill="none" />
                      <path className="opacity-75" fill="currentColor" d="M4 12a8 8 0 018-8V0C5.373 0 0 5.373 0 12h4z" />
                    </svg>
                    Saving…
                  </>
                ) : (
                  '💾 Save'
                )}
              </button>
              <button
                onClick={cancelEditing}
                className="px-4 py-2 text-sm text-gray-400 border border-gray-700
                           hover:text-gray-200 hover:border-gray-500 rounded-lg transition"
              >
                Cancel
              </button>
            </>
          )}
        </div>
      </div>

      {/* Main content card */}
      <div className="bg-gray-800 rounded-xl border border-gray-700 overflow-hidden">
        {/* Title section */}
        <div className="p-6 border-b border-gray-700/50">
          {editing ? (
            <div>
              <label className="block text-xs text-gray-500 uppercase tracking-wide mb-1.5">Title</label>
              <input
                type="text"
                value={editTitle}
                onChange={e => setEditTitle(e.target.value)}
                placeholder="Give this entry a title (optional)"
                className="w-full bg-gray-900 border border-gray-600 rounded-lg px-4 py-3 text-lg
                           focus:outline-none focus:border-blue-500 transition placeholder-gray-500"
              />
            </div>
          ) : (
            <h1 className="text-2xl font-bold text-gray-100">{displayTitle}</h1>
          )}

          {/* Metadata row */}
          <div className="flex flex-wrap items-center gap-x-4 gap-y-1 mt-3 text-xs text-gray-500">
            <span className="inline-flex items-center gap-1">
              🆔 <span className="font-mono">{entry.id.slice(0, 12)}</span>
            </span>
            <span className="inline-flex items-center gap-1">
              📄 {editing ? (
                <select
                  value={editContentType}
                  onChange={e => setEditContentType(e.target.value as ContentType)}
                  className="bg-gray-700 border border-gray-600 rounded px-2 py-0.5 text-xs text-gray-300
                             focus:outline-none focus:border-blue-500"
                >
                  {CONTENT_TYPES.map(ct => (
                    <option key={ct.value} value={ct.value}>{ct.label}</option>
                  ))}
                </select>
              ) : (
                entry.content_type
              )}
            </span>
            <span className="inline-flex items-center gap-1">
              📅 Created {fmtDate(entry.created_at)}
            </span>
            {entry.updated_at !== entry.created_at && (
              <span className="inline-flex items-center gap-1">
                ✏️ Updated {fmtDate(entry.updated_at)}
              </span>
            )}
          </div>
        </div>

        {/* Content section */}
        <div className="p-6 border-b border-gray-700/50">
          <h2 className="text-xs font-medium text-gray-500 uppercase tracking-wide mb-3">Content</h2>
          {editing ? (
            <textarea
              value={editContent}
              onChange={e => setEditContent(e.target.value)}
              rows={12}
              className="w-full bg-gray-900 border border-gray-600 rounded-lg px-4 py-3
                         focus:outline-none focus:border-blue-500 resize-y transition
                         font-mono text-sm leading-relaxed placeholder-gray-500"
              placeholder="Enter content..."
            />
          ) : (
            <div className="bg-gray-900/50 rounded-lg p-5 max-h-[500px] overflow-y-auto">
              {entry.content_type === 'markdown' ? (
                <div
                  className="prose prose-invert prose-sm max-w-none text-gray-300 leading-relaxed"
                  dangerouslySetInnerHTML={{ __html: renderMarkdown(entry.content) }}
                />
              ) : (
                <pre className="text-sm text-gray-300 whitespace-pre-wrap font-sans leading-relaxed">
                  {entry.content}
                </pre>
              )}
            </div>
          )}
        </div>

        {/* Tags section */}
        <div className="p-6 border-b border-gray-700/50">
          <h2 className="text-xs font-medium text-gray-500 uppercase tracking-wide mb-3">Tags</h2>
          {editing ? (
            <div>
              <div
                className="w-full bg-gray-900 border border-gray-600 rounded-lg px-3 py-2
                           flex flex-wrap gap-2 items-center cursor-text min-h-[44px]
                           focus-within:border-blue-500 transition"
                onClick={() => tagInputRef.current?.focus()}
              >
                {editTags.map((tag, i) => (
                  <span
                    key={tag}
                    className="inline-flex items-center gap-1 bg-blue-600/30 text-blue-300
                               px-2.5 py-1 rounded-full text-sm border border-blue-500/30
                               hover:bg-blue-600/50 transition group"
                  >
                    {tag}
                    <button
                      type="button"
                      onClick={e => {
                        e.stopPropagation()
                        removeTag(i)
                      }}
                      className="text-blue-400/60 hover:text-red-400 transition ml-0.5 text-xs font-bold"
                      aria-label={`Remove tag "${tag}"`}
                    >
                      ×
                    </button>
                  </span>
                ))}
                <input
                  ref={tagInputRef}
                  type="text"
                  value={editTagInput}
                  onChange={e => setEditTagInput(e.target.value)}
                  onKeyDown={handleTagKeyDown}
                  onBlur={() => { if (editTagInput.trim()) addTag(editTagInput) }}
                  placeholder={editTags.length === 0 ? 'Type a tag and press Enter…' : 'Add more…'}
                  className="bg-transparent outline-none flex-1 min-w-[100px] text-sm
                             placeholder-gray-500 py-1"
                />
              </div>
              <p className="text-xs text-gray-500 mt-1">
                Press <kbd className="bg-gray-700 px-1.5 py-0.5 rounded text-xs">Enter</kbd> or{' '}
                <kbd className="bg-gray-700 px-1.5 py-0.5 rounded text-xs">,</kbd> to add.
                Backspace removes the last.
              </p>
            </div>
          ) : entry.tags.length > 0 ? (
            <div className="flex flex-wrap gap-2">
              {entry.tags.map(tag => (
                <span
                  key={tag}
                  className={`px-3 py-1 text-sm rounded-full border ${tagColorClass(tag)}`}
                >
                  {tag}
                </span>
              ))}
            </div>
          ) : (
            <p className="text-gray-600 text-sm italic">No tags</p>
          )}
        </div>

        {/* Source section */}
        <div className="p-6 border-b border-gray-700/50">
          <h2 className="text-xs font-medium text-gray-500 uppercase tracking-wide mb-3">Source</h2>
          {editing ? (
            <input
              type="text"
              value={editSource}
              onChange={e => setEditSource(e.target.value)}
              placeholder="https://example.com or Book: Chapter 3"
              className="w-full bg-gray-900 border border-gray-600 rounded-lg px-4 py-3
                         focus:outline-none focus:border-blue-500 transition placeholder-gray-500 text-sm"
            />
          ) : entry.source ? (
            entry.source.startsWith('http') ? (
              <a
                href={entry.source}
                target="_blank"
                rel="noopener noreferrer"
                className="text-blue-400 hover:text-blue-300 text-sm hover:underline break-all inline-flex items-center gap-1.5"
              >
                🔗 {entry.source}
                <svg className="w-3.5 h-3.5 flex-shrink-0" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                  <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M10 6H6a2 2 0 00-2 2v10a2 2 0 002 2h10a2 2 0 002-2v-4M14 4h6m0 0v6m0-6L10 14" />
                </svg>
              </a>
            ) : (
              <p className="text-gray-300 text-sm">{entry.source}</p>
            )
          ) : (
            <p className="text-gray-600 text-sm italic">No source specified</p>
          )}
        </div>

        {/* Relations section */}
        <div className="p-6">
          <h2 className="text-xs font-medium text-gray-500 uppercase tracking-wide mb-3">
            Relations
            {relations.length > 0 && (
              <span className="text-gray-600 ml-1">({relations.length})</span>
            )}
          </h2>
          {relations.length > 0 ? (
            <div className="space-y-1.5">
              {relations.map(rel => (
                <Link
                  key={rel.id}
                  to={`/knowledge/${rel.connectedNodeId}`}
                  className="flex items-center gap-3 px-4 py-2.5 bg-gray-900/40 hover:bg-gray-700/60
                             rounded-lg transition group"
                >
                  {/* Direction indicator */}
                  <span className={`text-xs font-mono px-2 py-0.5 rounded flex-shrink-0
                    ${rel.direction === 'outgoing'
                      ? 'bg-emerald-900/40 text-emerald-400 border border-emerald-800/50'
                      : 'bg-blue-900/40 text-blue-400 border border-blue-800/50'
                    }`}
                  >
                    {rel.direction === 'outgoing' ? '→' : '←'} {rel.type}
                  </span>
                  {/* Connected node title */}
                  <span className="text-sm text-gray-300 group-hover:text-blue-400 transition truncate flex-1">
                    {rel.connectedNodeTitle}
                  </span>
                  {/* Navigate hint */}
                  <svg
                    className="w-4 h-4 text-gray-600 group-hover:text-gray-400 transition flex-shrink-0"
                    fill="none"
                    stroke="currentColor"
                    viewBox="0 0 24 24"
                  >
                    <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M9 5l7 7-7 7" />
                  </svg>
                </Link>
              ))}
            </div>
          ) : (
            <p className="text-gray-600 text-sm italic">
              No relations yet.{' '}
              <Link to="/" className="text-blue-400 hover:underline">
                Use the graph view
              </Link>{' '}
              to link knowledge entries.
            </p>
          )}
        </div>
      </div>

      {/* Delete confirmation dialog */}
      {showDeleteConfirm && (
        <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/60 backdrop-blur-sm">
          <div className="bg-gray-800 rounded-xl border border-gray-700 p-6 max-w-md w-full mx-4 shadow-2xl">
            <h3 className="text-lg font-semibold text-gray-100 mb-2">Delete this entry?</h3>
            <p className="text-gray-400 text-sm mb-1">
              You are about to delete:
            </p>
            <p className="text-gray-200 text-sm font-medium mb-4 truncate">
              "{displayTitle}"
            </p>
            <p className="text-gray-500 text-xs mb-6">
              This action cannot be undone. All relations to this entry will also be removed.
            </p>
            <div className="flex items-center justify-end gap-3">
              <button
                onClick={() => setShowDeleteConfirm(false)}
                disabled={deleting}
                className="px-4 py-2 text-sm text-gray-400 border border-gray-700
                           hover:text-gray-200 hover:border-gray-500 rounded-lg transition"
              >
                Cancel
              </button>
              <button
                onClick={handleDelete}
                disabled={deleting}
                className="px-4 py-2 text-sm bg-red-600 hover:bg-red-700 text-white
                           rounded-lg transition disabled:opacity-50 inline-flex items-center gap-1.5"
              >
                {deleting ? (
                  <>
                    <svg className="animate-spin h-4 w-4" viewBox="0 0 24 24">
                      <circle className="opacity-25" cx="12" cy="12" r="10" stroke="currentColor" strokeWidth="4" fill="none" />
                      <path className="opacity-75" fill="currentColor" d="M4 12a8 8 0 018-8V0C5.373 0 0 5.373 0 12h4z" />
                    </svg>
                    Deleting…
                  </>
                ) : (
                  '🗑 Delete'
                )}
              </button>
            </div>
          </div>
        </div>
      )}
    </div>
  )
}
