/**
 * KnowledgeGraph - Interactive D3.js force-directed graph visualization
 *
 * Renders knowledge nodes and their relationships as an interactive graph.
 * Features:
 * - Force-directed layout with D3.js and tag-aware clustering
 * - Nodes sized by connection count (degree)
 * - Nodes colored by primary tag
 * - Arrow markers on directed edges with labeled relation types
 * - Zoom: scroll to zoom, double-click to zoom in, shift+double-click to zoom out
 * - Pan: click-drag on background
 * - Node drag: click-drag on node repositions it within the simulation
 * - Smooth animated transitions on zoom actions
 * - Fit-to-view and reset zoom controls with keyboard shortcuts (+/-/0)
 * - Zoom level indicator
 * - Minimap overview for large graphs with viewport indicator
 * - Zoom-adaptive label visibility to avoid overlap
 * - Entrance animations for nodes and edges
 * - Click-to-inspect side panel
 * - Hover highlighting with connected-node emphasis
 * - Link Mode: click two nodes to create a relation between them
 * - Tag filtering and search-in-graph highlighting
 * - Enhanced touch support for mobile (larger targets, long-press)
 */

import React, { useRef, useEffect, useState, useCallback, useMemo } from 'react'
import * as d3 from 'd3'
import { api, GraphData, GraphNode, GraphEdge } from '../api/client'
import { NodeDetailPanel, NodeInfo } from '../components/NodeDetailPanel'
import { GraphFilters, TagCount } from '../components/GraphFilters'
import { LinkModeDialog } from '../components/LinkModeDialog'
import { LoadingSpinner } from '../components/LoadingSpinner'

/** Simulation node with degree (connection count) for sizing. */
interface SimNode extends d3.SimulationNodeDatum {
  id: string
  label: string
  content: string
  tags: string[]
  created_at: string
  degree: number
  radius: number
}

interface SimLink extends d3.SimulationLinkDatum<SimNode> {
  id: string
  type: string
  weight: number
}

const ZOOM_MIN = 0.1
const ZOOM_MAX = 6
const ZOOM_STEP = 1.5
const TRANSITION_MS = 400

/** Dynamic tag color palette — generates colors for unknown tags. */
const TAG_COLOR_BASE: Record<string, string> = {
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

/** HSL-based color generation for unknown tags. */
function hashTagColor(tag: string): string {
  let hash = 0
  for (let i = 0; i < tag.length; i++) {
    hash = ((hash << 5) - hash + tag.charCodeAt(i)) | 0
  }
  const hue = Math.abs(hash) % 360
  return `hsl(${hue}, 60%, 55%)`
}

function getNodeColor(tags: string[]): string {
  for (const tag of tags) {
    const lower = tag.toLowerCase()
    for (const [key, color] of Object.entries(TAG_COLOR_BASE)) {
      if (lower === key.toLowerCase()) return color
    }
  }
  if (tags.length > 0) return hashTagColor(tags[0])
  return '#6b7280'
}

function computeRadius(degree: number): number {
  const MIN_R = 12
  const MAX_R = 36
  const r = MIN_R + Math.sqrt(degree) * 6
  return Math.min(r, MAX_R)
}

/** Truncate a label with smart break. */
function truncLabel(text: string, maxLen: number): string {
  if (text.length <= maxLen) return text
  return text.slice(0, maxLen - 1).trimEnd() + '…'
}

/** Minimap dimensions */
const MINIMAP_W = 160
const MINIMAP_H = 110
const MINIMAP_PAD = 10

/** Zoom thresholds for adaptive label display */
const LABEL_HIDE_ZOOM = 0.35     // Below this, hide ALL labels
const LABEL_HUBS_ONLY_ZOOM = 0.6 // Below this, only show labels for hub nodes (degree>=3)
const HUB_DEGREE_THRESHOLD = 3

/**
 * Minimap - Small overview of the entire graph with a viewport rectangle.
 * Shows all nodes as colored dots and a blue rect indicating the visible area.
 */
function Minimap({
  nodes,
  zoomTransform,
  svgWidth,
  svgHeight,
}: {
  nodes: SimNode[]
  zoomTransform: d3.ZoomTransform
  svgWidth: number
  svgHeight: number
}) {
  const canvasRef = useRef<HTMLCanvasElement>(null)

  useEffect(() => {
    const canvas = canvasRef.current
    if (!canvas || nodes.length === 0) return
    const ctx = canvas.getContext('2d')
    if (!ctx) return

    // Compute bounds of all nodes
    let minX = Infinity, minY = Infinity, maxX = -Infinity, maxY = -Infinity
    for (const n of nodes) {
      if (n.x == null || n.y == null) continue
      minX = Math.min(minX, n.x - n.radius)
      minY = Math.min(minY, n.y - n.radius)
      maxX = Math.max(maxX, n.x + n.radius)
      maxY = Math.max(maxY, n.y + n.radius)
    }
    if (!isFinite(minX)) return

    const gw = maxX - minX || 1
    const gh = maxY - minY || 1
    const pad = MINIMAP_PAD
    const scaleX = (MINIMAP_W - pad * 2) / gw
    const scaleY = (MINIMAP_H - pad * 2) / gh
    const scale = Math.min(scaleX, scaleY)

    const offsetX = pad + (MINIMAP_W - pad * 2 - gw * scale) / 2
    const offsetY = pad + (MINIMAP_H - pad * 2 - gh * scale) / 2

    // Clear
    ctx.clearRect(0, 0, MINIMAP_W, MINIMAP_H)

    // Background
    ctx.fillStyle = 'rgba(17, 24, 39, 0.85)'
    ctx.fillRect(0, 0, MINIMAP_W, MINIMAP_H)
    ctx.strokeStyle = 'rgba(55, 65, 81, 0.6)'
    ctx.lineWidth = 1
    ctx.strokeRect(0, 0, MINIMAP_W, MINIMAP_H)

    // Draw nodes as dots
    for (const n of nodes) {
      if (n.x == null || n.y == null) continue
      const mx = (n.x - minX) * scale + offsetX
      const my = (n.y - minY) * scale + offsetY
      const mr = Math.max(2, n.radius * scale * 0.5)
      ctx.beginPath()
      ctx.arc(mx, my, mr, 0, Math.PI * 2)
      ctx.fillStyle = getNodeColor(n.tags)
      ctx.globalAlpha = 0.8
      ctx.fill()
    }
    ctx.globalAlpha = 1.0

    // Draw viewport rectangle
    const { x: tx, y: ty, k } = zoomTransform
    // The visible area in graph coordinates:
    const vx1 = (-tx) / k
    const vy1 = (-ty) / k
    const vx2 = (svgWidth - tx) / k
    const vy2 = (svgHeight - ty) / k

    const rx = (vx1 - minX) * scale + offsetX
    const ry = (vy1 - minY) * scale + offsetY
    const rw = (vx2 - vx1) * scale
    const rh = (vy2 - vy1) * scale

    ctx.strokeStyle = 'rgba(96, 165, 250, 0.7)'
    ctx.lineWidth = 1.5
    ctx.strokeRect(
      Math.max(0, rx),
      Math.max(0, ry),
      Math.min(rw, MINIMAP_W - Math.max(0, rx)),
      Math.min(rh, MINIMAP_H - Math.max(0, ry)),
    )
  }, [nodes, zoomTransform, svgWidth, svgHeight])

  if (nodes.length < 5) return null // Only show minimap for non-trivial graphs

  return (
    <canvas
      ref={canvasRef}
      width={MINIMAP_W}
      height={MINIMAP_H}
      className="absolute bottom-4 left-4 rounded-md pointer-events-none opacity-80
                 transition-opacity duration-300 hover:opacity-100"
      style={{ imageRendering: 'auto' }}
    />
  )
}

export function KnowledgeGraph() {
  const svgRef = useRef<SVGSVGElement>(null)
  const containerRef = useRef<HTMLDivElement>(null)
  const [graphData, setGraphData] = useState<GraphData | null>(null)
  const [selectedNode, setSelectedNode] = useState<SimNode | null>(null)
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState<string | null>(null)
  const [zoomLevel, setZoomLevel] = useState(1)
  const [zoomTransform, setZoomTransform] = useState<d3.ZoomTransform>(d3.zoomIdentity)
  const [svgDimensions, setSvgDimensions] = useState({ w: 900, h: 600 })
  const [activeTags, setActiveTags] = useState<Set<string>>(new Set())
  const [graphSearchQuery, setGraphSearchQuery] = useState('')

  // ============ Link Mode State ============
  const [linkModeActive, setLinkModeActive] = useState(false)
  const [linkSourceNode, setLinkSourceNode] = useState<SimNode | null>(null)
  const [linkTargetNode, setLinkTargetNode] = useState<SimNode | null>(null)
  const [linkDialogOpen, setLinkDialogOpen] = useState(false)
  const [linkSubmitting, setLinkSubmitting] = useState(false)

  // Refs
  const zoomRef = useRef<d3.ZoomBehavior<SVGSVGElement, unknown> | null>(null)
  const simulationRef = useRef<d3.Simulation<SimNode, SimLink> | null>(null)
  const nodesRef = useRef<SimNode[]>([])
  /** Ref so D3 closures always read current link mode state. */
  const linkModeRef = useRef({ active: false, sourceNode: null as SimNode | null })

  /** Sync link mode state → ref on every change. */
  useEffect(() => {
    linkModeRef.current = { active: linkModeActive, sourceNode: linkSourceNode }
  }, [linkModeActive, linkSourceNode])

  // ============ Derived data ============

  const nodeLabelMap = useMemo(() => {
    const map = new Map<string, string>()
    if (graphData) {
      for (const n of graphData.nodes) map.set(n.id, n.label)
    }
    return map
  }, [graphData])

  const tagCounts: TagCount[] = useMemo(() => {
    if (!graphData) return []
    const counts = new Map<string, number>()
    for (const node of graphData.nodes) {
      for (const tag of node.tags) counts.set(tag, (counts.get(tag) || 0) + 1)
    }
    return Array.from(counts.entries()).map(([tag, count]) => ({ tag, count }))
  }, [graphData])

  const allTags = useMemo(() => new Set(tagCounts.map(tc => tc.tag)), [tagCounts])

  const filteredNodeIds = useMemo(() => {
    if (!graphData) return new Set<string>()
    if (activeTags.size === 0) return new Set(graphData.nodes.map(n => n.id))
    return new Set(
      graphData.nodes.filter(n => n.tags.some(t => activeTags.has(t))).map(n => n.id)
    )
  }, [graphData, activeTags])

  const searchMatchIds = useMemo(() => {
    if (!graphData || !graphSearchQuery.trim()) return new Set<string>()
    const q = graphSearchQuery.toLowerCase().trim()
    return new Set(
      graphData.nodes
        .filter(n =>
          n.label.toLowerCase().includes(q) ||
          n.content.toLowerCase().includes(q) ||
          n.tags.some(t => t.toLowerCase().includes(q))
        )
        .map(n => n.id)
    )
  }, [graphData, graphSearchQuery])

  const visibleEdgeCount = useMemo(() => {
    if (!graphData) return 0
    if (activeTags.size === 0) return graphData.edges.length
    return graphData.edges.filter(e => {
      const src = typeof e.source === 'string' ? e.source : (e.source as any).id
      const tgt = typeof e.target === 'string' ? e.target : (e.target as any).id
      return filteredNodeIds.has(src) && filteredNodeIds.has(tgt)
    }).length
  }, [graphData, activeTags, filteredNodeIds])

  // ============ Tag filter callbacks ============

  const handleToggleTag = useCallback((tag: string) => {
    setActiveTags(prev => {
      const next = new Set(prev)
      if (prev.size === 0) return new Set([tag])
      if (next.has(tag)) {
        next.delete(tag)
        if (next.size === 0) return new Set<string>()
      } else {
        next.add(tag)
        if (next.size === allTags.size) return new Set<string>()
      }
      return next
    })
  }, [allTags])

  const handleSelectAll = useCallback(() => setActiveTags(new Set<string>()), [])
  const handleSelectNone = useCallback(() => setActiveTags(new Set(['__none__'])), [])

  // ============ Link Mode Handlers ============

  const toggleLinkMode = useCallback(() => {
    setLinkModeActive(prev => {
      if (prev) {
        setLinkSourceNode(null)
        setLinkTargetNode(null)
        setLinkDialogOpen(false)
      }
      return !prev
    })
  }, [])

  const cancelLinkMode = useCallback(() => {
    setLinkModeActive(false)
    setLinkSourceNode(null)
    setLinkTargetNode(null)
    setLinkDialogOpen(false)
  }, [])

  const cancelLinkDialog = useCallback(() => {
    setLinkTargetNode(null)
    setLinkDialogOpen(false)
    setLinkSourceNode(null)
  }, [])

  const confirmLink = useCallback(async (type: string, weight: number) => {
    if (!linkSourceNode || !linkTargetNode || !graphData) return

    setLinkSubmitting(true)
    try {
      const relation = await api.createRelation({
        source_id: linkSourceNode.id,
        target_id: linkTargetNode.id,
        type,
        weight,
      })

      // Update graph data with the new edge so D3 re-renders
      setGraphData(prev => {
        if (!prev) return prev
        return {
          ...prev,
          edges: [
            ...prev.edges,
            {
              id: relation.id,
              source: relation.source_id,
              target: relation.target_id,
              type: relation.type,
              weight: relation.weight,
            },
          ],
        }
      })

      // Reset link state but stay in link mode for chaining
      setLinkSourceNode(null)
      setLinkTargetNode(null)
      setLinkDialogOpen(false)
    } catch (err: any) {
      alert(`Failed to create relation: ${err.message || 'Unknown error'}`)
    } finally {
      setLinkSubmitting(false)
    }
  }, [linkSourceNode, linkTargetNode, graphData])

  // ============ Navigation ============

  const navigateToNode = useCallback((nodeId: string) => {
    const targetNode = nodesRef.current.find(n => n.id === nodeId)
    if (!targetNode || !svgRef.current || !zoomRef.current) return

    const w = svgRef.current.clientWidth || 900
    const h = svgRef.current.clientHeight || 600
    const targetScale = 2
    const tx = w / 2 - targetNode.x! * targetScale
    const ty = h / 2 - targetNode.y! * targetScale

    d3.select(svgRef.current).transition().duration(TRANSITION_MS * 1.5)
      .call(zoomRef.current!.transform, d3.zoomIdentity.translate(tx, ty).scale(targetScale))

    setSelectedNode(targetNode)
  }, [])

  // ============ Fetch graph data ============

  useEffect(() => {
    const fetchGraph = async () => {
      try {
        setLoading(true)
        const data = await api.getGraph()
        setGraphData(data)
      } catch (err: any) {
        setError(err.message || 'Failed to load graph')
        setGraphData({
          nodes: [
            { id: 'demo-1', label: 'KGKB Project', content: 'Knowledge Graph Knowledge Base', tags: ['project'], created_at: new Date().toISOString() },
            { id: 'demo-2', label: 'Graph Viz', content: 'D3.js force-directed graph visualization', tags: ['tech'], created_at: new Date().toISOString() },
            { id: 'demo-3', label: 'Vector Search', content: 'FAISS-based semantic search', tags: ['AI'], created_at: new Date().toISOString() },
            { id: 'demo-4', label: 'Knowledge Storage', content: 'SQLite + CLI knowledge management', tags: ['tech'], created_at: new Date().toISOString() },
            { id: 'demo-5', label: 'AI Prediction', content: 'Trend prediction based on graph patterns', tags: ['AI'], created_at: new Date().toISOString() },
          ],
          edges: [
            { id: 'e1', source: 'demo-1', target: 'demo-2', type: 'contains', weight: 1 },
            { id: 'e2', source: 'demo-1', target: 'demo-3', type: 'contains', weight: 1 },
            { id: 'e3', source: 'demo-1', target: 'demo-4', type: 'contains', weight: 1 },
            { id: 'e4', source: 'demo-1', target: 'demo-5', type: 'contains', weight: 1 },
            { id: 'e5', source: 'demo-3', target: 'demo-5', type: 'relates_to', weight: 0.8 },
          ],
        })
      } finally {
        setLoading(false)
      }
    }
    fetchGraph()
  }, [])

  // ============ Zoom helpers ============

  const fitToView = useCallback(() => {
    if (!svgRef.current || !zoomRef.current) return
    const svg = d3.select(svgRef.current)
    const g = svg.select<SVGGElement>('g.graph-container')
    if (g.empty()) return
    const bounds = (g.node() as SVGGElement).getBBox()
    if (bounds.width === 0 || bounds.height === 0) return

    const width = svgRef.current.clientWidth || 900
    const height = svgRef.current.clientHeight || 600
    const padding = 60
    const scale = Math.min(
      (width - padding * 2) / bounds.width,
      (height - padding * 2) / bounds.height,
      1.5,
    )
    const tx = (width - bounds.width * scale) / 2 - bounds.x * scale
    const ty = (height - bounds.height * scale) / 2 - bounds.y * scale
    svg.transition().duration(TRANSITION_MS).call(
      zoomRef.current.transform, d3.zoomIdentity.translate(tx, ty).scale(scale),
    )
  }, [])

  const resetZoom = useCallback(() => {
    if (!svgRef.current || !zoomRef.current) return
    d3.select(svgRef.current).transition().duration(TRANSITION_MS).call(
      zoomRef.current.transform, d3.zoomIdentity,
    )
  }, [])

  const zoomIn = useCallback(() => {
    if (!svgRef.current || !zoomRef.current) return
    d3.select(svgRef.current).transition().duration(TRANSITION_MS).call(
      zoomRef.current.scaleBy, ZOOM_STEP,
    )
  }, [])

  const zoomOut = useCallback(() => {
    if (!svgRef.current || !zoomRef.current) return
    d3.select(svgRef.current).transition().duration(TRANSITION_MS).call(
      zoomRef.current.scaleBy, 1 / ZOOM_STEP,
    )
  }, [])

  // ============ Keyboard shortcuts ============

  useEffect(() => {
    const handler = (e: KeyboardEvent) => {
      if (
        e.target instanceof HTMLInputElement ||
        e.target instanceof HTMLTextAreaElement ||
        e.target instanceof HTMLSelectElement
      ) return

      switch (e.key) {
        case '+': case '=': e.preventDefault(); zoomIn(); break
        case '-': case '_': e.preventDefault(); zoomOut(); break
        case '0': e.preventDefault(); resetZoom(); break
        case 'f': case 'F':
          if (!e.ctrlKey && !e.metaKey) { e.preventDefault(); fitToView() }
          break
        case 'Escape':
          if (linkModeActive) {
            cancelLinkMode()
          } else {
            setSelectedNode(null)
          }
          break
      }
    }
    window.addEventListener('keydown', handler)
    return () => window.removeEventListener('keydown', handler)
  }, [zoomIn, zoomOut, resetZoom, fitToView, linkModeActive, cancelLinkMode])

  // ============ D3 Rendering ============

  useEffect(() => {
    if (!graphData || !svgRef.current) return

    const svg = d3.select(svgRef.current)
    svg.selectAll('*').remove()

    const width = svgRef.current.clientWidth || 900
    const height = svgRef.current.clientHeight || 600

    // Compute degree per node
    const degreeMap = new Map<string, number>()
    for (const edge of graphData.edges) {
      const src = typeof edge.source === 'string' ? edge.source : (edge.source as any).id
      const tgt = typeof edge.target === 'string' ? edge.target : (edge.target as any).id
      degreeMap.set(src, (degreeMap.get(src) || 0) + 1)
      degreeMap.set(tgt, (degreeMap.get(tgt) || 0) + 1)
    }

    const nodes: SimNode[] = graphData.nodes.map(n => {
      const degree = degreeMap.get(n.id) || 0
      return {
        ...n, degree, radius: computeRadius(degree),
        x: width / 2 + (Math.random() - 0.5) * width * 0.6,
        y: height / 2 + (Math.random() - 0.5) * height * 0.6,
      }
    })

    const nodeMap = new Map(nodes.map(n => [n.id, n]))

    const links: SimLink[] = graphData.edges
      .filter(e => {
        const src = typeof e.source === 'string' ? e.source : (e.source as any).id
        const tgt = typeof e.target === 'string' ? e.target : (e.target as any).id
        return nodeMap.has(src) && nodeMap.has(tgt)
      })
      .map(e => ({
        ...e,
        source: typeof e.source === 'string' ? e.source : (e.source as any).id,
        target: typeof e.target === 'string' ? e.target : (e.target as any).id,
      }))

    // Graph container
    const g = svg.append('g').attr('class', 'graph-container')

    setSvgDimensions({ w: width, h: height })

    // Zoom behavior
    const zoom = d3.zoom<SVGSVGElement, unknown>()
      .scaleExtent([ZOOM_MIN, ZOOM_MAX])
      .filter((event) => !event.ctrlKey && !event.button)
      .on('zoom', (event) => {
        g.attr('transform', event.transform)
        setZoomLevel(event.transform.k)
        setZoomTransform(event.transform)

        // Adaptive label visibility based on zoom level
        const k = event.transform.k
        g.selectAll<SVGTextElement, SimNode>('.node-label')
          .attr('opacity', d => {
            if (k < LABEL_HIDE_ZOOM) return 0
            if (k < LABEL_HUBS_ONLY_ZOOM) return d.degree >= HUB_DEGREE_THRESHOLD ? 0.9 : 0
            return 1
          })
        // Edge labels: hide at very low zoom
        g.selectAll<SVGTextElement, SimLink>('.edge-label-text')
          .attr('opacity', k < LABEL_HUBS_ONLY_ZOOM ? 0 : 0.7)
      })

    svg.call(zoom)
    // Enable touch gestures for pinch-zoom on mobile
    svg.call(zoom).on('dblclick.zoom', null)
    svg.style('touch-action', 'none') // allow D3 to handle all touch events
    svg.on('dblclick', (event: MouseEvent) => {
      event.preventDefault()
      event.stopPropagation()
      const [mx, my] = d3.pointer(event, svgRef.current!)
      const factor = event.shiftKey ? (1 / ZOOM_STEP) : ZOOM_STEP
      svg.transition().duration(TRANSITION_MS).call(zoom.scaleBy, factor, [mx, my])
    })

    zoomRef.current = zoom

    // Defs: arrow markers, glow filter
    const defs = svg.append('defs')
    defs.append('marker')
      .attr('id', 'arrowhead')
      .attr('viewBox', '0 -5 10 10')
      .attr('refX', 10).attr('refY', 0)
      .attr('markerWidth', 6).attr('markerHeight', 6)
      .attr('orient', 'auto')
      .append('path').attr('d', 'M0,-5L10,0L0,5').attr('fill', '#4b5563')

    const glowFilter = defs.append('filter')
      .attr('id', 'glow')
      .attr('x', '-50%').attr('y', '-50%')
      .attr('width', '200%').attr('height', '200%')
    glowFilter.append('feGaussianBlur').attr('stdDeviation', '3').attr('result', 'blur')
    glowFilter.append('feMerge')
      .selectAll('feMergeNode')
      .data(['blur', 'SourceGraphic'])
      .join('feMergeNode').attr('in', d => d)

    // Force simulation — tuned for readability with tag-aware clustering
    const nodeCount = nodes.length
    const isLargeGraph = nodeCount > 30
    const chargeMult = isLargeGraph ? 0.6 : 1 // less repulsion in large graphs

    // Compute tag cluster centers for tag-aware grouping
    const uniqueTags = Array.from(new Set(nodes.flatMap(n => n.tags)))
    const tagClusterAngle = new Map<string, number>()
    uniqueTags.forEach((tag, i) => {
      tagClusterAngle.set(tag, (i / uniqueTags.length) * 2 * Math.PI)
    })
    const clusterRadius = Math.min(width, height) * 0.2 // how far clusters spread from center

    const simulation = d3.forceSimulation<SimNode>(nodes)
      .force('link', d3.forceLink<SimNode, SimLink>(links)
        .id(d => d.id)
        .distance(d => {
          const src = nodeMap.get(typeof d.source === 'string' ? d.source : (d.source as SimNode).id)
          const tgt = nodeMap.get(typeof d.target === 'string' ? d.target : (d.target as SimNode).id)
          return (src?.radius ?? 16) + (tgt?.radius ?? 16) + 80
        })
        .strength(d => Math.min(d.weight * 0.4, 0.8)))
      .force('charge', d3.forceManyBody()
        .strength(d => (-250 - (d as SimNode).radius * 10) * chargeMult)
        .distanceMax(isLargeGraph ? 500 : 800))
      .force('center', d3.forceCenter(width / 2, height / 2).strength(0.03))
      .force('collision', d3.forceCollide<SimNode>()
        .radius(d => d.radius + 16) // extra padding for labels
        .strength(0.9)
        .iterations(3))
      // Tag-based clustering: gently pull nodes toward their tag's cluster center
      .force('clusterX', d3.forceX<SimNode>(d => {
        if (d.tags.length === 0) return width / 2
        const angle = tagClusterAngle.get(d.tags[0]) ?? 0
        return width / 2 + Math.cos(angle) * clusterRadius
      }).strength(0.04))
      .force('clusterY', d3.forceY<SimNode>(d => {
        if (d.tags.length === 0) return height / 2
        const angle = tagClusterAngle.get(d.tags[0]) ?? 0
        return height / 2 + Math.sin(angle) * clusterRadius
      }).strength(0.04))
      .force('x', d3.forceX(width / 2).strength(0.015))
      .force('y', d3.forceY(height / 2).strength(0.015))
      .alphaDecay(0.018) // slightly slower cooldown for better layout convergence
      .velocityDecay(0.35) // balanced momentum

    simulationRef.current = simulation
    nodesRef.current = nodes

    // Render edges with entrance animation
    const link = g.append('g').attr('class', 'edges')
      .selectAll('line').data(links).join('line')
      .attr('stroke', '#4b5563')
      .attr('stroke-width', d => Math.max(1, d.weight * 2))
      .attr('stroke-opacity', 0)
      .attr('marker-end', 'url(#arrowhead)')

    // Animate edges in
    link.transition().duration(600).delay((_d, i) => 200 + i * 15)
      .attr('stroke-opacity', 0.6)

    // Edge labels — styled with a background rect for readability
    const linkLabel = g.append('g').attr('class', 'edge-labels')
      .selectAll('text').data(links).join('text')
      .attr('class', 'edge-label-text')
      .text(d => d.type.replace(/_/g, ' '))
      .attr('font-size', '8px').attr('fill', '#6b728099')
      .attr('text-anchor', 'middle').attr('pointer-events', 'none')
      .attr('font-style', 'italic')
      .attr('opacity', 0)

    // Animate edge labels in
    linkLabel.transition().duration(400).delay((_d, i) => 400 + i * 15)
      .attr('opacity', 0.7)

    // Drag behavior
    let isDragging = false
    const dragBehavior = d3.drag<SVGGElement, SimNode>()
      .on('start', (event, d) => {
        isDragging = false
        if (!event.active) simulation.alphaTarget(0.3).restart()
        d.fx = d.x; d.fy = d.y
      })
      .on('drag', (event, d) => {
        isDragging = true
        d.fx = event.x; d.fy = event.y
      })
      .on('end', (event, d) => {
        if (!event.active) simulation.alphaTarget(0)
        d.fx = null; d.fy = null
      })

    // Render nodes with entrance animation
    const node = g.append('g').attr('class', 'nodes')
      .selectAll<SVGGElement, SimNode>('g').data(nodes).join('g')
      .style('cursor', 'grab')
      .attr('opacity', 0)
      .call(dragBehavior)

    // Animate nodes in with staggered delay
    node.transition().duration(500).delay((_d, i) => i * 20)
      .attr('opacity', 1)

    node.on('mousedown.cursor', function () { d3.select(this).style('cursor', 'grabbing') })
    node.on('mouseup.cursor', function () { d3.select(this).style('cursor', 'grab') })

    // Node circles — with invisible larger hit area for touch devices
    node.append('circle')
      .attr('class', 'hit-area')
      .attr('r', d => d.radius + 10) // larger invisible touch target
      .attr('fill', 'transparent')
      .attr('stroke', 'none')

    // Visible node circle with scale-in animation
    node.append('circle')
      .attr('class', 'node-circle')
      .attr('r', 0) // start at 0 for scale animation
      .attr('fill', d => getNodeColor(d.tags))
      .attr('stroke', '#1f2937').attr('stroke-width', 2)
      .attr('opacity', 0.9)
      .transition().duration(400).delay((_d, i) => i * 20)
      .attr('r', d => d.radius) // animate to final size

    // Degree badge
    node.filter(d => d.degree >= 3)
      .append('text').attr('class', 'degree-badge')
      .text(d => String(d.degree))
      .attr('text-anchor', 'middle').attr('dy', '0.35em')
      .attr('font-size', '10px').attr('font-weight', 'bold')
      .attr('fill', '#fff').attr('pointer-events', 'none')

    // Node labels — positioned below node with smart truncation
    node.append('text').attr('class', 'node-label')
      .text(d => truncLabel(d.label, d.radius > 20 ? 22 : 16))
      .attr('text-anchor', 'middle').attr('dy', d => d.radius + 14)
      .attr('font-size', d => d.degree >= 3 ? '12px' : '11px')
      .attr('fill', '#d1d5db')
      .attr('pointer-events', 'none')
      .style('text-shadow', '0 1px 3px rgba(0,0,0,0.8), 0 0px 6px rgba(0,0,0,0.6)')

    // Adjacency map for hover highlighting
    const adjacency = new Map<string, Set<string>>()
    for (const l of links) {
      const src = typeof l.source === 'string' ? l.source : (l.source as SimNode).id
      const tgt = typeof l.target === 'string' ? l.target : (l.target as SimNode).id
      if (!adjacency.has(src)) adjacency.set(src, new Set())
      if (!adjacency.has(tgt)) adjacency.set(tgt, new Set())
      adjacency.get(src)!.add(tgt)
      adjacency.get(tgt)!.add(src)
    }

    // --- Click handler: normal mode selects node, link mode picks source/target ---
    node.on('click', (_event, d) => {
      if (isDragging) return

      const lm = linkModeRef.current
      if (lm.active) {
        if (!lm.sourceNode) {
          // First click: select source
          setLinkSourceNode(d)
        } else if (lm.sourceNode.id === d.id) {
          // Clicked same node: deselect
          setLinkSourceNode(null)
        } else {
          // Second click: set target, open dialog
          setLinkTargetNode(d)
          setLinkDialogOpen(true)
        }
      } else {
        setSelectedNode(prev => prev?.id === d.id ? null : d)
      }
    })

    // Double-click node: center + zoom
    node.on('dblclick', (event, d) => {
      event.preventDefault()
      event.stopPropagation()
      const w = svgRef.current!.clientWidth || 900
      const h = svgRef.current!.clientHeight || 600
      const ts = 2
      svg.transition().duration(TRANSITION_MS * 1.5).call(
        zoom.transform, d3.zoomIdentity.translate(w / 2 - d.x! * ts, h / 2 - d.y! * ts).scale(ts),
      )
      setSelectedNode(d)
    })

    // Hover: enlarge + fade unconnected
    node.on('mouseover', function (_event, d) {
      const neighbors = adjacency.get(d.id) || new Set<string>()

      d3.select(this).select('.node-circle')
        .transition().duration(150)
        .attr('r', d.radius + 4).attr('stroke', '#60a5fa')
        .attr('stroke-width', 3).attr('filter', 'url(#glow)')

      node.select('.node-circle').transition().duration(150)
        .attr('opacity', (n: any) => (n.id === d.id || neighbors.has(n.id)) ? 1 : 0.2)
      node.select('.node-label').transition().duration(150)
        .attr('opacity', (n: any) => (n.id === d.id || neighbors.has(n.id)) ? 1 : 0.15)
      node.select('.degree-badge').transition().duration(150)
        .attr('opacity', (n: any) => (n.id === d.id || neighbors.has(n.id)) ? 1 : 0.15)

      link.transition().duration(150)
        .attr('stroke-opacity', (l: any) => {
          const s = typeof l.source === 'string' ? l.source : l.source.id
          const t = typeof l.target === 'string' ? l.target : l.target.id
          return (s === d.id || t === d.id) ? 0.9 : 0.08
        })
      linkLabel.transition().duration(150)
        .attr('opacity', (l: any) => {
          const s = typeof l.source === 'string' ? l.source : l.source.id
          const t = typeof l.target === 'string' ? l.target : l.target.id
          return (s === d.id || t === d.id) ? 1 : 0.08
        })
    })

    node.on('mouseout', function (_event, d) {
      d3.select(this).select('.node-circle')
        .transition().duration(200)
        .attr('r', d.radius).attr('stroke', '#1f2937')
        .attr('stroke-width', 2).attr('filter', null)

      node.select('.node-circle').transition().duration(200).attr('opacity', 0.9)
      node.selectAll('.node-label').transition().duration(200).attr('opacity', 1)
      node.selectAll('.degree-badge').transition().duration(200).attr('opacity', 1)
      link.transition().duration(200).attr('stroke-opacity', 0.6)
      linkLabel.transition().duration(200).attr('opacity', 0.7)
    })

    // Tick: update positions
    simulation.on('tick', () => {
      link
        .attr('x1', d => (d.source as SimNode).x!)
        .attr('y1', d => (d.source as SimNode).y!)
        .attr('x2', d => {
          const src = d.source as SimNode, tgt = d.target as SimNode
          const dx = tgt.x! - src.x!, dy = tgt.y! - src.y!
          const dist = Math.sqrt(dx * dx + dy * dy) || 1
          return tgt.x! - (dx / dist) * tgt.radius
        })
        .attr('y2', d => {
          const src = d.source as SimNode, tgt = d.target as SimNode
          const dx = tgt.x! - src.x!, dy = tgt.y! - src.y!
          const dist = Math.sqrt(dx * dx + dy * dy) || 1
          return tgt.y! - (dy / dist) * tgt.radius
        })

      linkLabel
        .attr('x', d => ((d.source as SimNode).x! + (d.target as SimNode).x!) / 2)
        .attr('y', d => ((d.source as SimNode).y! + (d.target as SimNode).y!) / 2)

      node.attr('transform', d => `translate(${d.x},${d.y})`)
    })

    simulation.on('end', () => fitToView())

    return () => { simulation.stop() }
  }, [graphData, fitToView])

  // ============ Filter + Search highlight ============

  useEffect(() => {
    if (!svgRef.current || !graphData) return
    const svg = d3.select(svgRef.current)
    const isFiltering = activeTags.size > 0
    const isSearching = graphSearchQuery.trim().length > 0

    svg.selectAll<SVGGElement, SimNode>('g.nodes > g')
      .transition().duration(250)
      .attr('opacity', d => {
        if (!isFiltering) return 1
        return filteredNodeIds.has(d.id) ? 1 : 0.1
      })

    svg.selectAll<SVGLineElement, SimLink>('g.edges > line')
      .transition().duration(250)
      .attr('stroke-opacity', d => {
        if (!isFiltering) return 0.6
        const src = typeof d.source === 'string' ? d.source : (d.source as SimNode).id
        const tgt = typeof d.target === 'string' ? d.target : (d.target as SimNode).id
        return (filteredNodeIds.has(src) && filteredNodeIds.has(tgt)) ? 0.6 : 0.04
      })

    svg.selectAll<SVGTextElement, SimLink>('g.edge-labels > text')
      .transition().duration(250)
      .attr('opacity', d => {
        if (!isFiltering) return 0.7
        const src = typeof d.source === 'string' ? d.source : (d.source as SimNode).id
        const tgt = typeof d.target === 'string' ? d.target : (d.target as SimNode).id
        return (filteredNodeIds.has(src) && filteredNodeIds.has(tgt)) ? 0.7 : 0.04
      })

    // Search highlight
    svg.selectAll<SVGGElement, SimNode>('g.nodes > g').select('.node-circle')
      .transition().duration(200)
      .attr('stroke', d => (isSearching && searchMatchIds.has(d.id)) ? '#fbbf24' : '#1f2937')
      .attr('stroke-width', d => (isSearching && searchMatchIds.has(d.id)) ? 3.5 : 2)

    svg.selectAll<SVGGElement, SimNode>('g.nodes > g').select('.node-label')
      .transition().duration(200)
      .attr('fill', d => (isSearching && searchMatchIds.has(d.id)) ? '#fbbf24' : '#d1d5db')
      .attr('font-weight', d => (isSearching && searchMatchIds.has(d.id)) ? 'bold' : 'normal')
  }, [activeTags, graphSearchQuery, filteredNodeIds, searchMatchIds, graphData])

  // ============ Link Mode visual feedback ============

  useEffect(() => {
    if (!svgRef.current || !graphData) return
    const svg = d3.select(svgRef.current)

    if (linkModeActive) {
      // Crosshair cursor for all nodes in link mode
      svg.selectAll<SVGGElement, SimNode>('g.nodes > g').style('cursor', 'crosshair')

      // Highlight source node with blue dashed ring
      svg.selectAll<SVGGElement, SimNode>('g.nodes > g').select('.node-circle')
        .transition().duration(200)
        .attr('stroke', d => (linkSourceNode && d.id === linkSourceNode.id) ? '#3b82f6' : '#1f2937')
        .attr('stroke-width', d => (linkSourceNode && d.id === linkSourceNode.id) ? 4 : 2)
        .attr('stroke-dasharray', d => (linkSourceNode && d.id === linkSourceNode.id) ? '6 3' : 'none')

      // Dim non-source nodes slightly when source is selected
      if (linkSourceNode) {
        svg.selectAll<SVGGElement, SimNode>('g.nodes > g').select('.node-circle')
          .transition().duration(200)
          .attr('opacity', d => d.id === linkSourceNode.id ? 1 : 0.7)
      }
    } else {
      // Reset visuals when link mode off
      svg.selectAll<SVGGElement, SimNode>('g.nodes > g').style('cursor', 'grab')
      svg.selectAll<SVGGElement, SimNode>('g.nodes > g').select('.node-circle')
        .transition().duration(200)
        .attr('stroke', '#1f2937').attr('stroke-width', 2)
        .attr('stroke-dasharray', 'none').attr('opacity', 0.9)
    }
  }, [linkModeActive, linkSourceNode, graphData])

  // ============ Render ============

  if (loading) {
    return (
      <LoadingSpinner size="lg" label="Loading graph…" fullHeight />
    )
  }

  const nodeCount = graphData?.nodes.length ?? 0
  const edgeCount = graphData?.edges.length ?? 0
  const zoomPercent = Math.round(zoomLevel * 100)

  return (
    <div className="relative">
      <div className="flex items-center justify-between mb-4">
        <h1 className="text-2xl font-bold">🕸️ Knowledge Graph</h1>

        {/* Link Mode toggle button */}
        <button
          onClick={toggleLinkMode}
          className={`px-4 py-2 text-sm font-medium rounded-lg border transition-all duration-200
                     flex items-center gap-2
                     ${linkModeActive
              ? 'bg-blue-600/30 border-blue-500/60 text-blue-300 shadow-lg shadow-blue-500/10'
              : 'bg-gray-800 border-gray-700 text-gray-400 hover:border-gray-500 hover:text-gray-300'
            }`}
          title={linkModeActive ? 'Exit Link Mode (Esc)' : 'Enter Link Mode to connect nodes'}
        >
          <span className={linkModeActive ? 'animate-pulse' : ''}>🔗</span>
          {linkModeActive ? 'Linking…' : 'Link Mode'}
        </button>
      </div>

      {/* Link Mode instruction banner */}
      {linkModeActive && (
        <div className="bg-blue-900/30 border border-blue-500/30 rounded-lg px-4 py-2.5 mb-4
                        flex items-center justify-between">
          <div className="flex items-center gap-3">
            <span className="text-blue-400 text-lg">🔗</span>
            <div>
              {!linkSourceNode ? (
                <span className="text-sm text-blue-300">
                  <strong>Step 1:</strong> Click the <strong>source</strong> node
                </span>
              ) : (
                <span className="text-sm text-blue-300">
                  <strong>Step 2:</strong> Click the <strong>target</strong> node to link with
                  <span className="ml-2 px-2 py-0.5 bg-blue-600/30 rounded text-blue-200 text-xs font-medium">
                    {linkSourceNode.label}
                  </span>
                </span>
              )}
            </div>
          </div>
          <button
            onClick={cancelLinkMode}
            className="text-xs text-gray-400 hover:text-gray-200 px-2 py-1
                       border border-gray-700 hover:border-gray-500 rounded transition"
          >
            Cancel
          </button>
        </div>
      )}

      {/* Tag filters + search-in-graph */}
      {graphData && tagCounts.length > 0 && (
        <GraphFilters
          tagCounts={tagCounts}
          activeTags={activeTags}
          onToggleTag={handleToggleTag}
          onSelectAll={handleSelectAll}
          onSelectNone={handleSelectNone}
          searchQuery={graphSearchQuery}
          onSearchChange={setGraphSearchQuery}
          visibleNodeCount={filteredNodeIds.size}
          totalNodeCount={nodeCount}
          visibleEdgeCount={visibleEdgeCount}
          totalEdgeCount={edgeCount}
          searchMatchCount={searchMatchIds.size}
        />
      )}

      <div className="flex gap-4 graph-responsive" ref={containerRef}>
        {/* Graph Canvas */}
        <div className="flex-1 bg-gray-800 rounded-lg border border-gray-700 overflow-hidden relative">
          <svg ref={svgRef} width="100%" height="600" className="w-full min-h-[350px] sm:min-h-[500px]" />

          {/* Minimap overview for large graphs */}
          <Minimap
            nodes={nodesRef.current}
            zoomTransform={zoomTransform}
            svgWidth={svgDimensions.w}
            svgHeight={svgDimensions.h}
          />

          {/* Zoom controls overlay */}
          <div className="absolute bottom-4 right-4 flex flex-col gap-1.5">
            <div className="text-center text-xs text-gray-400 bg-gray-900/80 rounded px-2 py-0.5 backdrop-blur-sm select-none">
              {zoomPercent}%
            </div>
            <button onClick={zoomIn} className="w-8 h-8 bg-gray-700/90 hover:bg-gray-600 rounded flex items-center justify-center text-gray-300 text-lg transition backdrop-blur-sm" title="Zoom in (+)">+</button>
            <button onClick={zoomOut} className="w-8 h-8 bg-gray-700/90 hover:bg-gray-600 rounded flex items-center justify-center text-gray-300 text-lg transition backdrop-blur-sm" title="Zoom out (-)">−</button>
            <button onClick={fitToView} className="w-8 h-8 bg-gray-700/90 hover:bg-gray-600 rounded flex items-center justify-center text-gray-300 text-sm transition backdrop-blur-sm" title="Fit to view (F)">⛶</button>
            <button onClick={resetZoom} className="w-8 h-8 bg-gray-700/90 hover:bg-gray-600 rounded flex items-center justify-center text-gray-300 text-sm transition backdrop-blur-sm" title="Reset zoom (0)">↺</button>
          </div>

          {/* Interaction hints — desktop only */}
          <div className="absolute top-3 left-3 text-[10px] text-gray-500 leading-relaxed pointer-events-none opacity-70 select-none hidden sm:block">
            <span>Scroll: zoom · Drag: pan · Drag node: move</span><br />
            <span>Double-click: zoom in · Shift+dbl: zoom out</span><br />
            <span>Keys: +/−/0/F · Labels auto-hide on zoom out</span>
          </div>
          {/* Touch hints — mobile only */}
          <div className="absolute top-3 left-3 text-[10px] text-gray-500 leading-relaxed pointer-events-none opacity-70 select-none sm:hidden">
            <span>Pinch: zoom · Drag: pan · Tap: select</span>
          </div>
        </div>

        {/* Side Panel */}
        {selectedNode && (
          <NodeDetailPanel
            node={{
              id: selectedNode.id,
              label: selectedNode.label,
              content: selectedNode.content,
              tags: selectedNode.tags,
              created_at: selectedNode.created_at,
              degree: selectedNode.degree,
            }}
            onClose={() => setSelectedNode(null)}
            onNavigateToNode={navigateToNode}
            nodeLabelMap={nodeLabelMap}
          />
        )}
      </div>

      {/* Legend */}
      <div className="mt-4 flex flex-wrap gap-3 sm:gap-4 text-xs text-gray-400">
        {tagCounts.length > 0 ? (
          tagCounts
            .sort((a, b) => b.count - a.count)
            .slice(0, 12) // limit legend items for readability
            .map(({ tag }) => (
              <span key={tag} className="flex items-center gap-1.5">
                <span className="w-3 h-3 rounded-full inline-block flex-shrink-0" style={{ backgroundColor: getNodeColor([tag]) }} />
                <span className="truncate max-w-[80px] sm:max-w-none">{tag}</span>
              </span>
            ))
        ) : (
          Object.entries(TAG_COLOR_BASE).map(([tag, color]) => (
            <span key={tag} className="flex items-center gap-1.5">
              <span className="w-3 h-3 rounded-full inline-block flex-shrink-0" style={{ backgroundColor: color }} />
              {tag}
            </span>
          ))
        )}
        <span className="flex items-center gap-1.5 ml-4 text-gray-500">
          <span className="w-3 h-3 rounded-full inline-block border border-gray-500" />
          = few connections
        </span>
        <span className="flex items-center gap-1.5 text-gray-500">
          <span className="w-5 h-5 rounded-full inline-block border border-gray-500" />
          = hub node
        </span>
      </div>

      {error && (
        <p className="mt-2 text-xs text-yellow-500">⚠️ Using demo data — {error}</p>
      )}

      {/* Link Mode Dialog */}
      {linkDialogOpen && linkSourceNode && linkTargetNode && (
        <LinkModeDialog
          sourceLabel={linkSourceNode.label}
          targetLabel={linkTargetNode.label}
          submitting={linkSubmitting}
          onConfirm={confirmLink}
          onCancel={cancelLinkDialog}
        />
      )}
    </div>
  )
}
