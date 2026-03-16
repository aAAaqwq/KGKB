/**
 * AddKnowledge - Form to add new knowledge entries
 */

import React, { useState } from 'react'
import { api } from '../api/client'

export function AddKnowledge() {
  const [content, setContent] = useState('')
  const [tags, setTags] = useState('')
  const [source, setSource] = useState('')
  const [submitting, setSubmitting] = useState(false)
  const [success, setSuccess] = useState<string | null>(null)
  const [error, setError] = useState<string | null>(null)

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault()
    if (!content.trim()) return

    try {
      setSubmitting(true)
      setError(null)
      setSuccess(null)

      const tagList = tags
        .split(',')
        .map(t => t.trim())
        .filter(Boolean)

      const entry = await api.createKnowledge(
        content.trim(),
        tagList,
        source.trim() || undefined,
      )

      setSuccess(`Added knowledge ${entry.id.slice(0, 8)}`)
      setContent('')
      setTags('')
      setSource('')
    } catch (err: any) {
      setError(err.response?.data?.detail || err.message || 'Failed to add')
    } finally {
      setSubmitting(false)
    }
  }

  return (
    <div className="max-w-2xl">
      <h1 className="text-2xl font-bold mb-6">➕ Add Knowledge</h1>

      <form onSubmit={handleSubmit} className="space-y-4">
        <div>
          <label className="block text-sm text-gray-400 mb-1">Content *</label>
          <textarea
            value={content}
            onChange={e => setContent(e.target.value)}
            placeholder="Enter knowledge content..."
            rows={5}
            className="w-full bg-gray-800 border border-gray-700 rounded-lg px-4 py-3 focus:outline-none focus:border-blue-500 resize-y"
            autoFocus
          />
        </div>

        <div>
          <label className="block text-sm text-gray-400 mb-1">Tags (comma-separated)</label>
          <input
            type="text"
            value={tags}
            onChange={e => setTags(e.target.value)}
            placeholder="AI, tech, finance..."
            className="w-full bg-gray-800 border border-gray-700 rounded-lg px-4 py-3 focus:outline-none focus:border-blue-500"
          />
        </div>

        <div>
          <label className="block text-sm text-gray-400 mb-1">Source (URL or reference)</label>
          <input
            type="text"
            value={source}
            onChange={e => setSource(e.target.value)}
            placeholder="https://example.com/article"
            className="w-full bg-gray-800 border border-gray-700 rounded-lg px-4 py-3 focus:outline-none focus:border-blue-500"
          />
        </div>

        <button
          type="submit"
          disabled={submitting || !content.trim()}
          className="bg-blue-600 hover:bg-blue-700 px-6 py-3 rounded-lg font-medium transition disabled:opacity-50"
        >
          {submitting ? 'Adding...' : 'Add Knowledge'}
        </button>

        {success && (
          <p className="text-green-400 text-sm">✅ {success}</p>
        )}
        {error && (
          <p className="text-red-400 text-sm">❌ {error}</p>
        )}
      </form>

      <div className="mt-8 p-4 bg-gray-800 rounded-lg border border-gray-700">
        <h3 className="text-sm font-medium text-gray-400 mb-2">💡 CLI equivalent</h3>
        <code className="text-xs text-green-400 block">
          kgkb add "{content || 'Your knowledge'}"
          {tags && ` --tags "${tags}"`}
          {source && ` --source "${source}"`}
        </code>
      </div>
    </div>
  )
}
