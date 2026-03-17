/**
 * AddKnowledge - Complete form to add new knowledge entries
 *
 * Features:
 * - Title input
 * - Content textarea with markdown support and live preview toggle
 * - Chip-style tag input (add on Enter/comma, remove on click/backspace)
 * - Source URL input with basic validation
 * - Content type selector (text/url/markdown)
 * - Field validation with inline error hints
 * - Success/error feedback
 * - Form reset on success
 */

import React, { useState, useRef, useCallback, useEffect } from 'react'
import { api, getErrorMessage } from '../api/client'

/** Content type options for the selector */
const CONTENT_TYPES = [
  { value: 'text', label: '📝 Text', desc: 'Plain text content' },
  { value: 'markdown', label: '📄 Markdown', desc: 'Markdown formatted' },
  { value: 'url', label: '🔗 URL', desc: 'Web page / link' },
] as const

type ContentType = (typeof CONTENT_TYPES)[number]['value']

export function AddKnowledge() {
  // Form state
  const [title, setTitle] = useState('')
  const [content, setContent] = useState('')
  const [contentType, setContentType] = useState<ContentType>('text')
  const [tags, setTags] = useState<string[]>([])
  const [tagInput, setTagInput] = useState('')
  const [source, setSource] = useState('')
  const [showPreview, setShowPreview] = useState(false)

  // UI state
  const [submitting, setSubmitting] = useState(false)
  const [success, setSuccess] = useState<string | null>(null)
  const [error, setError] = useState<string | null>(null)
  const [fieldErrors, setFieldErrors] = useState<Record<string, string>>({})

  // Refs
  const tagInputRef = useRef<HTMLInputElement>(null)
  const contentRef = useRef<HTMLTextAreaElement>(null)

  // Auto-dismiss success message after 4 seconds
  useEffect(() => {
    if (!success) return
    const timer = setTimeout(() => setSuccess(null), 4000)
    return () => clearTimeout(timer)
  }, [success])

  // ---- Tag Management ----

  /** Add a tag (deduplicated, trimmed, lowercased) */
  const addTag = useCallback((raw: string) => {
    const tag = raw.trim().toLowerCase()
    if (!tag) return
    if (tags.includes(tag)) return
    setTags(prev => [...prev, tag])
    setTagInput('')
  }, [tags])

  /** Remove a tag by index */
  const removeTag = useCallback((index: number) => {
    setTags(prev => prev.filter((_, i) => i !== index))
  }, [])

  /** Handle tag input key events */
  const handleTagKeyDown = (e: React.KeyboardEvent<HTMLInputElement>) => {
    if (e.key === 'Enter' || e.key === ',') {
      e.preventDefault()
      addTag(tagInput)
    } else if (e.key === 'Backspace' && !tagInput && tags.length > 0) {
      // Remove last tag on backspace in empty input
      removeTag(tags.length - 1)
    }
  }

  /** Handle paste — split by commas and add multiple tags at once */
  const handleTagPaste = (e: React.ClipboardEvent<HTMLInputElement>) => {
    const pasted = e.clipboardData.getData('text')
    if (pasted.includes(',')) {
      e.preventDefault()
      pasted.split(',').forEach(t => addTag(t))
    }
  }

  // ---- Validation ----

  const validate = (): boolean => {
    const errors: Record<string, string> = {}

    if (!content.trim()) {
      errors.content = 'Content is required'
    }

    if (source.trim() && contentType === 'url') {
      // Light URL validation for URL type
      try {
        new URL(source.trim())
      } catch {
        errors.source = 'Please enter a valid URL'
      }
    }

    setFieldErrors(errors)
    return Object.keys(errors).length === 0
  }

  // ---- Submit ----

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault()
    if (!validate()) return

    try {
      setSubmitting(true)
      setError(null)
      setSuccess(null)

      const entry = await api.createKnowledge({
        title: title.trim() || undefined,
        content: content.trim(),
        content_type: contentType,
        tags: tags.length > 0 ? tags : undefined,
        source: source.trim() || undefined,
      })

      const displayTitle = entry.title || entry.content.slice(0, 40) + (entry.content.length > 40 ? '…' : '')
      setSuccess(`Added: "${displayTitle}" (${entry.id.slice(0, 8)})`)

      // Reset form
      setTitle('')
      setContent('')
      setContentType('text')
      setTags([])
      setTagInput('')
      setSource('')
      setShowPreview(false)
      setFieldErrors({})

      // Refocus content field for quick consecutive adds
      contentRef.current?.focus()
    } catch (err: unknown) {
      setError(getErrorMessage(err))
    } finally {
      setSubmitting(false)
    }
  }

  // ---- Simple markdown-to-HTML (basic rendering) ----

  const renderMarkdownPreview = (text: string): string => {
    return text
      // Headers
      .replace(/^### (.+)$/gm, '<h3 class="text-lg font-semibold mt-3 mb-1">$1</h3>')
      .replace(/^## (.+)$/gm, '<h2 class="text-xl font-semibold mt-4 mb-1">$1</h2>')
      .replace(/^# (.+)$/gm, '<h1 class="text-2xl font-bold mt-4 mb-2">$1</h1>')
      // Bold and italic
      .replace(/\*\*(.+?)\*\*/g, '<strong>$1</strong>')
      .replace(/\*(.+?)\*/g, '<em>$1</em>')
      // Inline code
      .replace(/`(.+?)`/g, '<code class="bg-gray-700 px-1 rounded text-sm">$1</code>')
      // Code blocks
      .replace(/```[\s\S]*?```/g, (match) => {
        const code = match.replace(/```\w*\n?/, '').replace(/\n?```$/, '')
        return `<pre class="bg-gray-800 p-3 rounded my-2 overflow-x-auto text-sm"><code>${code}</code></pre>`
      })
      // Links
      .replace(/\[(.+?)\]\((.+?)\)/g, '<a href="$2" class="text-blue-400 underline" target="_blank" rel="noopener">$1</a>')
      // Lists
      .replace(/^- (.+)$/gm, '<li class="ml-4 list-disc">$1</li>')
      // Paragraphs (double newline)
      .replace(/\n\n/g, '</p><p class="mt-2">')
      // Single newlines
      .replace(/\n/g, '<br/>')
  }

  return (
    <div className="max-w-2xl mx-auto">
      <h1 className="text-2xl font-bold mb-6">➕ Add Knowledge</h1>

      <form onSubmit={handleSubmit} className="space-y-5">
        {/* Title */}
        <div>
          <label className="block text-sm text-gray-400 mb-1">Title</label>
          <input
            type="text"
            value={title}
            onChange={e => setTitle(e.target.value)}
            placeholder="Give this knowledge a title (optional)"
            maxLength={500}
            className="w-full bg-gray-800 border border-gray-700 rounded-lg px-4 py-3 
                       focus:outline-none focus:border-blue-500 transition-colors
                       placeholder-gray-500"
          />
          <p className="text-xs text-gray-500 mt-1">
            A short label. If omitted, the first line of content is used.
          </p>
        </div>

        {/* Content Type Selector */}
        <div>
          <label className="block text-sm text-gray-400 mb-2">Content Type</label>
          <div className="flex gap-2">
            {CONTENT_TYPES.map(ct => (
              <button
                key={ct.value}
                type="button"
                onClick={() => setContentType(ct.value)}
                className={`px-4 py-2 rounded-lg text-sm font-medium transition-all
                  ${contentType === ct.value
                    ? 'bg-blue-600 text-white ring-2 ring-blue-400/50'
                    : 'bg-gray-800 text-gray-400 hover:bg-gray-700 hover:text-gray-200 border border-gray-700'
                  }`}
                title={ct.desc}
              >
                {ct.label}
              </button>
            ))}
          </div>
        </div>

        {/* Content */}
        <div>
          <div className="flex items-center justify-between mb-1">
            <label className="text-sm text-gray-400">
              Content <span className="text-red-400">*</span>
            </label>
            {contentType === 'markdown' && (
              <button
                type="button"
                onClick={() => setShowPreview(!showPreview)}
                className="text-xs text-blue-400 hover:text-blue-300 transition"
              >
                {showPreview ? '✏️ Edit' : '👁️ Preview'}
              </button>
            )}
          </div>

          {showPreview && contentType === 'markdown' ? (
            <div
              className="w-full bg-gray-800 border border-gray-700 rounded-lg px-4 py-3 
                         min-h-[160px] prose prose-invert prose-sm max-w-none"
              dangerouslySetInnerHTML={{
                __html: content.trim()
                  ? renderMarkdownPreview(content)
                  : '<p class="text-gray-500 italic">Nothing to preview</p>',
              }}
            />
          ) : (
            <textarea
              ref={contentRef}
              value={content}
              onChange={e => {
                setContent(e.target.value)
                if (fieldErrors.content) {
                  setFieldErrors(prev => {
                    const next = { ...prev }
                    delete next.content
                    return next
                  })
                }
              }}
              placeholder={
                contentType === 'url'
                  ? 'Paste a URL or describe the web resource...'
                  : contentType === 'markdown'
                  ? 'Write markdown content here...\n\n# Heading\n\n- List item\n- **Bold text**'
                  : 'Enter knowledge content...'
              }
              rows={8}
              className={`w-full bg-gray-800 border rounded-lg px-4 py-3 
                         focus:outline-none focus:border-blue-500 resize-y transition-colors
                         font-mono text-sm leading-relaxed placeholder-gray-500
                         ${fieldErrors.content ? 'border-red-500' : 'border-gray-700'}`}
              autoFocus
            />
          )}
          {fieldErrors.content && (
            <p className="text-red-400 text-xs mt-1">⚠️ {fieldErrors.content}</p>
          )}
          {content.length > 0 && (
            <p className="text-xs text-gray-500 mt-1 text-right">
              {content.length.toLocaleString()} / 50,000 chars
            </p>
          )}
        </div>

        {/* Tags — chip-style */}
        <div>
          <label className="block text-sm text-gray-400 mb-1">Tags</label>
          <div
            className="w-full bg-gray-800 border border-gray-700 rounded-lg px-3 py-2 
                       flex flex-wrap gap-2 items-center cursor-text min-h-[48px]
                       focus-within:border-blue-500 transition-colors"
            onClick={() => tagInputRef.current?.focus()}
          >
            {tags.map((tag, i) => (
              <span
                key={tag}
                className="inline-flex items-center gap-1 bg-blue-600/30 text-blue-300 
                           px-2.5 py-1 rounded-full text-sm border border-blue-500/30
                           hover:bg-blue-600/50 transition-colors group"
              >
                {tag}
                <button
                  type="button"
                  onClick={(e) => {
                    e.stopPropagation()
                    removeTag(i)
                  }}
                  className="text-blue-400/60 hover:text-red-400 transition-colors 
                             ml-0.5 text-xs font-bold leading-none"
                  aria-label={`Remove tag "${tag}"`}
                >
                  ×
                </button>
              </span>
            ))}
            <input
              ref={tagInputRef}
              type="text"
              value={tagInput}
              onChange={e => setTagInput(e.target.value)}
              onKeyDown={handleTagKeyDown}
              onPaste={handleTagPaste}
              onBlur={() => {
                if (tagInput.trim()) addTag(tagInput)
              }}
              placeholder={tags.length === 0 ? 'Type a tag and press Enter...' : 'Add more...'}
              className="bg-transparent outline-none flex-1 min-w-[100px] text-sm 
                         placeholder-gray-500 py-1"
            />
          </div>
          <p className="text-xs text-gray-500 mt-1">
            Press <kbd className="bg-gray-700 px-1.5 py-0.5 rounded text-xs">Enter</kbd> or{' '}
            <kbd className="bg-gray-700 px-1.5 py-0.5 rounded text-xs">,</kbd> to add a tag.
            Backspace removes the last one.
          </p>
        </div>

        {/* Source URL */}
        <div>
          <label className="block text-sm text-gray-400 mb-1">Source</label>
          <input
            type="text"
            value={source}
            onChange={e => {
              setSource(e.target.value)
              if (fieldErrors.source) {
                setFieldErrors(prev => {
                  const next = { ...prev }
                  delete next.source
                  return next
                })
              }
            }}
            placeholder="https://example.com/article  or  Book: Chapter 3"
            className={`w-full bg-gray-800 border rounded-lg px-4 py-3 
                       focus:outline-none focus:border-blue-500 transition-colors
                       placeholder-gray-500
                       ${fieldErrors.source ? 'border-red-500' : 'border-gray-700'}`}
          />
          {fieldErrors.source && (
            <p className="text-red-400 text-xs mt-1">⚠️ {fieldErrors.source}</p>
          )}
          <p className="text-xs text-gray-500 mt-1">
            Where this knowledge came from (URL, book reference, etc.)
          </p>
        </div>

        {/* Submit */}
        <div className="flex items-center gap-4 pt-2">
          <button
            type="submit"
            disabled={submitting || !content.trim()}
            className="bg-blue-600 hover:bg-blue-700 active:bg-blue-800 px-6 py-3 rounded-lg 
                       font-medium transition-all disabled:opacity-50 disabled:cursor-not-allowed
                       flex items-center gap-2"
          >
            {submitting ? (
              <>
                <svg className="animate-spin h-4 w-4" viewBox="0 0 24 24">
                  <circle className="opacity-25" cx="12" cy="12" r="10" stroke="currentColor" strokeWidth="4" fill="none" />
                  <path className="opacity-75" fill="currentColor" d="M4 12a8 8 0 018-8V0C5.373 0 0 5.373 0 12h4z" />
                </svg>
                Adding…
              </>
            ) : (
              'Add Knowledge'
            )}
          </button>

          {(title || content || tags.length > 0 || source) && !submitting && (
            <button
              type="button"
              onClick={() => {
                setTitle('')
                setContent('')
                setContentType('text')
                setTags([])
                setTagInput('')
                setSource('')
                setShowPreview(false)
                setFieldErrors({})
                setError(null)
                setSuccess(null)
              }}
              className="text-gray-400 hover:text-gray-200 text-sm transition"
            >
              Clear form
            </button>
          )}
        </div>

        {/* Success / Error feedback */}
        {success && (
          <div className="flex items-center gap-2 bg-green-900/30 border border-green-700/50 
                          text-green-400 px-4 py-3 rounded-lg text-sm animate-fadeIn">
            <span className="text-lg">✅</span>
            <span>{success}</span>
          </div>
        )}
        {error && (
          <div className="flex items-center gap-2 bg-red-900/30 border border-red-700/50 
                          text-red-400 px-4 py-3 rounded-lg text-sm">
            <span className="text-lg">❌</span>
            <span>{error}</span>
            <button
              type="button"
              onClick={() => setError(null)}
              className="ml-auto text-red-400/60 hover:text-red-300 transition"
            >
              ✕
            </button>
          </div>
        )}
      </form>

      {/* CLI hint */}
      <div className="mt-8 p-4 bg-gray-800/60 rounded-lg border border-gray-700/50">
        <h3 className="text-sm font-medium text-gray-400 mb-2">💡 CLI equivalent</h3>
        <code className="text-xs text-green-400 block whitespace-pre-wrap break-all">
          kgkb add "{content || 'Your knowledge content'}"
          {title && ` \\\n  --title "${title}"`}
          {tags.length > 0 && ` \\\n  --tags "${tags.join(', ')}"`}
          {source && ` \\\n  --source "${source}"`}
          {contentType !== 'text' && ` \\\n  --type ${contentType}`}
        </code>
      </div>
    </div>
  )
}
