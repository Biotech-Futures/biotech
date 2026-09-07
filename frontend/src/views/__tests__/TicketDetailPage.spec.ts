import { flushPromises, mount } from '@vue/test-utils'
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest'
import type { TicketDetail } from '@/utils/supportAPI'

/**
 * The address bar and the page have to name the same enquiry.
 *
 * What went wrong: the id was read once, in onMounted. A hash change inside
 * the same document (a typed URL, a bookmark, back and forward) swapped the
 * id without unmounting anything, so the page went on showing the enquiry it
 * loaded first while the URL named another one. The reply box under it takes
 * the id from that same stale object, so a reply typed on the page the URL
 * called 154 was filed against 152.
 *
 * The route is a reactive object here rather than a real router so a param
 * change is exactly what it is at runtime: the same component instance, a new
 * id, no remount.
 */

const holder = vi.hoisted(() => ({
  route: undefined as undefined | { params: { id: string } },
}))

vi.mock('vue-router', async () => {
  const { reactive } = await import('vue')
  holder.route = reactive({ params: { id: '152' } })
  return {
    useRoute: () => holder.route,
    RouterLink: { template: '<a><slot /></a>' },
  }
})

vi.mock('@/utils/supportAPI', async () => {
  const actual = await vi.importActual<typeof import('@/utils/supportAPI')>('@/utils/supportAPI')
  return { ...actual, fetchTicket: vi.fn(), replyToTicket: vi.fn() }
})

import { ApiError } from '@/utils/apiError'
import { fetchTicket, replyToTicket } from '@/utils/supportAPI'
import TicketDetailPage from '../TicketDetailPage.vue'

const fetchMock = vi.mocked(fetchTicket)
const replyMock = vi.mocked(replyToTicket)

// The one the component reads. It has to be the same proxy, not a copy, or a
// change to the id would not be a change the component can see.
const reactiveRoute = holder.route!

function detail(id: number, overrides: Partial<TicketDetail> = {}): TicketDetail {
  return {
    id,
    ticketNumber: `SUP-2026-00${id}`,
    subject: `Subject of ${id}`,
    category: 'technical_issue',
    status: 'open',
    priority: 'normal',
    body: `Body of ${id}`,
    createdAt: '2026-09-01T00:00:00Z',
    lastUpdated: '2026-09-01T00:00:00Z',
    messages: [],
    ...overrides,
  }
}

async function navigateTo(id: string) {
  reactiveRoute.params.id = id
  await flushPromises()
}

let wrapper: ReturnType<typeof mount> | null = null

function open() {
  wrapper = mount(TicketDetailPage)
  return wrapper
}

describe('TicketDetailPage follows the id in the address bar', () => {
  beforeEach(() => {
    // Before the mocks, and while nothing is mounted: setting the id is itself
    // a navigation, and a page left mounted from the previous test would load
    // against it.
    reactiveRoute.params.id = '152'
    fetchMock.mockReset()
    replyMock.mockReset()
  })

  afterEach(() => {
    wrapper?.unmount()
    wrapper = null
  })

  it('loads the new enquiry when only the id in the URL changes', async () => {
    fetchMock.mockResolvedValueOnce(detail(152))
    const wrapper = open()
    await flushPromises()
    expect(wrapper.text()).toContain('SUP-2026-00152')

    fetchMock.mockResolvedValueOnce(detail(154))
    await navigateTo('154')

    expect(fetchMock).toHaveBeenCalledTimes(2)
    expect(fetchMock).toHaveBeenLastCalledWith('154')
    expect(wrapper.text()).toContain('SUP-2026-00154')
    expect(wrapper.text()).not.toContain('SUP-2026-00152')
  })

  it('sends a reply to the enquiry the URL names, not the one loaded first', async () => {
    fetchMock.mockResolvedValueOnce(detail(152))
    const wrapper = open()
    await flushPromises()

    fetchMock.mockResolvedValueOnce(detail(154))
    await navigateTo('154')

    replyMock.mockResolvedValueOnce(detail(154))
    await wrapper.get('textarea.reply__control').setValue('Any news on this?')
    await wrapper.get('form.reply').trigger('submit')
    await flushPromises()

    expect(replyMock).toHaveBeenCalledWith(154, 'Any news on this?', [])
  })

  it('goes back to the enquiry the back button returns to', async () => {
    // Back and forward are the same hash change from this component's side,
    // and they were just as stale.
    fetchMock.mockResolvedValueOnce(detail(152))
    const wrapper = open()
    await flushPromises()

    fetchMock.mockResolvedValueOnce(detail(154))
    await navigateTo('154')

    fetchMock.mockResolvedValueOnce(detail(152))
    await navigateTo('152')

    expect(fetchMock).toHaveBeenCalledTimes(3)
    expect(wrapper.text()).toContain('SUP-2026-00152')
    expect(wrapper.text()).not.toContain('SUP-2026-00154')
  })

  it('shows the enquiry the URL ends on when two loads overlap', async () => {
    // Two ids typed quickly leave two requests in flight. The first answer
    // arrives last here, which is what a slow first request looks like.
    fetchMock.mockResolvedValueOnce(detail(152))
    const wrapper = open()
    await flushPromises()

    let releaseSlow: (value: TicketDetail) => void = () => {}
    fetchMock.mockImplementationOnce(
      () => new Promise<TicketDetail>((resolve) => { releaseSlow = resolve })
    )
    reactiveRoute.params.id = '154'
    await flushPromises()

    fetchMock.mockResolvedValueOnce(detail(155))
    await navigateTo('155')

    releaseSlow(detail(154))
    await flushPromises()

    expect(wrapper.text()).toContain('SUP-2026-00155')
    expect(wrapper.text()).not.toContain('SUP-2026-00154')
  })

  it('keeps waiting when an overtaken load finishes first', async () => {
    // The overtaken request must not switch the page out of its loading state
    // either. If it does, the enquiry loaded before the navigation is back on
    // screen under the new id, which is the original defect with a shorter
    // life.
    fetchMock.mockResolvedValueOnce(detail(152))
    const wrapper = open()
    await flushPromises()

    let releaseOvertaken: (value: TicketDetail) => void = () => {}
    fetchMock.mockImplementationOnce(
      () => new Promise<TicketDetail>((resolve) => { releaseOvertaken = resolve })
    )
    reactiveRoute.params.id = '154'
    await flushPromises()

    fetchMock.mockImplementationOnce(() => new Promise<TicketDetail>(() => {}))
    reactiveRoute.params.id = '155'
    await flushPromises()

    releaseOvertaken(detail(154))
    await flushPromises()

    expect(wrapper.text()).toContain('Loading this enquiry')
    expect(wrapper.text()).not.toContain('SUP-2026-00152')
    expect(wrapper.text()).not.toContain('SUP-2026-00154')
  })

  it('reports a load failure against the id that failed', async () => {
    fetchMock.mockResolvedValueOnce(detail(152))
    const wrapper = open()
    await flushPromises()

    // The shape a 404 really arrives in: TicketDetailView answers
    // {"msg": "Ticket not found"}, and normalizeApiErrorBody reads it.
    fetchMock.mockRejectedValueOnce(
      new ApiError({ error: 'Ticket not found', code: 'not_found', request_id: 'r1' }, 404)
    )
    await navigateTo('2')

    expect(wrapper.get('[role="alert"]').text()).toBe('Ticket not found')
    expect(wrapper.text()).not.toContain('SUP-2026-00152')
  })

  it('blames the connection, not the enquiry, when the read fails with nothing to quote', async () => {
    // The fallback used to read "This enquiry could not be found.", which is
    // the one thing a failed read cannot tell you. The 404 it was written for
    // carries a sentence of its own, pinned by the case above, so the
    // fallback is free to talk about the connection instead.
    //
    // Thrown as a bare value rather than a TypeError on purpose. A dropped
    // connection rejects with a TypeError, and apiErrorFromUnknown hands that
    // error's own message out in preference to this fallback, so a student
    // reads "Failed to fetch" there instead. Closing that means changing
    // @/utils/apiError, which the whole portal imports, so it was left for
    // its own issue. See the scope note in
    // components/support/__tests__/ticketErrorMessages.spec.ts.
    fetchMock.mockRejectedValueOnce('the connection went away')
    const wrapper = open()
    await flushPromises()

    const shown = wrapper.get('[role="alert"]').text()
    expect(shown).toBe('We could not load this enquiry. Check your connection and try again.')
    expect(shown).not.toMatch(/could not be found|does not exist|no longer/i)
  })
})
