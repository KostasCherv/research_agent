import { useCallback, useEffect, useRef, useState } from 'react'
import type { Session } from '@supabase/supabase-js'
import {
  createSession,
  deleteSession,
  getSession,
  listSessions,
  streamSessionResearch,
  updateSessionTitle,
} from '@/api/client'
import { FollowupChat } from '@/components/research/FollowupChat'
import { QueryForm } from '@/components/research/QueryForm'
import { ReportViewer } from '@/components/research/ReportViewer'
import { ResearchProgress } from '@/components/research/ResearchProgress'
import { SessionSidebar } from '@/components/research/SessionSidebar'
import type { ConversationTurn, ResearchStreamEvent, SessionSummary } from '@/types'

export function ResearchPage({ authSession }: { authSession: Session | null }) {
  const [isStreaming, setIsStreaming] = useState(false)
  const [events, setEvents] = useState<ResearchStreamEvent[]>([])
  const [report, setReport] = useState('')
  const [lastQuery, setLastQuery] = useState('')
  const [error, setError] = useState<string | null>(null)

  const [sessionId, setSessionId] = useState<string | null>(null)
  const [runId, setRunId] = useState<string | null>(null)
  const [conversation, setConversation] = useState<ConversationTurn[]>([])
  const [userSessions, setUserSessions] = useState<SessionSummary[]>([])

  const abortRef = useRef<AbortController | null>(null)
  const sessionsFetchInFlightRef = useRef(false)
  const sessionsFetchedTokenRef = useRef<string | null>(null)

  useEffect(() => {
    return () => {
      abortRef.current?.abort()
    }
  }, [])

  const loadUserSessions = useCallback(async (accessToken: string, force = false) => {
    if (sessionsFetchInFlightRef.current) return
    if (!force && sessionsFetchedTokenRef.current === accessToken) return

    sessionsFetchInFlightRef.current = true
    try {
      const { sessions } = await listSessions(accessToken)
      setUserSessions(sessions)
      sessionsFetchedTokenRef.current = accessToken
    } catch (sessionsError) {
      setUserSessions([])
      const message = sessionsError instanceof Error ? sessionsError.message : 'Failed to load sessions.'
      setError(message)
    } finally {
      sessionsFetchInFlightRef.current = false
    }
  }, [])

  useEffect(() => {
    if (!authSession?.access_token) return
    void loadUserSessions(authSession.access_token)
  }, [authSession?.access_token, loadUserSessions])

  const handleConversationUpdate = useCallback((turn: ConversationTurn) => {
    setConversation((prev) => [...prev, turn])
  }, [])

  const openSession = useCallback(
    async (selectedSessionId: string) => {
      if (!authSession?.access_token) return
      try {
        const detail = await getSession(selectedSessionId, authSession.access_token)
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

  const handleRenameSession = useCallback(
    async (targetSessionId: string, nextTitle: string) => {
      if (!authSession?.access_token) return
      try {
        await updateSessionTitle(targetSessionId, nextTitle, authSession.access_token)
        setUserSessions((prev) =>
          prev.map((s) => (s.session_id === targetSessionId ? { ...s, title: nextTitle } : s)),
        )
        setError(null)
      } catch (err) {
        setError(err instanceof Error ? err.message : 'Failed to rename session.')
        throw err
      }
    },
    [authSession?.access_token],
  )

  const handleDeleteSession = useCallback(
    async (targetSessionId: string) => {
      if (!authSession?.access_token) return
      const confirmed = window.confirm('Delete this session? This action cannot be undone.')
      if (!confirmed) return

      try {
        await deleteSession(targetSessionId, authSession.access_token)
        setUserSessions((prev) => prev.filter((session) => session.session_id !== targetSessionId))

        if (sessionId === targetSessionId) {
          setSessionId(null)
          setRunId(null)
          setConversation([])
          setReport('')
          setLastQuery('')
          setEvents([])
        }
        setError(null)
      } catch (err) {
        setError(err instanceof Error ? err.message : 'Failed to delete session.')
      }
    },
    [authSession?.access_token, sessionId],
  )

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
        setSessionId(session_id)
        await loadUserSessions(authSession.access_token, true)
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
    [authSession, loadUserSessions],
  )

  return (
    <div className="flex h-[calc(100vh-3.5rem)]">
      {authSession && (
        <SessionSidebar
          sessions={userSessions}
          activeSessionId={sessionId}
          onSelect={(id) => void openSession(id)}
          onRename={handleRenameSession}
          onDelete={handleDeleteSession}
          onNew={() => {
            setSessionId(null)
            setReport('')
            setEvents([])
            setConversation([])
          }}
        />
      )}
      <main className="flex-1 overflow-y-auto">
        <div className="max-w-3xl mx-auto px-4 py-6 space-y-4">
          {!authSession && (
            <p className="text-sm text-muted-foreground text-center py-4">
              Sign in to save and revisit your research sessions.
            </p>
          )}
          <QueryForm
            onSubmit={handleSubmit}
            disabled={isStreaming || !authSession}
            isStreaming={isStreaming}
          />
          <ResearchProgress events={events} isStreaming={isStreaming} />
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
      </main>
    </div>
  )
}
