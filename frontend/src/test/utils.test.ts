import { describe, expect, it, vi, afterEach } from 'vitest'
import { fmt, fmtInt, pct, reliabilityTier, signed } from '@/lib/utils'
import { get, num } from '@/lib/api'

describe('formatters', () => {
  it('handles nulls and NaN', () => {
    expect(fmt(null)).toBe('–')
    expect(fmt(Number.NaN)).toBe('–')
    expect(fmtInt(undefined)).toBe('–')
    expect(pct(null)).toBe('–')
  })
  it('formats numbers', () => {
    expect(fmt(12.345)).toBe('12.3')
    expect(fmt(6.5, 2)).toBe('6.50')
    expect(pct(0.843)).toBe('84%')
    expect(signed(3.21)).toBe('+3.2')
    expect(signed(-1.5, 2)).toBe('-1.50')
  })
  it('maps reliability into tiers without touching performance', () => {
    expect(reliabilityTier(60).label).toBe('High')
    expect(reliabilityTier(30).label).toBe('Medium')
    expect(reliabilityTier(10).label).toBe('Low')
  })
})

describe('api helpers', () => {
  afterEach(() => vi.restoreAllMocks())
  it('num() only returns finite numbers', () => {
    expect(num({ a: 1.5, b: 'x', c: null }, 'a')).toBe(1.5)
    expect(num({ b: 'x' }, 'b')).toBeNull()
  })
  it('get() drops empty and "All" params', async () => {
    const spy = vi.spyOn(globalThis, 'fetch').mockResolvedValue(new Response(JSON.stringify({ ok: 1 })))
    await get('/api/x', { competition: 'All', season: 2024, team: '', q: null })
    expect(spy).toHaveBeenCalledWith('/api/x?season=2024')
  })
  it('get() throws on HTTP errors', async () => {
    vi.spyOn(globalThis, 'fetch').mockResolvedValue(new Response('nope', { status: 500, statusText: 'Server Error' }))
    await expect(get('/api/bad')).rejects.toThrow('500')
  })
})
