export type Role = 'batters' | 'bowlers'

/** A rated player row. Batters carry BPPI / p_sr…, bowlers BoPPI / p_econ… */
export interface PlayerRow {
  player_id: number
  name: string
  team: string | null
  competition: string | null
  style?: string | null
  pace_or_spin?: string | null
  rank: number | null
  eligible: boolean
  reliability: number | null
  p_top10: number | null
  rank_lo: number | null
  rank_hi: number | null
  n: number
  matches: number
  pressure_matches: number
  justification: string
  rating?: number | null
  /** IPL 2027 auction tags (see src/auction.py) */
  auction_status?: string | null
  player_type?: string | null
  nationality?: string | null
  exclusion?: string | null
  [key: string]: unknown
}

export interface Overview {
  matches: number
  ipl_matches: number
  t20i_matches: number
  deliveries: number
  players: number
  batters: number
  bowlers: number
  pressure_deliveries: number
  high_deliveries: number
  extreme_deliveries: number
  eligible_batters: number
  eligible_bowlers: number
  seasons: number[]
  generated_at: string
}

export interface Filters {
  competitions: string[]
  seasons: number[]
  teams: string[]
  pressure_categories: string[]
  phases: string[]
}

export interface Split {
  k: string
  balls: number
  runs: number
  outs?: number
  wkts?: number
  sr?: number
  exp_sr?: number
  econ?: number
  exp_econ?: number
  dot_pct: number
  boundary_pct: number
  wpa: number
}

export interface Component {
  component: string
  weight: number
  z: number | null
  shrunk: number | null
  raw: number | null
  contribution: number
  signal_share: number
}

export interface MatchLog {
  match_id: number
  match_date: string
  season_year: number
  competition: string
  team: string
  opponent: string
  innings: number
  runs: number
  wpa: number
  mean_pressure: number
  close_match: boolean
  won: number | null
  pressure_runs: number
  pressure_exp_runs: number
  balls?: number
  out?: boolean
  pressure_balls?: number
  pressure_outs?: number
  legal_balls?: number
  wkts?: number
  pressure_legal_balls?: number
  pressure_wkts?: number
}

export interface PlayerProfile {
  role: Role
  player: PlayerRow
  components: Component[]
  matches: MatchLog[]
  by_category: Split[]
  by_phase: Split[]
  by_chase: Split[]
  by_season: Split[]
  competition_split: Split[]
}

export interface PressureSummary {
  categories: { category: string; deliveries: number; runs_per_ball: number; wicket_pct: number; dot_pct: number; boundary_pct: number; leverage: number; close_pct: number }[]
  phase_mix: { innings: number; phase: string; category: string; n: number }[]
  histogram: { innings: number; bucket: number; n: number; runs_per_ball: number; wicket_pct: number }[]
  by_over: { innings: number; over: number; mean_pressure: number; leverage: number; pressure_share: number }[]
  chase: { outcome: string; category: string; n: number; runs_per_ball: number; wicket_pct: number }[]
}

export interface Moment {
  match_id: number
  match_date: string
  competition: string
  comp_name: string
  batting_team: string
  bowling_team: string
  innings: number
  overid: number
  over_ball_num: number
  runs_needed: number | null
  balls_left: number
  wkts_before: number
  wp_before: number
  leverage: number
  striker_name: string
  bowler_name: string
  bat_runs: number
  team_wicket: boolean
  wpa: number
}

export interface Ball {
  innings: number
  overid: number
  over_ball_num: number
  batting_team: string
  bowling_team: string
  striker_name: string
  bowler_name: string
  runs_before: number
  wkts_before: number
  target: number | null
  runs_needed: number | null
  balls_left: number
  wp_before: number
  wp_after: number
  wpa: number
  leverage: number
  pressure_bat: number
  pcat_bat: string
  bat_runs: number
  total_runs: number
  team_wicket: boolean
  match_date: string
  comp_name: string
}

export type ExplorerRow = Record<string, number | string | null> & { player_id: number; name: string }

// eslint-disable-next-line @typescript-eslint/no-explicit-any
export type Json = any

const BASE = import.meta.env.VITE_API_BASE ?? ''

export async function get<T>(path: string, params?: Record<string, string | number | boolean | null | undefined>): Promise<T> {
  const qs = new URLSearchParams()
  Object.entries(params ?? {}).forEach(([k, v]) => {
    if (v !== undefined && v !== null && v !== '' && v !== 'All') qs.set(k, String(v))
  })
  const url = `${BASE}${path}${qs.toString() ? `?${qs}` : ''}`
  const res = await fetch(url)
  if (!res.ok) throw new Error(`${res.status} ${res.statusText} – ${url}`)
  return res.json() as Promise<T>
}

export const api = {
  overview: () => get<Overview>('/api/overview'),
  filters: () => get<Filters>('/api/filters'),
  rankings: (role: Role, p: { competition?: string; team?: string; search?: string; eligible_only?: boolean }) =>
    get<{ rows: PlayerRow[]; count: number }>(`/api/rankings/${role}`, p),
  top10: (role: Role) => get<PlayerRow[]>(`/api/top10/${role}`),
  player: (role: Role, id: number, p: { competition?: string; season?: number | null }) =>
    get<PlayerProfile>(`/api/players/${role}/${id}`, p),
  distribution: (role: Role, id: number) => get<{ bucket: number; n: number }[]>(`/api/players/${role}/${id}/distribution`),
  search: (q: string) => get<{ player_id: number; name: string; team: string; role: Role; rating: number | null; eligible: boolean }[]>('/api/search', { q }),
  explorer: (role: Role, p: Record<string, string | number | null | undefined>) => get<ExplorerRow[]>(`/api/explorer/${role}`, p),
  pressure: (p: { competition?: string; season?: number | null }) => get<PressureSummary>('/api/pressure/summary', p),
  moments: (p: { competition?: string; season?: number | null; limit?: number }) => get<Moment[]>('/api/pressure/moments', p),
  match: (id: number) => get<Ball[]>(`/api/matches/${id}`),
  competition: (role: Role) => get<{ players: Json[]; by_category: Json[] }>(`/api/competition/${role}`),
  methodology: () => get<Json>('/api/methodology'),
  validation: () => get<Json>('/api/validation'),
}

/** Role-aware accessors so pages can treat batters and bowlers uniformly. */
export const roleMeta = {
  batters: {
    label: 'Batters', single: 'Batter', index: 'BPPI', primary: 'p_sr', primaryLabel: 'Pressure SR', baseline: 'n_sr',
    baselineLabel: 'Normal SR', balls: 'p_balls', higherIsBetter: true,
  },
  bowlers: {
    label: 'Bowlers', single: 'Bowler', index: 'BoPPI', primary: 'p_econ', primaryLabel: 'Pressure Econ', baseline: 'n_econ',
    baselineLabel: 'Normal Econ', balls: 'p_legal_balls', higherIsBetter: false,
  },
} as const

export const num = (row: Record<string, unknown>, key: string): number | null => {
  const v = row[key]
  return typeof v === 'number' && !Number.isNaN(v) ? v : null
}
