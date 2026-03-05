import { CheckCircle2, CircleDot, LoaderCircle, XCircle } from 'lucide-react'
import type { ResearchStreamEvent } from '../types'

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
  search_node: 'Searching',
  retrieve_node: 'Retrieving Sources',
  summarize_node: 'Summarizing',
  combine_node: 'Combining Insights',
  report_node: 'Generating Report',
  vector_store_node: 'Storing Report',
  __end__: 'Completed',
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

function normalizeNodeName(node: string): string {
  return NODE_ALIASES[node] ?? node
}

type ResearchProgressProps = {
  events: ResearchStreamEvent[]
  isStreaming: boolean
}

export function ResearchProgress({ events, isStreaming }: ResearchProgressProps) {
  const normalizedNodes = events.map((event) => normalizeNodeName(event.node))
  const seenNodes = new Set(normalizedNodes)
  const latestNode = normalizedNodes.length > 0 ? normalizedNodes[normalizedNodes.length - 1] : null
  const latestIndex = latestNode ? ORDERED_PHASES.indexOf(latestNode) : -1
  const hasError = seenNodes.has('__error__')
  const ended = seenNodes.has('__end__')

  return (
    <section className="glass-panel card-spacing">
      <h2>Progress</h2>
      <ul className="progress-list" aria-live="polite">
        {ORDERED_PHASES.map((node, index) => {
          const complete = seenNodes.has(node) && latestIndex > index
          const current = latestNode === node && isStreaming
          return (
            <li key={node} className="progress-item">
              {complete ? (
                <CheckCircle2 size={18} className="status-online" />
              ) : current ? (
                <LoaderCircle size={18} className="spin" />
              ) : (
                <CircleDot size={18} className="status-muted" />
              )}
              <span>{NODE_LABELS[node] ?? node}</span>
            </li>
          )
        })}
        {hasError && (
          <li className="progress-item">
            <XCircle size={18} className="status-offline" />
            <span>{NODE_LABELS.__error__}</span>
          </li>
        )}
        {ended && (
          <li className="progress-item">
            <CheckCircle2 size={18} className="status-online" />
            <span>{NODE_LABELS.__end__}</span>
          </li>
        )}
      </ul>
    </section>
  )
}
