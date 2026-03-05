import type { HealthResponse, ResearchRequest, ResearchStreamEvent } from '../types'

const API_BASE = import.meta.env.VITE_API_BASE_URL ?? 'http://localhost:8000'

type StreamOptions = {
  signal?: AbortSignal
  onEvent: (event: ResearchStreamEvent) => void
  onDone?: () => void
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
