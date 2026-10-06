import { DOMWrapper, flushPromises, mount, type VueWrapper } from '@vue/test-utils'
import { vi } from 'vitest'

import { ApiError, apiErrorFromResponse } from '@/utils/apiError'
import * as agentAPI from '@/utils/ticketAgentAPI'
import type {
  AssigneeOption,
  TicketDetail,
  TicketHistoryEntry,
  TicketMessage
} from '@/utils/ticketAgentSchema'
import { ticketDetailSchema } from '@/utils/ticketAgentSchema'

import TicketDetailPanel from '../TicketDetailPanel.vue'

// Shared by the detail panel's specs. The ticket is the real detail shape and
// goes through the real schema below, unlike the React fixture (TDP.test
// ticketWith), which used a `user` key, left out requester, body,
// firstResponseAt and resolvedAt, and bypassed the parse because the hook was
// stubbed.

export const OWNER: AssigneeOption = { id: 3, name: 'Gone Agent', assignable: false }
export const ACTIVE: AssigneeOption = { id: 1, name: 'Sam Reid', assignable: true }

export function ticketWith(overrides: Partial<TicketDetail> = {}): TicketDetail {
  return ticketDetailSchema.parse({
    id: 7,
    ticketNumber: 'SUP-2026-00007',
    subject: 'Cannot access group workspace',
    body: 'I cannot open my group.',
    category: 'help_student_group',
    status: 'in_progress',
    priority: 'normal',
    channel: 'portal',
    region: 'Australia',
    requester: {
      id: 9,
      name: 'Mia Thompson',
      email: 'mia@example.com',
      region: 'Australia',
      registeredAt: '2026-07-01T00:00:00Z'
    },
    assignee: null,
    createdAt: '2026-08-01T00:00:00Z',
    updatedAt: '2026-08-02T00:00:00Z',
    supportUpdatedAt: '2026-08-03T00:00:00Z',
    firstResponseAt: null,
    resolvedAt: null,
    overdue: false,
    messages: [],
    ...overrides
  })
}

export function messageWith(overrides: Partial<TicketMessage> = {}): TicketMessage {
  return {
    id: 1,
    messageType: 'user_message',
    body: 'I cannot open my group.',
    author: { id: 9, name: 'Mia Thompson' },
    createdAt: '2026-08-01T00:00:00Z',
    attachments: [],
    ...overrides
  }
}

export function historyEntry(overrides: Partial<TicketHistoryEntry> = {}): TicketHistoryEntry {
  return {
    id: 1,
    action: 'status',
    actor: { id: 4, name: 'Sam Reid' },
    beforeState: { status: 'open' },
    afterState: { status: 'in_progress' },
    createdAt: '2026-08-02T00:00:00Z',
    ...overrides
  }
}

/** A failure built the way the transport really builds one: a Response with
 *  the server's body, through apiErrorFromResponse. Two envelopes are in
 *  play and the difference is the point: anything raised comes back as
 *  `{error, code, request_id}`, while the views' own 404s are `{msg, data}`. */
export function serverError(status: number, body: Record<string, unknown>): Promise<ApiError> {
  return apiErrorFromResponse(
    new Response(JSON.stringify(body), {
      status,
      headers: { 'Content-Type': 'application/json' }
    }),
    'Something went wrong at our end. Please try again in a moment.'
  )
}

/** A 400 the backend wrote for a person: an attachment rule or a serializer. */
export function refusal(reason: string, code = 'invalid') {
  return serverError(400, { error: reason, code, request_id: '06cba68950f1' })
}

/** What every ticket admin view answers once the ticket is gone. */
export function ticketGone() {
  return serverError(404, { msg: 'Ticket not found', data: null })
}

// --- Mounting --------------------------------------------------------------

/** Every network call the panel makes. Each spec file mocks the module with
 *  exactly these seven (vi.mock is hoisted per file, so the list is written
 *  out in each) and keeps the rest real: ticketRefusalReason and
 *  attachmentErrorMessage stay real because a stub of them would be the
 *  sentences asserting themselves. */
export const api = {
  fetchTicketDetail: vi.mocked(agentAPI.fetchTicketDetail),
  fetchAssignees: vi.mocked(agentAPI.fetchAssignees),
  fetchTicketHistory: vi.mocked(agentAPI.fetchTicketHistory),
  updateTicket: vi.mocked(agentAPI.updateTicket),
  sendTicketMessage: vi.mocked(agentAPI.sendTicketMessage),
  deleteTicket: vi.mocked(agentAPI.deleteTicket),
  downloadTicketAttachment: vi.mocked(agentAPI.downloadTicketAttachment)
}

let mounted: VueWrapper | null = null
let host: HTMLElement | null = null

/** A node in the document for the panel to mount into. Attached, so focus
 *  and document-level key handling behave as they do in a browser. */
export function panelHost(): HTMLElement {
  if (!host) {
    host = document.createElement('div')
    document.body.appendChild(host)
  }
  return host
}

/** The queue's listeners, passed the way a parent template's @changed and
 *  @deleted arrive. `wrapper.emitted()` only records emits, and an emit is
 *  exactly what cannot reach the queue once the panel has closed, so the
 *  tests about that listen here instead. */
export type PanelListeners = {
  onClose?: () => void
  onChanged?: () => void
  onDeleted?: (id: number) => void
}

export type PanelOptions = {
  canDelete?: boolean
  /** What the assignee request does: a list comes back, or the promise to
   *  use (pending() for still loading, a rejection for failed). */
  roster?: AssigneeOption[] | Promise<AssigneeOption[]>
  listeners?: PanelListeners
}

export type Panel = {
  /** The component: props, emitted events, unmount. */
  wrapper: VueWrapper
  /** The document the panel teleports into. Everything on screen, the
   *  panel and its ConfirmDialog included, is found through this. */
  page: DOMWrapper<Element>
}

/** Mounts the panel with the real Teleport, so its content lands in
 *  document.body as it does in the app.
 *
 *  ⚠️ Not the `stubs: { teleport: true }` the Team 1 specs use. That stub
 *  re-creates the teleported children on every re-render of the panel
 *  (measured: the reply textarea was a new element after a click on the
 *  Details tab, and after a refused status change), so a typed draft was
 *  wiped by the TEST HARNESS, and a test of "the draft survives" could not
 *  tell the harness from the component. With the real Teleport the same
 *  element and the same draft survive. */
export function mountPanel(
  ticketId: number,
  canDelete = false,
  listeners: PanelListeners = {}
): Panel {
  mounted = mount(TicketDetailPanel, {
    props: { ticketId, canDelete, ...listeners },
    attachTo: panelHost()
  })
  return { wrapper: mounted, page: new DOMWrapper(document.body) }
}

/** Opens the panel on a ticket the way the queue does: mounted with an id,
 *  every request answered, then settled. */
export async function openPanel(ticket: TicketDetail, options: PanelOptions = {}): Promise<Panel> {
  api.fetchTicketDetail.mockResolvedValue(ticket)
  const roster = options.roster ?? [ACTIVE, OWNER]
  api.fetchAssignees.mockImplementation(() =>
    Array.isArray(roster) ? Promise.resolve(roster) : roster
  )
  const panel = mountPanel(ticket.id, options.canDelete ?? false, options.listeners)
  await flushPromises()
  return panel
}

/** What the queue does on @close: take the panel off the page. */
export function closeLikeTheQueue({ wrapper }: Panel) {
  wrapper.unmount()
  mounted = null
}

export function resetPanelTests() {
  // A test that closed the panel itself has unmounted it already.
  try {
    mounted?.unmount()
  } catch {
    // already gone
  }
  mounted = null
  host?.remove()
  host = null
  document.body.innerHTML = ''
  vi.resetAllMocks()
  api.fetchTicketHistory.mockResolvedValue([])
  api.downloadTicketAttachment.mockResolvedValue(undefined)
}

/** The text of the option a native select is showing. */
export function shownOption(select: { element: Element }): string {
  const element = select.element as HTMLSelectElement
  return element.options[element.selectedIndex]?.text ?? ''
}

export function optionTexts(select: { element: Element }): string[] {
  return Array.from((select.element as HTMLSelectElement).options).map((option) => option.text)
}

/** A promise that never settles: a request still in flight. */
export function pending<T>(): Promise<T> {
  return new Promise<T>(() => {})
}

/** A promise the test settles by hand. */
export function deferred<T>() {
  let resolve!: (value: T) => void
  let reject!: (reason: unknown) => void
  const promise = new Promise<T>((yes, no) => {
    resolve = yes
    reject = no
  })
  return { promise, resolve, reject }
}
