import { useCallback, useEffect, useMemo, useRef, useState } from 'react'
import { AlertCircle, CheckCircle2, LoaderCircle } from 'lucide-react'
import type { AuthChangeEvent, Session } from '@supabase/supabase-js'
import {
  checkHealth,
  createSession,
  getSession,
  listSessions,
  streamSessionResearch,
} from './api/client'
import { ChatForm } from './components/ChatForm'
import { FollowupChat } from './components/FollowupChat'
import { Layout } from './components/Layout'
import { ReportViewer } from './components/ReportViewer'
import { ResearchProgress } from './components/ResearchProgress'
import { supabase } from './lib/supabase'
import type {
  ConversationTurn,
  HealthResponse,
  ResearchStreamEvent,
  SessionSummary,
} from './types'

type HealthState = 'loading' | 'online' | 'offline'

function App() {
  const [health, setHealth] = useState<HealthState>('loading')
  const [isStreaming, setIsStreaming] = useState(false)
  const [events, setEvents] = useState<ResearchStreamEvent[]>([])
  const [report, setReport] = useState('')
  const [lastQuery, setLastQuery] = useState('')
  const [error, setError] = useState<string | null>(null)
  const [authSession, setAuthSession] = useState<Session | null>(null)

  // Session state
  const [sessionId, setSessionId] = useState<string | null>(null)
  const [runId, setRunId] = useState<string | null>(null)
  const [conversation, setConversation] = useState<ConversationTurn[]>([])
  const [userSessions, setUserSessions] = useState<SessionSummary[]>([])

  const abortRef = useRef<AbortController | null>(null)
  const sessionsFetchInFlightRef = useRef(false)
  const sessionsFetchedTokenRef = useRef<string | null>(null)

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
    void supabase.auth.getSession().then(({ data }: { data: { session: Session | null } }) => {
      setAuthSession(data.session)
    })
    const { data } = supabase.auth.onAuthStateChange(
      (_event: AuthChangeEvent, session: Session | null) => {
        setAuthSession(session)
        if (!session) {
          setSessionId(null)
          setRunId(null)
          setConversation([])
          setUserSessions([])
          setReport('')
          setLastQuery('')
          sessionsFetchedTokenRef.current = null
          return
        }
      },
    )
    return () => {
      data.subscription.unsubscribe()
    }
  }, [loadUserSessions])

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

      // Always create a fresh session for each new research run.
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
          if (event.data.report) setReport(event.data.report)
          if (event.node === '__error__') {
            setError(event.data.error ?? 'Research failed unexpectedly.')
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
    [sessionId, authSession, loadUserSessions],
  )

  const signInWithGoogle = useCallback(async () => {
    const redirectTo = `${window.location.origin}/`
    const { error: signInError } = await supabase.auth.signInWithOAuth({
      provider: 'google',
      options: { redirectTo },
    })
    if (signInError) {
      setError(signInError.message)
    }
  }, [])

  const signOut = useCallback(async () => {
    const { error: signOutError } = await supabase.auth.signOut()
    if (signOutError) {
      setError(signOutError.message)
      return
    }
    setSessionId(null)
    setRunId(null)
    setConversation([])
    setUserSessions([])
    setReport('')
    setLastQuery('')
  }, [])

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
      actions={
        authSession ? (
          <button type="button" className="auth-button" onClick={() => void signOut()}>
            Sign out
          </button>
        ) : (
          <button type="button" className="auth-button" onClick={() => void signInWithGoogle()}>
            Sign in with Google
          </button>
        )
      }
      sidebar={
        authSession ? (
          <div className="sessions-menu">
            <h2>Past sessions</h2>
            {userSessions.length === 0 ? (
              <p className="sessions-empty">No sessions yet.</p>
            ) : (
              <ul className="sessions-list">
                {userSessions.map((s) => (
                  <li key={s.session_id}>
                    <button
                      type="button"
                      className={`session-item ${sessionId === s.session_id ? 'is-active' : ''}`}
                      onClick={() => void openSession(s.session_id)}
                    >
                      <span className="session-item-id">{s.title}</span>
                      <span className="session-item-date">
                        {new Date(s.created_at).toLocaleString()}
                      </span>
                    </button>
                  </li>
                ))}
              </ul>
            )}
          </div>
        ) : null
      }
    >
      <ChatForm onSubmit={handleSubmit} disabled={isStreaming || !authSession} />
      <ResearchProgress events={events} isStreaming={isStreaming} />
      <ReportViewer
        report={report}
        query={lastQuery}
        isStreaming={isStreaming}
        error={error}
      />
      {report && sessionId && (
        <FollowupChat
          sessionId={sessionId}
          runId={runId}
          accessToken={authSession?.access_token ?? null}
          conversation={conversation}
          onConversationUpdate={handleConversationUpdate}
        />
      )}
    </Layout>
  )
}

export default App
