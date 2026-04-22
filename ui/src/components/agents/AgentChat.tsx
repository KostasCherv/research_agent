import { useState } from 'react'
import { ArrowLeft, SendHorizontal } from 'lucide-react'
import { chatWithRagAgent } from '@/api/client'
import { Badge } from '@/components/ui/badge'
import { Button } from '@/components/ui/button'
import { ScrollArea } from '@/components/ui/scroll-area'
import { Textarea } from '@/components/ui/textarea'
import type { RagAgent, RagChatMessage } from '@/types'

type Props = {
  agent: RagAgent
  accessToken: string
  onBack: () => void
}

export function AgentChat({ agent, accessToken, onBack }: Props) {
  const [messages, setMessages] = useState<RagChatMessage[]>([])
  const [sessionId, setSessionId] = useState<string | null>(null)
  const [input, setInput] = useState('')
  const [chatting, setChatting] = useState(false)
  const [error, setError] = useState<string | null>(null)

  const send = async () => {
    if (!input.trim() || chatting) return
    setChatting(true)
    setError(null)
    try {
      const res = await chatWithRagAgent(agent.agent_id, input.trim(), sessionId, accessToken)
      setSessionId(res.session_id)
      setMessages(res.messages)
      setInput('')
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Chat failed.')
    } finally {
      setChatting(false)
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
                  {m.content}
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
  )
}
