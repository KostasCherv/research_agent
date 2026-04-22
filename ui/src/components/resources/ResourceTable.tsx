import { Trash2 } from 'lucide-react'
import { Badge } from '@/components/ui/badge'
import { Button } from '@/components/ui/button'
import type { RagResource, RagResourceState } from '@/types'

const STATE_VARIANT: Record<RagResourceState, 'default' | 'secondary' | 'destructive' | 'outline'> = {
  ready: 'default',
  processing: 'secondary',
  uploaded: 'secondary',
  failed: 'destructive',
}

type Props = {
  resources: RagResource[]
  onDelete: (id: string) => Promise<void>
}

export function ResourceTable({ resources, onDelete }: Props) {
  if (resources.length === 0) {
    return (
      <div className="text-center py-12 text-muted-foreground text-sm">
        No resources yet. Upload a file to get started.
      </div>
    )
  }

  return (
    <div className="rounded-md border">
      <table className="w-full text-sm">
        <thead>
          <tr className="border-b bg-muted/50">
            <th className="text-left px-4 py-2.5 font-medium text-muted-foreground">Name</th>
            <th className="text-left px-4 py-2.5 font-medium text-muted-foreground">Size</th>
            <th className="text-left px-4 py-2.5 font-medium text-muted-foreground">Status</th>
            <th className="text-left px-4 py-2.5 font-medium text-muted-foreground">Added</th>
            <th className="px-4 py-2.5" />
          </tr>
        </thead>
        <tbody>
          {resources.map((r) => (
            <tr key={r.resource_id} className="border-b last:border-0">
              <td className="px-4 py-3 font-medium max-w-xs truncate">{r.filename}</td>
              <td className="px-4 py-3 text-muted-foreground">{(r.byte_size / 1024).toFixed(1)} KB</td>
              <td className="px-4 py-3">
                <Badge variant={STATE_VARIANT[r.state]} className="capitalize">
                  {r.state}
                </Badge>
              </td>
              <td className="px-4 py-3 text-muted-foreground">
                {new Date(r.created_at).toLocaleDateString()}
              </td>
              <td className="px-4 py-3">
                <Button
                  variant="ghost"
                  size="icon"
                  className="size-7 text-muted-foreground hover:text-destructive"
                  onClick={() => void onDelete(r.resource_id)}
                >
                  <Trash2 size={14} />
                </Button>
              </td>
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  )
}
