import { Loader2, XCircle } from 'lucide-react'

type Props = {
  status: 'idle' | 'running' | 'completed' | 'failed'
  error?: string | null
}

export function InlineProgress({ status, error }: Props) {
  if (status === 'idle' || status === 'completed') return null

  return (
    <div className="flex items-center gap-2 flex-wrap" aria-live="polite">
      {status === 'running' && (
        <span className="flex items-center gap-1 text-xs px-2 py-0.5 rounded-full border border-primary/40 bg-primary/5 text-primary">
          <Loader2 size={10} className="animate-spin" />
          Researching and drafting report...
        </span>
      )}
      {status === 'failed' && (
        <span className="flex items-center gap-1 text-xs px-2 py-0.5 rounded-full border border-destructive/30 bg-destructive/5 text-destructive">
          <XCircle size={10} />
          {error || 'Research failed.'}
        </span>
      )}
    </div>
  )
}
