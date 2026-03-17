/**
 * KGKB API Client
 *
 * Complete TypeScript client for the KGKB backend API.
 * Covers: Knowledge CRUD, Relations CRUD, Search (text/semantic/hybrid),
 * Graph data, Tags, Import/Export, Health, Stats, and Embedding status.
 */

import axios, { AxiosInstance, AxiosError } from 'axios'

// ============ HTTP Instance ============

/**
 * Base URL: in dev, Vite proxy forwards /api → backend.
 * In production, the same origin serves both.
 * Only set VITE_API_URL if the backend is on a different host.
 */
const BASE_URL = import.meta.env.VITE_API_URL || ''

const http: AxiosInstance = axios.create({
  baseURL: BASE_URL,
  timeout: 15000,
  headers: { 'Content-Type': 'application/json' },
})

// ============ Types — Knowledge ============

/** A full knowledge entry returned by the backend. */
export interface KnowledgeEntry {
  id: string
  title: string
  content: string
  content_type: string
  tags: string[]
  source: string | null
  created_at: string
  updated_at: string
}

/** Payload for creating a knowledge entry. */
export interface KnowledgeCreatePayload {
  title?: string
  content: string
  content_type?: string
  tags?: string[]
  source?: string
}

/** Payload for updating a knowledge entry (all fields optional). */
export interface KnowledgeUpdatePayload {
  title?: string
  content?: string
  content_type?: string
  tags?: string[]
  source?: string
}

/** Paginated list response for knowledge entries. */
export interface PaginatedKnowledgeResponse {
  items: KnowledgeEntry[]
  total: number
  limit: number
  offset: number
}

// ============ Types — Relations ============

/** A relationship between two knowledge entries. */
export interface RelationEntry {
  id: string
  source_id: string
  target_id: string
  type: string
  weight: number
  created_at: string
}

/** Payload for creating a relation. */
export interface RelationCreatePayload {
  source_id: string
  target_id: string
  type?: string
  weight?: number
}

/** List response for relations. */
export interface RelationListResponse {
  items: RelationEntry[]
  total: number
  node_id: string | null
}

// ============ Types — Search ============

/** A single search result with relevance score. */
export interface SearchResultItem {
  id: string
  title: string
  content: string
  tags: string[]
  source: string | null
  score: number
  created_at: string
}

/** Full search response from /api/knowledge/search. */
export interface KnowledgeSearchResponse {
  results: SearchResultItem[]
  total: number
  query: string
  mode: string
}

/** Search mode options. */
export type SearchMode = 'text' | 'semantic' | 'hybrid'

// ============ Types — Graph ============

/** A node in the knowledge graph. */
export interface GraphNode {
  id: string
  label: string
  content: string
  tags: string[]
  created_at: string
}

/** An edge in the knowledge graph. */
export interface GraphEdge {
  id: string
  source: string
  target: string
  type: string
  weight: number
}

/** Graph data for visualization. */
export interface GraphData {
  nodes: GraphNode[]
  edges: GraphEdge[]
}

// ============ Types — Stats & Health ============

/** Health check response. */
export interface HealthResponse {
  status: string
  version: string
  vector_count: number
  knowledge_count: number
  embedding_available: boolean
}

/** Database stats response. */
export interface StatsResponse {
  knowledge_count: number
  relation_count: number
  embedding_count: number
  tag_counts: Record<string, number>
  [key: string]: unknown
}

/** Embedding service status. */
export interface EmbeddingStatus {
  available: boolean
  provider?: string
  model?: string
  dimension?: number
  endpoint?: string
  embedded_count?: number
  unembedded_count?: number
  reason?: string
  [key: string]: unknown
}

// ============ Types — Legacy Search ============

/** Legacy search response from /api/search. */
export interface LegacySearchResponse {
  results: Array<{
    id: string
    content: string
    score?: number
    tags?: string[]
  }>
  total: number
  query: string
}

// ============ Types — Delete ============

export interface DeleteResponse {
  status: string
  id: string
}

// ============ Error Helper ============

/** Extract a human-readable error message from an Axios error. */
export function getErrorMessage(err: unknown): string {
  if (axios.isAxiosError(err)) {
    const axErr = err as AxiosError<{ detail?: string }>
    if (axErr.response?.data?.detail) {
      return axErr.response.data.detail
    }
    if (axErr.response) {
      return `Server error: ${axErr.response.status}`
    }
    if (axErr.code === 'ECONNABORTED') {
      return 'Request timed out'
    }
    return 'Network error — is the backend running?'
  }
  if (err instanceof Error) return err.message
  return String(err)
}

// ============ API Client ============

export const api = {
  // ---------- Knowledge CRUD ----------

  /** Create a new knowledge entry. */
  async createKnowledge(payload: KnowledgeCreatePayload): Promise<KnowledgeEntry> {
    const { data } = await http.post<KnowledgeEntry>('/api/knowledge', payload)
    return data
  },

  /** Get a single knowledge entry by ID (supports prefix matching). */
  async getKnowledge(id: string): Promise<KnowledgeEntry> {
    const { data } = await http.get<KnowledgeEntry>(`/api/knowledge/${id}`)
    return data
  },

  /** List knowledge entries with pagination and optional filters. */
  async listKnowledge(params?: {
    tag?: string
    content_type?: string
    limit?: number
    offset?: number
  }): Promise<PaginatedKnowledgeResponse> {
    const { data } = await http.get<PaginatedKnowledgeResponse>('/api/knowledge', {
      params: {
        tag: params?.tag || undefined,
        content_type: params?.content_type || undefined,
        limit: params?.limit ?? 20,
        offset: params?.offset ?? 0,
      },
    })
    return data
  },

  /** Update a knowledge entry (partial update — only provided fields change). */
  async updateKnowledge(id: string, payload: KnowledgeUpdatePayload): Promise<KnowledgeEntry> {
    const { data } = await http.put<KnowledgeEntry>(`/api/knowledge/${id}`, payload)
    return data
  },

  /** Delete a knowledge entry by ID. */
  async deleteKnowledge(id: string): Promise<DeleteResponse> {
    const { data } = await http.delete<DeleteResponse>(`/api/knowledge/${id}`)
    return data
  },

  // ---------- Tags ----------

  /** Get all unique tags across all knowledge entries. */
  async listTags(): Promise<string[]> {
    const { data } = await http.get<string[]>('/api/tags')
    return data
  },

  // ---------- Search ----------

  /**
   * Advanced search with mode selection (text/semantic/hybrid).
   * This is the primary search endpoint.
   */
  async searchKnowledge(params: {
    q: string
    mode?: SearchMode
    limit?: number
    min_score?: number
  }): Promise<KnowledgeSearchResponse> {
    const { data } = await http.get<KnowledgeSearchResponse>('/api/knowledge/search', {
      params: {
        q: params.q,
        mode: params.mode ?? 'text',
        limit: params.limit ?? 10,
        min_score: params.min_score ?? 0.0,
      },
    })
    return data
  },

  /**
   * Legacy search endpoint (kept for backward compatibility).
   * Prefer searchKnowledge() for new code.
   */
  async search(query: string, limit = 10, semantic = false): Promise<LegacySearchResponse> {
    const { data } = await http.get<LegacySearchResponse>('/api/search', {
      params: { q: query, limit, semantic },
    })
    return data
  },

  // ---------- Graph ----------

  /** Get graph data for visualization (nodes + edges). */
  async getGraph(params?: {
    depth?: number
    node_id?: string
  }): Promise<GraphData> {
    const { data } = await http.get<GraphData>('/api/graph', {
      params: {
        depth: params?.depth ?? 2,
        node_id: params?.node_id || undefined,
      },
    })
    return data
  },

  // ---------- Relations CRUD ----------

  /** Create a relation between two knowledge entries. */
  async createRelation(payload: RelationCreatePayload): Promise<RelationEntry> {
    const { data } = await http.post<RelationEntry>('/api/relations', {
      source_id: payload.source_id,
      target_id: payload.target_id,
      type: payload.type ?? 'relates_to',
      weight: payload.weight ?? 1.0,
    })
    return data
  },

  /** List relations, optionally filtered by node ID and/or type. */
  async listRelations(params?: {
    node_id?: string
    type?: string
    limit?: number
  }): Promise<RelationListResponse> {
    const { data } = await http.get<RelationListResponse>('/api/relations', {
      params: {
        node_id: params?.node_id || undefined,
        type: params?.type || undefined,
        limit: params?.limit ?? 50,
      },
    })
    return data
  },

  /** Get a single relation by ID. */
  async getRelation(id: string): Promise<RelationEntry> {
    const { data } = await http.get<RelationEntry>(`/api/relations/${id}`)
    return data
  },

  /** Delete a relation by ID. */
  async deleteRelation(id: string): Promise<DeleteResponse> {
    const { data } = await http.delete<DeleteResponse>(`/api/relations/${id}`)
    return data
  },

  /** Get all distinct relation types in use. */
  async listRelationTypes(): Promise<string[]> {
    const { data } = await http.get<string[]>('/api/relations/types')
    return data
  },

  // ---------- Import / Export ----------

  /** Import knowledge entries from a JSON array. */
  async importKnowledge(items: KnowledgeCreatePayload[]): Promise<{ imported: number }> {
    const { data } = await http.post<{ imported: number }>('/api/import', items)
    return data
  },

  /** Export all knowledge as JSON. */
  async exportKnowledge(format: 'json' | 'markdown' = 'json'): Promise<unknown> {
    const { data } = await http.get('/api/export', { params: { format } })
    return data
  },

  // ---------- Health / Stats / Embedding ----------

  /** Health check — returns status, counts, and embedding availability. */
  async health(): Promise<HealthResponse> {
    const { data } = await http.get<HealthResponse>('/api/health')
    return data
  },

  /** Get database statistics (node/edge/embedding counts, tag distribution). */
  async stats(): Promise<StatsResponse> {
    const { data } = await http.get<StatsResponse>('/api/stats')
    return data
  },

  /** Get embedding service status and configuration. */
  async embeddingStatus(): Promise<EmbeddingStatus> {
    const { data } = await http.get<EmbeddingStatus>('/api/embedding/status')
    return data
  },
}

// Default export for convenience
export default api
