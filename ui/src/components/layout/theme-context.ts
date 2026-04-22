import { createContext } from 'react'

type Theme = 'light' | 'dark'

export type ThemeContextValue = {
  theme: Theme
  toggle: () => void
}

export const ThemeContext = createContext<ThemeContextValue | null>(null)
