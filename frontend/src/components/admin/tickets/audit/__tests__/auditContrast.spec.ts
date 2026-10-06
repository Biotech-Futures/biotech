import { readFileSync } from 'node:fs'
import { dirname, resolve } from 'node:path'
import { fileURLToPath } from 'node:url'
import { describe, expect, it } from 'vitest'

import AUDIT_PAGE from '@/views/admin/tickets/TicketAuditPage.vue?raw'
import AUDIT_TABLE from '../TicketAuditTable.vue?raw'
import AUDIT_PAGER from '../AuditPager.vue?raw'

/**
 * The ticket audit page's colours, held to WCAG AA in both themes.
 *
 * jsdom applies no scoped styles, so this reads the three files' own
 * stylesheets and main.css and measures, the way
 * components/support/__tests__/ticketMutedContrast.spec.ts does for the
 * requester's side. Two traps U1 section 5.3 lists are what this is for:
 * --text-muted and --danger are under AA on --bg-light, and --dark-green is
 * not redefined in the dark theme, so green text or a green focus ring on a
 * dark surface is 2.79:1.
 *
 * Grounds are read from main.css, not written out here, so a token moving
 * there is caught.
 */

// Read off disk: Vitest stubs CSS imports to an empty string, and `?raw` on
// a stylesheet would hand every regex below nothing to find.
const STYLESHEET = readFileSync(
  resolve(dirname(fileURLToPath(import.meta.url)), '../../../../../assets/main.css'),
  'utf8'
)

const AA_TEXT = 4.5
// A focus indicator is a non-text contrast: 3:1 (WCAG 1.4.11).
const AA_NON_TEXT = 3

type Rgb = [number, number, number]

function block(dark: boolean): string {
  const match = dark
    ? STYLESHEET.match(/:root\[data-theme="dark"\]\s*\{([^}]*)\}/)
    : STYLESHEET.match(/(^|\n):root\s*\{([^}]*)\}/)
  if (!match) throw new Error(`no ${dark ? 'dark' : 'light'} :root block in main.css`)
  return match[dark ? 1 : 2]
}

function token(name: string, dark: boolean): string {
  const match = block(dark).match(new RegExp(`${name}\\s*:\\s*([^;]+);`))
  if (!match) {
    // Dark only redefines some tokens; the rest keep their light value.
    if (dark) return token(name, false)
    throw new Error(`no ${name} in main.css`)
  }
  return match[1].trim()
}

function colour(value: string, dark: boolean): { rgb: Rgb; alpha: number } {
  const reference = /^var\((--[a-z0-9-]+)\)$/i.exec(value)
  if (reference) return colour(token(reference[1], dark), dark)
  const hex = /^#([0-9a-f]{2})([0-9a-f]{2})([0-9a-f]{2})$/i.exec(value)
  if (hex) {
    const [r, g, b] = hex.slice(1).map((pair) => parseInt(pair, 16))
    return { rgb: [r, g, b], alpha: 1 }
  }
  if (/^#fff$/i.test(value)) return { rgb: [255, 255, 255], alpha: 1 }
  const rgba = /^rgba?\(([^)]*)\)$/.exec(value)
  if (rgba) {
    const parts = rgba[1].split(',').map((part) => Number(part.trim()))
    return { rgb: [parts[0], parts[1], parts[2]], alpha: parts.length > 3 ? parts[3] : 1 }
  }
  throw new Error(`not a colour this test can measure: ${value}`)
}

function opaque(value: string, dark: boolean): Rgb {
  const parsed = colour(value, dark)
  if (parsed.alpha !== 1) throw new Error(`text colour is not opaque: ${value}`)
  return parsed.rgb
}

// "--light-green over --white" mixes a translucent token over what is behind
// it, the way the browser paints it.
function ground(spec: string, dark: boolean): Rgb {
  const [front, behind] = spec.split(' over ')
  const top = colour(`var(${front})`, dark)
  if (top.alpha === 1) return top.rgb
  if (!behind) throw new Error(`${spec} is translucent and nothing was named behind it`)
  const back = ground(behind, dark)
  return top.rgb.map((value, i) => top.alpha * value + (1 - top.alpha) * back[i]) as Rgb
}

const channel = (value: number) => {
  const c = value / 255
  return c <= 0.04045 ? c / 12.92 : ((c + 0.055) / 1.055) ** 2.4
}
const luminance = ([r, g, b]: Rgb) => 0.2126 * channel(r) + 0.7152 * channel(g) + 0.0722 * channel(b)
function contrast(a: Rgb, b: Rgb): number {
  const x = luminance(a)
  const y = luminance(b)
  return (Math.max(x, y) + 0.05) / (Math.min(x, y) + 0.05)
}

function stylesheetOf(sfc: string): string {
  const style = (sfc.match(/<style scoped>([\s\S]*)<\/style>/) as RegExpMatchArray)[1]
  return style.replace(/\/\*[\s\S]*?\*\//g, '')
}

function rules(sfc: string): Array<{ selector: string; body: string }> {
  // Media blocks unwrapped rather than dropped: a rule inside one still paints.
  const css = stylesheetOf(sfc).replace(/@media[^{]*\{([\s\S]*?)\n\}/g, '$1')
  const out: Array<{ selector: string; body: string }> = []
  for (const [, selectors, body] of css.matchAll(/([^{}@]+)\{([^}]*)\}/g)) {
    for (const selector of selectors.split(',')) out.push({ selector: selector.trim(), body })
  }
  return out
}

function declared(sfc: string, custom: string, dark: boolean): { selector: string; value: string } {
  const found = rules(sfc)
    .filter(({ selector }) => selector.includes("[data-theme='dark']") === dark)
    .map(({ selector, body }) => ({
      selector,
      match: body.match(new RegExp(`${custom}\\s*:\\s*([^;]+);`))
    }))
    .filter(({ match }) => match)
  // Exactly one place each, or "which one wins" is a question with no answer.
  expect(found.map(({ selector }) => selector)).toHaveLength(1)
  return { selector: found[0]!.selector, value: found[0]!.match![1].trim() }
}

function rootClass(sfc: string): string {
  const template = (sfc.match(/<template>([\s\S]*?)\n<\/template>/) as RegExpMatchArray)[1]
  // The first element tag, skipping comments.
  const withoutComments = template.replace(/<!--[\s\S]*?-->/g, '')
  const firstTag = (withoutComments.match(/<[a-zA-Z][^>]*>/) as RegExpMatchArray)[0]
  const classes = (firstTag.match(/\sclass="([^"]*)"/) as RegExpMatchArray)[1]
  return classes.trim().split(/\s+/)[0]!
}

// The first class of every element a keyboard can land on: form controls,
// buttons, links and anything given a tabindex. Read off the template, so a
// control added later is on this list whether or not anybody remembers it.
function focusableClasses(sfc: string): string[] {
  const template = (sfc.match(/<template>([\s\S]*?)\n<\/template>/) as RegExpMatchArray)[1].replace(
    /<!--[\s\S]*?-->/g,
    ''
  )
  const tags =
    template.match(
      /<(?:select|input|textarea|button|a|RouterLink)\b[^>]*>|<[a-zA-Z][\w-]*\s[^>]*\btabindex=[^>]*>/g
    ) ?? []
  const classes = tags.map((tag) => {
    const found = tag.match(/\sclass="([^"]*)"/)
    if (!found) throw new Error(`a focusable element with no class to style: ${tag}`)
    return found[1].trim().split(/\s+/)[0]!
  })
  return [...new Set(classes)]
}

type Painted = { custom: string; light: string[]; dark: string[] }

// What each file paints with which property, on which grounds, and which
// controls in it can take keyboard focus.
const FILES: Record<string, { source: string; painted: Painted[]; focusable: string[] }> = {
  'TicketAuditPage.vue': {
    source: AUDIT_PAGE,
    // The two filters, and the alert that takes focus when it replaces the
    // footer.
    focusable: ['ticket-audit__filter', 'ticket-audit__error'],
    painted: [
      // Subtitle and the error line, straight on the section's .content-area.
      { custom: '--audit-muted', light: ['--bg-light'], dark: ['--bg-light'] },
      { custom: '--audit-danger', light: ['--bg-light'], dark: ['--bg-light'] }
    ]
  },
  'TicketAuditTable.vue': {
    source: AUDIT_TABLE,
    // The scrolling region and the ticket links.
    focusable: ['audit-table', 'audit-table__link'],
    painted: [
      // The card, and the global thead / tbody tr:hover wash on it.
      {
        custom: '--audit-muted',
        light: ['--white', '--light-green'],
        dark: ['--white', '--light-green over --white']
      },
      {
        custom: '--audit-link',
        light: ['--white', '--light-green'],
        dark: ['--white', '--light-green over --white']
      }
    ]
  },
  'AuditPager.vue': {
    source: AUDIT_PAGER,
    // The size select, the custom size box, and every button (Presets and
    // the page buttons share one class).
    focusable: ['audit-pager__select', 'audit-pager__custom', 'audit-pager__btn'],
    painted: [{ custom: '--audit-muted', light: ['--bg-light'], dark: ['--bg-light'] }]
  }
}

describe('the ticket audit page colours', () => {
  it('measures against grounds read out of main.css', () => {
    // If --light-green stopped being translucent in dark, the mixing below
    // would be measuring something imaginary.
    expect(colour('var(--light-green)', true).alpha).toBeLessThan(1)
    expect(colour('var(--bg-light)', false).alpha).toBe(1)
  })

  for (const [file, { source, painted, focusable }] of Object.entries(FILES)) {
    describe(`${file}`, () => {
      for (const { custom, light, dark } of painted) {
        it(`declares ${custom} on its root element, light and dark`, () => {
          // A custom property reaches only what inherits it. Moved to a
          // sibling class, the file reads the same and every ratio below
          // still passes while the screen goes back to the failing token.
          const root = `.${rootClass(source)}`
          expect(declared(source, custom, false).selector).toBe(root)
          expect(declared(source, custom, true).selector).toBe(`:root[data-theme='dark'] ${root}`)
        })

        it(`${custom} clears AA on every ground it paints on, in both themes`, () => {
          const lightValue = opaque(declared(source, custom, false).value, false)
          for (const spec of light) {
            expect(contrast(lightValue, ground(spec, false))).toBeGreaterThanOrEqual(AA_TEXT)
          }
          const darkValue = opaque(declared(source, custom, true).value, true)
          for (const spec of dark) {
            expect(contrast(darkValue, ground(spec, true))).toBeGreaterThanOrEqual(AA_TEXT)
          }
        })
      }

      it('paints no text straight from a token that fails on these grounds', () => {
        // The regression this file exists for: each of these is fine
        // somewhere and wrong here, so every colour goes through a property
        // measured above.
        const css = stylesheetOf(source)
        expect(css).not.toMatch(/(^|[^-])color:\s*var\(--text-muted\)/)
        expect(css).not.toMatch(/(^|[^-])color:\s*var\(--danger\)/)
        expect(css).not.toMatch(/(^|[^-])color:\s*var\(--dark-green\)/)
      })

      it('gives the focus ring a colour that shows on the dark surface', () => {
        // The global ring is --dark-green, 2.79:1 on the dark card. Every
        // control in this file gets a dark override, measured here.
        const overrides = rules(source).filter(
          ({ selector, body }) =>
            selector.startsWith(":root[data-theme='dark']") &&
            selector.endsWith(':focus-visible') &&
            /outline-color:/.test(body)
        )
        expect(overrides.length).toBeGreaterThan(0)
        for (const { body } of overrides) {
          const value = (body.match(/outline-color:\s*([^;]+);/) as RegExpMatchArray)[1].trim()
          for (const spec of ['--white', '--bg-light']) {
            expect(contrast(opaque(value, true), ground(spec, true))).toBeGreaterThanOrEqual(
              AA_NON_TEXT
            )
          }
        }
      })

      it('overrides the dark focus ring on every control a keyboard can reach', () => {
        // "At least one override" was all the test above could say. A control
        // added without its own line in that rule keeps the global ring,
        // 2.79:1 on the dark card, and every ratio above still passes.
        expect(focusableClasses(source)).toEqual(focusable)
        const overridden = rules(source)
          .filter(
            ({ selector, body }) =>
              selector.startsWith(":root[data-theme='dark']") &&
              selector.endsWith(':focus-visible') &&
              /outline-color:/.test(body)
          )
          .map(({ selector }) => selector)
        for (const name of focusable) {
          expect(overridden).toContain(`:root[data-theme='dark'] .${name}:focus-visible`)
        }
      })
    })
  }

  it('puts white, not the --white surface token, on the current page', () => {
    // --white is a surface colour and turns green-black in the dark theme.
    const current = rules(AUDIT_PAGER).find(({ selector }) =>
      selector.endsWith("[aria-current='page']")
    )!
    expect(current.body).toMatch(/color:\s*#fff;/)
    expect(current.body).toMatch(/background:\s*var\(--dark-green\);/)
    for (const dark of [false, true]) {
      expect(contrast(opaque('#fff', dark), opaque('var(--dark-green)', dark))).toBeGreaterThanOrEqual(
        AA_TEXT
      )
    }
  })
})
