import { useState } from 'react'
import type { GraphState, GraphNodeState, NodeStatus } from '../types'
import { DAG_MAIN_PATH } from '../lib/graphEventReducer'

// ---------------------------------------------------------------------------
// Layout constants
// ---------------------------------------------------------------------------

const NODE_W = 108
const NODE_H = 44
const NODE_RX = 8
const COL_GAP = 32
const ROW_Y = 60
const BRANCH_Y = 150
const PADDING_X = 16

const MAIN_X: Record<string, number> = {}
DAG_MAIN_PATH.forEach((node, i) => {
  MAIN_X[node] = PADDING_X + i * (NODE_W + COL_GAP)
})

const BRANCH_NODES: Record<string, { x: number; y: number }> = {
  abort: { x: MAIN_X['search'], y: BRANCH_Y },
  empty: { x: MAIN_X['retrieve'], y: BRANCH_Y },
}

const SVG_W = PADDING_X * 2 + DAG_MAIN_PATH.length * NODE_W + (DAG_MAIN_PATH.length - 1) * COL_GAP
const SVG_H = BRANCH_Y + NODE_H + PADDING_X

// ---------------------------------------------------------------------------
// Node labels & status colors
// ---------------------------------------------------------------------------

const NODE_LABELS: Record<string, string> = {
  search: 'Search',
  retrieve: 'Retrieve',
  memory_context: 'Memory',
  summarize: 'Summarize',
  combine: 'Combine',
  report: 'Report',
  vector_store: 'Store',
  abort: 'Abort',
  empty: 'No Results',
}

const STATUS_FILL: Record<NodeStatus, string> = {
  idle: '#475569',      // slate-600
  running: '#2563eb',   // blue-600
  completed: '#16a34a', // green-600
  failed: '#dc2626',    // red-600
}

const STATUS_STROKE: Record<NodeStatus, string> = {
  idle: '#64748b',
  running: '#3b82f6',
  completed: '#22c55e',
  failed: '#ef4444',
}

// ---------------------------------------------------------------------------
// Edge helpers
// ---------------------------------------------------------------------------

function cx(node: string): number {
  return (MAIN_X[node] ?? BRANCH_NODES[node]?.x ?? 0) + NODE_W / 2
}

function cy(node: string): number {
  return (BRANCH_NODES[node] ? BRANCH_Y : ROW_Y) + NODE_H / 2
}

function edgePath(fromNode: string, toNode: string): string {
  const x1 = cx(fromNode)
  const y1 = cy(fromNode)
  const x2 = cx(toNode) - NODE_W / 2
  const y2 = cy(toNode)
  const mx = (x1 + x2) / 2
  return `M ${x1} ${y1} C ${mx} ${y1}, ${mx} ${y2}, ${x2} ${y2}`
}

type EdgeProps = {
  from: string
  to: string
  active: boolean
  failed: boolean
}

function Edge({ from, to, active, failed }: EdgeProps) {
  const stroke = failed ? '#ef4444' : active ? '#3b82f6' : '#475569'
  const opacity = active || failed ? 1 : 0.4
  return (
    <path
      d={edgePath(from, to)}
      fill="none"
      stroke={stroke}
      strokeWidth={active ? 2.5 : 1.5}
      strokeOpacity={opacity}
      strokeDasharray={active ? '6 3' : undefined}
      className={active ? 'graph-edge--animated' : undefined}
    />
  )
}

// ---------------------------------------------------------------------------
// Single graph node
// ---------------------------------------------------------------------------

type GraphNodeProps = {
  id: string
  x: number
  y: number
  state: GraphNodeState
  selected: boolean
  onClick: (id: string) => void
}

function GraphNode({ id, x, y, state, selected, onClick }: GraphNodeProps) {
  const { status } = state
  const fill = STATUS_FILL[status]
  const stroke = selected ? '#f8fafc' : STATUS_STROKE[status]
  const label = NODE_LABELS[id] ?? id

  return (
    <g
      className={`graph-node graph-node--${status}`}
      onClick={() => onClick(id)}
      style={{ cursor: 'pointer' }}
      role="button"
      aria-label={`${label} — ${status}`}
    >
      <rect
        x={x}
        y={y}
        width={NODE_W}
        height={NODE_H}
        rx={NODE_RX}
        fill={fill}
        fillOpacity={status === 'idle' ? 0.4 : 0.85}
        stroke={stroke}
        strokeWidth={selected ? 2.5 : 1.5}
      />
      <text
        x={x + NODE_W / 2}
        y={y + NODE_H / 2 + 1}
        textAnchor="middle"
        dominantBaseline="middle"
        fontSize={11}
        fontWeight={status === 'running' ? 700 : 500}
        fill="#f1f5f9"
        style={{ userSelect: 'none', pointerEvents: 'none' }}
      >
        {label}
      </text>
      {status === 'running' && (
        <circle cx={x + NODE_W - 10} cy={y + 10} r={4} fill="#93c5fd" className="graph-node__pulse" />
      )}
    </g>
  )
}

// ---------------------------------------------------------------------------
// Details panel
// ---------------------------------------------------------------------------

type DetailsPanelProps = {
  nodeId: string
  state: GraphNodeState
  onClose: () => void
}

function DetailsPanel({ nodeId, state, onClose }: DetailsPanelProps) {
  const label = NODE_LABELS[nodeId] ?? nodeId
  const { status, metrics, ts } = state

  return (
    <div className="graph-details-panel">
      <div className="graph-details-header">
        <span className="graph-details-title">{label}</span>
        <button type="button" onClick={onClose} className="graph-details-close" aria-label="Close">
          ×
        </button>
      </div>
      <dl className="graph-details-body">
        <dt>Status</dt>
        <dd>
          <span className={`graph-status-chip graph-status-chip--${status}`}>{status}</span>
        </dd>
        {ts && (
          <>
            <dt>Completed at</dt>
            <dd>{new Date(ts).toLocaleTimeString()}</dd>
          </>
        )}
        {metrics?.duration_ms != null && (
          <>
            <dt>Duration</dt>
            <dd>{metrics.duration_ms} ms</dd>
          </>
        )}
        {metrics?.result_count != null && (
          <>
            <dt>Search results</dt>
            <dd>{metrics.result_count}</dd>
          </>
        )}
        {metrics?.retrieved_count != null && (
          <>
            <dt>Pages fetched</dt>
            <dd>{metrics.retrieved_count}</dd>
          </>
        )}
        {metrics?.summary_count != null && (
          <>
            <dt>Summaries</dt>
            <dd>{metrics.summary_count}</dd>
          </>
        )}
      </dl>
    </div>
  )
}

// ---------------------------------------------------------------------------
// Main component
// ---------------------------------------------------------------------------

type ResearchGraphProps = {
  graphState: GraphState
}

export function ResearchGraph({ graphState }: ResearchGraphProps) {
  const [selectedNode, setSelectedNode] = useState<string | null>(null)

  const handleNodeClick = (id: string) => {
    setSelectedNode((prev) => (prev === id ? null : id))
  }

  // Determine which edges are "active" (connecting a completed node to a running one)
  function isEdgeActive(from: string, to: string): boolean {
    return (
      graphState[from]?.status === 'completed' && graphState[to]?.status === 'running'
    )
  }

  function isEdgeFailed(from: string, to: string): boolean {
    return graphState[from]?.status === 'failed' || graphState[to]?.status === 'failed'
  }

  return (
    <div className="research-graph-container">
      <svg
        viewBox={`0 0 ${SVG_W} ${SVG_H}`}
        width="100%"
        height={SVG_H}
        aria-label="Research pipeline graph"
        style={{ overflow: 'visible' }}
      >
        {/* Main path edges */}
        {DAG_MAIN_PATH.slice(0, -1).map((node, i) => {
          const next = DAG_MAIN_PATH[i + 1]
          return (
            <Edge
              key={`${node}-${next}`}
              from={node}
              to={next}
              active={isEdgeActive(node, next)}
              failed={isEdgeFailed(node, next)}
            />
          )
        })}

        {/* Branch edges */}
        <Edge from="search" to="abort" active={false} failed={graphState['abort']?.status === 'completed'} />
        <Edge from="retrieve" to="empty" active={false} failed={graphState['empty']?.status === 'completed'} />

        {/* Main path nodes */}
        {DAG_MAIN_PATH.map((node) => (
          <GraphNode
            key={node}
            id={node}
            x={MAIN_X[node]}
            y={ROW_Y}
            state={graphState[node] ?? { status: 'idle' }}
            selected={selectedNode === node}
            onClick={handleNodeClick}
          />
        ))}

        {/* Branch nodes */}
        {Object.entries(BRANCH_NODES).map(([id, pos]) => (
          <GraphNode
            key={id}
            id={id}
            x={pos.x}
            y={pos.y}
            state={graphState[id] ?? { status: 'idle' }}
            selected={selectedNode === id}
            onClick={handleNodeClick}
          />
        ))}
      </svg>

      {selectedNode && graphState[selectedNode] && (
        <DetailsPanel
          nodeId={selectedNode}
          state={graphState[selectedNode]}
          onClose={() => setSelectedNode(null)}
        />
      )}
    </div>
  )
}
