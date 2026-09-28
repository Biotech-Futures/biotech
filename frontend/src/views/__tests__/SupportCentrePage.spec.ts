import { flushPromises, mount } from '@vue/test-utils'
import { beforeEach, describe, expect, it, vi } from 'vitest'
import SupportCentrePage from '../SupportCentrePage.vue'

vi.mock('vue-router', () => ({
  useRouter: () => ({ push: vi.fn() }),
  RouterLink: { template: '<a><slot /></a>' },
}))

vi.mock('@/utils/supportAPI', async () => {
  const actual = await vi.importActual<typeof import('@/utils/supportAPI')>(
    '@/utils/supportAPI'
  )
  return { ...actual, fetchMyTickets: vi.fn() }
})

import { fetchMyTickets } from '@/utils/supportAPI'

const fetchMock = vi.mocked(fetchMyTickets)

import type { TicketRow } from '@/utils/supportAPI'

function row(id: number): TicketRow {
  return {
    id,
    ticketNumber: `SUP-2026-0000${id}`,
    subject: `Ticket ${id}`,
    category: 'help_student_group',
  priority: 'normal',
    status: 'open',
    lastUpdated: '2026-08-01T00:00:00Z',
  }
}

function pageOf(
  ids: number[],
  {
    total = 20,
    page = 1,
    hasMore = true,
    asOf = '2026-09-02T04:00:00Z',
    after = '2026-09-02T04:00:00Z_1',
  } = {}
) {
  return { items: ids.map(row), total, page, limit: 10, hasMore, asOf, after }
}

/**
 * "Show more" appends to a list that is already on screen, which makes its
 * failure rules different from first load: there is something to protect.
 * All three rules held when traced by hand and none had a test, so any of
 * them could be lost in a refactor with the suite green — and the symptom
 * (a list that blinks empty, or an error that wipes ten rows) is exactly
 * the kind of thing only the manual checklist would ever catch again.
 */
describe('SupportCentrePage Show more', () => {
  beforeEach(() => {
    fetchMock.mockReset()
  })

  it('appends the next page under the rows already on screen', async () => {
    fetchMock.mockResolvedValueOnce(pageOf([1, 2], { page: 1 }))
    const wrapper = mount(SupportCentrePage)
    await flushPromises()
    expect(wrapper.text()).toContain('SUP-2026-00001')

    fetchMock.mockResolvedValueOnce(pageOf([3], { page: 2, hasMore: false }))
    await wrapper.get('button.support__more-button').trigger('click')
    await flushPromises()

    // Both pages, not just the newest one.
    for (const number of ['SUP-2026-00001', 'SUP-2026-00002', 'SUP-2026-00003']) {
      expect(wrapper.text()).toContain(number)
    }
  })

  it('keeps the rows it has when the second page fails', async () => {
    fetchMock.mockResolvedValueOnce(pageOf([1, 2], { page: 1 }))
    const wrapper = mount(SupportCentrePage)
    await flushPromises()

    fetchMock.mockRejectedValueOnce(new Error('network down'))
    await wrapper.get('button.support__more-button').trigger('click')
    await flushPromises()

    expect(wrapper.text()).toContain('SUP-2026-00001')
    expect(wrapper.text()).toContain('SUP-2026-00002')
  })

  it('walks later pages from where the last one ended', async () => {
    /**
     * Without this the list pages over a live ordering: an enquiry that gets
     * a reply between two "Show more" clicks moves above what is already on
     * screen and is never loaded at all.
     *
     * Both halves are asserted, and so is their absence on the first call.
     * Checking only that page two carries them would still pass if page one
     * carried them too, and page one sending a snapshot is how the list would
     * stop showing anything that arrived while the reader was away.
     */
    fetchMock.mockResolvedValueOnce(
      pageOf([1], { page: 1, asOf: 'STAMP', after: 'STAMP_7' }),
    )
    const wrapper = mount(SupportCentrePage)
    await flushPromises()

    fetchMock.mockResolvedValueOnce(pageOf([2], { page: 2, hasMore: false }))
    await wrapper.get('button.support__more-button').trigger('click')
    await flushPromises()

    expect(fetchMock.mock.calls[0][2]).toBeUndefined()
    expect(fetchMock.mock.calls[1][2]).toEqual({ asOf: 'STAMP', after: 'STAMP_7' })
  })

  it('stops walking when a page comes back with no cursor', async () => {
    /**
     * A null cursor means there was no last row. Sending the previous page's
     * cursor again would serve the same rows twice; sending nothing restarts
     * the walk, which is the honest answer to "there is nothing after this".
     */
    fetchMock.mockResolvedValueOnce(
      pageOf([1], { page: 1, asOf: 'STAMP', after: null as unknown as string }),
    )
    const wrapper = mount(SupportCentrePage)
    await flushPromises()

    fetchMock.mockResolvedValueOnce(pageOf([2], { page: 2, hasMore: false }))
    await wrapper.get('button.support__more-button').trigger('click')
    await flushPromises()

    expect(fetchMock.mock.calls[1][2]).toBeUndefined()
  })

  it('reports a second-page failure in its own slot, not the page-level one', async () => {
    fetchMock.mockResolvedValueOnce(pageOf([1], { page: 1 }))
    const wrapper = mount(SupportCentrePage)
    await flushPromises()

    fetchMock.mockRejectedValueOnce(new Error('network down'))
    await wrapper.get('button.support__more-button').trigger('click')
    await flushPromises()

    // The alert renders under the table; the table itself is still there.
    expect(wrapper.get('[role="alert"]').text()).toContain('network down')
    expect(wrapper.text()).toContain('SUP-2026-00001')
  })
})

describe('the promise at the foot of the page', () => {
  /**
   * p48 ends with "You can reply to any open ticket in this portal or by
   * email. We'll keep all updates in one place." Half of that is a promise we
   * cannot keep: replies by email are a later goal, nothing reads the support
   * mailbox, and outbound mail is sent from info@. A student who believed the
   * "or by email" half would type an answer into a mail client and wait for a
   * reply nobody would ever see.
   *
   * So the page states the half that is true. This test is the guard against
   * somebody restoring the client's sentence verbatim before the inbound
   * channel exists.
   */
  beforeEach(() => {
    fetchMock.mockResolvedValue(pageOf([1], { total: 1, hasMore: false }))
  })

  it('promises email updates, which we do send', async () => {
    const wrapper = mount(SupportCentrePage)
    await flushPromises()

    expect(wrapper.get('.support__promise').text()).toContain(
      'we will email you every update'
    )
  })

  it('does not offer replying by email, which we cannot receive', async () => {
    const wrapper = mount(SupportCentrePage)
    await flushPromises()

    // Replying *on the page* is exactly what we do offer, so the forbidden
    // thing is the pairing: any form of "reply ... by email" inside one
    // sentence. The client's original wording matches this and ours does not.
    const promise = wrapper.get('.support__promise').text().toLowerCase()
    expect(promise).not.toMatch(/repl\w*[^.]*by email/)
    expect(promise).not.toMatch(/by email[^.]*repl\w*/)
  })
})
