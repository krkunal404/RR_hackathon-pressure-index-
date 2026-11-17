import { motion } from 'framer-motion'
import { useNavigate } from 'react-router-dom'
import { Badge } from '@/components/ui/primitives'
import { RankMedal, RatingBar, ReliabilityPill } from '@/components/widgets'
import { num, roleMeta, type PlayerRow, type Role } from '@/lib/api'
import { fmt, fmtInt, pct } from '@/lib/utils'

export function LeaderboardList({ role, rows, compact }: { role: Role; rows: PlayerRow[]; compact?: boolean }) {
  const nav = useNavigate()
  const m = roleMeta[role]
  const color = role === 'batters' ? '#f43f5e' : '#38bdf8'
  return (
    <ol className="divide-y divide-line/70" data-testid={`leaderboard-${role}`}>
      {rows.map((r, i) => (
        <motion.li key={r.player_id} initial={{ opacity: 0, x: -6 }} animate={{ opacity: 1, x: 0 }} transition={{ delay: i * 0.03 }}>
          <button onClick={() => nav(`/players/${role}/${r.player_id}`)}
            className="grid w-full grid-cols-[auto_1fr_auto] items-center gap-3 px-5 py-3 text-left transition-colors hover:bg-panel-2/60 md:grid-cols-[auto_minmax(0,1.3fr)_minmax(0,1fr)_auto]">
            <RankMedal rank={r.rank} />
            <div className="min-w-0">
              <div className="truncate font-semibold text-ink">{r.name}</div>
              <div className="flex items-center gap-1.5 truncate text-[12px] text-faint">
                <span className="truncate">{r.team}</span>
                {r.auction_status?.startsWith('Current') && <Badge tone="brand" title="Already in the Rajasthan Royals squad">RR · retain</Badge>}
                {r.player_type === 'Overseas' && <Badge tone="warn" title="Uses an overseas squad slot">Overseas</Badge>}
                {!compact && r.pace_or_spin && <Badge tone={r.pace_or_spin === 'Spin' ? 'violet' : 'sky'}>{r.pace_or_spin}</Badge>}
              </div>
            </div>
            <div className="hidden md:block">
              <RatingBar value={num(r, m.index)} lo={num(r, `${m.index}_lo`)} hi={num(r, `${m.index}_hi`)} color={color} />
            </div>
            <div className="flex flex-col items-end gap-1 text-right">
              <span className="tabular text-[13px] font-semibold text-ink md:hidden">{fmt(num(r, m.index))}</span>
              <span className="tabular text-[12px] text-dim">
                {m.primaryLabel} <b className="text-ink">{fmt(num(r, m.primary), role === 'batters' ? 1 : 2)}</b>
                {!compact && <span className="text-faint"> · {fmtInt(num(r, m.balls))} balls</span>}
              </span>
              {!compact && <span className="flex items-center gap-1.5"><ReliabilityPill value={r.reliability} /><Badge tone="default" title="Bootstrap probability of a top-10 finish">P(top10) {pct(r.p_top10)}</Badge></span>}
            </div>
          </button>
        </motion.li>
      ))}
    </ol>
  )
}
