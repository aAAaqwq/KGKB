/**
 * KnowledgeGraph - Interactive D3.js force-directed graph visualization
 *
 * Renders knowledge nodes and their relationships as an interactive graph.
 * Features:
 * - Force-directed layout with D3.js
 * - Nodes sized by connection count (degree)
 * - Nodes colored by primary tag
 * - Arrow markers on directed edges
 * - Zoom: scroll to zoom, double-click to zoom in, shift+double-click to zoom out
 * - Pan: click-drag on background
 * - Node drag: click-drag on node repositions it within the simulation
 * - Smooth animated transitions on zoom actions
 * - Fit-to-view and reset zoom controls with keyboard shortcuts (+/-/0)
 * - Zoom level indicator
 * - Click-to-inspect side panel
 * - Hover highlighting with connected-node emphasis
 */

import React, { useRef, useEffect, useState, useCallback, useMemo } from 'react'
import * as d3 from 'd3'
import { api, GraphData, GraphNode, GraphEdge, getErrorMessage } from '../api/client'
import { NodeDetailPanel, NodeInfo } from '../components/NodeDetailPanel'
import { GraphFilters, TagCount } from '../components/GraphFilters'
import { LinkDialog } from '../components/LinkDialog'
import { LinkModeDialog } from '../components/LinkModeDialog'

/** Simulation node with degree (connection count) for sizing. */
interface SimNode extends d3.SimulationNodeDatum {
  id: string
  label: string
  content: string
  tags: string[]
  created_at: string
  /** Number of connections (in + out edges). */
  degree: number
  /** Computed radius based on degree. */
  radius: number
}

interface SimLink extends d3.SimulationLinkDatum<SimNode> {
  id: string
  type: string
  weight: number
}

/** Color palette for the most common tags. Falls back to gray. */
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
  default: '#6b7280',
}

/** Zoom constraints */
const ZOOM_MIN = 0.1
const ZOOM_MAX = 6
const ZOOM_STEP = 1.5 // multiplier per zoom-in/out action
const TRANSITION_MS = 400 // default animation duration

/** Return the color for a node based on its first matching tag. */
function getNodeColor(tags: string[]): string {
  for (const tag of tags) {
    const lower = tag.toLowerCase()
    for (const [key, color] of Object.entries(TAG_COLORS)) {
      if (key === 'default') continue
      if (lower === key.toLowerCase()) return color
    }
  }
  return TAG_COLORS.default
}

/**
 * Compute node radius from degree.
 * Minimum 12px (isolated node), scales up with sqrt for visual balance.
 * Max capped at 36px to avoid dominating the layout.
 */
function computeRadius(degree: number): number {
  const MIN_R = 12
  const MAX_R = 36
  const r = MIN_R + Math.sqrt(degree) * 6
  return Math.min(r, MAX_R)
}

export function KnowledgeGraph() {
  const svgRef = useRef<SVGSVGElement>(null)
  const containerRef = useRef<HTMLDivElement>(null)
  const [graphData, setGraphData] = useState<GraphData | null>(null)
  const [selectedNode, setSelectedNode] = useState<SimNode | null>(null)
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState<string | null>(null)
  /** Current zoom level for the indicator. */
  const [zoomLevel, setZoomLevel] = useState(1)
  /** Tag filter: empty set = show all, non-empty = only show nodes with these tags. */
  const [activeTags, setActiveTags] = useState<Set<string>>(new Set())
  /** Search-in-graph query for highlighting matching nodes. */
  const [graphSearchQuery, setGraphSearchQuery] = useState('')
  /** Link mode: active, source node selected, dialog showing, submitting. */
  const [linkModeActive, setLinkModeActive] = useState(false)
  const [linkSourceNode, setLinkSourceNode] = useState<SimNode | null>(null)
  const [linkTargetNode, setLinkTargetNode] = useState<SimNode | null>(null)
  const [linkDialogOpen, setLinkDialogOpen] = useState(false)
  const [linkSubmitting, setLinkSubmitting] = useState(false)
  // ============ Link Mode State ============
  /** Whether link mode is active (user is creating a relation). */
  const [linkMode, setLinkMode] = useState(false)
  /** First node selected in link mode (source). */
  const [linkSource, setLinkSource] = useState<SimNode | null>(null)
  /** Second node selected in link mode (target) — triggers dialog. */
  const [linkTarget, setLinkTarget] = useState<SimNode | null>(null)
  /** Whether the link creation API call is in progress. */
  const [linkLoading, setLinkLoading] = useState(false)
  /** Error from link creation API call. */
  const [linkError, setLinkError] = useState<string | null>(null)
  /** Success toast message. */
  const [linkSuccess, setLinkSuccess] = useState<string | null>(null)

  /** Store current zoom behavior so reset/fit-to-view can use it. */
  const zoomRef = useRef<d3.ZoomBehavior<SVGSVGElement, unknown> | null>(null)
  /** Store the simulation ref for external control (e.g., reheat on center-to-node). */
  const simulationRef = useRef<d3.Simulation<SimNode, SimLink> | null>(null)
  /** Store current SimNodes for external access (e.g., navigate-to-node). */
  const nodesRef = useRef<SimNode[]>([])
  /** Refs for link mode state (so D3 event handlers can read current values). */
  const linkModeRef = useRef({ active: false, sourceNode: null as SimNode | null })

  /** Build a map of node ID → label for the detail panel to resolve relations. */
  const nodeLabelMap = useMemo(() => {
    const map = new Map<string, string>()
    if (graphData) {
      for (const n of graphData.nodes) {
        map.set(n.id, n.label)
      }
    }
    return map
  }, [graphData])

  /** Compute unique tags with counts from graph data. */
  const tagCounts: TagCount[] = useMemo(() => {
    if (!graphData) return []
    const counts = new Map<string, number>()
    for (const node of graphData.nodes) {
      for (const tag of node.tags) {
        counts.set(tag, (counts.get(tag) || 0) + 1)
      }
    }
    return Array.from(counts.entries()).map(([tag, count]) => ({ tag, count }))
  }, [graphData])

  /** All unique tags for the "select all" operation. */
  const allTags = useMemo(() => new Set(tagCounts.map(tc => tc.tag)), [tagCounts])

  /** Set of node IDs that pass the tag filter. Empty activeTags = all pass. */
  const filteredNodeIds = useMemo(() => {
    if (!graphData) return new Set<string>()
    if (activeTags.size === 0) {
      return new Set(graphData.nodes.map(n => n.id))
    }
    return new Set(
      graphData.nodes
        .filter(n => n.tags.some(t => activeTags.has(t)))
        .map(n => n.id)
    )
  }, [graphData, activeTags])

  /** Set of node IDs matching the search query. */
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

  /** Visible edge count after tag filter. */
  const visibleEdgeCount = useMemo(() => {
    if (!graphData) return 0
    if (activeTags.size === 0) return graphData.edges.length
    return graphData.edges.filter(e => {
      const src = typeof e.source === 'string' ? e.source : (e.source as any).id
      const tgt = typeof e.target === 'string' ? e.target : (e.target as any).id
      return filteredNodeIds.has(src) && filteredNodeIds.has(tgt)
    }).length
  }, [graphData, activeTags, filteredNodeIds])

  /** Tag filter callbacks. */
  const handleToggleTag = useCallback((tag: string) => {
    setActiveTags(prev => {
      const next = new Set(prev)
      // If currently showing all (empty set), switch to showing only this tag
      if (prev.size === 0) {
        // Start filtering: show only this tag
        return new Set([tag])
      }
      if (next.has(tag)) {
        next.delete(tag)
        // If removing the last filter, go back to "show all"
        if (next.size === 0) return new Set<string>()
      } else {
        next.add(tag)
        // If all tags selected, clear filter (= show all)
        if (next.size === allTags.size) return new Set<string>()
      }
      return next
    })
  }, [allTags])

  const handleSelectAll = useCallback(() => {
    setActiveTags(new Set<string>())
  }, [])

  const handleSelectNone = useCallback(() => {
    // Set to a special "none" state — use a placeholder impossible tag
    // Actually, set activeTags to contain a dummy so filteredNodeIds is empty
    setActiveTags(new Set(['__none__']))
  }, [])

  /** Toggle link mode on/off. Resets any in-progress link. */
  const toggleLinkMode = useCallback(() => {
    setLinkModeActive(prev => {
      if (prev) {
        // Turning off: reset link state
        setLinkSourceNode(null)
        setLinkTargetNode(null)
        setLinkDialogOpen(false)
      }
      return !prev
    })
  }, [])

  /** Cancel link mode entirely. */
  const cancelLinkMode = useCallback(() => {
    setLinkModeActive(false)
    setLinkSourceNode(null)
    setLinkTargetNode(null)
    setLinkDialogOpen(false)
  }, [])

  /** Cancel the dialog but stay in link mode. */
  const cancelLinkDialog = useCallback(() => {
    setLinkTargetNode(null)
    setLinkDialogOpen(false)
    // Reset source too so user can start fresh
    setLinkSourceNode(null)
  }, [])

  /** Confirm link creation: call API, update graph. */
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

  /** Sync link mode state to ref so D3 event handlers read current values. */
  useEffect(() => {
    linkModeRef.current = { active: linkModeActive, sourceNode: linkSourceNode }
  }, [linkModeActive, linkSourceNode])

  /**
   * Navigate to a specific node in the graph: center + zoom on it, and select it.
   * Used when clicking a connected node in the detail panel.
   */
  const navigateToNode = useCallback((nodeId: string) => {
    const targetNode = nodesRef.current.find(n => n.id === nodeId)
    if (!targetNode || !svgRef.current || !zoomRef.current) return

    const w = svgRef.current.clientWidth || 900
    const h = svgRef.current.clientHeight || 600
    const targetScale = 2

    const tx = w / 2 - targetNode.x! * targetScale
    const ty = h / 2 - targetNode.y! * targetScale

    const svg = d3.select(svgRef.current)
    svg.transition().duration(TRANSITION_MS * 1.5)
      .call(
        zoomRef.current!.transform,
        d3.zoomIdentity.translate(tx, ty).scale(targetScale),
      )

    // Select the target node
    setSelectedNode(targetNode)
  }, [])

  // ============ Link Mode Handlers ============

  /** Toggle link mode on/off. Clears selection state when toggling off. */
  const toggleLinkMode = useCallback(() => {
    setLinkMode(prev => {
      if (prev) {
        // Turning off: clear link state
        setLinkSource(null)
        setLinkTarget(null)
        setLinkError(null)
      }
      return !prev
    })
  }, [])

  /** Cancel link mode entirely (e.g., from dialog cancel or Escape). */
  const cancelLinkMode = useCallback(() => {
    setLinkSource(null)
    setLinkTarget(null)
    setLinkError(null)
  }, [])

  /** Handle link mode node click: first click = source, second click = target. */
  const handleLinkNodeClick = useCallback((node: SimNode) => {
    if (!linkMode) return false // not in link mode, let normal click handle it

    if (!linkSource) {
      // First click: set source
      setLinkSource(node)
      setLinkError(null)
      return true
    }

    if (node.id === linkSource.id) {
      // Clicked same node: deselect source
      setLinkSource(null)
      return true
    }

    // Second click: set target and show dialog
    setLinkTarget(node)
    return true
  }, [linkMode, linkSource])

  /** Confirm relation creation from the dialog. */
  const handleLinkConfirm = useCallback(async (relationType: string) => {
    if (!linkSource || !linkTarget) return

    setLinkLoading(true)
    setLinkError(null)

    try {
      await api.createRelation({
        source_id: linkSource.id,
        target_id: linkTarget.id,
        type: relationType,
        weight: 1.0,
      })

      // Success: refresh graph data to include the new edge
      const freshData = await api.getGraph()
      setGraphData(freshData)

      // Show success toast
      setLinkSuccess(
        `Linked "${linkSource.label}" → "${linkTarget.label}" (${relationType})`
      )
      setTimeout(() => setLinkSuccess(null), 3500)

      // Reset link selection (stay in link mode for creating more links)
      setLinkSource(null)
      setLinkTarget(null)
    } catch (err: unknown) {
      setLinkError(getErrorMessage(err))
    } finally {
      setLinkLoading(false)
    }
  }, [linkSource, linkTarget])

  /** Cancel the link dialog (keep link mode active, clear target). */
  const handleLinkDialogCancel = useCallback(() => {
    setLinkTarget(null)
    setLinkError(null)
  }, [])

  // Fetch graph data from API
  useEffect(() => {
    const fetchGraph = async () => {
      try {
        setLoading(true)
        const data = await api.getGraph()
        setGraphData(data)
      } catch (err: any) {
        setError(err.message || 'Failed to load graph')
        // Provide demo data so the graph still renders
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

  /** Fit the graph into the viewport with a smooth transition. */
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
      1.5, // don't zoom in too much
    )
    const tx = (width - bounds.width * scale) / 2 - bounds.x * scale
    const ty = (height - bounds.height * scale) / 2 - bounds.y * scale

    svg.transition().duration(TRANSITION_MS).call(
      zoomRef.current.transform,
      d3.zoomIdentity.translate(tx, ty).scale(scale),
    )
  }, [])

  /** Reset zoom to identity (1:1 centered). */
  const resetZoom = useCallback(() => {
    if (!svgRef.current || !zoomRef.current) return
    const svg = d3.select(svgRef.current)
    svg.transition().duration(TRANSITION_MS).call(
      zoomRef.current.transform,
      d3.zoomIdentity,
    )
  }, [])

  /** Programmatic zoom in centered on the current viewport. */
  const zoomIn = useCallback(() => {
    if (!svgRef.current || !zoomRef.current) return
    const svg = d3.select(svgRef.current)
    svg.transition().duration(TRANSITION_MS).call(
      zoomRef.current.scaleBy,
      ZOOM_STEP,
    )
  }, [])

  /** Programmatic zoom out centered on the current viewport. */
  const zoomOut = useCallback(() => {
    if (!svgRef.current || !zoomRef.current) return
    const svg = d3.select(svgRef.current)
    svg.transition().duration(TRANSITION_MS).call(
      zoomRef.current.scaleBy,
      1 / ZOOM_STEP,
    )
  }, [])

  // Keyboard shortcuts: +/= zoom in, - zoom out, 0 reset, f fit-to-view
  useEffect(() => {
    const handler = (e: KeyboardEvent) => {
      // Don't capture when user is typing in an input
      if (
        e.target instanceof HTMLInputElement ||
        e.target instanceof HTMLTextAreaElement ||
        e.target instanceof HTMLSelectElement
      ) return

      switch (e.key) {
        case '+':
        case '=':
          e.preventDefault()
          zoomIn()
          break
        case '-':
        case '_':
          e.preventDefault()
          zoomOut()
          break
        case '0':
          e.preventDefault()
          resetZoom()
          break
        case 'f':
        case 'F':
          // Only if no modifiers (so Ctrl+F still works for browser find)
          if (!e.ctrlKey && !e.metaKey) {
            e.preventDefault()
            fitToView()
          }
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

    // --- Compute degree (connection count) per node ---
    const degreeMap = new Map<string, number>()
    for (const edge of graphData.edges) {
      const src = typeof edge.source === 'string' ? edge.source : (edge.source as any).id
      const tgt = typeof edge.target === 'string' ? edge.target : (edge.target as any).id
      degreeMap.set(src, (degreeMap.get(src) || 0) + 1)
      degreeMap.set(tgt, (degreeMap.get(tgt) || 0) + 1)
    }

    // Build simulation nodes with degree and radius
    const nodes: SimNode[] = graphData.nodes.map(n => {
      const degree = degreeMap.get(n.id) || 0
      return {
        ...n,
        degree,
        radius: computeRadius(degree),
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

    // --- Graph container (all graph elements inside, transformed by zoom) ---
    const g = svg.append('g').attr('class', 'graph-container')

    // --- Zoom behavior with smooth transitions ---
    const zoom = d3.zoom<SVGSVGElement, unknown>()
      .scaleExtent([ZOOM_MIN, ZOOM_MAX])
      .filter((event) => {
        // Allow scroll-wheel, touch, and programmatic events always.
        // For mouse buttons: only allow left-button (for pan) if not on a node.
        // D3 default filter handles most of this.
        return !event.ctrlKey && !event.button
      })
      .on('zoom', (event) => {
        g.attr('transform', event.transform)
        setZoomLevel(event.transform.k)
      })

    svg.call(zoom)

    // Double-click on SVG background: zoom in centered on click point.
    // Shift + double-click: zoom out.
    svg.on('dblclick.zoom', null) // remove d3-zoom's default double-click handler
    svg.on('dblclick', (event: MouseEvent) => {
      event.preventDefault()
      event.stopPropagation()

      const [mx, my] = d3.pointer(event, svgRef.current!)
      const factor = event.shiftKey ? (1 / ZOOM_STEP) : ZOOM_STEP

      // Zoom centered on the click position
      svg.transition().duration(TRANSITION_MS).call(
        zoom.scaleBy,
        factor,
        [mx, my],
      )
    })

    zoomRef.current = zoom

    // --- Defs: arrow markers, glow filter ---
    const defs = svg.append('defs')

    defs.append('marker')
      .attr('id', 'arrowhead')
      .attr('viewBox', '0 -5 10 10')
      .attr('refX', 10)
      .attr('refY', 0)
      .attr('markerWidth', 6)
      .attr('markerHeight', 6)
      .attr('orient', 'auto')
      .append('path')
      .attr('d', 'M0,-5L10,0L0,5')
      .attr('fill', '#4b5563')

    // Glow filter for hover effect
    const filter = defs.append('filter')
      .attr('id', 'glow')
      .attr('x', '-50%').attr('y', '-50%')
      .attr('width', '200%').attr('height', '200%')
    filter.append('feGaussianBlur').attr('stdDeviation', '3').attr('result', 'blur')
    filter.append('feMerge')
      .selectAll('feMergeNode')
      .data(['blur', 'SourceGraphic'])
      .join('feMergeNode')
      .attr('in', d => d)

    // --- Force simulation ---
    const simulation = d3.forceSimulation<SimNode>(nodes)
      .force('link', d3.forceLink<SimNode, SimLink>(links)
        .id(d => d.id)
        .distance(d => {
          const src = nodeMap.get(typeof d.source === 'string' ? d.source : (d.source as SimNode).id)
          const tgt = nodeMap.get(typeof d.target === 'string' ? d.target : (d.target as SimNode).id)
          const r1 = src?.radius ?? 16
          const r2 = tgt?.radius ?? 16
          return r1 + r2 + 60
        })
        .strength(d => Math.min(d.weight * 0.5, 1)))
      .force('charge', d3.forceManyBody()
        .strength(d => -200 - (d as SimNode).radius * 8))
      .force('center', d3.forceCenter(width / 2, height / 2).strength(0.05))
      .force('collision', d3.forceCollide<SimNode>()
        .radius(d => d.radius + 8)
        .strength(0.8))
      .force('x', d3.forceX(width / 2).strength(0.03))
      .force('y', d3.forceY(height / 2).strength(0.03))

    simulationRef.current = simulation
    nodesRef.current = nodes

    // --- Render edges ---
    const link = g.append('g').attr('class', 'edges')
      .selectAll('line')
      .data(links)
      .join('line')
      .attr('stroke', '#4b5563')
      .attr('stroke-width', d => Math.max(1, d.weight * 2))
      .attr('stroke-opacity', 0.6)
      .attr('marker-end', 'url(#arrowhead)')

    // Edge labels
    const linkLabel = g.append('g').attr('class', 'edge-labels')
      .selectAll('text')
      .data(links)
      .join('text')
      .text(d => d.type)
      .attr('font-size', '9px')
      .attr('fill', '#6b7280')
      .attr('text-anchor', 'middle')
      .attr('pointer-events', 'none')

    // --- Drag behavior ---
    // Track drag state to distinguish click vs drag
    let isDragging = false

    const dragBehavior = d3.drag<SVGGElement, SimNode>()
      .on('start', (event: d3.D3DragEvent<SVGGElement, SimNode, SimNode>, d) => {
        isDragging = false
        if (!event.active) simulation.alphaTarget(0.3).restart()
        d.fx = d.x
        d.fy = d.y
      })
      .on('drag', (event: d3.D3DragEvent<SVGGElement, SimNode, SimNode>, d) => {
        isDragging = true
        d.fx = event.x
        d.fy = event.y
      })
      .on('end', (event: d3.D3DragEvent<SVGGElement, SimNode, SimNode>, d) => {
        if (!event.active) simulation.alphaTarget(0)
        // Release the node so it floats back into simulation
        d.fx = null
        d.fy = null
      })

    // --- Render nodes ---
    const node = g.append('g').attr('class', 'nodes')
      .selectAll<SVGGElement, SimNode>('g')
      .data(nodes)
      .join('g')
      .style('cursor', 'grab')
      .call(dragBehavior)

    // Change cursor on drag
    node.on('mousedown.cursor', function () {
      d3.select(this).style('cursor', 'grabbing')
    })
    node.on('mouseup.cursor', function () {
      d3.select(this).style('cursor', 'grab')
    })

    // Node circles — radius scales with degree
    node.append('circle')
      .attr('r', d => d.radius)
      .attr('fill', d => getNodeColor(d.tags))
      .attr('stroke', '#1f2937')
      .attr('stroke-width', 2)
      .attr('opacity', 0.9)

    // Degree badge for highly-connected nodes (degree >= 3)
    node.filter(d => d.degree >= 3)
      .append('text')
      .attr('class', 'degree-badge')
      .text(d => String(d.degree))
      .attr('text-anchor', 'middle')
      .attr('dy', '0.35em')
      .attr('font-size', '10px')
      .attr('font-weight', 'bold')
      .attr('fill', '#fff')
      .attr('pointer-events', 'none')

    // Node labels below the circle
    node.append('text')
      .attr('class', 'node-label')
      .text(d => d.label.length > 18 ? d.label.slice(0, 18) + '…' : d.label)
      .attr('text-anchor', 'middle')
      .attr('dy', d => d.radius + 14)
      .attr('font-size', '11px')
      .attr('fill', '#d1d5db')
      .attr('pointer-events', 'none')

    // --- Adjacency set for highlight on hover ---
    const adjacency = new Map<string, Set<string>>()
    for (const l of links) {
      const src = typeof l.source === 'string' ? l.source : (l.source as SimNode).id
      const tgt = typeof l.target === 'string' ? l.target : (l.target as SimNode).id
      if (!adjacency.has(src)) adjacency.set(src, new Set())
      if (!adjacency.has(tgt)) adjacency.set(tgt, new Set())
      adjacency.get(src)!.add(tgt)
      adjacency.get(tgt)!.add(src)
    }

    // --- Click to select (normal mode) or link nodes (link mode) ---
    node.on('click', (_event, d) => {
      if (isDragging) return

      const lm = linkModeRef.current
      if (lm.active) {
        // Link mode click behavior
        if (!lm.sourceNode) {
          // First click: select source node
          setLinkSourceNode(d)
        } else if (lm.sourceNode.id === d.id) {
          // Clicked the same node: deselect
          setLinkSourceNode(null)
        } else {
          // Second click on a different node: open dialog
          setLinkTargetNode(d)
          setLinkDialogOpen(true)
        }
      } else {
        // Normal mode: toggle detail panel
        setSelectedNode(prev => prev?.id === d.id ? null : d)
      }
    })

    // --- Double-click on node: center and zoom to it ---
    node.on('dblclick', (event, d) => {
      event.preventDefault()
      event.stopPropagation()

      const w = svgRef.current!.clientWidth || 900
      const h = svgRef.current!.clientHeight || 600
      const targetScale = 2

      // Center the node in the viewport
      const tx = w / 2 - d.x! * targetScale
      const ty = h / 2 - d.y! * targetScale

      svg.transition().duration(TRANSITION_MS * 1.5)
        .call(
          zoom.transform,
          d3.zoomIdentity.translate(tx, ty).scale(targetScale),
        )

      // Also select the node
      setSelectedNode(d)
    })

    // --- Hover: enlarge hovered node, fade unconnected nodes ---
    node.on('mouseover', function (_event, d) {
      const neighbors = adjacency.get(d.id) || new Set<string>()

      // Enlarge hovered node
      d3.select(this).select('circle')
        .transition().duration(150)
        .attr('r', d.radius + 4)
        .attr('stroke', '#60a5fa')
        .attr('stroke-width', 3)
        .attr('filter', 'url(#glow)')

      // Fade non-neighbors
      node.select('circle')
        .transition().duration(150)
        .attr('opacity', (n: any) => (n.id === d.id || neighbors.has(n.id)) ? 1 : 0.2)

      node.select('.node-label')
        .transition().duration(150)
        .attr('opacity', (n: any) => (n.id === d.id || neighbors.has(n.id)) ? 1 : 0.15)

      node.select('.degree-badge')
        .transition().duration(150)
        .attr('opacity', (n: any) => (n.id === d.id || neighbors.has(n.id)) ? 1 : 0.15)

      link.transition().duration(150)
        .attr('stroke-opacity', (l: any) => {
          const src = typeof l.source === 'string' ? l.source : l.source.id
          const tgt = typeof l.target === 'string' ? l.target : l.target.id
          return (src === d.id || tgt === d.id) ? 0.9 : 0.08
        })

      linkLabel.transition().duration(150)
        .attr('opacity', (l: any) => {
          const src = typeof l.source === 'string' ? l.source : l.source.id
          const tgt = typeof l.target === 'string' ? l.target : l.target.id
          return (src === d.id || tgt === d.id) ? 1 : 0.08
        })
    })

    node.on('mouseout', function (_event, d) {
      // Restore all to normal
      d3.select(this).select('circle')
        .transition().duration(200)
        .attr('r', d.radius)
        .attr('stroke', '#1f2937')
        .attr('stroke-width', 2)
        .attr('filter', null)

      node.select('circle')
        .transition().duration(200)
        .attr('opacity', 0.9)

      node.selectAll('.node-label')
        .transition().duration(200)
        .attr('opacity', 1)

      node.selectAll('.degree-badge')
        .transition().duration(200)
        .attr('opacity', 1)

      link.transition().duration(200)
        .attr('stroke-opacity', 0.6)

      linkLabel.transition().duration(200)
        .attr('opacity', 1)
    })

    // --- Tick: update positions on each frame ---
    simulation.on('tick', () => {
      // Shorten edge lines so arrows end at node boundary
      link
        .attr('x1', d => (d.source as SimNode).x!)
        .attr('y1', d => (d.source as SimNode).y!)
        .attr('x2', d => {
          const src = d.source as SimNode
          const tgt = d.target as SimNode
          const dx = tgt.x! - src.x!
          const dy = tgt.y! - src.y!
          const dist = Math.sqrt(dx * dx + dy * dy) || 1
          return tgt.x! - (dx / dist) * tgt.radius
        })
        .attr('y2', d => {
          const src = d.source as SimNode
          const tgt = d.target as SimNode
          const dx = tgt.x! - src.x!
          const dy = tgt.y! - src.y!
          const dist = Math.sqrt(dx * dx + dy * dy) || 1
          return tgt.y! - (dy / dist) * tgt.radius
        })

      linkLabel
        .attr('x', d => ((d.source as SimNode).x! + (d.target as SimNode).x!) / 2)
        .attr('y', d => ((d.source as SimNode).y! + (d.target as SimNode).y!) / 2)

      node.attr('transform', d => `translate(${d.x},${d.y})`)
    })

    // Auto fit-to-view once simulation stabilizes
    simulation.on('end', () => {
      fitToView()
    })

    return () => { simulation.stop() }
  }, [graphData, fitToView])

  // ============ Filter + Search highlight (applied without re-rendering D3) ============
  useEffect(() => {
    if (!svgRef.current || !graphData) return
    const svg = d3.select(svgRef.current)
    const isFiltering = activeTags.size > 0
    const isSearching = graphSearchQuery.trim().length > 0

    // Apply tag filter: fade non-matching nodes and edges
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
        if (!isFiltering) return 1
        const src = typeof d.source === 'string' ? d.source : (d.source as SimNode).id
        const tgt = typeof d.target === 'string' ? d.target : (d.target as SimNode).id
        return (filteredNodeIds.has(src) && filteredNodeIds.has(tgt)) ? 1 : 0.04
      })

    // Apply search highlight: add glow ring around matching nodes
    svg.selectAll<SVGGElement, SimNode>('g.nodes > g')
      .select('circle')
      .transition().duration(200)
      .attr('stroke', d => {
        if (isSearching && searchMatchIds.has(d.id)) return '#fbbf24' // yellow highlight
        return '#1f2937'
      })
      .attr('stroke-width', d => {
        if (isSearching && searchMatchIds.has(d.id)) return 3.5
        return 2
      })

    // Also brighten the label of search matches
    svg.selectAll<SVGGElement, SimNode>('g.nodes > g')
      .select('.node-label')
      .transition().duration(200)
      .attr('fill', d => {
        if (isSearching && searchMatchIds.has(d.id)) return '#fbbf24'
        return '#d1d5db'
      })
      .attr('font-weight', d => {
        if (isSearching && searchMatchIds.has(d.id)) return 'bold'
        return 'normal'
      })
  }, [activeTags, graphSearchQuery, filteredNodeIds, searchMatchIds, graphData])

  // ============ Link Mode visual feedback ============
  useEffect(() => {
    if (!svgRef.current || !graphData) return
    const svg = d3.select(svgRef.current)

    if (linkModeActive) {
      // Change cursor on all nodes to crosshair
      svg.selectAll<SVGGElement, SimNode>('g.nodes > g')
        .style('cursor', 'crosshair')

      // Highlight source node with a pulsing ring
      svg.selectAll<SVGGElement, SimNode>('g.nodes > g')
        .select('circle')
        .transition().duration(200)
        .attr('stroke', d => {
          if (linkSourceNode && d.id === linkSourceNode.id) return '#3b82f6' // blue for source
          return '#1f2937'
        })
        .attr('stroke-width', d => {
          if (linkSourceNode && d.id === linkSourceNode.id) return 4
          return 2
        })
        .attr('stroke-dasharray', d => {
          if (linkSourceNode && d.id === linkSourceNode.id) return '6 3'
          return 'none'
        })

      // Dim non-source nodes slightly when source is selected
      if (linkSourceNode) {
        svg.selectAll<SVGGElement, SimNode>('g.nodes > g')
          .select('circle')
          .transition().duration(200)
          .attr('opacity', d => d.id === linkSourceNode.id ? 1 : 0.7)
      }
    } else {
      // Reset all link mode visuals
      svg.selectAll<SVGGElement, SimNode>('g.nodes > g')
        .style('cursor', 'grab')

      svg.selectAll<SVGGElement, SimNode>('g.nodes > g')
        .select('circle')
        .transition().duration(200)
        .attr('stroke', '#1f2937')
        .attr('stroke-width', 2)
        .attr('stroke-dasharray', 'none')
        .attr('opacity', 0.9)
    }
  }, [linkModeActive, linkSourceNode, graphData])

  // ============ Render ============

  if (loading) {
    return (
      <div className="flex items-center justify-center h-[600px]">
        <div className="animate-pulse text-gray-400 text-lg">Loading graph...</div>
      </div>
    )
  }

  const nodeCount = graphData?.nodes.length ?? 0
  const edgeCount = graphData?.edges.length ?? 0
  const zoomPercent = Math.round(zoomLevel * 100)

  return (
    <div className="relative">
      <div className="flex items-center justify-between mb-4">
        <h1 className="text-2xl font-bold">🕸️ Knowledge Graph</h1>
        {/* Link Mode toggle */}
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

      {/* Link Mode instructions banner */}
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

      <div className="flex gap-4" ref={containerRef}>
        {/* Graph Canvas */}
        <div className="flex-1 bg-gray-800 rounded-lg border border-gray-700 overflow-hidden relative">
          <svg
            ref={svgRef}
            width="100%"
            height="600"
            className="w-full"
          />

          {/* Zoom controls overlay (bottom-right) */}
          <div className="absolute bottom-4 right-4 flex flex-col gap-1.5">
            {/* Zoom percentage indicator */}
            <div className="text-center text-xs text-gray-400 bg-gray-900/80 rounded px-2 py-0.5 backdrop-blur-sm select-none">
              {zoomPercent}%
            </div>

            {/* Zoom in */}
            <button
              onClick={zoomIn}
              className="w-8 h-8 bg-gray-700/90 hover:bg-gray-600 rounded flex items-center justify-center text-gray-300 text-lg transition backdrop-blur-sm"
              title="Zoom in (+)"
            >
              +
            </button>

            {/* Zoom out */}
            <button
              onClick={zoomOut}
              className="w-8 h-8 bg-gray-700/90 hover:bg-gray-600 rounded flex items-center justify-center text-gray-300 text-lg transition backdrop-blur-sm"
              title="Zoom out (-)"
            >
              −
            </button>

            {/* Fit to view */}
            <button
              onClick={fitToView}
              className="w-8 h-8 bg-gray-700/90 hover:bg-gray-600 rounded flex items-center justify-center text-gray-300 text-sm transition backdrop-blur-sm"
              title="Fit to view (F)"
            >
              ⛶
            </button>

            {/* Reset zoom */}
            <button
              onClick={resetZoom}
              className="w-8 h-8 bg-gray-700/90 hover:bg-gray-600 rounded flex items-center justify-center text-gray-300 text-sm transition backdrop-blur-sm"
              title="Reset zoom (0)"
            >
              ↺
            </button>
          </div>

          {/* Interaction hints (top-left, fades after 5s) */}
          <div className="absolute top-3 left-3 text-[10px] text-gray-500 leading-relaxed pointer-events-none opacity-70 select-none">
            <span>Scroll: zoom · Drag: pan · Drag node: move</span><br />
            <span>Double-click: zoom in · Shift+dbl: zoom out</span><br />
            <span>Double-click node: focus · Keys: +/−/0/F</span>
          </div>
        </div>

        {/* Side Panel — full node details with relations */}
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

      {/* Legend — dynamic tag colors from actual graph data + size hint */}
      <div className="mt-4 flex flex-wrap gap-4 text-xs text-gray-400">
        {tagCounts.length > 0 ? (
          tagCounts
            .sort((a, b) => b.count - a.count)
            .map(({ tag }) => (
              <span key={tag} className="flex items-center gap-1">
                <span
                  className="w-3 h-3 rounded-full inline-block"
                  style={{ backgroundColor: getNodeColor([tag]) }}
                />
                {tag}
              </span>
            ))
        ) : (
          // Fallback: show default palette when no data
          Object.entries(TAG_COLORS).filter(([k]) => k !== 'default').map(([tag, color]) => (
            <span key={tag} className="flex items-center gap-1">
              <span className="w-3 h-3 rounded-full inline-block" style={{ backgroundColor: color }} />
              {tag}
            </span>
          ))
        )}
        <span className="flex items-center gap-1 ml-4 text-gray-500">
          <span className="w-3 h-3 rounded-full inline-block border border-gray-500" />
          = few connections
        </span>
        <span className="flex items-center gap-1 text-gray-500">
          <span className="w-5 h-5 rounded-full inline-block border border-gray-500" />
          = hub node
        </span>
      </div>

      {error && (
        <p className="mt-2 text-xs text-yellow-500">⚠️ Using demo data — {error}</p>
      )}

      {/* Link Mode confirmation dialog */}
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
