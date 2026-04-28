import { CheckCircle2, CircleDot, Loader2, XCircle } from 'lucide-react'
import { cn } from '@/lib/utils'
import type { ResearchStreamEvent } from '@/types'

const NODE_ALIASES: Record<string, string> = {
  search: 'search_node',
  retrieve: 'retrieve_node',
  summarize: 'summarize_node',
  combine: 'combine_node',
  report: 'report_node',
  vector_store: 'vector_store_node',
  abort: '__error__',
}

const NODE_LABELS: Record<string, string> = {
  search_node: 'Search',
  retrieve_node: 'Retrieve',
  summarize_node: 'Summarize',
  combine_node: 'Combine',
  report_node: 'Report',
  vector_store_node: 'Store',
  __error__: 'Failed',
}

const ORDERED_PHASES = [
  'search_node',
  'retrieve_node',
  'summarize_node',
  'combine_node',
  'report_node',
  'vector_store_node',
]

type Props = {
  events: ResearchStreamEvent[]
  isStreaming: boolean
}

export function InlineProgress({ events, isStreaming }: Props) {
  if (events.length === 0 && !isStreaming) return null

  const normalizedNodes = events.map((e) => NODE_ALIASES[e.node] ?? e.node)
  const seenNodes = new Set(normalizedNodes)
  const latestNode = normalizedNodes.at(-1) ?? null
  const latestIndex = latestNode ? ORDERED_PHASES.indexOf(latestNode) : -1
  const hasError = seenNodes.has('__error__')
  const ended = seenNodes.has('__end__')

  return (
    <div className="flex items-center gap-1 flex-wrap" aria-live="polite">
      {ORDERED_PHASES.map((node, index) => {
        const complete = seenNodes.has(node) && (latestIndex > index || ended)
        const current = latestNode === node && isStreaming && !ended
        const seen = seenNodes.has(node)

        return (
          <div key={node} className="flex items-center gap-1">
            <span
              className={cn(
                'flex items-center gap-1 text-xs px-2 py-0.5 rounded-full border transition-colors',
                complete
                  ? 'border-green-200 bg-green-50 text-green-700 dark:border-green-800 dark:bg-green-950/40 dark:text-green-400'
                  : current
                    ? 'border-primary/40 bg-primary/5 text-primary'
                    : seen
                      ? 'border-border bg-muted/50 text-foreground'
                      : 'border-border bg-transparent text-muted-foreground',
              )}
            >
              {complete ? (
                <CheckCircle2 size={10} />
              ) : current ? (
                <Loader2 size={10} className="animate-spin" />
              ) : (
                <CircleDot size={10} />
              )}
              {NODE_LABELS[node] ?? node}
            </span>
            {index < ORDERED_PHASES.length - 1 && (
              <span className="text-muted-foreground/40 text-xs select-none">›</span>
            )}
          </div>
        )
      })}
      {hasError && (
        <span className="flex items-center gap-1 text-xs px-2 py-0.5 rounded-full border border-destructive/30 bg-destructive/5 text-destructive">
          <XCircle size={10} />
          Failed
        </span>
      )}
    </div>
  )
}
