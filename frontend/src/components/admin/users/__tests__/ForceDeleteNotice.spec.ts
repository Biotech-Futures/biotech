import { describe, expect, it } from 'vitest'
import { mount } from '@vue/test-utils'

import ForceDeleteNotice from '../ForceDeleteNotice.vue'

/**
 * The sentence an admin reads before destroying somebody's content, pinned
 * word for word (ported from adminweb ForceDeleteNotice.test.tsx).
 *
 * It is written out here rather than imported from the component, because
 * comparing the component against itself would pass whatever it said. What
 * this guards is not the wording as such: it is that the wording keeps naming
 * support tickets. It stopped doing that once already: tickets were added to
 * the purge and every copy of this list stayed as it was, so the checkbox
 * promised to delete four things and deleted five. The portal's own two
 * copies were still the four-item version when this was ported.
 */
const text = (subject: string) =>
  mount(ForceDeleteNotice, { props: { subject } })
    .text()
    .replace(/\s+/g, ' ')
    .trim()

describe('the force delete notice', () => {
  it('says exactly what is destroyed', () => {
    expect(text('user')).toBe(
      "Force delete: also permanently delete each user's chat messages, uploaded resources, " +
        'workshops, match runs, and any support ticket they raised, including the replies and ' +
        'internal notes support staff wrote on it. Required to remove accounts that have any activity.'
    )
  })

  it('names support tickets, which the purge destroys', () => {
    const notice = text('user')
    expect(notice).toContain('any support ticket they raised')
    // Not just the ticket: an agent's replies and internal notes go with it,
    // and those belong to work somebody else is doing.
    expect(notice).toContain('internal notes support staff wrote on it')
  })

  it('still names everything it named before tickets were added', () => {
    const notice = text('user')
    for (const item of ['chat messages', 'uploaded resources', 'workshops', 'match runs']) {
      expect(notice).toContain(item)
    }
  })

  it('says whose content it is, on each of the three tabs that use it', () => {
    // Users, Students and Supervisors share this sentence and each names its
    // own subject. A single hard-coded noun would have read "each user's" on
    // the students tab, which is where most tickets come from.
    for (const subject of ['user', 'supervisor', 'student']) {
      expect(text(subject)).toContain(`each ${subject}'s chat messages`)
    }
  })

  it('carries no em-dash (port UI copy rule)', () => {
    expect(text('user')).not.toContain('—')
  })
})
