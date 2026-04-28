import { useEffect, useId, useState } from 'react'
import { Loader2 } from 'lucide-react'
import { Button } from '@/components/ui/button'
import { Checkbox } from '@/components/ui/checkbox'
import { Input } from '@/components/ui/input'
import { Label } from '@/components/ui/label'
import { ScrollArea } from '@/components/ui/scroll-area'
import { Sheet, SheetContent, SheetFooter, SheetHeader, SheetTitle } from '@/components/ui/sheet'
import { Textarea } from '@/components/ui/textarea'
import type { RagAgent, RagResource } from '@/types'

type NewAgentPayload = {
  name: string
  description: string
  system_instructions: string
  linked_resource_ids: string[]
}

type Props = {
  open: boolean
  onOpenChange: (open: boolean) => void
  agent?: RagAgent | null
  readyResources: RagResource[]
  onCreate: (payload: NewAgentPayload) => Promise<void>
  onUpdate?: (agentId: string, payload: NewAgentPayload) => Promise<void>
}

export function NewAgentSheet({ open, onOpenChange, agent, readyResources, onCreate, onUpdate }: Props) {
  const [name, setName] = useState('')
  const [description, setDescription] = useState('')
  const [instructions, setInstructions] = useState('')
  const [selectedIds, setSelectedIds] = useState<string[]>([])
  const [saving, setSaving] = useState(false)
  const [error, setError] = useState<string | null>(null)
  const nameId = useId()
  const descriptionId = useId()
  const instructionsId = useId()
  const isEditing = Boolean(agent)

  useEffect(() => {
    if (!open) return
    setName(agent?.name ?? '')
    setDescription(agent?.description ?? '')
    setInstructions(agent?.system_instructions ?? '')
    setSelectedIds(agent?.linked_resource_ids ?? [])
    setError(null)
  }, [agent, open])

  const toggle = (id: string) =>
    setSelectedIds((prev) => (prev.includes(id) ? prev.filter((x) => x !== id) : [...prev, id]))

  const handleSave = async () => {
    if (!name.trim()) return
    setSaving(true)
    setError(null)
    const payload = {
      name: name.trim(),
      description: description.trim(),
      system_instructions: instructions.trim(),
      linked_resource_ids: selectedIds,
    }
    try {
      if (agent) {
        if (!onUpdate) throw new Error('Missing update handler.')
        await onUpdate(agent.agent_id, payload)
      } else {
        await onCreate(payload)
      }
      onOpenChange(false)
    } catch (err) {
      setError(err instanceof Error ? err.message : `Failed to ${isEditing ? 'update' : 'create'} agent.`)
    } finally {
      setSaving(false)
    }
  }

  return (
    <Sheet open={open} onOpenChange={onOpenChange}>
      <SheetContent className="flex flex-col gap-0 p-0">
        <SheetHeader className="px-4 py-4 border-b">
          <SheetTitle>{isEditing ? 'Edit Agent' : 'New Agent'}</SheetTitle>
        </SheetHeader>
        <ScrollArea className="flex-1">
          <div className="px-4 py-4 space-y-4">
            <div className="space-y-1.5">
              <Label htmlFor={nameId}>Name</Label>
              <Input
                id={nameId}
                placeholder="e.g. Research Assistant"
                value={name}
                onChange={(e) => setName(e.target.value)}
              />
            </div>
            <div className="space-y-1.5">
              <Label htmlFor={descriptionId}>Description</Label>
              <Input
                id={descriptionId}
                placeholder="Brief description"
                value={description}
                onChange={(e) => setDescription(e.target.value)}
              />
            </div>
            <div className="space-y-1.5">
              <Label htmlFor={instructionsId}>System instructions</Label>
              <Textarea
                id={instructionsId}
                placeholder="How should this agent behave?"
                rows={4}
                value={instructions}
                onChange={(e) => setInstructions(e.target.value)}
              />
            </div>
            <div className="space-y-2">
              <Label>Resources</Label>
              {readyResources.length === 0 ? (
                <p className="text-sm text-muted-foreground">No ready resources. Upload some first.</p>
              ) : (
                readyResources.map((r) => (
                  <div key={r.resource_id} className="flex items-center gap-2">
                    <Checkbox
                      id={r.resource_id}
                      checked={selectedIds.includes(r.resource_id)}
                      onCheckedChange={() => toggle(r.resource_id)}
                    />
                    <Label htmlFor={r.resource_id} className="font-normal cursor-pointer text-sm">
                      {r.filename}
                    </Label>
                  </div>
                ))
              )}
            </div>
            {error && (
              <p role="alert" className="rounded-md border border-destructive/25 bg-destructive/10 px-3 py-2 text-sm text-destructive">
                {error}
              </p>
            )}
          </div>
        </ScrollArea>
        <SheetFooter className="px-4 py-4 border-t">
          <Button variant="outline" onClick={() => onOpenChange(false)} disabled={saving}>
            Cancel
          </Button>
          <Button onClick={() => void handleSave()} disabled={!name.trim() || saving}>
            {saving && <Loader2 size={14} className="animate-spin" />}
            {saving ? (isEditing ? 'Saving' : 'Creating') : isEditing ? 'Save changes' : 'Create agent'}
          </Button>
        </SheetFooter>
      </SheetContent>
    </Sheet>
  )
}
