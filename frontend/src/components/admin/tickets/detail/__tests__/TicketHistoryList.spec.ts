import { flushPromises, mount } from '@vue/test-utils'
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest'

import type { TicketHistoryEntry } from '@/utils/ticketAgentSchema'

import TicketHistoryList from '../TicketHistoryList.vue'
import {
  api,
  deferred,
  historyEntry,
  openPanel,
  panelHost,
  resetPanelTests,
  serverError,
  ticketWith,
  type Panel
} from './ticketDetailFixtures'

// Where focus goes when the History list's Try again is pressed. The button
// is removed as soon as it is pressed ("Loading…" takes its place), and a
// browser sends focus from a removed element to the page body, which here is
// outside the modal panel. Through the real panel, so the retry is the real
// one and the list really is re-rendered in its place.
vi.mock('@/utils/ticketAgentAPI', async (importOriginal) => ({
  ...(await importOriginal<typeof import('@/utils/ticketAgentAPI')>()),
  fetchTicketDetail: vi.fn(),
  fetchAssignees: vi.fn(),
  fetchTicketHistory: vi.fn(),
  updateTicket: vi.fn(),
  sendTicketMessage: vi.fn(),
  deleteTicket: vi.fn(),
  downloadTicketAttachment: vi.fn()
}))

beforeEach(resetPanelTests)
afterEach(resetPanelTests)

const historyDown = () =>
  serverError(500, { error: 'Internal server error', code: 'internal_server_error', request_id: 'h1' })

/** The panel on its Details tab, with the history read refused once. */
async function detailsWithHistoryDown(): Promise<Panel> {
  api.fetchTicketHistory.mockRejectedValueOnce(await historyDown())
  const panel = await openPanel(ticketWith())
  const details = panel.page.findAll('[role="tab"]').find((tab) => tab.text() === 'Details')!
  await details.trigger('click')
  await flushPromises()
  return panel
}

function tryAgain({ page }: Panel) {
  return page
    .get('.ticket-history')
    .findAll('button')
    .find((button) => button.text() === 'Try again')
}

function historyHeading({ page }: Panel) {
  return page.get('.ticket-history h3')
}

async function pressTryAgain(panel: Panel) {
  const button = tryAgain(panel)!
  ;(button.element as HTMLButtonElement).focus()
  expect(document.activeElement).toBe(button.element)
  await button.trigger('click')
  await flushPromises()
}

describe('History: Try again', () => {
  it('moves focus to the History heading, inside the panel, while the list loads again', async () => {
    const panel = await detailsWithHistoryDown()
    const answer = deferred<TicketHistoryEntry[]>()
    api.fetchTicketHistory.mockReturnValueOnce(answer.promise)

    await pressTryAgain(panel)

    // The button has gone, as it should: the read is running again.
    expect(tryAgain(panel)).toBeUndefined()
    expect(panel.page.get('.ticket-history').text()).toContain('Loading…')
    // Focus did not go to the page body with it.
    expect(document.activeElement).toBe(historyHeading(panel).element)
    expect(document.activeElement!.textContent).toBe('History')
    expect(panel.page.get('[role="dialog"]').element.contains(document.activeElement)).toBe(true)

    // And it is still there once the list is back.
    answer.resolve([historyEntry()])
    await flushPromises()
    expect(panel.page.get('.ticket-history__list').text()).toContain('Status changed')
    expect(document.activeElement).toBe(historyHeading(panel).element)
  })

  it('stays on the heading when the second try fails too, with the new Try again next', async () => {
    const panel = await detailsWithHistoryDown()
    api.fetchTicketHistory.mockRejectedValueOnce(await historyDown())

    await pressTryAgain(panel)

    expect(panel.page.get('.ticket-history [role="alert"]').text()).toBe('The history could not be loaded.')
    expect(tryAgain(panel)).toBeDefined()
    expect(document.activeElement).toBe(historyHeading(panel).element)
  })

  it('can take focus from a script, and is not a stop in the Tab order', async () => {
    const panel = await detailsWithHistoryDown()

    expect(historyHeading(panel).attributes('tabindex')).toBe('-1')
  })

  it('leaves focus on the button when nothing started a new read', async () => {
    // The list itself, with a parent that ignores the event: the button stays,
    // and moving focus away from a button that is still there would lose the
    // reader's place for nothing.
    const list = mount(TicketHistoryList, {
      props: { entries: null, state: 'failed' },
      attachTo: panelHost()
    })
    const button = list.findAll('button').find((node) => node.text() === 'Try again')!
    ;(button.element as HTMLButtonElement).focus()

    await button.trigger('click')
    await flushPromises()

    expect(list.emitted('retry')).toEqual([[]])
    expect(button.element.isConnected).toBe(true)
    expect(document.activeElement).toBe(button.element)
    list.unmount()
  })
})
