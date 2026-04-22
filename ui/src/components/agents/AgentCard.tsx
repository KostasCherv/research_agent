import { MessageSquare, MoreHorizontal } from 'lucide-react'
import { Button } from '@/components/ui/button'
import { Card, CardContent, CardFooter, CardHeader, CardTitle } from '@/components/ui/card'
import {
  DropdownMenu,
  DropdownMenuContent,
  DropdownMenuItem,
  DropdownMenuTrigger,
} from '@/components/ui/dropdown-menu'
import type { RagAgent } from '@/types'

type Props = {
  agent: RagAgent
  onChat: (agent: RagAgent) => void
  onDelete: (agentId: string) => void
}

export function AgentCard({ agent, onChat, onDelete }: Props) {
  return (
    <Card>
      <CardHeader className="pb-2">
        <div className="flex items-start justify-between gap-2">
          <CardTitle className="text-base">{agent.name}</CardTitle>
          <DropdownMenu>
            <DropdownMenuTrigger asChild>
              <Button variant="ghost" size="icon" className="size-7 shrink-0">
                <MoreHorizontal size={14} />
              </Button>
            </DropdownMenuTrigger>
            <DropdownMenuContent align="end">
              <DropdownMenuItem className="text-destructive" onClick={() => onDelete(agent.agent_id)}>
                Delete
              </DropdownMenuItem>
            </DropdownMenuContent>
          </DropdownMenu>
        </div>
      </CardHeader>
      <CardContent className="pb-3">
        <p className="text-sm text-muted-foreground line-clamp-2">{agent.description || 'No description'}</p>
        <p className="text-xs text-muted-foreground mt-2">
          {agent.linked_resource_ids.length} resource{agent.linked_resource_ids.length !== 1 ? 's' : ''}
        </p>
      </CardContent>
      <CardFooter>
        <Button size="sm" className="w-full" onClick={() => onChat(agent)}>
          <MessageSquare size={14} />
          Chat
        </Button>
      </CardFooter>
    </Card>
  )
}
