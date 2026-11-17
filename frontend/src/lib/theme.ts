import { useCallback, useEffect, useState } from 'react'

export type Theme = 'dark' | 'light'

/** Light is the default on every load; dark is a temporary switch that is never saved. */
export const DEFAULT_THEME: Theme = 'light'

export function applyTheme(t: Theme) {
  const el = document.documentElement
  el.classList.toggle('light', t === 'light')
  el.classList.toggle('dark', t === 'dark')
}

export function useTheme() {
  const [theme, setTheme] = useState<Theme>(DEFAULT_THEME)
  useEffect(() => { applyTheme(theme) }, [theme])
  const toggle = useCallback(() => setTheme((t) => (t === 'dark' ? 'light' : 'dark')), [])
  return { theme, toggle }
}
