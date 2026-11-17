import * as React from 'react'
import { cva, type VariantProps } from 'class-variance-authority'
import { cn } from '@/lib/utils'

/* shadcn/ui-style primitives, themed for the platform. */

export function Card({ className, ...p }: React.HTMLAttributes<HTMLDivElement>) {
  return <div className={cn('glass rounded-2xl border border-line', className)} {...p} />
}

export function CardHeader({ title, subtitle, action, className, icon }: {
  title: React.ReactNode; subtitle?: React.ReactNode; action?: React.ReactNode; className?: string; icon?: React.ReactNode
}) {
  return (
    <div className={cn('flex items-start justify-between gap-4 px-5 pt-5', className)}>
      <div className="flex min-w-0 items-start gap-3">
        {icon && <div className="mt-0.5 grid h-8 w-8 shrink-0 place-items-center rounded-lg bg-panel-2 text-brand-2 ring-1 ring-line">{icon}</div>}
        <div className="min-w-0">
          <h3 className="text-[15px] font-semibold tracking-tight text-ink">{title}</h3>
          {subtitle && <p className="mt-0.5 text-[12.5px] leading-snug text-dim">{subtitle}</p>}
        </div>
      </div>
      {action}
    </div>
  )
}

export function CardBody({ className, ...p }: React.HTMLAttributes<HTMLDivElement>) {
  return <div className={cn('p-5', className)} {...p} />
}

const badgeV = cva('inline-flex items-center gap-1 rounded-full px-2 py-0.5 text-[11px] font-semibold ring-1 ring-inset whitespace-nowrap', {
  variants: {
    tone: {
      default: 'bg-panel-2 text-dim ring-line',
      brand: 'bg-brand/10 text-brand-2 ring-brand/30',
      good: 'bg-emerald/10 text-emerald ring-emerald/30',
      warn: 'bg-gold/10 text-gold ring-gold/30',
      bad: 'bg-brand/10 text-brand-2 ring-brand/30',
      sky: 'bg-sky/10 text-sky ring-sky/30',
      violet: 'bg-violet/10 text-violet ring-violet/30',
      muted: 'bg-panel-2 text-faint ring-line',
    },
  },
  defaultVariants: { tone: 'default' },
})
export function Badge({ tone, className, ...p }: React.HTMLAttributes<HTMLSpanElement> & VariantProps<typeof badgeV>) {
  return <span className={cn(badgeV({ tone }), className)} {...p} />
}

const buttonV = cva('inline-flex items-center justify-center gap-2 rounded-lg text-sm font-medium transition-colors focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-brand/60 disabled:opacity-50', {
  variants: {
    variant: {
      default: 'bg-brand text-white hover:bg-brand-2',
      outline: 'border border-line bg-panel-2/60 text-ink hover:bg-panel-2',
      ghost: 'text-dim hover:bg-panel-2 hover:text-ink',
    },
    size: { sm: 'h-8 px-3', md: 'h-9 px-4', icon: 'h-9 w-9' },
  },
  defaultVariants: { variant: 'default', size: 'md' },
})
export function Button({ variant, size, className, ...p }: React.ButtonHTMLAttributes<HTMLButtonElement> & VariantProps<typeof buttonV>) {
  return <button className={cn(buttonV({ variant, size }), className)} {...p} />
}

export const Input = React.forwardRef<HTMLInputElement, React.InputHTMLAttributes<HTMLInputElement>>(
  ({ className, ...p }, ref) => (
    <input ref={ref} className={cn('h-9 w-full rounded-lg border border-line bg-panel-2/70 px-3 text-sm text-ink placeholder:text-faint outline-none focus:border-brand/60 focus:ring-2 focus:ring-brand/20', className)} {...p} />
  ),
)
Input.displayName = 'Input'

export function Select({ label, value, onChange, options, className, testId }: {
  label: string; value: string; onChange: (v: string) => void; options: { value: string; label: string }[]; className?: string; testId?: string
}) {
  return (
    <label className={cn('flex min-w-0 flex-col gap-1', className)}>
      <span className="text-[10.5px] font-semibold uppercase tracking-wider text-faint">{label}</span>
      <select
        data-testid={testId}
        aria-label={label}
        value={value}
        onChange={(e) => onChange(e.target.value)}
        className="h-9 w-full cursor-pointer rounded-lg border border-line bg-panel-2/70 px-2.5 text-sm text-ink outline-none focus:border-brand/60 focus:ring-2 focus:ring-brand/20"
      >
        {options.map((o) => <option key={o.value} value={o.value} className="bg-panel">{o.label}</option>)}
      </select>
    </label>
  )
}

export function Tabs<T extends string>({ value, onChange, items, className }: {
  value: T; onChange: (v: T) => void; items: { value: T; label: React.ReactNode }[]; className?: string
}) {
  return (
    <div role="tablist" className={cn('inline-flex rounded-xl border border-line bg-panel-2/60 p-1', className)}>
      {items.map((it) => (
        <button
          key={it.value}
          role="tab"
          aria-selected={value === it.value}
          onClick={() => onChange(it.value)}
          className={cn('rounded-lg px-3 py-1.5 text-[13px] font-medium transition-all',
            value === it.value ? 'bg-brand text-white shadow-[0_6px_20px_-8px_rgba(244,63,94,0.8)]' : 'text-dim hover:text-ink')}
        >
          {it.label}
        </button>
      ))}
    </div>
  )
}

export function Skeleton({ className }: { className?: string }) {
  return <div className={cn('animate-pulse rounded-lg bg-panel-2', className)} />
}

export function ErrorState({ error }: { error: unknown }) {
  return (
    <Card className="border-brand/40">
      <CardBody>
        <p className="font-semibold text-brand-2">Could not load data</p>
        <p className="mt-1 text-sm text-dim">{String((error as Error)?.message ?? error)}</p>
        <p className="mt-2 text-xs text-faint">Is the API running? <code className="font-mono">uvicorn backend.main:app --port 8000</code></p>
      </CardBody>
    </Card>
  )
}
