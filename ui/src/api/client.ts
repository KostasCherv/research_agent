import type {
  Citation,
  FollowupStreamEvent,
  HealthResponse,
  ResearchRequest,
  ResearchStreamEvent,
  SessionDetail,
  SessionSummary,
} from '../types'

const API_BASE = import.meta.env.VITE_API_BASE_URL ?? 'http://localhost:8000'

type StreamOptions = {
  signal?: AbortSignal
  onEvent: (event: ResearchStreamEvent) => void
  onDone?: () => void
}

function authHeaders(accessToken: string | null): HeadersInit {
  if (!accessToken) {
    return {}
  }
  return { Authorization: `Bearer ${accessToken}` }
}

export async function checkHealth(): Promise<HealthResponse> {
  const response = await fetch(`${API_BASE}/health`)
  if (!response.ok) {
    throw new Error(`Health check failed: ${response.status}`)
  }
  return (await response.json()) as HealthResponse
}

function parseEventBlock(block: string): ResearchStreamEvent | null {
  const dataLines = block
    .split('\n')
    .map((line) => line.trim())
    .filter((line) => line.startsWith('data:'))
    .map((line) => line.replace(/^data:\s?/, ''))

  if (dataLines.length === 0) {
    return null
  }

  const rawData = dataLines.join('\n')
  const parsed = JSON.parse(rawData) as ResearchStreamEvent
  if (!parsed?.node || typeof parsed.data !== 'object') {
    return null
  }
  return parsed
}

// ---------------------------------------------------------------------------
// Session API
// ---------------------------------------------------------------------------

export async function createSession(
  accessToken: string | null,
  query?: string,
): Promise<{ session_id: string; title: string; created_at: string }> {
  const response = await fetch(`${API_BASE}/sessions`, {
    method: 'POST',
    headers: {
      'Content-Type': 'application/json',
      ...authHeaders(accessToken),
    },
    body: JSON.stringify({ query: query ?? null }),
  })
  if (!response.ok) {
    throw new Error(`Failed to create session: ${response.status}`)
  }
  return (await response.json()) as { session_id: string; title: string; created_at: string }
}

export async function getSession(sessionId: string, accessToken: string | null): Promise<SessionDetail> {
  const response = await fetch(`${API_BASE}/sessions/${sessionId}`, {
    headers: authHeaders(accessToken),
  })
  if (!response.ok) {
    throw new Error(`Session not found: ${response.status}`)
  }
  return (await response.json()) as SessionDetail
}

export async function listSessions(
  accessToken: string | null,
): Promise<{ sessions: SessionSummary[] }> {
  const response = await fetch(`${API_BASE}/sessions`, {
    headers: authHeaders(accessToken),
  })
  // Backward compatibility while backend is restarting/updating.
  // 401 is treated as empty so optional sidebar loading never hard-fails the UI.
  if (response.status === 401 || response.status === 404 || response.status === 405) {
    return { sessions: [] }
  }
  if (!response.ok) {
    throw new Error(`Failed to list sessions: ${response.status}`)
  }
  return (await response.json()) as { sessions: SessionSummary[] }
}

export async function updateSessionTitle(
  sessionId: string,
  title: string,
  accessToken: string | null,
): Promise<{ session_id: string; title: string }> {
  const response = await fetch(`${API_BASE}/sessions/${sessionId}`, {
    method: 'PATCH',
    headers: {
      'Content-Type': 'application/json',
      ...authHeaders(accessToken),
    },
    body: JSON.stringify({ title }),
  })
  if (!response.ok) {
    throw new Error(`Failed to rename session: ${response.status}`)
  }
  return (await response.json()) as { session_id: string; title: string }
}

export async function deleteSession(
  sessionId: string,
  accessToken: string | null,
): Promise<{ session_id: string; deleted: boolean }> {
  const response = await fetch(`${API_BASE}/sessions/${sessionId}`, {
    method: 'DELETE',
    headers: authHeaders(accessToken),
  })
  if (!response.ok) {
    throw new Error(`Failed to delete session: ${response.status}`)
  }
  return (await response.json()) as { session_id: string; deleted: boolean }
}

type FollowupOptions = {
  signal?: AbortSignal
  onChunk: (text: string) => void
  onCitations: (citations: Citation[]) => void
  onDone: () => void
  onError?: (error: string) => void
}

export async function streamFollowup(
  sessionId: string,
  question: string,
  runId: string | null,
  accessToken: string | null,
  options: FollowupOptions,
): Promise<void> {
  const response = await fetch(`${API_BASE}/sessions/${sessionId}/followup`, {
    method: 'POST',
    headers: {
      'Content-Type': 'application/json',
      Accept: 'text/event-stream',
      ...authHeaders(accessToken),
    },
    body: JSON.stringify({ question, run_id: runId }),
    signal: options.signal,
  })

  if (!response.ok) {
    throw new Error(`Followup request failed: ${response.status}`)
  }
  if (!response.body) {
    throw new Error('Streaming not supported.')
  }

  const reader = response.body.getReader()
  const decoder = new TextDecoder('utf-8')
  let buffer = ''

  const handleFollowupEvent = (parsed: FollowupStreamEvent): boolean => {
    if (parsed.type === 'chunk') {
      options.onChunk(parsed.text)
      return false
    }
    if (parsed.type === 'citations') {
      options.onCitations(parsed.citations)
      return false
    }
    if (parsed.type === 'done') {
      options.onDone()
      return true
    }
    if (parsed.type === 'error') {
      options.onError?.(parsed.error)
      return true
    }
    return false
  }

  while (true) {
    const { value, done } = await reader.read()
    if (done) break
    buffer += decoder.decode(value, { stream: true })
    const chunks = buffer.split('\n\n')
    buffer = chunks.pop() ?? ''

    for (const chunk of chunks) {
      const dataLine = chunk.split('\n').find((l) => l.startsWith('data:'))
      if (!dataLine) continue
      let parsed: FollowupStreamEvent
      try {
        parsed = JSON.parse(dataLine.replace(/^data:\s?/, '')) as FollowupStreamEvent
      } catch {
        continue
      }
      if (handleFollowupEvent(parsed)) {
        return
      }
    }
  }

  if (buffer.trim()) {
    const dataLine = buffer
      .split('\n')
      .map((line) => line.trim())
      .find((line) => line.startsWith('data:'))
    if (dataLine) {
      try {
        const parsed = JSON.parse(dataLine.replace(/^data:\s?/, '')) as FollowupStreamEvent
        if (handleFollowupEvent(parsed)) {
          return
        }
      } catch {
        // Ignore trailing partial event and report abnormal termination below.
      }
    }
  }

  options.onError?.('Follow-up stream ended before a terminal event was received.')
}

export async function streamSessionResearch(
  sessionId: string,
  payload: ResearchRequest,
  accessToken: string | null,
  options: StreamOptions,
): Promise<{ runId: string | null }> {
  const response = await fetch(`${API_BASE}/sessions/${sessionId}/research`, {
    method: 'POST',
    headers: {
      'Content-Type': 'application/json',
      Accept: 'text/event-stream',
      ...authHeaders(accessToken),
    },
    body: JSON.stringify(payload),
    signal: options.signal,
  })

  if (!response.ok) {
    throw new Error(`Session research failed: ${response.status}`)
  }
  if (!response.body) {
    throw new Error('Streaming not supported.')
  }

  const runId = response.headers.get('X-Run-Id')

  const reader = response.body.getReader()
  const decoder = new TextDecoder('utf-8')
  let buffer = ''

  while (true) {
    const { value, done } = await reader.read()
    if (done) break
    buffer += decoder.decode(value, { stream: true })
    const chunks = buffer.split('\n\n')
    buffer = chunks.pop() ?? ''

    for (const chunk of chunks) {
      const event = parseEventBlock(chunk)
      if (!event) continue
      options.onEvent(event)
      if (event.node === '__end__') {
        options.onDone?.()
        return { runId }
      }
    }
  }

  if (buffer.trim()) {
    const event = parseEventBlock(buffer)
    if (event) options.onEvent(event)
  }
  options.onDone?.()
  return { runId }
}

export async function streamResearch(
  payload: ResearchRequest,
  options: StreamOptions,
): Promise<void> {
  const response = await fetch(`${API_BASE}/research`, {
    method: 'POST',
    headers: {
      'Content-Type': 'application/json',
      Accept: 'text/event-stream',
    },
    body: JSON.stringify(payload),
    signal: options.signal,
  })

  if (!response.ok) {
    throw new Error(`Research request failed: ${response.status}`)
  }
  if (!response.body) {
    throw new Error('Streaming not supported by this browser response.')
  }

  const reader = response.body.getReader()
  const decoder = new TextDecoder('utf-8')
  let buffer = ''

  while (true) {
    const { value, done } = await reader.read()
    if (done) {
      break
    }

    buffer += decoder.decode(value, { stream: true })
    const chunks = buffer.split('\n\n')
    buffer = chunks.pop() ?? ''

    for (const chunk of chunks) {
      const event = parseEventBlock(chunk)
      if (!event) {
        continue
      }
      options.onEvent(event)
      if (event.node === '__end__') {
        options.onDone?.()
        return
      }
    }
  }

  if (buffer.trim()) {
    const event = parseEventBlock(buffer)
    if (event) {
      options.onEvent(event)
    }
  }
  options.onDone?.()
}
