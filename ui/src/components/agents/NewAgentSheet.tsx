import { useState } from 'react'
import { Button } from '@/components/ui/button'
import { Checkbox } from '@/components/ui/checkbox'
import { Input } from '@/components/ui/input'
import { Label } from '@/components/ui/label'
import { ScrollArea } from '@/components/ui/scroll-area'
import { Sheet, SheetContent, SheetFooter, SheetHeader, SheetTitle } from '@/components/ui/sheet'
import { Textarea } from '@/components/ui/textarea'
import type { RagResource } from '@/types'

type NewAgentPayload = {
  name: string
  description: string
  system_instructions: string
  linked_resource_ids: string[]
}

type Props = {
  open: boolean
  onOpenChange: (open: boolean) => void
  readyResources: RagResource[]
  onCreate: (payload: NewAgentPayload) => Promise<void>
}

export function NewAgentSheet({ open, onOpenChange, readyResources, onCreate }: Props) {
  const [name, setName] = useState('')
  const [description, setDescription] = useState('')
  const [instructions, setInstructions] = useState('')
  const [selectedIds, setSelectedIds] = useState<string[]>([])
  const [saving, setSaving] = useState(false)
  const [error, setError] = useState<string | null>(null)

  const toggle = (id: string) =>
    setSelectedIds((prev) => (prev.includes(id) ? prev.filter((x) => x !== id) : [...prev, id]))

  const handleCreate = async () => {
    if (!name.trim()) return
    setSaving(true)
    setError(null)
    try {
      await onCreate({
        name: name.trim(),
        description: description.trim(),
        system_instructions: instructions.trim(),
        linked_resource_ids: selectedIds,
      })
      setName('')
      setDescription('')
      setInstructions('')
      setSelectedIds([])
      onOpenChange(false)
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Failed to create agent.')
    } finally {
      setSaving(false)
    }
  }

  return (
    <Sheet open={open} onOpenChange={onOpenChange}>
      <SheetContent className="flex flex-col gap-0 p-0">
        <SheetHeader className="px-4 py-4 border-b">
          <SheetTitle>New Agent</SheetTitle>
        </SheetHeader>
        <ScrollArea className="flex-1">
          <div className="px-4 py-4 space-y-4">
            <div className="space-y-1.5">
              <Label>Name</Label>
              <Input
                placeholder="e.g. Research Assistant"
                value={name}
                onChange={(e) => setName(e.target.value)}
              />
            </div>
            <div className="space-y-1.5">
              <Label>Description</Label>
              <Input
                placeholder="Brief description"
                value={description}
                onChange={(e) => setDescription(e.target.value)}
              />
            </div>
            <div className="space-y-1.5">
              <Label>System instructions</Label>
              <Textarea
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
            {error && <p className="text-destructive text-sm">{error}</p>}
          </div>
        </ScrollArea>
        <SheetFooter className="px-4 py-4 border-t">
          <Button variant="outline" onClick={() => onOpenChange(false)} disabled={saving}>
            Cancel
          </Button>
          <Button onClick={() => void handleCreate()} disabled={!name.trim() || saving}>
            {saving ? 'Creating...' : 'Create agent'}
          </Button>
        </SheetFooter>
      </SheetContent>
    </Sheet>
  )
}
