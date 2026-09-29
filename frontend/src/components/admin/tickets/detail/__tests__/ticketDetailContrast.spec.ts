import { readFileSync } from 'node:fs'
import { dirname, resolve } from 'node:path'
import { fileURLToPath } from 'node:url'
import { describe, expect, it } from 'vitest'

/**
 * The detail panel's colours, held to WCAG AA in both themes.
 *
 * jsdom applies no scoped SFC styles, so this reads the sources off disk (the
 * same approach as components/support/__tests__/ticketMutedContrast.spec.ts)
 * and computes each ratio from the numbers in them. The theme tokens are read
 * from main.css rather than written out, so a token moving there is caught.
 *
 * Two traps this guards against, both measured in the portal (U1 5.3):
 * --text-muted is 4.45:1 and --danger 4.30:1 on --bg-light, and --dark-green
 * is not redefined for dark, where it is 2.79:1. None of the three may paint
 * text here in light, and the dark values are measured, not assumed.
 */

const here = dirname(fileURLToPath(import.meta.url))
const read = (path: string) => readFileSync(resolve(here, path), 'utf8')

const MAIN = read('../../../../../assets/main.css')

function block(css: string, selector: string): Record<string, string> {
  const escaped = selector.replace(/[.*+?^${}()|[\]\\]/g, '\\$&')
  const match = new RegExp(`(?:^|\\n)\\s*${escaped}\\s*\\{([^}]*)\\}`).exec(css)
  if (!match) throw new Error(`no rule for ${selector}`)
  const declarations: Record<string, string> = {}
  for (const line of match[1].split(';')) {
    const at = line.indexOf(':')
    if (at === -1) continue
    const name = line.slice(0, at).replace(/\/\*[\s\S]*?\*\//g, '').trim()
    if (name) declarations[name] = line.slice(at + 1).trim()
  }
  return declarations
}

const THEME = {
  light: block(MAIN, ':root'),
  dark: { ...block(MAIN, ':root'), ...block(MAIN, ':root[data-theme="dark"]') }
}

type Theme = keyof typeof THEME

function style(file: string): string {
  const source = read(`../${file}`)
  const match = /<style scoped>([\s\S]*?)<\/style>/.exec(source)
  if (!match) throw new Error(`no scoped style in ${file}`)
  return match[1]
}

/** A component's own custom properties in a theme: the light rule, with the
 *  dark rule laid over it for dark. */
function locals(file: string, selector: string, theme: Theme): Record<string, string> {
  const css = style(file)
  const light = block(css, selector)
  return theme === 'light' ? light : { ...light, ...block(css, `:root[data-theme='dark'] ${selector}`) }
}

function resolveColour(value: string, scope: Record<string, string>, theme: Theme): string {
  const trimmed = value.trim()
  if (trimmed.startsWith('#')) return trimmed
  const ref = /^var\((--[\w-]+)\)$/.exec(trimmed)
  if (!ref) throw new Error(`cannot measure ${value}`)
  const next = scope[ref[1]] ?? THEME[theme][ref[1]]
  if (!next) throw new Error(`unknown ${ref[1]}`)
  return resolveColour(next, scope, theme)
}

function luminance(hex: string): number {
  const full = hex.length === 4 ? `#${hex[1]}${hex[1]}${hex[2]}${hex[2]}${hex[3]}${hex[3]}` : hex
  const [r, g, b] = [1, 3, 5]
    .map((i) => parseInt(full.slice(i, i + 2), 16) / 255)
    .map((c) => (c <= 0.03928 ? c / 12.92 : ((c + 0.055) / 1.055) ** 2.4))
  return 0.2126 * r + 0.7152 * g + 0.0722 * b
}

function ratio(a: string, b: string): number {
  const [hi, lo] = [luminance(a), luminance(b)].sort((x, y) => y - x)
  return (hi + 0.05) / (lo + 0.05)
}

const AA_TEXT = 4.5
const AA_NON_TEXT = 3

// Text and its grounds, per component. Every ground is the panel's own
// --white, or the note's amber, which is the only other colour anything sits
// on inside the panel.
const TEXT: { file: string; selector: string; ink: string[]; grounds: string[] }[] = [
  {
    file: 'TicketMessageTimeline.vue',
    selector: '.agent-timeline',
    ink: ['--timeline-muted', '--timeline-danger', '--timeline-file'],
    grounds: ['--white', '--note-ground']
  },
  { file: 'TicketMessageTimeline.vue', selector: '.agent-timeline', ink: ['--note-ink'], grounds: ['--note-ground'] },
  { file: 'TicketReplyComposer.vue', selector: '.reply-box', ink: ['--reply-muted', '--reply-danger'], grounds: ['--white'] },
  { file: 'TicketNoteComposer.vue', selector: '.note-box', ink: ['--note-ink'], grounds: ['--note-ground'] },
  { file: 'TicketNoteComposer.vue', selector: '.note-box', ink: ['--note-on-ink'], grounds: ['--note-ink'] },
  { file: 'TicketTriageControls.vue', selector: '.triage__label', ink: ['--triage-muted'], grounds: ['--white'] },
  { file: 'TicketTriageControls.vue', selector: '.triage__saving', ink: ['--triage-muted'], grounds: ['--white'] },
  { file: 'TicketFacts.vue', selector: '.ticket-facts', ink: ['--facts-muted'], grounds: ['--white'] },
  { file: 'TicketHistoryList.vue', selector: '.ticket-history', ink: ['--history-muted', '--history-danger'], grounds: ['--white'] },
  { file: 'TicketDetailPanel.vue', selector: '.ticket-panel', ink: ['--panel-muted', '--panel-danger'], grounds: ['--white'] }
]

// Lines that carry meaning without being text: the note's dashed wall, the
// active tab's rule and the focus ring.
const NON_TEXT: { file: string; selector: string; line: string; ground: string }[] = [
  { file: 'TicketMessageTimeline.vue', selector: '.agent-timeline', line: '--note-border', ground: '--note-ground' },
  { file: 'TicketNoteComposer.vue', selector: '.note-box', line: '--note-border', ground: '--note-ground' },
  { file: 'TicketDetailPanel.vue', selector: '.ticket-panel', line: '--panel-accent', ground: '--white' }
]

describe('the detail panel clears AA in both themes', () => {
  for (const theme of ['light', 'dark'] as const) {
    for (const { file, selector, ink, grounds } of TEXT) {
      for (const name of ink) {
        for (const ground of grounds) {
          it(`${theme}: ${file} ${selector} ${name} on ${ground}`, () => {
            const scope = locals(file, selector, theme)
            const measured = ratio(
              resolveColour(`var(${name})`, scope, theme),
              resolveColour(`var(${ground})`, scope, theme)
            )
            expect(measured).toBeGreaterThanOrEqual(AA_TEXT)
          })
        }
      }
    }

    for (const { file, selector, line, ground } of NON_TEXT) {
      it(`${theme}: ${file} ${line} on ${ground} (non-text)`, () => {
        const scope = locals(file, selector, theme)
        const measured = ratio(
          resolveColour(`var(${line})`, scope, theme),
          resolveColour(`var(${ground})`, scope, theme)
        )
        expect(measured).toBeGreaterThanOrEqual(AA_NON_TEXT)
      })
    }
  }

  it("the reused priority badge still clears AA on the panel's ground", () => {
    // TicketPriorityBadge paints no background, and its own measurements are
    // against the page's --bg-light. Inside this panel it sits on --white.
    const css = /<style scoped>([\s\S]*?)<\/style>/.exec(
      read('../../../../support/TicketPriorityBadge.vue')
    )![1]
    const below: string[] = []
    for (const theme of ['light', 'dark'] as const) {
      const base = block(css, '.priority-badge')
      const high = block(css, '.priority-badge--high')
      const scope =
        theme === 'light'
          ? { ...base, ...high }
          : {
              ...base,
              ...high,
              ...block(css, ':root[data-theme="dark"] .priority-badge'),
              ...block(css, ':root[data-theme="dark"] .priority-badge--high')
            }
      const ground = resolveColour('var(--white)', {}, theme)
      for (const ink of ['--ticket-muted', '--badge-danger']) {
        if (ratio(resolveColour(`var(${ink})`, scope, theme), ground) < AA_TEXT) below.push(`${theme} ${ink}`)
      }
    }
    expect(below).toEqual([])
  })

  it('puts white text on the two solid buttons, never --white', () => {
    // --white is a surface token and turns dark green in the dark theme.
    const send = block(style('TicketReplyComposer.vue'), '.reply-box__send')
    const remove = block(style('TicketDetailPanel.vue'), '.ticket-panel__delete-button')

    expect(send.color).toBe('#fff')
    expect(ratio('#ffffff', send.background)).toBeGreaterThanOrEqual(AA_TEXT)
    expect(remove.color).toBe('#fff')
    expect(ratio('#ffffff', remove.background)).toBeGreaterThanOrEqual(AA_TEXT)
  })

  it('never paints with the three tokens that fail, outside a measured dark rule', () => {
    const files = [
      'TicketDetailPanel.vue',
      'TicketMessageTimeline.vue',
      'TicketReplyComposer.vue',
      'TicketNoteComposer.vue',
      'TicketTriageControls.vue',
      'TicketFacts.vue',
      'TicketHistoryList.vue'
    ]
    const offenders = files.filter((file) =>
      /var\(--(text-muted|danger|dark-green)\)/.test(
        style(file).replace(/:root\[data-theme='dark'\][^{]*\{[^}]*\}/g, '')
      )
    )
    expect(offenders).toEqual([])
  })
})

describe('text other people wrote', () => {
  it('keeps line breaks and wraps long unbroken runs', () => {
    const css = style('TicketMessageTimeline.vue')

    expect(block(css, '.agent-timeline__body')['white-space']).toBe('pre-wrap')
    expect(block(css, '.agent-timeline')['overflow-wrap']).toBe('anywhere')
  })

  it('never renders it as markup', () => {
    const files = [
      'TicketDetailPanel.vue',
      'TicketMessageTimeline.vue',
      'TicketFacts.vue',
      'TicketHistoryList.vue'
    ]
    // The directive, not the word: a comment may say "never v-html".
    expect(files.filter((file) => /\sv-html\s*=/.test(read(`../${file}`)))).toEqual([])
  })
})
