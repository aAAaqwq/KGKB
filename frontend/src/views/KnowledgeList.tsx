/**
 * KnowledgeList - Browse and manage knowledge entries
 */

import React, { useState, useEffect } from 'react'
import { api, KnowledgeEntry, PaginatedKnowledgeResponse } from '../api/client'

export function KnowledgeList() {
  const [entries, setEntries] = useState<KnowledgeEntry[]>([])
  const [loading, setLoading] = useState(true)
  const [tagFilter, setTagFilter] = useState('')

  useEffect(() => {
    loadEntries()
  }, [tagFilter])

  const loadEntries = async () => {
    try {
      setLoading(true)
      const data = await api.listKnowledge({
        tag: tagFilter || undefined,
        limit: 50,
      })
      setEntries(data.items)
    } catch (err) {
      console.error('Failed to load entries:', err)
      setEntries([])
    } finally {
      setLoading(false)
    }
  }

  const handleDelete = async (id: string) => {
    if (!confirm('Delete this entry?')) return
    try {
      await api.deleteKnowledge(id)
      setEntries(prev => prev.filter(e => e.id !== id))
    } catch (err) {
      console.error('Failed to delete:', err)
    }
  }

  return (
    <div>
      <div className="flex items-center justify-between mb-6">
        <h1 className="text-2xl font-bold">📋 Knowledge Entries</h1>
        <input
          type="text"
          placeholder="Filter by tag..."
          value={tagFilter}
          onChange={e => setTagFilter(e.target.value)}
          className="bg-gray-800 border border-gray-700 rounded px-3 py-2 text-sm focus:outline-none focus:border-blue-500"
        />
      </div>

      {loading ? (
        <div className="text-gray-400">Loading...</div>
      ) : entries.length === 0 ? (
        <div className="text-center py-12 text-gray-500">
          <p className="text-4xl mb-4">📭</p>
          <p>No entries yet. Use <code className="bg-gray-800 px-2 py-1 rounded">kgkb add</code> to add knowledge.</p>
        </div>
      ) : (
        <div className="space-y-3">
          {entries.map(entry => (
            <div
              key={entry.id}
              className="bg-gray-800 rounded-lg border border-gray-700 p-4 hover:border-gray-600 transition"
            >
              <div className="flex justify-between items-start">
                <div className="flex-1">
                  <p className="text-gray-200 mb-2">{entry.content}</p>
                  <div className="flex items-center gap-3 text-xs text-gray-500">
                    <span>ID: {entry.id.slice(0, 8)}</span>
                    <span>•</span>
                    <span>{new Date(entry.created_at).toLocaleDateString()}</span>
                    {entry.source && (
                      <>
                        <span>•</span>
                        <a href={entry.source} target="_blank" rel="noreferrer" className="text-blue-500 hover:underline">
                          Source ↗
                        </a>
                      </>
                    )}
                  </div>
                  {entry.tags.length > 0 && (
                    <div className="flex gap-1 mt-2">
                      {entry.tags.map(tag => (
                        <span
                          key={tag}
                          onClick={() => setTagFilter(tag)}
                          className="px-2 py-0.5 text-xs bg-gray-700 text-gray-300 rounded-full cursor-pointer hover:bg-gray-600"
                        >
                          {tag}
                        </span>
                      ))}
                    </div>
                  )}
                </div>
                <button
                  onClick={() => handleDelete(entry.id)}
                  className="text-gray-600 hover:text-red-400 text-sm ml-4"
                >
                  ✕
                </button>
              </div>
            </div>
          ))}
        </div>
      )}
    </div>
  )
}
