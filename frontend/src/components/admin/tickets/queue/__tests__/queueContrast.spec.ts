import { readFileSync } from 'node:fs'
import { dirname, resolve as resolvePath } from 'node:path'
import { fileURLToPath } from 'node:url'
import { flushPromises, mount, type VueWrapper } from '@vue/test-utils'
import { createPinia, setActivePinia } from 'pinia'
import { afterAll, beforeAll, describe, expect, it, vi } from 'vitest'
import { compileStyle } from 'vue/compiler-sfc'

import { pureAgent } from '@/__tests__/supportAccountFixtures'
import type { TicketQueue, TicketRow } from '@/utils/ticketAgentSchema'

/**
 * The queue page's row colours and focus ring, held to WCAG AA in both
 * themes, measured on the page as it is really put together.
 *
 * jsdom applies no stylesheet, so this does the part of a browser that
 * matters here: it compiles every queue component's scoped style the way the
 * build does, under the scope id the mounted component really carries, reads
 * main.css, and runs the cascade (specificity, then source order, then
 * inheritance and var()) over the mounted page. Hover and keyboard focus are
 * stood in for by a class on the elements a pointer or focus would be on.
 *
 * Two regressions it exists for:
 *   - a hovered row in the dark theme was painted twice, by main.css's
 *     `tbody tr:hover` on the row and by QueueTable on every cell. The wash
 *     is translucent in dark, so two of them are darker than one, and muted
 *     text fell to 4.30:1;
 *   - the global focus ring is --dark-green, which dark does not redefine:
 *     2.79:1 on the dark card and less on the washes, under the 3:1 a focus
 *     indicator needs. The page gives every control in it the mint instead.
 *
 * Every ratio is computed here from the stylesheets, the thresholds are
 * written out, and nothing expected is read back from a component.
 */

vi.mock('vue-router', () => ({
  useRoute: () => ({ path: '/admin/tickets', query: {} }),
  useRouter: () => ({ replace: vi.fn() })
}))

vi.mock('@/utils/ticketAgentAPI', async () => {
  const actual =
    await vi.importActual<typeof import('@/utils/ticketAgentAPI')>('@/utils/ticketAgentAPI')
  return {
    ...actual,
    fetchTicketQueue: vi.fn(),
    fetchTicketSummary: vi.fn(),
    fetchAssignees: vi.fn(),
    fetchTicketRegions: vi.fn()
  }
})

import BulkActionsBar from '@/components/admin/BulkActionsBar.vue'
import BULK_ACTIONS_BAR from '@/components/admin/BulkActionsBar.vue?raw'
import { useAuthStore } from '@/stores/auth'
import {
  fetchAssignees,
  fetchTicketQueue,
  fetchTicketRegions,
  fetchTicketSummary
} from '@/utils/ticketAgentAPI'
import TicketQueuePage from '@/views/admin/tickets/TicketQueuePage.vue'
import PAGE from '@/views/admin/tickets/TicketQueuePage.vue?raw'
import BulkAssignBar from '../BulkAssignBar.vue'
import BULK_ASSIGN_BAR from '../BulkAssignBar.vue?raw'
import CounterCards from '../CounterCards.vue'
import COUNTER_CARDS from '../CounterCards.vue?raw'
import FilterBar from '../FilterBar.vue'
import FILTER_BAR from '../FilterBar.vue?raw'
import PageSizeControl from '../PageSizeControl.vue'
import PAGE_SIZE_CONTROL from '../PageSizeControl.vue?raw'
import QueuePager from '../QueuePager.vue'
import QUEUE_PAGER from '../QueuePager.vue?raw'
import QueueTable from '../QueueTable.vue'
import QUEUE_TABLE from '../QueueTable.vue?raw'

// Read off disk: Vitest stubs CSS imports to an empty string, `?raw`
// included (ticketMutedContrast.spec.ts found the same).
const MAIN_CSS = readFileSync(
  resolvePath(dirname(fileURLToPath(import.meta.url)), '../../../../../assets/main.css'),
  'utf8'
)

const AA_TEXT = 4.5
// A focus indicator is non-text contrast: 3:1 (WCAG 1.4.11).
const AA_NON_TEXT = 3

type Theme = 'light' | 'dark'
type Rgba = [number, number, number, number]
type Rule = { selector: string; body: Record<string, string>; specificity: number[]; order: number }

// --- The stylesheets ---------------------------------------------------------

function declarations(body: string): Record<string, string> {
  return Object.fromEntries(
    [...body.matchAll(/([\w-]+)\s*:\s*([^;]+);/g)].map((m) => [m[1]!, m[2]!.trim()])
  )
}

// Top-level rules only. At-rule blocks are skipped: @media ones hold the
// phone layout (nothing in them paints a row or a ring) and @keyframes are
// not rules at all.
function topLevelRules(css: string): { selectors: string[]; body: string }[] {
  const text = css.replace(/\/\*[\s\S]*?\*\//g, '')
  const out: { selectors: string[]; body: string }[] = []
  let i = 0
  while (i < text.length) {
    const open = text.indexOf('{', i)
    if (open === -1) break
    const prelude = text.slice(i, open).trim()
    let depth = 1
    let j = open + 1
    while (j < text.length && depth > 0) {
      if (text[j] === '{') depth++
      else if (text[j] === '}') depth--
      j++
    }
    if (!prelude.startsWith('@')) {
      out.push({
        selectors: prelude.split(',').map((s) => s.trim()),
        body: text.slice(open + 1, j - 1)
      })
    }
    i = j
  }
  return out
}

function specificity(selector: string): number[] {
  let s = selector.replace(/::[\w-]+/g, ' ').replace(/:not\(([^)]*)\)/g, ' $1 ')
  const attributes = (s.match(/\[[^\]]*\]/g) ?? []).length
  s = s.replace(/\[[^\]]*\]/g, ' ')
  const ids = (s.match(/#[\w-]+/g) ?? []).length
  const classes = (s.match(/\.[\w-]+/g) ?? []).length
  const pseudoClasses = (s.match(/:[\w-]+/g) ?? []).length
  s = s.replace(/#[\w-]+|\.[\w-]+|:[\w-]+/g, ' ')
  const types = (s.match(/(^|[\s>+~])[a-zA-Z][\w-]*/g) ?? []).length
  return [ids, classes + attributes + pseudoClasses, types]
}

// A component's style, compiled as the build compiles it.
function compiled(source: string, component: unknown, filename: string): string {
  const style = /<style scoped>([\s\S]*?)<\/style>/.exec(source)
  const scopeId = (component as { __scopeId?: string }).__scopeId
  if (!style || !scopeId) throw new Error(`${filename} has no scoped style`)
  const { code, errors } = compileStyle({ source: style[1]!, filename, id: scopeId, scoped: true })
  if (errors.length) throw new Error(`${filename}: ${errors.join('; ')}`)
  return code
}

// main.css first, then the components, which the app injects after it.
const SHEETS = [
  MAIN_CSS,
  compiled(PAGE, TicketQueuePage, 'TicketQueuePage.vue'),
  compiled(QUEUE_TABLE, QueueTable, 'QueueTable.vue'),
  compiled(QUEUE_PAGER, QueuePager, 'QueuePager.vue'),
  compiled(PAGE_SIZE_CONTROL, PageSizeControl, 'PageSizeControl.vue'),
  compiled(FILTER_BAR, FilterBar, 'FilterBar.vue'),
  compiled(COUNTER_CARDS, CounterCards, 'CounterCards.vue'),
  compiled(BULK_ASSIGN_BAR, BulkAssignBar, 'BulkAssignBar.vue'),
  compiled(BULK_ACTIONS_BAR, BulkActionsBar, 'BulkActionsBar.vue')
]

// Hover and focus become classes the test puts on the elements concerned.
const HOVER = '__hover'
const FOCUS = '__focus'

const RULES: Rule[] = SHEETS.flatMap((sheet) => topLevelRules(sheet)).flatMap(
  ({ selectors, body }, order) =>
    selectors.map((raw) => {
      const selector = raw
        .replace(/:hover\b/g, `.${HOVER}`)
        .replace(/:focus-visible\b/g, `.${FOCUS}`)
        .replace(/:focus(?![\w-])/g, `.${FOCUS}`)
      return { selector, body: declarations(body), specificity: specificity(raw), order }
    })
)

function matches(element: Element, selector: string): boolean {
  try {
    return element.matches(selector)
  } catch {
    // A pseudo-element or a selector jsdom cannot read: it styles nothing
    // measured here.
    return false
  }
}

// The value the cascade gives one property on one element, before
// inheritance. A colour longhand is also read from its shorthand:
// background-color from `background`, outline-color from `outline`.
function cascaded(element: Element, property: string): string | undefined {
  const names =
    property === 'background-color'
      ? ['background', 'background-color']
      : property === 'outline-color'
        ? ['outline', 'outline-color']
        : [property]
  let best: { value: string; specificity: number[]; order: number } | undefined
  for (const rule of RULES) {
    for (const name of names) {
      const value = rule.body[name]
      if (value === undefined || !matches(element, rule.selector)) continue
      // Higher specificity wins; between equals, the later rule.
      const beats =
        !best || (compare(rule.specificity, best.specificity) || rule.order - best.order) >= 0
      if (beats) {
        const own = name === 'outline' ? outlineColour(value) : value
        best = { value: own, specificity: rule.specificity, order: rule.order }
      }
    }
  }
  return best?.value
}

function compare(a: number[], b: number[]): number {
  for (let k = 0; k < 3; k++) if (a[k] !== b[k]) return a[k]! - b[k]!
  return 0
}

// The colour inside an `outline` shorthand, or 'none'.
function outlineColour(value: string): string {
  if (/\bnone\b/.test(value)) return 'none'
  const colour = value.match(/(var\([^)]*\)|#[0-9a-f]{3,6}\b|rgba?\([^)]*\))/i)
  return colour ? colour[1]! : 'currentColor'
}

// Inherited properties (colour, custom properties) climb to the parent.
function computed(element: Element | null, property: string): string | undefined {
  for (let node = element; node; node = node.parentElement) {
    const value = cascaded(node, property)
    if (value !== undefined) return value
    if (property !== 'color' && !property.startsWith('--')) return undefined
  }
  return undefined
}

function resolveVars(element: Element, value: string): string {
  return value.replace(/var\((--[\w-]+)\)/g, (_, name: string) => {
    const found = computed(element, name)
    if (found === undefined) throw new Error(`${name} is not set on ${element.className}`)
    return resolveVars(element, found)
  })
}

function parse(value: string): Rgba {
  const v = value.trim().toLowerCase()
  if (v === 'transparent' || v === 'none') return [0, 0, 0, 0]
  const short = /^#([0-9a-f])([0-9a-f])([0-9a-f])$/.exec(v)
  if (short) return [...short.slice(1).map((c) => parseInt(c + c, 16)), 1] as Rgba
  const hex = /^#([0-9a-f]{2})([0-9a-f]{2})([0-9a-f]{2})$/.exec(v)
  if (hex) return [...hex.slice(1).map((c) => parseInt(c, 16)), 1] as Rgba
  const rgba = /^rgba?\(([^)]*)\)$/.exec(v)
  if (rgba) {
    const parts = rgba[1]!.split(',').map((p) => Number(p.trim()))
    return [parts[0]!, parts[1]!, parts[2]!, parts.length > 3 ? parts[3]! : 1]
  }
  throw new Error(`not a colour this test can measure: ${value}`)
}

function background(element: Element): Rgba {
  const value = cascaded(element, 'background-color')
  return value === undefined ? [0, 0, 0, 0] : parse(resolveVars(element, value))
}

// The elements from `from` upwards that paint anything, up to and including
// the first that paints opaquely: the layers a pixel there is made of.
function layers(from: Element): { element: Element; colour: Rgba }[] {
  const out: { element: Element; colour: Rgba }[] = []
  for (let node: Element | null = from; node; node = node.parentElement) {
    const colour = background(node)
    if (colour[3] === 0) continue
    out.push({ element: node, colour })
    if (colour[3] === 1) return out
  }
  throw new Error('nothing opaque behind this element')
}

// The layers laid over each other the way a browser lays them.
function ground(from: Element): Rgba {
  return layers(from)
    .reverse()
    .reduce<Rgba>(
      (under, { colour: [r, g, b, a] }) => [
        r * a + under[0] * (1 - a),
        g * a + under[1] * (1 - a),
        b * a + under[2] * (1 - a),
        1
      ],
      [0, 0, 0, 1]
    )
}

function channel(value: number): number {
  const c = value / 255
  return c <= 0.04045 ? c / 12.92 : ((c + 0.055) / 1.055) ** 2.4
}

function luminance([r, g, b]: Rgba): number {
  return 0.2126 * channel(r) + 0.7152 * channel(g) + 0.0722 * channel(b)
}

function contrast(a: Rgba, b: Rgba): number {
  const x = luminance(a)
  const y = luminance(b)
  return (Math.max(x, y) + 0.05) / (Math.min(x, y) + 0.05)
}

function textColour(element: Element): Rgba {
  const value = computed(element, 'color')
  if (value === undefined) throw new Error(`no colour reaches ${element.className}`)
  const colour = parse(resolveVars(element, value))
  if (colour[3] !== 1) throw new Error(`text colour is not opaque on ${element.className}`)
  return colour
}

// --- The page ----------------------------------------------------------------

const row = (id: number, overrides: Partial<TicketRow> = {}): TicketRow => ({
  id,
  ticketNumber: `SUP-2026-${String(id).padStart(5, '0')}`,
  user: { name: 'Mia', region: 'Australia', anonymous: false },
  subject: `Enquiry ${id}`,
  status: 'open',
  priority: 'normal',
  assignee: null,
  supportUpdatedAt: '2026-09-01T00:00:00Z',
  overdue: false,
  ...overrides
})

let wrapper: VueWrapper
let host: HTMLElement

function setTheme(theme: Theme) {
  if (theme === 'dark') document.documentElement.setAttribute('data-theme', 'dark')
  else document.documentElement.removeAttribute('data-theme')
}

beforeAll(async () => {
  vi.mocked(fetchTicketQueue).mockImplementation(
    async (page, limit): Promise<TicketQueue> => ({
      // Row 1 is selected below; row 2 is left alone.
      items: [row(1), row(2)],
      total: 25,
      page,
      limit,
      hasMore: true,
      asOf: '2026-09-06T05:00:00Z',
      after: '2026-09-01T00:00:00Z_2'
    })
  )
  vi.mocked(fetchTicketSummary).mockResolvedValue({
    unassigned: 2,
    open: 2,
    pendingUser: 0,
    overdue: 0
  })
  vi.mocked(fetchAssignees).mockResolvedValue([{ id: 9, name: 'Sam Reid', assignable: true }])
  vi.mocked(fetchTicketRegions).mockResolvedValue([])
  setActivePinia(createPinia())
  useAuthStore().loginWithUser(pureAgent as never)
  // The section shell's ground, as in the app.
  host = document.createElement('div')
  host.className = 'content-area'
  document.body.appendChild(host)
  wrapper = mount(TicketQueuePage, {
    attachTo: host,
    global: { stubs: { TicketDetailPanel: true } }
  })
  await flushPromises()
  // The bulk bar only renders with a selection, and its controls take focus
  // too.
  await wrapper.get('input[aria-label="Select SUP-2026-00001"]').setValue(true)
})

afterAll(() => {
  wrapper.unmount()
  host.remove()
  setTheme('light')
})

function tableRow(id: number): HTMLTableRowElement {
  const button = wrapper.get(`button[aria-label="Open SUP-2026-${String(id).padStart(5, '0')}"]`)
  return button.element.closest('tr')!
}

// What a pointer resting on `cell` hovers: the cell and everything above it.
function hovering<T>(cell: Element, measure: () => T): T {
  const chain: Element[] = []
  for (let node: Element | null = cell; node; node = node.parentElement) chain.push(node)
  chain.forEach((node) => node.classList.add(HOVER))
  try {
    return measure()
  } finally {
    chain.forEach((node) => node.classList.remove(HOVER))
  }
}

// The four states a row's cells are read in.
const STATES = [
  ['at rest', 2, false],
  ['selected', 1, false],
  ['hovered', 2, true],
  ['selected and hovered', 1, true]
] as const

// The card the rows sit on: the scrolling frame, the first opaque layer.
function card(): Element {
  return wrapper.get('.queue-table__scroll').element
}

describe('the queue rows', () => {
  it('reads the selection it was set up with', () => {
    expect(tableRow(1).classList.contains('queue-table__row--selected')).toBe(true)
    expect(tableRow(2).classList.contains('queue-table__row--selected')).toBe(false)
  })

  for (const theme of ['light', 'dark'] as const) {
    it(`${theme}: paints a selected or hovered row once, and a row at rest not at all`, () => {
      setTheme(theme)
      const painted = STATES.map(([state, id, hover]) => {
        const cell = tableRow(id).querySelector('td.queue-table__when')!
        const measure = () =>
          layers(cell).filter(({ element }) => element !== card() && card().contains(element))
            .length
        return [state, hover ? hovering(cell, measure) : measure()]
      })

      expect(painted).toEqual([
        ['at rest', 0],
        ['selected', 1],
        ['hovered', 1],
        ['selected and hovered', 1]
      ])
      // And the layer under the washes is the card, not the page.
      expect(layers(tableRow(2).querySelector('td')!).at(-1)!.element).toBe(card())
    })

    it(`${theme}: muted text and the ticket link clear AA on every row ground`, () => {
      setTheme(theme)
      const measured: string[] = []
      for (const [state, id, hover] of STATES) {
        const tr = tableRow(id)
        const texts = [
          ['Last activity', tr.querySelector('td.queue-table__when')!],
          ['region', tr.querySelector('.queue-table__region')!],
          ['Unassigned', tr.querySelector('span.queue-table__muted')!],
          ['ticket link', tr.querySelector('button.queue-table__open')!]
        ] as const
        for (const [what, element] of texts) {
          const cell = element.closest('td')!
          const under = hover ? hovering(cell, () => ground(element)) : ground(element)
          const value = contrast(textColour(element), under)
          if (value < AA_TEXT) measured.push(`${what}, ${state}: ${value.toFixed(2)}`)
        }
      }

      expect(measured).toEqual([])
    })
  }

  it('dark: would put muted text under AA if a row were washed twice', () => {
    // The check above is only worth something if it can fail: two washes is
    // the state it replaced, and it is measured the same way here.
    setTheme('dark')
    const cell = tableRow(2).querySelector('td.queue-table__when')!
    const [r, g, b, a] = parse(resolveVars(cell, 'var(--light-green)'))
    const once = ground(cell)
    const blend = (under: Rgba): Rgba => [
      r * a + under[0] * (1 - a),
      g * a + under[1] * (1 - a),
      b * a + under[2] * (1 - a),
      1
    ]

    expect(a).toBeLessThan(1)
    expect(contrast(textColour(cell), blend(blend(once)))).toBeLessThan(AA_TEXT)
    expect(contrast(textColour(cell), blend(once))).toBeGreaterThanOrEqual(AA_TEXT)
  })
})

describe('the focus ring on the queue page', () => {
  // Every element a keyboard can land on, and the table region the page
  // sends focus to by script.
  function focusables(): Element[] {
    return Array.from(
      wrapper.element.querySelectorAll('a[href], button, input, select, textarea, [tabindex]')
    )
  }

  // The ring is drawn just outside the control, over whatever is behind it.
  function ring(element: Element): { colour: Rgba; around: Rgba } {
    element.classList.add(FOCUS)
    try {
      const value = cascaded(element, 'outline-color')
      if (value === undefined || value === 'none')
        throw new Error(`no ring on ${element.outerHTML}`)
      return { colour: parse(resolveVars(element, value)), around: ground(element.parentElement!) }
    } finally {
      element.classList.remove(FOCUS)
    }
  }

  it('covers every kind of control on the page', () => {
    // So a control that vanished from the mount shows up here rather than
    // quietly dropping out of the checks below, and one added later is
    // counted in.
    const names = focusables().map((el) => el.getAttribute('aria-label') ?? el.textContent!.trim())
    expect(names).toEqual(
      expect.arrayContaining([
        'Search tickets',
        'Filter by status',
        'Export to Excel',
        'Assign to',
        'Clear selection',
        'Select every ticket on this page',
        'Select SUP-2026-00001',
        'Open SUP-2026-00002',
        'Tickets',
        'Rows per page',
        'Presets',
        'Next',
        'Go to page 1'
      ])
    )
    // Five filters and search, Export, three counter cards, the bulk bar's
    // select and two buttons, three checkboxes, two Open buttons, the table
    // region, the size box and Presets, Previous, three pages and Next.
    expect(focusables()).toHaveLength(26)
  })

  for (const theme of ['light', 'dark'] as const) {
    it(`${theme}: every control's ring clears 3:1 on the ground around it, rows hovered or not`, () => {
      setTheme(theme)
      const failing: string[] = []
      for (const element of focusables()) {
        const name = element.getAttribute('aria-label') ?? element.textContent!.trim()
        const cell = element.closest('td, th')
        const grounds = cell ? [false, true] : [false]
        for (const hover of grounds) {
          const { colour, around } = hover ? hovering(cell!, () => ring(element)) : ring(element)
          const value = contrast(colour, around)
          if (value < AA_NON_TEXT)
            failing.push(`${name}${hover ? ' (hovered)' : ''}: ${value.toFixed(2)}`)
        }
      }

      expect(failing).toEqual([])
    })
  }

  it('dark: gives every control the mint, where the global ring would fail', () => {
    // The global ring, measured the same way, is what this page overrides.
    setTheme('dark')
    const open = wrapper.get('button[aria-label="Open SUP-2026-00002"]').element
    const { colour, around } = ring(open)

    expect(colour).toEqual(parse('#5ea99e'))
    expect(contrast(parse(resolveVars(open, 'var(--dark-green)')), around)).toBeLessThan(
      AA_NON_TEXT
    )
    for (const element of focusables()) {
      expect(ring(element).colour).toEqual(parse('#5ea99e'))
    }
  })

  it('light: leaves the global ring alone', () => {
    setTheme('light')
    for (const element of focusables()) {
      expect(ring(element).colour).toEqual(parse('#017151'))
    }
  })
})
