import { useQuery } from '@tanstack/react-query'
import { ArrowRight, Crosshair, Database, Flame, Gauge, Users, Zap } from 'lucide-react'
import { Link } from 'react-router-dom'
import { Bar, BarChart, CartesianGrid, Cell, ComposedChart, Line, ResponsiveContainer, Tooltip, XAxis, YAxis } from 'recharts'
import { LeaderboardList } from '@/components/Leaderboard'
import { Badge, Card, CardBody, CardHeader, ErrorState, Skeleton } from '@/components/ui/primitives'
import { ChartTooltip, PageHeader, StatTile } from '@/components/widgets'
import { api } from '@/lib/api'
import { fmt, PRESSURE_COLORS } from '@/lib/utils'

export default function Overview() {
  const ov = useQuery({ queryKey: ['overview'], queryFn: api.overview })
  const bat = useQuery({ queryKey: ['top10', 'batters'], queryFn: () => api.top10('batters') })
  const bowl = useQuery({ queryKey: ['top10', 'bowlers'], queryFn: () => api.top10('bowlers') })
  const pr = useQuery({ queryKey: ['pressure', 'All', null], queryFn: () => api.pressure({}) })
  const moments = useQuery({ queryKey: ['moments', 'All', null, 6], queryFn: () => api.moments({ limit: 6 }) })

  if (ov.error) return <ErrorState error={ov.error} />
  const o = ov.data
  const overs = (pr.data?.by_over ?? []).filter((r) => r.innings === 2).map((r) => ({
    over: r.over, share: r.pressure_share,
    first: pr.data!.by_over.find((x) => x.innings === 1 && x.over === r.over)?.pressure_share,
  }))

  return (
    <div className="space-y-6">
      <div className="relative overflow-hidden rounded-3xl border border-line bg-gradient-to-br from-panel-2 via-panel to-bg p-6 md:p-8">
        <div className="pointer-events-none absolute -right-20 -top-24 h-72 w-72 rounded-full bg-brand/20 blur-3xl" />
        <div className="pointer-events-none absolute -bottom-24 right-40 h-56 w-56 rounded-full bg-sky/10 blur-3xl" />
        <PageHeader
          eyebrow="SupeRR Selector · Season 2 · Round 1"
          title={<>Who delivers <span className="bg-gradient-to-r from-brand-2 to-gold bg-clip-text text-transparent">when it matters?</span></>}
          desc="Pressure is measured as how much the result hinges on each delivery, using cross-fitted win-probability models built only from the scoreboard before the ball. Players are judged against what an average player achieves in the same situation, shrunk for sample size, with uncertainty shown next to every rating."
          actions={
            <div className="flex gap-2">
              <Link to="/rankings/batters" className="inline-flex h-10 shrink-0 items-center gap-2 whitespace-nowrap rounded-xl bg-brand px-4 text-sm font-semibold text-white shadow-[0_10px_30px_-10px_rgba(244,63,94,0.9)] hover:bg-brand-2">Rankings <ArrowRight className="h-4 w-4" /></Link>
              <Link to="/methodology" className="inline-flex h-10 shrink-0 items-center whitespace-nowrap rounded-xl border border-line bg-panel-2/70 px-4 text-sm font-medium text-ink hover:bg-panel-2">How it works</Link>
            </div>
          }
        />
      </div>

      <div className="grid grid-cols-2 gap-3 md:grid-cols-3 xl:grid-cols-6">
        {o ? <>
          <StatTile label="Matches" value={o.matches.toLocaleString()} sub={`${o.ipl_matches} IPL · ${o.t20i_matches} T20I`} icon={<Database className="h-4 w-4" />} accent="sky" />
          <StatTile label="Deliveries" value={(o.deliveries / 1000).toFixed(1) + 'k'} sub={`${o.seasons[0]}–${o.seasons[o.seasons.length - 1]}`} icon={<Zap className="h-4 w-4" />} accent="gold" delay={0.04} />
          <StatTile label="Players" value={o.players.toLocaleString()} sub={`${o.batters} batted · ${o.bowlers} bowled`} icon={<Users className="h-4 w-4" />} accent="violet" delay={0.08} />
          <StatTile label="Pressure balls" value={(o.pressure_deliveries / 1000).toFixed(1) + 'k'} sub="High + Extreme (top 25%)" icon={<Flame className="h-4 w-4" />} delay={0.12} />
          <StatTile label="Extreme moments" value={o.extreme_deliveries.toLocaleString()} sub="Top 10% within innings" icon={<Crosshair className="h-4 w-4" />} delay={0.16} />
          <StatTile label="Rated players" value={`${o.eligible_batters} / ${o.eligible_bowlers}`} sub="batters / bowlers eligible" icon={<Gauge className="h-4 w-4" />} accent="emerald" delay={0.2} />
        </> : Array.from({ length: 6 }).map((_, i) => <Skeleton key={i} className="h-[104px] rounded-2xl" />)}
      </div>

      <div className="grid gap-6 xl:grid-cols-2">
        {(['batters', 'bowlers'] as const).map((role) => {
          const q = role === 'batters' ? bat : bowl
          return (
            <Card key={role}>
              <CardHeader
                title={`Top 10 ${role} for RR to back · IPL 2027 auction`}
                subtitle={`${role === 'batters' ? 'Batter Pressure Performance Index (BPPI)' : 'Bowler Pressure Performance Index (BoPPI)'}. Auction pool only: no Pakistan players, active in 2025-26. Bar shows the 90% bootstrap interval.`}
                action={<Link to={`/rankings/${role}`} className="shrink-0 text-[12.5px] font-medium text-brand-2 hover:underline">Full table →</Link>}
              />
              <div className="mt-3">
                {q.data ? <LeaderboardList role={role} rows={q.data} compact /> : <div className="space-y-2 p-5">{Array.from({ length: 10 }).map((_, i) => <Skeleton key={i} className="h-10" />)}</div>}
              </div>
            </Card>
          )
        })}
      </div>

      <div className="grid gap-6 xl:grid-cols-5">
        <Card className="xl:col-span-3">
          <CardHeader title="Pressure isn't just the death overs" subtitle="Share of deliveries rated High or Extreme by over. A death over in a decided game scores low; a tight middle-overs chase scores high." />
          <CardBody className="h-72">
            <ResponsiveContainer>
              <ComposedChart data={overs} margin={{ left: -18, right: 8, top: 8 }}>
                <CartesianGrid vertical={false} />
                <XAxis dataKey="over" tickLine={false} axisLine={false} />
                <YAxis tickLine={false} axisLine={false} unit="%" />
                <Tooltip content={<ChartTooltip formatter={(v) => `${v.toFixed(1)}%`} />} />
                <Bar dataKey="share" name="Chase (inn 2)" fill="#f43f5e" radius={[4, 4, 0, 0]} />
                <Line dataKey="first" name="Setting (inn 1)" stroke="#38bdf8" strokeWidth={2} dot={false} />
              </ComposedChart>
            </ResponsiveContainer>
          </CardBody>
        </Card>
        <Card className="xl:col-span-2">
          <CardHeader title="What pressure does to play" subtitle="League-wide outcomes by pressure category" />
          <CardBody className="h-72">
            <ResponsiveContainer>
              <BarChart data={pr.data?.categories ?? []} margin={{ left: -18, right: 8, top: 8 }}>
                <CartesianGrid vertical={false} />
                <XAxis dataKey="category" tickLine={false} axisLine={false} />
                <YAxis tickLine={false} axisLine={false} unit="%" />
                <Tooltip content={<ChartTooltip formatter={(v) => `${v.toFixed(2)}%`} />} />
                <Bar dataKey="wicket_pct" name="Wicket %" radius={[6, 6, 0, 0]}>
                  {(pr.data?.categories ?? []).map((c) => <Cell key={c.category} fill={PRESSURE_COLORS[c.category]} />)}
                </Bar>
              </BarChart>
            </ResponsiveContainer>
          </CardBody>
        </Card>
      </div>

      <Card>
        <CardHeader title="Highest-pressure moments" subtitle="The single most pressured delivery in each of the most pressured matches" action={<Link to="/pressure" className="text-[12.5px] font-medium text-brand-2 hover:underline">Pressure Lab →</Link>} />
        <CardBody className="grid gap-3 md:grid-cols-2 xl:grid-cols-3">
          {(moments.data ?? []).map((m) => (
            <Link key={m.match_id} to={`/pressure?match=${m.match_id}`} className="group rounded-xl border border-line bg-panel-2/50 p-4 transition-colors hover:border-brand/40">
              <div className="flex items-center justify-between text-[11px] text-faint">
                <span>{m.comp_name} · {m.match_date}</span>
                <Badge tone="brand">Extreme</Badge>
              </div>
              <div className="mt-2 font-semibold text-ink">{m.batting_team} <span className="text-faint">v</span> {m.bowling_team}</div>
              <div className="mt-1 text-[12.5px] text-dim">
                Over {m.overid}.{m.over_ball_num} · {m.innings === 2 ? `need ${m.runs_needed} off ${m.balls_left}` : `1st innings, ${m.balls_left} balls left`} · {m.wkts_before} down · WP {fmt(m.wp_before * 100, 0)}%
              </div>
              <div className="mt-2 text-[12px] text-faint">{m.striker_name} v {m.bowler_name} → <b className="text-ink">{m.team_wicket ? 'WICKET' : `${m.bat_runs} run${m.bat_runs === 1 ? '' : 's'}`}</b> ({m.wpa >= 0 ? '+' : ''}{(m.wpa * 100).toFixed(1)} WP pts)</div>
            </Link>
          ))}
          {!moments.data && Array.from({ length: 6 }).map((_, i) => <Skeleton key={i} className="h-32" />)}
        </CardBody>
      </Card>
    </div>
  )
}
