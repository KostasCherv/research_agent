import { useCallback, useEffect, useMemo, useRef, useState } from 'react'
import { AlertCircle, CheckCircle2, LoaderCircle } from 'lucide-react'
import { checkHealth, streamResearch } from './api/client'
import { ChatForm } from './components/ChatForm'
import { Layout } from './components/Layout'
import { ReportViewer } from './components/ReportViewer'
import { ResearchProgress } from './components/ResearchProgress'
import type { HealthResponse, ResearchStreamEvent } from './types'

type HealthState = 'loading' | 'online' | 'offline'

function App() {
  const [health, setHealth] = useState<HealthState>('loading')
  const [isStreaming, setIsStreaming] = useState(false)
  const [events, setEvents] = useState<ResearchStreamEvent[]>([])
  const [report, setReport] = useState('')
  const [lastQuery, setLastQuery] = useState('')
  const [error, setError] = useState<string | null>(null)
  const abortRef = useRef<AbortController | null>(null)

  const loadHealth = useCallback(async () => {
    try {
      const response: HealthResponse = await checkHealth()
      setHealth(response.status === 'ok' ? 'online' : 'offline')
    } catch {
      setHealth('offline')
    }
  }, [])

  useEffect(() => {
    void loadHealth()
  }, [loadHealth])

  useEffect(() => {
    return () => {
      abortRef.current?.abort()
    }
  }, [])

  const handleSubmit = useCallback(
    async (query: string, useVectorStore: boolean) => {
      if (!query.trim()) {
        setError('Please enter a research query.')
        return
      }
      const normalizedQuery = query.trim()

      abortRef.current?.abort()
      const controller = new AbortController()
      abortRef.current = controller

      setError(null)
      setReport('')
      setLastQuery(normalizedQuery)
      setEvents([])
      setIsStreaming(true)

      try {
        await streamResearch(
          { query: normalizedQuery, use_vector_store: useVectorStore },
          {
            signal: controller.signal,
            onEvent: (event) => {
              setEvents((prev) => [...prev, event])
              if (event.data.report) {
                setReport(event.data.report)
              }
              if (event.node === '__error__') {
                setError(event.data.error ?? 'Research failed unexpectedly.')
              }
            },
            onDone: () => {
              setIsStreaming(false)
            },
          },
        )
      } catch (streamError) {
        if (controller.signal.aborted) {
          return
        }
        const message =
          streamError instanceof Error
            ? streamError.message
            : 'Unable to stream research updates.'
        setError(message)
        setIsStreaming(false)
      } finally {
        if (abortRef.current === controller) {
          abortRef.current = null
        }
      }
    },
    [],
  )

  const healthIndicator = useMemo(() => {
    if (health === 'loading') {
      return {
        label: 'Checking backend...',
        icon: <LoaderCircle size={16} className="spin" />,
      }
    }
    if (health === 'online') {
      return {
        label: 'Backend connected',
        icon: <CheckCircle2 size={16} className="status-online" />,
      }
    }
    return {
      label: 'Backend offline',
      icon: <AlertCircle size={16} className="status-offline" />,
    }
  }, [health])

  return (
    <Layout
      title="Research Agent"
      subtitle="Stream multi-step research progress and view final markdown reports."
      status={healthIndicator}
    >
      <ChatForm onSubmit={handleSubmit} disabled={isStreaming} />
      <ResearchProgress events={events} isStreaming={isStreaming} />
      <ReportViewer
        report={report}
        query={lastQuery}
        isStreaming={isStreaming}
        error={error}
      />
    </Layout>
  )
}

export default App
