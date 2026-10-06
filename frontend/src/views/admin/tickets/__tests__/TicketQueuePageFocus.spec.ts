import { flushPromises, mount, type VueWrapper } from '@vue/test-utils'
import { createPinia, setActivePinia } from 'pinia'
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest'

import { pureAgent, ticketAdmin } from '@/__tests__/supportAccountFixtures'
import type { TicketQueue, TicketRow } from '@/utils/ticketAgentSchema'

/**
 * Where keyboard focus goes on the queue page when the control that had it is
 * taken away. Real components throughout, the detail panel included: the
 * panel hands focus back to the row button that opened it as it closes, and
 * what the page does after that is only worth testing against the real
 * hand-back.
 *
 * jsdom moves focus to <body> when the focused element leaves the document,
 * as a browser does, so every case below starts from the same place a
 * keyboard user does. (It does not do the same for a control that is
 * disabled; those cases are pinned by attribute in the pager's specs.)
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

// The queue's calls and the panel's, and nothing else: the helpers stay real.
vi.mock('@/utils/ticketAgentAPI', async () => {
  const actual =
    await vi.importActual<typeof import('@/utils/ticketAgentAPI')>('@/utils/ticketAgentAPI')
  return {
    ...actual,
    fetchTicketQueue: vi.fn(),
    fetchTicketSummary: vi.fn(),
    fetchAssignees: vi.fn(),
    fetchTicketRegions: vi.fn(),
    bulkAssignTickets: vi.fn(),
    exportTickets: vi.fn(),
    saveTicketExport: vi.fn(),
    fetchTicketDetail: vi.fn(),
    fetchTicketHistory: vi.fn(),
    updateTicket: vi.fn(),
    sendTicketMessage: vi.fn(),
    deleteTicket: vi.fn(),
    downloadTicketAttachment: vi.fn()
  }
})

import TicketDetailPanel from '@/components/admin/tickets/detail/TicketDetailPanel.vue'
import { ticketWith } from '@/components/admin/tickets/detail/__tests__/ticketDetailFixtures'
import {
  bulkAssignTickets,
  fetchAssignees,
  fetchTicketDetail,
  fetchTicketHistory,
  fetchTicketQueue,
  fetchTicketRegions,
  fetchTicketSummary
} from '@/utils/ticketAgentAPI'
import { useAuthStore } from '@/stores/auth'
import TicketQueuePage from '../TicketQueuePage.vue'

const route = holder.route!

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

// What the queue endpoint holds right now. A test takes a row out to stand
// for a ticket that has left the filter the agent is looking at.
let rows: TicketRow[] = []

let wrapper: VueWrapper | null = null

beforeEach(() => {
  vi.clearAllMocks()
  vi.spyOn(console, 'warn').mockImplementation(() => {})
  rows = [row(7), row(8)]
  vi.mocked(fetchTicketQueue).mockImplementation(
    async (page, limit): Promise<TicketQueue> => ({
      items: structuredClone(rows),
      total: rows.length,
      page,
      limit,
      hasMore: false,
      asOf: '2026-09-06T05:00:00Z',
      after: null
    })
  )
  vi.mocked(fetchTicketSummary).mockResolvedValue({
    unassigned: 2,
    open: 2,
    pendingUser: 0,
    overdue: 0
  })
  vi.mocked(fetchAssignees).mockResolvedValue([{ id: 9, name: 'Sam Reid', assignable: true }])
  vi.mocked(fetchTicketRegions).mockResolvedValue([])
  vi.mocked(fetchTicketDetail).mockImplementation(async (id) =>
    ticketWith({ id, ticketNumber: `SUP-2026-${String(id).padStart(5, '0')}` })
  )
  vi.mocked(fetchTicketHistory).mockResolvedValue([])
  vi.mocked(bulkAssignTickets).mockResolvedValue({ results: [{ ticketId: 7, ok: true }] })
})

afterEach(() => {
  wrapper?.unmount()
  wrapper = null
  route.query = {}
  document.body.innerHTML = ''
  vi.restoreAllMocks()
})

async function mountPage(user: object = pureAgent) {
  setActivePinia(createPinia())
  useAuthStore().loginWithUser(user as never)
  wrapper = mount(TicketQueuePage, { attachTo: document.body })
  await flushPromises()
  return wrapper
}

function w() {
  if (!wrapper) throw new Error('mount the page first')
  return wrapper
}

function table() {
  return w().get('[role="region"][aria-label="Tickets"]').element
}

function openButton(id: number) {
  return w().find<HTMLButtonElement>(
    `button[aria-label="Open SUP-2026-${String(id).padStart(5, '0')}"]`
  )
}

async function openFromRow(id: number) {
  await openButton(id).trigger('click')
  await flushPromises()
  expect(document.querySelector('.ticket-panel')).not.toBeNull()
}

async function pressEscape() {
  document.dispatchEvent(new KeyboardEvent('keydown', { key: 'Escape', bubbles: true }))
  await flushPromises()
  expect(document.querySelector('.ticket-panel')).toBeNull()
}

function panel() {
  return w().findComponent(TicketDetailPanel)
}

describe('focus after a bulk assign goes through', () => {
  async function pickAndFocusAssign() {
    await w().get('input[aria-label="Select SUP-2026-00007"]').setValue(true)
    await w().get('select[aria-label="Assign to"]').setValue('9')
    const assign = w()
      .findAll<HTMLButtonElement>('button')
      .find((b) => b.text() === 'Assign')!
    assign.element.focus()
    return assign
  }

  it('moves to the table when the bar holding the pressed button goes', async () => {
    await mountPage()
    const assign = await pickAndFocusAssign()

    await assign.trigger('click')
    await flushPromises()

    expect(w().find('[aria-label="Bulk actions"]').exists()).toBe(false)
    expect(document.activeElement).toBe(table())
  })

  it('stays where the agent took it while the batch was out', async () => {
    let finish: (value: { results: { ticketId: number; ok: boolean }[] }) => void = () => {}
    vi.mocked(bulkAssignTickets).mockImplementation(
      () => new Promise((resolve) => (finish = resolve))
    )
    await mountPage()
    const assign = await pickAndFocusAssign()
    await assign.trigger('click')
    const search = w().get('input[aria-label="Search tickets"]').element as HTMLInputElement
    search.focus()

    finish({ results: [{ ticketId: 7, ok: true }] })
    await flushPromises()

    expect(w().find('[aria-label="Bulk actions"]').exists()).toBe(false)
    expect(document.activeElement).toBe(search)
  })
})

describe('focus when the detail panel closes', () => {
  it('goes back to the row button that opened the panel while that row is still there', async () => {
    // The panel's own hand-back. The page must not override it.
    await mountPage()
    await openFromRow(7)

    await pressEscape()

    expect(document.activeElement).toBe(openButton(7).element)
  })

  it('goes to the table when a refresh took the row away while the panel was open', async () => {
    // The triage flow: from the Unassigned card, an agent opens a ticket and
    // assigns it. The panel reports the write, the quiet refresh leaves that
    // ticket out, and its row and Open button go with it.
    await mountPage()
    await openFromRow(7)
    rows = [row(8)]
    panel().vm.$emit('changed')
    await flushPromises()
    expect(openButton(7).exists()).toBe(false)

    await pressEscape()

    expect(document.activeElement).toBe(table())
  })

  it('goes to the table when the panel was opened from a link, with nothing here to return to', async () => {
    route.query = { ticket: '7' }
    await mountPage()
    expect(document.querySelector('.ticket-panel')).not.toBeNull()

    await pressEscape()

    expect(document.activeElement).toBe(table())
  })

  it('goes to the table once a ticket deleted from its panel has left the queue', async () => {
    // The panel hands focus back to the deleted ticket's row button as it
    // closes, and the refresh then takes that row away.
    await mountPage(ticketAdmin)
    await openFromRow(7)
    rows = [row(8)]

    panel().vm.$emit('deleted', 7)
    await flushPromises()

    expect(document.querySelector('.ticket-panel')).toBeNull()
    expect(openButton(7).exists()).toBe(false)
    expect(document.activeElement).toBe(table())
  })
})
