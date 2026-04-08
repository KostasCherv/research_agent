export type HealthResponse = {
  status: string
  version: string
}

export type ResearchRequest = {
  query: string
  use_vector_store: boolean
}

export type NodeStatus = 'idle' | 'running' | 'completed' | 'failed'

export type NodeMetrics = {
  duration_ms?: number
  result_count?: number
  summary_count?: number
  retrieved_count?: number
}

export type GraphNodeState = {
  status: NodeStatus
  metrics?: NodeMetrics
  ts?: string
}

export type GraphState = Record<string, GraphNodeState>

export type ResearchStreamEvent = {
  node: string
  node_status?: string
  ts?: string
  metrics?: NodeMetrics
  data: {
    error?: string
    report?: string
    combined_insights?: string
    [key: string]: unknown
  }
}
