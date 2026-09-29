import { readFileSync } from 'node:fs'
import { dirname, resolve as resolvePath } from 'node:path'
import { fileURLToPath } from 'node:url'
import { mount, type VueWrapper } from '@vue/test-utils'
import { afterEach, describe, expect, it } from 'vitest'
import { compileStyle } from 'vue/compiler-sfc'

// Read as text rather than rendered: jsdom applies no scoped-SFC styles, so a
// mounted button reports no colours at all. Same approach as
// overdueBadgeContrast.spec.ts and components/support/__tests__.
//
// The stylesheet is read off disk rather than imported: Vitest stubs CSS out
// to an empty string, `?raw` included, so every regex below would find
// nothing (components/support/__tests__/ticketMutedContrast.spec.ts found the
// same).
const THEME = readFileSync(
  resolvePath(dirname(fileURLToPath(import.meta.url)), '../../../../../assets/main.css'),
  'utf8'
)

import SHARED_BAR from '@/components/admin/BulkActionsBar.vue?raw'
import SOURCE from '../BulkAssignBar.vue?raw'
import BulkAssignBar from '../BulkAssignBar.vue'

/**
 * The bulk bar's Clear button, in both themes.
 *
 * The bar is Team 1's BulkActionsBar: its Clear is var(--dark-green) on the
 * bar's var(--light-green) wash, and the dark theme redefines the wash but
 * not the green (U1 §5.3), so in dark it is green on green. BulkAssignBar
 * gives it mint there. Two things have to hold for that to reach the screen:
 *   - the compiled selector really reaches the button. The obvious spelling,
 *     `:root[data-theme='dark'] :deep(.bulk-actions-bar__clear)`, compiles
 *     with the scope id on :root and matches nothing;
 *   - the colour clears 4.5:1 on the wash, at rest and hovered, with the
 *     translucent dark wash laid over the page the way a browser lays it.
 * Every colour is read from the sources (the theme's tokens, the shared bar's
 * rules), so a token change elsewhere is measured here rather than trusted.
 */

const AA_NORMAL_TEXT = 4.5

type Theme = 'light' | 'dark'
type Rgb = [number, number, number]

function declarations(body: string): Record<string, string> {
  return Object.fromEntries(
    [...body.matchAll(/([\w-]+)\s*:\s*([^;]+);/g)].map((m) => [m[1]!, m[2]!.trim()])
  )
}

function block(source: string, selector: RegExp): Record<string, string> {
  const match = new RegExp(`(?:^|\\n)${selector.source}\\s*\\{([^}]*)\\}`).exec(source)
  if (!match) throw new Error(`no rule ${selector.source}`)
  return declarations(match[1]!)
}

// The theme's custom properties: the light set, with dark's overrides on top.
function tokens(theme: Theme): Record<string, string> {
  const light = block(THEME, /:root/)
  return theme === 'light' ? light : { ...light, ...block(THEME, /:root\[data-theme="dark"\]/) }
}

function resolve(value: string, theme: Theme): string {
  const token = /^var\((--[\w-]+)\)$/.exec(value)
  if (!token) return value
  const resolved = tokens(theme)[token[1]!]
  if (!resolved) throw new Error(`${token[1]} is not a theme token`)
  return resolved
}

// An opaque colour, with a translucent one laid over `under`.
function paint(value: string, under: Rgb): Rgb {
  const hex = /^#([0-9a-f]{2})([0-9a-f]{2})([0-9a-f]{2})$/i.exec(value)
  if (hex) return [1, 2, 3].map((i) => parseInt(hex[i]!, 16)) as Rgb
  const rgba = /^rgba\(\s*(\d+),\s*(\d+),\s*(\d+),\s*([\d.]+)\s*\)$/.exec(value)
  if (!rgba) throw new Error(`cannot read the colour ${value}`)
  const alpha = Number(rgba[4])
  return [1, 2, 3].map((i, k) => Number(rgba[i]) * alpha + under[k]! * (1 - alpha)) as Rgb
}

function channel(value: number): number {
  const c = value / 255
  return c <= 0.04045 ? c / 12.92 : ((c + 0.055) / 1.055) ** 2.4
}

function luminance([r, g, b]: Rgb): number {
  return 0.2126 * channel(r) + 0.7152 * channel(g) + 0.0722 * channel(b)
}

function contrast(a: Rgb, b: Rgb): number {
  const [x, y] = [luminance(a), luminance(b)]
  return (Math.max(x, y) + 0.05) / (Math.min(x, y) + 0.05)
}

// The shared bar's own rules.
const bar = block(SHARED_BAR, /\.bulk-actions-bar/)
const clearAtRest = block(SHARED_BAR, /\.bulk-actions-bar__clear/)
const clearHovered = block(SHARED_BAR, /\.bulk-actions-bar__clear:hover:not\(:disabled\)/)

// The page ground the bar sits on: TicketsSection's .content-area.
const contentArea = block(THEME, /\.content-area/)

function grounds(theme: Theme): { rest: Rgb; hover: Rgb } {
  const page = paint(resolve(contentArea['background-color']!, theme), [255, 255, 255])
  const rest = paint(resolve(bar['background-color']!, theme), page)
  return { rest, hover: paint(resolve(clearHovered['background-color']!, theme), rest) }
}

// BulkAssignBar's style compiled the way the build compiles it, under the
// scope id the mounted component really carries.
function compiledRules(): { selectors: string[]; body: Record<string, string> }[] {
  const style = /<style scoped>([\s\S]*?)<\/style>/.exec(SOURCE)
  const scopeId = (BulkAssignBar as { __scopeId?: string }).__scopeId
  if (!style || !scopeId) throw new Error('BulkAssignBar has no scoped style')
  const { code, errors } = compileStyle({
    source: style[1]!,
    filename: 'BulkAssignBar.vue',
    id: scopeId,
    scoped: true
  })
  expect(errors).toEqual([])
  return [...code.replace(/\/\*[\s\S]*?\*\//g, '').matchAll(/([^{}]+)\{([^}]*)\}/g)].map((m) => ({
    selectors: m[1]!.split(',').map((s) => s.trim()),
    body: declarations(m[2]!)
  }))
}

let wrapper: VueWrapper | null = null

afterEach(() => {
  wrapper?.unmount()
  wrapper = null
  document.documentElement.removeAttribute('data-theme')
})

function mountBar() {
  wrapper = mount(BulkAssignBar, {
    attachTo: document.body,
    props: {
      count: 2,
      assignees: [],
      assigneesUnavailable: false,
      assigneesLoading: false,
      pending: false
    }
  })
  return wrapper.get('button.bulk-actions-bar__clear').element
}

// The colour the Clear button ends up with in a theme: the last colour rule
// among this component's rules that actually matches the mounted button, or
// the shared bar's own when none does. Every candidate here outranks the
// shared rule (it adds :root, the attribute and the bar's class to it).
function clearColour(theme: Theme): string {
  if (theme === 'dark') document.documentElement.setAttribute('data-theme', 'dark')
  const button = mountBar()
  const ours = compiledRules().filter(
    (rule) => rule.body.color && rule.selectors.some((s) => button.matches(s))
  )
  return ours.length ? ours[ours.length - 1]!.body.color! : clearAtRest.color!
}

describe('the bulk bar Clear button', () => {
  it('is reached by the dark rule this component adds', () => {
    // The rule is only worth something if it lands. Checked against the DOM
    // the component really renders, under its real scope id.
    document.documentElement.setAttribute('data-theme', 'dark')
    const button = mountBar()

    const dark = compiledRules().filter((rule) =>
      rule.selectors.some((s) => s.includes("data-theme='dark'") && s.includes('bulk-actions-bar__clear'))
    )

    expect(dark.length).toBe(1)
    expect(dark[0]!.selectors.some((s) => button.matches(s))).toBe(true)
    expect(dark[0]!.body.color).toBe('var(--mint-green)')
  })

  it('leaves the light theme to the shared bar', () => {
    expect(clearColour('light')).toBe('var(--dark-green)')
  })

  for (const theme of ['light', 'dark'] as const) {
    it(`${theme}: reads at AA on the bar, at rest and hovered`, () => {
      const colour = paint(resolve(clearColour(theme), theme), [255, 255, 255])
      const { rest, hover } = grounds(theme)

      expect(contrast(colour, rest)).toBeGreaterThanOrEqual(AA_NORMAL_TEXT)
      expect(contrast(colour, hover)).toBeGreaterThanOrEqual(AA_NORMAL_TEXT)
    })
  }
})
