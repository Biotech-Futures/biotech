import { readFileSync } from 'node:fs'
import { dirname, resolve as resolvePath } from 'node:path'
import { fileURLToPath } from 'node:url'
import { describe, expect, it } from 'vitest'

// Read as text rather than rendered: jsdom applies no scoped-SFC styles, so a
// mounted component reports no colours at all. Same approach as
// components/support/__tests__/statusBadgeContrast.spec.ts. main.css goes
// through the file system, as in analyticsContrast.spec.ts: a `?raw` CSS
// import comes back empty under vitest.
import SECTION from '@/views/admin/tickets/TicketsSection.vue?raw'

/**
 * The focus ring on the Queue / Audit / Analytics switcher, held to the 3:1 a
 * focus indicator needs, in both themes.
 *
 * What went wrong: the global ring is --dark-green (main.css :focus-visible),
 * and the dark theme does not redefine that colour. On the dark rail it is
 * 2.79:1, so a keyboard user moving between the three links could not see
 * which one had focus. The audit, analytics and detail pages had already
 * fixed their own rings; this shell had not.
 *
 * The ring is drawn 2px outside the link, on the rail (--white). The page
 * ground (--bg-light) is measured too, in case the rail is ever made
 * narrower than the ring. The ratios are computed here, the threshold is
 * written out, and nothing expected is read back from the component.
 */

const MAIN_CSS = readFileSync(
  resolvePath(dirname(fileURLToPath(import.meta.url)), '../../../assets/main.css'),
  'utf8'
)

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

// The global ring's colour: the last word of main.css's `outline` shorthand
// on :focus-visible ("2px solid var(--dark-green)").
function globalRing(theme: Theme): string {
  const outline = declaration(block(MAIN_CSS, ':focus-visible'), 'outline')
  return resolve(outline.split(/\s+/).at(-1)!, theme)
}

// The ring a switcher link actually gets in a theme: this file's dark
// override when there is one, otherwise the global ring.
function switcherRing(theme: Theme): string {
  if (theme === 'light') return globalRing('light')
  const rule = block(SECTION, ":root[data-theme='dark'] .tickets-section__switch:focus-visible")
  return resolve(declaration(rule, 'outline-color'), 'dark')
}

const rail = (theme: Theme) => resolve('var(--white)', theme)
const page = (theme: Theme) => resolve('var(--bg-light)', theme)

describe('support queue section switcher focus ring', () => {
  for (const theme of ['light', 'dark'] as const) {
    it(`${theme}: the ring stands out from the rail and the page`, () => {
      const ring = switcherRing(theme)
      expect(contrast(ring, rail(theme))).toBeGreaterThanOrEqual(AA_NON_TEXT)
      expect(contrast(ring, page(theme))).toBeGreaterThanOrEqual(AA_NON_TEXT)
    })
  }

  it('dark: the global ring really does fail on the rail, so the override is needed', () => {
    // If the theme ever redefines --dark-green this goes red, and the
    // override above can be dropped.
    expect(contrast(globalRing('dark'), rail('dark'))).toBeLessThan(AA_NON_TEXT)
  })

  it('dark: the ring is the mint the audit, analytics and detail rings use', () => {
    expect(switcherRing('dark')).toBe('#5ea99e')
  })
})
