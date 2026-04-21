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
  suggestions?: string[]
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
  | { type: 'suggestions'; suggestions: string[] }
  | { type: 'done' }
  | { type: 'error'; error: string }

export type RagResourceState = 'uploaded' | 'processing' | 'ready' | 'failed'

export type RagResource = {
  resource_id: string
  owner_id: string
  workspace_id: string
  filename: string
  mime_type: string
  byte_size: number
  storage_uri: string
  state: RagResourceState
  error_details?: string | null
  created_at: string
  updated_at: string
}

export type RagAgent = {
  agent_id: string
  owner_id: string
  workspace_id: string
  name: string
  description: string
  system_instructions: string
  linked_resource_ids: string[]
  created_at: string
  updated_at: string
}

export type RagChatMessage = {
  message_id: string
  session_id: string
  agent_id: string
  owner_id: string
  role: 'user' | 'assistant'
  content: string
  citations: Citation[]
  created_at: string
}
