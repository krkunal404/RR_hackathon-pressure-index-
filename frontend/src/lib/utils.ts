import { clsx, type ClassValue } from 'clsx'
import { twMerge } from 'tailwind-merge'

export function cn(...inputs: ClassValue[]) {
  return twMerge(clsx(inputs))
}

export const fmt = (v: number | null | undefined, digits = 1) =>
  v === null || v === undefined || Number.isNaN(v) ? '–' : v.toFixed(digits)

export const fmtInt = (v: number | null | undefined) =>
  v === null || v === undefined || Number.isNaN(v) ? '–' : Math.round(v).toLocaleString()

export const pct = (v: number | null | undefined, digits = 0) =>
  v === null || v === undefined || Number.isNaN(v) ? '–' : `${(v * 100).toFixed(digits)}%`

export const signed = (v: number | null | undefined, digits = 1) =>
  v === null || v === undefined || Number.isNaN(v) ? '–' : `${v >= 0 ? '+' : ''}${v.toFixed(digits)}`

export const PRESSURE_COLORS: Record<string, string> = {
  Low: '#475569',
  Moderate: '#38bdf8',
  High: '#f59e0b',
  Extreme: '#f43f5e',
}

export const COMPONENT_COLORS: Record<string, string> = {
  scoring: '#f43f5e',
  economy: '#f43f5e',
  survival: '#fbbf24',
  wickets: '#fbbf24',
  impact: '#38bdf8',
  uplift: '#34d399',
  consistency: '#a78bfa',
}

export const COMPONENT_LABEL: Record<string, string> = {
  scoring: 'Scoring vs expected',
  economy: 'Runs saved vs expected',
  survival: 'Dismissals avoided',
  wickets: 'Wickets above expected',
  impact: 'Win probability added',
  uplift: 'Uplift vs own baseline',
  consistency: 'Match consistency',
}

export function reliabilityTier(r: number | null | undefined) {
  if (r === null || r === undefined) return { label: 'n/a', tone: 'muted' as const }
  if (r >= 45) return { label: 'High', tone: 'good' as const }
  if (r >= 25) return { label: 'Medium', tone: 'warn' as const }
  return { label: 'Low', tone: 'bad' as const }
}
