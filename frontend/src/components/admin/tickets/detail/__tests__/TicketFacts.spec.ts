import { mount } from '@vue/test-utils'
import { describe, expect, it } from 'vitest'

import { ticketDetailSchema } from '@/utils/ticketAgentSchema'
import TicketFacts from '../TicketFacts.vue'

/**
 * C-39: the details tab names the groups the requester is in. The client
 * asked on 26 October 2026 to "show the group numbers in this details page";
 * a group's number is its name, "BTF07" for an auto-named one.
 */

const MIA = {
  id: 1,
  name: 'Mia Thompson',
  email: 'mia@example.com',
  region: 'Australia',
  registeredAt: '2026-05-01T00:00:00Z'
}

const PAYLOAD = {
  id: 89,
  ticketNumber: 'SUP-2026-00043',
  subject: 'Cannot access group workspace',
  body: 'I get an error opening my group.',
  category: 'help_student_group',
  status: 'open',
  priority: 'normal',
  channel: 'portal',
  region: 'Australia',
  requester: MIA,
  assignee: null,
  createdAt: '2026-08-25T09:00:00Z',
  updatedAt: '2026-08-25T09:00:00Z',
  supportUpdatedAt: '2026-08-25T09:00:00Z',
  firstResponseAt: null,
  resolvedAt: null,
  overdue: false,
  messages: []
}

/** The tab's terms and values, as the reader sees them. */
function facts(requester: unknown): Record<string, string> {
  const ticket = ticketDetailSchema.parse({ ...PAYLOAD, requester })
  const wrapper = mount(TicketFacts, { props: { ticket } })
  const values = wrapper.findAll('dd').map((dd) => dd.text())
  return Object.fromEntries(wrapper.findAll('dt').map((dt, i) => [dt.text(), values[i]!]))
}

describe('the requester’s groups on the details tab', () => {
  it('names the one group the requester is in', () => {
    expect(facts({ ...MIA, groups: [{ id: 186, name: 'BTF186' }] }).Group).toBe('BTF186')
  })

  it('names every group, in the order the server sent them, under a plural term', () => {
    const shown = facts({
      ...MIA,
      groups: [
        { id: 7, name: 'BTF07' },
        { id: 186, name: 'BTF186' }
      ]
    })
    expect(shown.Groups).toBe('BTF07, BTF186')
    expect(shown.Group).toBeUndefined()
  })

  it('says so when the requester is in no group', () => {
    expect(facts({ ...MIA, groups: [] }).Group).toBe('Not in a group')
  })

  it('shows a dash for a ticket the platform raised, which has no requester', () => {
    expect(facts(null).Group).toBe('—')
  })

  it('shows a dash, not "Not in a group", when a backend from before the list sends none', () => {
    expect(facts(MIA).Group).toBe('—')
  })

  it('puts the row with the requester’s other facts, after the region', () => {
    const terms = Object.keys(facts({ ...MIA, groups: [] }))
    expect(terms.indexOf('Group')).toBe(terms.indexOf('Region') + 1)
  })
})
