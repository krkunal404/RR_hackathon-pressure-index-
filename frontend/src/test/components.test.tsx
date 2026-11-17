import { QueryClient, QueryClientProvider } from '@tanstack/react-query'
import { render, screen, waitFor } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { MemoryRouter, Route, Routes } from 'react-router-dom'
import { afterEach, beforeAll, describe, expect, it, vi } from 'vitest'
import { LeaderboardList } from '@/components/Leaderboard'
import { Delta, RatingBar, ReliabilityPill } from '@/components/widgets'
import type { PlayerRow } from '@/lib/api'
import Rankings from '@/pages/Rankings'

beforeAll(() => {
  // Recharts / framer-motion need these in jsdom
  globalThis.ResizeObserver = class { observe() {} unobserve() {} disconnect() {} } as unknown as typeof ResizeObserver
  window.scrollTo = vi.fn() as unknown as typeof window.scrollTo
})
afterEach(() => vi.restoreAllMocks())

const row = (i: number, extra: Partial<PlayerRow> = {}): PlayerRow => ({
  player_id: i, name: `Player ${i}`, team: 'Team X', competition: 'IPL', rank: i, eligible: true, reliability: 40,
  p_top10: 0.5, rank_lo: 1, rank_hi: 20, n: 200, matches: 30, pressure_matches: 20, justification: 'because',
  BPPI: 100 - i * 5, BPPI_lo: 60, BPPI_hi: 110, p_sr: 150 + i, n_sr: 140, p_balls: 200, rating: 100 - i * 5, ...extra,
})

function wrap(ui: React.ReactNode, path = '/') {
  const qc = new QueryClient({ defaultOptions: { queries: { retry: false } } })
  return render(
    <QueryClientProvider client={qc}>
      <MemoryRouter initialEntries={[path]}>
        <Routes>
          <Route path="/rankings/:role" element={ui} />
          <Route path="*" element={ui} />
        </Routes>
      </MemoryRouter>
    </QueryClientProvider>,
  )
}

describe('widgets', () => {
  it('RatingBar shows the value', () => {
    render(<RatingBar value={72.34} lo={50} hi={90} />)
    expect(screen.getByText('72.3')).toBeInTheDocument()
  })
  it('ReliabilityPill labels certainty, not quality', () => {
    render(<ReliabilityPill value={12} />)
    expect(screen.getByText(/Low/)).toBeInTheDocument()
    expect(screen.getByTitle(/how certain the rating is/i)).toBeInTheDocument()
  })
  it('Delta inverts colour for economy', () => {
    const { container } = render(<Delta value={-1.2} invert digits={2} />)
    expect(container.textContent).toContain('1.20')
    expect(container.firstElementChild?.className).toContain('text-emerald')
  })
})

describe('LeaderboardList', () => {
  it('renders ranked players in order', () => {
    wrap(<LeaderboardList role="batters" rows={[row(1), row(2), row(3)]} />)
    const items = screen.getAllByRole('listitem')
    expect(items).toHaveLength(3)
    expect(items[0]).toHaveTextContent('Player 1')
    expect(items[2]).toHaveTextContent('Player 3')
  })
})

describe('Rankings page', () => {
  it('loads rankings from the API and filters by competition', async () => {
    const calls: string[] = []
    vi.spyOn(globalThis, 'fetch').mockImplementation(async (input) => {
      const url = String(input)
      calls.push(url)
      if (url.startsWith('/api/filters')) return new Response(JSON.stringify({ competitions: ['IPL', 'T20I'], seasons: [2024], teams: ['India'], pressure_categories: [], phases: [] }))
      return new Response(JSON.stringify({ role: 'batters', competition: 'All', count: 12, rows: Array.from({ length: 12 }, (_, i) => row(i + 1)) }))
    })
    wrap(<Rankings />, '/rankings/batters')
    await waitFor(() => expect(screen.getByTestId('rankings-table')).toBeInTheDocument())
    expect(screen.getAllByText('Player 1').length).toBeGreaterThan(0)
    expect(screen.getByText('RR auction top 10')).toBeInTheDocument()

    await userEvent.selectOptions(screen.getByTestId('filter-competition'), 'IPL')
    await waitFor(() => expect(calls.some((c) => c.includes('competition=IPL'))).toBe(true))
    expect(screen.queryByText('RR auction top 10')).not.toBeInTheDocument()
  })
})
