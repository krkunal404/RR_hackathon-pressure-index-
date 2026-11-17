import { useQuery } from '@tanstack/react-query'
import { ArrowLeft, Info } from 'lucide-react'
import { useMemo, useState } from 'react'
import { Link, useParams } from 'react-router-dom'
import {
  Bar, BarChart, CartesianGrid, Cell, ComposedChart, Legend, Line, LineChart, ReferenceLine, ResponsiveContainer, Tooltip, XAxis, YAxis,
} from 'recharts'
import { Badge, Card, CardBody, CardHeader, ErrorState, Select, Skeleton } from '@/components/ui/primitives'
import { ChartTooltip, Delta, RatingBar, ReliabilityPill } from '@/components/widgets'
import { api, num, roleMeta, type Role, type Split } from '@/lib/api'
import { COMPONENT_COLORS, COMPONENT_LABEL, fmt, fmtInt, pct, PRESSURE_COLORS, signed } from '@/lib/utils'

const CATS = ['Low', 'Moderate', 'High', 'Extreme']

function Metric({ label, value, sub }: { label: string; value: React.ReactNode; sub?: React.ReactNode }) {
  return (
    <div className="rounded-xl border border-line bg-panel-2/50 p-3">
      <div className="text-[10.5px] font-semibold uppercase tracking-wider text-faint">{label}</div>
      <div className="tabular mt-1 text-lg font-bold text-ink">{value}</div>
      {sub && <div className="text-[11.5px] text-dim">{sub}</div>}
    </div>
  )
}

export default function PlayerDetail() {
  const { role: rp = 'batters', id = '0' } = useParams()
  const role = (rp === 'bowlers' ? 'bowlers' : 'batters') as Role
  const pid = Number(id)
  const m = roleMeta[role]
  const bat = role === 'batters'
  const [competition, setCompetition] = useState('All')
  const [season, setSeason] = useState('All')
  const filters = useQuery({ queryKey: ['filters'], queryFn: api.filters })
  const q = useQuery({
    queryKey: ['player', role, pid, competition, season],
    queryFn: () => api.player(role, pid, { competition, season: season === 'All' ? null : Number(season) }),
  })
  const dist = useQuery({ queryKey: ['dist', role, pid], queryFn: () => api.distribution(role, pid) })

  const metricOf = (s: Split) => (bat ? s.sr : s.econ) ?? null
  const expOf = (s: Split) => (bat ? s.exp_sr : s.exp_econ) ?? null
  const dp = bat ? 1 : 2

  const cat = useMemo(() => CATS.map((c) => {
    const s = q.data?.by_category.find((x) => x.k === c)
    return { category: c, value: s ? metricOf(s) : null, expected: s ? expOf(s) : null, balls: s?.balls ?? 0 }
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }), [q.data])

  const phases = useMemo(() => ['Powerplay', 'Middle', 'Death'].map((ph) => {
    const p = q.data?.by_phase.find((x) => x.k === `${ph} - pressure`)
    const n = q.data?.by_phase.find((x) => x.k === `${ph} - normal`)
    return { phase: ph, pressure: p ? metricOf(p) : null, normal: n ? metricOf(n) : null, pBalls: p?.balls ?? 0, nBalls: n?.balls ?? 0 }
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }), [q.data])

  const seasons = useMemo(() => {
    const ys = Array.from(new Set((q.data?.by_season ?? []).map((s) => s.k.split('|')[0]))).sort()
    return ys.map((y) => {
      const p = q.data!.by_season.find((s) => s.k === `${y}|P`)
      const n = q.data!.by_season.find((s) => s.k === `${y}|N`)
      return { season: y, pressure: p ? metricOf(p) : null, normal: n ? metricOf(n) : null, pBalls: p?.balls ?? 0 }
    })
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [q.data])

  const matches = useMemo(() => (q.data?.matches ?? [])
    .filter((x) => (bat ? (x.pressure_balls ?? 0) : (x.pressure_legal_balls ?? 0)) > 0)
    .map((x, i) => ({
      i: i + 1, date: x.match_date, opp: x.opponent, comp: x.competition,
      value: bat ? x.pressure_runs - x.pressure_exp_runs : x.pressure_exp_runs - x.pressure_runs,
      balls: bat ? x.pressure_balls : x.pressure_legal_balls, runs: x.pressure_runs,
      extra: bat ? (x.pressure_outs ? 'out' : 'not out') : `${x.pressure_wkts} wkt`,
    })), [q.data, bat])

  if (q.error) return <ErrorState error={q.error} />
  if (!q.data) return <div className="space-y-4"><Skeleton className="h-32" /><Skeleton className="h-80" /><Skeleton className="h-80" /></div>

  const p = q.data.player
  const color = bat ? '#f43f5e' : '#38bdf8'
  const comp = q.data.components
  const cs = (key: string) => q.data!.competition_split.find((s) => s.k === key)
  const chase = q.data.by_chase.filter((c) => c.k !== 'No result')

  return (
    <div className="space-y-6">
      <Link to={`/rankings/${role}`} className="inline-flex items-center gap-1.5 text-[13px] text-dim hover:text-ink"><ArrowLeft className="h-4 w-4" /> {m.label} rankings</Link>

      <Card className="relative overflow-hidden">
        <div className="pointer-events-none absolute -right-16 -top-16 h-60 w-60 rounded-full blur-3xl" style={{ background: `${color}22` }} />
        <CardBody className="grid gap-6 lg:grid-cols-[1.3fr_1fr]">
          <div>
            <div className="flex flex-wrap items-center gap-2">
              <Badge tone={bat ? 'brand' : 'sky'}>{m.single}</Badge>
              {p.eligible ? <Badge tone="good">Rank #{p.rank}</Badge> : <Badge tone="muted">{p.exclusion ?? 'Below sample bar'}</Badge>}
              {p.auction_status?.startsWith('Current') && <Badge tone="brand">RR · retain</Badge>}
              {p.player_type === 'Overseas' && <Badge tone="warn">Overseas</Badge>}
              {p.competition && <Badge>{p.competition}</Badge>}
              {p.style && <Badge tone="violet">{p.style}</Badge>}
            </div>
            <h1 className="mt-3 text-3xl font-bold tracking-tight text-ink" data-testid="player-name">{p.name}</h1>
            <p className="mt-1 text-sm text-dim">{p.team}{p.ipl_team && p.ipl_team !== p.team ? ` · IPL: ${p.ipl_team}` : ''}{p.national_team && p.national_team !== p.team ? ` · ${p.national_team}` : ''} · {String(p.seasons ?? '')}</p>
            {p.justification && <p className="mt-4 rounded-xl border border-line bg-panel-2/50 p-3 text-[13px] leading-relaxed text-dim">{p.justification}</p>}
          </div>
          <div className="space-y-3">
            <div className="flex items-end justify-between">
              <div>
                <div className="text-[11px] font-semibold uppercase tracking-wider text-faint">{m.index}</div>
                <div className="tabular text-5xl font-extrabold tracking-tight" style={{ color }}>{fmt(num(p, m.index))}</div>
              </div>
              <div className="text-right text-[12px] text-dim">
                90% interval<br /><b className="tabular text-ink">{fmt(num(p, `${m.index}_lo`), 0)} – {fmt(num(p, `${m.index}_hi`), 0)}</b>
              </div>
            </div>
            <RatingBar value={num(p, m.index)} lo={num(p, `${m.index}_lo`)} hi={num(p, `${m.index}_hi`)} color={color} />
            <div className="grid grid-cols-3 gap-2">
              <Metric label="Reliability" value={<ReliabilityPill value={p.reliability} />} sub="certainty, not quality" />
              <Metric label="P(top 10)" value={pct(p.p_top10)} sub={p.rank_lo != null ? `rank ${fmt(p.rank_lo, 0)}–${fmt(p.rank_hi, 0)}` : '–'} />
              <Metric label="Pressure matches" value={p.pressure_matches} sub={`${fmtInt(p.n)} ${bat ? 'balls' : 'legal balls'}`} />
            </div>
          </div>
        </CardBody>
      </Card>

      <div className="grid grid-cols-2 gap-3 md:grid-cols-3 xl:grid-cols-6">
        {bat ? <>
          <Metric label="Pressure SR" value={fmt(num(p, 'p_sr'))} sub={<>vs context {fmt(num(p, 'p_exp_sr'))}</>} />
          <Metric label="Normal SR" value={fmt(num(p, 'n_sr'))} sub={<Delta value={num(p, 'sr_change')} />} />
          <Metric label="Pressure avg" value={fmt(num(p, 'p_avg'))} sub={`${fmtInt(num(p, 'p_outs'))} dismissals`} />
          <Metric label="Boundary %" value={fmt(num(p, 'p_boundary_pct'))} sub="under pressure" />
          <Metric label="Dot %" value={fmt(num(p, 'p_dot_pct'))} sub="under pressure" />
          <Metric label="Close-match SR" value={fmt(num(p, 'close_sr'))} sub={`${fmtInt(num(p, 'close_balls'))} balls`} />
        </> : <>
          <Metric label="Pressure econ" value={fmt(num(p, 'p_econ'), 2)} sub={<>vs context {fmt(num(p, 'p_exp_econ'), 2)}</>} />
          <Metric label="Normal econ" value={fmt(num(p, 'n_econ'), 2)} sub={<Delta value={num(p, 'econ_change')} digits={2} invert />} />
          <Metric label="Pressure wkts" value={fmtInt(num(p, 'p_wkts'))} sub={`${fmt(num(p, 'p_wkts_per_over'), 2)} per over`} />
          <Metric label="Dot %" value={fmt(num(p, 'p_dot_pct'))} sub={`boundary ${fmt(num(p, 'p_boundary_pct'))}%`} />
          <Metric label="Death econ (P)" value={fmt(num(p, 'death_econ'), 2)} sub={`${fmtInt(num(p, 'death_legal_balls'))} balls`} />
          <Metric label="RRR ≥ 10 econ" value={fmt(num(p, 'high_rrr_econ'), 2)} sub={`${fmtInt(num(p, 'high_rrr_legal_balls'))} balls`} />
        </>}
      </div>

      <div className="grid gap-6 xl:grid-cols-2">
        <Card>
          <CardHeader title={`What drives the ${m.index}`} subtitle="Weighted, standardised contribution of each component (shrunk for reliability)" />
          <CardBody className="h-64">
            <ResponsiveContainer>
              <BarChart data={comp.map((c) => ({ ...c, label: COMPONENT_LABEL[c.component] }))} layout="vertical" margin={{ left: 40, right: 16 }}>
                <CartesianGrid horizontal={false} />
                <XAxis type="number" tickLine={false} axisLine={false} />
                <YAxis type="category" dataKey="label" width={150} tickLine={false} axisLine={false} />
                <ReferenceLine x={0} stroke="#475569" />
                <Tooltip content={<ChartTooltip formatter={(v) => signed(v, 3)} />} />
                <Bar dataKey="contribution" name="Contribution" radius={4}>
                  {comp.map((c) => <Cell key={c.component} fill={COMPONENT_COLORS[c.component]} fillOpacity={c.contribution >= 0 ? 1 : 0.45} />)}
                </Bar>
              </BarChart>
            </ResponsiveContainer>
          </CardBody>
          <div className="grid grid-cols-5 gap-2 px-5 pb-5 text-center text-[11px] text-faint">
            {comp.map((c) => <div key={c.component}><div className="font-semibold text-dim">{(c.weight * 100).toFixed(0)}%</div>weight · signal {(c.signal_share * 100).toFixed(0)}%</div>)}
          </div>
        </Card>

        <Card>
          <CardHeader title={`${bat ? 'Strike rate' : 'Economy'} by pressure category`} subtitle="Player vs what an average player achieves in the same situations (dashed)"
            action={<div className="flex gap-2">
              <Select className="w-28" label="Competition" value={competition} onChange={setCompetition} options={[{ value: 'All', label: 'All' }, { value: 'IPL', label: 'IPL' }, { value: 'T20I', label: 'T20I' }]} />
              <Select className="w-24" label="Season" value={season} onChange={setSeason} options={[{ value: 'All', label: 'All' }, ...(filters.data?.seasons ?? []).map((s) => ({ value: String(s), label: String(s) }))]} />
            </div>} />
          <CardBody className="h-64">
            <ResponsiveContainer>
              <ComposedChart data={cat} margin={{ left: -12, right: 8, top: 8 }}>
                <CartesianGrid vertical={false} />
                <XAxis dataKey="category" tickLine={false} axisLine={false} />
                <YAxis tickLine={false} axisLine={false} />
                <Tooltip content={<ChartTooltip formatter={(v) => fmt(v, dp)} />} />
                <Bar dataKey="value" name={bat ? 'SR' : 'Economy'} radius={[6, 6, 0, 0]}>
                  {cat.map((c) => <Cell key={c.category} fill={PRESSURE_COLORS[c.category]} />)}
                </Bar>
                <Line dataKey="expected" name="Context expected" stroke="var(--color-ink)" strokeDasharray="5 4" strokeWidth={2} dot={{ r: 3 }} />
              </ComposedChart>
            </ResponsiveContainer>
          </CardBody>
        </Card>
      </div>

      <Card>
        <CardHeader title="Match-by-match pressure value" subtitle={bat ? 'Runs above context-expected on pressure balls in each match (chronological)' : 'Runs saved vs context-expected on pressure deliveries in each match (chronological)'} />
        <CardBody className="h-72">
          <ResponsiveContainer>
            <BarChart data={matches} margin={{ left: -12, right: 8, top: 8 }}>
              <CartesianGrid vertical={false} />
              <XAxis dataKey="i" tickLine={false} axisLine={false} />
              <YAxis tickLine={false} axisLine={false} />
              <ReferenceLine y={0} stroke="#475569" />
              <Tooltip content={({ active, payload }) => {
                if (!active || !payload?.length) return null
                const d = payload[0].payload as (typeof matches)[number]
                return (
                  <div className="rounded-xl border border-line bg-panel/95 px-3 py-2 text-xs shadow-xl">
                    <div className="font-semibold text-ink">{d.date} · v {d.opp} ({d.comp})</div>
                    <div className="text-dim">{d.balls} pressure balls · {d.runs} runs · {d.extra}</div>
                    <div className="mt-1 font-semibold" style={{ color: d.value >= 0 ? '#34d399' : '#fb7185' }}>{signed(d.value)} vs expected</div>
                  </div>
                )
              }} />
              <Bar dataKey="value" radius={[3, 3, 0, 0]}>
                {matches.map((x) => <Cell key={x.i} fill={x.value >= 0 ? '#34d399' : '#f43f5e'} />)}
              </Bar>
            </BarChart>
          </ResponsiveContainer>
        </CardBody>
        <div className="px-5 pb-5 text-[12px] text-dim">
          {matches.length} pressure matches · positive in <b className="text-ink">{matches.filter((x) => x.value >= 0).length}</b> ({pct(matches.filter((x) => x.value >= 0).length / Math.max(matches.length, 1))})
        </div>
      </Card>

      <div className="grid gap-6 xl:grid-cols-3">
        <Card>
          <CardHeader title="By innings phase" subtitle="Pressure vs normal balls" />
          <CardBody className="h-60">
            <ResponsiveContainer>
              <BarChart data={phases} margin={{ left: -12, right: 8, top: 8 }}>
                <CartesianGrid vertical={false} />
                <XAxis dataKey="phase" tickLine={false} axisLine={false} />
                <YAxis tickLine={false} axisLine={false} />
                <Tooltip content={<ChartTooltip formatter={(v) => fmt(v, dp)} />} />
                <Legend />
                <Bar dataKey="normal" name="Normal" fill="#475569" radius={[4, 4, 0, 0]} />
                <Bar dataKey="pressure" name="Pressure" fill={color} radius={[4, 4, 0, 0]} />
              </BarChart>
            </ResponsiveContainer>
          </CardBody>
        </Card>
        <Card>
          <CardHeader title="Performance trend" subtitle="By season · pressure vs normal" />
          <CardBody className="h-60">
            <ResponsiveContainer>
              <LineChart data={seasons} margin={{ left: -12, right: 8, top: 8 }}>
                <CartesianGrid vertical={false} />
                <XAxis dataKey="season" tickLine={false} axisLine={false} />
                <YAxis tickLine={false} axisLine={false} domain={['auto', 'auto']} />
                <Tooltip content={<ChartTooltip formatter={(v) => fmt(v, dp)} />} />
                <Legend />
                <Line dataKey="normal" name="Normal" stroke="#8b95b2" strokeWidth={2} dot={{ r: 3 }} connectNulls />
                <Line dataKey="pressure" name="Pressure" stroke={color} strokeWidth={2.5} dot={{ r: 4 }} connectNulls />
              </LineChart>
            </ResponsiveContainer>
          </CardBody>
        </Card>
        <Card>
          <CardHeader title="Pressure faced" subtitle="Distribution of pressure scores on this player's balls" />
          <CardBody className="h-60">
            <ResponsiveContainer>
              <BarChart data={dist.data ?? []} margin={{ left: -12, right: 8, top: 8 }}>
                <CartesianGrid vertical={false} />
                <XAxis dataKey="bucket" tickLine={false} axisLine={false} />
                <YAxis tickLine={false} axisLine={false} />
                <Tooltip content={<ChartTooltip formatter={(v) => fmtInt(v)} />} />
                <Bar dataKey="n" name="Balls" radius={[3, 3, 0, 0]}>
                  {(dist.data ?? []).map((d) => <Cell key={d.bucket} fill={d.bucket >= 90 ? PRESSURE_COLORS.Extreme : d.bucket >= 75 ? PRESSURE_COLORS.High : d.bucket >= 50 ? PRESSURE_COLORS.Moderate : PRESSURE_COLORS.Low} />)}
                </Bar>
              </BarChart>
            </ResponsiveContainer>
          </CardBody>
        </Card>
      </div>

      <div className="grid gap-6 xl:grid-cols-2">
        <Card>
          <CardHeader title={bat ? 'Chase context' : 'Opposition chase context'} subtitle={bat ? 'Setting a target vs successful and failed chases' : 'Bowling first vs defending in chases the opposition won/lost'} />
          <CardBody>
            <table className="w-full text-[13px]">
              <thead><tr className="text-left text-[10.5px] uppercase tracking-wider text-faint"><th className="pb-2">Situation</th><th className="pb-2 text-right">Balls</th><th className="pb-2 text-right">{bat ? 'SR' : 'Econ'}</th><th className="pb-2 text-right">Context</th><th className="pb-2 text-right">{bat ? 'Outs' : 'Wkts'}</th><th className="pb-2 text-right">WPA</th></tr></thead>
              <tbody>
                {chase.map((c) => (
                  <tr key={c.k} className="border-t border-line/60">
                    <td className="py-2 text-ink">{bat ? c.k : c.k === 'Setting target' ? 'Opposition setting target' : `Opposition ${c.k.toLowerCase()}`}</td>
                    <td className="tabular py-2 text-right text-dim">{fmtInt(c.balls)}</td>
                    <td className="tabular py-2 text-right font-semibold text-ink">{fmt(metricOf(c), dp)}</td>
                    <td className="tabular py-2 text-right text-dim">{fmt(expOf(c), dp)}</td>
                    <td className="tabular py-2 text-right text-dim">{fmtInt(bat ? c.outs : c.wkts)}</td>
                    <td className="tabular py-2 text-right" style={{ color: c.wpa >= 0 ? '#34d399' : '#fb7185' }}>{signed(c.wpa * 100)}</td>
                  </tr>
                ))}
              </tbody>
            </table>
            <p className="mt-3 flex gap-1.5 text-[11.5px] text-faint"><Info className="mt-0.5 h-3.5 w-3.5 shrink-0" /> WPA = win-probability points added for the player's side (sum over balls, ×100).</p>
          </CardBody>
        </Card>
        <Card>
          <CardHeader title="IPL vs T20I" subtitle="Pressure and normal performance in each competition, plus competition-only ratings" />
          <CardBody>
            <div className="grid grid-cols-2 gap-3">
              {(['IPL', 'T20I'] as const).map((c) => {
                const pr = cs(`${c}|P`)
                const nr = cs(`${c}|N`)
                const rating = num(p, `${m.index}_${c}`)
                return (
                  <div key={c} className="rounded-xl border border-line bg-panel-2/50 p-4">
                    <div className="flex items-center justify-between"><span className="font-semibold text-ink">{c}</span>
                      {p[`eligible_${c}`] ? <Badge tone="good">#{fmt(num(p, `rank_${c}`), 0)}</Badge> : <Badge tone="muted">n/e</Badge>}</div>
                    <div className="mt-3 space-y-1.5 text-[12.5px]">
                      <div className="flex justify-between text-dim"><span>Pressure {bat ? 'SR' : 'econ'}</span><b className="tabular text-ink">{pr ? fmt(metricOf(pr), dp) : '–'}</b></div>
                      <div className="flex justify-between text-dim"><span>Normal {bat ? 'SR' : 'econ'}</span><b className="tabular text-ink">{nr ? fmt(metricOf(nr), dp) : '–'}</b></div>
                      <div className="flex justify-between text-dim"><span>Pressure balls</span><b className="tabular text-ink">{fmtInt(pr?.balls)}</b></div>
                      <div className="flex justify-between text-dim"><span>{m.index} ({c})</span><b className="tabular text-ink">{fmt(rating)}</b></div>
                    </div>
                  </div>
                )
              })}
            </div>
          </CardBody>
        </Card>
      </div>
    </div>
  )
}
