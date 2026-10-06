import { readFileSync } from 'node:fs'
import { dirname, resolve } from 'node:path'
import { fileURLToPath } from 'node:url'
import { describe, expect, it } from 'vitest'

/**
 * The colour pairs the first redesign round (October 2026) brought to the
 * ticket screens, held to WCAG AA in both themes.
 *
 * That round gave the screens pairs no other spec measures: a mint bubble and
 * its words, pale green table heads and their capitals, an amber callout,
 * file cards, round pictures on empty lists, and control edges that can be
 * seen. Each component keeps these colours as custom properties on its own
 * root. The specs beside the components measure what was there before
 * (muted text, errors, focus rings, row washes); this one measures the rest,
 * so a later tidy-up that moves one of these under AA goes red.
 *
 * Everything is read off disk, as ticketMutedContrast.spec.ts does: jsdom
 * applies no scoped styles, and a `?raw` import of main.css comes back empty
 * under vitest. The grounds are written down from where each component
 * paints, and the theme tokens are read from main.css, so a value moving in
 * either file is caught. A ground written "A over B" is a translucent A laid
 * on B, mixed the way the browser mixes them.
 */

const here = dirname(fileURLToPath(import.meta.url))
const src = (path: string) => readFileSync(resolve(here, '../../..', path), 'utf8')
const uncommented = (css: string) => css.replace(/\/\*[\s\S]*?\*\//g, '')

type Theme = 'light' | 'dark'
type Rgb = [number, number, number]

function declarations(body: string): Record<string, string> {
  const out: Record<string, string> = {}
  for (const line of body.split(';')) {
    const at = line.indexOf(':')
    if (at === -1) continue
    const name = line.slice(0, at).trim()
    if (name) out[name] = line.slice(at + 1).trim()
  }
  return out
}

// The first rule whose whole selector is `selector`.
function rule(css: string, selector: string): Record<string, string> | null {
  const escaped = selector.replace(/[.*+?^${}()|[\]\\]/g, '\\$&')
  const match = new RegExp(`(?:^|\\n|\\})\\s*${escaped}\\s*\\{([^}]*)\\}`).exec(css)
  return match ? declarations(match[1]) : null
}

const MAIN = uncommented(src('assets/main.css'))
const THEME: Record<Theme, Record<string, string>> = {
  light: rule(MAIN, ':root')!,
  // The dark block lists only what it changes.
  dark: { ...rule(MAIN, ':root')!, ...rule(MAIN, ':root[data-theme="dark"]')! }
}

function stylesheet(file: string): string {
  const match = /<style scoped>([\s\S]*?)<\/style>/.exec(src(file))
  if (!match) throw new Error(`no scoped style in ${file}`)
  return uncommented(match[1])
}

// The root's own properties in a theme: the light rule, and for dark the dark
// rule laid over it. Both quote styles of the theme selector are in use.
function locals(file: string, root: string, theme: Theme): Record<string, string> {
  const css = stylesheet(file)
  const light = rule(css, root)
  if (!light) throw new Error(`no ${root} rule in ${file}`)
  if (theme === 'light') return light
  const dark =
    rule(css, `:root[data-theme='dark'] ${root}`) ?? rule(css, `:root[data-theme="dark"] ${root}`)
  if (!dark) throw new Error(`no dark ${root} rule in ${file}`)
  return { ...light, ...dark }
}

function parse(value: string): { rgb: Rgb; alpha: number } {
  const hex = /^#([0-9a-f]{2})([0-9a-f]{2})([0-9a-f]{2})$/i.exec(value)
  if (hex) return { rgb: hex.slice(1).map((pair) => parseInt(pair, 16)) as Rgb, alpha: 1 }
  const rgba = /^rgba?\(([^)]*)\)$/.exec(value)
  if (rgba) {
    const parts = rgba[1].split(',').map((part) => Number(part.trim()))
    return { rgb: [parts[0], parts[1], parts[2]], alpha: parts.length > 3 ? parts[3] : 1 }
  }
  throw new Error(`not a colour this test can measure: ${value}`)
}

// A literal, or a property: the component's own first, then the theme's.
function lookup(name: string, scope: Record<string, string>, theme: Theme): string {
  if (name.startsWith('#')) return name
  const value = scope[name] ?? THEME[theme][name]
  if (!value) throw new Error(`unknown ${name}`)
  const ref = /^var\((--[\w-]+)\)$/.exec(value)
  return ref ? lookup(ref[1], scope, theme) : value
}

function colour(spec: string, scope: Record<string, string>, theme: Theme): Rgb {
  const [front, behind] = spec.split(' over ')
  const top = parse(lookup(front, scope, theme))
  if (top.alpha === 1) return top.rgb
  if (!behind) throw new Error(`${spec} is translucent in ${theme} and nothing is named behind it`)
  const back = colour(behind, scope, theme)
  return top.rgb.map((value, i) => top.alpha * value + (1 - top.alpha) * back[i]) as Rgb
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

const TEXT = 4.5
const NON_TEXT = 3

type Pair = [ink: string, ground: string, threshold: number]

// Text needs 4.5:1. An icon, a control's edge or a focus edge needs 3:1, and
// an edge is measured on both sides of it: the field inside, the ground
// outside.
const FILES: { file: string; root: string; pairs: Pair[] }[] = [
  {
    // The hero is on the page; the help card and the tickets card are
    // --surface-elevated; the count pill and the promise under the table are
    // the band.
    file: 'views/SupportCentrePage.vue',
    root: '.support',
    pairs: [
      ['--ticket-muted', '--bg-light', TEXT],
      ['--ticket-muted', '--surface-elevated', TEXT],
      ['--ticket-muted', '--ticket-band', TEXT],
      ['--ticket-link', '--bg-light', TEXT],
      ['--ticket-link', '--surface-elevated', TEXT],
      ['--ticket-tile-ink', '--ticket-tile', NON_TEXT],
      ['--ticket-control-edge', '--surface-elevated', NON_TEXT]
    ]
  },
  {
    // In the tickets card. A row under the pointer takes main.css's
    // tbody tr:hover wash.
    file: 'components/support/MyTicketsTable.vue',
    root: '.my-tickets',
    pairs: [
      ['--my-tickets-head-ink', '--my-tickets-head', TEXT],
      ['--my-tickets-link', '--surface-elevated', TEXT],
      ['--my-tickets-link', '--light-green over --surface-elevated', TEXT],
      ['--my-tickets-tile-ink', '--my-tickets-tile', NON_TEXT]
    ]
  },
  {
    // A --surface-elevated card with --white fields; the button is brand
    // green, darker under the pointer.
    file: 'components/support/TicketForm.vue',
    root: '.ticket-form',
    pairs: [
      ['--form-muted', '--surface-elevated', TEXT],
      ['--form-placeholder', '--white', TEXT],
      ['--form-control-edge', '--white', NON_TEXT],
      ['--form-control-edge', '--surface-elevated', NON_TEXT],
      ['--form-focus-edge', '--white', NON_TEXT],
      ['--form-focus-edge', '--surface-elevated', NON_TEXT],
      ['#ffffff', '--dark-green', TEXT],
      ['#ffffff', '#174243', TEXT]
    ]
  },
  {
    // In the form card or the reply card, both --surface-elevated. A picked
    // file is a --bg-light row, and so is the drop zone while a file is held
    // over it. The remove cross turns red under the pointer.
    file: 'components/support/TicketAttachmentPicker.vue',
    root: '.attach',
    pairs: [
      ['--attach-muted', '--surface-elevated', TEXT],
      ['--attach-muted', '--bg-light', TEXT],
      ['--attach-hover', '--surface-elevated', TEXT],
      ['--attach-danger', '--attach-danger-ground', TEXT],
      ['--attach-danger', '--bg-light', NON_TEXT],
      ['--attach-edge', '--surface-elevated', NON_TEXT],
      ['--attach-tile-ink', '--attach-tile', NON_TEXT]
    ]
  },
  {
    // Bubbles on the page. Support's words take the page's text colour; the
    // file pills are --white with an edge.
    file: 'components/support/TicketTimeline.vue',
    root: '.timeline',
    pairs: [
      ['--timeline-mine-ink', '--timeline-mine', TEXT],
      ['--charcoal', '--timeline-theirs', TEXT],
      ['--timeline-file', '--white', TEXT],
      ['--timeline-file-edge', '--white', NON_TEXT],
      ['--timeline-file-edge', '--bg-light', NON_TEXT]
    ]
  },
  {
    // The back link and the waiting callout, on the page.
    file: 'views/TicketDetailPage.vue',
    root: '.ticket',
    pairs: [
      ['--ticket-wait-ink', '--ticket-wait', TEXT],
      ['--ticket-link', '--bg-light', TEXT]
    ]
  },
  {
    // A --surface-elevated card with a --white field, and the same button as
    // the form's.
    file: 'components/support/TicketReplyBox.vue',
    root: '.reply',
    pairs: [
      ['--reply-muted', '--surface-elevated', TEXT],
      ['--reply-placeholder', '--white', TEXT],
      ['--reply-edge', '--white', NON_TEXT],
      ['--reply-edge', '--surface-elevated', NON_TEXT],
      ['--reply-focus-edge', '--white', NON_TEXT],
      ['--reply-focus-edge', '--surface-elevated', NON_TEXT],
      ['#ffffff', '--dark-green', TEXT],
      ['#ffffff', '#174243', TEXT]
    ]
  },
  {
    // The subtitle and the export alert, on the page.
    file: 'views/admin/tickets/TicketQueuePage.vue',
    root: '.ticket-queue',
    pairs: [
      ['--ticket-queue-muted', '--bg-light', TEXT],
      ['--ticket-queue-danger', '--bg-light', TEXT]
    ]
  },
  {
    // --white cards.
    file: 'components/admin/tickets/queue/CounterCards.vue',
    root: '.queue-card',
    pairs: [
      ['--queue-card-muted', '--white', TEXT],
      ['--queue-card-alert', '--white', TEXT]
    ]
  },
  {
    // The head row on the --white frame, and the empty list's round picture.
    file: 'components/admin/tickets/queue/QueueTable.vue',
    root: '.queue-table',
    pairs: [
      ['--queue-head-ink', '--queue-head over --white', TEXT],
      ['--queue-tile-ink', '--queue-tile', NON_TEXT]
    ]
  },
  {
    // --white fields on the page.
    file: 'components/admin/tickets/queue/FilterBar.vue',
    root: '.queue-filters',
    pairs: [
      ['--queue-filter-placeholder', '--white', TEXT],
      ['--queue-filter-edge', '--white', NON_TEXT],
      ['--queue-filter-edge', '--bg-light', NON_TEXT]
    ]
  },
  {
    // "Page N of M" and --white buttons on the page; the current page is
    // white on brand green.
    file: 'components/admin/tickets/queue/QueuePager.vue',
    root: '.queue-pager',
    pairs: [
      ['--pager-muted', '--bg-light', TEXT],
      ['--pager-edge', '--white', NON_TEXT],
      ['--pager-edge', '--bg-light', NON_TEXT],
      ['#ffffff', '--dark-green', TEXT]
    ]
  },
  {
    // Presets is a link on the page; the select and the box are --white.
    file: 'components/admin/tickets/queue/PageSizeControl.vue',
    root: '.page-size',
    pairs: [
      ['--page-size-link', '--bg-light', TEXT],
      ['--page-size-edge', '--white', NON_TEXT],
      ['--page-size-edge', '--bg-light', NON_TEXT]
    ]
  },
  {
    // A --white select on the shared bar, which is --light-green on the page.
    file: 'components/admin/tickets/queue/BulkAssignBar.vue',
    root: '.bulk-actions-bar.bulk-assign',
    pairs: [
      ['--bulk-edge', '--white', NON_TEXT],
      ['--bulk-edge', '--light-green over --bg-light', NON_TEXT]
    ]
  },
  {
    // The head row on the --white frame.
    file: 'components/admin/tickets/audit/TicketAuditTable.vue',
    root: '.audit-table',
    pairs: [['--audit-head-ink', '--audit-head over --white', TEXT]]
  },
  {
    // --white controls on the page.
    file: 'components/admin/tickets/audit/AuditPager.vue',
    root: '.audit-pager',
    pairs: [
      ['--audit-edge', '--white', NON_TEXT],
      ['--audit-edge', '--bg-light', NON_TEXT]
    ]
  },
  {
    // The two filters, --white on the page.
    file: 'views/admin/tickets/TicketAuditPage.vue',
    root: '.ticket-audit',
    pairs: [
      ['--audit-edge', '--white', NON_TEXT],
      ['--audit-edge', '--bg-light', NON_TEXT]
    ]
  },
  {
    // The date fields and the select, --white on the page.
    file: 'views/admin/tickets/TicketAnalyticsPage.vue',
    root: '.ticket-analytics',
    pairs: [
      ['--analytics-edge', '--white', NON_TEXT],
      ['--analytics-edge', '--bg-light', NON_TEXT]
    ]
  },
  {
    // The search box and the create button are on the page; Grant is in the
    // --white results card; Revoke is on a table row, which is --white until
    // the pointer washes it.
    file: 'views/admin/SupportAgentsPage.vue',
    root: '.support-agents',
    pairs: [
      ['--roster-edge', '--white', NON_TEXT],
      ['--roster-edge', '--bg-light', NON_TEXT],
      ['--roster-row-edge', '--white', NON_TEXT],
      ['--roster-row-edge', '--light-green over --white', NON_TEXT],
      ['--roster-focus', '--white', NON_TEXT],
      ['--roster-focus', '--bg-light', NON_TEXT],
      ['--roster-accent', '--white', NON_TEXT],
      ['--roster-accent', '--bg-light', NON_TEXT]
    ]
  }
]

describe('the controls on a peach ground take the darker edge', () => {
  // #84938f is 2.80:1 on --light-green's peach, so the two controls that sit
  // on it take #7a8884 instead. The greys look alike, and the pairs above only
  // measure the properties; this pins each control to its own.
  it('draws Revoke with the row edge, not the search box grey', () => {
    const revoke = rule(stylesheet('components/admin/support-agents/SupportRosterTable.vue'), '.support-roster__revoke')
    expect(revoke?.border).toBe('1px solid var(--roster-row-edge)')
  })

  it('draws the bulk bar select with the bar edge', () => {
    const select = rule(stylesheet('components/admin/tickets/queue/BulkAssignBar.vue'), '.bulk-assign__select')
    expect(select?.border).toBe('1px solid var(--bulk-edge)')
  })
})

describe('the redesign round keeps its colour pairs at AA', () => {
  for (const theme of ['light', 'dark'] as const) {
    for (const { file, root, pairs } of FILES) {
      for (const [ink, ground, threshold] of pairs) {
        it(`${theme}: ${file} ${ink} on ${ground}`, () => {
          const scope = locals(file, root, theme)
          const measured = contrast(colour(ink, scope, theme), colour(ground, scope, theme))
          expect(measured).toBeGreaterThanOrEqual(threshold)
        })
      }
    }
  }
})

// The chevron on every ticket <select>, the paperclip on the detail panel's
// file buttons and the cross in the roster's search box. Each is an SVG in a
// data URI, so its colour is written into it once per theme. All three are
// drawn on a --white control.
const CONTROLS = uncommented(src('components/support/ticketControls.css'))
const ICONS = ['--ticket-select-chevron', '--ticket-paperclip', '--ticket-clear-x']

function stroke(theme: Theme, icon: string): Rgb {
  const block = rule(CONTROLS, theme === 'light' ? ':root' : ":root[data-theme='dark']")
  const match = /stroke='%23([0-9a-f]{6})'/i.exec(block?.[icon] ?? '')
  if (!match) throw new Error(`no stroke colour in ${icon} for ${theme}`)
  return parse(`#${match[1]}`).rgb
}

describe('the icons drawn into ticket controls', () => {
  for (const theme of ['light', 'dark'] as const) {
    for (const icon of ICONS) {
      it(`${theme}: ${icon} clears 3:1 on the control`, () => {
        const field = colour('--white', {}, theme)
        expect(contrast(stroke(theme, icon), field)).toBeGreaterThanOrEqual(NON_TEXT)
      })
    }
  }
})
