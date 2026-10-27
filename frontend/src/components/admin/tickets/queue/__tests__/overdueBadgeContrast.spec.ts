import { describe, expect, it } from 'vitest'

// Read as text rather than rendered: jsdom applies no scoped-SFC styles, so a
// mounted badge reports no colours at all. Same approach as
// components/support/__tests__/statusBadgeContrast.spec.ts.
import SOURCE from '../OverdueBadge.vue?raw'

/**
 * The Overdue badge is the one badge the queue could not borrow from the
 * portal: the status and priority badges already exist with measured pairs,
 * this one did not. The React colours (red-100 / red-800) were chosen against
 * the admin app's ground and U2 KEEP-32 says to re-measure rather than copy.
 *
 * Both halves of each pair must be literal and opaque, so the contrast cannot
 * be moved from another file, and each pair must clear 4.5:1, the threshold
 * for text this size. The ratio is computed here, not copied from the
 * component's comment.
 */

const AA_NORMAL_TEXT = 4.5

function ruleFor(theme: 'light' | 'dark'): string {
  const selector =
    theme === 'dark' ? String.raw`:root\[data-theme='dark'\] \.overdue-badge` : String.raw`\.overdue-badge`
  const match = SOURCE.match(new RegExp(`(^|\\n)${selector}\\s*\\{([^}]*)\\}`))
  if (!match) throw new Error(`no ${theme} rule`)
  return match[2]!
}

function declaration(rule: string, property: string): string {
  const match = rule.match(new RegExp(`(?:^|[\\s;])${property}\\s*:\\s*([^;]+);`))
  if (!match) throw new Error(`no ${property} in ${JSON.stringify(rule)}`)
  return match[1]!.trim()
}

function channel(value: number): number {
  const c = value / 255
  return c <= 0.04045 ? c / 12.92 : ((c + 0.055) / 1.055) ** 2.4
}

function luminance(hex: string): number {
  const m = /^#([0-9a-f]{2})([0-9a-f]{2})([0-9a-f]{2})$/i.exec(hex)
  if (!m) throw new Error(`not an opaque hex colour: ${hex}`)
  const [r, g, b] = m.slice(1).map((pair) => channel(parseInt(pair, 16)))
  return 0.2126 * r! + 0.7152 * g! + 0.0722 * b!
}

function contrast(foreground: string, background: string): number {
  const a = luminance(foreground)
  const b = luminance(background)
  return (Math.max(a, b) + 0.05) / (Math.min(a, b) + 0.05)
}

describe('OverdueBadge colours', () => {
  for (const theme of ['light', 'dark'] as const) {
    it(`${theme}: reads at AA`, () => {
      const rule = ruleFor(theme)
      const background = declaration(rule, 'background')
      const color = declaration(rule, 'color')

      expect(background).toMatch(/^#[0-9a-f]{6}$/i)
      expect(color).toMatch(/^#[0-9a-f]{6}$/i)
      expect(contrast(color, background)).toBeGreaterThanOrEqual(AA_NORMAL_TEXT)
    })
  }
})
