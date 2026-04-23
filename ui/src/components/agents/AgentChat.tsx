import { useCallback, useEffect, useMemo, useRef, useState } from 'react'
import { ArrowLeft, Plus, Search, SendHorizontal } from 'lucide-react'
import ReactMarkdown from 'react-markdown'
import {
  chatWithRagAgent,
  getRagAgentChatSessionMessages,
  listRagAgentChatSessions,
} from '@/api/client'
import { Badge } from '@/components/ui/badge'
import { Button } from '@/components/ui/button'
import { Input } from '@/components/ui/input'
import { ScrollArea } from '@/components/ui/scroll-area'
import { Textarea } from '@/components/ui/textarea'
import { cn } from '@/lib/utils'
import type { RagAgent, RagChatMessage, RagChatSessionSummary } from '@/types'

type Props = {
  agent: RagAgent
  accessToken: string
  onBack: () => void
}

function chatSessionStorageKey(agentId: string): string {
  return `rag-agent-chat:${agentId}:session`
}

function MarkdownMessage({ content }: { content: string }) {
  return (
    <div className="prose prose-sm dark:prose-invert max-w-none prose-p:my-0 prose-ul:my-1 prose-ol:my-1 prose-li:my-0 prose-pre:my-2 prose-code:before:content-none prose-code:after:content-none">
      <ReactMarkdown>{content}</ReactMarkdown>
    </div>
  )
}

export function AgentChat({ agent, accessToken, onBack }: Props) {
  const [messages, setMessages] = useState<RagChatMessage[]>([])
  const [sessions, setSessions] = useState<RagChatSessionSummary[]>([])
  const [sessionId, setSessionId] = useState<string | null>(null)
  const [search, setSearch] = useState('')
  const [input, setInput] = useState('')
  const [chatting, setChatting] = useState(false)
  const [sessionsLoading, setSessionsLoading] = useState(false)
  const [error, setError] = useState<string | null>(null)
  const sessionsRequestRef = useRef(0)
  const messagesRequestRef = useRef(0)
  const currentAgentIdRef = useRef(agent.agent_id)

  useEffect(() => {
    currentAgentIdRef.current = agent.agent_id
  }, [agent.agent_id])

  const filteredSessions = useMemo(() => {
    const q = search.trim().toLowerCase()
    if (!q) return sessions
    return sessions.filter((s) => (s.last_message_preview || 'New chat').toLowerCase().includes(q))
  }, [search, sessions])

  const loadSessions = useCallback(async (): Promise<RagChatSessionSummary[]> => {
    const requestId = ++sessionsRequestRef.current
    setSessionsLoading(true)
    try {
      const res = await listRagAgentChatSessions(agent.agent_id, accessToken)
      if (requestId !== sessionsRequestRef.current || currentAgentIdRef.current !== agent.agent_id) {
        return []
      }
      setSessions(res.sessions)
      setError(null)
      return res.sessions
    } catch (err) {
      if (requestId === sessionsRequestRef.current && currentAgentIdRef.current === agent.agent_id) {
        setSessions([])
        setError(err instanceof Error ? err.message : 'Failed to load chat sessions.')
      }
      return []
    } finally {
      if (requestId === sessionsRequestRef.current && currentAgentIdRef.current === agent.agent_id) {
        setSessionsLoading(false)
      }
    }
  }, [accessToken, agent.agent_id])

  const openSession = useCallback(
    async (nextSessionId: string, persist = true) => {
      const requestId = ++messagesRequestRef.current
      setChatting(false)
      try {
        const res = await getRagAgentChatSessionMessages(agent.agent_id, nextSessionId, accessToken)
        if (requestId !== messagesRequestRef.current || currentAgentIdRef.current !== agent.agent_id) {
          return
        }
        setSessionId(res.session_id)
        setMessages(res.messages)
        if (persist) {
          window.localStorage.setItem(chatSessionStorageKey(agent.agent_id), res.session_id)
        }
        setError(null)
      } catch (err) {
        if (requestId === messagesRequestRef.current && currentAgentIdRef.current === agent.agent_id) {
          setError(err instanceof Error ? err.message : 'Failed to load chat session.')
        }
      }
    },
    [accessToken, agent.agent_id],
  )

  const startNewChat = useCallback(() => {
    messagesRequestRef.current += 1
    window.localStorage.removeItem(chatSessionStorageKey(agent.agent_id))
    setSessionId(null)
    setMessages([])
    setInput('')
    setChatting(false)
  }, [agent.agent_id])

  useEffect(() => {
    messagesRequestRef.current += 1
    setSessionId(null)
    setMessages([])
    setSearch('')
    setInput('')

    void (async () => {
      const loadedSessions = await loadSessions()
      const persistedSessionId = window.localStorage.getItem(chatSessionStorageKey(agent.agent_id))
      const sessionToOpen =
        loadedSessions.find((s) => s.session_id === persistedSessionId) ?? loadedSessions[0]
      if (sessionToOpen) {
        await openSession(sessionToOpen.session_id, true)
      }
    })()
  }, [agent.agent_id, loadSessions, openSession])

  const send = async () => {
    if (!input.trim() || chatting) return
    const requestId = ++messagesRequestRef.current
    setChatting(true)
    setError(null)
    try {
      const res = await chatWithRagAgent(agent.agent_id, input.trim(), sessionId, accessToken)
      if (requestId !== messagesRequestRef.current || currentAgentIdRef.current !== agent.agent_id) {
        return
      }
      setSessionId(res.session_id)
      setMessages(res.messages)
      window.localStorage.setItem(chatSessionStorageKey(agent.agent_id), res.session_id)
      await loadSessions()
      setInput('')
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
    <div className="flex flex-col h-[calc(100vh-3.5rem)]">
      <div className="border-b px-4 py-3 flex items-center gap-3">
        <Button variant="ghost" size="icon" className="size-8" onClick={onBack}>
          <ArrowLeft size={16} />
        </Button>
        <div>
          <p className="font-semibold text-sm">{agent.name}</p>
          <p className="text-xs text-muted-foreground">{agent.linked_resource_ids.length} resources</p>
        </div>
        <Badge variant="outline" className="ml-auto text-xs">
          RAG Agent
        </Badge>
      </div>

      <div className="flex min-h-0 flex-1">
        <aside className="w-60 shrink-0 border-r flex flex-col">
          <div className="p-3 border-b flex items-center gap-2">
            <div className="relative flex-1">
              <Search
                size={14}
                className="absolute left-2.5 top-1/2 -translate-y-1/2 text-muted-foreground"
              />
              <Input
                placeholder="Search chats..."
                className="pl-8 h-8 text-sm"
                value={search}
                onChange={(e) => setSearch(e.target.value)}
              />
            </div>
            <Button
              size="icon"
              variant="ghost"
              className="size-8 shrink-0"
              onClick={startNewChat}
              aria-label="New chat"
            >
              <Plus size={14} />
            </Button>
          </div>

          <ScrollArea className="flex-1">
            <div className="p-2 space-y-0.5">
              {sessionsLoading && (
                <p className="text-xs text-muted-foreground text-center py-6">Loading chats...</p>
              )}
              {!sessionsLoading && filteredSessions.length === 0 && (
                <p className="text-xs text-muted-foreground text-center py-6">
                  {sessions.length === 0 ? 'No chats yet.' : 'No matches.'}
                </p>
              )}
              {filteredSessions.map((s) => (
                <button
                  key={s.session_id}
                  type="button"
                  className={cn(
                    'w-full text-left rounded-md px-2 py-1.5 hover:bg-muted',
                    sessionId === s.session_id && 'bg-muted',
                  )}
                  onClick={() => void openSession(s.session_id)}
                >
                  <span className="block text-sm truncate font-medium">
                    {s.last_message_preview || 'New chat'}
                  </span>
                  <span className="block text-xs text-muted-foreground">
                    {new Date(s.last_message_at || s.created_at).toLocaleDateString()}
                  </span>
                </button>
              ))}
            </div>
          </ScrollArea>
        </aside>

        <div className="flex min-w-0 flex-1 flex-col">
          <ScrollArea className="flex-1 px-4 py-4">
            <div className="max-w-2xl mx-auto space-y-4">
              {messages.length === 0 && (
                <p className="text-center text-muted-foreground text-sm py-8">
                  Ask {agent.name} anything about its linked resources.
                </p>
              )}
              {messages.map((m) =>
                m.role === 'user' ? (
                  <div key={m.message_id} className="flex justify-end">
                    <div className="max-w-[75%] bg-primary text-primary-foreground rounded-2xl rounded-br-sm px-3 py-2 text-sm">
                      {m.content}
                    </div>
                  </div>
                ) : (
                  <div key={m.message_id} className="flex gap-2 items-start">
                    <div className="size-7 rounded-full bg-muted flex items-center justify-center text-[10px] font-bold shrink-0">
                      AI
                    </div>
                    <div className="max-w-[75%] bg-muted rounded-2xl rounded-bl-sm px-3 py-2 text-sm">
                      <MarkdownMessage content={m.content} />
                    </div>
                  </div>
                ),
              )}
            </div>
          </ScrollArea>

          {error && <p className="text-destructive text-xs px-4 pb-1">{error}</p>}

          <div className="border-t px-4 py-3">
            <div className="max-w-2xl mx-auto flex gap-2 items-end">
              <Textarea
                className="resize-none min-h-10 max-h-32"
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
              <Button size="icon" onClick={() => void send()} disabled={!input.trim() || chatting}>
                <SendHorizontal size={16} />
              </Button>
            </div>
          </div>
        </div>
      </div>
    </div>
  )
}
