/**
 * API Client for KGKB Backend
 */

import axios from 'axios'

const BASE_URL = import.meta.env.VITE_API_URL || 'http://localhost:8000'

const http = axios.create({
  baseURL: BASE_URL,
  timeout: 10000,
  headers: { 'Content-Type': 'application/json' },
})

// Types
export interface GraphNode {
  id: string
  label: string
  content: string
  tags: string[]
  created_at: string
}

export interface GraphEdge {
  id: string
  source: string
  target: string
  type: string
  weight: number
}

export interface GraphData {
  nodes: GraphNode[]
  edges: GraphEdge[]
}

export interface KnowledgeEntry {
  id: string
  content: string
  tags: string[]
  source: string | null
  created_at: string
  updated_at: string
}

export interface SearchResult {
  results: Array<{
    id: string
    content: string
    score?: number
    tags?: string[]
  }>
  total: number
  query: string
}

// API methods
export const api = {
  // Knowledge CRUD
  async createKnowledge(content: string, tags: string[] = [], source?: string): Promise<KnowledgeEntry> {
    const { data } = await http.post('/api/knowledge', { content, tags, source })
    return data
  },

  async getKnowledge(id: string): Promise<KnowledgeEntry> {
    const { data } = await http.get(`/api/knowledge/${id}`)
    return data
  },

  async listKnowledge(tag?: string, limit = 20, offset = 0): Promise<KnowledgeEntry[]> {
    const params: any = { limit, offset }
    if (tag) params.tag = tag
    const { data } = await http.get('/api/knowledge', { params })
    return data
  },

  async deleteKnowledge(id: string): Promise<void> {
    await http.delete(`/api/knowledge/${id}`)
  },

  // Search
  async search(query: string, limit = 10, semantic = false): Promise<SearchResult> {
    const { data } = await http.get('/api/search', {
      params: { q: query, limit, semantic },
    })
    return data
  },

  // Graph
  async getGraph(depth = 2, nodeId?: string): Promise<GraphData> {
    const params: any = { depth }
    if (nodeId) params.node_id = nodeId
    const { data } = await http.get('/api/graph', { params })
    return data
  },

  // Relations
  async createRelation(sourceId: string, targetId: string, type = 'relates_to', weight = 1.0) {
    const { data } = await http.post('/api/relations', {
      source_id: sourceId,
      target_id: targetId,
      type,
      weight,
    })
    return data
  },

  async deleteRelation(id: string): Promise<void> {
    await http.delete(`/api/relations/${id}`)
  },

  // Health
  async health(): Promise<{ status: string; vector_count: number; knowledge_count: number }> {
    const { data } = await http.get('/api/health')
    return data
  },
}
