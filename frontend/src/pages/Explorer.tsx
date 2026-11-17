import { useQuery } from '@tanstack/react-query'
import type { ColumnDef } from '@tanstack/react-table'
import { Info } from 'lucide-react'
import { useMemo, useState } from 'react'
import { useNavigate } from 'react-router-dom'
import { CartesianGrid, ResponsiveContainer, Scatter, ScatterChart, Tooltip, XAxis, YAxis, ZAxis, ReferenceLine } from 'recharts'
import { DataTable } from '@/components/DataTable'
import { Card, CardBody, CardHeader, ErrorState, Select, Skeleton, Tabs } from '@/components/ui/primitives'
import { Delta, PageHeader } from '@/components/widgets'
import { api, type ExplorerRow, type Role } from '@/lib/api'
import { fmt, fmtInt } from '@/lib/utils'

export default function Explorer() {
  const nav = useNavigate()
  const [role, setRole] = useState<Role>('batters')
  const [competition, setCompetition] = useState('All')
  const [season, setSeason] = useState('All')
  const [team, setTeam] = useState('All')
  const [category, setCategory] = useState('High+Extreme')
  const [phase, setPhase] = useState('All')
  const [minBalls, setMinBalls] = useState('60')
  const filters = useQuery({ queryKey: ['filters'], queryFn: api.filters })
  const params = { competition, season: season === 'All' ? null : season, team: team === 'All' ? null : team, pressure_category: category, phase: phase === 'All' ? null : phase, min_balls: minBalls, limit: 300 }
  const q = useQuery({ queryKey: ['explorer', role, params], queryFn: () => api.explorer(role, params) })
  const bat = role === 'batters'
  const rows = useMemo(() => q.data ?? [], [q.data])

  const columns = useMemo<ColumnDef<ExplorerRow, unknown>[]>(() => {
    const n = (k: string, d = 1) => (c: { row: { original: ExplorerRow } }) => fmt(c.row.original[k] as number, d)
    const base: ColumnDef<ExplorerRow, unknown>[] = [
      { id: 'i', header: '#', cell: (c) => <span className="text-faint">{c.row.index + 1}</span>, enableSorting: false },
      { accessorKey: 'name', header: 'Player', cell: (c) => <span className="font-semibold text-ink">{c.row.original.name}</span> },
      { accessorKey: 'matches', header: 'Matches', meta: { align: 'right' } },
      { accessorKey: 'balls', header: bat ? 'Balls' : 'Legal balls', meta: { align: 'right' }, cell: (c) => fmtInt(c.row.original.balls as number) },
      { accessorKey: 'runs', header: 'Runs', meta: { align: 'right' }, cell: (c) => fmtInt(c.row.original.runs as number) },
    ]
    return bat ? [...base,
      { accessorKey: 'outs', header: 'Outs', meta: { align: 'right' }, cell: (c) => fmtInt(c.row.original.outs as number) },
      { accessorKey: 'sr', header: 'SR', meta: { align: 'right' }, cell: (c) => <b className="text-ink">{fmt(c.row.original.sr as number)}</b> },
      { accessorKey: 'exp_sr', header: 'Context SR', meta: { align: 'right' }, cell: n('exp_sr') },
      { accessorKey: 'sr_vs_exp', header: 'Δ vs context', meta: { align: 'right' }, cell: (c) => <Delta value={c.row.original.sr_vs_exp as number} /> },
      { accessorKey: 'avg', header: 'Avg', meta: { align: 'right' }, cell: n('avg') },
      { accessorKey: 'boundary_pct', header: '4s+6s %', meta: { align: 'right' }, cell: n('boundary_pct') },
      { accessorKey: 'dot_pct', header: 'Dot %', meta: { align: 'right' }, cell: n('dot_pct') },
      { accessorKey: 'wpa', header: 'WPA (pts)', meta: { align: 'right' }, cell: (c) => <Delta value={(c.row.original.wpa as number) * 100} /> },
    ] : [...base,
      { accessorKey: 'wkts', header: 'Wkts', meta: { align: 'right' }, cell: (c) => fmtInt(c.row.original.wkts as number) },
      { accessorKey: 'econ', header: 'Econ', meta: { align: 'right' }, cell: (c) => <b className="text-ink">{fmt(c.row.original.econ as number, 2)}</b> },
      { accessorKey: 'exp_econ', header: 'Context econ', meta: { align: 'right' }, cell: n('exp_econ', 2) },
      { accessorKey: 'econ_saved', header: 'Saved / over', meta: { align: 'right' }, cell: (c) => <Delta value={c.row.original.econ_saved as number} digits={2} /> },
      { accessorKey: 'dot_pct', header: 'Dot %', meta: { align: 'right' }, cell: n('dot_pct') },
      { accessorKey: 'boundary_pct', header: 'Bdry %', meta: { align: 'right' }, cell: n('boundary_pct') },
      { accessorKey: 'wpa', header: 'WPA (pts)', meta: { align: 'right' }, cell: (c) => <Delta value={(c.row.original.wpa as number) * 100} /> },
    ]
  }, [bat])

  const xKey = bat ? 'exp_sr' : 'exp_econ'
  const yKey = bat ? 'sr' : 'econ'

  return (
    <div className="space-y-6">
      <PageHeader eyebrow="Explorer" title="Slice pressure performance any way"
        desc="Live aggregates straight from the delivery-level DuckDB store. Pick a competition, season, team, pressure category and phase. These are descriptive context-adjusted numbers, not the shrunk official ratings."
        actions={<Tabs value={role} onChange={setRole} items={[{ value: 'batters', label: 'Batting' }, { value: 'bowlers', label: 'Bowling' }]} />} />
      <Card className="p-4">
        <div className="grid grid-cols-2 gap-3 md:grid-cols-6">
          <Select label="Competition" testId="explorer-competition" value={competition} onChange={setCompetition} options={[{ value: 'All', label: 'All' }, { value: 'IPL', label: 'IPL' }, { value: 'T20I', label: 'T20I' }]} />
          <Select label="Season" value={season} onChange={setSeason} options={[{ value: 'All', label: 'All seasons' }, ...(filters.data?.seasons ?? []).map((s) => ({ value: String(s), label: String(s) }))]} />
          <Select label={bat ? 'Batting team' : 'Bowling team'} value={team} onChange={setTeam} options={[{ value: 'All', label: 'All teams' }, ...(filters.data?.teams ?? []).map((t) => ({ value: t, label: t }))]} />
          <Select label="Pressure category" testId="explorer-category" value={category} onChange={setCategory} options={[{ value: 'High+Extreme', label: 'High + Extreme' }, { value: 'Extreme', label: 'Extreme' }, { value: 'High', label: 'High' }, { value: 'Moderate', label: 'Moderate' }, { value: 'Low', label: 'Low' }, { value: 'All', label: 'All balls' }]} />
          <Select label="Phase" value={phase} onChange={setPhase} options={[{ value: 'All', label: 'All phases' }, { value: 'Powerplay', label: 'Powerplay (1-6)' }, { value: 'Middle', label: 'Middle (7-15)' }, { value: 'Death', label: 'Death (16-20)' }]} />
          <Select label="Min balls" value={minBalls} onChange={setMinBalls} options={['20', '40', '60', '100', '150', '250'].map((v) => ({ value: v, label: v }))} />
        </div>
      </Card>

      <Card>
        <CardHeader title={bat ? 'Strike rate vs what the situation demanded' : 'Economy vs what the situation demanded'}
          subtitle={bat ? 'Above the diagonal = scoring faster than an average batter in the same contexts. Bubble size = balls.' : 'Below the diagonal = conceding less than an average bowler in the same contexts. Bubble size = balls.'} />
        <CardBody className="h-80">
          {q.data ? (
            <ResponsiveContainer>
              <ScatterChart margin={{ left: -6, right: 16, top: 8 }}>
                <CartesianGrid />
                <XAxis type="number" dataKey={xKey} name="Context" domain={['auto', 'auto']} tickLine={false} axisLine={false} label={{ value: bat ? 'Context-expected SR' : 'Context-expected economy', position: 'insideBottom', offset: -4, fill: '#5b6585', fontSize: 11 }} />
                <YAxis type="number" dataKey={yKey} name="Actual" domain={['auto', 'auto']} tickLine={false} axisLine={false} />
                <ZAxis type="number" dataKey="balls" range={[50, 500]} />
                <ReferenceLine segment={bat ? [{ x: 100, y: 100 }, { x: 200, y: 200 }] : [{ x: 5, y: 5 }, { x: 13, y: 13 }]} stroke="#475569" strokeDasharray="4 4" ifOverflow="hidden" />
                <Tooltip cursor={{ strokeDasharray: '3 3' }} content={({ active, payload }) => {
                  if (!active || !payload?.length) return null
                  const d = payload[0].payload as ExplorerRow
                  return <div className="rounded-xl border border-line bg-panel/95 px-3 py-2 text-xs shadow-xl"><div className="font-semibold text-ink">{d.name}</div>
                    <div className="text-dim">{fmtInt(d.balls as number)} balls · {bat ? `SR ${fmt(d.sr as number)} vs ${fmt(d.exp_sr as number)}` : `econ ${fmt(d.econ as number, 2)} vs ${fmt(d.exp_econ as number, 2)}`}</div></div>
                }} />
                <Scatter data={rows} fill={bat ? '#f43f5e' : '#38bdf8'} fillOpacity={0.7} onClick={(d: { payload?: ExplorerRow }) => d.payload && nav(`/players/${role}/${d.payload.player_id}`)} />
              </ScatterChart>
            </ResponsiveContainer>
          ) : <Skeleton className="h-full" />}
        </CardBody>
      </Card>

      <Card>
        <CardHeader title={`${rows.length} players`} subtitle={bat ? 'Sorted by strike rate above context' : 'Sorted by runs saved per over vs context'} />
        <div className="mt-3">
          {q.error ? <div className="p-5"><ErrorState error={q.error} /></div> : q.data
            ? <DataTable testId="explorer-table" data={rows} columns={columns} dense onRowClick={(x) => nav(`/players/${role}/${x.player_id}`)} />
            : <div className="space-y-2 p-5">{Array.from({ length: 8 }).map((_, i) => <Skeleton key={i} className="h-9" />)}</div>}
        </div>
        <p className="flex items-center gap-2 px-5 pb-4 text-[11.5px] text-faint"><Info className="h-3.5 w-3.5" /> Raw slices can be noisy for small samples. Use the official rankings for shrunk, reliability-checked ratings.</p>
      </Card>
    </div>
  )
}
