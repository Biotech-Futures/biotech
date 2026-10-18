import { flushPromises, mount } from '@vue/test-utils'
import { createPinia, setActivePinia } from 'pinia'
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest'
import SupportCentrePage from '../SupportCentrePage.vue'
import { setSupervisorPages } from '@/composables/useSupervisorPages'
import { useAuthStore } from '@/stores/auth'

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

vi.mock('@/utils/resourcesAPI', async () => {
  const actual = await vi.importActual<typeof import('@/utils/resourcesAPI')>(
    '@/utils/resourcesAPI'
  )
  return { ...actual, fetchResourceLabels: vi.fn(async () => []) }
})

import { fetchMyTickets } from '@/utils/supportAPI'
import { fetchResourceLabels } from '@/utils/resourcesAPI'

const fetchMock = vi.mocked(fetchMyTickets)
const labelsMock = vi.mocked(fetchResourceLabels)

// The page reads who is signed in (the help panel below), so every mount
// needs a store, signed in or not.
beforeEach(() => {
  setActivePinia(createPinia())
})

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

/**
 * The second redesign round's header (D2-01): no small capitals above the
 * title, and the client's p48 question, "How can we help?", as the line
 * under it, now that the form below is called "Raise an enquiry". The help
 * card's opening sentence is his one-liner (D2-07).
 */
describe('the page header', () => {
  beforeEach(() => {
    fetchMock.mockResolvedValue(pageOf([], { total: 0, hasMore: false }))
  })

  it('asks the client’s question under the title', async () => {
    const wrapper = mount(SupportCentrePage)
    await flushPromises()

    const hero = wrapper.get('header.support__hero')
    expect(hero.get('h1').text()).toBe('Support Centre')
    expect(hero.get('.support__tagline').text()).toBe('How can we help?')
    expect(hero.text()).not.toMatch(/help and support/i)
  })

  it('opens the help card with one short sentence', async () => {
    const wrapper = mount(SupportCentrePage)
    await flushPromises()

    expect(wrapper.get('.support__selfserve-lede').text()).toBe('Quick answers to common questions.')
  })
})

/**
 * The help panel links each topic to its shelf in Resources. Resources is one
 * of the pages Management > Supervisor Pages Visibility keeps from a
 * supervisor until it shows them (the router guard sends them to their
 * profile), so while it is off a supervisor gets the topics as text.
 */
describe('SupportCentrePage help panel', () => {
  const supervisor = {
    id: 31,
    email: 'supervisor@example.com',
    first_name: 'Sue',
    last_name: 'Park',
    current_role_name: 'supervisor',
    timezone: 'UTC',
    must_change_password: false,
    isAdmin: false,
    isSupport: false
  }

  beforeEach(() => {
    fetchMock.mockReset()
    fetchMock.mockResolvedValue(pageOf([], { total: 0, hasMore: false }))
    // A shelf for one topic, so that topic is offered as a link.
    labelsMock.mockResolvedValue([{ id: 7, name: 'Registration' }])
  })

  afterEach(() => {
    setSupervisorPages({ shown: false })
    labelsMock.mockResolvedValue([])
  })

  async function panelFor(user: object, pagesShown: boolean) {
    setSupervisorPages({ shown: pagesShown })
    useAuthStore().loginWithUser(user as never)
    const wrapper = mount(SupportCentrePage)
    await flushPromises()
    return wrapper.get('.support__selfserve').text()
  }

  it('names the topics without linking a supervisor to Resources while it is hidden', async () => {
    const panel = await panelFor(supervisor, false)

    expect(panel).toContain('Registration')
    expect(panel).not.toContain('Read the guides')
    expect(panel).not.toContain('View all help articles in Resources')
  })

  it('links them for a supervisor once the pages are shown', async () => {
    const panel = await panelFor(supervisor, true)

    expect(panel).toContain('Read the guides')
    expect(panel).toContain('View all help articles in Resources')
  })

  it('links them for a student whatever the switch says', async () => {
    const panel = await panelFor({ ...supervisor, id: 32, current_role_name: 'student' }, false)

    expect(panel).toContain('Read the guides')
    expect(panel).toContain('View all help articles in Resources')
  })
})

