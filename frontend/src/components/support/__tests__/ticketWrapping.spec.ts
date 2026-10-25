import { describe, expect, it } from 'vitest'

import TIMELINE from '../TicketTimeline.vue?raw'
import TICKET_DETAIL_PAGE from '@/views/TicketDetailPage.vue?raw'

/**
 * Where an unbroken run of text is allowed to break on a ticket.
 *
 * What went wrong: MyTicketsTable.vue was taught this and the enquiry page
 * next door was not. A subject is whatever the requester typed and people
 * paste links into them, and subject holds 255 characters. One 200-character
 * URL sets the minimum width of .content-area, and the whole column goes
 * sideways behind a scrollbar macOS hides until it is used. The timeline has
 * three more of the same: a bounce note carries an email address, an
 * attachment carries a filename, and both are held to 255 too.
 *
 * jsdom lays nothing out, so this reads the rules. Measured in Chromium 1234
 * with the real markup and styles of both files, .content-area scrollWidth
 * over clientWidth:
 *
 *   375px   before 1625/375   after 375/375
 *   900px   before 1625/900   after 900/900
 *   1280px  before 1625/960   after 960/960
 *
 * and how far past the right edge of the column each line ran, before:
 *
 *   h1.ticket__title            +1176px at 375, +651px at 900, +591px at 1280
 *   .timeline__system           +88px at 375 (an address with no hyphen in it)
 *   .timeline__files a          +401px at 375, +48px at 900
 *   .timeline__author           +65px at 375 (one long name, no space)
 *
 * after, every one of them is inside the column at every width. The table
 * half of this is in myTicketsTableLayout.spec.ts.
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
  return Array.from(withoutMedia.matchAll(/([^{}@]+)\{([^}]*)\}/g))
    .filter(([, selectors]) => selectors.split(',').some((one) => one.trim() === selector))
    .map(([, , body]) => body)
    .join('\n')
}

function value(declarations: string, property: string): string | null {
  const match = declarations.match(new RegExp(`(^|\\n|;)\\s*${property}\\s*:\\s*([^;]+);`))
  return match ? match[2].trim() : null
}

function rootClasses(sfc: string): string[] {
  // The classes on the outermost element of the template, which is the only
  // place a rule reaches every line inside the component from.
  const template = (sfc.match(/<template>([\s\S]*?)\n<\/template>/) as RegExpMatchArray)[1]
  const firstTag = template.match(/<[a-zA-Z][^>]*>/) as RegExpMatchArray
  const classes = firstTag[0].match(/\sclass="([^"]*)"/)
  if (!classes) throw new Error(`no class on the root element: ${firstTag[0]}`)
  return classes[1].trim().split(/\s+/)
}

describe('long text on a ticket breaks instead of widening the page', () => {
  it('breaks a pasted link in the enquiry title', () => {
    // `anywhere`, not `break-word`: only `anywhere` lowers the min-content
    // width, and min-content is the number the column is laid out from.
    expect(value(declarationsFor(TICKET_DETAIL_PAGE, '.ticket__title'), 'overflow-wrap')).toBe(
      'anywhere',
    )
  })

  it('breaks every line on the timeline, not one of them', () => {
    expect(value(declarationsFor(TIMELINE, '.timeline'), 'overflow-wrap')).toBe('anywhere')
  })

  it('declares that on the timeline root, so it reaches all four lines', () => {
    // A system note, an attachment name, an author and a body each sit in a
    // different block. Declared anywhere below the root it would reach one of
    // them and the other three would go on setting the column width.
    expect(rootClasses(TIMELINE)).toContain('timeline')
  })
})
