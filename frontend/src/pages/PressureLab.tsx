import { useQuery } from '@tanstack/react-query'
import { useMemo, useState } from 'react'
import { useSearchParams } from 'react-router-dom'
import {
  Area, Bar, BarChart, CartesianGrid, Cell, ComposedChart, Legend, Line, ReferenceLine, ResponsiveContainer, Tooltip, XAxis, YAxis,
} from 'recharts'
import { Badge, Card, CardBody, CardHeader, ErrorState, Select, Skeleton } from '@/components/ui/primitives'
import { ChartTooltip, PageHeader } from '@/components/widgets'
import { api, type Ball } from '@/lib/api'
import { cn, fmt, fmtInt, PRESSURE_COLORS } from '@/lib/utils'

const CATS = ['Low', 'Moderate', 'High', 'Extreme']

function MatchCurve({ matchId }: { matchId: number }) {
  const q = useQuery({ queryKey: ['match', matchId], queryFn: () => api.match(matchId) })
  const data = useMemo(() => (q.data ?? []).map((b: Ball, i) => ({
    i, ...b, wp: b.innings === 1 ? (1 - b.wp_before) * 100 : b.wp_before * 100, label: `Inn ${b.innings} · ${b.overid}.${b.over_ball_num}`,
  })), [q.data])
  if (q.error) return <ErrorState error={q.error} />
  if (!q.data) return <Skeleton className="h-80" />
  const first = q.data[0]
  const split = data.find((d) => d.innings === 2)?.i
  const chasing = q.data.find((b) => b.innings === 2)?.batting_team ?? first.bowling_team
  return (
    <div className="min-w-0">
      <div className="mb-3 flex flex-wrap items-center gap-2 text-[13px] text-dim">
        <Badge tone="brand">{first.comp_name}</Badge><span>{first.match_date}</span>
        <span className="font-semibold text-ink">{first.batting_team} v {first.bowling_team}</span>
      </div>
      <div className="h-80">
        <ResponsiveContainer>
          <ComposedChart data={data} margin={{ left: -12, right: 8, top: 8 }}>
            <defs>
              <linearGradient id="pg" x1="0" y1="0" x2="0" y2="1"><stop offset="0%" stopColor="#f43f5e" stopOpacity={0.55} /><stop offset="100%" stopColor="#f43f5e" stopOpacity={0.02} /></linearGradient>
            </defs>
            <CartesianGrid vertical={false} />
            <XAxis dataKey="i" tickLine={false} axisLine={false} tickFormatter={(v) => (data[v]?.innings === 2 ? `${data[v].overid}*` : `${data[v]?.overid ?? ''}`)} interval={23} />
            <YAxis domain={[0, 100]} tickLine={false} axisLine={false} />
            {split !== undefined && <ReferenceLine x={split} stroke="#8b95b2" strokeDasharray="4 4" label={{ value: 'Chase begins', fill: '#8b95b2', fontSize: 11, position: 'insideTopRight' }} />}
            <ReferenceLine y={75} stroke="#f59e0b" strokeDasharray="2 4" />
            <Tooltip content={({ active, payload }) => {
              if (!active || !payload?.length) return null
              const d = payload[0].payload as (typeof data)[number]
              return (
                <div className="rounded-xl border border-line bg-panel/95 px-3 py-2 text-xs shadow-xl">
                  <div className="font-semibold text-ink">{d.label} · {d.batting_team} {d.runs_before}/{d.wkts_before}</div>
                  {d.innings === 2 && <div className="text-dim">Need {d.runs_needed} off {d.balls_left}</div>}
                  <div className="text-dim">{d.striker_name} v {d.bowler_name} → {d.team_wicket ? 'WICKET' : `${d.total_runs} run(s)`}</div>
                  <div className="mt-1 flex gap-3"><span style={{ color: PRESSURE_COLORS[d.pcat_bat] }}>Pressure {fmt(d.pressure_bat, 0)} ({d.pcat_bat})</span><span className="text-sky">{chasing} WP {fmt(d.wp, 0)}%</span></div>
                </div>
              )
            }} />
            <Legend />
            <Area dataKey="pressure_bat" name="Pressure score" stroke="#f43f5e" fill="url(#pg)" strokeWidth={1.2} isAnimationActive={false} />
            <Line dataKey="wp" name={`${chasing} win probability %`} stroke="#38bdf8" strokeWidth={2.2} dot={false} isAnimationActive={false} />
          </ComposedChart>
        </ResponsiveContainer>
      </div>
    </div>
  )
}

export default function PressureLab() {
  const [sp, setSp] = useSearchParams()
  const [competition, setCompetition] = useState('All')
  const [season, setSeason] = useState('All')
  const filters = useQuery({ queryKey: ['filters'], queryFn: api.filters })
  const s = season === 'All' ? null : Number(season)
  const pr = useQuery({ queryKey: ['pressure', competition, s], queryFn: () => api.pressure({ competition, season: s }) })
  const moments = useQuery({ queryKey: ['moments', competition, s, 15], queryFn: () => api.moments({ competition, season: s, limit: 15 }) })
  const selected = Number(sp.get('match')) || moments.data?.[0]?.match_id

  const mix = useMemo(() => {
    const rows: Record<string, number | string>[] = []
    for (const inn of [1, 2]) for (const ph of ['Powerplay', 'Middle', 'Death']) {
      const cells = (pr.data?.phase_mix ?? []).filter((x) => x.innings === inn && x.phase === ph)
      const tot = cells.reduce((a, b) => a + b.n, 0) || 1
      const r: Record<string, number | string> = { label: `${inn === 1 ? 'Setting' : 'Chasing'} · ${ph}` }
      CATS.forEach((c) => { r[c] = (100 * (cells.find((x) => x.category === c)?.n ?? 0)) / tot })
      rows.push(r)
    }
    return rows
  }, [pr.data])

  const chase = useMemo(() => CATS.map((c) => {
    const ok = pr.data?.chase.find((x) => x.outcome === 'Successful chase' && x.category === c)
    const bad = pr.data?.chase.find((x) => x.outcome === 'Failed chase' && x.category === c)
    return { category: c, success: ok?.runs_per_ball, failed: bad?.runs_per_ball, sw: ok?.wicket_pct, fw: bad?.wicket_pct }
  }), [pr.data])

  const hist = useMemo(() => {
    const b = new Map<number, { bucket: number; first?: number; second?: number }>()
    ;(pr.data?.histogram ?? []).forEach((h) => {
      const r = b.get(h.bucket) ?? { bucket: h.bucket }
      if (h.innings === 1) r.first = h.runs_per_ball; else r.second = h.runs_per_ball
      b.set(h.bucket, r)
    })
    return Array.from(b.values()).sort((a, c) => a.bucket - c.bucket)
  }, [pr.data])

  return (
    <div className="space-y-6">
      <PageHeader eyebrow="Pressure Lab" title="How the pressure model behaves"
        desc="Pressure = 0.55 × leverage (win-probability swing between a boundary and a wicket) + 0.30 × closeness × match progress + 0.15 × stress (required-rate difficulty, recent collapse), ×1.15 in knockouts, then ranked within innings to give 0–100."
        actions={<div className="flex gap-2">
          <Select label="Competition" value={competition} onChange={setCompetition} options={[{ value: 'All', label: 'All' }, { value: 'IPL', label: 'IPL' }, { value: 'T20I', label: 'T20I' }]} />
          <Select label="Season" value={season} onChange={setSeason} options={[{ value: 'All', label: 'All' }, ...(filters.data?.seasons ?? []).map((x) => ({ value: String(x), label: String(x) }))]} />
        </div>} />

      <div className="grid grid-cols-2 gap-3 lg:grid-cols-4">
        {(pr.data?.categories ?? []).map((c) => (
          <Card key={c.category} className="p-4">
            <div className="flex items-center justify-between">
              <span className="text-sm font-semibold" style={{ color: PRESSURE_COLORS[c.category] }}>{c.category}</span>
              <span className="tabular text-[11.5px] text-faint">{fmtInt(c.deliveries)} balls</span>
            </div>
            <div className="mt-3 grid grid-cols-3 gap-2 text-center">
              <div><div className="tabular text-lg font-bold text-ink">{fmt(c.runs_per_ball, 2)}</div><div className="text-[10.5px] text-faint">runs/ball</div></div>
              <div><div className="tabular text-lg font-bold text-ink">{fmt(c.wicket_pct, 1)}%</div><div className="text-[10.5px] text-faint">wicket</div></div>
              <div><div className="tabular text-lg font-bold text-ink">{fmt(c.close_pct, 0)}%</div><div className="text-[10.5px] text-faint">close games</div></div>
            </div>
          </Card>
        ))}
        {!pr.data && Array.from({ length: 4 }).map((_, i) => <Skeleton key={i} className="h-28" />)}
      </div>

      <Card>
        <CardHeader title="Match pressure trace" subtitle="Pick one of the highest-pressure matches. Pressure (red) rises when the game is live and late, and collapses once the result is clear." />
        <CardBody className="grid gap-5 xl:grid-cols-[300px_1fr]">
          <div className="max-h-[22rem] space-y-1.5 overflow-auto pr-1 scroll-thin">
            {(moments.data ?? []).map((m) => (
              <button key={m.match_id} onClick={() => setSp({ match: String(m.match_id) })}
                className={cn('w-full rounded-xl border px-3 py-2 text-left text-[12.5px] transition-colors',
                  selected === m.match_id ? 'border-brand/50 bg-brand/10' : 'border-line bg-panel-2/40 hover:bg-panel-2')}>
                <div className="font-semibold text-ink">{m.batting_team} v {m.bowling_team}</div>
                <div className="text-faint">{m.match_date} · {m.competition} · peak at {m.overid}.{m.over_ball_num}</div>
              </button>
            ))}
          </div>
          {selected ? <MatchCurve matchId={selected} /> : <Skeleton className="h-80" />}
        </CardBody>
      </Card>

      <div className="grid gap-6 xl:grid-cols-2">
        <Card>
          <CardHeader title="Pressure categories by innings phase" subtitle="Share of deliveries in each category. No phase is automatically high pressure." />
          <CardBody className="h-80">
            <ResponsiveContainer>
              <BarChart data={mix} layout="vertical" margin={{ left: 40, right: 12 }}>
                <CartesianGrid horizontal={false} />
                <XAxis type="number" domain={[0, 100]} ticks={[0, 25, 50, 75, 100]} unit="%" tickLine={false} axisLine={false} />
                <YAxis type="category" dataKey="label" width={130} tickLine={false} axisLine={false} />
                <Tooltip content={<ChartTooltip formatter={(v) => `${v.toFixed(1)}%`} />} />
                <Legend />
                {CATS.map((c) => <Bar key={c} dataKey={c} stackId="a" fill={PRESSURE_COLORS[c]} />)}
              </BarChart>
            </ResponsiveContainer>
          </CardBody>
        </Card>
        <Card>
          <CardHeader title="Successful vs failed chases" subtitle="Runs per ball by pressure category. Winning chases keep scoring when pressure peaks." />
          <CardBody className="h-80">
            <ResponsiveContainer>
              <BarChart data={chase} margin={{ left: -12, right: 8, top: 8 }}>
                <CartesianGrid vertical={false} />
                <XAxis dataKey="category" tickLine={false} axisLine={false} />
                <YAxis tickLine={false} axisLine={false} />
                <Tooltip content={<ChartTooltip formatter={(v) => v.toFixed(2)} />} />
                <Legend />
                <Bar dataKey="success" name="Successful chase" fill="#34d399" radius={[4, 4, 0, 0]} />
                <Bar dataKey="failed" name="Failed chase" fill="#f43f5e" radius={[4, 4, 0, 0]} />
              </BarChart>
            </ResponsiveContainer>
          </CardBody>
        </Card>
      </div>

      <div className="grid gap-6 xl:grid-cols-2">
        <Card>
          <CardHeader title="Scoring falls as pressure rises" subtitle="League runs per ball by pressure score (5-point buckets)" />
          <CardBody className="h-72">
            <ResponsiveContainer>
              <ComposedChart data={hist} margin={{ left: -12, right: 8, top: 8 }}>
                <CartesianGrid vertical={false} />
                <XAxis dataKey="bucket" tickLine={false} axisLine={false} />
                <YAxis tickLine={false} axisLine={false} domain={['auto', 'auto']} />
                <Tooltip content={<ChartTooltip formatter={(v) => v.toFixed(3)} />} />
                <Legend />
                <Line dataKey="first" name="Setting" stroke="#38bdf8" strokeWidth={2} dot={false} />
                <Line dataKey="second" name="Chasing" stroke="#f43f5e" strokeWidth={2} dot={false} />
              </ComposedChart>
            </ResponsiveContainer>
          </CardBody>
        </Card>
        <Card>
          <CardHeader title="Average pressure by over" subtitle="Mean pressure score and leverage through the innings" />
          <CardBody className="h-72">
            <ResponsiveContainer>
              <ComposedChart data={(pr.data?.by_over ?? []).filter((x) => x.innings === 2).map((x) => ({ ...x, first: pr.data!.by_over.find((y) => y.innings === 1 && y.over === x.over)?.mean_pressure }))} margin={{ left: -12, right: 8, top: 8 }}>
                <CartesianGrid vertical={false} />
                <XAxis dataKey="over" tickLine={false} axisLine={false} />
                <YAxis tickLine={false} axisLine={false} domain={[30, 70]} />
                <Tooltip content={<ChartTooltip formatter={(v) => v.toFixed(1)} />} />
                <Legend />
                <Bar dataKey="mean_pressure" name="Chasing" radius={[3, 3, 0, 0]}>
                  {(pr.data?.by_over ?? []).filter((x) => x.innings === 2).map((x) => <Cell key={x.over} fill={x.over >= 16 ? '#f43f5e' : x.over <= 6 ? '#38bdf8' : '#a78bfa'} />)}
                </Bar>
                <Line dataKey="first" name="Setting" stroke="#fbbf24" strokeWidth={2} dot={false} />
              </ComposedChart>
            </ResponsiveContainer>
          </CardBody>
        </Card>
      </div>
    </div>
  )
}
