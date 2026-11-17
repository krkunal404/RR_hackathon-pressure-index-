import { useQuery } from '@tanstack/react-query'
import { Brain, Calculator, Database, Scale, Sigma, Target } from 'lucide-react'
import { CartesianGrid, Legend, Line, LineChart, ResponsiveContainer, Scatter, ComposedChart, Tooltip, XAxis, YAxis, ZAxis } from 'recharts'
import { Badge, Card, CardBody, CardHeader, ErrorState, Skeleton } from '@/components/ui/primitives'
import { ChartTooltip, PageHeader } from '@/components/widgets'
import { api, type Json } from '@/lib/api'
import { COMPONENT_COLORS, COMPONENT_LABEL, fmt } from '@/lib/utils'

function Formula({ children }: { children: React.ReactNode }) {
  return <pre className="overflow-x-auto rounded-xl border border-line bg-bg/70 p-4 font-mono text-[12.5px] leading-relaxed text-ink scroll-thin">{children}</pre>
}

function ComponentTable({ meta, weights }: { meta: Json; weights: Record<string, number> }) {
  return (
    <div className="space-y-2.5">
      {Object.entries(weights).map(([k, w]) => (
        <div key={k} className="grid grid-cols-[1fr_auto] items-center gap-3">
          <div>
            <div className="flex items-center gap-2 text-[13px] font-medium text-ink"><span className="h-2.5 w-2.5 rounded-full" style={{ background: COMPONENT_COLORS[k] }} />{COMPONENT_LABEL[k]}</div>
            <div className="mt-1 h-1.5 overflow-hidden rounded-full bg-panel-2"><div className="h-full rounded-full" style={{ width: `${meta.component_signal_share[k] * 100}%`, background: COMPONENT_COLORS[k] }} /></div>
          </div>
          <div className="text-right text-[12px] text-dim"><b className="text-ink">{(w * 100).toFixed(0)}%</b> weight<br />{(meta.component_signal_share[k] * 100).toFixed(0)}% signal</div>
        </div>
      ))}
    </div>
  )
}

export default function Methodology() {
  const q = useQuery({ queryKey: ['methodology'], queryFn: api.methodology })
  if (q.error) return <ErrorState error={q.error} />
  if (!q.data) return <div className="space-y-4"><Skeleton className="h-40" /><Skeleton className="h-80" /></div>
  const { win_probability: wp, batter_meta: bm, bowler_meta: wm, config: cfg, audit, wicket_run_value: lam } = q.data
  const calib = [1, 2].map((inn) => wp[`innings_${inn}`].calibration as { pred: number; obs: number; n: number }[])

  return (
    <div className="space-y-6">
      <PageHeader eyebrow="Methodology" title="From ball-by-ball data to a pressure rating"
        desc="Every step is transparent and reproducible with `python main.py`. Nothing here is hand-tuned to favour particular players. Weights are fixed up front, and the data decides how much each component can move a rating." />

      <div className="grid gap-6 xl:grid-cols-3">
        <Card className="xl:col-span-2">
          <CardHeader icon={<Brain className="h-4 w-4" />} title="1 · Win-probability models" subtitle="P(batting side wins | state before the ball), cross-fitted by match so no match's own result informs it" />
          <CardBody className="grid gap-5 md:grid-cols-2">
            <div className="space-y-3 text-[13px] leading-relaxed text-dim">
              <p><b className="text-ink">Chase:</b> runs needed, balls left, wickets left, required rate, IPL flag. <b className="text-ink">Setting:</b> runs, balls left, wickets left, IPL flag.</p>
              <p>Gradient-boosted classifiers with <b className="text-ink">monotonic constraints</b> that enforce cricket logic (more runs needed can never raise chase WP). A logistic regression is kept as a transparent benchmark.</p>
              <div className="grid grid-cols-2 gap-2">
                {[1, 2].map((i) => (
                  <div key={i} className="rounded-xl border border-line bg-panel-2/50 p-3">
                    <div className="text-[11px] font-semibold uppercase tracking-wider text-faint">{i === 1 ? 'Setting' : 'Chasing'}</div>
                    <div className="tabular mt-1 text-xl font-bold text-ink">AUC {fmt(wp[`innings_${i}`].auc, 3)}</div>
                    <div className="tabular text-[11.5px]">Brier {fmt(wp[`innings_${i}`].brier, 3)} · 2025-26 hold-out {fmt(wp[`innings_${i}`].holdout_2025_26_auc, 3)}</div>
                  </div>
                ))}
              </div>
            </div>
            <div className="h-64">
              <ResponsiveContainer>
                <ComposedChart margin={{ left: -12, right: 8, top: 8 }}>
                  <CartesianGrid />
                  <XAxis type="number" dataKey="pred" domain={[0, 1]} tickLine={false} axisLine={false} label={{ value: 'Predicted WP', position: 'insideBottom', offset: -2, fill: '#5b6585', fontSize: 11 }} />
                  <YAxis type="number" dataKey="obs" domain={[0, 1]} tickLine={false} axisLine={false} />
                  <Tooltip content={<ChartTooltip formatter={(v) => v.toFixed(3)} />} />
                  <Legend />
                  <Line data={[{ pred: 0, obs: 0 }, { pred: 1, obs: 1 }]} dataKey="obs" stroke="#475569" strokeDasharray="4 4" dot={false} name="Perfect" legendType="none" />
                  <ZAxis range={[90, 90]} />
                  <Scatter data={calib[0]} name="Setting" fill="#38bdf8" />
                  <Scatter data={calib[1]} name="Chasing" fill="#f43f5e" />
                </ComposedChart>
              </ResponsiveContainer>
            </div>
          </CardBody>
        </Card>
        <Card>
          <CardHeader icon={<Database className="h-4 w-4" />} title="Data rules" subtitle="Established in the data audit" />
          <CardBody className="space-y-2 text-[12.5px] leading-relaxed text-dim">
            <p><Badge>rule</Badge> <code className="font-mono text-ink">extras1_runs</code> is the recorded extra-run amount ({Object.entries(audit.extras_runs_by_type ?? {}).map(([k, v]) => `${k} ${v}`).join(', ')}); byes off a no-ball come from <code className="font-mono text-ink">extras_2_runs</code>.</p>
            <p><Badge tone="warn">fix</Badge> “other” extras behave as no-balls (illegal).</p>
            <p><Badge>rule</Badge> Bowler runs = bat runs + wide and no-ball runs. Byes, leg-byes and penalties excluded.</p>
            <p><Badge>rule</Badge> Bowler wickets: caught, bowled, LBW, stumped, hit wicket.</p>
            <p><Badge>scope</Badge> Super overs ({audit.super_over_deliveries} balls) and A-team events excluded.</p>
            <p><Badge>ids</Badge> Joins use player ids. {audit.names_with_multiple_ids.length} names are shared by more than one id.</p>
          </CardBody>
        </Card>
      </div>

      <Card>
        <CardHeader icon={<Calculator className="h-4 w-4" />} title="2 · Pressure score (0–100)" subtitle="Computed only from the state before each delivery" />
        <CardBody className="grid gap-5 lg:grid-cols-2">
          <Formula>{`leverage   L = clip((WP_if_four − WP_if_wicket) / p99, 0, 1)
closeness  Q = (1 − |2·WP − 1|) × match_progress
stress     S = max(recent_wkts_24 / 3, (RRR − 7.5) / 7.5)   clipped 0..1

raw        R = (${cfg.PRESSURE_WEIGHTS.leverage}·L + ${cfg.PRESSURE_WEIGHTS.closeness}·Q + ${cfg.PRESSURE_WEIGHTS.stress}·S) × ${cfg.KNOCKOUT_MULTIPLIER} if knockout
bowling    R_b = ${1 - cfg.BOWLING_SPELL_WEIGHT}·R + ${cfg.BOWLING_SPELL_WEIGHT}·spell_stress

Pressure  = 100 × percentile(R | innings)`}</Formula>
          <div className="grid grid-cols-2 gap-3 text-[12.5px] text-dim">
            {[['Low', '< 50', '#475569'], ['Moderate', '50 – 75', '#38bdf8'], ['High', '75 – 90', '#f59e0b'], ['Extreme', '≥ 90', '#f43f5e']].map(([l, r, c]) => (
              <div key={l} className="rounded-xl border border-line bg-panel-2/50 p-3"><div className="font-semibold" style={{ color: c }}>{l}</div><div className="tabular text-lg font-bold text-ink">{r}</div></div>
            ))}
            <p className="col-span-2 leading-relaxed"><b className="text-ink">Why these features?</b> Leverage is the most direct measure of how much a ball can change the result. Closeness, weighted by match progress, marks a live game with little time left to recover. Stress picks up collapses and steep required rates that the WP model smooths over. Because the score is a within-innings percentile, first-innings pressure is judged against first-innings norms.</p>
          </div>
        </CardBody>
      </Card>

      <div className="grid gap-6 xl:grid-cols-2">
        <Card>
          <CardHeader icon={<Target className="h-4 w-4" />} title="3 · BPPI — batters" subtitle="Weights fixed up front · bar shows how much of each component is real signal after shrinkage" />
          <CardBody><ComponentTable meta={bm} weights={cfg.BPPI_WEIGHTS} /></CardBody>
        </Card>
        <Card>
          <CardHeader icon={<Target className="h-4 w-4" />} title="4 · BoPPI — bowlers" subtitle="Bowler-attributed runs and bowler-credited wickets only" />
          <CardBody><ComponentTable meta={wm} weights={cfg.BOPPI_WEIGHTS} /></CardBody>
        </Card>
      </div>

      <div className="grid gap-6 xl:grid-cols-2">
        <Card>
          <CardHeader icon={<Sigma className="h-4 w-4" />} title="5 · Context baselines & composite" />
          <CardBody>
            <Formula>{`expected  = cell mean(competition × innings × over × wkts × pressure)
            shrunk 100 balls → parent cell, + opposition strength
value/ball = (runs − expected) + ${fmt(lam, 1)} × (exp. dismissals − dismissals)
             (${fmt(lam, 1)} = runs-equivalent of a wicket, from WPA regression)

component = Σ w·value / (Σ w + k)          empirical-Bayes shrinkage
z         = (component − mean) / sd(raw component)
index     = 100 × (Σ weight·z − min) / (max − min)`}</Formula>
          </CardBody>
        </Card>
        <Card>
          <CardHeader icon={<Scale className="h-4 w-4" />} title="6 · Fairness & reliability" />
          <CardBody className="space-y-3 text-[13px] leading-relaxed text-dim">
            <p><b className="text-ink">Eligibility:</b> ≥ {cfg.MIN_PRESSURE_BALLS_BAT} pressure balls and ≥ {cfg.MIN_PRESSURE_MATCHES} pressure matches.</p>
            <p><b className="text-ink">Shrinkage k</b> (pseudo-balls) — batters: scoring {fmt(bm.k.score, 0)}, survival {fmt(bm.k.surv, 0)}, impact {fmt(bm.k.imp, 0)}; bowlers: economy {fmt(wm.k.score, 0)}, wickets {fmt(wm.k.surv, 0)}, impact {fmt(wm.k.imp, 0)}.</p>
            <p><b className="text-ink">Clutch is mostly noise:</b> at 200 pressure balls only {fmt(bm.uplift_reliability_at_200_balls * 100, 0)}% of a batter's uplift over their own baseline is signal (bowlers ≈ {fmt(wm.uplift_reliability_at_200_balls * 100, 0)}%), so it is shrunk accordingly.</p>
            <p><b className="text-ink">Competition weights:</b> IPL {cfg.COMPETITION_WEIGHTS.IPL}, Full-Member T20I {cfg.COMPETITION_WEIGHTS.T20I_FULL}, T20I vs Associate {cfg.COMPETITION_WEIGHTS.T20I_ASSOC}.</p>
            <p><b className="text-ink">Uncertainty:</b> a match-level cluster bootstrap ({cfg.BOOTSTRAP_REPS} resamples) gives 90% intervals, rank ranges and P(top-10). Reliability (0–100) is shown separately and never mixed into the rating.</p>
          </CardBody>
        </Card>
      </div>

      <Card>
        <CardHeader title="Calibration detail" subtitle="Observed win rate in each predicted-WP decile (out-of-fold)" />
        <CardBody className="h-64">
          <ResponsiveContainer>
            <LineChart data={calib[1].map((c, i) => ({ bin: i + 1, chasePred: c.pred, chaseObs: c.obs, setPred: calib[0][i]?.pred, setObs: calib[0][i]?.obs }))} margin={{ left: -12, right: 8, top: 8 }}>
              <CartesianGrid vertical={false} />
              <XAxis dataKey="bin" tickLine={false} axisLine={false} />
              <YAxis domain={[0, 1]} tickLine={false} axisLine={false} />
              <Tooltip content={<ChartTooltip formatter={(v) => v.toFixed(3)} />} />
              <Legend />
              <Line dataKey="chasePred" name="Chase predicted" stroke="#f43f5e" strokeDasharray="4 3" dot={false} />
              <Line dataKey="chaseObs" name="Chase observed" stroke="#f43f5e" strokeWidth={2} />
              <Line dataKey="setPred" name="Setting predicted" stroke="#38bdf8" strokeDasharray="4 3" dot={false} />
              <Line dataKey="setObs" name="Setting observed" stroke="#38bdf8" strokeWidth={2} />
            </LineChart>
          </ResponsiveContainer>
        </CardBody>
      </Card>
    </div>
  )
}
