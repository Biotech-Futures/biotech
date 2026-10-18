import { mount, type VueWrapper } from '@vue/test-utils'
import { afterEach, describe, expect, it } from 'vitest'

import type { TicketRow } from '@/utils/ticketAgentSchema'
import QueueTable from '../QueueTable.vue'

/** The table's own rules: columns, fallbacks, badges and row controls. React
 *  had no test for the column set or any of the fallbacks (U2 QU-22, QU-26,
 *  QU-27). Paging and the empty sentences are pinned through the page, where
 *  the walk that decides them lives. */

const ROW: TicketRow = {
  id: 1,
  ticketNumber: 'SUP-2026-00001',
  user: { name: 'Mia', region: 'Australia', anonymous: false },
  subject: 'Poster upload fails',
  status: 'open',
  priority: 'high',
  assignee: { id: 9, name: 'Sam Reid' },
  supportUpdatedAt: '2026-09-01T00:00:00Z',
  overdue: false
}

let wrapper: VueWrapper | null = null

function show(tickets: TicketRow[], selectedIds: number[] = []) {
  wrapper = mount(QueueTable, {
    props: { tickets, loading: false, failed: false, selectedIds, continuesWalk: false }
  })
  return wrapper
}

afterEach(() => {
  wrapper?.unmount()
  wrapper = null
})

function cells(rowIndex = 0) {
  return wrapper!
    .findAll('tbody tr')
    [rowIndex]!.findAll('td')
    .map((td) => td.text().replace(/\s+/g, ' '))
}

describe('the queue table', () => {
  it('has the React columns, in the React order', () => {
    show([ROW])

    expect(wrapper!.findAll('thead th').map((th) => th.text())).toEqual([
      '',
      'Ticket',
      'Requester',
      'Subject',
      'Status',
      'Priority',
      'Assignee',
      'Last activity'
    ])
  })

  it('prints a row with its requester, region, badges and owner', () => {
    show([ROW])

    const [, ticket, requester, subject, status, priority, assignee] = cells()
    expect(ticket).toBe('SUP-2026-00001')
    expect(requester).toBe('MiaAustralia')
    expect(wrapper!.get('.queue-table__region').text()).toBe('Australia')
    expect(subject).toBe('Poster upload fails')
    expect(status).toBe('Open')
    // The portal's own priority badge, reused for its measured contrast,
    // spells the word out.
    expect(priority).toBe('High priority')
    expect(assignee).toBe('Sam Reid')
  })

  it('says who is missing when a ticket has no requester or no owner', () => {
    // No requester at all on tickets the platform raised itself.
    show([{ ...ROW, user: { name: null, region: '', anonymous: false }, assignee: null }])

    const [, , requester, , , , assignee] = cells()
    expect(requester).toBe('—No requester')
    expect(wrapper!.find('.queue-table__region').exists()).toBe(false)
    expect(assignee).toBe('Unassigned')
  })

  it('marks an overdue row from the flag the server sent, and only then', () => {
    // The page never works the rule out: the server marks rows with the same
    // condition that counts the Overdue card.
    show([ROW, { ...ROW, id: 2, ticketNumber: 'SUP-2026-00002', overdue: true }])

    expect(cells(0)[4]).toBe('Open')
    expect(cells(1)[4]).toBe('OpenOverdue')
  })

  it('keeps a long subject readable in full from its title', () => {
    const subject = 'A'.repeat(300)
    show([{ ...ROW, subject }])

    expect(wrapper!.get('td.queue-table__subject').attributes('title')).toBe(subject)
  })

  it('labels every checkbox by its ticket, not by its position', () => {
    show([ROW, { ...ROW, id: 2, ticketNumber: 'SUP-2026-00002' }])

    expect(
      wrapper!.findAll('input[type="checkbox"]').map((box) => box.attributes('aria-label'))
    ).toEqual([
      'Select every ticket on this page',
      'Select SUP-2026-00001',
      'Select SUP-2026-00002'
    ])
  })

  it('reports a ticked box as a toggle of that ticket and nothing else', async () => {
    show([ROW])

    await wrapper!.get('input[aria-label="Select SUP-2026-00001"]').trigger('change')

    expect(wrapper!.emitted('toggle')).toEqual([[1]])
    expect(wrapper!.emitted('open')).toBeUndefined()
  })

  it('opens a ticket once from its button', async () => {
    show([ROW])

    await wrapper!.get('button[aria-label="Open SUP-2026-00001"]').trigger('click')

    expect(wrapper!.emitted('open')).toEqual([[1]])
  })

  it('does not open a ticket when the click lands on its checkbox cell', async () => {
    show([ROW])

    await wrapper!.get('td.queue-table__check').trigger('click')

    expect(wrapper!.emitted('open')).toBeUndefined()
  })
})

describe('the table as somewhere for focus to land', () => {
  // The page sends focus here when the control that had it is taken away
  // (TicketQueuePageFocus.spec.ts drives those cases end to end).
  it.each([
    ['rows on screen', { tickets: [ROW], loading: false }],
    ['a page still loading', { tickets: [], loading: true }],
    ['an empty page', { tickets: [], loading: false }]
  ])('is a named region the page can focus, with %s, and not a Tab stop', (_, state) => {
    wrapper = mount(QueueTable, {
      attachTo: document.body,
      props: { failed: false, selectedIds: [], continuesWalk: false, ...state }
    })

    const region = wrapper.get('[role="region"]')
    expect(region.element).toBe(wrapper.element)
    expect(region.attributes('aria-label')).toBe('Tickets')
    expect(region.attributes('tabindex')).toBe('-1')
    ;(wrapper.vm as unknown as { focus: () => void }).focus()

    expect(document.activeElement).toBe(region.element)
  })
})
