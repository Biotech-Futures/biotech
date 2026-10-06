import { describe, expect, it } from 'vitest'

import TIMELINE from '../TicketTimeline.vue?raw'
import TICKET_DETAIL_PAGE from '@/views/TicketDetailPage.vue?raw'

/**
 * How a ticket conversation sits on the page.
 *
 * Client items C-07 and C-08. The bubbles sat too far apart to read as one
 * conversation: each row was as wide as the 60rem page and a bubble stopped
 * at 38rem, so a short reply sat on the far left, the short message above it
 * on the far right, and the screen between them was empty. The owner chose
 * the Instagram and Messenger shape: the requester on the right, support on
 * the left, both in one narrower column, with bubbles that fill most of it.
 * Separately, the status and priority badges in the header sat too close.
 *
 * jsdom lays nothing out, so this reads the rules. Measured in Chromium 149
 * with the real markup shape and the styles of both files, in light and dark:
 *
 *   1280px   short reply to short message   before 454px apart   after 190px
 *            long bubble                    before 608px         after 626px
 *   768px    long bubble                    before 555px         after 575px
 *   375px    long bubble                    before 233px         after 241px
 *            requester's name and stamp     before each on two   after one line each
 *                                           lines, side by side
 *   badges   space between the two          before 5.6px         after 9.6px
 *
 * and nothing wider than the column at 320, 375, 768, 1024, 1280 or 1440.
 *
 * The first redesign round (October 2026) then laid it out again, and the
 * owner took the designer's layout over the narrower column (decision
 * DEC-046): the thread runs the full width of the page, so support lines up
 * with the title and the requester with the badges, a message may take 74%
 * of it (a long bubble 663px at 1440px, wider than the 626px before), and
 * the name and stamp sit above each bubble. The rules below are that
 * layout's; the left and right sides and the tucked corners are what both
 * layouts keep.
 */

function stylesheet(sfc: string): string {
  // Only the stylesheet, and without its comments. The template above it is
  // full of {{ }}, and a comment sitting on top of a rule reads as part of
  // its selector, so both would make nonsense of reading CSS blocks out.
  const style = (sfc.match(/<style scoped>([\s\S]*)<\/style>/) as RegExpMatchArray)[1]
  return style.replace(/\/\*[\s\S]*?\*\//g, '')
}

function declarationsFor(sfc: string, selector: string): string {
  const source = stylesheet(sfc)
  // Media blocks dropped: a rule that only holds on a phone is not the rule
  // this file is asking for. Neither file has one today.
  const withoutMedia = (source.match(/@media[^{]*\{[\s\S]*?\n\}/g) || []).reduce(
    (text, block) => text.replace(block, ''),
    source,
  )
  const bodies = Array.from(withoutMedia.matchAll(/([^{}@]+)\{([^}]*)\}/g))
    .filter(([, selectors]) => selectors.split(',').some((one) => one.trim() === selector))
    .map(([, , body]) => body)
  // A selector that is not in the file at all would otherwise read as every
  // property being absent, and the message would not say why.
  if (!bodies.length) throw new Error(`no rule for ${selector}`)
  return bodies.join('\n')
}

function value(declarations: string, property: string): string | null {
  const match = declarations.match(new RegExp(`(^|\\n|;)\\s*${property}\\s*:\\s*([^;]+);`))
  return match ? match[2].trim() : null
}

describe('the conversation reads as one exchange', () => {
  it('runs the conversation the full width of the page', () => {
    // No column of its own any more (DEC-046): no cap, and nothing centring
    // a narrower box under the header.
    const thread = declarationsFor(TICKET_DETAIL_PAGE, '.ticket__conversation')
    expect(value(thread, 'max-width')).toBeNull()
    expect(value(thread, 'margin')).not.toMatch(/auto/)
  })

  it('lets a message fill most of the thread', () => {
    // A share of the thread, not a rem cap: 74% is the designer's, and on
    // the full-width thread it makes a long bubble wider than before.
    expect(value(declarationsFor(TIMELINE, '.timeline__message'), 'max-width')).toBe('74%')
  })

  it('leaves room for the name above each bubble', () => {
    // The gap runs from the foot of one message to the name over the next.
    expect(value(declarationsFor(TIMELINE, '.timeline'), 'gap')).toBe('0.875rem')
  })

  it('rounds the bubbles the way a messaging app does', () => {
    expect(value(declarationsFor(TIMELINE, '.timeline__bubble'), 'border-radius')).toBe('18px')
  })

  it('tucks in the corner nearest the requester on their own messages', () => {
    expect(
      value(
        declarationsFor(TIMELINE, '.timeline__row--mine .timeline__bubble'),
        'border-bottom-right-radius',
      ),
    ).toBe('6px')
  })

  it('tucks in the corner nearest support on a reply', () => {
    expect(
      value(
        declarationsFor(TIMELINE, '.timeline__row--support .timeline__bubble'),
        'border-bottom-left-radius',
      ),
    ).toBe('6px')
  })

  it('keeps the requester on the right, support on the left and system notes centred', () => {
    // What the reshaping must not move.
    expect(value(declarationsFor(TIMELINE, '.timeline__row--mine'), 'justify-content')).toBe(
      'flex-end',
    )
    expect(value(declarationsFor(TIMELINE, '.timeline__row--support'), 'justify-content')).toBe(
      'flex-start',
    )
    expect(value(declarationsFor(TIMELINE, '.timeline__row--system'), 'justify-content')).toBe(
      'center',
    )
  })

  it('moves the stamp under the name whole when the two do not fit side by side', () => {
    // The stamp carries the time now. On a 375px phone the name and the stamp
    // squeezed into one line and each broke across two; wrapping puts each on
    // a line of its own instead.
    expect(value(declarationsFor(TIMELINE, '.timeline__meta'), 'flex-wrap')).toBe('wrap')
  })

  it("keeps a system note's stamp in one piece when the note wraps", () => {
    // Without it the resolved note ended one line on "24" and started the
    // next on "September 2026, 3:37 pm" at 1280px.
    expect(value(declarationsFor(TIMELINE, '.timeline__system time'), 'display')).toBe(
      'inline-block',
    )
  })
})

describe('the badges in the enquiry header', () => {
  it('puts clear space between the status and the priority', () => {
    // 0.35rem read as one block.
    expect(value(declarationsFor(TICKET_DETAIL_PAGE, '.ticket__badges'), 'gap')).toBe('0.6rem')
  })

  it('still stacks them on the right, one above the other', () => {
    const badges = declarationsFor(TICKET_DETAIL_PAGE, '.ticket__badges')
    expect(value(badges, 'flex-direction')).toBe('column')
    expect(value(badges, 'align-items')).toBe('flex-end')
  })
})
