/**
 * SearchView - Semantic and keyword search interface
 */

import React, { useState } from 'react'
import { api } from '../api/client'

interface Result {
  id: string
  content: string
  score?: number
  tags?: string[]
}

export function SearchView() {
  const [query, setQuery] = useState('')
  const [results, setResults] = useState<Result[]>([])
  const [searching, setSearching] = useState(false)
  const [semantic, setSemantic] = useState(false)
  const [searched, setSearched] = useState(false)

  const handleSearch = async (e: React.FormEvent) => {
    e.preventDefault()
    if (!query.trim()) return

    try {
      setSearching(true)
      setSearched(true)
      const data = await api.search(query, 20, semantic)
      setResults(data.results)
    } catch (err) {
      console.error('Search failed:', err)
      setResults([])
    } finally {
      setSearching(false)
    }
  }

  return (
    <div>
      <h1 className="text-2xl font-bold mb-6">🔍 Search Knowledge</h1>

      <form onSubmit={handleSearch} className="mb-8">
        <div className="flex gap-3">
          <input
            type="text"
            placeholder="Search your knowledge base..."
            value={query}
            onChange={e => setQuery(e.target.value)}
            className="flex-1 bg-gray-800 border border-gray-700 rounded-lg px-4 py-3 text-lg focus:outline-none focus:border-blue-500"
            autoFocus
          />
          <button
            type="submit"
            disabled={searching}
            className="bg-blue-600 hover:bg-blue-700 px-6 py-3 rounded-lg font-medium transition disabled:opacity-50"
          >
            {searching ? '...' : 'Search'}
          </button>
        </div>
        <label className="flex items-center gap-2 mt-3 text-sm text-gray-400 cursor-pointer">
          <input
            type="checkbox"
            checked={semantic}
            onChange={e => setSemantic(e.target.checked)}
            className="rounded"
          />
          Enable semantic search (requires embedding service)
        </label>
      </form>

      {searching ? (
        <div className="text-gray-400 text-center py-8">Searching...</div>
      ) : results.length > 0 ? (
        <div className="space-y-3">
          <p className="text-sm text-gray-500 mb-4">{results.length} results found</p>
          {results.map((r, i) => (
            <div
              key={r.id}
              className="bg-gray-800 rounded-lg border border-gray-700 p-4 hover:border-gray-600 transition"
            >
              <div className="flex items-start gap-3">
                <span className="text-gray-600 text-sm font-mono mt-1">{i + 1}</span>
                <div className="flex-1">
                  <p className="text-gray-200">{r.content}</p>
                  <div className="flex items-center gap-3 mt-2 text-xs text-gray-500">
                    <span>ID: {r.id.slice(0, 8)}</span>
                    {r.score !== undefined && (
                      <>
                        <span>•</span>
                        <span className="text-green-500">Score: {r.score.toFixed(3)}</span>
                      </>
                    )}
                  </div>
                  {r.tags && r.tags.length > 0 && (
                    <div className="flex gap-1 mt-2">
                      {r.tags.map(tag => (
                        <span key={tag} className="px-2 py-0.5 text-xs bg-gray-700 text-gray-300 rounded-full">
                          {tag}
                        </span>
                      ))}
                    </div>
                  )}
                </div>
              </div>
            </div>
          ))}
        </div>
      ) : searched ? (
        <div className="text-center py-12 text-gray-500">
          <p className="text-4xl mb-4">🔍</p>
          <p>No results found for "{query}"</p>
        </div>
      ) : null}
    </div>
  )
}
