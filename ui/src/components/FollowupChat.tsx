import { useCallback, useRef, useState } from 'react'
import { streamFollowup } from '../api/client'
import type { Citation, ConversationTurn } from '../types'

type FollowupChatProps = {
  sessionId: string
  runId: string | null
  conversation: ConversationTurn[]
  onConversationUpdate: (turn: ConversationTurn) => void
}

function CitationChip({ citation }: { citation: Citation }) {
  return (
    <a
      href={citation.source_url}
      target="_blank"
      rel="noopener noreferrer"
      className="citation-chip"
      title={citation.source_url}
    >
      {citation.source_title || 'source'}
    </a>
  )
}

function TurnBubble({ turn }: { turn: ConversationTurn }) {
  const isUser = turn.role === 'user'
  return (
    <div className={`followup-turn followup-turn--${isUser ? 'user' : 'assistant'}`}>
      <p className="followup-turn__content">{turn.content}</p>
      {!isUser && turn.citations.length > 0 && (
        <div className="followup-turn__citations">
          {turn.citations.map((c) => (
            <CitationChip key={c.source_url} citation={c} />
          ))}
        </div>
      )}
    </div>
  )
}

export function FollowupChat({ sessionId, runId, conversation, onConversationUpdate }: FollowupChatProps) {
  const [question, setQuestion] = useState('')
  const [streaming, setStreaming] = useState(false)
  const [streamingText, setStreamingText] = useState('')
  const [error, setError] = useState<string | null>(null)
  const abortRef = useRef<AbortController | null>(null)

  const handleSubmit = useCallback(
    async (e: React.FormEvent) => {
      e.preventDefault()
      const q = question.trim()
      if (!q || streaming) return

      abortRef.current?.abort()
      const controller = new AbortController()
      abortRef.current = controller

      // Optimistically add user turn
      const userTurn: ConversationTurn = {
        role: 'user',
        content: q,
        run_id: runId,
        citations: [],
        created_at: new Date().toISOString(),
      }
      onConversationUpdate(userTurn)
      setQuestion('')
      setStreamingText('')
      setError(null)
      setStreaming(true)

      let accumulatedAnswer = ''
      let finalCitations: Citation[] = []

      try {
        await streamFollowup(sessionId, q, runId, {
          signal: controller.signal,
          onChunk: (text) => {
            accumulatedAnswer += text
            setStreamingText((prev) => prev + text)
          },
          onCitations: (citations) => {
            finalCitations = citations
          },
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
    },
    [question, streaming, sessionId, runId, onConversationUpdate],
  )

  return (
    <section className="glass-panel card-spacing followup-panel">
      <h2>Follow-up Questions</h2>
      <p className="followup-hint">
        Ask questions about the research above — answers are grounded to the same sources.
      </p>

      {conversation.length > 0 && (
        <div className="followup-conversation">
          {conversation.map((turn, i) => (
            <TurnBubble key={i} turn={turn} />
          ))}
          {streaming && streamingText && (
            <div className="followup-turn followup-turn--assistant followup-turn--streaming">
              <p className="followup-turn__content">{streamingText}</p>
            </div>
          )}
        </div>
      )}

      {error && <p className="error-banner">{error}</p>}

      <form onSubmit={handleSubmit} className="followup-form">
        <input
          type="text"
          value={question}
          onChange={(e) => setQuestion(e.target.value)}
          placeholder="Ask a follow-up question..."
          disabled={streaming}
          className="followup-input"
          aria-label="Follow-up question"
        />
        <button
          type="submit"
          disabled={streaming || !question.trim()}
          className="submit-button followup-submit"
        >
          {streaming ? 'Thinking…' : 'Ask'}
        </button>
      </form>
    </section>
  )
}
