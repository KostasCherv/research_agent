import { useState } from 'react'
import { SendHorizontal } from 'lucide-react'

type ChatFormProps = {
  onSubmit: (query: string, useVectorStore: boolean) => Promise<void>
  disabled: boolean
}

export function ChatForm({ onSubmit, disabled }: ChatFormProps) {
  const [query, setQuery] = useState('')
  const [useVectorStore, setUseVectorStore] = useState(true)

  async function handleSubmit(event: React.FormEvent<HTMLFormElement>) {
    event.preventDefault()
    if (!query.trim() || disabled) {
      return
    }
    await onSubmit(query, useVectorStore)
  }

  return (
    <section className="glass-panel card-spacing">
      <h2>Start Research</h2>
      <form onSubmit={handleSubmit} className="form-stack">
        <label htmlFor="query-input" className="input-label">
          Research query
        </label>
        <textarea
          id="query-input"
          name="query"
          value={query}
          onChange={(event) => setQuery(event.target.value)}
          placeholder="Example: Compare Model Context Protocol server frameworks in Python vs TypeScript."
          className="query-input"
          rows={4}
          disabled={disabled}
          required
        />

        <label htmlFor="vector-toggle" className="toggle-row">
          <span>Store report in vector database</span>
          <input
            id="vector-toggle"
            type="checkbox"
            checked={useVectorStore}
            onChange={(event) => setUseVectorStore(event.target.checked)}
            disabled={disabled}
          />
        </label>

        <button
          type="submit"
          className="submit-button"
          disabled={disabled || !query.trim()}
        >
          <SendHorizontal size={16} />
          {disabled ? 'Running...' : 'Run Research'}
        </button>
      </form>
    </section>
  )
}
