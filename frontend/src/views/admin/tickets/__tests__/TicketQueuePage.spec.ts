import { flushPromises, mount, type DOMWrapper, type VueWrapper } from '@vue/test-utils'
import { createPinia, setActivePinia } from 'pinia'
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest'
import { defineComponent, h } from 'vue'

import { pureAgent, ticketAdmin } from '@/__tests__/supportAccountFixtures'
import { ApiError } from '@/utils/apiError'
import type { QueueWalk } from '@/utils/ticketAgentAPI'
import type { TicketQueue, TicketRow } from '@/utils/ticketAgentSchema'

/**
 * The ticket queue page, ported from adminweb's TicketQueuePage.test.tsx.
 *
 * The React file replaced every React Query hook, so nothing there exercised
 * the requests themselves. Here the API module is mocked at its boundary
 * instead (utils/ticketAgentAPI: the network calls only, the helpers stay
 * real), so every assertion about paging reads what the page actually asked
 * the server for, and the reloads the hooks used to do for free (after a
 * write, on tab focus) are pinned as requests.
 *
 * The route is a reactive object rather than a real router, so `?ticket=`
 * changing is what it is at runtime: the same page instance, a new query.
 */

const holder = vi.hoisted(() => ({
  route: undefined as undefined | { path: string; query: Record<string, unknown> },
  replace: undefined as undefined | ((to: { query: Record<string, unknown> }) => Promise<void>)
}))

vi.mock('vue-router', async () => {
  const { reactive } = await import('vue')
  const route = reactive({ path: '/admin/tickets', query: {} as Record<string, unknown> })
  holder.route = route
  holder.replace = vi.fn(async (to: { query: Record<string, unknown> }) => {
    route.query = { ...to.query }
  })
  return { useRoute: () => route, useRouter: () => ({ replace: holder.replace }) }
})

vi.mock('@/utils/ticketAgentAPI', async () => {
  const actual = await vi.importActual<typeof import('@/utils/ticketAgentAPI')>(
    '@/utils/ticketAgentAPI'
  )
  return {
    ...actual,
    fetchTicketQueue: vi.fn(),
    fetchTicketSummary: vi.fn(),
    fetchAssignees: vi.fn(),
    fetchTicketRegions: vi.fn(),
    bulkAssignTickets: vi.fn(),
    exportTickets: vi.fn(),
    saveTicketExport: vi.fn()
  }
})

import {
  bulkAssignTickets,
  exportTickets,
  fetchAssignees,
  fetchTicketQueue,
  fetchTicketRegions,
  fetchTicketSummary,
  saveTicketExport
} from '@/utils/ticketAgentAPI'
import { useAuthStore } from '@/stores/auth'
import TicketQueuePage from '../TicketQueuePage.vue'

const queueMock = vi.mocked(fetchTicketQueue)
const summaryMock = vi.mocked(fetchTicketSummary)
const assigneesMock = vi.mocked(fetchAssignees)
const regionsMock = vi.mocked(fetchTicketRegions)
const bulkMock = vi.mocked(bulkAssignTickets)
const exportMock = vi.mocked(exportTickets)
const saveMock = vi.mocked(saveTicketExport)

const route = holder.route!
const replaceMock = vi.mocked(holder.replace!)

// The detail panel belongs to another owner and loads its own data. The
// queue relies on its contract and nothing else (props ticketId and
// canDelete; events close, changed, deleted), so the panel is stood in for by
// a component declaring exactly that contract, and the tests read what the
// queue hands it.
const PanelStub = defineComponent({
  name: 'TicketDetailPanel',
  props: { ticketId: { type: Number, required: true }, canDelete: { type: Boolean, required: true } },
  emits: ['close', 'changed', 'deleted'],
  setup(props) {
    return () => h('aside', { 'data-panel': String(props.ticketId) })
  }
})

const ROW: TicketRow = {
  id: 1,
  ticketNumber: 'SUP-2026-00001',
  user: { name: 'Mia', region: 'Australia', anonymous: false },
  subject: 'Poster upload fails',
  status: 'open',
  priority: 'normal',
  assignee: null,
  supportUpdatedAt: '2026-09-01T00:00:00Z',
  overdue: false
}

const WALK = { asOf: '2026-09-06T05:00:00Z', after: '2026-09-01T00:00:00Z_1' }

const SUPPORT_AGENTS = [{ id: 9, name: 'Sam Reid', assignable: true }]

let firstPageItems: TicketRow[] = [ROW]

const firstPage = (): TicketQueue => ({
  items: firstPageItems,
  total: 25,
  page: 1,
  limit: 10,
  hasMore: true,
  ...WALK
})

// Page two after somebody worked every row in front of the reader: they left
// the frozen set the walk is reading, so the page comes back with nothing on
// it while the frozen total still counts them.
const emptySecondPage = (page: number): TicketQueue => ({
  items: [],
  total: 25,
  page,
  limit: 10,
  hasMore: false,
  asOf: WALK.asOf,
  after: null
})

// Per-page answers for the tests that walk further than page two. Empty by
// default, which leaves the two fixtures above answering everything.
const responses: Record<number, TicketQueue> = {}

// What the queue was actually asked for, oldest first: one entry per request.
type Asked = { page: number; limit: number; filters: Record<string, unknown>; walk?: QueueWalk }
const asked: Asked[] = []

let wrapper: VueWrapper | null = null

function signIn(user: object) {
  setActivePinia(createPinia())
  useAuthStore().loginWithUser(user as never)
}

async function mountPage(user: object = pureAgent) {
  signIn(user)
  wrapper = mount(TicketQueuePage, {
    attachTo: document.body,
    global: { stubs: { TicketDetailPanel: PanelStub } }
  })
  await flushPromises()
  return wrapper
}

function w() {
  if (!wrapper) throw new Error('mount the page first')
  return wrapper
}

/** The one button with this accessible name (aria-label, else its text). */
function button(name: string | RegExp): DOMWrapper<HTMLButtonElement> {
  const found = w()
    .findAll<HTMLButtonElement>('button')
    .filter((b) => {
      const accessible = b.attributes('aria-label') ?? b.text().trim()
      return typeof name === 'string' ? accessible === name : name.test(accessible)
    })
  if (found.length !== 1) throw new Error(`${found.length} buttons named ${String(name)}`)
  return found[0]!
}

function hasButton(name: string) {
  return w()
    .findAll('button')
    .some((b) => (b.attributes('aria-label') ?? b.text().trim()) === name)
}

async function click(name: string | RegExp) {
  await button(name).trigger('click')
  await flushPromises()
}

async function selectRow(ticketNumber = 'SUP-2026-00001') {
  await w().get(`input[aria-label="Select ${ticketNumber}"]`).setValue(true)
}

async function assignTo(value: string) {
  await w().get('select[aria-label="Assign to"]').setValue(value)
  await click(value === '__unassigned__' ? 'Unassign' : 'Assign')
}

function alerts() {
  return w()
    .findAll('[role="alert"]')
    .map((a) => a.text().replace(/\s+/g, ' '))
}

function lastAsk() {
  return asked[asked.length - 1]
}

function text() {
  return w().text().replace(/\s+/g, ' ')
}

let visibility: DocumentVisibilityState = 'visible'

async function tabBecomes(state: DocumentVisibilityState) {
  visibility = state
  document.dispatchEvent(new Event('visibilitychange'))
  await flushPromises()
}

beforeEach(() => {
  vi.clearAllMocks()
  vi.spyOn(console, 'warn').mockImplementation(() => {})
  Object.defineProperty(document, 'visibilityState', {
    configurable: true,
    get: () => visibility
  })
  queueMock.mockImplementation(async (page, limit, filters = {}, walk) => {
    asked.push({ page, limit, filters: { ...filters }, walk })
    return structuredClone(responses[page] ?? (page === 1 ? firstPage() : emptySecondPage(page)))
  })
  summaryMock.mockResolvedValue({ unassigned: 1, open: 1, pendingUser: 0, overdue: 0 })
  assigneesMock.mockResolvedValue(structuredClone(SUPPORT_AGENTS))
  regionsMock.mockResolvedValue([])
  bulkMock.mockResolvedValue({ results: [{ ticketId: 1, ok: true }] })
})

afterEach(() => {
  wrapper?.unmount()
  wrapper = null
  route.query = {}
  visibility = 'visible'
  asked.length = 0
  firstPageItems = [ROW]
  for (const key of Object.keys(responses)) delete responses[Number(key)]
  vi.restoreAllMocks()
})

const FAILURE = /Could not assign the selected tickets/

/** A refusal with no sentence meant for a person in it. */
function fault(status: number) {
  return new ApiError({ error: 'Request failed.', code: `http_${status}`, request_id: 'r-1' }, status)
}

describe('the bulk assign failure message', () => {
  beforeEach(() => {
    bulkMock.mockRejectedValue(fault(400))
  })

  it('appears while the batch it describes is still selected', async () => {
    await mountPage()
    await selectRow()
    await assignTo('9')

    expect(alerts().some((a) => FAILURE.test(a))).toBe(true)
  })

  it('goes away with the selection rather than outliving it', async () => {
    // It used to render outside the selection block, so an agent who cleared
    // the selection was left reading a warning about a batch that was no
    // longer there.
    await mountPage()
    await selectRow()
    await assignTo('9')

    await click('Clear selection')

    expect(text()).not.toMatch(FAILURE)
  })

  it('does not come back with the next selection once the agent has cleared it', async () => {
    // React pinned this by asserting the mutation's reset() was called. There
    // is no mutation object here, so the behaviour it protected is asserted
    // instead: hiding it is not enough on its own, or the same message comes
    // straight back the moment a different batch is picked, reading as
    // though the new selection had failed too, before anything was sent.
    await mountPage()
    await selectRow()
    await assignTo('9')
    await click('Clear selection')

    await selectRow()

    expect(text()).not.toMatch(FAILURE)
  })

  it('does not come back after a filter change emptied the selection either', async () => {
    // React reset the failure on Clear only, so a card or filter that
    // cleared the selection left it waiting for the next batch.
    await mountPage()
    await selectRow()
    await assignTo('9')
    expect(text()).toMatch(FAILURE)

    await click('Open')
    await selectRow()

    expect(text()).not.toMatch(FAILURE)
  })
})

describe('the counter cards', () => {
  it('explains Overdue by the rule the counter actually uses', async () => {
    // The client replaced the first-response test on 2026-09-04: the clock
    // restarts every time the requester writes back, so a ticket support has
    // already answered can be overdue. The card used to say the opposite of
    // the number printed above it.
    await mountPage()

    expect(text()).toContain('Waiting on support for longer than its priority allows')
    expect(text()).not.toMatch(/first reply/i)
  })

  it('gives the other three cards the hints they had', async () => {
    await mountPage()

    expect(w().findAll('.queue-card__hint').map((p) => p.text())).toEqual([
      'Still needs somebody to pick it up',
      'Nobody has picked it up yet',
      'Waiting on the requester',
      'Waiting on support for longer than its priority allows'
    ])
  })

  it('takes the agent to the tickets the Open card counts', async () => {
    await mountPage()

    await click('Open')

    expect(lastAsk()).toMatchObject({ page: 1, filters: { status: 'open' } })
  })

  it('takes the agent to the tickets the Pending user card counts', async () => {
    await mountPage()

    await click('Pending user')

    expect(lastAsk()).toMatchObject({ page: 1, filters: { status: 'pending_user' } })
  })

  it('takes the agent to the tickets the Unassigned card counts', async () => {
    await mountPage()

    await click('Unassigned')

    expect(lastAsk()).toMatchObject({ page: 1, filters: { assignee: '__unassigned__' } })
  })

  it('leaves Overdue as a number, because no filter reproduces it', async () => {
    // The queue endpoint has no overdue parameter: it is worked out per row
    // as the page is served. A card that navigated to a filter the server
    // ignores would list the whole queue and claim it was the overdue part.
    await mountPage()

    expect(hasButton('Overdue')).toBe(false)
  })

  it('keeps the filters already on screen when a card is clicked', async () => {
    // applyFilters replaces the whole filter state, so passing the card's
    // filter on its own would silently clear the region the agent had
    // already narrowed to.
    regionsMock.mockResolvedValue([{ value: 'Australia', label: 'Australia' }])
    await mountPage()
    await w().get('select[aria-label="Filter by region"]').setValue('Australia')
    await flushPromises()

    await click('Open')

    expect(lastAsk().filters).toEqual({ region: 'Australia', status: 'open' })
  })

  it('asks for the list once per click on a card, not twice', async () => {
    // React wired the handler to the card and to the button inside it, so
    // one click on the label ran it twice.
    await mountPage()
    const before = asked.length

    await click('Open')

    expect(asked.length - before).toBe(1)
  })

  it('shows no number while the counts are loading or after they failed', async () => {
    // A failed request is not the same as a count of zero, and "Overdue 0"
    // is the one thing on this page an agent might act on by walking away.
    summaryMock.mockRejectedValue(fault(500))
    await mountPage()

    const values = w().findAll('.queue-card__value')
    // Drawn as a dash, read out as words.
    expect(values.map((p) => p.get('[aria-hidden="true"]').text())).toEqual(Array(4).fill('—'))
    expect(values.map((p) => p.get('.sr-only').text())).toEqual(Array(4).fill('not available'))
    expect(values.map((p) => p.text()).join(' ')).not.toMatch(/\d/)
  })

  it('shows no number while the counts are still on their way', async () => {
    summaryMock.mockImplementation(() => new Promise(() => {}))
    await mountPage()

    expect(w().findAll('.queue-card__value').map((p) => p.text())).toEqual(
      Array(4).fill('—not available')
    )
  })

  it('takes the numbers away again when a refresh of them fails', async () => {
    // React showed dashes whenever the query was in error, stale data or
    // not: a count that could not be confirmed is not shown as if it were.
    await mountPage()
    summaryMock.mockRejectedValue(fault(500))

    await tabBecomes('hidden')
    await tabBecomes('visible')

    expect(w().findAll('.queue-card__value').map((p) => p.text())).toEqual(
      Array(4).fill('—not available')
    )
  })

  it('says out loud that the counts could not be loaded', async () => {
    // A dash is also what a card shows while its first answer is on the way,
    // and nothing here retries on its own, so a failure sat there looking
    // like a slow request (U2 GAP-16: React had the dashes only).
    summaryMock.mockRejectedValue(fault(500))

    await mountPage()

    expect(alerts()).toEqual(['The counts above could not be loaded. Reload to try again.'])
  })

  it('says nothing about the counts while they are still on their way', async () => {
    summaryMock.mockImplementation(() => new Promise(() => {}))

    await mountPage()

    expect(alerts()).toEqual([])
  })

  it('takes that sentence down once a refresh brings the counts back', async () => {
    summaryMock.mockRejectedValueOnce(fault(500))
    await mountPage()
    expect(alerts()).toEqual(['The counts above could not be loaded. Reload to try again.'])

    await tabBecomes('hidden')
    await tabBecomes('visible')

    expect(alerts()).toEqual([])
    expect(w().findAll('.queue-card__value').map((p) => p.text())).toEqual(['1', '1', '0', '0'])
  })

  // Two counter refreshes overlap easily: the tab comes back, and a moment
  // later a write in the panel asks again. Whichever answer arrives last
  // must not be the one that decides, unless it is also the newest.
  const twoOverlappingCountRefreshes = async (older: 'answers' | 'fails') => {
    let finishOlder: (value: { unassigned: number; open: number; pendingUser: number; overdue: number }) => void =
      () => {}
    let failOlder: (reason: unknown) => void = () => {}
    summaryMock.mockImplementationOnce(
      () =>
        new Promise((resolve, reject) => {
          finishOlder = resolve
          failOlder = reject
        })
    )
    summaryMock.mockImplementationOnce(async () => ({ unassigned: 7, open: 6, pendingUser: 5, overdue: 4 }))
    const before = summaryMock.mock.calls.length

    await tabBecomes('hidden')
    await tabBecomes('visible')
    await tabBecomes('hidden')
    await tabBecomes('visible')
    // Both refreshes really went out, the newer one has answered.
    expect(summaryMock.mock.calls.length - before).toBe(2)

    if (older === 'answers') finishOlder({ unassigned: 1, open: 1, pendingUser: 1, overdue: 1 })
    else failOlder(fault(500))
    await flushPromises()
  }

  it('does not paint an older count over a newer one', async () => {
    await mountPage()

    await twoOverlappingCountRefreshes('answers')

    expect(w().findAll('.queue-card__value').map((p) => p.text())).toEqual(['7', '6', '5', '4'])
  })

  it('does not let an older failed count take the newer numbers away', async () => {
    await mountPage()

    await twoOverlappingCountRefreshes('fails')

    expect(w().findAll('.queue-card__value').map((p) => p.text())).toEqual(['7', '6', '5', '4'])
    expect(alerts()).toEqual([])
  })

  it('marks the Overdue number once anything is overdue', async () => {
    summaryMock.mockResolvedValue({ unassigned: 1, open: 1, pendingUser: 0, overdue: 3 })
    await mountPage()

    const overdue = w().findAll('.queue-card__value')[3]!
    expect(overdue.text()).toBe('3')
    expect(overdue.classes()).toContain('queue-card__value--alert')
  })

  it('leaves the Overdue number plain at zero', async () => {
    await mountPage()

    const overdue = w().findAll('.queue-card__value')[3]!
    expect(overdue.text()).toBe('0')
    expect(overdue.classes()).not.toContain('queue-card__value--alert')
  })
})

describe('an empty page', () => {
  it('does not claim nothing matches when the rows ahead were worked', async () => {
    // The walk is frozen at the moment it began, and a ticket somebody works
    // leaves that frozen set. The rows this page was going to show still
    // match the filters perfectly well; they are just at the front now.
    await mountPage()

    await click('Next')

    expect(text()).toContain(
      'Nothing left on this page. The tickets that were here have been worked on since you opened the queue, which moves them to the front of it. Go back to page 1 to see them.'
    )
    expect(text()).not.toMatch(/no tickets match these filters/i)
  })

  it('still says nothing matches when the first page comes back empty', async () => {
    firstPageItems = []

    await mountPage()

    expect(text()).toContain('No tickets match these filters.')
  })

  it('says nothing matches when a page reached by its number is empty', async () => {
    // Clicking a page number is not continuing the walk. The cursors are
    // dropped and the page is read from a fresh snapshot, so an empty one
    // there is no evidence that the rows ahead were worked, and telling the
    // agent to go back to page 1 to find them is a guess.
    await mountPage()

    await click('Go to page 3')

    expect(text()).toContain('No tickets match these filters.')
    expect(text()).not.toMatch(/go back to page 1/i)
  })
})

describe('when the queue cannot be read', () => {
  it('says the queue could not be loaded, never that nothing matches', async () => {
    // "No tickets match these filters" is a claim about the queue, and a
    // request that failed licenses no claim about it.
    queueMock.mockRejectedValue(fault(500))

    await mountPage()

    expect(alerts()).toEqual([
      'The queue could not be loaded, so this page is not showing the real state of it. Reload to try again.',
      'The queue could not be loaded.'
    ])
    expect(text()).not.toMatch(/no tickets match/i)
  })

  it('keeps the rows on screen when a background refresh fails', async () => {
    // One failed refresh must not replace a screen of real tickets with a
    // single line of red text; the page banner says the rows may be stale.
    await mountPage()
    queueMock.mockRejectedValue(fault(500))

    await tabBecomes('hidden')
    await tabBecomes('visible')

    expect(w().find('button[aria-label="Open SUP-2026-00001"]').exists()).toBe(true)
    expect(alerts()).toEqual([
      'The queue could not be loaded, so this page is not showing the real state of it. Reload to try again.'
    ])
  })

  it('takes the banner down again once a refresh succeeds', async () => {
    // The banner says the page is not showing the real state of the queue.
    // Once a refresh has brought the real state back, that is no longer true.
    await mountPage()
    queueMock.mockRejectedValueOnce(fault(500))
    await tabBecomes('hidden')
    await tabBecomes('visible')
    expect(alerts()).toHaveLength(1)

    await tabBecomes('hidden')
    await tabBecomes('visible')

    expect(alerts()).toEqual([])
  })

  const noQueueAccess = () =>
    new ApiError(
      { error: 'You do not have support privileges.', code: 'permission_denied', request_id: 'r-1' },
      403
    )

  const REFUSED =
    'You do not have access to the ticket queue. It is open to the support team and to administrators.'

  it('says the agent has no access, rather than that the queue is broken, on a refusal', async () => {
    // U2 GAP-04. The guard keeps anyone without queue access off this page,
    // so a 403 here means the access went while the page was open. "Could
    // not be loaded, reload" reads as a fault in the product when it is
    // working as intended. Same sentence as the audit and analytics tabs.
    queueMock.mockRejectedValue(noQueueAccess())

    await mountPage()

    expect(alerts()).toEqual([REFUSED, 'The queue could not be loaded.'])
  })

  it('says it once for the page when the counts are refused too', async () => {
    queueMock.mockRejectedValue(noQueueAccess())
    summaryMock.mockRejectedValue(noQueueAccess())

    await mountPage()

    expect(alerts()).toEqual([REFUSED, 'The queue could not be loaded.'])
  })

  it('stops speaking for the counts once the refusal is over', async () => {
    // The refusal sentence stands in for the counts' own while it is up.
    // Once the queue reads again (access given back), a count that fails
    // afterwards is a fault of its own and has to say so.
    queueMock.mockRejectedValueOnce(noQueueAccess())
    await mountPage()
    expect(alerts()).toEqual([REFUSED, 'The queue could not be loaded.'])
    summaryMock.mockRejectedValue(fault(500))

    await tabBecomes('hidden')
    await tabBecomes('visible')

    expect(alerts()).toEqual(['The counts above could not be loaded. Reload to try again.'])
  })

  it('keeps the rows on screen when a refresh is refused', async () => {
    await mountPage()
    queueMock.mockRejectedValue(noQueueAccess())

    await tabBecomes('hidden')
    await tabBecomes('visible')

    expect(w().find('button[aria-label="Open SUP-2026-00001"]').exists()).toBe(true)
    expect(alerts()).toEqual([REFUSED])
  })

  it('says it is loading, not that the queue is empty, while the first page is on its way', async () => {
    queueMock.mockImplementation(() => new Promise(() => {}))

    await mountPage()

    expect(w().get('[role="status"]').text()).toBe('Loading the queue…')
    expect(text()).not.toMatch(/no tickets match/i)
    expect(button('Next').element.disabled).toBe(true)
  })
})

describe('an answer that arrives late', () => {
  it('does not paint an older request over a newer one', async () => {
    // Two filter changes in a row leave two requests in flight. The slower
    // one must not decide what is on screen, or the rows would not be the
    // ones the filters above them say.
    await mountPage()
    let finishOld: (value: TicketQueue) => void = () => {}
    queueMock.mockImplementationOnce(
      () => new Promise<TicketQueue>((resolve) => (finishOld = resolve))
    )
    queueMock.mockImplementationOnce(async () => ({
      ...firstPage(),
      items: [{ ...ROW, id: 7, ticketNumber: 'SUP-2026-00007' }]
    }))

    await click('Open')
    await click('Pending user')
    finishOld({ ...firstPage(), items: [{ ...ROW, id: 5, ticketNumber: 'SUP-2026-00005' }] })
    await flushPromises()

    expect(w().find('button[aria-label="Open SUP-2026-00007"]').exists()).toBe(true)
    expect(w().find('button[aria-label="Open SUP-2026-00005"]').exists()).toBe(false)
  })

  it('does not let an older request that failed mark the newer page as broken', async () => {
    // The same token on the failure path: the rows on screen are the newer
    // request's, and nothing is wrong with them.
    await mountPage()
    let failOld: (reason: unknown) => void = () => {}
    queueMock.mockImplementationOnce(() => new Promise<TicketQueue>((_, reject) => (failOld = reject)))
    queueMock.mockImplementationOnce(async () => ({
      ...firstPage(),
      items: [{ ...ROW, id: 7, ticketNumber: 'SUP-2026-00007' }]
    }))

    await click('Open')
    await click('Pending user')
    failOld(fault(500))
    await flushPromises()

    expect(w().find('button[aria-label="Open SUP-2026-00007"]').exists()).toBe(true)
    expect(alerts()).toEqual([])
  })

  it('keeps saying it is loading while the newer request is still out', async () => {
    // The older answer arriving first must not end the newer request's
    // loading state: with nothing on screen yet, that would print "No
    // tickets match these filters" about a page nobody has read.
    await mountPage()
    let finishOld: (value: TicketQueue) => void = () => {}
    queueMock.mockImplementationOnce(
      () => new Promise<TicketQueue>((resolve) => (finishOld = resolve))
    )
    queueMock.mockImplementationOnce(() => new Promise<TicketQueue>(() => {}))

    await click('Open')
    await click('Pending user')
    finishOld(firstPage())
    await flushPromises()

    expect(w().get('[role="status"]').text()).toBe('Loading the queue…')
    expect(text()).not.toMatch(/no tickets match/i)
  })
})

describe('paging backwards', () => {
  // Four pages of one row each, each handing out the cursor for the one after
  // it, all under one snapshot. Fixed strings rather than anything read off a
  // clock: what is asserted is which cursor was sent, not when. `total` is
  // four pages' worth so the footer offers all four numbers from the start.
  const fourPageWalk = () => {
    const last = 4
    for (let n = 1; n <= last; n++) {
      responses[n] = {
        items: [{ ...ROW, id: n, ticketNumber: `SUP-2026-0000${n}` }],
        total: last * 10,
        page: n,
        limit: 10,
        hasMore: n < last,
        asOf: WALK.asOf,
        after: n < last ? `cursor-after-page-${n}` : null
      }
    }
  }

  const afterPage = (n: number) => ({ asOf: WALK.asOf, after: `cursor-after-page-${n}` })

  const trace = () => asked.map(({ page, walk }) => ({ page, walk }))

  it('reads backwards from a fresh snapshot, not from a held cursor', async () => {
    // Only Next continues the walk. Previous is a jump, and a jump drops the
    // cursors and reads by offset out of a new snapshot.
    //
    // Reaching page N-1 with the cursor page N-2 handed out was tried and
    // reverted, so this pins the route rather than leaving it to whichever
    // reading of the backend's paging.py docstring the next person arrives
    // with. It does not remove the repeats, it moves them: measured against
    // the queue endpoint, 220 tickets ten to a page with three worked behind
    // the reader, the cursor route repeated six rows across pages where the
    // offset route repeated three.
    //
    // Neither route loses a row. That is the property the snapshot is for,
    // and it is the one to protect if this is ever revisited.
    fourPageWalk()
    await mountPage()

    await click('Next')
    await click('Next')
    await click('Previous')
    await click('Next')

    // One request per page landed on: there is no query cache here, so the
    // React test's de-duplication of repeated renders is not needed.
    expect(trace()).toEqual([
      { page: 1, walk: undefined },
      { page: 2, walk: afterPage(1) },
      { page: 3, walk: afterPage(2) },
      { page: 2, walk: undefined },
      { page: 3, walk: afterPage(2) }
    ])
  })

  it('reads page one live, because no cursor points at it', async () => {
    // There is no cursor for the first page and there never will be. Sending
    // a stale one would serve page two under page one's number.
    fourPageWalk()
    await mountPage()

    await click('Next')
    await click('Previous')

    expect(lastAsk()).toMatchObject({ page: 1, walk: undefined })
  })

  it('does not carry the old cursors past a fresh read of page one', async () => {
    // Page one is answered live, so the walk that reached page two is over
    // and its cursors describe a snapshot nothing on screen is reading any
    // more. They are normally overwritten by page one's own response, but a
    // page that hands out no cursor cannot overwrite anything: here every row
    // on page one was worked while the reader was on page two, so the reply
    // comes back empty and there is nothing to replace them with.
    fourPageWalk()
    await mountPage()

    await click('Next')
    responses[1] = { ...responses[1]!, items: [], hasMore: false, after: null }
    await click('Previous')
    // One step forward, which is the move that would continue a walk if a
    // cursor for page two were still held.
    await click('Next')

    expect(lastAsk()).toMatchObject({ page: 2, walk: undefined })
  })

  it('still reads a page chosen by its number from a fresh snapshot', async () => {
    // Skipping pages is the reader saying they do not want the walk, and two
    // pages back is a jump the same way two pages forward is. The cursor for
    // page 2 is sitting in the map here, left by the walk out to page 4, so
    // "whichever pages we happen to hold a cursor for" would answer this one
    // out of a snapshot several minutes old.
    fourPageWalk()
    await mountPage()

    await click('Next')
    await click('Next')
    await click('Next')
    await click('Go to page 2')

    expect(lastAsk()).toMatchObject({ page: 2, walk: undefined })
  })

  // After a filter or size change the old walk's cursors are only visible
  // where the new walk fails to overwrite them: a page that comes back empty
  // (every row on it worked) hands out no cursor, so the step after it would
  // continue the old walk. The frozen total still counts four pages, so Next
  // stays open on that empty page.
  const newWalkEmptiesPageTwo = () => {
    responses[1] = { ...responses[1]!, after: 'new-walk-after-page-1' }
    responses[2] = {
      items: [],
      total: 40,
      page: 2,
      limit: 10,
      hasMore: false,
      asOf: WALK.asOf,
      after: null
    }
  }

  it('starts a fresh walk when the filters change', async () => {
    // Page 3 of the old filter is rarely page 3 of the new one, and the old
    // cursors describe a different set.
    fourPageWalk()
    await mountPage()
    await click('Next')
    await click('Next')
    newWalkEmptiesPageTwo()

    await click('Open')
    await click('Next')
    await click('Next')

    expect(trace().slice(-3)).toEqual([
      { page: 1, walk: undefined },
      { page: 2, walk: { asOf: WALK.asOf, after: 'new-walk-after-page-1' } },
      { page: 3, walk: undefined }
    ])
    expect(lastAsk().filters).toEqual({ status: 'open' })
  })

  it('starts a fresh walk when the page size changes', async () => {
    fourPageWalk()
    await mountPage()
    await click('Next')
    await click('Next')
    newWalkEmptiesPageTwo()

    const box = w().get('input[aria-label="Rows per page"]')
    await box.setValue('25')
    await box.trigger('keydown', { key: 'Enter' })
    await flushPromises()
    await click('Next')
    await click('Next')

    expect(asked.slice(-3).map(({ page, limit, walk }) => ({ page, limit, walk }))).toEqual([
      { page: 1, limit: 25, walk: undefined },
      { page: 2, limit: 25, walk: { asOf: WALK.asOf, after: 'new-walk-after-page-1' } },
      { page: 3, limit: 25, walk: undefined }
    ])
  })
})

describe('the address bar', () => {
  it('holds the open ticket and nothing else: no filters, page or size', async () => {
    // As the React queue: reloading returns to page one, ten rows, no
    // filters. A cursor in a URL goes stale, and adding URL state is a new
    // feature, not part of the port.
    await mountPage()

    await click('Open')
    await click('Next')
    const box = w().get('input[aria-label="Rows per page"]')
    await box.setValue('25')
    await box.trigger('keydown', { key: 'Enter' })
    await flushPromises()

    expect(replaceMock).not.toHaveBeenCalled()
    expect(route.query).toEqual({})
  })
})

describe('the last activity column', () => {
  it('names the time zone it is printing', async () => {
    // Rendered in the reader's own zone, so the same row is 03:37 pm in
    // Sydney and 02:37 am in Sao Paulo. Agents read these times to each other
    // and compare them against the overdue windows.
    await mountPage()

    const cells = w().findAll('td')
    const lastActivity = cells[cells.length - 1]!.text()

    // Built from the clock this machine is on rather than matched against a
    // list of zone spellings. The short name is "UTC" here, "AEST" in Sydney,
    // "GMT-3" in Sao Paulo and "GMT+5:30" in Kolkata, and a hand-written list
    // of those turns the suite red on whichever machine it happens to miss.
    const stamp = { day: 'numeric', month: 'short', hour: '2-digit', minute: '2-digit' } as const
    const withoutZone = new Date(ROW.supportUpdatedAt).toLocaleString('en-AU', stamp)
    const withZone = new Date(ROW.supportUpdatedAt).toLocaleString('en-AU', {
      ...stamp,
      timeZoneName: 'short'
    })

    expect(lastActivity).toBe(withZone)
    // The zone name is an addition, not a replacement: the timestamp is still
    // in front of it, and there is something after it.
    expect(withZone.startsWith(withoutZone)).toBe(true)
    expect(lastActivity).not.toBe(withoutZone)
  })
})

describe('the filter option lists', () => {
  it('says so when the assignee list could not be loaded', async () => {
    // An empty dropdown is indistinguishable from a platform with nobody on
    // it, and the same list feeds the assign controls further down.
    assigneesMock.mockRejectedValue(fault(500))

    await mountPage()

    expect(alerts()).toEqual([
      'The assignee list could not be loaded. The filters above are missing those choices, and so are the assign controls on this page. Reload to try again.'
    ])
  })

  it('says so when the region list could not be loaded', async () => {
    // The other half of the same hole. Regions fail on their own endpoint.
    regionsMock.mockRejectedValue(fault(500))

    await mountPage()

    expect(alerts()).toEqual([
      'The region list could not be loaded. The filters above are missing those choices. Reload to try again.'
    ])
    // The assignee list is fine, so its dropdowns are full. Naming them here
    // would send the agent looking for a fault that is not there.
    expect(text()).not.toMatch(/assign controls/i)
  })

  it('names both lists when both endpoints are down', async () => {
    assigneesMock.mockRejectedValue(fault(500))
    regionsMock.mockRejectedValue(fault(500))

    await mountPage()

    expect(alerts()).toEqual([
      'The assignee and region lists could not be loaded. The filters above are missing those choices, and so are the assign controls on this page. Reload to try again.'
    ])
  })

  it('says nothing while both lists are fine', async () => {
    await mountPage()

    expect(text()).not.toMatch(/could not be loaded/i)
  })

  it('reads the two lists once per visit, not on every refresh', async () => {
    // Only the queue and the counters refresh on their own. The detail panel
    // fetches its own roster whenever it opens.
    await mountPage()

    await tabBecomes('hidden')
    await tabBecomes('visible')

    expect(assigneesMock).toHaveBeenCalledTimes(1)
    expect(regionsMock).toHaveBeenCalledTimes(1)
  })
})

describe('handing a batch back to the pool', () => {
  it('sends a null assignee, which is what the endpoint reads as the pool', async () => {
    // The whole point of the option: the serializer has taken null since it
    // was written and three backend tests pin it, but the only control that
    // could ask for it was the one-ticket panel.
    await mountPage()
    await selectRow()

    await assignTo('__unassigned__')

    expect(bulkMock.mock.calls).toEqual([[[1], null]])
  })

  it('does not blame the person nobody picked when it fails', async () => {
    // The assign wording sends the agent checking whether somebody still has
    // the support role, and on a hand-back there is no somebody.
    bulkMock.mockRejectedValue(fault(400))
    await mountPage()
    await selectRow()

    await assignTo('__unassigned__')

    expect(alerts()).toEqual([
      'Could not hand the selected tickets back to the pool. Nothing was changed. Try again.'
    ])
  })

  it('keeps the assign wording when a person was picked', async () => {
    // React's sentence carried a dash between its two halves; the port's UI
    // copy takes none, so it is two sentences with the same words.
    bulkMock.mockRejectedValue(fault(400))
    await mountPage()
    await selectRow()

    await assignTo('9')

    expect(alerts()).toEqual([
      'Could not assign the selected tickets. Nothing was changed. Check that the person you picked can still work the queue, then try again.'
    ])
  })

  it('says the assignee list is down inside the dropdown as well', async () => {
    // The banner above says it once for the page. The dropdown needs it too:
    // the pool line is always offered, so a dead endpoint leaves it opening
    // on one plausible option instead of on nothing at all.
    assigneesMock.mockRejectedValue(fault(500))
    await mountPage()
    await selectRow()

    const options = w().get('select[aria-label="Assign to"]').findAll('option')
    const last = options[options.length - 1]!
    expect(last.text().replace(/\s+/g, ' ')).toBe(
      'The assignee list could not be loaded, so there is nobody to pick here. Reload to try again.'
    )
    expect(last.attributes('disabled')).toBeDefined()
  })

  it('passes on the transport’s own refusal instead of advising a retry', async () => {
    // A session that changed hands is refused again on every press, so
    // "try again" is the one answer that cannot be right. "Nothing was
    // changed" stays: it is the first thing somebody told their session
    // changed hands wants to know.
    const { TicketSessionError } = await import('@/utils/ticketTransport')
    bulkMock.mockRejectedValue(
      new TicketSessionError('signed-in-as-someone-else', 'the transport wording, which agent pages do not show')
    )
    await mountPage()
    await selectRow()

    await assignTo('9')

    expect(alerts()).toEqual([
      'Could not assign the selected tickets. Nothing was changed. You appear to be signed in as someone else now. This can happen if you signed in to another BIOTech page in the same browser. Please reload and sign in again.'
    ])
  })
})

describe('a bulk assign the server refused in words', () => {
  // U2 GAP-06: React showed its standing sentence for every refusal, and the
  // server's own reason never reached the agent.
  const noSupportAccess = () =>
    new ApiError(
      { error: 'You do not have support privileges.', code: 'permission_denied', request_id: 'r-1' },
      403
    )

  it('says the agent’s own access was withdrawn, not the person they picked', async () => {
    // "Check that the person you picked can still work the queue" sends the
    // agent to check somebody else when it is their own access that went.
    bulkMock.mockRejectedValue(noSupportAccess())
    await mountPage()
    await selectRow()

    await assignTo('9')

    expect(alerts()).toEqual([
      'Could not assign the selected tickets. Nothing was changed. You do not have support privileges.'
    ])
  })

  it('says the same for a batch handed back to the pool', async () => {
    bulkMock.mockRejectedValue(noSupportAccess())
    await mountPage()
    await selectRow()

    await assignTo('__unassigned__')

    expect(alerts()).toEqual([
      'Could not hand the selected tickets back to the pool. Nothing was changed. You do not have support privileges.'
    ])
  })

  it('keeps the standing advice for a refused assignee, which the server names by id', async () => {
    // The server's sentence for this one is 'Cannot assign to user "9"',
    // and an agent has never seen that number anywhere. The standing
    // sentence says the same thing by the person they picked.
    bulkMock.mockRejectedValue(
      new ApiError(
        {
          error: 'Cannot assign to user "9". They need an active account with support queue access.',
          code: 'does_not_exist',
          request_id: 'r-1'
        },
        400
      )
    )
    await mountPage()
    await selectRow()

    await assignTo('9')

    expect(alerts()).toEqual([
      'Could not assign the selected tickets. Nothing was changed. Check that the person you picked can still work the queue, then try again.'
    ])
  })
})

describe('a bulk assign that goes through', () => {
  it('sends the whole selection in one request, as numbers', async () => {
    firstPageItems = [ROW, { ...ROW, id: 2, ticketNumber: 'SUP-2026-00002' }]
    await mountPage()
    await selectRow('SUP-2026-00001')
    await selectRow('SUP-2026-00002')

    await assignTo('9')

    expect(bulkMock.mock.calls).toEqual([[[1, 2], 9]])
  })

  it('clears the selection and reloads the rows and the counters', async () => {
    await mountPage()
    await selectRow()
    const queueBefore = queueMock.mock.calls.length
    const summaryBefore = summaryMock.mock.calls.length

    await assignTo('9')

    expect(w().find('[aria-label="Bulk actions"]').exists()).toBe(false)
    expect(queueMock.mock.calls.length - queueBefore).toBe(1)
    expect(summaryMock.mock.calls.length - summaryBefore).toBe(1)
  })

  it('sends one batch however fast the button is pressed', async () => {
    // Guarded on live state, not on the rendered disabled attribute, which
    // only catches up on the next render.
    let finish: (value: { results: { ticketId: number; ok: boolean }[] }) => void = () => {}
    bulkMock.mockImplementation(() => new Promise((resolve) => (finish = resolve)))
    await mountPage()
    await selectRow()
    await w().get('select[aria-label="Assign to"]').setValue('9')

    const go = button('Assign')
    go.element.click()
    go.element.click()
    finish({ results: [{ ticketId: 1, ok: true }] })
    await flushPromises()

    expect(bulkMock).toHaveBeenCalledTimes(1)
  })

  it('says it is working and will not clear the batch mid-request', async () => {
    bulkMock.mockImplementation(() => new Promise(() => {}))
    await mountPage()
    await selectRow()

    await assignTo('9')

    expect(button('Assigning…').element.disabled).toBe(true)
    expect(button('Clear selection').element.disabled).toBe(true)
  })
})

describe('a bulk assign that partly failed', () => {
  it('names the tickets it could not assign, by number and reason', async () => {
    // The response identifies them by internal id, which appears nowhere an
    // agent can see. A bare "1 of 2 could not be assigned" leaves them
    // re-selecting the whole batch to work out which one.
    bulkMock.mockResolvedValue({
      results: [
        { ticketId: 1, ok: false, error: 'not found' },
        { ticketId: 2, ok: true }
      ]
    })
    await mountPage()
    await selectRow()

    await assignTo('9')

    expect(alerts()).toEqual([
      '1 of 2 could not be assigned: SUP-2026-00001 (not found). Tickets deleted while they sat in the selection come back as not found, and sending the batch again will not change that.'
    ])
  })

  it('does not call a second try pointless when a retry could work', async () => {
    // bulk_assign fails two ways. A row that is gone comes back as "not
    // found" and no amount of retrying brings it back; anything the write
    // itself throws comes back as the exception text, and that one can come
    // good on a second try. One of each here, so the sentence about deleted
    // tickets is true of half the batch and must not be printed.
    firstPageItems = [ROW, { ...ROW, id: 2, ticketNumber: 'SUP-2026-00002' }]
    bulkMock.mockResolvedValue({
      results: [
        { ticketId: 1, ok: false, error: 'not found' },
        { ticketId: 2, ok: false, error: 'deadlock detected' }
      ]
    })
    await mountPage()
    await w().get('input[aria-label="Select every ticket on this page"]').setValue(true)

    await assignTo('9')

    expect(alerts()).toEqual([
      '2 of 2 could not be assigned: SUP-2026-00001 (not found); SUP-2026-00002 (deadlock detected).'
    ])
  })

  it('gives a reason even when the server sent an empty one', async () => {
    // The reason is an optional string on the wire, and an exception with no
    // message serialises to "" rather than to nothing.
    bulkMock.mockResolvedValue({ results: [{ ticketId: 1, ok: false, error: '' }] })
    await mountPage()
    await selectRow()

    await assignTo('9')

    expect(alerts()).toEqual(['1 of 1 could not be assigned: SUP-2026-00001 (no reason given).'])
  })

  it('names a ticket that has since left the page by the number it had', async () => {
    // The failed rows are exactly the ones that leave the queue after the
    // batch, so by the time the message is read there is no row to take a
    // number from. The page remembers every number it has shown.
    bulkMock.mockResolvedValue({ results: [{ ticketId: 1, ok: false, error: 'not found' }] })
    await mountPage()
    await selectRow()
    firstPageItems = []

    await assignTo('9')

    expect(w().find('button[aria-label="Open SUP-2026-00001"]').exists()).toBe(false)
    expect(alerts()[0]).toMatch(/^1 of 1 could not be assigned: SUP-2026-00001 \(not found\)\./)
  })

  it('stays until the agent clears the next selection', async () => {
    // A partial failure clears the selection, so the message outlives the
    // bar on purpose. React's Clear reset the whole mutation, this message
    // included; the next Clear is where it goes.
    bulkMock.mockResolvedValue({ results: [{ ticketId: 1, ok: false, error: 'not found' }] })
    await mountPage()
    await selectRow()
    await assignTo('9')
    expect(text()).toMatch(/could not be assigned/)

    await selectRow()
    expect(text()).toMatch(/could not be assigned/)
    await click('Clear selection')

    expect(text()).not.toMatch(/could not be assigned/)
  })

  it('says nothing when every ticket in the batch was assigned', async () => {
    await mountPage()
    await selectRow()

    await assignTo('9')

    expect(text()).not.toMatch(/could not be assigned/)
  })

  it('goes as soon as the next batch is sent, not when it answers', async () => {
    // While the next batch is out, the line would be describing it, and it
    // is about the one before.
    bulkMock.mockResolvedValueOnce({ results: [{ ticketId: 1, ok: false, error: 'not found' }] })
    bulkMock.mockImplementationOnce(() => new Promise(() => {}))
    await mountPage()
    await selectRow()
    await assignTo('9')
    expect(text()).toMatch(/could not be assigned/)

    await selectRow()
    await assignTo('9')

    expect(button('Assigning…').element.disabled).toBe(true)
    expect(text()).not.toMatch(/could not be assigned/)
  })
})

describe('the selection', () => {
  const twoPages = () => {
    responses[1] = {
      items: [ROW, { ...ROW, id: 2, ticketNumber: 'SUP-2026-00002' }],
      total: 4,
      page: 1,
      limit: 2,
      hasMore: true,
      asOf: WALK.asOf,
      after: 'cursor-after-page-1'
    }
    responses[2] = {
      items: [
        { ...ROW, id: 3, ticketNumber: 'SUP-2026-00003' },
        { ...ROW, id: 4, ticketNumber: 'SUP-2026-00004' }
      ],
      total: 4,
      page: 2,
      limit: 2,
      hasMore: false,
      asOf: WALK.asOf,
      after: null
    }
  }

  const header = () =>
    w().get<HTMLInputElement>('input[aria-label="Select every ticket on this page"]')

  const selectedCount = () => w().get('.bulk-actions-bar__count').text()

  it('answers the header checkbox for the rows on screen, not the whole selection', async () => {
    // A shipped bug with no React test: with page one fully selected, page
    // two's header showed as ticked, and clicking it cleared page one's
    // selection instead of selecting page two.
    twoPages()
    await mountPage()
    await header().setValue(true)
    expect(selectedCount()).toBe('2 tickets selected')

    await click('Next')
    expect(header().element.checked).toBe(false)

    await header().setValue(true)

    expect(selectedCount()).toBe('4 tickets selected')
    expect(header().element.checked).toBe(true)
  })

  it('takes only this page back off when its header is unticked', async () => {
    twoPages()
    await mountPage()
    await header().setValue(true)
    await click('Next')
    await header().setValue(true)

    await header().setValue(false)

    expect(selectedCount()).toBe('2 tickets selected')
  })

  it('shows a partly selected page as partly selected', async () => {
    twoPages()
    await mountPage()

    await selectRow('SUP-2026-00001')

    expect(header().element.checked).toBe(false)
    expect(header().element.indeterminate).toBe(true)
  })

  it('survives paging forward and back', async () => {
    twoPages()
    await mountPage()
    await selectRow('SUP-2026-00001')

    await click('Next')
    await click('Previous')

    expect(selectedCount()).toBe('1 ticket selected')
    expect(
      w().get<HTMLInputElement>('input[aria-label="Select SUP-2026-00001"]').element.checked
    ).toBe(true)
  })

  it('is dropped when the filters change', async () => {
    await mountPage()
    await selectRow()

    await click('Pending user')

    expect(w().find('[aria-label="Bulk actions"]').exists()).toBe(false)
  })

  it('is kept when only the page size changes, as it was in React', async () => {
    await mountPage()
    await selectRow()

    const box = w().get('input[aria-label="Rows per page"]')
    await box.setValue('25')
    await box.trigger('keydown', { key: 'Enter' })
    await flushPromises()

    expect(lastAsk()).toMatchObject({ page: 1, limit: 25 })
    expect(selectedCount()).toBe('1 ticket selected')
  })

  it('does not open the ticket when its checkbox is ticked', async () => {
    await mountPage()

    await w().get('input[aria-label="Select SUP-2026-00001"]').trigger('click')

    expect(replaceMock).not.toHaveBeenCalled()
  })
})

describe('opening a ticket', () => {
  it('reaches every row from the keyboard, by a button named after the ticket', async () => {
    // AdminDataTable's rows open by mouse only. The name is the one the e2e
    // suite clicks: "Open SUP-YYYY-NNNNN".
    await mountPage()

    const open = button('Open SUP-2026-00001')
    expect(open.element.tagName).toBe('BUTTON')
    expect(open.attributes('type')).toBe('button')
    expect(open.text()).toBe('SUP-2026-00001')
  })

  it('writes the ticket into the address with replace, and opens the panel on it', async () => {
    await mountPage()

    await click('Open SUP-2026-00001')

    expect(replaceMock.mock.calls).toEqual([[{ query: { ticket: '1' } }]])
    expect(w().find('[data-panel="1"]').exists()).toBe(true)
  })

  it('opens from anywhere on the row, and moves focus to that row’s button', async () => {
    // The panel returns focus to whatever opened it; a click on a plain cell
    // would otherwise leave it nothing to return to.
    await mountPage()

    await w().get('td.queue-table__subject').trigger('click')
    await flushPromises()

    expect(replaceMock.mock.calls).toEqual([[{ query: { ticket: '1' } }]])
    expect(document.activeElement).toBe(button('Open SUP-2026-00001').element)
  })

  it('opens the panel from a deep link', async () => {
    route.query = { ticket: '128' }

    await mountPage()

    const panel = w().findComponent(PanelStub)
    expect(panel.props()).toEqual({ ticketId: 128, canDelete: false })
  })

  it.each([['abc'], ['0'], ['-3'], ['1.5'], ['012'], ['1e3'], [' 12'], ['']])(
    'ignores ?ticket=%j rather than opening a ticket that cannot exist',
    async (value) => {
      route.query = { ticket: value }

      await mountPage()

      expect(w().findComponent(PanelStub).exists()).toBe(false)
    }
  )

  it('ignores a ticket named twice in the address', async () => {
    route.query = { ticket: ['4', '5'] }

    await mountPage()

    expect(w().findComponent(PanelStub).exists()).toBe(false)
  })

  it('offers delete to an admin only', async () => {
    route.query = { ticket: '128' }

    await mountPage(ticketAdmin)

    expect(w().findComponent(PanelStub).props('canDelete')).toBe(true)
  })

  // Deleting is gated on the server's AdminScope (IsAdminScoped), which the
  // store carries as isTicketAdmin. The role name is a different question,
  // Team 1's isAdmin getter, and the two can disagree: a role that says admin
  // with the AdminScope row gone, or AdminScope granted to another role. The
  // fixtures above agree on both, so they cannot tell the two apart.
  it.each([
    ['role admin, AdminScope gone', { ...ticketAdmin, isAdmin: false }, false],
    ['role support, AdminScope granted', { ...pureAgent, isAdmin: true }, true]
  ])('asks the server flag, not the role name: %s', async (_, user, canDelete) => {
    route.query = { ticket: '128' }

    await mountPage(user)

    expect(w().findComponent(PanelStub).props('canDelete')).toBe(canDelete)
  })

  it('keeps the rest of the address when it opens a ticket', async () => {
    route.query = { from: 'email' }
    await mountPage()

    await click('Open SUP-2026-00001')

    expect(replaceMock.mock.calls).toEqual([[{ query: { from: 'email', ticket: '1' } }]])
  })

  it('keeps focus on the ticket’s own button when that is what was clicked', async () => {
    // Safari, and Firefox on macOS, do not focus a clicked button (nor does
    // jsdom), which would leave the panel no opener to hand focus back to.
    await mountPage()

    await click('Open SUP-2026-00001')

    expect(document.activeElement).toBe(button('Open SUP-2026-00001').element)
  })

  it('takes the ticket out of the address when the panel closes, and nothing else', async () => {
    route.query = { ticket: '128', from: 'email' }
    await mountPage()

    w().findComponent(PanelStub).vm.$emit('close')
    await flushPromises()

    expect(replaceMock.mock.calls).toEqual([[{ query: { from: 'email' } }]])
    expect(w().findComponent(PanelStub).exists()).toBe(false)
  })

  it('reloads the rows and the counters after a write in the panel, on the same page and walk', async () => {
    // Anything that changes a ticket can move it between counter cards and
    // in the sort order, so both are read again, under the walk already on
    // screen.
    await mountPage()
    await click('Next')
    route.query = { ticket: '1' }
    await flushPromises()
    const summaryBefore = summaryMock.mock.calls.length

    w().findComponent(PanelStub).vm.$emit('changed')
    await flushPromises()

    expect(lastAsk()).toMatchObject({ page: 2, walk: WALK })
    expect(summaryMock.mock.calls.length - summaryBefore).toBe(1)
  })

  it('closes, reloads and forgets a ticket deleted from the panel', async () => {
    // The bulk bar counts the selection, so leaving the id there makes it
    // offer to assign a ticket that no longer exists.
    firstPageItems = [ROW, { ...ROW, id: 2, ticketNumber: 'SUP-2026-00002' }]
    await mountPage(ticketAdmin)
    await selectRow('SUP-2026-00001')
    await selectRow('SUP-2026-00002')
    await click('Open SUP-2026-00001')
    const queueBefore = queueMock.mock.calls.length
    const summaryBefore = summaryMock.mock.calls.length

    w().findComponent(PanelStub).vm.$emit('deleted', 1)
    await flushPromises()

    expect(w().findComponent(PanelStub).exists()).toBe(false)
    expect(route.query).toEqual({})
    expect(w().get('.bulk-actions-bar__count').text()).toBe('1 ticket selected')
    expect(queueMock.mock.calls.length - queueBefore).toBe(1)
    expect(summaryMock.mock.calls.length - summaryBefore).toBe(1)
  })

  it('leaves another ticket open when a delete from an earlier panel lands late', async () => {
    // Back took ?ticket=1 away while its delete was in flight, and the agent
    // opened ticket 2 before the answer came back.
    firstPageItems = [ROW, { ...ROW, id: 2, ticketNumber: 'SUP-2026-00002' }]
    await mountPage(ticketAdmin)
    route.query = { ticket: '2' }
    await flushPromises()
    const queueBefore = queueMock.mock.calls.length

    w().findComponent(PanelStub).vm.$emit('deleted', 1)
    await flushPromises()

    expect(route.query).toEqual({ ticket: '2' })
    expect(w().findComponent(PanelStub).exists()).toBe(true)
    expect(queueMock.mock.calls.length - queueBefore).toBe(1)
  })
})

describe('coming back to the tab', () => {
  it('reads the queue and the counters again, on the page and walk on screen', async () => {
    // React Query's refetchOnWindowFocus, which the React queue turned on
    // for these two and nothing else. An agent works with the queue open and
    // comes back to it expecting to see what arrived while they were away.
    await mountPage()
    await click('Next')
    const summaryBefore = summaryMock.mock.calls.length
    const queueBefore = queueMock.mock.calls.length

    await tabBecomes('hidden')
    await tabBecomes('visible')

    expect(queueMock.mock.calls.length - queueBefore).toBe(1)
    expect(lastAsk()).toMatchObject({ page: 2, walk: WALK })
    expect(summaryMock.mock.calls.length - summaryBefore).toBe(1)
  })

  it('does nothing while the tab is hidden', async () => {
    await mountPage()
    const before = queueMock.mock.calls.length

    await tabBecomes('hidden')

    expect(queueMock.mock.calls.length).toBe(before)
  })

  it('stops listening once the page is gone', async () => {
    await mountPage()
    wrapper!.unmount()
    wrapper = null
    const before = queueMock.mock.calls.length

    await tabBecomes('visible')

    expect(queueMock.mock.calls.length).toBe(before)
  })
})

describe('a refresh of page one', () => {
  // Page one's own answer hands out the cursor for page two, so the walk map
  // holds an entry for page two the moment page one has loaded. A refresh of
  // page one that reached for any cursor it could find would take that one
  // and print page two's rows under page one's number. Page one is read live
  // every time, whatever asked for it (U2 QU-41, QU-63).
  const refreshes: [string, () => Promise<void>][] = [
    [
      'the tab coming back',
      async () => {
        await tabBecomes('hidden')
        await tabBecomes('visible')
      }
    ],
    [
      'a write in the detail panel',
      async () => {
        route.query = { ticket: '1' }
        await flushPromises()
        w().findComponent(PanelStub).vm.$emit('changed')
        await flushPromises()
      }
    ],
    [
      'a bulk assign',
      async () => {
        await selectRow()
        await assignTo('9')
      }
    ]
  ]

  it.each(refreshes)('reads page one live after %s', async (_, refresh) => {
    await mountPage()
    const before = asked.length

    await refresh()

    // A request really went out: the mount's own page-one read would satisfy
    // the second assertion on its own.
    expect(asked.length - before).toBe(1)
    expect(lastAsk()).toEqual({ page: 1, limit: 10, filters: {}, walk: undefined })
  })
})

describe('Export to Excel (C-09)', () => {
  const FILE = { blob: new Blob(['xlsx']), filename: 'tickets-2026-09-29.xlsx' }

  it('exports what the filters match, and never the page, size or walk', async () => {
    // An export is a fresh look at everything that matches now. An old
    // walk's asOf would drop every ticket worked since it was taken.
    exportMock.mockResolvedValue(FILE)
    await mountPage()
    await click('Open')
    await click('Next')

    await click('Export to Excel')

    expect(exportMock.mock.calls).toEqual([[{ status: 'open' }]])
    expect(saveMock.mock.calls).toEqual([[FILE]])
  })

  it('cannot be started twice while one is running', async () => {
    // Two presses in one tick, before the disabled attribute has rendered:
    // the guard has to read live state.
    exportMock.mockImplementation(() => new Promise(() => {}))
    await mountPage()

    const go = button('Export to Excel')
    go.element.click()
    go.element.click()
    await flushPromises()

    expect(exportMock).toHaveBeenCalledTimes(1)
  })

  it('says it is running and is disabled until it finishes', async () => {
    let finish: (file: typeof FILE) => void = () => {}
    exportMock.mockImplementation(() => new Promise((resolve) => (finish = resolve)))
    await mountPage()

    await click('Export to Excel')
    expect(button(/Exporting…/).element.disabled).toBe(true)

    finish(FILE)
    await flushPromises()
    expect(button('Export to Excel').element.disabled).toBe(false)
  })

  it('says so when the export fails', async () => {
    exportMock.mockRejectedValue(fault(500))
    await mountPage()

    await click('Export to Excel')

    expect(alerts()).toEqual(['Could not export the tickets. Please try again.'])
    expect(saveMock).not.toHaveBeenCalled()
    expect(button('Export to Excel').element.disabled).toBe(false)
  })

  it('takes the last failure down when the next export works', async () => {
    exportMock.mockRejectedValueOnce(fault(500))
    exportMock.mockResolvedValueOnce(FILE)
    await mountPage()
    await click('Export to Excel')
    expect(alerts()).toEqual(['Could not export the tickets. Please try again.'])

    await click('Export to Excel')

    expect(alerts()).toEqual([])
    expect(saveMock.mock.calls).toEqual([[FILE]])
  })

  it('gives the server’s own reason when it wrote one for a person', async () => {
    exportMock.mockRejectedValue(
      new ApiError(
        {
          error: 'You do not have support privileges.',
          code: 'permission_denied',
          request_id: 'r-1'
        },
        403
      )
    )
    await mountPage()

    await click('Export to Excel')

    expect(alerts()).toEqual(['You do not have support privileges.'])
  })
})
