import { readFileSync } from 'node:fs'
import { dirname, resolve as resolvePath } from 'node:path'
import { fileURLToPath } from 'node:url'
import { describe, expect, it } from 'vitest'

// Read as text rather than rendered: jsdom applies no scoped-SFC styles, so a
// mounted component reports no colours at all. Same approach as
// components/support/__tests__/statusBadgeContrast.spec.ts. main.css goes
// through the file system, as in ticketMutedContrast.spec.ts: a `?raw` CSS
// import comes back empty under vitest.
import PAGE from '@/views/admin/tickets/TicketAnalyticsPage.vue?raw'
import BARS from '../MeasureBars.vue?raw'
import TILE from '../StatTile.vue?raw'

/**
 * The analytics page's colours, held to WCAG AA in both themes.
 *
 * React never had a dark palette for this page (U4 AN-37), and the brand
 * green the portal uses for marks is not redefined by the dark theme, where
 * it falls to 2.79:1 on a card. So every colour this page picks is checked
 * here against the ground it actually sits on:
 *   - text against 4.5:1;
 *   - the bars and the focus ring, which are not text, against 3:1.
 *
 * Grounds come from main.css (the card is --white, the page is --bg-light,
 * both redefined for dark). The ratios are computed here, the thresholds are
 * written out, and nothing expected is read back from the component.
 */

const MAIN_CSS = readFileSync(
  resolvePath(dirname(fileURLToPath(import.meta.url)), '../../../../../assets/main.css'),
  'utf8'
)

const AA_TEXT = 4.5
const AA_NON_TEXT = 3

type Theme = 'light' | 'dark'

function escape(selector: string): string {
  return selector.replace(/[.*+?^${}()|[\]\\]/g, '\\$&')
}

function block(source: string, selector: string): string {
  const match = source.match(new RegExp(`(^|\\n)${escape(selector)}\\s*\\{([^}]*)\\}`))
  if (!match) throw new Error(`no rule for ${selector}`)
  return match[2]!
}

function declaration(rule: string, property: string): string {
  const match = rule.match(new RegExp(`(^|[\\s;{])${escape(property)}\\s*:\\s*([^;]+);`))
  if (!match) throw new Error(`no ${property} in ${JSON.stringify(rule)}`)
  return match[2]!.trim()
}

// A token's value in main.css for the given theme; the dark block only lists
// what it changes, so anything it leaves out is the light value.
function token(name: string, theme: Theme): string {
  if (theme === 'dark') {
    const dark = block(MAIN_CSS, ':root[data-theme="dark"]')
    if (new RegExp(`${escape(name)}\\s*:`).test(dark)) return declaration(dark, name)
  }
  return declaration(block(MAIN_CSS, ':root'), name)
}

function resolve(value: string, theme: Theme): string {
  const reference = /^var\((--[\w-]+)\)$/.exec(value)
  return reference ? resolve(token(reference[1]!, theme), theme) : value
}

// The colour a component sets on `selector` for `property`, in a theme.
function colour(source: string, selector: string, property: string, theme: Theme): string {
  const rule = theme === 'dark' ? block(source, `:root[data-theme='dark'] ${selector}`) : block(source, selector)
  return resolve(declaration(rule, property), theme)
}

function channel(value: number): number {
  const c = value / 255
  return c <= 0.04045 ? c / 12.92 : ((c + 0.055) / 1.055) ** 2.4
}

function luminance(hex: string): number {
  const m = /^#([0-9a-f]{2})([0-9a-f]{2})([0-9a-f]{2})$/i.exec(hex)
  if (!m) throw new Error(`not an opaque hex colour: ${hex}`)
  const [r, g, b] = m.slice(1).map((pair) => channel(parseInt(pair, 16)))
  return 0.2126 * r! + 0.7152 * g! + 0.0722 * b!
}

function contrast(a: string, b: string): number {
  const x = luminance(a)
  const y = luminance(b)
  return (Math.max(x, y) + 0.05) / (Math.min(x, y) + 0.05)
}

const card = (theme: Theme) => resolve('var(--white)', theme)
const page = (theme: Theme) => resolve('var(--bg-light)', theme)

describe('ticket analytics colours', () => {
  for (const theme of ['light', 'dark'] as const) {
    it(`${theme}: the bars stand out from the card`, () => {
      const bar = colour(BARS, '.measure-bars', '--measure-bar', theme)
      expect(contrast(bar, card(theme))).toBeGreaterThanOrEqual(AA_NON_TEXT)
    })

    it(`${theme}: the axis, the table toggle and the empty sentence are readable on the card`, () => {
      const muted = colour(BARS, '.measure-bars', '--measure-muted', theme)
      const empty = colour(BARS, '.measure-bars__empty', 'color', theme)
      expect(contrast(muted, card(theme))).toBeGreaterThanOrEqual(AA_TEXT)
      expect(contrast(empty, card(theme))).toBeGreaterThanOrEqual(AA_TEXT)
    })

    it(`${theme}: a tile's label and hint are readable on the card`, () => {
      const muted = colour(TILE, '.stat-tile', '--stat-muted', theme)
      expect(contrast(muted, card(theme))).toBeGreaterThanOrEqual(AA_TEXT)
    })

    it(`${theme}: the subtitle, the window echo and the errors are readable where they sit`, () => {
      const muted = colour(PAGE, '.ticket-analytics', '--analytics-muted', theme)
      const danger = colour(PAGE, '.ticket-analytics', '--analytics-danger', theme)
      // On the page ground: the subtitle, the echo, "Loading…", the page alert.
      expect(contrast(muted, page(theme))).toBeGreaterThanOrEqual(AA_TEXT)
      expect(contrast(danger, page(theme))).toBeGreaterThanOrEqual(AA_TEXT)
      // On the card: the roster warning in the breakdown card.
      expect(contrast(danger, card(theme))).toBeGreaterThanOrEqual(AA_TEXT)
    })
  }

  it('dark: the focus ring is visible on the card', () => {
    // The global ring is --dark-green, which dark does not redefine.
    const ring = declaration(
      block(PAGE, ":root[data-theme='dark'] .ticket-analytics :deep(:focus-visible)"),
      'outline-color'
    )
    expect(contrast(ring, card('dark'))).toBeGreaterThanOrEqual(AA_NON_TEXT)
    expect(contrast(resolve('var(--dark-green)', 'dark'), card('dark'))).toBeLessThan(AA_NON_TEXT)
  })

  it('draws every bar in the one colour, and a tile value on one line', () => {
    expect(declaration(block(BARS, '.measure-bars__bar'), 'background')).toBe('var(--measure-bar)')
    // Rounded at the data end only, anchored to the baseline.
    expect(declaration(block(BARS, '.measure-bars__bar'), 'border-radius')).toBe('0 4px 4px 0')
    // A duration reads as two numbers when it wraps: "33h" above "58m".
    expect(declaration(block(TILE, '.stat-tile__value'), 'white-space')).toBe('nowrap')
  })
})
