import { useCallback, useEffect, useMemo, useRef, useState } from 'react'
import { AlertCircle, CheckCircle2, LoaderCircle } from 'lucide-react'
import { checkHealth, streamResearch } from './api/client'
import { ChatForm } from './components/ChatForm'
import { Layout } from './components/Layout'
import { ReportViewer } from './components/ReportViewer'
import { ResearchGraph } from './components/ResearchGraph'
import { ResearchProgress } from './components/ResearchProgress'
import { initialGraphState, applyEvents } from './lib/graphEventReducer'
import type { GraphState, HealthResponse, ResearchStreamEvent } from './types'

const BATCH_INTERVAL_MS = 100

type HealthState = 'loading' | 'online' | 'offline'

function App() {
  const [health, setHealth] = useState<HealthState>('loading')
  const [isStreaming, setIsStreaming] = useState(false)
  const [events, setEvents] = useState<ResearchStreamEvent[]>([])
  const [report, setReport] = useState('')
  const [lastQuery, setLastQuery] = useState('')
  const [error, setError] = useState<string | null>(null)
  const [graphState, setGraphState] = useState<GraphState>(initialGraphState())

  // Batch pending graph events to avoid per-node re-renders
  const pendingGraphEvents = useRef<ResearchStreamEvent[]>([])
  const batchTimer = useRef<ReturnType<typeof setTimeout> | null>(null)

  const abortRef = useRef<AbortController | null>(null)

  const scheduleGraphUpdate = useCallback((event: ResearchStreamEvent) => {
    pendingGraphEvents.current.push(event)
    if (batchTimer.current === null) {
      batchTimer.current = setTimeout(() => {
        const batch = pendingGraphEvents.current
        pendingGraphEvents.current = []
        batchTimer.current = null
        setGraphState((prev) => applyEvents(prev, batch))
      }, BATCH_INTERVAL_MS)
    }
  }, [])

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
      if (batchTimer.current !== null) {
        clearTimeout(batchTimer.current)
      }
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

      // Reset all state for new run
      setError(null)
      setReport('')
      setLastQuery(normalizedQuery)
      setEvents([])
      setGraphState(initialGraphState())
      pendingGraphEvents.current = []
      if (batchTimer.current !== null) {
        clearTimeout(batchTimer.current)
        batchTimer.current = null
      }
      setIsStreaming(true)

      try {
        await streamResearch(
          { query: normalizedQuery, use_vector_store: useVectorStore },
          {
            signal: controller.signal,
            onEvent: (event) => {
              setEvents((prev) => [...prev, event])
              scheduleGraphUpdate(event)
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
    [scheduleGraphUpdate],
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

      {/* Graph: visible on medium+ screens */}
      <div className="graph-panel-desktop">
        <section className="glass-panel card-spacing">
          <h2>Pipeline</h2>
          <ResearchGraph graphState={graphState} />
        </section>
      </div>

      {/* Progress list: mobile fallback */}
      <div className="progress-panel-mobile">
        <ResearchProgress events={events} isStreaming={isStreaming} />
      </div>

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
