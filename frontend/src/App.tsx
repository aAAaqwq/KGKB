import React from 'react'
import { BrowserRouter, Routes, Route, Link } from 'react-router-dom'
import { KnowledgeGraph } from './views/KnowledgeGraph'
import { KnowledgeList } from './views/KnowledgeList'
import { SearchView } from './views/SearchView'
import { AddKnowledge } from './views/AddKnowledge'
import './App.css'

export function App() {
  return (
    <BrowserRouter>
      <div className="min-h-screen bg-gray-900 text-white">
        <nav className="bg-gray-800 border-b border-gray-700 px-6 py-4">
          <div className="flex items-center justify-between max-w-7xl mx-auto">
            <Link to="/" className="text-xl font-bold text-blue-400">
              🧠 KGKB
            </Link>
            <div className="flex gap-6">
              <Link to="/" className="hover:text-blue-400 transition">Graph</Link>
              <Link to="/list" className="hover:text-blue-400 transition">List</Link>
              <Link to="/search" className="hover:text-blue-400 transition">Search</Link>
              <Link to="/add" className="hover:text-blue-400 transition">Add</Link>
            </div>
          </div>
        </nav>

        <main className="max-w-7xl mx-auto px-6 py-8">
          <Routes>
            <Route path="/" element={<KnowledgeGraph />} />
            <Route path="/list" element={<KnowledgeList />} />
            <Route path="/search" element={<SearchView />} />
            <Route path="/add" element={<AddKnowledge />} />
          </Routes>
        </main>
      </div>
    </BrowserRouter>
  )
}
