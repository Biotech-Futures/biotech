import { flushPromises, mount, type VueWrapper } from '@vue/test-utils'
import { createPinia, setActivePinia } from 'pinia'
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest'

import { pureAgent } from '@/__tests__/supportAccountFixtures'
import type { TicketQueue, TicketRow } from '@/utils/ticketAgentSchema'

/**
 * The queue's page count and rows-per-page control, against the size the
 * server actually served rather than the one the agent asked for. Ported from
 * adminweb's TicketQueuePagePageSize.test.tsx.
 *
 * The admin queue endpoint clamps `limit` to MAX_PAGE_SIZE and answers with
 * the value it used, pinned on the server side by
 * tests/apps/tickets/test_api_admin.py::test_the_queue_echoes_the_limit_it_used_not_the_one_asked_for,
 * which writes 100 out rather than importing the constant. The cap is written
 * out here for the same reason: this file is about the client honouring what
 * it was served, and importing the number from either side would make the
 * test agree with a change nobody meant to make.
 *
 * One thing differs from React on purpose. The React control offered 200 and
 * a custom box reaching 500 and then read "200" while the server sent 100 a
 * page (U2 GAP-10, kept there as a trade-off React's Select forced). This
 * control offers nothing past the server's cap, so the first sweep below
 * types 200 and 500 and expects the control, the request and the count to
 * say 100. The page count still divides by the size the server served, and
 * the walk tests below prove it against a server whose cap sits under what
 * was asked for, which is the only way that rule can still matter.
 */

vi.mock('vue-router', () => ({
  useRoute: () => ({ path: '/admin/tickets', query: {} }),
  useRouter: () => ({ replace: vi.fn() })
}))

vi.mock('@/utils/ticketAgentAPI', async () => {
  const actual = await vi.importActual<typeof import('@/utils/ticketAgentAPI')>(
    '@/utils/ticketAgentAPI'
  )
  return {
    ...actual,
    fetchTicketQueue: vi.fn(),
    fetchTicketSummary: vi.fn(),
    fetchAssignees: vi.fn(),
    fetchTicketRegions: vi.fn()
  }
})

import {
  fetchAssignees,
  fetchTicketQueue,
  fetchTicketRegions,
  fetchTicketSummary
} from '@/utils/ticketAgentAPI'
import { useAuthStore } from '@/stores/auth'
import { PAGE_SIZE_PRESETS } from '@/components/admin/tickets/queue/queueRules'
import TicketQueuePage from '../TicketQueuePage.vue'

/** What apps/tickets/views.py clamps `limit` to. Measured, not imported. */
const SERVER_CAP = 100

/** The largest size this page's control lets an agent ask for. Written out
 *  for the same reason as the cap: it is a decision, not a derivation. */
const CONTROL_MAX = 100

let serverCap = SERVER_CAP

/** The fake server's whole contract, and the only model of it in this file. */
const serverServes = (asked: number) => Math.min(asked, serverCap)

/** What the control sends when a size is typed into it. */
const controlAsks = (typed: number) => Math.min(typed, CONTROL_MAX)

/**
 * What the footer must read. Written from the served size, and deliberately
 * not from anything the component computes.
 */
const truePageCount = (total: number, typed: number) =>
  Math.max(1, Math.ceil(total / serverServes(controlAsks(typed))))

const row = (id: number): TicketRow => ({
  id,
  ticketNumber: `SUP-2026-${String(id).padStart(5, '0')}`,
  user: { name: 'Mia', region: 'Australia', anonymous: false },
  subject: `Enquiry ${id}`,
  status: 'open',
  priority: 'normal',
  assignee: null,
  supportUpdatedAt: '2026-09-01T00:00:00Z',
  overdue: false
})

/**
 * The queue the fake server is holding.
 *
 * `rowCap` exists only to keep eighty-odd mounts cheap: the footer count, the
 * numbered nav and the control are a function of total / served / hasMore /
 * page and of nothing else on the response, so the sweep serves two rows a
 * page. The walk and the last-page click below serve full pages instead, and
 * they are the tests that read row numbers.
 */
let queueState: { total: number; rowCap: number; forceHasMore?: boolean } = {
  total: 0,
  rowCap: Infinity
}
/** Every (page, limit) the component asked the server for, oldest first. */
const asked: { page: number; limit: number }[] = []

let wrapper: VueWrapper | null = null

beforeEach(() => {
  vi.clearAllMocks()
  vi.mocked(fetchTicketQueue).mockImplementation(async (page, limit): Promise<TicketQueue> => {
    asked.push({ page, limit })
    const served = serverServes(limit)
    const start = (page - 1) * served
    const remaining = Math.max(0, Math.min(served, queueState.total - start))
    const shown = Math.min(remaining, queueState.rowCap)
    return {
      items: Array.from({ length: shown }, (_, i) => row(start + i + 1)),
      total: queueState.total,
      page,
      // The point of the whole file: the server answers with the size it
      // used, which is not always the size it was asked for.
      limit: served,
      hasMore: queueState.forceHasMore ?? start + remaining < queueState.total,
      asOf: '2026-09-06T05:00:00Z',
      after: remaining ? `2026-09-01T00:00:00Z_${start + remaining}` : null
    }
  })
  vi.mocked(fetchTicketSummary).mockResolvedValue({
    unassigned: 0,
    open: 0,
    pendingUser: 0,
    overdue: 0
  })
  vi.mocked(fetchAssignees).mockResolvedValue([])
  vi.mocked(fetchTicketRegions).mockResolvedValue([])
})

afterEach(() => {
  wrapper?.unmount()
  wrapper = null
  queueState = { total: 0, rowCap: Infinity }
  serverCap = SERVER_CAP
  asked.length = 0
})

async function mountPage() {
  setActivePinia(createPinia())
  useAuthStore().loginWithUser(pureAgent as never)
  wrapper = mount(TicketQueuePage, {
    global: { stubs: { TicketDetailPanel: true } }
  })
  await flushPromises()
  return wrapper
}

function w() {
  if (!wrapper) throw new Error('mount the page first')
  return wrapper
}

/**
 * Type a rows-per-page size into the control.
 *
 * The queue opens on 10, which is not a preset, so the control is the custom
 * number box, and typing the size then pressing Enter is the path an agent
 * takes to reach a size that is not on the list. One call per mount: once
 * the control has snapped to the dropdown it is a different widget.
 */
async function setRowsPerPage(size: number) {
  const box = w().get('input[aria-label="Rows per page"]')
  await box.setValue(String(size))
  await box.trigger('keydown', { key: 'Enter' })
  await flushPromises()
}

/** The exact footer sentence, so a wrong number cannot pass on a substring. */
function footer() {
  return w().get('.queue-pager__where').text()
}

/** What the rows-per-page control is claiming, in either of its two shapes. */
function rowsPerPageReads() {
  const control = w().get('[aria-label="Rows per page"]').element as
    | HTMLInputElement
    | HTMLSelectElement
  return control.value
}

/** The numbered buttons in the footer nav, in order, as they read. */
function pageNumbers() {
  return w()
    .get('nav[aria-label="Pagination"]')
    .findAll('button')
    .map((b) => b.text())
    .filter((label) => /^\d+$/.test(label))
}

function next() {
  return w()
    .get('nav[aria-label="Pagination"]')
    .findAll<HTMLButtonElement>('button')
    .find((b) => b.text() === 'Next')!
}

function ticketNumbersOnScreen() {
  return Array.from(w().text().matchAll(/SUP-2026-\d{5}/g)).map((m) => m[0])
}

/**
 * The sizes and totals the sweep covers, generated rather than listed.
 *
 * Sizes: every preset the control offers, plus two typed sizes past the
 * server's cap (the React control's 200 and the top of its custom box), plus
 * two sizes under the cap that are not presets. Taking the presets from the
 * control means a preset added later is covered without anyone remembering to
 * come back here.
 *
 * Totals: built around each size's *served* page boundary (a page short of
 * one, exactly one, one over, and the same at two and four pages), because
 * that is where a page count is wrong by one and nobody notices.
 */
const SIZES = [...PAGE_SIZE_PRESETS, 200, 500, 33, 7]
const CASES = SIZES.flatMap((size) =>
  [0, 1, 2, 4]
    .flatMap((pages) => [-1, 0, 1].map((delta) => pages * serverServes(controlAsks(size)) + delta))
    .filter((total) => total >= 1)
    .map((total) => ({ size, total }))
)

describe('the page count the queue prints', () => {
  it('covers every rows-per-page size the control offers, and sizes past the cap', () => {
    // Guards the generator itself. The expectations are written out by
    // hand, because deriving either from SIZES or PAGE_SIZE_PRESETS compared
    // the generator to itself: shrinking PAGE_SIZE_PRESETS to [25] deleted
    // thirty cases in React and the guard stayed green.
    expect(SIZES).toEqual(expect.arrayContaining([25, 50, 100, 200, 500]))
    expect(CASES.length).toBeGreaterThanOrEqual(70)
    expect(CASES.some(({ size }) => size > SERVER_CAP)).toBe(true)
    expect(CASES.some(({ size }) => size < SERVER_CAP)).toBe(true)
  })

  it.each(CASES)(
    'counts $total tickets at a typed $size by the size the server served',
    async ({ size, total }) => {
      queueState = { total, rowCap: 2 }
      await mountPage()
      await setRowsPerPage(size)

      const expected = truePageCount(total, size)
      expect(footer()).toBe(`Page 1 of ${expected}`)
      // The control never claims a size the server is not serving: typing
      // 200 or 500 reads back as 100.
      expect(rowsPerPageReads()).toBe(String(controlAsks(size)))
      // The pinned last-page button is the control an agent uses to reach the
      // end of a long queue, so it has to name the real last page.
      expect(pageNumbers().at(-1)).toBe(String(expected))
      // And the component must really have asked for that size: a client
      // that quietly sent something else would pass every line above.
      expect(asked.at(-1)).toEqual({ page: 1, limit: controlAsks(size) })
    }
  )
})

describe('walking a queue deeper than the server will serve a page of', () => {
  // The control cannot ask past 100 any more, so the case React measured
  // (450 rows at a requested 200, served as 100) is reproduced with a server
  // whose cap sits under a size the control does offer: 50 asked, 40 served.
  // Dividing by the asked size reads 9 pages where the server holds 12.
  const LOWER_CAP = 40

  it('never misstates the count on any page of the walk', async () => {
    serverCap = LOWER_CAP
    queueState = { total: 450, rowCap: Infinity }
    await mountPage()
    await setRowsPerPage(50)

    const expected = truePageCount(450, 50)
    expect(expected).toBe(12)
    const walk: string[] = []
    const nextOpen: boolean[] = []
    for (let i = 1; i <= expected; i++) {
      walk.push(footer())
      nextOpen.push(!next().element.disabled)
      if (i < expected) {
        await next().trigger('click')
        await flushPromises()
      }
    }

    expect(walk).toEqual(Array.from({ length: expected }, (_, i) => `Page ${i + 1} of ${expected}`))
    // Open on every page but the last, and shut there.
    expect(nextOpen).toEqual([...Array(expected - 1).fill(true), false])
  })

  it('sends the pinned last-page button to the last rows, not to the middle', async () => {
    serverCap = LOWER_CAP
    queueState = { total: 450, rowCap: Infinity }
    await mountPage()
    await setRowsPerPage(50)

    const last = truePageCount(450, 50)
    await w().get(`button[aria-label="Go to page ${last}"]`).trigger('click')
    await flushPromises()

    expect(footer()).toBe(`Page ${last} of ${last}`)
    // The last row of the queue, which is the row an agent clicks that button
    // to reach.
    expect(ticketNumbersOnScreen().at(-1)).toBe('SUP-2026-00450')
    expect(ticketNumbersOnScreen().at(0)).toBe('SUP-2026-00441')
  })
})

describe('the floor the walk’s frozen total needs', () => {
  it('still counts a page past the end when the server says there is more', async () => {
    // Unrelated to the clamp and easy to break while changing the divisor:
    // `total` counts the walk's frozen set, and a ticket somebody works
    // mid-walk leaves it, so the count can fall below the page being read.
    // hasMore is the floor that keeps Next alive with rows still ahead.
    queueState = { total: 25, rowCap: Infinity }
    await mountPage()
    expect(footer()).toBe('Page 1 of 3')

    // Somebody worked every row the walk had counted ahead of the reader, so
    // page two comes back with a total behind the page being read and
    // hasMore still true.
    queueState = { total: 5, rowCap: Infinity, forceHasMore: true }
    await next().trigger('click')
    await flushPromises()

    // ceil(5/10) = 1, but the reader is standing on page 2 with more behind
    // it, so the floor has to carry the count to 3.
    expect(footer()).toBe('Page 2 of 3')
    expect(next().element.disabled).toBe(false)
  })
})

describe('the footer while a page is loading', () => {
  it('holds every control still until the answer is in', async () => {
    queueState = { total: 25, rowCap: Infinity }
    await mountPage()
    vi.mocked(fetchTicketQueue).mockImplementation(() => new Promise(() => {}))

    await next().trigger('click')
    await flushPromises()

    expect(footer()).toBe('Page 2 of 2')
    const nav = w().get('nav[aria-label="Pagination"]').findAll<HTMLButtonElement>('button')
    expect(nav.every((b) => b.element.disabled)).toBe(true)
    expect(
      (w().get('[aria-label="Rows per page"]').element as HTMLInputElement).disabled
    ).toBe(true)
  })
})
