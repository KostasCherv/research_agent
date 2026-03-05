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
