import type { FC } from 'react'

type SuggestionChipsProps = {
  suggestions: string[]
  onSelect: (text: string) => void
  disabled: boolean
}

const SuggestionChips: FC<SuggestionChipsProps> = ({ suggestions, onSelect, disabled }) => {
  if (suggestions.length === 0) return null

  return (
    <div className="followup-suggestions">
      {suggestions.map((s, i) => (
        <button
          key={i}
          className="followup-suggestion-chip"
          onClick={() => onSelect(s)}
          disabled={disabled}
          type="button"
        >
          {s}
        </button>
      ))}
    </div>
  )
}

export default SuggestionChips
