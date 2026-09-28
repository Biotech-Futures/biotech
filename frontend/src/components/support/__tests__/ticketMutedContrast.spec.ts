import { readFileSync } from 'node:fs'
import { dirname, resolve } from 'node:path'
import { fileURLToPath } from 'node:url'
import { describe, expect, it } from 'vitest'

// Read off disk rather than imported. Vitest stubs CSS modules out to an empty
// string, so `?raw` on a stylesheet would hand every regex below nothing to
// find and every assertion would pass on air. Built with node:path rather than
// `new URL('...', import.meta.url)`, which Vite rewrites into a served asset
// URL before node ever sees it.
const STYLESHEET = readFileSync(
  resolve(dirname(fileURLToPath(import.meta.url)), '../../../assets/main.css'),
  'utf8',
)

import PRIORITY_BADGE from '../TicketPriorityBadge.vue?raw'
import TIMELINE from '../TicketTimeline.vue?raw'
import MY_TICKETS_TABLE from '../MyTicketsTable.vue?raw'
import TICKET_DETAIL_PAGE from '@/views/TicketDetailPage.vue?raw'

/**
 * The quiet text on a ticket, held to WCAG AA.
 *
 * What went wrong: every muted line took --text-muted, which is #6c757d, and
 * none of these components paint a background of their own. The ground is
 * whichever ancestor does, and on the Support Centre that is one of three
 * light tokens. #6c757d is 4.45:1 on two of them and 4.10:1 on the third, all
 * under the 4.5:1 these files hold themselves to. The priority badge's own
 * comment measured its High variant against exactly this ground and still let
 * its two siblings take the failing token, because they were never measured.
 *
 * The badge was one of ten places on the same two pages. So the assertion is
 * not "the badge is readable", it is "no file in this feature paints text with
 * the failing tokens, and the replacements clear AA against every ground the
 * feature actually uses".
 *
 * Ratios are computed here from the numbers in the stylesheets rather than
 * copied out of them, and the grounds are read from main.css rather than
 * written out, so a token moving in either place is caught.
 *
 * Three things this file could not see on the first pass, all three found by
 * moving a declaration and watching nothing go red:
 *
 *  - a custom property only reaches the text below where it is declared, and
 *    matching CSS as text cannot tell where that is. So the declaration is
 *    pinned to the class on the component's own root element.
 *  - dark was only checked by string equality, never measured. It is measured
 *    now, and the table head turned out to be 4.4938:1 there.
 *  - the opacity check read the whole file, template and script included, so
 *    any future opacity anywhere would have failed it for no reason. It is
 *    scoped to the rules that paint muted text and their descendants.
 */

const AA_NORMAL_TEXT = 4.5

// The light backgrounds a ticket paints muted text on: .content-area and the
// system-note pill (--bg-light), the support bubble (--surface-elevated), and
// the requester's own bubble and the table head (--light-green). Every file is
// held to all three in light, because all three are opaque hex there and one
// value clears the lot.
const GROUND_TOKENS = ['--bg-light', '--surface-elevated', '--light-green']

// Dark needs naming per file. --light-green is translucent there, so what a
// ratio comes out as depends on what is behind the green: the card for the
// table head, the page for the requester's own bubble.
const DARK_GROUNDS: Record<string, string[]> = {
  // The badge paints no background and is only ever rendered in the enquiry
  // header, which sits straight on the page.
  'TicketPriorityBadge.vue': ['--bg-light'],
  // System notes on the page, meta lines inside both kinds of bubble.
  'TicketTimeline.vue': ['--bg-light', '--surface-elevated', '--light-green over --bg-light'],
  // The head row takes the global thead --light-green, and SupportCentrePage
  // wraps the table in a --surface-elevated card. The empty line is on that
  // same card.
  'MyTicketsTable.vue': ['--surface-elevated', '--light-green over --surface-elevated'],
  // Number, meta and state all sit straight on the page.
  'TicketDetailPage.vue': ['--bg-light'],
}

const SOURCES: Record<string, string> = {
  'TicketPriorityBadge.vue': PRIORITY_BADGE,
  'TicketTimeline.vue': TIMELINE,
  'MyTicketsTable.vue': MY_TICKETS_TABLE,
  'TicketDetailPage.vue': TICKET_DETAIL_PAGE,
}

function lightRootBlock(): string {
  // The first :root block, not the [data-theme="dark"] one that follows it.
  const match = STYLESHEET.match(/(^|\n):root\s*\{([^}]*)\}/)
  if (!match) throw new Error('no :root block in main.css')
  return match[2]
}

function darkRootBlock(): string {
  const match = STYLESHEET.match(/:root\[data-theme="dark"\]\s*\{([^}]*)\}/)
  if (!match) throw new Error('no dark :root block in main.css')
  return match[1]
}

function token(name: string, dark = false): string {
  const block = dark ? darkRootBlock() : lightRootBlock()
  const match = block.match(new RegExp(`${name}\\s*:\\s*([^;]+);`))
  // Dark only redefines some of them; the rest keep their light value.
  if (!match) {
    if (dark) return token(name)
    throw new Error(`no ${name} in the light :root block`)
  }
  return match[1].trim()
}

type Rgb = [number, number, number]

function colour(value: string): { rgb: Rgb; alpha: number } {
  const hex = /^#([0-9a-f]{2})([0-9a-f]{2})([0-9a-f]{2})$/i.exec(value)
  if (hex) {
    const [r, g, b] = hex.slice(1).map((pair) => parseInt(pair, 16))
    return { rgb: [r, g, b], alpha: 1 }
  }
  const rgba = /^rgba?\(([^)]*)\)$/.exec(value)
  if (rgba) {
    const parts = rgba[1].split(',').map((part) => Number(part.trim()))
    return { rgb: [parts[0], parts[1], parts[2]], alpha: parts.length > 3 ? parts[3] : 1 }
  }
  throw new Error(`not a colour this test can measure: ${value}`)
}

// "--light-green over --surface-elevated" resolves the green, resolves what is
// behind it, and mixes them the way the browser paints them.
function ground(spec: string, dark: boolean): Rgb {
  const [front, behind] = spec.split(' over ')
  const top = colour(token(front, dark))
  if (top.alpha === 1) return top.rgb
  if (!behind) throw new Error(`${spec} is translucent and nothing was named behind it`)
  const back = ground(behind, dark)
  return top.rgb.map((value, i) => top.alpha * value + (1 - top.alpha) * back[i]) as Rgb
}

function channel(value: number): number {
  const c = value / 255
  return c <= 0.04045 ? c / 12.92 : ((c + 0.055) / 1.055) ** 2.4
}

function luminance([r, g, b]: Rgb): number {
  return 0.2126 * channel(r) + 0.7152 * channel(g) + 0.0722 * channel(b)
}

function contrast(foreground: Rgb, background: Rgb): number {
  const a = luminance(foreground)
  const b = luminance(background)
  return (Math.max(a, b) + 0.05) / (Math.min(a, b) + 0.05)
}

function opaque(value: string): Rgb {
  const parsed = colour(value)
  if (parsed.alpha !== 1) throw new Error(`text colour is not opaque: ${value}`)
  return parsed.rgb
}

function stylesheetOf(sfc: string): string {
  // Only the scoped stylesheet, and without its comments: the template above
  // it is full of {{ }}, and a comment sitting on top of a rule reads as part
  // of that rule's selector.
  const style = (sfc.match(/<style scoped>([\s\S]*)<\/style>/) as RegExpMatchArray)[1]
  return style.replace(/\/\*[\s\S]*?\*\//g, '')
}

function flatten(css: string): string {
  // Media blocks unwrapped rather than dropped: a rule inside one still paints.
  return (css.match(/@media[^{]*\{[\s\S]*?\n\}/g) || []).reduce(
    (text, block) =>
      text.replace(block, block.replace(/^@media[^{]*\{/, '').replace(/\n\}$/, '')),
    css,
  )
}

function rules(sfc: string): Array<{ selector: string; body: string }> {
  const out: Array<{ selector: string; body: string }> = []
  for (const [, selectors, body] of flatten(stylesheetOf(sfc)).matchAll(
    /([^{}@]+)\{([^}]*)\}/g,
  )) {
    for (const selector of selectors.split(',')) out.push({ selector: selector.trim(), body })
  }
  return out
}

function lightValue(sfc: string, custom: string): string | null {
  // Declarations outside the dark override, which redefines the same name.
  const withoutDark = sfc.replace(/:root\[data-theme="dark"\][^{]*\{[^}]*\}/g, '')
  const match = withoutDark.match(new RegExp(`${custom}\\s*:\\s*([^;]+);`))
  return match ? match[1].trim() : null
}

function darkValue(sfc: string, custom: string): string | null {
  const blocks = sfc.match(/:root\[data-theme="dark"\][^{]*\{[^}]*\}/g) || []
  for (const block of blocks) {
    const match = block.match(new RegExp(`${custom}\\s*:\\s*([^;]+);`))
    if (match) return match[1].trim()
  }
  return null
}

function resolvedDark(sfc: string): Rgb {
  const value = darkValue(sfc, '--ticket-muted') as string
  return opaque(value === 'var(--text-muted)' ? token('--text-muted', true) : value)
}

const DARK_PREFIX = ':root[data-theme="dark"] '

function declaringSelectors(sfc: string, custom: string): { light: string[]; dark: string[] } {
  const declaring = rules(sfc)
    .filter(({ body }) => new RegExp(`${custom}\\s*:`).test(body))
    .map(({ selector }) => selector)
  return {
    light: declaring.filter((selector) => !selector.includes('[data-theme=')),
    dark: declaring.filter((selector) => selector.startsWith(DARK_PREFIX)),
  }
}

function rootClasses(sfc: string): string[] {
  const template = (sfc.match(/<template>([\s\S]*?)\n<\/template>/) as RegExpMatchArray)[1]
  const firstTag = (template.match(/<[a-zA-Z][^>]*>/) as RegExpMatchArray)[0]
  const classes = firstTag.match(/\sclass="([^"]*)"/)
  if (!classes) throw new Error(`no class on the root element: ${firstTag}`)
  return classes[1].trim().split(/\s+/)
}

describe('muted text on a ticket', () => {
  it('reads the grounds it is measured against out of main.css', () => {
    // If this ever stops being three opaque hex colours in light the ratios
    // below are measuring something imaginary.
    for (const name of GROUND_TOKENS) {
      expect(token(name)).toMatch(/^#[0-9a-f]{6}$/i)
    }
    // And in dark the green really is translucent, which is the whole reason
    // DARK_GROUNDS has to say what is behind it.
    expect(colour(token('--light-green', true)).alpha).toBeLessThan(1)
  })

  for (const [file, source] of Object.entries(SOURCES)) {
    describe(file, () => {
      it('takes muted text from a literal, not the failing token', () => {
        const value = lightValue(source, '--ticket-muted')
        // A file that stopped declaring it would otherwise be skipped by every
        // assertion below and this list would quietly cover nothing.
        expect(value).toMatch(/^#[0-9a-f]{6}$/i)
      })

      it('declares it on the component root, where the text below can see it', () => {
        // A custom property reaches the text that inherits it and nothing
        // else. Moved to a sibling class the file still reads the same and
        // every ratio below still passes, while the screen goes back to the
        // colour that was being replaced.
        const { light, dark } = declaringSelectors(source, '--ticket-muted')
        expect(light).toHaveLength(1)
        // One plain class, so "is it on the root" is a question with an answer.
        expect(light[0]).toMatch(/^\.[a-z0-9_-]+$/)
        expect(rootClasses(source)).toContain(light[0].slice(1))
        // And the dark override on the same element, not a cousin of it.
        expect(dark).toEqual([`${DARK_PREFIX}${light[0]}`])
      })

      it('clears AA on every ground the feature paints on', () => {
        const value = opaque(lightValue(source, '--ticket-muted') as string)
        for (const name of GROUND_TOKENS) {
          expect(contrast(value, ground(name, false))).toBeGreaterThanOrEqual(AA_NORMAL_TEXT)
        }
      })

      it('says what muted text is in dark', () => {
        // Either the theme's own token or a value of its own, but one of them.
        expect(darkValue(source, '--ticket-muted')).toMatch(
          /^(var\(--text-muted\)|#[0-9a-f]{6})$/i,
        )
      })

      it('clears AA in dark as well, on the grounds this file sits on', () => {
        // Measured, not asserted by name. Handing the colour back to the theme
        // is fine on three of these four and is 4.4938:1 on the table head.
        for (const spec of DARK_GROUNDS[file]) {
          expect(contrast(resolvedDark(source), ground(spec, true))).toBeGreaterThanOrEqual(
            AA_NORMAL_TEXT,
          )
        }
      })

      it('paints no text with --text-muted or --danger', () => {
        // The regression this file exists for. Both tokens are fine somewhere
        // and wrong here, so the check is on the declaration, not the token.
        const stylesheet = stylesheetOf(source)
        expect(stylesheet).not.toMatch(/color:\s*var\(--text-muted\)/)
        expect(stylesheet).not.toMatch(/color:\s*var\(--danger\)/)
      })

      it('does not fade muted text with opacity', () => {
        // Opacity mixes the ground back in and puts the ratio under AA again.
        // 0.75 on the system note's timestamp cost 5.29:1 down to 3.19:1.
        //
        // Only the rules that paint muted text and the rules below them. An
        // opacity somewhere else in the file, on a disabled button or a hover,
        // has nothing to do with this. The one case this cannot see is an
        // opacity on an ancestor that is not itself a muted rule.
        const painted = rules(source)
          .filter(({ body }) => /color:\s*var\(--ticket-muted\)/.test(body))
          .map(({ selector }) => selector)
        const faded = rules(source)
          .filter(
            ({ selector, body }) =>
              /(^|\n|;)\s*opacity\s*:/.test(body) &&
              painted.some((one) => selector === one || selector.startsWith(`${one} `)),
          )
          .map(({ selector }) => selector)
        expect(faded).toEqual([])
      })
    })
  }

  it('the error line on a ticket clears AA too', () => {
    // --danger is 4.30:1 on --bg-light, which the badge next door had already
    // measured and written down before this page went on using it.
    const value = lightValue(TICKET_DETAIL_PAGE, '--ticket-danger') as string
    expect(value).toMatch(/^#[0-9a-f]{6}$/i)
    for (const name of GROUND_TOKENS) {
      expect(contrast(opaque(value), ground(name, false))).toBeGreaterThanOrEqual(AA_NORMAL_TEXT)
    }
    expect(darkValue(TICKET_DETAIL_PAGE, '--ticket-danger')).toBe('var(--danger)')
    expect(contrast(opaque(token('--danger', true)), ground('--bg-light', true))).toBeGreaterThanOrEqual(
      AA_NORMAL_TEXT,
    )
  })
})
