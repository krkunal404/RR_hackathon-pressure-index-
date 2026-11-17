import { useQuery } from '@tanstack/react-query'
import type { ColumnDef } from '@tanstack/react-table'
import { Download, Info } from 'lucide-react'
import { useMemo, useState } from 'react'
import { useNavigate, useParams } from 'react-router-dom'
import { DataTable } from '@/components/DataTable'
import { LeaderboardList } from '@/components/Leaderboard'
import { Badge, Button, Card, CardHeader, ErrorState, Input, Select, Skeleton, Tabs } from '@/components/ui/primitives'
import { Delta, PageHeader, RankMedal, RatingBar, ReliabilityPill } from '@/components/widgets'
import { api, num, roleMeta, type PlayerRow, type Role } from '@/lib/api'
import { fmt, fmtInt, pct } from '@/lib/utils'

function toCsv(rows: PlayerRow[], cols: string[]) {
  const esc = (v: unknown) => `"${String(v ?? '').replace(/"/g, '""')}"`
  return [cols.join(','), ...rows.map((r) => cols.map((c) => esc(r[c])).join(','))].join('\n')
}

export default function Rankings() {
  const { role = 'batters' } = useParams<{ role: Role }>()
  const r = (role === 'bowlers' ? 'bowlers' : 'batters') as Role
  const m = roleMeta[r]
  const nav = useNavigate()
  const [competition, setCompetition] = useState('All')
  const [team, setTeam] = useState('All')
  const [search, setSearch] = useState('')
  const [eligibleOnly, setEligibleOnly] = useState('yes')

  const filters = useQuery({ queryKey: ['filters'], queryFn: api.filters })
  const q = useQuery({
    queryKey: ['rankings', r, competition, team, search, eligibleOnly],
    queryFn: () => api.rankings(r, { competition, team: team === 'All' ? undefined : team, search, eligible_only: eligibleOnly === 'yes' }),
  })
  const rows = useMemo(() => q.data?.rows ?? [], [q.data])
  const color = r === 'batters' ? '#f43f5e' : '#38bdf8'
  const dp = r === 'batters' ? 1 : 2
  const isAll = competition === 'All'

  const columns = useMemo<ColumnDef<PlayerRow, unknown>[]>(() => [
    { id: 'rank', header: '#', accessorFn: (x) => x.rank ?? 9999, cell: (c) => <RankMedal rank={c.row.original.rank} /> },
    {
      id: 'name', header: m.single, accessorKey: 'name',
      cell: (c) => (
        <div className="min-w-[160px]">
          <div className="font-semibold text-ink">{c.row.original.name}</div>
          <div className="text-[11.5px] text-faint">{c.row.original.team} · {c.row.original.competition}{c.row.original.pace_or_spin ? ` · ${c.row.original.pace_or_spin}` : ''}</div>
        </div>
      ),
    },
    {
      id: 'rating', header: isAll ? m.index : `${m.index} (${competition})`, accessorFn: (x) => num(x, 'rating') ?? -1,
      cell: (c) => <div className="w-48"><RatingBar value={num(c.row.original, 'rating')} lo={isAll ? num(c.row.original, `${m.index}_lo`) : null} hi={isAll ? num(c.row.original, `${m.index}_hi`) : null} color={color} /></div>,
    },
    { id: 'rel', header: 'Reliability', accessorFn: (x) => x.reliability ?? 0, cell: (c) => <ReliabilityPill value={c.row.original.reliability} /> },
    { id: 'ptop', header: 'P(top10)', accessorFn: (x) => x.p_top10 ?? 0, meta: { align: 'right' }, cell: (c) => pct(c.row.original.p_top10) },
    { id: 'balls', header: 'Pressure balls', accessorFn: (x) => num(x, m.balls) ?? 0, meta: { align: 'right' }, cell: (c) => fmtInt(num(c.row.original, m.balls)) },
    { id: 'primary', header: m.primaryLabel, accessorFn: (x) => num(x, m.primary) ?? 0, meta: { align: 'right' }, cell: (c) => <b className="text-ink">{fmt(num(c.row.original, m.primary), dp)}</b> },
    { id: 'base', header: m.baselineLabel, accessorFn: (x) => num(x, m.baseline) ?? 0, meta: { align: 'right' }, cell: (c) => fmt(num(c.row.original, m.baseline), dp) },
    {
      id: 'chg', header: 'Δ vs own', accessorFn: (x) => num(x, r === 'batters' ? 'sr_change' : 'econ_change') ?? 0, meta: { align: 'right' },
      cell: (c) => <Delta value={num(c.row.original, r === 'batters' ? 'sr_change' : 'econ_change')} digits={dp} invert={r === 'bowlers'} />,
    },
    {
      id: 'vsexp', header: 'Δ vs context', accessorFn: (x) => num(x, r === 'batters' ? 'p_sr_vs_expected' : 'p_econ_vs_expected') ?? 0, meta: { align: 'right' },
      cell: (c) => <Delta value={num(c.row.original, r === 'batters' ? 'p_sr_vs_expected' : 'p_econ_vs_expected')} digits={dp} invert={r === 'bowlers'} />,
    },
    { id: 'pm', header: 'Pressure matches', accessorKey: 'pressure_matches', meta: { align: 'right' } },
  ], [m, r, color, dp, isAll, competition])

  const download = () => {
    const cols = ['rank', 'player_id', 'name', 'team', 'competition', m.index, `${m.index}_lo`, `${m.index}_hi`, 'reliability', 'p_top10', m.balls, m.primary, m.baseline, 'pressure_matches', 'justification']
    const blob = new Blob([toCsv(rows, cols)], { type: 'text/csv' })
    const a = document.createElement('a')
    a.href = URL.createObjectURL(blob)
    a.download = `${r}_pressure_rankings.csv`
    a.click()
  }

  return (
    <div className="space-y-6">
      <PageHeader
        eyebrow="Rankings"
        title={`${m.label} under pressure`}
        desc={r === 'batters'
          ? 'BPPI combines runs above context-expected, dismissals avoided, win probability added, uplift vs own baseline and match consistency, all measured on High/Extreme pressure balls and shrunk for sample size.'
          : 'BoPPI combines runs saved vs context-expected, wickets above expected, win probability added, uplift vs own baseline and spell consistency, all measured on High/Extreme pressure deliveries and shrunk for sample size.'}
        actions={<Tabs value={r} onChange={(v) => nav(`/rankings/${v}`)} items={[{ value: 'batters', label: 'Batters' }, { value: 'bowlers', label: 'Bowlers' }]} />}
      />

      <Card className="p-4">
        <div className="grid grid-cols-2 gap-3 md:grid-cols-5">
          <Select label="Competition" testId="filter-competition" value={competition} onChange={setCompetition}
            options={[{ value: 'All', label: 'Combined (official)' }, { value: 'IPL', label: 'IPL only' }, { value: 'T20I', label: 'T20I only' }]} />
          <Select label="Team" value={team} onChange={setTeam}
            options={[{ value: 'All', label: 'All teams' }, ...(filters.data?.teams ?? []).map((t) => ({ value: t, label: t }))]} />
          <Select label="Eligibility" value={eligibleOnly} onChange={setEligibleOnly}
            options={[{ value: 'yes', label: 'Eligible only' }, { value: 'no', label: 'Include below sample bar' }]} />
          <label className="col-span-2 flex flex-col gap-1">
            <span className="text-[10.5px] font-semibold uppercase tracking-wider text-faint">Player</span>
            <div className="flex gap-2">
              <Input placeholder="Filter by name…" value={search} onChange={(e) => setSearch(e.target.value)} aria-label="Filter by name" />
              <Button variant="outline" onClick={download} title="Download CSV"><Download className="h-4 w-4" /></Button>
            </div>
          </label>
        </div>
        {!isAll && (
          <p className="mt-3 flex items-center gap-2 text-[12px] text-dim"><Info className="h-3.5 w-3.5 text-sky" />
            Competition-only ratings are re-estimated within {competition} with a lower bar (100 pressure balls, 10 matches). The official submission uses the combined rating.</p>
        )}
      </Card>

      {isAll && team === 'All' && !search && eligibleOnly === 'yes' && (
        <Card>
          <CardHeader title="RR auction top 10" subtitle="IPL 2027 auction pool (no Pakistan players, active in 2025-26) · reliability and P(top10) are shown separately from the rating"
            action={<Badge tone="brand">{q.data?.count ?? 0} eligible</Badge>} />
          <div className="mt-3">{q.data ? <LeaderboardList role={r} rows={rows.slice(0, 10)} /> : <Skeleton className="m-5 h-96" />}</div>
        </Card>
      )}

      <Card>
        <CardHeader title="Full ranking table" subtitle="Sortable · click a player for the full profile" />
        <div className="mt-3">
          {q.error ? <div className="p-5"><ErrorState error={q.error} /></div>
            : q.data ? <DataTable testId="rankings-table" data={rows} columns={columns} onRowClick={(x) => nav(`/players/${r}/${x.player_id}`)} />
              : <div className="space-y-2 p-5">{Array.from({ length: 8 }).map((_, i) => <Skeleton key={i} className="h-10" />)}</div>}
        </div>
      </Card>
    </div>
  )
}
