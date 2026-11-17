import { useQuery } from '@tanstack/react-query'
import { AnimatePresence, motion } from 'framer-motion'
import { Activity, BookOpenText, Flame, Gauge, Globe2, LayoutDashboard, Menu, Moon, Search, ShieldCheck, Sun, Swords, Target, X } from 'lucide-react'
import { useEffect, useRef, useState } from 'react'
import { NavLink, Outlet, useLocation, useNavigate } from 'react-router-dom'
import { api } from '@/lib/api'
import { useTheme } from '@/lib/theme'
import { cn, fmt } from '@/lib/utils'

const NAV = [
  { to: '/', label: 'Overview', icon: LayoutDashboard, end: true },
  { to: '/rankings/batters', label: 'Batters', icon: Swords },
  { to: '/rankings/bowlers', label: 'Bowlers', icon: Target },
  { to: '/explorer', label: 'Explorer', icon: Activity },
  { to: '/pressure', label: 'Pressure Lab', icon: Flame },
  { to: '/competitions', label: 'IPL vs T20I', icon: Globe2 },
  { to: '/methodology', label: 'Methodology', icon: BookOpenText },
  { to: '/validation', label: 'Validation', icon: ShieldCheck },
]

function GlobalSearch() {
  const [q, setQ] = useState('')
  const [open, setOpen] = useState(false)
  const nav = useNavigate()
  const ref = useRef<HTMLDivElement>(null)
  const { data } = useQuery({ queryKey: ['search', q], queryFn: () => api.search(q), enabled: q.length >= 2 })
  useEffect(() => {
    const h = (e: MouseEvent) => { if (!ref.current?.contains(e.target as Node)) setOpen(false) }
    document.addEventListener('mousedown', h)
    return () => document.removeEventListener('mousedown', h)
  }, [])
  return (
    <div ref={ref} className="relative w-full max-w-md">
      <Search className="pointer-events-none absolute left-3 top-1/2 h-4 w-4 -translate-y-1/2 text-faint" />
      <input
        aria-label="Search players"
        placeholder="Search any player…"
        value={q}
        onFocus={() => setOpen(true)}
        onChange={(e) => { setQ(e.target.value); setOpen(true) }}
        className="h-10 w-full rounded-xl border border-line bg-panel-2/70 pl-9 pr-3 text-sm text-ink placeholder:text-faint outline-none focus:border-brand/60 focus:ring-2 focus:ring-brand/20"
      />
      <AnimatePresence>
        {open && q.length >= 2 && (
          <motion.ul initial={{ opacity: 0, y: -4 }} animate={{ opacity: 1, y: 0 }} exit={{ opacity: 0, y: -4 }}
            className="absolute z-50 mt-2 max-h-80 w-full overflow-auto rounded-xl border border-line bg-panel p-1 shadow-2xl scroll-thin">
            {(data ?? []).length === 0 && <li className="px-3 py-2 text-sm text-faint">No players found</li>}
            {(data ?? []).map((p) => (
              <li key={`${p.role}-${p.player_id}`}>
                <button
                  className="flex w-full items-center justify-between rounded-lg px-3 py-2 text-left text-sm hover:bg-panel-2"
                  onClick={() => { nav(`/players/${p.role}/${p.player_id}`); setOpen(false); setQ('') }}
                >
                  <span>
                    <span className="font-medium text-ink">{p.name}</span>
                    <span className="ml-2 text-xs text-faint">{p.team}</span>
                  </span>
                  <span className="flex items-center gap-2 text-xs">
                    <span className={cn('rounded px-1.5 py-0.5', p.role === 'batters' ? 'bg-brand/10 text-brand-2' : 'bg-sky/10 text-sky')}>
                      {p.role === 'batters' ? 'BAT' : 'BOWL'}
                    </span>
                    <span className="tabular w-8 text-right text-dim">{p.eligible ? fmt(p.rating, 0) : 'n/e'}</span>
                  </span>
                </button>
              </li>
            ))}
          </motion.ul>
        )}
      </AnimatePresence>
    </div>
  )
}

export function ThemeToggle() {
  const { theme, toggle } = useTheme()
  const light = theme === 'light'
  return (
    <button
      type="button"
      role="switch"
      aria-checked={light}
      aria-label={light ? 'Switch to dark mode' : 'Switch to light mode'}
      title={light ? 'Switch to dark mode' : 'Switch to light mode'}
      onClick={toggle}
      data-testid="theme-toggle"
      className="relative inline-flex h-9 w-[68px] shrink-0 items-center rounded-full border border-line bg-panel-2 p-1 transition-colors focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-brand/60"
    >
      <Moon className={cn('absolute left-2 h-4 w-4 transition-opacity', light ? 'text-faint opacity-60' : 'opacity-0')} />
      <Sun className={cn('absolute right-2 h-4 w-4 transition-opacity', light ? 'opacity-0' : 'text-faint opacity-60')} />
      <motion.span
        layout
        transition={{ type: 'spring', stiffness: 500, damping: 32 }}
        className={cn('grid h-7 w-7 place-items-center rounded-full shadow-md', light ? 'ml-auto bg-gold text-white' : 'bg-brand text-white')}
      >
        {light ? <Sun className="h-4 w-4" /> : <Moon className="h-4 w-4" />}
      </motion.span>
    </button>
  )
}

function Brand() {
  return (
    <div className="flex items-center gap-2.5 px-2">
      <div className="relative grid h-9 w-9 place-items-center rounded-xl bg-gradient-to-br from-brand to-rose-700 shadow-[0_8px_24px_-8px_rgba(244,63,94,0.9)]">
        <Gauge className="h-5 w-5 text-white" />
      </div>
      <div className="leading-tight">
        <div className="text-[15px] font-bold tracking-tight text-ink">Pressure Index</div>
        <div className="text-[10.5px] font-medium uppercase tracking-[0.14em] text-faint">SupeRR Selector · S2</div>
      </div>
    </div>
  )
}

function NavItems({ onNav }: { onNav?: () => void }) {
  return (
    <nav className="mt-6 flex flex-col gap-1">
      {NAV.map(({ to, label, icon: Icon, end }) => (
        <NavLink key={to} to={to} end={end} onClick={onNav}
          className={({ isActive }) => cn('group flex items-center gap-3 rounded-xl px-3 py-2.5 text-[13.5px] font-medium transition-colors',
            isActive ? 'bg-brand/10 text-ink ring-1 ring-brand/25' : 'text-dim hover:bg-panel-2 hover:text-ink')}>
          {({ isActive }) => (
            <>
              <Icon className={cn('h-[18px] w-[18px]', isActive ? 'text-brand-2' : 'text-faint group-hover:text-dim')} />
              {label}
            </>
          )}
        </NavLink>
      ))}
    </nav>
  )
}

export default function Layout() {
  const [mobile, setMobile] = useState(false)
  const loc = useLocation()
  const { data: ov } = useQuery({ queryKey: ['overview'], queryFn: api.overview })
  useEffect(() => { window.scrollTo({ top: 0 }) }, [loc.pathname])
  return (
    <div className="flex min-h-full">
      <aside className="sticky top-0 hidden h-screen w-64 shrink-0 flex-col border-r border-line bg-panel/60 px-3 py-5 backdrop-blur lg:flex">
        <Brand />
        <NavItems />
        <div className="mt-auto rounded-xl border border-line bg-panel-2/60 p-3 text-[11.5px] leading-relaxed text-dim">
          <div className="font-semibold text-ink">Dataset</div>
          {ov ? <>IPL + T20I · {ov.seasons[0]}–{ov.seasons[ov.seasons.length - 1]}<br />{ov.matches} matches · {ov.deliveries.toLocaleString()} balls</> : '…'}
        </div>
      </aside>

      <AnimatePresence>
        {mobile && (
          <motion.div className="fixed inset-0 z-50 lg:hidden" initial={{ opacity: 0 }} animate={{ opacity: 1 }} exit={{ opacity: 0 }}>
            <div className="absolute inset-0 bg-black/60" onClick={() => setMobile(false)} />
            <motion.aside initial={{ x: -280 }} animate={{ x: 0 }} exit={{ x: -280 }} transition={{ type: 'tween', duration: 0.2 }}
              className="absolute inset-y-0 left-0 w-64 border-r border-line bg-panel px-3 py-5">
              <div className="flex items-center justify-between"><Brand /><button aria-label="Close menu" onClick={() => setMobile(false)}><X className="h-5 w-5 text-dim" /></button></div>
              <NavItems onNav={() => setMobile(false)} />
            </motion.aside>
          </motion.div>
        )}
      </AnimatePresence>

      <div className="flex min-w-0 flex-1 flex-col">
        <header className="sticky top-0 z-40 flex items-center gap-3 border-b border-line bg-bg/70 px-4 py-3 backdrop-blur md:px-8">
          <button aria-label="Open menu" className="lg:hidden" onClick={() => setMobile(true)}><Menu className="h-5 w-5 text-dim" /></button>
          <GlobalSearch />
          <div className="ml-auto hidden items-center gap-2 text-[12px] text-faint md:flex">
            <span className="relative flex h-2 w-2"><span className="absolute inline-flex h-full w-full animate-ping rounded-full bg-emerald opacity-60" /><span className="relative inline-flex h-2 w-2 rounded-full bg-emerald" /></span>
            Model run {ov ? new Date(ov.generated_at).toLocaleDateString(undefined, { day: 'numeric', month: 'short', year: 'numeric' }) : '…'}
          </div>
          <div className="ml-auto md:ml-0"><ThemeToggle /></div>
        </header>
        <main className="mx-auto w-full max-w-[1400px] flex-1 px-4 py-6 md:px-8 md:py-8">
          <motion.div key={loc.pathname} initial={{ opacity: 0, y: 6 }} animate={{ opacity: 1, y: 0 }} transition={{ duration: 0.25 }}>
            <Outlet />
          </motion.div>
        </main>
        <footer className="border-t border-line px-8 py-4 text-[11.5px] text-faint">
          Every figure is computed from the supplied IPL &amp; T20I ball-by-ball data (2022+). Ratings are shrunk Bayesian estimates; reliability is reported separately.
        </footer>
      </div>
    </div>
  )
}
