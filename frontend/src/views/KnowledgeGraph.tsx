/**
 * KnowledgeGraph - Interactive D3.js force-directed graph visualization
 *
 * Renders knowledge nodes and their relationships as an interactive graph.
 * Features:
 * - Force-directed layout with D3.js
 * - Nodes sized by connection count (degree)
 * - Nodes colored by primary tag
 * - Arrow markers on directed edges
 * - Zoom, pan, and node drag interactions
 * - Click-to-inspect side panel
 * - Hover highlighting with connected-node emphasis
 * - Fit-to-view and reset zoom controls
 */

import React, { useRef, useEffect, useState, useCallback } from 'react'
import * as d3 from 'd3'
import { api, GraphData, GraphNode, GraphEdge } from '../api/client'

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
  /** Store current zoom transform so reset/fit-to-view can use it. */
  const zoomRef = useRef<d3.ZoomBehavior<SVGSVGElement, unknown> | null>(null)

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

    svg.transition().duration(500).call(
      zoomRef.current.transform,
      d3.zoomIdentity.translate(tx, ty).scale(scale),
    )
  }, [])

  /** Reset zoom to identity (1:1 centered). */
  const resetZoom = useCallback(() => {
    if (!svgRef.current || !zoomRef.current) return
    const svg = d3.select(svgRef.current)
    svg.transition().duration(400).call(
      zoomRef.current.transform,
      d3.zoomIdentity,
    )
  }, [])

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

    // Zoom container
    const g = svg.append('g').attr('class', 'graph-container')

    const zoom = d3.zoom<SVGSVGElement, unknown>()
      .scaleExtent([0.1, 4])
      .on('zoom', (event) => {
        g.attr('transform', event.transform)
      })
    svg.call(zoom)
    zoomRef.current = zoom

    // Arrow marker definition — refX will be set per-link dynamically
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

    // Add a glow filter for hover effect
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
    const dragBehavior = d3.drag<SVGGElement, SimNode>()
      .on('start', (event: d3.D3DragEvent<SVGGElement, SimNode, SimNode>, d) => {
        if (!event.active) simulation.alphaTarget(0.3).restart()
        d.fx = d.x
        d.fy = d.y
      })
      .on('drag', (event: d3.D3DragEvent<SVGGElement, SimNode, SimNode>, d) => {
        d.fx = event.x
        d.fy = event.y
      })
      .on('end', (event: d3.D3DragEvent<SVGGElement, SimNode, SimNode>, d) => {
        if (!event.active) simulation.alphaTarget(0)
        d.fx = null
        d.fy = null
      })

    // --- Render nodes ---
    const node = g.append('g').attr('class', 'nodes')
      .selectAll<SVGGElement, SimNode>('g')
      .data(nodes)
      .join('g')
      .style('cursor', 'pointer')
      .call(dragBehavior)

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
      .text(d => String(d.degree))
      .attr('text-anchor', 'middle')
      .attr('dy', '0.35em')
      .attr('font-size', '10px')
      .attr('font-weight', 'bold')
      .attr('fill', '#fff')
      .attr('pointer-events', 'none')

    // Node labels below the circle
    node.append('text')
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

    // Click to select
    node.on('click', (_event, d) => {
      setSelectedNode(prev => prev?.id === d.id ? null : d)
    })

    // Hover: enlarge hovered node, fade unconnected nodes
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

      node.select('text')
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

      node.selectAll('text')
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

  return (
    <div className="relative">
      <div className="flex items-center justify-between mb-4">
        <h1 className="text-2xl font-bold">🕸️ Knowledge Graph</h1>
        <div className="flex items-center gap-3 text-sm text-gray-400">
          <span>{nodeCount} nodes</span>
          <span>·</span>
          <span>{edgeCount} edges</span>
          <button
            onClick={fitToView}
            className="ml-3 px-2.5 py-1 bg-gray-700 hover:bg-gray-600 rounded text-xs text-gray-300 transition"
            title="Fit graph to view"
          >
            ⛶ Fit
          </button>
          <button
            onClick={resetZoom}
            className="px-2.5 py-1 bg-gray-700 hover:bg-gray-600 rounded text-xs text-gray-300 transition"
            title="Reset zoom to 1:1"
          >
            ↺ Reset
          </button>
        </div>
      </div>

      <div className="flex gap-4" ref={containerRef}>
        {/* Graph Canvas */}
        <div className="flex-1 bg-gray-800 rounded-lg border border-gray-700 overflow-hidden">
          <svg
            ref={svgRef}
            width="100%"
            height="600"
            className="w-full"
          />
        </div>

        {/* Side Panel — selected node details */}
        {selectedNode && (
          <div className="w-80 bg-gray-800 rounded-lg border border-gray-700 p-4 animate-in slide-in-from-right">
            <div className="flex items-center justify-between mb-2">
              <h3 className="text-lg font-semibold text-blue-400">
                {selectedNode.label}
              </h3>
              <button
                onClick={() => setSelectedNode(null)}
                className="text-gray-500 hover:text-gray-300 text-lg leading-none"
                title="Close panel"
              >
                ×
              </button>
            </div>
            <p className="text-gray-300 text-sm mb-3 whitespace-pre-wrap">{selectedNode.content}</p>
            <div className="flex flex-wrap gap-1 mb-3">
              {selectedNode.tags.map(tag => (
                <span
                  key={tag}
                  className="px-2 py-0.5 text-xs rounded-full"
                  style={{ backgroundColor: getNodeColor([tag]) + '33', color: getNodeColor([tag]) }}
                >
                  {tag}
                </span>
              ))}
            </div>
            <div className="text-gray-500 text-xs space-y-0.5">
              <p>ID: {selectedNode.id.slice(0, 8)}</p>
              <p>Connections: {selectedNode.degree}</p>
              <p>Created: {new Date(selectedNode.created_at).toLocaleDateString()}</p>
            </div>
          </div>
        )}
      </div>

      {/* Legend — tag color mapping */}
      <div className="mt-4 flex flex-wrap gap-4 text-xs text-gray-400">
        {Object.entries(TAG_COLORS).filter(([k]) => k !== 'default').map(([tag, color]) => (
          <span key={tag} className="flex items-center gap-1">
            <span className="w-3 h-3 rounded-full inline-block" style={{ backgroundColor: color }} />
            {tag}
          </span>
        ))}
        <span className="flex items-center gap-1 ml-4 text-gray-500">
          <span className="w-3 h-3 rounded-full inline-block border border-gray-500" />
          = small node (few connections)
        </span>
        <span className="flex items-center gap-1 text-gray-500">
          <span className="w-5 h-5 rounded-full inline-block border border-gray-500" />
          = large node (hub)
        </span>
      </div>

      {error && (
        <p className="mt-2 text-xs text-yellow-500">⚠️ Using demo data — {error}</p>
      )}
    </div>
  )
}
