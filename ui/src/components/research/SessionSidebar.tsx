import * as React from 'react'
import { useState } from 'react'
import { MoreHorizontal, Plus, Search } from 'lucide-react'
import { Button } from '@/components/ui/button'
import { Input } from '@/components/ui/input'
import { ScrollArea } from '@/components/ui/scroll-area'
import {
  DropdownMenu,
  DropdownMenuContent,
  DropdownMenuItem,
  DropdownMenuTrigger,
} from '@/components/ui/dropdown-menu'
import {
  Dialog,
  DialogContent,
  DialogFooter,
  DialogHeader,
  DialogTitle,
} from '@/components/ui/dialog'
import { cn } from '@/lib/utils'
import type { SessionSummary } from '@/types'

type Props = {
  sessions: SessionSummary[]
  activeSessionId: string | null
  onSelect: (sessionId: string) => void
  onRename: (sessionId: string, newTitle: string) => Promise<void>
  onDelete: (sessionId: string) => Promise<void>
  onNew: () => void
}

export function SessionSidebar({
  sessions,
  activeSessionId,
  onSelect,
  onRename,
  onDelete,
  onNew,
}: Props) {
  const [search, setSearch] = useState('')
  const [renameTarget, setRenameTarget] = useState<{ id: string; title: string } | null>(null)
  const [renameInput, setRenameInput] = useState('')
  const [renaming, setRenaming] = useState(false)
  const [renameError, setRenameError] = useState<string | null>(null)
  const [contextMenu, setContextMenu] = useState<{
    id: string
    title: string
    x: number
    y: number
  } | null>(null)

  const filtered = sessions.filter((s) => s.title.toLowerCase().includes(search.toLowerCase()))

  const openRename = (id: string, title: string) => {
    setRenameTarget({ id, title })
    setRenameInput(title)
    setRenameError(null)
  }

  const submitRename = async () => {
    if (!renameTarget || !renameInput.trim()) return
    setRenaming(true)
    setRenameError(null)
    try {
      await onRename(renameTarget.id, renameInput.trim())
      setRenameTarget(null)
    } catch (err) {
      setRenameError(err instanceof Error ? err.message : 'Failed to rename session.')
    } finally {
      setRenaming(false)
    }
  }

  React.useEffect(() => {
    if (!contextMenu) return

    const closeMenu = () => setContextMenu(null)
    window.addEventListener('click', closeMenu)
    window.addEventListener('scroll', closeMenu, true)
    window.addEventListener('resize', closeMenu)

    return () => {
      window.removeEventListener('click', closeMenu)
      window.removeEventListener('scroll', closeMenu, true)
      window.removeEventListener('resize', closeMenu)
    }
  }, [contextMenu])

  return (
    <aside className="w-60 shrink-0 border-r flex flex-col h-[calc(100vh-3.5rem)] sticky top-14">
      <div className="p-3 border-b flex items-center gap-2">
        <div className="relative flex-1">
          <Search
            size={14}
            className="absolute left-2.5 top-1/2 -translate-y-1/2 text-muted-foreground"
          />
          <Input
            placeholder="Search sessions..."
            className="pl-8 h-8 text-sm"
            value={search}
            onChange={(e) => setSearch(e.target.value)}
          />
        </div>
        <Button size="icon" variant="ghost" className="size-8 shrink-0" onClick={onNew} aria-label="New session">
          <Plus size={14} />
        </Button>
      </div>

      <ScrollArea className="flex-1">
        <div className="p-2 space-y-0.5">
          {filtered.length === 0 && (
            <p className="text-xs text-muted-foreground text-center py-6">
              {sessions.length === 0 ? 'No sessions yet.' : 'No matches.'}
            </p>
          )}
          {filtered.map((s) => (
            <div
              key={s.session_id}
              role="button"
              tabIndex={0}
              className={cn(
                'w-full text-left group flex items-center gap-1 rounded-md px-2 py-1.5 cursor-pointer hover:bg-muted',
                activeSessionId === s.session_id && 'bg-muted',
              )}
              onClick={() => onSelect(s.session_id)}
              onKeyDown={(e) => { if (e.key === 'Enter' || e.key === ' ') onSelect(s.session_id) }}
              onContextMenu={(e) => {
                e.preventDefault()
                e.stopPropagation()
                setContextMenu({
                  id: s.session_id,
                  title: s.title,
                  x: e.clientX,
                  y: e.clientY,
                })
              }}
            >
              <div className="flex-1 min-w-0">
                <p className="text-sm truncate font-medium">{s.title}</p>
                <p className="text-xs text-muted-foreground">{new Date(s.created_at).toLocaleDateString()}</p>
              </div>
              <DropdownMenu>
                <DropdownMenuTrigger
                  onClick={(e: React.MouseEvent) => e.stopPropagation()}
                  className="flex items-center justify-center rounded p-1 text-muted-foreground hover:bg-muted hover:text-foreground focus:outline-none"
                >
                  <MoreHorizontal size={16} />
                </DropdownMenuTrigger>
                <DropdownMenuContent align="end">
                  <DropdownMenuItem
                    onClick={(e: React.MouseEvent) => {
                      e.stopPropagation()
                      openRename(s.session_id, s.title)
                    }}
                  >
                    Rename
                  </DropdownMenuItem>
                  <DropdownMenuItem
                    className="text-destructive"
                    onClick={(e: React.MouseEvent) => {
                      e.stopPropagation()
                      void onDelete(s.session_id)
                    }}
                  >
                    Delete
                  </DropdownMenuItem>
                </DropdownMenuContent>
              </DropdownMenu>
            </div>
          ))}
        </div>
      </ScrollArea>

      {contextMenu && (
        <div
          className="fixed z-50 min-w-32 rounded-md border bg-popover p-1 text-popover-foreground shadow-md"
          style={{ left: contextMenu.x, top: contextMenu.y }}
          onClick={(e) => e.stopPropagation()}
        >
          <button
            type="button"
            className="w-full rounded-sm px-2 py-1.5 text-left text-sm hover:bg-accent hover:text-accent-foreground"
            onClick={() => {
              openRename(contextMenu.id, contextMenu.title)
              setContextMenu(null)
            }}
          >
            Rename
          </button>
          <button
            type="button"
            className="w-full rounded-sm px-2 py-1.5 text-left text-sm text-destructive hover:bg-accent"
            onClick={() => {
              void onDelete(contextMenu.id)
              setContextMenu(null)
            }}
          >
            Delete
          </button>
        </div>
      )}

      <Dialog
        open={!!renameTarget}
        onOpenChange={(open: boolean) => {
          if (!open) setRenameTarget(null)
        }}
      >
        <DialogContent className="sm:max-w-md">
          <DialogHeader>
            <DialogTitle>Rename session</DialogTitle>
          </DialogHeader>
          <Input
            value={renameInput}
            onChange={(e) => setRenameInput(e.target.value)}
            maxLength={120}
            autoFocus
            onKeyDown={(e) => {
              if (e.key === 'Enter') void submitRename()
            }}
          />
          {renameError && <p className="text-destructive text-sm">{renameError}</p>}
          <DialogFooter>
            <Button variant="outline" onClick={() => setRenameTarget(null)} disabled={renaming}>
              Cancel
            </Button>
            <Button onClick={() => void submitRename()} disabled={renaming || !renameInput.trim()}>
              {renaming ? 'Saving...' : 'Save'}
            </Button>
          </DialogFooter>
        </DialogContent>
      </Dialog>
    </aside>
  )
}
