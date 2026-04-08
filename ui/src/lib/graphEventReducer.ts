import type { GraphState, GraphNodeState, NodeStatus, ResearchStreamEvent } from '../types'

// DAG topology matching src/graph/graph.py
export const DAG_MAIN_PATH = [
  'search',
  'retrieve',
  'memory_context',
  'summarize',
  'combine',
  'report',
  'vector_store',
] as const

export const DAG_ALL_NODES = [...DAG_MAIN_PATH, 'abort', 'empty'] as const

export function initialGraphState(): GraphState {
  return Object.fromEntries(
    DAG_ALL_NODES.map((n) => [n, { status: 'idle' as NodeStatus }])
  )
}

export function graphEventReducer(state: GraphState, event: ResearchStreamEvent): GraphState {
  const { node, node_status, ts, metrics } = event

  // Ignore lifecycle sentinels — they carry no node-level state
  if (node === '__end__' || node === '__error__') {
    return state
  }

  const status: NodeStatus =
    node_status === 'failed' || event.data?.error ? 'failed' : 'completed'

  const updatedNode: GraphNodeState = { status, ts, metrics }
  const next: GraphState = { ...state, [node]: updatedNode }

  // Promote the next node in the main path to "running"
  const idx = DAG_MAIN_PATH.indexOf(node as (typeof DAG_MAIN_PATH)[number])
  if (idx >= 0 && idx < DAG_MAIN_PATH.length - 1 && status !== 'failed') {
    const nextNodeName = DAG_MAIN_PATH[idx + 1]
    const current = next[nextNodeName]
    if (current?.status === 'idle') {
      next[nextNodeName] = { ...current, status: 'running' }
    }
  }

  return next
}

export function applyEvents(state: GraphState, events: ResearchStreamEvent[]): GraphState {
  return events.reduce(graphEventReducer, state)
}
