import { describe, expect, it } from 'vitest'

import SFC from '../MyTicketsTable.vue?raw'

// Only the stylesheet, and without its comments. The template above it is full
// of {{ }}, and a comment sitting on top of a rule reads as part of its
// selector, so both would make nonsense of reading CSS blocks out of the file.
const SOURCE = (SFC.match(/<style scoped>([\s\S]*)<\/style>/) as RegExpMatchArray)[1].replace(
  /\/\*[\s\S]*?\*\//g,
  '',
)

/**
 * Where the ticket table puts its sideways overflow.
 *
 * What went wrong: the wrapper only became a scroller inside
 * @media (max-width: 720px). Above that it was overflow: visible, so the
 * nearest scrolling ancestor was .content-area and the table dragged the whole
 * column sideways with it, form and help card included, behind a scrollbar
 * macOS hides until it is used. Six columns want about 560px, and a tablet in
 * portrait or a half-width laptop window is narrower than that once the
 * padding is taken off.
 *
 * jsdom lays nothing out, so this reads the rules. Measured in Chromium with
 * the component's real styles in a fixed-width column (three realistic rows):
 *
 *   column 420px   before: the column itself scrolled sideways
 *                  after:  the table's own box scrolls, the column does not
 *   column 500px   same
 *   column 620px   nothing overflows either way
 *
 * and with one 200-character URL pasted into a subject, which is the sharper
 * version of the same edge:
 *
 *   column 900px   before: table 1130px wide, four headers off the column
 *                  after:  table 836px wide, none off
 */

function declarationsFor(selector: string, { insideMediaQuery = false } = {}): string {
  // Strip the media blocks, or keep only them, so a rule can be pinned to the
  // side of the query it is meant to be on.
  const mediaBlocks = SOURCE.match(/@media[^{]*\{[\s\S]*?\n\}/g) || []
  const scope = insideMediaQuery
    ? mediaBlocks.map((block) => block.replace(/^@media[^{]*\{/, '').replace(/\n\}$/, '')).join('\n')
    : mediaBlocks.reduce((text, block) => text.replace(block, ''), SOURCE)

  // Every block this selector appears in, not the first one: the file declares
  // .my-tickets twice, and a check that stopped at the first would report
  // whatever the other one said as missing.
  const blocks = Array.from(scope.matchAll(/([^{}@]+)\{([^}]*)\}/g))
  return blocks
    .filter(([, selectors]) =>
      selectors.split(',').some((one) => one.trim() === selector)
    )
    .map(([, , body]) => body)
    .join('\n')
}

function value(declarations: string, property: string): string | null {
  const match = declarations.match(new RegExp(`(^|\\n|;)\\s*${property}\\s*:\\s*([^;]+);`))
  return match ? match[2].trim() : null
}

describe('MyTicketsTable keeps its overflow to itself', () => {
  it('scrolls its own box at every width, not just on a phone', () => {
    // Unconditional. Inside the media query this rule was, the defect was.
    expect(value(declarationsFor('.my-tickets'), 'overflow-x')).toBe('auto')
  })

  it('still gives the table a floor to scroll against on a phone', () => {
    // The other half of the phone rule, which the fix must not take with it:
    // without it the columns squeeze instead of scrolling.
    expect(value(declarationsFor('.my-tickets__table', { insideMediaQuery: true }), 'min-width')).toBe(
      '560px'
    )
  })

  it('lets a pasted link break so it cannot set the column width', () => {
    // `anywhere`, not `break-word`: only `anywhere` lowers the min-content
    // width, and min-content is the number a table is laid out from.
    expect(value(declarationsFor('.my-tickets__subject'), 'overflow-wrap')).toBe('anywhere')
  })
})
