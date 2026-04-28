import { useCallback, useEffect, useRef, useState } from 'react'
import { Loader2, SendHorizontal } from 'lucide-react'
import ReactMarkdown from 'react-markdown'
import { chatWithRagAgent, getRagAgentChatSessionMessages } from '@/api/client'
import { Button } from '@/components/ui/button'
import { ScrollArea } from '@/components/ui/scroll-area'
import { Textarea } from '@/components/ui/textarea'
import { cn } from '@/lib/utils'
import type { RagAgent, RagChatMessage } from '@/types'

type Props = {
  agent: RagAgent
  accessToken: string
  activeSessionId: string | null
  onSessionActivated: (id: string | null) => void
  onSessionsChanged: () => void
}

function MarkdownMessage({ content }: { content: string }) {
  return (
    <div className="prose prose-sm dark:prose-invert max-w-none prose-p:my-0 prose-ul:my-1 prose-ol:my-1 prose-li:my-0 prose-pre:my-2 prose-code:before:content-none prose-code:after:content-none">
      <ReactMarkdown>{content}</ReactMarkdown>
    </div>
  )
}

export function AgentChat({ agent, accessToken, activeSessionId, onSessionActivated, onSessionsChanged }: Props) {
  const [messages, setMessages] = useState<RagChatMessage[]>([])
  const [sessionId, setSessionId] = useState<string | null>(null)
  const [input, setInput] = useState('')
  const [chatting, setChatting] = useState(false)
  const [error, setError] = useState<string | null>(null)

  const messagesRequestRef = useRef(0)
  const loadedSessionRef = useRef<string | null>(null)
  const currentAgentIdRef = useRef(agent.agent_id)
  const bottomRef = useRef<HTMLDivElement>(null)

  useEffect(() => {
    currentAgentIdRef.current = agent.agent_id
  }, [agent.agent_id])

  // Reset when agent changes
  useEffect(() => {
    messagesRequestRef.current += 1
    loadedSessionRef.current = null
    setSessionId(null)
    setMessages([])
    setInput('')
    setError(null)
  }, [agent.agent_id])

  // Scroll to bottom on new messages
  useEffect(() => {
    bottomRef.current?.scrollIntoView({ behavior: 'smooth' })
  }, [messages])

  const openSession = useCallback(
    async (nextSessionId: string) => {
      if (loadedSessionRef.current === nextSessionId) return
      const requestId = ++messagesRequestRef.current
      try {
        const res = await getRagAgentChatSessionMessages(agent.agent_id, nextSessionId, accessToken)
        if (requestId !== messagesRequestRef.current || currentAgentIdRef.current !== agent.agent_id) return
        loadedSessionRef.current = res.session_id
        setSessionId(res.session_id)
        setMessages(res.messages)
        setError(null)
      } catch (err) {
        if (requestId === messagesRequestRef.current && currentAgentIdRef.current === agent.agent_id) {
          setError(err instanceof Error ? err.message : 'Failed to load chat session.')
        }
      }
    },
    [accessToken, agent.agent_id],
  )

  // Respond to session selection from the rail
  useEffect(() => {
    if (!activeSessionId) {
      if (activeSessionId === null && loadedSessionRef.current !== null) {
        loadedSessionRef.current = null
        setSessionId(null)
        setMessages([])
      }
      return
    }
    void openSession(activeSessionId)
  }, [activeSessionId, openSession])

  const send = async () => {
    if (!input.trim() || chatting) return
    const requestId = ++messagesRequestRef.current
    setChatting(true)
    setError(null)
    try {
      const res = await chatWithRagAgent(agent.agent_id, input.trim(), sessionId, accessToken)
      if (requestId !== messagesRequestRef.current || currentAgentIdRef.current !== agent.agent_id) return
      loadedSessionRef.current = res.session_id
      setSessionId(res.session_id)
      setMessages(res.messages)
      setInput('')
      if (!sessionId) {
        onSessionActivated(res.session_id)
      }
      onSessionsChanged()
    } catch (err) {
      if (requestId === messagesRequestRef.current && currentAgentIdRef.current === agent.agent_id) {
        setError(err instanceof Error ? err.message : 'Chat failed.')
      }
    } finally {
      if (requestId === messagesRequestRef.current && currentAgentIdRef.current === agent.agent_id) {
        setChatting(false)
      }
    }
  }

  return (
    <div className="flex h-dvh flex-col max-md:h-full">
      {/* Agent context header */}
      <div className="flex h-14 shrink-0 items-center justify-between gap-4 border-b px-6 max-md:px-4">
        <div className="min-w-0">
          <p className="font-medium text-sm">{agent.name}</p>
          {agent.description && (
            <p className="text-xs text-muted-foreground truncate max-w-md">{agent.description}</p>
          )}
        </div>
        <span className="shrink-0 text-xs text-muted-foreground">{agent.linked_resource_ids.length} resources</span>
      </div>

      {/* Messages */}
      <ScrollArea className="min-h-0 flex-1 px-6 py-6 max-md:px-4">
        <div className="max-w-2xl mx-auto space-y-4">
          {messages.length === 0 && (
            <p className="py-8 text-center text-sm text-muted-foreground">
              Ask {agent.name} about its linked resources.
            </p>
          )}
          {messages.map((m) =>
            m.role === 'user' ? (
              <div key={m.message_id} className="flex justify-end">
                <div className="max-w-[75%] rounded-2xl rounded-br-sm bg-primary px-3 py-2 text-sm text-primary-foreground max-md:max-w-[86%]">
                  {m.content}
                </div>
              </div>
            ) : (
              <div key={m.message_id} className="flex gap-2 items-start">
                <div className="mt-0.5 flex size-7 shrink-0 items-center justify-center rounded-full bg-muted text-[10px] font-bold">
                  AI
                </div>
                <div className="max-w-[75%] rounded-2xl rounded-bl-sm bg-muted px-3 py-2 text-sm max-md:max-w-[86%]">
                  <MarkdownMessage content={m.content} />
                </div>
              </div>
            ),
          )}
          <div ref={bottomRef} />
        </div>
      </ScrollArea>

      {error && (
        <p role="alert" className="mx-6 mb-2 shrink-0 rounded-md border border-destructive/25 bg-destructive/10 px-3 py-2 text-xs text-destructive max-md:mx-4">
          {error}
        </p>
      )}

      {/* Composer */}
      <div className="shrink-0 border-t bg-background px-6 py-4 max-md:px-4">
        <div className="max-w-2xl mx-auto flex gap-2 items-end">
          <Textarea
            className="resize-none min-h-10 max-h-32 text-sm"
            placeholder="Ask a question..."
            rows={1}
            value={input}
            onChange={(e) => setInput(e.target.value)}
            onKeyDown={(e) => {
              if (e.key === 'Enter' && !e.shiftKey) {
                e.preventDefault()
                void send()
              }
            }}
            disabled={chatting}
          />
          <Button
            size="icon"
            onClick={() => void send()}
            disabled={!input.trim() || chatting}
            className={cn(chatting && 'opacity-50')}
            aria-label={chatting ? 'Sending message' : 'Send message'}
          >
            {chatting ? <Loader2 size={15} className="animate-spin" /> : <SendHorizontal size={15} />}
          </Button>
        </div>
      </div>
    </div>
  )
}
