import { flushPromises } from '@vue/test-utils'
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest'

import type { AssigneeOption, TicketDetail, TicketHistoryEntry } from '@/utils/ticketAgentSchema'

import {
  ACTIVE,
  api,
  closeLikeTheQueue,
  deferred,
  historyEntry,
  mountPanel,
  openPanel,
  optionTexts,
  panelHost,
  pending,
  resetPanelTests,
  serverError,
  ticketGone,
  ticketWith,
  type Panel
} from './ticketDetailFixtures'

// Ported from adminweb/src/components/tickets/TicketDetailPanel.test.tsx
// (shell, header, history, times, delete) plus what the Vue panel owns that
// the React one left to TanStack Query and Radix: the stale-response token,
// the assignee read on every open (T02), focus in and out, Esc, and telling
// the queue after a write.
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

const STAMP = {
  day: 'numeric',
  month: 'short',
  year: 'numeric',
  hour: '2-digit',
  minute: '2-digit'
} as const

const REPLY = 'textarea[aria-label="Reply to the requester"]'
const NOTE = 'textarea[aria-label="Internal note, not visible to the requester"]'

/** The <dd> after a <dt> with this text, in the Details list. */
function fact({ page }: Panel, term: string): string {
  const dt = page.findAll('dt').find((node) => node.text() === term)
  if (!dt) throw new Error(`no <dt>${term}</dt>`)
  return dt.element.nextElementSibling?.textContent?.trim() ?? ''
}

function tab({ page }: Panel, label: string) {
  const found = page.findAll('[role="tab"]').find((node) => node.text() === label)
  if (!found) throw new Error(`no ${label} tab`)
  return found
}

async function openDetails(panel: Panel) {
  await tab(panel, 'Details').trigger('click')
  await flushPromises()
}

function button({ page }: Panel, scope: string, label: string) {
  const found = page.get(scope).findAll('button').find((node) => node.text() === label)
  if (!found) throw new Error(`no ${label} button in ${scope}`)
  return found
}

async function askToDelete(panel: Panel) {
  await openDetails(panel)
  await panel.page.get('.ticket-panel__delete-button').trigger('click')
  await flushPromises()
}

describe('opening a ticket', () => {
  it('says it is loading while the ticket is on its way, and nothing else', async () => {
    api.fetchTicketDetail.mockReturnValue(pending())
    api.fetchAssignees.mockResolvedValue([ACTIVE])
    const { page } = mountPanel(7)
    await flushPromises()

    expect(page.get('[role="dialog"]').text()).toContain('Loading…')
    expect(page.find('[role="alert"]').exists()).toBe(false)
  })

  it('answers a ticket that cannot be opened instead of loading for ever', async () => {
    // Never a permanent spinner. The commonest way to land here is a link to
    // a ticket that has since been deleted, and "Loading…" forever reads as a
    // broken page rather than an answer.
    api.fetchTicketDetail.mockRejectedValue(await ticketGone())
    api.fetchAssignees.mockResolvedValue([ACTIVE])
    const { page } = mountPanel(7)
    await flushPromises()

    expect(page.get('[role="alert"]').text()).toBe(
      'That ticket could not be opened. It may have been deleted.'
    )
    expect(page.text()).not.toContain('Loading…')
  })

  it('heads the panel with the number, the badges and the subject', async () => {
    const { page } = await openPanel(
      ticketWith({ status: 'pending_user', priority: 'high', overdue: true })
    )

    const title = page.get('h2')
    expect(title.text()).toContain('SUP-2026-00007')
    expect(title.get('.ticket-badge').text()).toBe('Pending user')
    expect(title.get('.priority-badge').text()).toBe('High priority')
    expect(title.get('.ticket-panel__overdue').text()).toBe('Overdue')
    expect(page.get('.ticket-panel__subject').text()).toBe('Cannot access group workspace')
  })

  it('leaves the overdue mark off a ticket the server does not call overdue', async () => {
    const { page } = await openPanel(ticketWith({ overdue: false }))

    expect(page.get('h2').text()).not.toContain('Overdue')
  })

  it('is a modal dialog named by its heading', async () => {
    const { page } = await openPanel(ticketWith())

    const dialog = page.get('[role="dialog"]')
    expect(dialog.attributes('aria-modal')).toBe('true')
    const title = document.getElementById(dialog.attributes('aria-labelledby') ?? '')
    expect(title?.tagName).toBe('H2')
    expect(title?.textContent).toContain('SUP-2026-00007')
  })

  it('never paints an older ticket over the one asked for', async () => {
    // Switching tickets quickly leaves two reads in flight. The slower one
    // answering last must not put the first ticket back on screen.
    const seven = deferred<TicketDetail>()
    const eight = deferred<TicketDetail>()
    api.fetchTicketDetail.mockReturnValueOnce(seven.promise).mockReturnValueOnce(eight.promise)
    api.fetchAssignees.mockResolvedValue([ACTIVE])
    const { wrapper, page } = mountPanel(7)
    await wrapper.setProps({ ticketId: 8 })

    eight.resolve(ticketWith({ id: 8, ticketNumber: 'SUP-2026-00008', subject: 'Eight' }))
    await flushPromises()
    seven.resolve(ticketWith({ id: 7, ticketNumber: 'SUP-2026-00007', subject: 'Seven' }))
    await flushPromises()

    expect(page.get('h2').text()).toContain('SUP-2026-00008')
    expect(page.text()).not.toContain('SUP-2026-00007')
    expect(api.fetchTicketDetail.mock.calls.map((call) => call[0])).toEqual([7, 8])
  })

  it('shows nothing of the previous ticket while the next one is loading', async () => {
    const { wrapper, page } = await openPanel(ticketWith())
    api.fetchTicketDetail.mockReturnValue(pending())

    await wrapper.setProps({ ticketId: 8 })
    await flushPromises()

    expect(page.get('[role="dialog"]').text()).toContain('Loading…')
    expect(page.text()).not.toContain('SUP-2026-00007')
    expect(page.find('textarea').exists()).toBe(false)
  })

  it('reads the assignee list afresh every time the panel opens (T02)', async () => {
    // In React the list was read once by the queue page and kept. A revoke on
    // the support agents page never reached it, so the revoked agent was
    // still on offer here and picking them was refused.
    const first = await openPanel(ticketWith(), {
      roster: [ACTIVE, { id: 5, name: 'Rita Revoked', assignable: true }]
    })
    expect(first.page.get('select[aria-label="Change assignee"]').text()).toContain('Rita Revoked')
    first.wrapper.unmount()

    const again = await openPanel(ticketWith(), {
      roster: [ACTIVE, { id: 5, name: 'Rita Revoked', assignable: false }]
    })

    expect(api.fetchAssignees).toHaveBeenCalledTimes(2)
    expect(again.page.get('select[aria-label="Change assignee"]').text()).not.toContain(
      'Rita Revoked'
    )
  })

  it('reads the assignee list again when the panel moves to another ticket', async () => {
    const { wrapper } = await openPanel(ticketWith())
    api.fetchTicketDetail.mockResolvedValue(ticketWith({ id: 8, ticketNumber: 'SUP-2026-00008' }))

    await wrapper.setProps({ ticketId: 8 })
    await flushPromises()

    expect(api.fetchAssignees).toHaveBeenCalledTimes(2)
  })

  it('never lets an older assignee list land over a newer one', async () => {
    // Two opens in a row leave two list reads in flight. The first one asked
    // before a revoke and answers last: painting it would put the revoked
    // agent back on offer, which is T02 again by another route.
    const before = deferred<AssigneeOption[]>()
    api.fetchAssignees
      .mockReturnValueOnce(before.promise)
      .mockResolvedValueOnce([ACTIVE, { id: 5, name: 'Rita Revoked', assignable: false }])
    api.fetchTicketDetail.mockResolvedValue(ticketWith())
    const { wrapper, page } = mountPanel(7)
    await flushPromises()

    api.fetchTicketDetail.mockResolvedValue(ticketWith({ id: 8, ticketNumber: 'SUP-2026-00008' }))
    await wrapper.setProps({ ticketId: 8 })
    await flushPromises()
    before.resolve([ACTIVE, { id: 5, name: 'Rita Revoked', assignable: true }])
    await flushPromises()

    expect(optionTexts(page.get('select[aria-label="Change assignee"]'))).toEqual([
      'Unassigned',
      'Sam Reid'
    ])
  })
})

describe('when the assignee list does not load', () => {
  const ASSIGNEES_DOWN =
    'The assignee list could not be loaded. The Assignee control is missing those choices.'

  async function failedRoster() {
    return Promise.reject(
      await serverError(500, {
        error: 'Internal server error',
        code: 'internal_server_error',
        request_id: 'a1'
      })
    )
  }

  function alertTexts({ page }: Panel) {
    return page.findAll('[role="alert"]').map((node) => node.text())
  }

  it('says so above the controls, since the panel made the request itself', async () => {
    // In React the queue page made this request and its banner said it
    // failed. The panel owns the request now, and without this the only sign
    // was a disabled row inside a dropdown nobody had opened yet.
    const panel = await openPanel(ticketWith(), { roster: failedRoster() })

    expect(alertTexts(panel)).toEqual([ASSIGNEES_DOWN])
  })

  it('says nothing while the list is still on its way, or once it is in', async () => {
    const loading = await openPanel(ticketWith(), { roster: pending() })
    expect(alertTexts(loading)).toEqual([])
    closeLikeTheQueue(loading)

    const loaded = await openPanel(ticketWith())
    expect(alertTexts(loaded)).toEqual([])
  })

  it('reads the list again on Try again, and moves focus to the Assignee control', async () => {
    const panel = await openPanel(ticketWith(), { roster: failedRoster() })
    api.fetchAssignees.mockResolvedValue([ACTIVE])

    await button(panel, '.ticket-panel__assignees-failed', 'Try again').trigger('click')
    await flushPromises()

    expect(api.fetchAssignees).toHaveBeenCalledTimes(2)
    expect(alertTexts(panel)).toEqual([])
    const assignee = panel.page.get('select[aria-label="Change assignee"]')
    expect(optionTexts(assignee)).toEqual(['Unassigned', 'Sam Reid'])
    // The button it was on has gone; focus did not go to the page with it.
    expect(document.activeElement).toBe(assignee.element)
  })

  it('names the Try again button by what it is for', async () => {
    const panel = await openPanel(ticketWith(), { roster: failedRoster() })

    const retry = button(panel, '.ticket-panel__assignees-failed', 'Try again')
    const described = document.getElementById(retry.attributes('aria-describedby') ?? '')
    expect(described?.textContent?.trim().replace(/\s+/g, ' ')).toBe(ASSIGNEES_DOWN)
  })
})

describe('focus, Esc and closing', () => {
  it('moves focus into the panel when it opens', async () => {
    const { page } = await openPanel(ticketWith())

    expect(document.activeElement).toBe(page.get('[role="dialog"]').element)
  })

  it('gives focus back to whatever opened it when it closes', async () => {
    const opener = document.createElement('button')
    opener.textContent = 'SUP-2026-00007'
    panelHost().appendChild(opener)
    opener.focus()

    const { wrapper } = await openPanel(ticketWith())
    expect(document.activeElement).not.toBe(opener)
    wrapper.unmount()

    expect(document.activeElement).toBe(opener)
  })

  it('closes on Esc from anywhere in the panel', async () => {
    const { wrapper, page } = await openPanel(ticketWith())

    await page.get(REPLY).trigger('keydown', { key: 'Escape' })

    expect(wrapper.emitted('close')).toHaveLength(1)
  })

  it('closes from the Close button and from a click beside the panel', async () => {
    const { wrapper, page } = await openPanel(ticketWith())

    await page.get('button[aria-label="Close"]').trigger('click')
    await page.get('.ticket-panel__backdrop').trigger('mousedown')

    expect(wrapper.emitted('close')).toHaveLength(2)
  })

  it('leaves Esc to the delete confirmation while that is open', async () => {
    const panel = await openPanel(ticketWith(), { canDelete: true })
    await askToDelete(panel)

    await panel.page.get('.admin-modal').trigger('keydown', { key: 'Escape' })
    await flushPromises()

    expect(panel.wrapper.emitted('close')).toBeUndefined()
    expect(panel.page.find('.admin-modal').exists()).toBe(false)
  })

  it('keeps Tab inside the panel: past the last control it comes back to the first', async () => {
    const { page } = await openPanel(ticketWith())
    await page.get(NOTE).setValue('Called the school.')
    const last = page.get('.note-box__send')
    ;(last.element as HTMLElement).focus()

    await last.trigger('keydown', { key: 'Tab' })

    expect(document.activeElement).toBe(page.get('button[aria-label="Close"]').element)
  })

  it('keeps Shift+Tab inside the panel too: before the first control it goes to the last', async () => {
    const { page } = await openPanel(ticketWith())
    await page.get(NOTE).setValue('Called the school.')
    const first = page.get('button[aria-label="Close"]')
    ;(first.element as HTMLElement).focus()

    await first.trigger('keydown', { key: 'Tab', shiftKey: true })

    expect(document.activeElement).toBe(page.get('.note-box__send').element)
  })
})

describe('the two tabs', () => {
  it('are a real tablist, with the selected one marked', async () => {
    const { page } = await openPanel(ticketWith())

    const tabs = page.findAll('[role="tab"]')
    expect(tabs.map((node) => [node.text(), node.attributes('aria-selected')])).toEqual([
      ['Conversation', 'true'],
      ['Details', 'false']
    ])
    const controlled = document.getElementById(tabs[1].attributes('aria-controls') ?? '')
    expect(controlled?.getAttribute('role')).toBe('tabpanel')
    expect(controlled?.textContent).toContain('History')
  })

  it('moves between tabs with the arrow keys', async () => {
    const panel = await openPanel(ticketWith())

    await tab(panel, 'Conversation').trigger('keydown', { key: 'ArrowRight' })
    await flushPromises()

    expect(panel.page.findAll('[role="tab"]').map((node) => node.attributes('aria-selected'))).toEqual(
      ['false', 'true']
    )
    expect(document.activeElement).toBe(tab(panel, 'Details').element)
  })

  it('keeps both drafts when the agent looks at Details and comes back (T09)', async () => {
    const panel = await openPanel(ticketWith())
    await panel.page.get(REPLY).setValue('Half a reply')
    await panel.page.get(NOTE).setValue('Half a note')

    await openDetails(panel)
    await tab(panel, 'Conversation').trigger('click')

    expect((panel.page.get(REPLY).element as HTMLTextAreaElement).value).toBe('Half a reply')
    expect((panel.page.get(NOTE).element as HTMLTextAreaElement).value).toBe('Half a note')
  })

  it('reads the history only when Details is opened', async () => {
    const panel = await openPanel(ticketWith())
    expect(api.fetchTicketHistory).not.toHaveBeenCalled()

    await openDetails(panel)

    expect(api.fetchTicketHistory).toHaveBeenCalledWith(7)
  })
})

describe('the requester and the ticket facts', () => {
  it('names the requester and their address', async () => {
    const panel = await openPanel(ticketWith())
    await openDetails(panel)

    expect(fact(panel, 'Requester')).toBe('Mia Thompson')
    expect(fact(panel, 'Email')).toBe('mia@example.com')
  })

  it('shows a dash, not a blank, on a ticket screening raised with no requester', async () => {
    const panel = await openPanel(
      ticketWith({ requester: null, region: '', channel: 'ai_screening' })
    )
    await openDetails(panel)

    expect(fact(panel, 'Requester')).toBe('—')
    expect(fact(panel, 'Email')).toBe('—')
    expect(fact(panel, 'Member since')).toBe('—')
    expect(fact(panel, 'Region')).toBe('Unknown')
    expect(fact(panel, 'Channel')).toBe('ai_screening')
  })

  it('says a ticket nobody has answered is not answered yet, and not resolved', async () => {
    const panel = await openPanel(ticketWith({ firstResponseAt: null, resolvedAt: null }))
    await openDetails(panel)

    expect(fact(panel, 'First reply')).toBe('Not yet')
    expect(fact(panel, 'Resolved')).toBe('—')
    expect(fact(panel, 'Category')).toBe('Help with a student or group')
  })

  it('shows the support clock as Updated, not the requester one', async () => {
    const panel = await openPanel(
      ticketWith({ updatedAt: '2026-08-02T00:00:00Z', supportUpdatedAt: '2026-08-05T06:30:00Z' })
    )
    await openDetails(panel)

    expect(fact(panel, 'Updated')).toBe(
      new Date('2026-08-05T06:30:00Z').toLocaleString('en-AU', { ...STAMP, timeZoneName: 'short' })
    )
  })
})

describe('the times this panel prints', () => {
  const RAISED = '2026-08-01T00:00:00Z'

  it('names the time zone on a timestamp', async () => {
    // Built from the clock this machine is on rather than matched against a
    // list of zone spellings: "UTC" here, "AEST" in Sydney, "GMT-3" in Sao
    // Paulo. Agents quote these times to each other across zones.
    const panel = await openPanel(ticketWith({ createdAt: RAISED }))
    await openDetails(panel)

    const withoutZone = new Date(RAISED).toLocaleString('en-AU', STAMP)
    const withZone = new Date(RAISED).toLocaleString('en-AU', { ...STAMP, timeZoneName: 'short' })
    expect(fact(panel, 'Raised')).toBe(withZone)
    // The zone is an addition, not a replacement.
    expect(withZone.startsWith(withoutZone)).toBe(true)
    expect(fact(panel, 'Raised')).not.toBe(withoutZone)
  })

  it('leaves Member since a plain date, with no zone on it', async () => {
    const panel = await openPanel(
      ticketWith({
        requester: {
          id: 9,
          name: 'Mia Thompson',
          email: 'mia@example.com',
          region: 'Australia',
          registeredAt: RAISED
        }
      })
    )
    await openDetails(panel)

    expect(fact(panel, 'Member since')).toBe(
      new Date(RAISED).toLocaleDateString('en-AU', {
        day: 'numeric',
        month: 'short',
        year: 'numeric'
      })
    )
  })
})

describe("the ticket's own history", () => {
  function line({ page }: Panel) {
    return page.get('.ticket-history__list').text()
  }

  it('names an action the way the audit page names it', async () => {
    api.fetchTicketHistory.mockResolvedValue([historyEntry()])
    const panel = await openPanel(ticketWith())
    await openDetails(panel)

    expect(line(panel)).toContain('Status changed')
    expect(line(panel)).not.toContain('status')
  })

  it('names the person when the row still has one', async () => {
    api.fetchTicketHistory.mockResolvedValue([historyEntry()])
    const panel = await openPanel(ticketWith())
    await openDetails(panel)

    expect(line(panel)).toContain('Sam Reid')
  })

  it("does not call a row the platform wrote 'system'", async () => {
    // The screening handoff writes with no actor on purpose, because no
    // person opened that ticket, and its snapshot carries the channel that
    // says so.
    api.fetchTicketHistory.mockResolvedValue([
      historyEntry({
        action: 'create',
        actor: null,
        beforeState: null,
        afterState: { channel: 'ai_screening', ticket_number: 'SUP-2026-00262' }
      })
    ])
    const panel = await openPanel(ticketWith())
    await openDetails(panel)

    expect(line(panel)).toContain('Automated screening')
    expect(line(panel)).not.toContain('system')
  })

  it('says the account is gone on a row that had a person on it', async () => {
    // Load-bearing next to the case above: printing "Automated screening" for
    // every empty actor passes that one on its own.
    api.fetchTicketHistory.mockResolvedValue([historyEntry({ actor: null })])
    const panel = await openPanel(ticketWith())
    await openDetails(panel)

    expect(line(panel)).toContain('Account removed')
    expect(line(panel)).not.toContain('system')
  })

  it('says so when there is nothing yet', async () => {
    api.fetchTicketHistory.mockResolvedValue([])
    const panel = await openPanel(ticketWith())
    await openDetails(panel)

    expect(panel.page.get('.ticket-history').text()).toContain('Nothing recorded yet.')
  })

  it('says the history could not be loaded instead of claiming there is none (T08)', async () => {
    api.fetchTicketHistory.mockRejectedValueOnce(
      await serverError(500, {
        error: 'Internal server error',
        code: 'internal_server_error',
        request_id: '9f1c2a'
      })
    )
    const panel = await openPanel(ticketWith())
    await openDetails(panel)

    const block = panel.page.get('.ticket-history')
    expect(block.get('[role="alert"]').text()).toBe('The history could not be loaded.')
    expect(block.text()).not.toContain('Nothing recorded yet.')

    api.fetchTicketHistory.mockResolvedValueOnce([historyEntry()])
    await button(panel, '.ticket-history', 'Try again').trigger('click')
    await flushPromises()

    expect(line(panel)).toContain('Status changed')
  })

  it("never shows the previous ticket's history under the next one", async () => {
    // Details stays open across a ticket change, so ticket 7's history read
    // can still be in flight when ticket 8's starts, and answer last.
    const seven = deferred<TicketHistoryEntry[]>()
    api.fetchTicketHistory.mockReturnValueOnce(seven.promise).mockResolvedValueOnce([])
    const panel = await openPanel(ticketWith())
    await openDetails(panel)

    api.fetchTicketDetail.mockResolvedValue(ticketWith({ id: 8, ticketNumber: 'SUP-2026-00008' }))
    await panel.wrapper.setProps({ ticketId: 8 })
    await flushPromises()
    seven.resolve([historyEntry({ actor: { id: 4, name: 'Seven Actor' } })])
    await flushPromises()

    expect(panel.page.get('h2').text()).toContain('SUP-2026-00008')
    expect(api.fetchTicketHistory.mock.calls.map((call) => call[0])).toEqual([7, 8])
    expect(panel.page.get('.ticket-history').text()).not.toContain('Seven Actor')
    expect(panel.page.get('.ticket-history').text()).toContain('Nothing recorded yet.')
  })

  it('reads the history again after a change while Details is showing', async () => {
    api.fetchTicketHistory.mockResolvedValue([])
    api.updateTicket.mockResolvedValue(ticketWith({ priority: 'high' }))
    const panel = await openPanel(ticketWith())
    await openDetails(panel)
    expect(api.fetchTicketHistory).toHaveBeenCalledTimes(1)

    await panel.page.get('select[aria-label="Change priority"]').setValue('high')
    await flushPromises()

    expect(api.fetchTicketHistory).toHaveBeenCalledTimes(2)
  })
})

describe('telling the queue', () => {
  it('says a change went through, and paints the answer without reading the ticket again', async () => {
    api.updateTicket.mockResolvedValue(ticketWith({ status: 'resolved' }))
    const { wrapper, page } = await openPanel(ticketWith({ status: 'in_progress' }))

    await page.get('select[aria-label="Change status"]').setValue('resolved')
    await flushPromises()

    expect(wrapper.emitted('changed')).toHaveLength(1)
    expect(page.get('h2 .ticket-badge').text()).toBe('Resolved')
    expect(api.fetchTicketDetail).toHaveBeenCalledTimes(1)
  })

  it('says nothing to the queue when the change was refused', async () => {
    api.updateTicket.mockRejectedValue(await ticketGone())
    const { wrapper, page } = await openPanel(ticketWith())

    await page.get('select[aria-label="Change status"]').setValue('resolved')
    await flushPromises()

    expect(wrapper.emitted('changed')).toBeUndefined()
  })

  it('reads the ticket once more after two changes that overlapped', async () => {
    // Two answers in flight can come back in either order, and the server
    // may have applied them in the other one. One read at the end settles it.
    const first = deferred<TicketDetail>()
    const second = deferred<TicketDetail>()
    api.updateTicket.mockReturnValueOnce(first.promise).mockReturnValueOnce(second.promise)
    const { wrapper, page } = await openPanel(ticketWith())
    api.fetchTicketDetail.mockResolvedValue(ticketWith({ status: 'resolved', priority: 'high' }))

    await page.get('select[aria-label="Change status"]').setValue('resolved')
    await page.get('select[aria-label="Change priority"]').setValue('high')
    second.resolve(ticketWith({ status: 'in_progress', priority: 'high' }))
    await flushPromises()
    first.resolve(ticketWith({ status: 'resolved', priority: 'normal' }))
    await flushPromises()

    expect(api.fetchTicketDetail).toHaveBeenCalledTimes(2)
    expect(page.get('h2 .ticket-badge').text()).toBe('Resolved')
    expect(page.get('h2 .priority-badge').text()).toBe('High priority')
    expect(wrapper.emitted('changed')).toHaveLength(2)
  })

  it('does not let an older answer overwrite a newer one while that read is on its way', async () => {
    const first = deferred<TicketDetail>()
    const second = deferred<TicketDetail>()
    api.updateTicket.mockReturnValueOnce(first.promise).mockReturnValueOnce(second.promise)
    const { page } = await openPanel(ticketWith())
    api.fetchTicketDetail.mockReturnValue(pending())

    await page.get('select[aria-label="Change status"]').setValue('resolved')
    await page.get('select[aria-label="Change priority"]').setValue('high')
    second.resolve(ticketWith({ status: 'in_progress', priority: 'high' }))
    await flushPromises()
    first.resolve(ticketWith({ status: 'resolved', priority: 'normal' }))
    await flushPromises()

    // The answer to the change made second is on screen; the one made first,
    // which came back last, is not painted over it.
    expect(page.get('h2 .priority-badge').text()).toBe('High priority')
  })

  it('does not paint the answer to a change on the ticket the panel has since left', async () => {
    // The agent changes ticket 7's priority and moves to ticket 8 before the
    // answer comes back. The answer is ticket 7; ticket 8 is on screen.
    const answer = deferred<TicketDetail>()
    api.updateTicket.mockReturnValue(answer.promise)
    const panel = await openPanel(ticketWith())
    await panel.page.get('select[aria-label="Change priority"]').setValue('high')

    api.fetchTicketDetail.mockResolvedValue(
      ticketWith({ id: 8, ticketNumber: 'SUP-2026-00008', subject: 'Eight' })
    )
    await panel.wrapper.setProps({ ticketId: 8 })
    await flushPromises()
    answer.resolve(ticketWith({ priority: 'high' }))
    await flushPromises()

    expect(panel.page.get('h2').text()).toContain('SUP-2026-00008')
    expect(panel.page.text()).not.toContain('SUP-2026-00007')
    // The change still went through, so the queue still hears about it.
    expect(panel.wrapper.emitted('changed')).toHaveLength(1)
  })
})

describe('a write that lands after the panel was closed (DT-39)', () => {
  // The queue unmounts the panel on close, and Vue drops every emit from an
  // unmounted component. In React the query layer refreshed the queue on the
  // write's success whether or not the sheet was still open.

  it('still tells the queue about a status change that lands after Esc', async () => {
    const onChanged = vi.fn()
    const onClose = vi.fn()
    const answer = deferred<TicketDetail>()
    api.updateTicket.mockReturnValue(answer.promise)
    const panel = await openPanel(ticketWith({ status: 'in_progress' }), {
      listeners: { onChanged, onClose }
    })

    await panel.page.get('select[aria-label="Change status"]').setValue('resolved')
    await panel.page.get('select[aria-label="Change status"]').trigger('keydown', { key: 'Escape' })
    expect(onClose).toHaveBeenCalledTimes(1)
    closeLikeTheQueue(panel)
    answer.resolve(ticketWith({ status: 'resolved' }))
    await flushPromises()

    expect(api.updateTicket).toHaveBeenCalledWith(7, { status: 'resolved' })
    expect(onChanged).toHaveBeenCalledTimes(1)
  })

  it('still tells the queue about a reply that lands after the panel was closed', async () => {
    const onChanged = vi.fn()
    const answer = deferred<TicketDetail>()
    api.sendTicketMessage.mockReturnValue(answer.promise)
    const panel = await openPanel(ticketWith(), { listeners: { onChanged } })

    await panel.page.get(REPLY).setValue('We have fixed it.')
    await panel.page.get('.reply-box').trigger('submit')
    await panel.page.get('button[aria-label="Close"]').trigger('click')
    closeLikeTheQueue(panel)
    answer.resolve(ticketWith())
    await flushPromises()

    expect(onChanged).toHaveBeenCalledTimes(1)
  })

  it('says nothing to the queue when the write that outlived the panel was refused', async () => {
    const onChanged = vi.fn()
    const answer = deferred<TicketDetail>()
    api.updateTicket.mockReturnValue(answer.promise)
    const panel = await openPanel(ticketWith(), { listeners: { onChanged } })

    await panel.page.get('select[aria-label="Change status"]').setValue('resolved')
    closeLikeTheQueue(panel)
    answer.reject(await ticketGone())
    await flushPromises()

    expect(onChanged).not.toHaveBeenCalled()
  })

  it('tells the queue once per write while it is open, not twice', async () => {
    // Load-bearing next to the tests above: calling the listener directly on
    // top of the emit would pass them and reload the queue twice here.
    const onChanged = vi.fn()
    api.updateTicket.mockResolvedValue(ticketWith({ priority: 'high' }))
    const panel = await openPanel(ticketWith(), { listeners: { onChanged } })

    await panel.page.get('select[aria-label="Change priority"]').setValue('high')
    await flushPromises()

    expect(onChanged).toHaveBeenCalledTimes(1)
    expect(panel.wrapper.emitted('changed')).toHaveLength(1)
  })

  it('reads nothing more for a panel that is no longer there', async () => {
    // Two overlapping writes normally end in one more read of the ticket, and
    // with Details showing, one of its history. With the panel gone there is
    // nothing to show either on.
    const first = deferred<TicketDetail>()
    const second = deferred<TicketDetail>()
    api.updateTicket.mockReturnValueOnce(first.promise).mockReturnValueOnce(second.promise)
    const panel = await openPanel(ticketWith())
    await openDetails(panel)
    expect(api.fetchTicketHistory).toHaveBeenCalledTimes(1)

    await panel.page.get('select[aria-label="Change status"]').setValue('resolved')
    await panel.page.get('select[aria-label="Change priority"]').setValue('high')
    closeLikeTheQueue(panel)
    second.resolve(ticketWith({ status: 'in_progress', priority: 'high' }))
    first.resolve(ticketWith({ status: 'resolved', priority: 'normal' }))
    await flushPromises()

    expect(api.fetchTicketDetail).toHaveBeenCalledTimes(1)
    expect(api.fetchTicketHistory).toHaveBeenCalledTimes(1)
  })

  it('still tells the queue which ticket went when a delete lands after the panel was closed', async () => {
    // The confirmation holds the panel open while a delete is on its way, but
    // the queue can still take the panel away (Back in the browser drops
    // ?ticket= from the address).
    const onDeleted = vi.fn()
    const answer = deferred<number>()
    api.deleteTicket.mockReturnValue(answer.promise)
    const panel = await openPanel(ticketWith(), { canDelete: true, listeners: { onDeleted } })
    await askToDelete(panel)
    await button(panel, '.admin-modal', 'Delete').trigger('click')

    closeLikeTheQueue(panel)
    answer.resolve(7)
    await flushPromises()

    expect(onDeleted).toHaveBeenCalledWith(7)
    expect(onDeleted).toHaveBeenCalledTimes(1)
  })
})

describe('deleting a ticket', () => {
  it('is not offered to a support agent at all', async () => {
    const panel = await openPanel(ticketWith(), { canDelete: false })
    await openDetails(panel)

    expect(panel.page.text()).not.toContain('Delete this ticket')
    expect(panel.page.find('.ticket-panel__delete-button').exists()).toBe(false)
  })

  it('asks first, naming the ticket and whose list it leaves', async () => {
    const panel = await openPanel(ticketWith(), { canDelete: true })
    await askToDelete(panel)

    const dialog = panel.page.get('.admin-modal')
    expect(dialog.get('h2').text()).toBe('Delete SUP-2026-00007?')
    expect(dialog.get('.admin-modal__message').text()).toBe(
      "This removes it from the queue and from Mia Thompson's own list of enquiries. " +
        'It cannot be undone from the app. A record of the deletion is kept in the history.'
    )
    expect(api.deleteTicket).not.toHaveBeenCalled()
  })

  it('says "the requester" when the ticket has none to name', async () => {
    const panel = await openPanel(ticketWith({ requester: null }), { canDelete: true })
    await askToDelete(panel)

    expect(panel.page.get('.admin-modal__message').text()).toContain(
      "from the requester's own list of enquiries"
    )
  })

  it('opens the confirmation on "Keep it", so an Enter straight away does not delete', async () => {
    // Radix's AlertDialog in React opened on its Cancel. ConfirmDialog
    // focuses its confirm button, which here is the one that deletes a
    // ticket for good.
    const panel = await openPanel(ticketWith(), { canDelete: true })
    await askToDelete(panel)

    expect(document.activeElement).toBe(button(panel, '.admin-modal', 'Keep it').element)
    expect(document.activeElement).not.toBe(button(panel, '.admin-modal', 'Delete').element)
  })

  it('sends one delete, however fast the second click on Delete comes', async () => {
    // Both clicks land before a re-render, so ConfirmDialog has not seen
    // `busy` yet and passes both on. What stops the second is the panel's
    // own check of `deleting`, read live.
    const answer = deferred<number>()
    api.deleteTicket.mockReturnValue(answer.promise)
    const panel = await openPanel(ticketWith(), { canDelete: true })
    await askToDelete(panel)

    const confirm = button(panel, '.admin-modal', 'Delete').element as HTMLButtonElement
    confirm.click()
    confirm.click()
    answer.resolve(7)
    await flushPromises()

    expect(api.deleteTicket).toHaveBeenCalledTimes(1)
    expect(panel.wrapper.emitted('deleted')).toEqual([[7]])
  })

  it('does not carry a refused delete over to the next ticket', async () => {
    api.deleteTicket.mockRejectedValue(
      await serverError(403, {
        error: 'You do not have admin privileges.',
        code: 'permission_denied',
        request_id: 'c3fbf345963e'
      })
    )
    const panel = await openPanel(ticketWith(), { canDelete: true })
    await askToDelete(panel)
    await button(panel, '.admin-modal', 'Delete').trigger('click')
    await flushPromises()
    expect(panel.page.find('.ticket-panel__delete [role="alert"]').exists()).toBe(true)

    api.fetchTicketDetail.mockResolvedValue(ticketWith({ id: 8, ticketNumber: 'SUP-2026-00008' }))
    await panel.wrapper.setProps({ ticketId: 8 })
    await flushPromises()

    expect(panel.page.get('h2').text()).toContain('SUP-2026-00008')
    expect(panel.page.find('.ticket-panel__delete [role="alert"]').exists()).toBe(false)
  })

  it('keeps it on "Keep it" and hands focus back to the Delete button', async () => {
    const panel = await openPanel(ticketWith(), { canDelete: true })
    await askToDelete(panel)

    await button(panel, '.admin-modal', 'Keep it').trigger('click')
    await flushPromises()

    expect(api.deleteTicket).not.toHaveBeenCalled()
    expect(document.activeElement).toBe(panel.page.get('.ticket-panel__delete-button').element)
  })

  it('deletes on "Delete" and tells the queue which ticket went', async () => {
    api.deleteTicket.mockResolvedValue(7)
    const panel = await openPanel(ticketWith(), { canDelete: true })
    await askToDelete(panel)

    await button(panel, '.admin-modal', 'Delete').trigger('click')
    await flushPromises()

    expect(api.deleteTicket).toHaveBeenCalledWith(7)
    expect(panel.wrapper.emitted('deleted')).toEqual([[7]])
    // The queue closes the panel and reloads on this one event.
    expect(panel.wrapper.emitted('changed')).toBeUndefined()
    // The ticket is gone, so reading it again would only fetch a 404.
    expect(api.fetchTicketDetail).toHaveBeenCalledTimes(1)
  })

  it('says what the server said, on top of saying nothing changed', async () => {
    // An admin whose admin access was taken away mid-session still has the
    // button, because canDelete came from the session loaded with the page.
    // "Nothing has changed" alone leaves them clicking it again.
    api.deleteTicket.mockRejectedValue(
      await serverError(403, {
        error: 'You do not have admin privileges.',
        code: 'permission_denied',
        request_id: 'c3fbf345963e'
      })
    )
    const panel = await openPanel(ticketWith(), { canDelete: true })
    await askToDelete(panel)
    await button(panel, '.admin-modal', 'Delete').trigger('click')
    await flushPromises()

    expect(panel.page.get('.ticket-panel__delete [role="alert"]').text()).toBe(
      'That did not delete. Nothing has changed. You do not have admin privileges.'
    )
    expect(panel.wrapper.emitted('deleted')).toBeUndefined()
  })

  it('says nothing more when the ticket was already deleted', async () => {
    // Two admins pressing Delete on the same ticket. The second gets the 404,
    // and its two words add nothing to the sentence already there.
    api.deleteTicket.mockRejectedValue(await ticketGone())
    const panel = await openPanel(ticketWith(), { canDelete: true })
    await askToDelete(panel)
    await button(panel, '.admin-modal', 'Delete').trigger('click')
    await flushPromises()

    expect(panel.page.get('.ticket-panel__delete [role="alert"]').text()).toBe(
      'That did not delete. Nothing has changed.'
    )
  })
})
