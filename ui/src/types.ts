export type HealthResponse = {
  status: string
  version: string
}

export type ResearchRequest = {
  query: string
  use_vector_store: boolean
}

export type ResearchStreamEvent = {
  node: string
  data: {
    error?: string
    report?: string
    combined_insights?: string
    [key: string]: unknown
  }
}

// ---------------------------------------------------------------------------
// Sessions
// ---------------------------------------------------------------------------

export type SessionRun = {
  run_id: string
  query: string
  source_urls: string[]
  report: string
  created_at: string
}

export type Citation = {
  source_url: string
  source_title: string
}

export type ConversationTurn = {
  role: 'user' | 'assistant'
  content: string
  run_id: string | null
  citations: Citation[]
  created_at: string
}

export type SessionDetail = {
  session_id: string
  title: string
  runs: SessionRun[]
  conversation: ConversationTurn[]
  created_at: string
}

export type SessionSummary = {
  session_id: string
  title: string
  created_at: string
}

export type FollowupStreamEvent =
  | { type: 'chunk'; text: string }
  | { type: 'citations'; citations: Citation[] }
  | { type: 'done' }
  | { type: 'error'; error: string }
