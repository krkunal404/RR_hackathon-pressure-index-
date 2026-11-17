import { render, screen } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { beforeEach, describe, expect, it } from 'vitest'
import { ThemeToggle } from '@/components/Layout'

describe('ThemeToggle', () => {
  beforeEach(() => {
    localStorage.clear()
    document.documentElement.className = 'light'
  })

  it('starts in light mode and switches to dark and back', async () => {
    render(<ThemeToggle />)
    const sw = screen.getByRole('switch')
    expect(sw).toHaveAttribute('aria-checked', 'true')
    expect(document.documentElement).toHaveClass('light')

    await userEvent.click(sw)
    expect(sw).toHaveAttribute('aria-checked', 'false')
    expect(document.documentElement).toHaveClass('dark')
    expect(document.documentElement).not.toHaveClass('light')

    await userEvent.click(sw)
    expect(document.documentElement).toHaveClass('light')
  })

  it('never saves dark mode', async () => {
    const { unmount } = render(<ThemeToggle />)
    await userEvent.click(screen.getByRole('switch'))
    expect(localStorage.length).toBe(0)
    unmount()
    render(<ThemeToggle />)
    expect(screen.getByRole('switch')).toHaveAttribute('aria-checked', 'true')
    expect(document.documentElement).toHaveClass('light')
  })
})
