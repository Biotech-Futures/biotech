import { describe, expect, it } from 'vitest'
import { TICKET_PRIORITIES } from '@/utils/supportAPI'

/**
 * The urgency options have to fit inside a closed <select> on the narrowest
 * phone we support.
 *
 * The comment above TICKET_PRIORITIES has said since the wording was written
 * that the preselected line is the one line most students ever read, so it is
 * the line that must fit. It did not fit. At a 320px viewport the control is
 * 178.81px wide and "I can keep working for now" needs 180.81px, so the phone
 * drew "I can keep working f".
 *
 * jsdom paints nothing, so text width is computed here from Arial's own
 * advance widths rather than measured. The table below is Arial's, read out of
 * Chromium with canvas measureText at font-size 1000px, and the model agrees
 * with what the browser lays out to within 0.04px on every label in this file.
 *
 * How the two numbers were established, at a 320px viewport, control width
 * 178.81px, font 0.95rem Arial (frontend/src/components/support/TicketForm.vue
 * .ticket-form__control):
 *
 *   - the widest string Chromium painted in full was 131.69px;
 *   - the narrowest string it clipped was 135.08px.
 *
 * So the true edge is somewhere between them, and the budget is set below both
 * of them. The native dropdown arrow is what eats the difference between the
 * 152.81px content box and this figure; it sits inside the padding, so
 * subtracting padding is not enough and scrollWidth never exceeds clientWidth
 * on a <select>, which is why nothing caught this earlier.
 *
 * This walks TICKET_PRIORITIES itself. A hand-written list of the three labels
 * would go on passing after a fourth was added.
 */

// Arial advance widths in units per 1000 em, printable ASCII.
const ARIAL_1000: Record<string, number> = {
  ' ': 278, '!': 278, '"': 355, '#': 556, $: 556, '%': 889, '&': 667, "'": 191,
  '(': 333, ')': 333, '*': 389, '+': 584, ',': 278, '-': 333, '.': 278, '/': 278,
  0: 556, 1: 556, 2: 556, 3: 556, 4: 556, 5: 556, 6: 556, 7: 556, 8: 556, 9: 556,
  ':': 278, ';': 278, '<': 584, '=': 584, '>': 584, '?': 556, '@': 1015,
  A: 667, B: 667, C: 722, D: 722, E: 667, F: 611, G: 778, H: 722, I: 278,
  J: 500, K: 667, L: 556, M: 833, N: 722, O: 778, P: 667, Q: 778, R: 722,
  S: 667, T: 611, U: 722, V: 667, W: 944, X: 667, Y: 667, Z: 611,
  '[': 278, '\\': 278, ']': 278, '^': 469, _: 556, '`': 333,
  a: 556, b: 556, c: 500, d: 556, e: 556, f: 278, g: 556, h: 556, i: 222,
  j: 222, k: 500, l: 222, m: 833, n: 556, o: 556, p: 556, q: 556, r: 333,
  s: 500, t: 278, u: 556, v: 500, w: 722, x: 500, y: 500, z: 500,
  '{': 334, '|': 260, '}': 334, '~': 584,
}

// .ticket-form__control is font-size: 0.95rem against a 16px root.
const FONT_SIZE_PX = 15.2

// Under the 131.69px that was proven to paint in full at a 320px viewport.
const DRAWABLE_TEXT_PX = 130

function textWidth(label: string): number {
  return (
    Array.from(label).reduce((total, character) => {
      const advance = ARIAL_1000[character]
      // An unmeasured character would otherwise count as zero and let a long
      // label through.
      if (advance === undefined) {
        throw new Error(`no Arial advance width for ${JSON.stringify(character)}`)
      }
      return total + advance
    }, 0) /
      1000
  ) * FONT_SIZE_PX
}

describe('urgency labels fit a 320px phone', () => {
  for (const option of TICKET_PRIORITIES) {
    it(`${option.value}: "${option.label}"`, () => {
      expect(textWidth(option.label)).toBeLessThanOrEqual(DRAWABLE_TEXT_PX)
    })
  }

  it('the preselected line is the one a student reads without opening the list', () => {
    // Not an extra rule, the same rule pinned to the option it matters most
    // for. The middle option is the one the form starts on (TicketForm.vue),
    // and a label that fits in third place is no help if the default does not.
    expect(TICKET_PRIORITIES[1].value).toBe('normal')
    expect(textWidth(TICKET_PRIORITIES[1].label)).toBeLessThanOrEqual(DRAWABLE_TEXT_PX)
  })

  it('the width model matches what the browser laid out', () => {
    // Measured in Chromium at a 320px viewport with a hidden span carrying the
    // control's computed font. If this drifts, the budget above is being
    // compared against the wrong numbers.
    expect(textWidth('I can keep working for now')).toBeCloseTo(180.81, 1)
    expect(textWidth('I can keep working')).toBeCloseTo(126.75, 1)
    expect(textWidth('Help with a student or group')).toBeCloseTo(190.13, 1)
  })
})
