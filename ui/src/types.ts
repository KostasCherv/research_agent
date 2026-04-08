export type HealthResponse = {
  status: string
  version: string
}

export type ResearchRequest = {
  query: string
  use_vector_store: boolean
}

export type Claim = {
  id: string
  text: string
  confidence: number
  evidence_source_urls: string[]
  evidence_quote: string
}

export type SourceAssessment = {
  url: string
  reliability_score: number
  bias_flags: string[]
  freshness_days: number | null
}

export type StructuredReportV2 = {
  title: string
  executive_summary: string
  claims: Claim[]
  conclusion: string
  source_assessments: SourceAssessment[]
}

export type ResearchStreamEvent = {
  node: string
  data: {
    error?: string
    report?: string
    combined_insights?: string
    structured_report?: StructuredReportV2
    claims_count?: number
    low_confidence_claims_count?: number
    [key: string]: unknown
  }
}
