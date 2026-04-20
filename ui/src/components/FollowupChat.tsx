import { useCallback, useEffect, useRef, useState } from 'react'
import { streamFollowup } from '../api/client'
import type { Citation, ConversationTurn } from '../types'
import SuggestionChips from './SuggestionChips'

type FollowupChatProps = {
  sessionId: string
  runId: string | null
  accessToken: string | null
  conversation: ConversationTurn[]
  onConversationUpdate: (turn: ConversationTurn) => void
}

function CitationChip({ citation }: { citation: Citation }) {
  return (
    <a
      href={citation.source_url}
      target="_blank"
      rel="noopener noreferrer"
      className="followup-citation-chip"
      title={citation.source_url}
    >
      {citation.source_title || 'source'}
    </a>
  )
}

function UserBubble({ turn }: { turn: ConversationTurn }) {
  return (
    <div className="followup-row followup-row--user">
      <div className="followup-bubble followup-bubble--user">
        <p>{turn.content}</p>
      </div>
    </div>
  )
}

function AssistantBubble({
  turn,
  streaming,
}: {
  turn: ConversationTurn
  streaming?: boolean
}) {
  return (
    <div className="followup-row followup-row--assistant">
      <div className="followup-avatar" aria-hidden="true">
        AI
      </div>
      <div className="followup-bubble followup-bubble--assistant">
        <p>
          {turn.content}
          {streaming && <span className="followup-cursor" />}
        </p>
        {!streaming && turn.citations.length > 0 && (
          <div className="followup-citations">
            {turn.citations.map((c) => (
              <CitationChip key={c.source_url} citation={c} />
            ))}
          </div>
        )}
      </div>
    </div>
  )
}

export function FollowupChat({
  sessionId,
  runId,
  accessToken,
  conversation,
  onConversationUpdate,
}: FollowupChatProps) {
  const [question, setQuestion] = useState('')
  const [streaming, setStreaming] = useState(false)
  const [streamingText, setStreamingText] = useState('')
  const [error, setError] = useState<string | null>(null)
  const [latestSuggestions, setLatestSuggestions] = useState<string[]>([])
  const abortRef = useRef<AbortController | null>(null)
  const bottomRef = useRef<HTMLDivElement | null>(null)
  const textareaRef = useRef<HTMLTextAreaElement | null>(null)

  // Auto-scroll to bottom when new content arrives
  useEffect(() => {
    bottomRef.current?.scrollIntoView({ behavior: 'smooth' })
  }, [conversation, streamingText])

  // Auto-resize textarea
  const handleQuestionChange = useCallback((e: React.ChangeEvent<HTMLTextAreaElement>) => {
    setQuestion(e.target.value)
    const el = e.target
    el.style.height = 'auto'
    el.style.height = `${Math.min(el.scrollHeight, 160)}px`
  }, [])

  const handleKeyDown = useCallback(
    (e: React.KeyboardEvent<HTMLTextAreaElement>) => {
      if (e.key === 'Enter' && !e.shiftKey) {
        e.preventDefault()
        void submit()
      }
    },
    // eslint-disable-next-line react-hooks/exhaustive-deps
    [question, streaming],
  )

  const submit = useCallback(async (overrideText?: string) => {
    const text = overrideText ?? question
    const q = text.trim()
    if (!q || streaming) return

    abortRef.current?.abort()
    const controller = new AbortController()
    abortRef.current = controller

    const userTurn: ConversationTurn = {
      role: 'user',
      content: q,
      run_id: runId,
      citations: [],
      created_at: new Date().toISOString(),
    }
    onConversationUpdate(userTurn)
    setQuestion('')
    if (textareaRef.current) {
      textareaRef.current.style.height = 'auto'
    }
    setStreamingText('')
    setError(null)
    setStreaming(true)
    setLatestSuggestions([])

    let accumulatedAnswer = ''
    let finalCitations: Citation[] = []

    try {
      await streamFollowup(sessionId, q, runId, accessToken, {
        signal: controller.signal,
        onChunk: (text) => {
          accumulatedAnswer += text
          setStreamingText((prev) => prev + text)
        },
        onCitations: (citations) => {
          finalCitations = citations
        },
        onSuggestions: (suggestions) => setLatestSuggestions(suggestions),
        onDone: () => {
          const assistantTurn: ConversationTurn = {
            role: 'assistant',
            content: accumulatedAnswer,
            run_id: runId,
            citations: finalCitations,
            created_at: new Date().toISOString(),
          }
          onConversationUpdate(assistantTurn)
          setStreamingText('')
          setStreaming(false)
        },
        onError: (err) => {
          setError(err)
          setStreaming(false)
          setStreamingText('')
        },
      })
    } catch (err) {
      if (controller.signal.aborted) return
      setError(err instanceof Error ? err.message : 'Follow-up failed.')
      setStreaming(false)
      setStreamingText('')
    } finally {
      if (abortRef.current === controller) {
        abortRef.current = null
      }
    }
  }, [question, streaming, sessionId, runId, accessToken, onConversationUpdate])

  const handleSubmit = useCallback(
    (e: React.FormEvent) => {
      e.preventDefault()
      void submit()
    },
    [submit],
  )

  return (
    <section className="glass-panel followup-panel">
      <div className="followup-header">
        <h2>Follow-up Questions</h2>
        <p className="followup-hint">
          Ask questions grounded to the same research sources.
        </p>
      </div>

      <div className="followup-messages">
        {conversation.length === 0 && !streaming && (
          <p className="followup-empty">No questions yet. Ask something below.</p>
        )}

        {conversation.map((turn, i) =>
          turn.role === 'user' ? (
            <UserBubble key={i} turn={turn} />
          ) : (
            <AssistantBubble key={i} turn={turn} />
          ),
        )}

        {streaming && streamingText && (
          <AssistantBubble
            turn={{ role: 'assistant', content: streamingText, run_id: runId, citations: [], created_at: '' }}
            streaming
          />
        )}

        {streaming && !streamingText && (
          <div className="followup-row followup-row--assistant">
            <div className="followup-avatar" aria-hidden="true">AI</div>
            <div className="followup-bubble followup-bubble--assistant followup-bubble--thinking">
              <span className="followup-dot" />
              <span className="followup-dot" />
              <span className="followup-dot" />
            </div>
          </div>
        )}

        <div ref={bottomRef} />
      </div>

      <SuggestionChips
        suggestions={latestSuggestions}
        onSelect={(text) => void submit(text)}
        disabled={streaming}
      />

      {error && <p className="error-banner followup-error">{error}</p>}

      <form onSubmit={handleSubmit} className="followup-form">
        <textarea
          ref={textareaRef}
          value={question}
          onChange={handleQuestionChange}
          onKeyDown={handleKeyDown}
          placeholder="Ask a follow-up question… (Enter to send, Shift+Enter for newline)"
          disabled={streaming}
          className="followup-textarea"
          aria-label="Follow-up question"
          rows={1}
        />
        <button
          type="submit"
          disabled={streaming || !question.trim()}
          className="followup-send-btn"
          aria-label="Send"
        >
          <svg width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2.2" strokeLinecap="round" strokeLinejoin="round">
            <line x1="22" y1="2" x2="11" y2="13" />
            <polygon points="22 2 15 22 11 13 2 9 22 2" />
          </svg>
        </button>
      </form>
    </section>
  )
}
