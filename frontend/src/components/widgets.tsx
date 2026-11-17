import { motion } from 'framer-motion'
import type { ReactNode } from 'react'
import { Badge } from '@/components/ui/primitives'
import { cn, fmt, reliabilityTier } from '@/lib/utils'

export function StatTile({ label, value, sub, icon, accent = 'brand', delay = 0 }: {
  label: string; value: ReactNode; sub?: ReactNode; icon?: ReactNode; accent?: 'brand' | 'sky' | 'gold' | 'emerald' | 'violet'; delay?: number
}) {
  const ring = { brand: 'text-brand-2 bg-brand/10', sky: 'text-sky bg-sky/10', gold: 'text-gold bg-gold/10', emerald: 'text-emerald bg-emerald/10', violet: 'text-violet bg-violet/10' }[accent]
  return (
    <motion.div initial={{ opacity: 0, y: 8 }} animate={{ opacity: 1, y: 0 }} transition={{ delay, duration: 0.35 }}
      className="glass relative overflow-hidden rounded-2xl border border-line p-4">
      <div className="flex items-center justify-between">
        <span className="text-[11px] font-semibold uppercase tracking-wider text-faint">{label}</span>
        {icon && <span className={cn('grid h-7 w-7 place-items-center rounded-lg', ring)}>{icon}</span>}
      </div>
      <div className="tabular mt-2 text-[26px] font-bold leading-none tracking-tight text-ink">{value}</div>
      {sub && <div className="mt-1.5 text-[12px] text-dim">{sub}</div>}
    </motion.div>
  )
}

/** Horizontal 0-100 rating bar with optional 90% interval whisker. */
export function RatingBar({ value, lo, hi, color = '#f43f5e', className }: {
  value: number | null | undefined; lo?: number | null; hi?: number | null; color?: string; className?: string
}) {
  const v = Math.max(0, Math.min(100, value ?? 0))
  const l = lo == null ? null : Math.max(0, Math.min(100, lo))
  const h = hi == null ? null : Math.max(0, Math.min(100, hi))
  return (
    <div className={cn('flex items-center gap-2.5', className)}>
      <div className="relative h-2 flex-1 overflow-hidden rounded-full bg-panel-2 ring-1 ring-line">
        {l != null && h != null && (
          <div className="absolute inset-y-0 rounded-full bg-ink/10" style={{ left: `${l}%`, width: `${Math.max(h - l, 0)}%` }} />
        )}
        <motion.div initial={{ width: 0 }} animate={{ width: `${v}%` }} transition={{ duration: 0.6, ease: 'easeOut' }}
          className="absolute inset-y-0 left-0 rounded-full" style={{ background: `linear-gradient(90deg, ${color}66, ${color})` }} />
      </div>
      <span className="tabular w-10 text-right text-[13px] font-semibold text-ink">{fmt(value)}</span>
    </div>
  )
}

export function ReliabilityPill({ value }: { value: number | null | undefined }) {
  const t = reliabilityTier(value)
  return (
    <Badge tone={t.tone} title="Reliability measures how certain the rating is (sample size and match coverage), not how good the player is.">
      <span className="tabular">{fmt(value, 0)}</span>
      <span className="opacity-70">· {t.label}</span>
    </Badge>
  )
}

export function Delta({ value, digits = 1, invert = false, suffix = '' }: { value: number | null | undefined; digits?: number; invert?: boolean; suffix?: string }) {
  if (value == null || Number.isNaN(value)) return <span className="text-faint">–</span>
  const good = invert ? value < 0 : value > 0
  return (
    <span className={cn('tabular whitespace-nowrap font-semibold', good ? 'text-emerald' : value === 0 ? 'text-dim' : 'text-brand-2')}>
      {value > 0 ? '▲' : value < 0 ? '▼' : '•'} {Math.abs(value).toFixed(digits)}{suffix}
    </span>
  )
}

export function RankMedal({ rank }: { rank: number | null | undefined }) {
  if (rank == null) return <span className="text-faint">–</span>
  const style = rank === 1 ? 'from-gold to-amber-600 text-black' : rank === 2 ? 'from-slate-200 to-slate-400 text-black'
    : rank === 3 ? 'from-orange-300 to-orange-700 text-black' : 'from-panel-2 to-panel-2 text-ink ring-1 ring-line'
  return <span className={cn('tabular grid h-7 w-7 place-items-center rounded-lg bg-gradient-to-br text-[12px] font-bold', style)}>{rank}</span>
}

export function PageHeader({ eyebrow, title, desc, actions }: { eyebrow?: string; title: ReactNode; desc?: ReactNode; actions?: ReactNode }) {
  return (
    <div className="flex flex-col gap-4 md:flex-row md:items-end md:justify-between">
      <div>
        {eyebrow && <p className="text-[11px] font-semibold uppercase tracking-[0.18em] text-brand-2">{eyebrow}</p>}
        <h1 className="mt-1 text-2xl font-bold tracking-tight text-ink md:text-[28px]">{title}</h1>
        {desc && <p className="mt-1.5 max-w-3xl text-[13.5px] leading-relaxed text-dim">{desc}</p>}
      </div>
      {actions}
    </div>
  )
}

export function ChartTooltip({ active, payload, label, formatter }: {
  active?: boolean; payload?: { name: string; value: number; color: string; dataKey: string }[]; label?: string | number;
  formatter?: (v: number, name: string) => string
}) {
  if (!active || !payload?.length) return null
  return (
    <div className="rounded-xl border border-line bg-panel/95 px-3 py-2 text-xs shadow-xl backdrop-blur">
      {label !== undefined && <div className="mb-1 font-semibold text-ink">{label}</div>}
      {payload.map((p) => (
        <div key={p.dataKey + p.name} className="flex items-center gap-2 text-dim">
          <span className="h-2 w-2 rounded-full" style={{ background: p.color }} />
          <span>{p.name}</span>
          <span className="tabular ml-auto pl-3 font-semibold text-ink">{formatter ? formatter(p.value, p.name) : typeof p.value === 'number' ? p.value.toFixed(2) : p.value}</span>
        </div>
      ))}
    </div>
  )
}
