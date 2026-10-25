import { readFileSync } from 'node:fs'
import { dirname, resolve } from 'node:path'
import { fileURLToPath } from 'node:url'
import { describe, expect, it } from 'vitest'

/**
 * Every dropdown on the ticket screens is the platform's AppSelect since the
 * 2026-10-22 client meeting (C-29), or the queue's own check-box list built
 * to look like it (C-27). Both ring the box, not the field inside that has
 * keyboard focus, and both ring it in --dark-green, which the dark theme does
 * not redefine: about 2.8:1 on the dark grounds, under the 3:1 a focus
 * indicator needs. The screens' own dark rings (`:deep(:focus-visible)` and
 * the like) never reach that box, because the box is not what is focused.
 *
 * So each box gets a dark override of its own, `.box:has(:focus-visible)`,
 * and this reads every ticket file for its dropdowns, so a dropdown added
 * later is held to it whether or not anybody remembers.
 */
const SRC = resolve(dirname(fileURLToPath(import.meta.url)), '../../../..')
const read = (path: string) => readFileSync(resolve(SRC, path), 'utf8')

const FILES = [
  'components/support/TicketForm.vue',
  'components/admin/tickets/detail/TicketReplyComposer.vue',
  'components/admin/tickets/detail/TicketTriageControls.vue',
  'components/admin/tickets/queue/BulkAssignBar.vue',
  'components/admin/tickets/queue/PageSizeControl.vue',
  'components/admin/tickets/audit/AuditPager.vue',
  'views/admin/tickets/TicketAuditPage.vue',
  'views/admin/tickets/TicketAnalyticsPage.vue'
]

// main.css's dark theme: the page, a field, and a card. Every ticket
// dropdown sits on one of these.
const MAIN = read('assets/main.css')
const darkBlock = MAIN.slice(MAIN.indexOf(':root[data-theme="dark"]'))
const lightBlock = MAIN.slice(MAIN.indexOf(':root {'), MAIN.indexOf(':root[data-theme="dark"]'))
function token(name: string, block: string): string | undefined {
  return new RegExp(`${name}:\\s*(#[0-9a-fA-F]{6})`).exec(block)?.[1]
}
const DARK_GROUNDS = ['--bg-light', '--white', '--surface-elevated'].map((name) => token(name, darkBlock)!)

function colourOf(value: string): string {
  const named = /^var\((--[\w-]+)\)$/.exec(value.trim())
  // A name the dark theme leaves alone keeps its light value there.
  if (named) return token(named[1], darkBlock) ?? token(named[1], lightBlock)!
  return value.trim()
}

function luminance(hex: string): number {
  const channels = [1, 3, 5].map((at) => parseInt(hex.slice(at, at + 2), 16) / 255)
  const [r, g, b] = channels.map((c) => (c <= 0.03928 ? c / 12.92 : ((c + 0.055) / 1.055) ** 2.4))
  return 0.2126 * r + 0.7152 * g + 0.0722 * b
}

function contrast(a: string, b: string): number {
  const [hi, lo] = [luminance(a), luminance(b)].sort((x, y) => y - x)
  return (hi + 0.05) / (lo + 0.05)
}

/** The class list of each AppSelect in a file: the box it rings. */
function boxes(sfc: string): string[] {
  const template = sfc.slice(0, sfc.indexOf('<script'))
  return [...template.matchAll(/<AppSelect\b[^>]*?\sclass="([^"]*)"/g)].map((m) => m[1].trim())
}

/** The outline colour a file's dark rule gives the box, under any of its
 *  classes: `.class:has(:focus-visible)`. */
function darkRing(sfc: string, box: string): string | undefined {
  const css = sfc.slice(sfc.indexOf('<style')).replace(/\/\*[\s\S]*?\*\//g, '')
  const wanted = box.split(/\s+/).map((name) => `:root[data-theme='dark'] .${name}:has(:focus-visible)`)
  for (const [, selectors, body] of css.matchAll(/([^{}]+)\{([^}]*)\}/g)) {
    const listed = selectors.split(',').map((one) => one.trim())
    if (!listed.some((one) => wanted.includes(one))) continue
    const colour = /outline-color:\s*([^;]+);/.exec(body)?.[1]
    if (colour) return colour
  }
  return undefined
}

describe('the dark focus ring on every ticket dropdown', () => {
  it('finds the dropdowns it is about', () => {
    // Load-bearing: a reader that found none would pass everything below.
    expect(FILES.flatMap((file) => boxes(read(file)))).toEqual([
      'ticket-form__control ticket-form__select',
      'ticket-form__control ticket-form__select',
      'reply-box__select',
      'triage__select',
      'triage__select',
      'triage__select',
      'triage__select',
      'bulk-assign__select',
      'page-size__select',
      'audit-pager__select',
      'ticket-audit__filter',
      'ticket-audit__filter',
      'ticket-analytics__input ticket-analytics__select'
    ])
    expect(DARK_GROUNDS).toEqual(['#0f1715', '#161f1d', '#1d2826'])
  })

  for (const file of FILES) {
    for (const box of [...new Set(boxes(read(file)))]) {
      it(`${file}: "${box}" rings in a colour that clears 3:1 on every dark ground`, () => {
        const ring = darkRing(read(file), box)
        expect(ring, `no dark :has(:focus-visible) rule for "${box}"`).toBeDefined()
        for (const ground of DARK_GROUNDS) {
          expect(contrast(colourOf(ring!), ground)).toBeGreaterThanOrEqual(3)
        }
      })
    }
  }

  it('holds the queue’s check-box list to the same', () => {
    const sfc = read('components/admin/tickets/queue/QueueFilterSelect.vue')
    const css = sfc.slice(sfc.indexOf('<style')).replace(/\/\*[\s\S]*?\*\//g, '')
    const rule = /:root\[data-theme='dark'\] \.filter-select:has\(\.filter-select__button:focus-visible\)\s*\{([^}]*)\}/.exec(css)
    const ring = rule && /outline-color:\s*([^;]+);/.exec(rule[1])?.[1]
    expect(ring).toBeDefined()
    for (const ground of DARK_GROUNDS) {
      expect(contrast(colourOf(ring!), ground)).toBeGreaterThanOrEqual(3)
    }
  })

  it('measures what the box would have without it as the failure it is', () => {
    // The reason for all of the above, so it cannot quietly stop being true.
    const fallback = colourOf('var(--dark-green)')
    expect(DARK_GROUNDS.some((ground) => contrast(fallback, ground) < 3)).toBe(true)
  })
})
