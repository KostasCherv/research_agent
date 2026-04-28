import { useCallback, useEffect, useRef, useState } from 'react'
import type { Session } from '@supabase/supabase-js'
import {
  createSession,
  getSession,
  streamSessionResearch,
} from '@/api/client'
import { FollowupChat } from '@/components/research/FollowupChat'
import { InlineProgress } from '@/components/research/InlineProgress'
import { QueryComposer } from '@/components/research/QueryComposer'
import { ReportViewer } from '@/components/research/ReportViewer'
import { ScrollArea } from '@/components/ui/scroll-area'
import type { ConversationTurn, ResearchStreamEvent } from '@/types'

type Props = {
  authSession: Session | null
  activeSessionId: string | null
  onSessionActivated: (id: string | null) => void
  onSessionsChanged: () => void
}

export function ResearchPage({ authSession, activeSessionId, onSessionActivated, onSessionsChanged }: Props) {
  const [isStreaming, setIsStreaming] = useState(false)
  const [events, setEvents] = useState<ResearchStreamEvent[]>([])
  const [report, setReport] = useState('')
  const [lastQuery, setLastQuery] = useState('')
  const [error, setError] = useState<string | null>(null)
  const [sessionId, setSessionId] = useState<string | null>(null)
  const [runId, setRunId] = useState<string | null>(null)
  const [conversation, setConversation] = useState<ConversationTurn[]>([])

  const abortRef = useRef<AbortController | null>(null)
  const loadedSessionRef = useRef<string | null>(null)

  useEffect(() => {
    return () => {
      abortRef.current?.abort()
    }
  }, [])

  const openSession = useCallback(
    async (selectedSessionId: string) => {
      if (!authSession?.access_token) return
      try {
        const detail = await getSession(selectedSessionId, authSession.access_token)
        loadedSessionRef.current = detail.session_id
        setSessionId(detail.session_id)
        setRunId(detail.runs.at(-1)?.run_id ?? null)
        setConversation(detail.conversation)
        setLastQuery(detail.runs.at(-1)?.query ?? '')
        setReport(detail.runs.at(-1)?.report ?? '')
        setEvents([])
        setError(null)
      } catch (sessionError) {
        setError(sessionError instanceof Error ? sessionError.message : 'Failed to load session.')
      }
    },
    [authSession],
  )

  // Respond to session selection from the rail
  useEffect(() => {
    if (!activeSessionId) {
      if (activeSessionId === null && loadedSessionRef.current !== null) {
        loadedSessionRef.current = null
        setSessionId(null)
        setRunId(null)
        setConversation([])
        setReport('')
        setLastQuery('')
        setEvents([])
      }
      return
    }
    if (activeSessionId === loadedSessionRef.current) return
    void openSession(activeSessionId)
  }, [activeSessionId, openSession])

  const handleConversationUpdate = useCallback((turn: ConversationTurn) => {
    setConversation((prev) => [...prev, turn])
  }, [])

  const handleSubmit = useCallback(
    async (query: string, useVectorStore: boolean) => {
      if (!query.trim()) {
        setError('Please enter a research query.')
        return
      }
      if (!authSession?.access_token) {
        setError('Please sign in with Google to create and use sessions.')
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
      setConversation([])
      setRunId(null)
      setIsStreaming(true)

      let currentSessionId: string
      try {
        const { session_id } = await createSession(authSession.access_token, normalizedQuery)
        currentSessionId = session_id
        loadedSessionRef.current = session_id
        setSessionId(session_id)
        onSessionActivated(session_id)
        onSessionsChanged()
      } catch (sessionError) {
        setError(sessionError instanceof Error ? sessionError.message : 'Failed to create session.')
        setIsStreaming(false)
        return
      }

      const streamOptions = {
        signal: controller.signal,
        onEvent: (event: ResearchStreamEvent) => {
          setEvents((prev) => [...prev, event])
          if (event.data.report && typeof event.data.report === 'string') setReport(event.data.report)
          if (event.node === '__error__') {
            setError(typeof event.data.error === 'string' ? event.data.error : 'Research failed unexpectedly.')
          }
        },
        onDone: () => setIsStreaming(false),
      }

      try {
        const { runId: newRunId } = await streamSessionResearch(
          currentSessionId,
          { query: normalizedQuery, use_vector_store: useVectorStore },
          authSession.access_token,
          streamOptions,
        )
        if (newRunId) setRunId(newRunId)
      } catch (streamError) {
        if (controller.signal.aborted) return
        const message =
          streamError instanceof Error ? streamError.message : 'Unable to stream research updates.'
        setError(message)
        setIsStreaming(false)
      } finally {
        if (abortRef.current === controller) {
          abortRef.current = null
        }
      }
    },
    [authSession, onSessionActivated, onSessionsChanged],
  )

  const hasContent = !!(report || events.length > 0 || isStreaming || error)

  return (
    <div className="flex h-dvh flex-col max-md:h-full">
      {!hasContent ? (
        // Empty state: centered composer
        <div className="flex flex-1 flex-col items-center justify-center px-6 py-8">
          <div className="w-full max-w-2xl space-y-2">
            <p className="text-sm font-medium text-foreground mb-3">Research</p>
            {!authSession && (
              <p className="text-sm text-muted-foreground mb-4">
                Sign in to save and revisit your research sessions.
              </p>
            )}
            <QueryComposer
              onSubmit={handleSubmit}
              disabled={isStreaming || !authSession}
              isStreaming={isStreaming}
            />
          </div>
        </div>
      ) : (
        // Active state: scrollable content + pinned composer
        <ScrollArea className="flex-1 min-h-0">
          <div className="mx-auto max-w-2xl space-y-6 px-6 py-8 max-md:px-4">
            <InlineProgress events={events} isStreaming={isStreaming} />
            <ReportViewer report={report} query={lastQuery} isStreaming={isStreaming} error={error} />
            {report && sessionId && (
              <FollowupChat
                key={sessionId}
                sessionId={sessionId}
                runId={runId}
                accessToken={authSession?.access_token ?? null}
                conversation={conversation}
                onConversationUpdate={handleConversationUpdate}
              />
            )}
          </div>
        </ScrollArea>
      )}

      {hasContent && (
        <div className="shrink-0 border-t bg-background px-6 py-4 max-md:px-4">
          <div className="max-w-2xl mx-auto">
            <QueryComposer
              onSubmit={handleSubmit}
              disabled={isStreaming || !authSession}
              isStreaming={isStreaming}
            />
          </div>
        </div>
      )}
    </div>
  )
}
