/**
 * KnowledgeGraph - Interactive D3.js force-directed graph visualization
 *
 * Renders knowledge nodes and their relationships as an interactive graph.
 * Supports zoom, drag, click-to-inspect, and force simulation.
 */

import React, { useRef, useEffect, useState, useCallback } from 'react'
import * as d3 from 'd3'
import { api, GraphData, GraphNode, GraphEdge } from '../api/client'

interface SimNode extends d3.SimulationNodeDatum {
  id: string
  label: string
  content: string
  tags: string[]
  created_at: string
}

interface SimLink extends d3.SimulationLinkDatum<SimNode> {
  id: string
  type: string
  weight: number
}

const TAG_COLORS: Record<string, string> = {
  AI: '#3b82f6',
  tech: '#10b981',
  finance: '#f59e0b',
  research: '#8b5cf6',
  project: '#ef4444',
  idea: '#ec4899',
  default: '#6b7280',
}

function getNodeColor(tags: string[]): string {
  for (const tag of tags) {
    if (TAG_COLORS[tag]) return TAG_COLORS[tag]
  }
  return TAG_COLORS.default
}

export function KnowledgeGraph() {
  const svgRef = useRef<SVGSVGElement>(null)
  const [graphData, setGraphData] = useState<GraphData | null>(null)
  const [selectedNode, setSelectedNode] = useState<SimNode | null>(null)
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState<string | null>(null)

  // Fetch graph data
  useEffect(() => {
    const fetchGraph = async () => {
      try {
        setLoading(true)
        const data = await api.getGraph()
        setGraphData(data)
      } catch (err: any) {
        setError(err.message || 'Failed to load graph')
        // Use demo data on failure
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

  // Render D3 graph
  useEffect(() => {
    if (!graphData || !svgRef.current) return

    const svg = d3.select(svgRef.current)
    svg.selectAll('*').remove()

    const width = svgRef.current.clientWidth || 900
    const height = svgRef.current.clientHeight || 600

    // Build simulation data
    const nodes: SimNode[] = graphData.nodes.map(n => ({
      ...n,
      x: Math.random() * width,
      y: Math.random() * height,
    }))

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
    const g = svg.append('g')

    const zoom = d3.zoom<SVGSVGElement, unknown>()
      .scaleExtent([0.1, 4])
      .on('zoom', (event) => {
        g.attr('transform', event.transform)
      })
    svg.call(zoom)

    // Arrow marker for directed edges
    svg.append('defs').append('marker')
      .attr('id', 'arrowhead')
      .attr('viewBox', '0 -5 10 10')
      .attr('refX', 20)
      .attr('refY', 0)
      .attr('markerWidth', 6)
      .attr('markerHeight', 6)
      .attr('orient', 'auto')
      .append('path')
      .attr('d', 'M0,-5L10,0L0,5')
      .attr('fill', '#4b5563')

    // Force simulation
    const simulation = d3.forceSimulation<SimNode>(nodes)
      .force('link', d3.forceLink<SimNode, SimLink>(links)
        .id(d => d.id)
        .distance(120)
        .strength(d => d.weight * 0.5))
      .force('charge', d3.forceManyBody().strength(-300))
      .force('center', d3.forceCenter(width / 2, height / 2))
      .force('collision', d3.forceCollide(40))

    // Render edges
    const link = g.append('g')
      .selectAll('line')
      .data(links)
      .join('line')
      .attr('stroke', '#4b5563')
      .attr('stroke-width', d => Math.max(1, d.weight * 2))
      .attr('stroke-opacity', 0.6)
      .attr('marker-end', 'url(#arrowhead)')

    // Edge labels
    const linkLabel = g.append('g')
      .selectAll('text')
      .data(links)
      .join('text')
      .text(d => d.type)
      .attr('font-size', '9px')
      .attr('fill', '#6b7280')
      .attr('text-anchor', 'middle')

    // Drag behavior
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

    // Render nodes
    const node = g.append('g')
      .selectAll<SVGGElement, SimNode>('g')
      .data(nodes)
      .join('g')
      .style('cursor', 'pointer')
      .call(dragBehavior)

    // Node circles
    node.append('circle')
      .attr('r', 16)
      .attr('fill', d => getNodeColor(d.tags))
      .attr('stroke', '#1f2937')
      .attr('stroke-width', 2)

    // Node labels
    node.append('text')
      .text(d => d.label.length > 20 ? d.label.slice(0, 20) + '…' : d.label)
      .attr('text-anchor', 'middle')
      .attr('dy', 30)
      .attr('font-size', '11px')
      .attr('fill', '#d1d5db')

    // Click to select
    node.on('click', (_event, d) => {
      setSelectedNode(prev => prev?.id === d.id ? null : d)
    })

    // Hover effects
    node.on('mouseover', function () {
      d3.select(this).select('circle')
        .transition().duration(150)
        .attr('r', 20)
        .attr('stroke', '#60a5fa')
        .attr('stroke-width', 3)
    })
    node.on('mouseout', function () {
      d3.select(this).select('circle')
        .transition().duration(150)
        .attr('r', 16)
        .attr('stroke', '#1f2937')
        .attr('stroke-width', 2)
    })

    // Tick
    simulation.on('tick', () => {
      link
        .attr('x1', d => (d.source as SimNode).x!)
        .attr('y1', d => (d.source as SimNode).y!)
        .attr('x2', d => (d.target as SimNode).x!)
        .attr('y2', d => (d.target as SimNode).y!)

      linkLabel
        .attr('x', d => ((d.source as SimNode).x! + (d.target as SimNode).x!) / 2)
        .attr('y', d => ((d.source as SimNode).y! + (d.target as SimNode).y!) / 2)

      node.attr('transform', d => `translate(${d.x},${d.y})`)
    })

    return () => { simulation.stop() }
  }, [graphData])

  if (loading) {
    return (
      <div className="flex items-center justify-center h-[600px]">
        <div className="text-gray-400 text-lg">Loading graph...</div>
      </div>
    )
  }

  return (
    <div className="relative">
      <h1 className="text-2xl font-bold mb-4">🕸️ Knowledge Graph</h1>

      <div className="flex gap-4">
        {/* Graph Canvas */}
        <div className="flex-1 bg-gray-800 rounded-lg border border-gray-700 overflow-hidden">
          <svg
            ref={svgRef}
            width="100%"
            height="600"
            className="w-full"
          />
        </div>

        {/* Side Panel */}
        {selectedNode && (
          <div className="w-80 bg-gray-800 rounded-lg border border-gray-700 p-4">
            <h3 className="text-lg font-semibold text-blue-400 mb-2">
              {selectedNode.label}
            </h3>
            <p className="text-gray-300 text-sm mb-3">{selectedNode.content}</p>
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
            <p className="text-gray-500 text-xs">
              ID: {selectedNode.id.slice(0, 8)}
            </p>
            <p className="text-gray-500 text-xs">
              Created: {new Date(selectedNode.created_at).toLocaleDateString()}
            </p>
            <button
              onClick={() => setSelectedNode(null)}
              className="mt-4 text-xs text-gray-500 hover:text-gray-300"
            >
              Close
            </button>
          </div>
        )}
      </div>

      {/* Legend */}
      <div className="mt-4 flex gap-4 text-xs text-gray-400">
        {Object.entries(TAG_COLORS).filter(([k]) => k !== 'default').map(([tag, color]) => (
          <span key={tag} className="flex items-center gap-1">
            <span className="w-3 h-3 rounded-full inline-block" style={{ backgroundColor: color }} />
            {tag}
          </span>
        ))}
      </div>

      {error && (
        <p className="mt-2 text-xs text-yellow-500">⚠️ Using demo data — {error}</p>
      )}
    </div>
  )
}
