import { readdirSync, readFileSync, statSync } from 'node:fs'
import { dirname, join, relative, resolve } from 'node:path'
import { fileURLToPath } from 'node:url'
import { describe, expect, it } from 'vitest'

/**
 * The peach is gone from the screens we built.
 *
 * At the 8 October meeting the client pointed at it on the designer's slides
 * ("salmon colour is not nice") and asked for it to go from the features we
 * made, not the rest of the platform (C-20). The designer's second round
 * gives every place it was used a green of his.
 *
 * It can come back two ways. Written out, as #fcede2. Or through a main.css
 * token that holds it in the light theme. Until main's 7dcee3c1 (11 October
 * 2026) two did: --light-green, which despite its name was that peach, and
 * --accent-green-soft, the same colour under another name, which slipped past
 * the first version of this test on four hovers. Since then both are the
 * brand light green. The tokens are read out of main.css rather than listed
 * here, so a name for the peach that ever comes back is caught too; dark
 * rules may keep them, as they are a translucent green there. This walks
 * every ticket screen's stylesheet and fails on either, so a later tidy-up
 * that reaches for a global token puts this test, not a client demo, in the
 * way.
 *
 * What it cannot see is a colour inherited from main.css's own rules, such as
 * `tbody tr:hover`: those are other teams' and are painted over in each
 * component, which the contrast specs measure.
 */

const SRC = resolve(dirname(fileURLToPath(import.meta.url)), '../../..')

const ROOTS = [
  'components/support',
  'components/admin/tickets',
  'views/SupportCentrePage.vue',
  'views/TicketDetailPage.vue',
  'views/SupportAccessPage.vue',
  'views/admin/tickets',
]

function vueFiles(path: string): string[] {
  const full = join(SRC, path)
  if (statSync(full).isFile()) return [full]
  return readdirSync(full).flatMap((name) =>
    name === '__tests__' ? [] : vueFiles(relative(SRC, join(full, name)))
  ).filter((file) => file.endsWith('.vue'))
}

const FILES = ROOTS.flatMap(vueFiles)

// main.css's light theme is its first, bare :root block.
const LIGHT_ROOT = readFileSync(join(SRC, 'assets/main.css'), 'utf8').match(/(?:^|\n):root\s*\{([^}]*)\}/)![1]!
const PEACH_TOKENS = [...LIGHT_ROOT.matchAll(/(--[\w-]+)\s*:\s*#fcede2\s*;/gi)].map((m) => m[1]!)
const takesPeach = (body: string) => PEACH_TOKENS.some((token) => body.includes(`var(${token})`))

function styleOf(sfc: string): string {
  return [...sfc.matchAll(/<style[^>]*>([\s\S]*?)<\/style>/g)]
    .map((m) => m[1]!)
    .join('\n')
    .replace(/\/\*[\s\S]*?\*\//g, '')
}

// Every rule, with the ones inside @media blocks taken out of them.
function rulesOf(css: string): { selectors: string[]; body: string }[] {
  const flat = css.replace(/@media[^{]*\{([\s\S]*?\})\s*\}/g, '$1')
  return [...flat.matchAll(/([^{}]+)\{([^}]*)\}/g)].map((m) => ({
    selectors: m[1]!.split(',').map((s) => s.trim()),
    body: m[2]!,
  }))
}

const isDark = (selector: string) => /^:root\[data-theme=(['"])dark\1\]/.test(selector)

describe('no ticket screen paints the peach', () => {
  it('finds the screens it is meant to walk', () => {
    // An empty list would pass everything below.
    expect(FILES.length).toBeGreaterThan(30)
    expect(FILES.some((f) => f.endsWith('TicketStatusBadge.vue'))).toBe(true)
    expect(FILES.some((f) => f.endsWith('QueueTable.vue'))).toBe(true)
  })

  it('finds no name main.css gives the peach', () => {
    // Two had it until main made them the brand light green (7dcee3c1). One
    // coming back fails here first, then wherever a ticket screen uses it.
    expect(PEACH_TOKENS).toEqual([])
  })

  for (const file of FILES) {
    const name = relative(SRC, file)

    it(`${name} does not write the peach out`, () => {
      expect(styleOf(readFileSync(file, 'utf8')).toLowerCase()).not.toContain('#fcede2')
    })

    it(`${name} takes the peach's tokens only in the dark theme`, () => {
      const light = rulesOf(styleOf(readFileSync(file, 'utf8')))
        .filter((rule) => !rule.selectors.every(isDark))
        .filter((rule) => takesPeach(rule.body))
        .map((rule) => rule.selectors.join(', '))
      expect(light).toEqual([])
    })
  }
})
