import { readFileSync } from 'node:fs'
import { dirname, resolve } from 'node:path'
import { fileURLToPath } from 'node:url'
import { describe, expect, it } from 'vitest'

import PAGE from '../SupportAgentsPage.vue?raw'
import GRANT from '@/components/admin/support-agents/SupportAgentGrant.vue?raw'
import ROSTER from '@/components/admin/support-agents/SupportRosterTable.vue?raw'

/**
 * The roster page's colours, held to WCAG AA from the source (jsdom applies
 * no scoped styles, so a mounted page reports none). Same method as
 * components/support/__tests__/ticketMutedContrast.spec.ts: the grounds are
 * read from main.css, the text colours from the page, and the ratios are
 * computed here rather than copied from a comment.
 *
 * Why it exists: --text-muted and --danger are under AA on the page ground
 * (.content-area's --bg-light) in light mode, and --dark-green is under AA on
 * every dark ground. The React page's amber mark (amber-700) was 4.39:1 on
 * the row hover. Each of those is a plausible "tidy-up" that would put the
 * page back under AA.
 */
const STYLESHEET = readFileSync(
  resolve(dirname(fileURLToPath(import.meta.url)), '../../../assets/main.css'),
  'utf8'
)

const AA_NORMAL_TEXT = 4.5

type Rgb = [number, number, number]

function block(source: string, selector: RegExp): string {
  const match = source.match(selector)
  if (!match) throw new Error(`no block for ${selector}`)
  return match[1]
}

const lightRoot = () => block(STYLESHEET, /(?:^|\n):root\s*\{([^}]*)\}/)
const darkRoot = () => block(STYLESHEET, /:root\[data-theme="dark"\]\s*\{([^}]*)\}/)

function declared(body: string, name: string): string | null {
  const match = body.match(new RegExp(`${name}\\s*:\\s*([^;]+);`))
  return match ? match[1].trim() : null
}

function token(name: string, dark: boolean): string {
  const value = (dark ? declared(darkRoot(), name) : null) ?? declared(lightRoot(), name)
  if (!value) throw new Error(`no ${name} in main.css`)
  return value
}

function colour(value: string): { rgb: Rgb; alpha: number } {
  const hex = /^#([0-9a-f]{2})([0-9a-f]{2})([0-9a-f]{2})$/i.exec(value)
  if (hex) return { rgb: hex.slice(1).map((pair) => parseInt(pair, 16)) as Rgb, alpha: 1 }
  const rgba = /^rgba?\(([^)]*)\)$/.exec(value)
  if (rgba) {
    const parts = rgba[1].split(',').map((part) => Number(part.trim()))
    return { rgb: [parts[0], parts[1], parts[2]], alpha: parts.length > 3 ? parts[3] : 1 }
  }
  throw new Error(`not a colour this test can measure: ${value}`)
}

// "--light-green over --white" mixes the translucent green with what is
// painted behind it, the way the browser does.
function ground(spec: string, dark: boolean): Rgb {
  const [front, behind] = spec.split(' over ')
  const top = colour(token(front, dark))
  if (top.alpha === 1) return top.rgb
  if (!behind) throw new Error(`${spec} is translucent and nothing was named behind it`)
  const back = ground(behind, dark)
  return top.rgb.map((value, i) => top.alpha * value + (1 - top.alpha) * back[i]) as Rgb
}

function textColour(value: string, dark: boolean): Rgb {
  const resolved = value.startsWith('var(') ? token(value.slice(4, -1).trim(), dark) : value
  const parsed = colour(resolved)
  if (parsed.alpha !== 1) throw new Error(`text colour is not opaque: ${value}`)
  return parsed.rgb
}

function channel(value: number): number {
  const c = value / 255
  return c <= 0.04045 ? c / 12.92 : ((c + 0.055) / 1.055) ** 2.4
}

function luminance([r, g, b]: Rgb): number {
  return 0.2126 * channel(r) + 0.7152 * channel(g) + 0.0722 * channel(b)
}

function contrast(a: Rgb, b: Rgb): number {
  const la = luminance(a)
  const lb = luminance(b)
  return (Math.max(la, lb) + 0.05) / (Math.min(la, lb) + 0.05)
}

const style = (sfc: string) =>
  (sfc.match(/<style scoped>([\s\S]*)<\/style>/) as RegExpMatchArray)[1].replace(
    /\/\*[\s\S]*?\*\//g,
    ''
  )

const pageStyle = style(PAGE)
const lightPage = block(pageStyle, /(?:^|\n)\.support-agents\s*\{([^}]*)\}/)
const darkPage = block(pageStyle, /:root\[data-theme='dark'\] \.support-agents\s*\{([^}]*)\}/)

function roster(name: string, dark: boolean): string {
  const value = declared(dark ? darkPage : lightPage, name)
  if (!value) throw new Error(`no ${name} in the ${dark ? 'dark' : 'light'} page block`)
  return value
}

// Where each colour is painted. The page prose, the grant refusal and the
// roster error sit on the page (--bg-light); the table and the candidate list
// on --white; a hovered table row on --light-green, which is translucent in
// dark and so is measured over the table's --white.
const PAIRS: Array<{ what: string; value: (dark: boolean) => string; grounds: [string[], string[]] }> = [
  {
    what: 'muted text (--roster-muted)',
    value: (dark) => roster('--roster-muted', dark),
    grounds: [
      ['--bg-light', '--white', '--light-green'],
      ['--bg-light', '--white', '--light-green over --white']
    ]
  },
  {
    what: 'error text (--roster-danger)',
    value: (dark) => roster('--roster-danger', dark),
    grounds: [['--bg-light', '--white'], ['--bg-light', '--white']]
  },
  {
    what: 'the cannot-sign-in mark (--roster-warn)',
    value: (dark) => roster('--roster-warn', dark),
    grounds: [
      ['--white', '--light-green'],
      ['--white', '--light-green over --white']
    ]
  },
  {
    what: 'the revoke refusal inside the dialog',
    value: (dark) =>
      declared(
        block(
          pageStyle,
          dark
            ? /:root\[data-theme='dark'\] \.support-agents__dialog-error\s*\{([^}]*)\}/
            : /(?:^|\n)\.support-agents__dialog-error\s*\{([^}]*)\}/
        ),
        'color'
      )!,
    grounds: [['--white'], ['--white']]
  },
  {
    what: 'outline button text (dark: this page’s override; light: .btn-outline’s green)',
    value: (dark) =>
      dark
        ? declared(
            block(pageStyle, /:root\[data-theme='dark'\] \.support-agents :deep\(\.btn-outline\)\s*\{([^}]*)\}/),
            'color'
          )!
        : token('--dark-green', false),
    grounds: [
      ['--bg-light', '--white', '--light-green'],
      ['--bg-light', '--white', '--light-green over --bg-light', '--light-green over --white']
    ]
  }
]

describe('support agents page colours', () => {
  for (const pair of PAIRS) {
    for (const dark of [false, true]) {
      const theme = dark ? 'dark' : 'light'
      for (const spec of pair.grounds[dark ? 1 : 0]) {
        it(`${theme}: ${pair.what} on ${spec} clears AA`, () => {
          const ratio = contrast(textColour(pair.value(dark), dark), ground(spec, dark))
          expect(ratio).toBeGreaterThanOrEqual(AA_NORMAL_TEXT)
        })
      }
    }
  }

  it('the components paint text only with the page’s measured colours or the theme text', () => {
    // A child reaching for --text-muted or --danger would slip past every
    // measurement above.
    for (const [name, sfc] of [
      ['SupportAgentGrant.vue', GRANT],
      ['SupportRosterTable.vue', ROSTER]
    ] as const) {
      const colours = [...style(sfc).matchAll(/(?:^|[\s;{])color\s*:\s*([^;]+);/g)].map((m) => m[1].trim())
      expect({ name, painted: colours.length > 0 }).toEqual({ name, painted: true })
      for (const value of colours) {
        expect({ name, value }).toEqual({
          name,
          value: expect.stringMatching(/^var\(--(roster-muted|roster-danger|roster-warn|charcoal)\)$/)
        })
      }
    }
  })
})
