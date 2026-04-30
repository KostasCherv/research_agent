import { CheckCircle2, CircleDot, Loader2, XCircle } from 'lucide-react'
import { cn } from '@/lib/utils'
import type { ResearchStreamEvent } from '@/types'

const NODE_ALIASES: Record<string, string> = {
  search: 'search_node',
  retrieve: 'retrieve_node',
  memory_context: 'memory_context_node',
  summarize: 'summarize_node',
  combine: 'combine_node',
  report: 'report_node',
  vector_store: 'vector_store_node',
  abort: '__error__',
}

const NODE_LABELS: Record<string, string> = {
  search_node: 'Search',
  retrieve_node: 'Retrieve',
  memory_context_node: 'Context',
  summarize_node: 'Summarize',
  combine_node: 'Combine',
  report_node: 'Report',
  vector_store_node: 'Store',
  __error__: 'Failed',
}

const PIPELINE_PHASES = [
  'search_node',
  'retrieve_node',
  'memory_context_node',
  'summarize_node',
  'combine_node',
  'report_node',
  'vector_store_node',
]

// Customize this list to display only selected phases in the UI.
const VISIBLE_PHASES = PIPELINE_PHASES

type Props = {
  events: ResearchStreamEvent[]
  isStreaming: boolean
}

export function InlineProgress({ events, isStreaming }: Props) {
  if (events.length === 0 && !isStreaming) return null

  const normalizedNodes = events.map((e) => NODE_ALIASES[e.node] ?? e.node)
  const seenNodes = new Set(normalizedNodes)
  const latestVisibleNode = [...normalizedNodes].reverse().find((node) => VISIBLE_PHASES.includes(node)) ?? null
  const furthestKnownPhaseIndex = normalizedNodes.reduce((max, node) => {
    const idx = PIPELINE_PHASES.indexOf(node)
    return idx > max ? idx : max
  }, -1)
  const hasError = seenNodes.has('__error__')
  const ended = seenNodes.has('__end__')
  const hasCurrent = isStreaming && !ended && !hasError

  return (
    <div className="flex items-center gap-1 flex-wrap" aria-live="polite">
      {VISIBLE_PHASES.map((node, index) => {
        const phaseIndex = PIPELINE_PHASES.indexOf(node)
        const complete = ended || (phaseIndex !== -1 && phaseIndex < furthestKnownPhaseIndex)
        const current =
          hasCurrent &&
          (latestVisibleNode === node ||
            (!latestVisibleNode &&
              furthestKnownPhaseIndex === -1 &&
              node === VISIBLE_PHASES[0]))
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
            {index < VISIBLE_PHASES.length - 1 && (
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
