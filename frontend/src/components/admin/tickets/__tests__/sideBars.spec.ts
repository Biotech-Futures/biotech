import { readdirSync, readFileSync, statSync } from 'node:fs'
import { dirname, join, resolve } from 'node:path'
import { fileURLToPath } from 'node:url'
import { describe, expect, it } from 'vitest'

/**
 * No thick strip down one side of a box on the support screens.
 *
 * At the 2026-10-22 meeting the client called two of them "AI UI" looks: the
 * 3px green top on the student's form card (C-24, "very commonly associated
 * with AI designs") and the 4px bar down the left of the student's waiting
 * banner (C-25, "the little side AI UI thing"). Both went, and the designer
 * had the bars like them go the same way: the attachment error, the Audit
 * tab's error, and the Users sheet's note on moving an agent off the support
 * role. This reads the styles of every support screen, so that a later
 * design round or a merge does not draw one back in unnoticed.
 *
 * A tab's underline is a border along the bottom and is not one of these.
 */
const SRC = resolve(dirname(fileURLToPath(import.meta.url)), '../../../..')
const read = (path: string) => readFileSync(resolve(SRC, path), 'utf8')

const ROOTS = [
  'components/support',
  'components/admin/tickets',
  'views/admin/tickets',
  'views/TicketDetailPage.vue',
  'views/SupportCentrePage.vue'
]

function styleFiles(path: string): string[] {
  if (statSync(resolve(SRC, path)).isFile()) return [path]
  return readdirSync(resolve(SRC, path))
    .filter((name) => name !== '__tests__')
    .flatMap((name) => {
      const child = join(path, name)
      if (statSync(resolve(SRC, child)).isDirectory()) return styleFiles(child)
      return /\.(vue|css)$/.test(name) ? [child] : []
    })
}

const FILES = ROOTS.flatMap(styleFiles)

/** The style a file draws with: a component's <style> blocks, or a whole
 *  stylesheet. */
function styles(path: string): string {
  const source = read(path)
  if (path.endsWith('.css')) return source
  return [...source.matchAll(/<style\b[^>]*>([\s\S]*?)<\/style>/g)].map((block) => block[1]).join('\n')
}

// A left, right or top edge 2px or wider, in any of the ways CSS spells one.
const SIDE_STRIP = /border-(?:left|right|top|inline-start|inline-end|block-start)(?:-width)?\s*:\s*(\d*\.?\d+)px/g

describe('no side strips on the support screens', () => {
  it('reads every support screen', () => {
    // Guards against a path change leaving the scan with nothing to read.
    expect(FILES.length).toBeGreaterThan(20)
    for (const file of [
      'components/support/TicketForm.vue',
      'components/support/TicketAttachmentPicker.vue',
      'views/TicketDetailPage.vue',
      'views/admin/tickets/TicketAuditPage.vue'
    ]) {
      expect(FILES).toContain(file)
    }
  })

  it.each(FILES)('%s draws no edge strip', (file) => {
    const strips = [...styles(file).matchAll(SIDE_STRIP)]
      .filter((match) => Number(match[1]) >= 2)
      .map((match) => match[0])
    expect(strips).toEqual([])
  })
})

describe("the Users sheet's support-role note", () => {
  // The sheet is shared with other teams, whose own notes and errors keep
  // their bars, so only this note is held to it.
  const sheet = read('components/admin/users/AdminUserFormSheet.vue')
  const style = sheet.slice(sheet.indexOf('<style'))

  it('carries the class that takes its bar away', () => {
    const note = /<p\b[^>]*\bid="f-role-support-note"[^>]*>/.exec(sheet)?.[0] ?? ''
    expect(note).toMatch(/\bclass="[^"]*\badmin-users-form__note--support\b/)
  })

  it('has no left edge, in a rule that comes after the ones that draw it', () => {
    const plain = [...style.matchAll(/\.admin-users-form__note\s*\{/g)].map((match) => match.index!)
    const support = /\.admin-users-form__note--support\s*\{([^}]*)\}/.exec(style)
    expect(plain.length).toBeGreaterThan(0)
    expect(support?.[1]).toMatch(/border-left:\s*(?:0|none)\s*;/)
    // The two selectors weigh the same, so the later one wins.
    expect(support!.index).toBeGreaterThan(Math.max(...plain))
  })
})
