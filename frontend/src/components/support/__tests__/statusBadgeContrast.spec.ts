import { describe, expect, it } from 'vitest'

// The stylesheet is read as text rather than rendered. jsdom applies no
// scoped-SFC styles, so a mounted badge reports no colours at all; the source
// is where the values actually live.
import SOURCE from '../TicketStatusBadge.vue?raw'

/**
 * The status badge's colours, held to WCAG AA from the component's own source.
 *
 * What went wrong: the badge took its two colours from global tokens, and the
 * dark theme redefines the background token but not the foreground one. Dark
 * "Open" ended up dark green on dark green. The same omission hit "In
 * progress" (--air-force-blue), and "Pending user" had a foreground that was
 * never a token at all, so no amount of tidying the dark block would have
 * reached it.
 *
 * Two things are asserted, because fixing one without the other leaves the
 * defect reachable:
 *
 *  - every pair clears 4.5:1, the threshold for text this size; and
 *  - both halves of every pair are literal colours, so the contrast cannot be
 *    changed from another file. A translucent background would do the same
 *    thing by a different route — it hands the real contrast to whichever
 *    ancestor paints underneath.
 *
 * The ratios are computed here from the numbers in the stylesheet rather than
 * copied from it, and the threshold is written out below. Reading the expected
 * values from the component would only prove the component uses the colours
 * it uses.
 */

const AA_NORMAL_TEXT = 4.5

const STATUSES = ['open', 'in_progress', 'pending_user', 'resolved'] as const

function ruleFor(status: string, theme: 'light' | 'dark'): string {
  const selector =
    theme === 'dark'
      ? String.raw`:root\[data-theme='dark'\] \.ticket-badge--${status}`
      : String.raw`\.ticket-badge--${status}`
  const match = SOURCE.match(new RegExp(`(^|\\n)${selector}\\s*\\{([^}]*)\\}`))
  if (!match) throw new Error(`no ${theme} rule for ${status}`)
  return match[2]
}

function declaration(rule: string, property: string): string {
  const match = rule.match(new RegExp(`${property}\\s*:\\s*([^;]+);`))
  if (!match) throw new Error(`no ${property} in ${JSON.stringify(rule)}`)
  return match[1].trim()
}

function channel(value: number): number {
  const c = value / 255
  return c <= 0.04045 ? c / 12.92 : ((c + 0.055) / 1.055) ** 2.4
}

function luminance(hex: string): number {
  const m = /^#([0-9a-f]{2})([0-9a-f]{2})([0-9a-f]{2})$/i.exec(hex)
  if (!m) throw new Error(`not an opaque hex colour: ${hex}`)
  const [r, g, b] = m.slice(1).map((pair) => channel(parseInt(pair, 16)))
  return 0.2126 * r + 0.7152 * g + 0.0722 * b
}

function contrast(foreground: string, background: string): number {
  const a = luminance(foreground)
  const b = luminance(background)
  return (Math.max(a, b) + 0.05) / (Math.min(a, b) + 0.05)
}

describe('TicketStatusBadge colours', () => {
  for (const theme of ['light', 'dark'] as const) {
    for (const status of STATUSES) {
      it(`${theme}: ${status} is readable`, () => {
        const rule = ruleFor(status, theme)
        const background = declaration(rule, 'background')
        const color = declaration(rule, 'color')

        // Not var(...), not rgba(...). Either one moves the real contrast out
        // of this file, which is how the dark theme broke in the first place.
        expect(background).toMatch(/^#[0-9a-f]{6}$/i)
        expect(color).toMatch(/^#[0-9a-f]{6}$/i)

        expect(contrast(color, background)).toBeGreaterThanOrEqual(AA_NORMAL_TEXT)
      })
    }
  }

  it('covers every status the app can render, in both themes', () => {
    // The list above is hand-written, and a hand-written list is exactly what
    // missed "In progress" and "Pending user" the first time. This ties it to
    // the statuses the API actually returns.
    const declared = Array.from(
      SOURCE.matchAll(/\.ticket-badge--([a-z_]+)\s*\{/g),
      (m) => m[1],
    )
    expect(new Set(declared)).toEqual(new Set(STATUSES))
    for (const status of STATUSES) {
      expect(declared.filter((s) => s === status)).toHaveLength(2)
    }
  })
})
