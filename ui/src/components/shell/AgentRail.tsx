import { useCallback, useEffect, useRef, useState } from 'react'
import { Bot, FolderOpen, Loader2, LogOut, Moon, MoreHorizontal, Pencil, Plus, Sun, Telescope, Trash2 } from 'lucide-react'
import type { Session } from '@supabase/supabase-js'
import { deleteRagAgent, listRagAgentChatSessions, listSessions } from '@/api/client'
import { Avatar, AvatarFallback } from '@/components/ui/avatar'
import { Button } from '@/components/ui/button'
import {
  DropdownMenu,
  DropdownMenuContent,
  DropdownMenuItem,
  DropdownMenuTrigger,
} from '@/components/ui/dropdown-menu'
import { ScrollArea } from '@/components/ui/scroll-area'
import { useTheme } from '@/hooks/useTheme'
import { cn } from '@/lib/utils'
import type { RagAgent, RagChatSessionSummary, SessionSummary } from '@/types'
import type { ActiveView } from './AppShell'

type Props = {
  health: 'loading' | 'online' | 'offline'
  authSession: Session | null
  activeView: ActiveView
  ragAgents: RagAgent[]
  activeSessionId: string | null
  sessionRefreshToken: number
  onViewChange: (view: ActiveView) => void
  onSessionSelect: (id: string) => void
  onSignIn: () => void
  onSignOut: () => void
  onEditAgent: (agent: RagAgent) => void
  onAgentDeleted: (agentId: string) => void
  onNewAgent: () => void
}

type ResearchSession = SessionSummary
type AgentSession = RagChatSessionSummary

function ResearchSessionList({
  accessToken,
  activeSessionId,
  refreshToken,
  onSelect,
}: {
  accessToken: string
  activeSessionId: string | null
  refreshToken: number
  onSelect: (id: string) => void
}) {
  const [sessions, setSessions] = useState<ResearchSession[] | null>(null)
  const fetchedTokenRef = useRef(-1)

  useEffect(() => {
    if (fetchedTokenRef.current === refreshToken) return
    fetchedTokenRef.current = refreshToken
    void listSessions(accessToken)
      .then(({ sessions: data }) => setSessions(data))
      .catch(() => setSessions([]))
  }, [accessToken, refreshToken])

  if (sessions === null) {
    return (
      <div className="flex items-center gap-1.5 px-2 py-1.5">
        <Loader2 size={11} className="animate-spin text-muted-foreground" />
        <span className="text-xs text-muted-foreground">Loading sessions</span>
      </div>
    )
  }

  return (
    <>
      {sessions.slice(0, 10).map((s) => (
        <button
          key={s.session_id}
          type="button"
          onClick={() => onSelect(s.session_id)}
          className={cn(
            'w-full truncate rounded px-2 py-1 text-left text-xs transition-colors focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring focus-visible:ring-offset-2 focus-visible:ring-offset-secondary',
            activeSessionId === s.session_id
              ? 'bg-primary/10 text-primary font-medium'
              : 'text-muted-foreground hover:text-foreground hover:bg-muted/60',
          )}
          aria-current={activeSessionId === s.session_id ? 'page' : undefined}
          title={s.title || 'Untitled session'}
        >
          {s.title || 'Untitled session'}
        </button>
      ))}
    </>
  )
}

function AgentSessionList({
  agentId,
  accessToken,
  activeSessionId,
  refreshToken,
  onSelect,
}: {
  agentId: string
  accessToken: string
  activeSessionId: string | null
  refreshToken: number
  onSelect: (id: string) => void
}) {
  const [sessions, setSessions] = useState<AgentSession[]>([])
  const [pending, setPending] = useState(true)
  const fetchedTokenRef = useRef(-1)

  useEffect(() => {
    if (fetchedTokenRef.current === refreshToken) return
    fetchedTokenRef.current = refreshToken
    void listRagAgentChatSessions(agentId, accessToken)
      .then(({ sessions: data }) => {
        setSessions(data)
        setPending(false)
      })
      .catch(() => {
        setSessions([])
        setPending(false)
      })
  }, [agentId, accessToken, refreshToken])

  if (pending) {
    return (
      <div className="flex items-center gap-1.5 px-2 py-1.5">
        <Loader2 size={11} className="animate-spin text-muted-foreground" />
        <span className="text-xs text-muted-foreground">Loading chats</span>
      </div>
    )
  }

  return (
    <>
      {sessions.slice(0, 10).map((s) => (
        <button
          key={s.session_id}
          type="button"
          onClick={() => onSelect(s.session_id)}
          className={cn(
            'w-full truncate rounded px-2 py-1 text-left text-xs transition-colors focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring focus-visible:ring-offset-2 focus-visible:ring-offset-secondary',
            activeSessionId === s.session_id
              ? 'bg-primary/10 text-primary font-medium'
              : 'text-muted-foreground hover:text-foreground hover:bg-muted/60',
          )}
          aria-current={activeSessionId === s.session_id ? 'page' : undefined}
          title={s.last_message_preview || 'New chat'}
        >
          {s.last_message_preview || 'New chat'}
        </button>
      ))}
    </>
  )
}

export function AgentRail({
  health,
  authSession,
  activeView,
  ragAgents,
  activeSessionId,
  sessionRefreshToken,
  onViewChange,
  onSessionSelect,
  onSignIn,
  onSignOut,
  onEditAgent,
  onAgentDeleted,
  onNewAgent,
}: Props) {
  const { theme, toggle } = useTheme()
  const accessToken = authSession?.access_token ?? null

  const handleDeleteAgent = useCallback(
    async (agent: RagAgent) => {
      if (!accessToken) return
      const confirmed = window.confirm(`Delete agent "${agent.name}"? This cannot be undone.`)
      if (!confirmed) return
      try {
        await deleteRagAgent(agent.agent_id, accessToken)
        onAgentDeleted(agent.agent_id)
      } catch {
        // silently ignore; user sees no change
      }
    },
    [accessToken, onAgentDeleted],
  )

  const isResearch = activeView.type === 'research'
  const isResources = activeView.type === 'resources'

  return (
    <aside className="flex h-dvh w-[280px] min-w-[280px] shrink-0 flex-col border-r border-border bg-secondary max-md:h-[42dvh] max-md:min-h-[260px] max-md:w-full max-md:min-w-0 max-md:border-b max-md:border-r-0">
      {/* Header */}
      <div className="flex h-14 shrink-0 items-center justify-between px-4 max-md:h-12">
        <span className="font-semibold tracking-tight text-foreground">Cortex</span>
        <span
          className={cn(
            'size-1.5 rounded-full',
            health === 'online'
              ? 'bg-green-500'
              : health === 'offline'
                ? 'bg-red-500'
                : 'bg-muted-foreground',
          )}
          title={health === 'online' ? 'Online' : health === 'offline' ? 'Offline' : 'Checking...'}
        />
      </div>

      <div className="flex min-h-0 flex-1 flex-col overflow-y-auto py-2">
        <div className="shrink-0 space-y-0.5 pl-2 pr-4">
          {/* Research */}
          <button
            type="button"
            onClick={() => onViewChange({ type: 'research' })}
            className={cn(
              'w-full flex items-center gap-2.5 rounded-md px-2 py-1.5 text-sm transition-colors focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring focus-visible:ring-offset-2 focus-visible:ring-offset-secondary',
              isResearch
                ? 'bg-background text-foreground font-medium shadow-sm'
                : 'text-muted-foreground hover:text-foreground hover:bg-muted/60',
            )}
          >
            <Telescope size={15} className="shrink-0" />
            Research
          </button>
        </div>

        {/* Research sessions */}
        {isResearch && authSession && (
          <ScrollArea className="max-h-44 shrink-0">
            <div className="ml-7 mt-0.5 mb-1 space-y-0.5 pr-4">
              <ResearchSessionList
                accessToken={authSession.access_token}
                activeSessionId={activeSessionId}
                refreshToken={sessionRefreshToken}
                onSelect={onSessionSelect}
              />
            </div>
          </ScrollArea>
        )}

        {/* My Agents section */}
        <div className="flex min-h-0 flex-1 flex-col pt-3">
          <div className="mb-1 flex w-full shrink-0 items-center justify-between gap-2 pl-4 pr-5">
            <span className="min-w-0 text-[10px] font-semibold uppercase tracking-widest text-muted-foreground">
              My Agents
            </span>
            <Button
              variant="ghost"
              size="icon"
              className="size-6 shrink-0 rounded-md border border-border bg-background text-foreground shadow-sm hover:border-primary/30 hover:bg-background hover:text-primary"
              onClick={authSession ? onNewAgent : onSignIn}
              aria-label={authSession ? 'New agent' : 'Sign in to create an agent'}
              title={authSession ? 'New agent' : 'Sign in to create an agent'}
            >
              <Plus size={14} />
            </Button>
          </div>

          <div className="min-h-0 flex-1">
            <div className="space-y-0.5 pl-2 pr-4">
              {!authSession && (
                <p className="px-2 py-1 text-xs text-muted-foreground">Sign in to create agents.</p>
              )}

              {authSession && ragAgents.length === 0 && (
                <p className="px-2 py-1 text-xs text-muted-foreground">No agents yet.</p>
              )}

              {authSession &&
                ragAgents.map((agent) => {
                  const isActive =
                    activeView.type === 'rag-agent' && activeView.agent.agent_id === agent.agent_id

                  return (
                    <div key={agent.agent_id} className="group">
                      <div className="flex items-center gap-1">
                        <button
                          type="button"
                          onClick={() => onViewChange({ type: 'rag-agent', agent })}
                          className={cn(
                            'flex min-w-0 flex-1 items-center gap-2.5 rounded-md px-2 py-1.5 text-sm transition-colors focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring focus-visible:ring-offset-2 focus-visible:ring-offset-secondary',
                            isActive
                              ? 'bg-background text-foreground font-medium shadow-sm'
                              : 'text-muted-foreground hover:text-foreground hover:bg-muted/60',
                          )}
                        >
                          <Bot size={15} className="shrink-0" />
                          <span className="truncate" title={agent.name}>{agent.name}</span>
                        </button>

                        <DropdownMenu>
                          <DropdownMenuTrigger asChild>
                            <Button
                              variant="ghost"
                              size="icon"
                              className="size-6 shrink-0 rounded-md opacity-0 text-muted-foreground transition-opacity hover:text-foreground group-hover:opacity-100 group-focus-within:opacity-100"
                              aria-label="Agent options"
                            >
                              <MoreHorizontal size={12} />
                            </Button>
                          </DropdownMenuTrigger>
                          <DropdownMenuContent align="end" className="w-36">
                            <DropdownMenuItem onClick={() => onEditAgent(agent)}>
                              <Pencil size={13} className="mr-2" />
                              Edit
                            </DropdownMenuItem>
                            <DropdownMenuItem
                              className="text-destructive focus:text-destructive"
                              onClick={() => void handleDeleteAgent(agent)}
                            >
                              <Trash2 size={13} className="mr-2" />
                              Delete
                            </DropdownMenuItem>
                          </DropdownMenuContent>
                        </DropdownMenu>
                      </div>

                      {/* Agent sessions */}
                      {isActive && (
                        <div className="ml-5 mt-0.5 mb-1 space-y-0.5">
                          <AgentSessionList
                            key={agent.agent_id}
                            agentId={agent.agent_id}
                            accessToken={authSession.access_token}
                            activeSessionId={activeSessionId}
                            refreshToken={sessionRefreshToken}
                            onSelect={onSessionSelect}
                          />
                        </div>
                      )}
                    </div>
                  )
                })}
            </div>
          </div>
        </div>
      </div>

      {/* Footer */}
      <div className="shrink-0 space-y-0.5 border-t border-border px-2 py-2 max-md:flex max-md:items-center max-md:gap-1 max-md:border-t-0 max-md:pt-0">
        <button
          type="button"
          onClick={() => onViewChange({ type: 'resources' })}
          className={cn(
            'w-full flex items-center gap-2.5 rounded-md px-2 py-1.5 text-sm transition-colors focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring focus-visible:ring-offset-2 focus-visible:ring-offset-secondary',
            isResources
              ? 'bg-background text-foreground font-medium shadow-sm'
              : 'text-muted-foreground hover:text-foreground hover:bg-muted/60',
          )}
        >
          <FolderOpen size={15} className="shrink-0" />
          Resources
        </button>

        <div className="flex items-center gap-1 pt-1 max-md:ml-auto max-md:pt-0">
          <Button
            variant="ghost"
            size="icon"
            className="size-7 text-muted-foreground hover:text-foreground"
            onClick={toggle}
            aria-label={`Switch to ${theme === 'dark' ? 'light' : 'dark'} theme`}
          >
            {theme === 'dark' ? <Sun size={14} /> : <Moon size={14} />}
          </Button>

          <div className="flex-1" />

          {authSession ? (
            <DropdownMenu>
              <DropdownMenuTrigger asChild>
                <Button variant="ghost" size="icon" className="size-7 rounded-full" aria-label="Account menu">
                  <Avatar className="size-6">
                    <AvatarFallback className="text-[10px]">
                      {authSession.user.email?.[0]?.toUpperCase() ?? '?'}
                    </AvatarFallback>
                  </Avatar>
                </Button>
              </DropdownMenuTrigger>
              <DropdownMenuContent align="end" side="top" className="w-48">
                <DropdownMenuItem className="text-xs text-muted-foreground" disabled>
                  {authSession.user.email}
                </DropdownMenuItem>
                <DropdownMenuItem onClick={onSignOut}>
                  <LogOut size={13} className="mr-2" />
                  Sign out
                </DropdownMenuItem>
              </DropdownMenuContent>
            </DropdownMenu>
          ) : (
            <Button size="sm" variant="ghost" className="text-xs h-7 px-2" onClick={onSignIn}>
              Sign in
            </Button>
          )}
        </div>
      </div>
    </aside>
  )
}
