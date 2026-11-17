import { useQuery } from '@tanstack/react-query'
import type { ColumnDef } from '@tanstack/react-table'
import { useMemo, useState } from 'react'
import { useNavigate } from 'react-router-dom'
import { Bar, BarChart, CartesianGrid, LabelList, Legend, ReferenceLine, ResponsiveContainer, Scatter, ScatterChart, Tooltip, XAxis, YAxis, ZAxis } from 'recharts'
import { DataTable } from '@/components/DataTable'
import { Card, CardBody, CardHeader, Skeleton, Tabs } from '@/components/ui/primitives'
import { ChartTooltip, PageHeader, ReliabilityPill } from '@/components/widgets'
import { api, type Json, type Role } from '@/lib/api'
import { fmt } from '@/lib/utils'

function spearman(a: number[], b: number[]) {
  const rank = (x: number[]) => { const s = x.map((v, i) => [v, i]).sort((p, q) => p[0] - q[0]); const r = Array(x.length); s.forEach(([, i], k) => { r[i] = k }); return r }
  const ra = rank(a), rb = rank(b), n = a.length
  if (n < 3) return NaN
  const d2 = ra.reduce((acc: number, v: number, i: number) => acc + (v - rb[i]) ** 2, 0)
  return 1 - (6 * d2) / (n * (n * n - 1))
}

export default function Competitions() {
  const nav = useNavigate()
  const [role, setRole] = useState<Role>('batters')
  const q = useQuery({ queryKey: ['competition', role], queryFn: () => api.competition(role) })
  const bat = role === 'batters'
  const players: Json[] = useMemo(() => q.data?.players ?? [], [q.data])
  const rho = spearman(players.map((p) => p.ipl), players.map((p) => p.t20i))

  const cats = useMemo(() => ['Low', 'Moderate', 'High', 'Extreme'].map((c) => {
    const f = (comp: string) => q.data?.by_category.find((x: Json) => x.competition === comp && x.category === c)?.value
    return { category: c, IPL: f('IPL'), T20I: f('T20I') }
  }), [q.data])

  const columns = useMemo<ColumnDef<Json, unknown>[]>(() => [
    { accessorKey: 'name', header: 'Player', cell: (c) => <div><div className="font-semibold text-ink">{c.row.original.name}</div><div className="text-[11.5px] text-faint">{c.row.original.team}</div></div> },
    { accessorKey: 'rating', header: 'Combined', meta: { align: 'right' }, cell: (c) => <b className="text-ink">{fmt(c.row.original.rating)}</b> },
    { accessorKey: 'ipl', header: 'IPL-only', meta: { align: 'right' }, cell: (c) => fmt(c.row.original.ipl) },
    { accessorKey: 't20i', header: 'T20I-only', meta: { align: 'right' }, cell: (c) => fmt(c.row.original.t20i) },
    { id: 'gap', header: 'Gap (IPL − T20I)', accessorFn: (x) => x.ipl - x.t20i, meta: { align: 'right' }, cell: (c) => { const g = c.row.original.ipl - c.row.original.t20i; return <span className={g >= 0 ? 'text-emerald' : 'text-brand-2'}>{g >= 0 ? '+' : ''}{g.toFixed(1)}</span> } },
    { accessorKey: 'rank_IPL', header: 'IPL rank', meta: { align: 'right' }, cell: (c) => fmt(c.row.original.rank_IPL, 0) },
    { accessorKey: 'rank_T20I', header: 'T20I rank', meta: { align: 'right' }, cell: (c) => fmt(c.row.original.rank_T20I, 0) },
    { accessorKey: 'reliability', header: 'Reliability', cell: (c) => <ReliabilityPill value={c.row.original.reliability} /> },
  ], [])

  return (
    <div className="space-y-6">
      <PageHeader eyebrow="Competition comparison" title="IPL vs T20I under pressure"
        desc="Ratings are re-estimated separately inside each competition (100 pressure balls, 10 matches). Players eligible in both show whether pressure performance travels. The official ranking combines both, weighting T20Is against Associate sides at 0.6."
        actions={<Tabs value={role} onChange={setRole} items={[{ value: 'batters', label: 'Batters' }, { value: 'bowlers', label: 'Bowlers' }]} />} />

      <div className="grid gap-6 xl:grid-cols-5">
        <Card className="xl:col-span-3">
          <CardHeader title={`Consistency across competitions · ${players.length} players eligible in both`} subtitle={`Spearman rank correlation ρ = ${Number.isNaN(rho) ? '–' : rho.toFixed(2)} · top-right = strong in both`} />
          <CardBody className="h-96">
            {q.data ? (
              <ResponsiveContainer>
                <ScatterChart margin={{ left: -6, right: 24, top: 8, bottom: 8 }}>
                  <CartesianGrid />
                  <XAxis type="number" dataKey="ipl" name="IPL" domain={[0, 100]} tickLine={false} axisLine={false} label={{ value: 'IPL-only rating', position: 'insideBottom', offset: -4, fill: '#5b6585', fontSize: 11 }} />
                  <YAxis type="number" dataKey="t20i" name="T20I" domain={[0, 100]} tickLine={false} axisLine={false} />
                  <ZAxis range={[110, 110]} />
                  <ReferenceLine segment={[{ x: 0, y: 0 }, { x: 100, y: 100 }]} stroke="#475569" strokeDasharray="4 4" />
                  <Tooltip content={({ active, payload }) => {
                    if (!active || !payload?.length) return null
                    const d = payload[0].payload
                    return <div className="rounded-xl border border-line bg-panel/95 px-3 py-2 text-xs shadow-xl"><div className="font-semibold text-ink">{d.name}</div><div className="text-dim">IPL {fmt(d.ipl)} · T20I {fmt(d.t20i)} · combined {fmt(d.rating)}</div></div>
                  }} />
                  <Scatter data={players} fill={bat ? '#f43f5e' : '#38bdf8'} fillOpacity={0.75} onClick={(d: { payload?: Json }) => d.payload && nav(`/players/${role}/${d.payload.player_id}`)}>
                    <LabelList dataKey="name" position="top" style={{ fill: '#8b95b2', fontSize: 9.5 }} formatter={(v: unknown) => String(v ?? '').split(' ').slice(-1)[0]} />
                  </Scatter>
                </ScatterChart>
              </ResponsiveContainer>
            ) : <Skeleton className="h-full" />}
          </CardBody>
        </Card>
        <Card className="xl:col-span-2">
          <CardHeader title={bat ? 'League strike rate by pressure' : 'League economy by pressure'} subtitle="How each competition plays as pressure rises" />
          <CardBody className="h-96">
            <ResponsiveContainer>
              <BarChart data={cats} margin={{ left: -12, right: 8, top: 8 }}>
                <CartesianGrid vertical={false} />
                <XAxis dataKey="category" tickLine={false} axisLine={false} />
                <YAxis tickLine={false} axisLine={false} domain={[0, 'auto']} />
                <Tooltip content={<ChartTooltip formatter={(v) => v.toFixed(bat ? 1 : 2)} />} />
                <Legend />
                <Bar dataKey="IPL" fill="#f43f5e" radius={[4, 4, 0, 0]} />
                <Bar dataKey="T20I" fill="#38bdf8" radius={[4, 4, 0, 0]} />
              </BarChart>
            </ResponsiveContainer>
          </CardBody>
        </Card>
      </div>

      <Card>
        <CardHeader title="Players rated in both competitions" subtitle="Sorted by combined rating" />
        <div className="mt-3">{q.data ? <DataTable data={players} columns={columns} dense onRowClick={(x) => nav(`/players/${role}/${x.player_id}`)} /> : <Skeleton className="m-5 h-64" />}</div>
      </Card>
    </div>
  )
}
