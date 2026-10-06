/**
 * The support agent's side of tickets: every endpoint under
 * /api/v1/admin/tickets/ that the React admin app called
 * (adminweb/src/query/ticket.ts), plus the queue export (client item C-09).
 *
 * Everything goes through ticketTransport.ts, never adminAPI.ts. These paths
 * sit under the admin prefix, so adminRequest would reach them, but it has
 * neither the stale-token retry nor the "is this still the same person" check,
 * and on this side a write that slips past that check is a reply, a status
 * change or an assignment recorded under another agent's name.
 *
 * What the React hooks did besides fetching, which the Vue pages now own
 * because there is no query cache here to do it for them:
 *   - The queue and the counters refetched on window focus: "An agent works
 *     with the queue open and comes back to it expecting to see what arrived
 *     while they were away", and "the counters sit above it and disagreeing
 *     with the rows underneath is worse than either being stale alone."
 *   - "Anything that changes a ticket invalidates the queue and the counters
 *     as well as the ticket itself: a status change moves it between counter
 *     cards and can move it in the sort order." After a delete, the ticket's
 *     own detail is NOT reloaded: it is gone, so that would only fetch a 404.
 *   - A roster grant or revoke made the assignee lists stale: "The assignee
 *     dropdowns are built from who can work the queue, so they go stale the
 *     moment the roster changes." In React that invalidation never reached a
 *     mounted query (T02), so fetch the assignees fresh whenever a panel
 *     opens rather than keeping a copy.
 */
import { z } from 'zod'

import { ApiError } from './apiError'
import {
  TicketSessionError,
  fetchBlob,
  requestBlob,
  requestJson,
  saveBlob,
  ticketFormData
} from './ticketTransport'
import {
  assigneeOptionSchema,
  bulkAssignResultSchema,
  regionOptionSchema,
  supportAgentSchema,
  ticketAnalyticsSchema,
  ticketAuditPageSchema,
  ticketDetailSchema,
  ticketHistoryEntrySchema,
  ticketQueueSchema,
  ticketSummarySchema,
  type AssigneeOption,
  type BulkAssignResult,
  type RegionOption,
  type SupportAgent,
  type TicketAnalytics,
  type TicketAuditPage,
  type TicketDetail,
  type TicketFilters,
  type TicketHistoryEntry,
  type TicketQueue,
  type TicketSummary
} from './ticketAgentSchema'

const BASE = '/api/v1/admin/tickets'

// The six the queue filters on, in one fixed order so a URL does not depend
// on the order somebody built the filter object in. The export sends exactly
// these and nothing else from the queue's state.
const FILTER_KEYS = ['region', 'status', 'category', 'assignee', 'priority', 'search'] as const

// The filters that are set, as [key, value] pairs in FILTER_KEYS order.
// Falsy means "no filter". The backend reads them the same way, so an empty
// select does not have to be special-cased on either side. The list puts
// these in its query string and the export in its body, both from here.
function activeFilters(filters: TicketFilters): Array<[string, string]> {
  return FILTER_KEYS.flatMap((key) => {
    const value = filters[key]
    return value ? [[key, value] as [string, string]] : []
  })
}

function appendFilters(params: URLSearchParams, filters: TicketFilters) {
  activeFilters(filters).forEach(([key, value]) => params.set(key, value))
  return params
}

function withQuery(path: string, params: URLSearchParams) {
  const query = params.toString()
  return query ? `${path}?${query}` : path
}

// --- The queue --------------------------------------------------------------

export type QueueWalk = { asOf: string; after: string }

export async function fetchTicketQueue(
  page: number,
  limit: number,
  filters: TicketFilters = {},
  walk?: QueueWalk
): Promise<TicketQueue> {
  const params = new URLSearchParams({ page: String(page), limit: String(limit) })
  appendFilters(params, filters)
  // Both halves or neither. A cursor without its snapshot is refused with a
  // 400, and a snapshot without a cursor is ignored: the server will not page
  // by offset inside a frozen set, because a frozen set can still shrink and
  // that is the defect the cursor exists to close.
  //
  // URLSearchParams percent-encodes on toString(), which matters here more
  // than anywhere else on this page: an un-encoded "+" in a timestamp arrives
  // as a space and the server cannot read it. Both values carry timestamps.
  if (walk) {
    params.set('asOf', walk.asOf)
    params.set('after', walk.after)
  }
  return ticketQueueSchema.parse(await requestJson<unknown>(withQuery(`${BASE}/`, params)))
}

export async function fetchTicketSummary(): Promise<TicketSummary> {
  return ticketSummarySchema.parse(await requestJson<unknown>(`${BASE}/summary/`))
}

// Everybody who could own a ticket, deactivated and revoked agents included.
// Use every row for the assignee FILTER and only `assignable` rows for anything
// that hands work to somebody (see assigneeOptionSchema).
export async function fetchAssignees(): Promise<AssigneeOption[]> {
  return z.array(assigneeOptionSchema).parse(await requestJson<unknown>(`${BASE}/assignees/`))
}

export async function fetchTicketRegions(): Promise<RegionOption[]> {
  return z.array(regionOptionSchema).parse(await requestJson<unknown>(`${BASE}/regions/`))
}

export async function bulkAssignTickets(
  ticketIds: number[],
  // null hands the whole batch back to the pool, the same way the
  // single-ticket PATCH below does it. The serializer takes null and refuses
  // the key being absent, so it is null or a primary key here and never
  // undefined.
  assigneeId: number | null
): Promise<BulkAssignResult> {
  const data = await requestJson<unknown>(`${BASE}/bulk-assign/`, {
    method: 'POST',
    body: JSON.stringify({ ticketIds, assigneeId })
  })
  // Per-ticket results: one bad id does not undo the rest of the batch, so the
  // caller has to be able to report which ones failed. `ticketId` is the
  // database id; nothing on the screen prints those, so map it back to the
  // ticket number from the rows that were selected.
  return bulkAssignResultSchema.parse(data)
}

/**
 * The queue as an Excel file (client item C-09): every row the current
 * filters match, not just the page on screen.
 *
 * The same six filters as the list and nothing else. No page, limit, asOf or
 * after: an export is a fresh look at everything that matches now, and an old
 * walk's asOf would drop every ticket worked since it was taken.
 *
 * The filename is the server's when Content-Disposition names one (settings.py
 * exposes that header cross-origin), otherwise tickets-YYYY-MM-DD.xlsx on the
 * reader's own calendar. The caller saves it with saveTicketExport.
 *
 * A POST with the filters as a JSON body, though it changes no ticket. The
 * export view writes an audit row under whoever owns the session, so the
 * backend takes it as a write and checks its CSRF token. Here it goes out
 * through the transport's write path (requestBlob in ticketTransport.ts),
 * with the token and the same "is this still the same person" check a reply
 * gets. When its token went stale because the session now belongs to
 * somebody else, it is refused with the same TicketSessionError, and
 * ticketRefusalReason already turns that into the sentence the queue page
 * shows. The check has the known gap described at send in ticketTransport.ts.
 */
export async function exportTickets(
  filters: TicketFilters = {}
): Promise<{ blob: Blob; filename: string }> {
  const { blob, filename } = await requestBlob(
    `${BASE}/export/`,
    { method: 'POST', body: JSON.stringify(Object.fromEntries(activeFilters(filters))) },
    'Could not export the tickets. Please try again.'
  )
  return { blob, filename: filename ?? `tickets-${localDateStamp(new Date())}.xlsx` }
}

export function saveTicketExport(file: { blob: Blob; filename: string }) {
  saveBlob(file.blob, file.filename)
}

function localDateStamp(date: Date) {
  const pad = (n: number) => String(n).padStart(2, '0')
  return `${date.getFullYear()}-${pad(date.getMonth() + 1)}-${pad(date.getDate())}`
}

// --- One ticket -------------------------------------------------------------

export async function fetchTicketDetail(id: number): Promise<TicketDetail> {
  return ticketDetailSchema.parse(await requestJson<unknown>(`${BASE}/${id}/`))
}

// Oldest first. 404 once the ticket is deleted; the audit list still has it.
export async function fetchTicketHistory(id: number): Promise<TicketHistoryEntry[]> {
  return z
    .array(ticketHistoryEntrySchema)
    .parse(await requestJson<unknown>(`${BASE}/${id}/history/`))
}

export type TicketPatch = {
  status?: string
  priority?: string
  // Re-filing a mis-categorised ticket. Like priority, it is a triage field:
  // the backend audits the change and deliberately writes no timeline message,
  // so the requester's list does not reorder and no email goes out.
  category?: string
  // null hands the ticket back to the pool. JSON.stringify keeps a null, so it
  // arrives as null rather than being dropped from the body; a key left
  // undefined is dropped, which is what "not changing this" should look like.
  assignee?: number | null
}

// status and assignee are mutually exclusive — the backend answers 400 if both
// arrive together, because each one drives a different transition and any
// implied ordering produces a wrong end state.
export async function updateTicket(id: number, patch: TicketPatch): Promise<TicketDetail> {
  const data = await requestJson<unknown>(`${BASE}/${id}/`, {
    method: 'PATCH',
    body: JSON.stringify(patch)
  })
  return ticketDetailSchema.parse(data)
}

export type TicketMessageInput = {
  messageType: 'support_reply' | 'internal_note'
  body: string
  files?: File[]
  // "Reply and wait for their reply": ONE request, so the email the requester
  // gets knows it is asking them something. Sending the reply and the status
  // change separately makes the email pick the wrong branch. The backend
  // refuses it on an internal note, which the requester never sees.
  moveToPending?: boolean
}

// A reply and an internal note are the same endpoint; messageType decides.
export async function sendTicketMessage(
  id: number,
  { messageType, body, files, moveToPending }: TicketMessageInput
): Promise<TicketDetail> {
  const fields: Record<string, string> = { messageType, body }
  // Only sent when ticked. FormData carries strings, so an unticked box would
  // otherwise post "false" — which the serializer does read correctly, but
  // leaving the key out keeps the request identical to what it was before
  // this option existed.
  if (moveToPending) fields.moveToPending = 'true'
  const data = await requestJson<unknown>(`${BASE}/${id}/messages/`, {
    method: 'POST',
    body: ticketFormData(fields, files ?? [])
  })
  return ticketDetailSchema.parse(data)
}

// Admin only on the server (IsAdminScoped): gate the control on
// auth.isTicketAdmin so a support agent never sees a button that would 403.
// A second delete, or losing the race to a colleague, answers 404.
export async function deleteTicket(id: number): Promise<number> {
  await requestJson<unknown>(`${BASE}/${id}/delete/`, { method: 'DELETE' })
  return id
}

/** Fetch the file rather than pointing the browser at it.
 *
 *  The panel used to render an `<a href>` straight at this endpoint. Two
 *  things were wrong with that. With `target="_blank"` WebKit opens a tab per
 *  click and closes none of them, so three downloads leave three tabs behind.
 *  Without the target, a click is a top-level navigation the browser commits
 *  to before it knows the answer, so any refusal — the ticket deleted from the
 *  button two inches away on this same panel, a session that aged out, a blob
 *  missing from the container — replaces the whole page with DRF's
 *  browsable-API error page and takes the reply being typed with it.
 *
 *  Fetching leaves the page alone: the refusal is a value the panel renders.
 *  The bytes go to disk through a blob: URL (saveBlob in ticketTransport.ts).
 *
 *  The backend streams this endpoint rather than redirecting to a signed Azure
 *  URL (`prefer_stream=True` in apps/tickets/views_admin.py) so that this
 *  request has one hop to make. Do not put the redirect back without giving
 *  the blob container a CORS rule for this origin first: a fetch re-applies
 *  CORS at the second hop and fails with a bare network error carrying no
 *  status.
 *
 *  Internal-note attachments are served here too; that is why this is the
 *  admin endpoint and never the requester's.
 *
 *  A plain read, unlike exportTickets, which is a write. The download view
 *  changes nothing and writes no audit row, so a download on a session that
 *  changed hands leaves no record under the wrong name.
 */
export async function downloadTicketAttachment(
  ticketId: number,
  attachmentId: number,
  filename: string
) {
  const { blob } = await fetchBlob(
    `${BASE}/${ticketId}/attachments/${attachmentId}/`,
    'Could not download that file. Try again.'
  )
  // The name the panel is already showing, the one the agent clicked.
  saveBlob(blob, filename)
}

/** What to put in front of an agent when the download is refused.
 *
 *  Keyed on the status alone, as the React version was. The detail panel
 *  reads the body's code first (components/admin/tickets/detail/
 *  ticketDetailText.ts) so a 403 for an agent whose queue access was just
 *  revoked does not read as an expired session; this is its fallback.
 *
 *  The 404 sentence covers two causes on purpose. Since T15 the download
 *  view opens the stored file before answering, and a file missing from
 *  storage comes back as the same {msg: "Attachment not found"} 404 as a
 *  deleted ticket or message, so the client cannot tell them apart. React's
 *  "the ticket ... was deleted" was true only for the first. */
export function attachmentErrorMessage(error: unknown): string {
  const status = error instanceof ApiError ? error.status : undefined
  if (status === 401 || status === 403) {
    return 'Your session has expired. Reload this page and sign in again to open this file.'
  }
  if (status === 404) {
    return 'This file could not be found. Its ticket or message may have been deleted, or the file is missing from storage. Reload the queue to check.'
  }
  return 'Could not download that file. Try again.'
}

// --- Audit and analytics ----------------------------------------------------

export type TicketAuditFilters = { action?: string; actor?: string }

// Plain offset paging, newest first. Unlike the queue there is no snapshot,
// so rows can repeat across pages when events arrive in between (T21).
export async function fetchTicketAudit(
  page: number,
  limit: number,
  filters: TicketAuditFilters = {}
): Promise<TicketAuditPage> {
  const params = new URLSearchParams({ page: String(page), limit: String(limit) })
  if (filters.action) params.set('action', filters.action)
  if (filters.actor) params.set('actor', filters.actor)
  return ticketAuditPageSchema.parse(await requestJson<unknown>(withQuery(`${BASE}/audit/`, params)))
}

export type AnalyticsParams = { from?: string; to?: string; dimension?: string }

// `to` is sent exactly as picked, as YYYY-MM-DD. The server alone makes a bare
// date inclusive by adding a day ("This is the only place that may make this
// correction"); adding it here as well would count a day twice.
export async function fetchTicketAnalytics(params: AnalyticsParams = {}): Promise<TicketAnalytics> {
  const search = new URLSearchParams()
  if (params.from) search.set('from', params.from)
  if (params.to) search.set('to', params.to)
  if (params.dimension) search.set('dimension', params.dimension)
  return ticketAnalyticsSchema.parse(
    await requestJson<unknown>(withQuery(`${BASE}/analytics/`, search))
  )
}

// --- The support roster. Admin-only on the server; the screen is admin-only
// --- too, so a support agent never sees a control that would 403.

const ROSTER = `${BASE}/support-scope/`

export async function fetchSupportRoster(): Promise<SupportAgent[]> {
  return z.array(supportAgentSchema).parse(await requestJson<unknown>(ROSTER))
}

// 201 when the row was created, 200 when the person already had access; the
// screen treats both as done. A refusal (a student, a switched-off account)
// is a 400 whose sentence is in `msg`: read it with serverMessage.
export async function grantSupport(userId: number): Promise<void> {
  await requestJson<unknown>(ROSTER, { method: 'POST', body: JSON.stringify({ userId }) })
}

// Does not hand the person's open tickets to anybody: they stay in their name.
export async function revokeSupport(userId: number): Promise<void> {
  await requestJson<unknown>(`${ROSTER}${userId}/`, { method: 'DELETE' })
}

// --- Reading a refusal ------------------------------------------------------

/** Codes marking a refusal somebody on this project wrote for a person.
 *
 *  config/exception_handler.py copies the code off whichever exception was
 *  raised. `invalid` is a ValidationError, which is how the attachment rules
 *  and both admin serializers refuse. `permission_denied` is the sentence in
 *  the ticket permission classes: "You do not have support privileges.",
 *  "You do not have admin privileges." `does_not_exist` is a rejected
 *  assignee: both fields that can raise it (serializers_admin.py, the PATCH's
 *  `assignee` and bulk-assign's `assigneeId`) override DRF's `Invalid pk "18"
 *  - object does not exist.` with NOT_ASSIGNABLE, "Cannot assign to user
 *  "18". They need an active account with support queue access." The React
 *  list left this code out (T03) and answered that sentence with "close the
 *  panel and reopen it", which is not what is wrong.
 *
 *  Every other code on this path carries DRF's own default English, written
 *  for whoever wrote the request rather than for an agent: a rejected enum is
 *  `"nope" is not a valid choice.`, an unhandled fault is "Internal server
 *  error". None of those tell an agent anything they can do, and the standing
 *  sentence at each call site does.
 *
 *  Add a code here when the backend starts answering it with a sentence
 *  meant to be read.
 */
const WRITTEN_FOR_A_PERSON = ['invalid', 'permission_denied', 'does_not_exist']

// The transport's own refusals, as an agent page shows them. The takeover
// sentence is the requester's words split into sentences: the requester pages
// still show their older copy with a dash in it, and the port's rule for new
// screens is no dashes in UI strings.
const AGENT_SIGNED_IN_AS_SOMEONE_ELSE =
  'You appear to be signed in as someone else now. This can happen if you signed in to ' +
  'another BIOTech page in the same browser. Please reload and sign in again.'

function sessionRefusal(error: TicketSessionError): string {
  return error.reason === 'signed-in-as-someone-else'
    ? AGENT_SIGNED_IN_AS_SOMEONE_ELSE
    : error.message
}

/** The server's own reason for refusing a ticket write, when it gave one.
 *
 *  Two error envelopes are in play. Anything raised under /admin/tickets/
 *  goes through config/exception_handler.py and comes back as
 *  `{error, code, request_id}`, which is what this reads.
 *
 *  The 404s never raise. views_admin.py's _not_found answers `{msg, data}`
 *  directly, the older admin shape serverMessage below reads, and its "Ticket
 *  not found" is deliberately not picked up here (apiError.ts gives a body
 *  with no code the code `http_404`, which is not on the list). That 404 is
 *  the commonest failure on this path, because it is what a colleague
 *  deleting the ticket looks like, and every caller already answers it with
 *  a longer sentence that says what to do next.
 *
 *  Worth reading, because the commonest refusals that do raise are ones the
 *  agent can act on: "Attachment exceeds the maximum allowed size of 10 MB.",
 *  "Attach at most 5 files to one message." Answering those with "try again"
 *  sends the agent round a loop that ends the same way every time.
 *
 *  The transport's own refusals come through too (TicketSessionError: the
 *  session now belongs to somebody else, or no secure session could be set
 *  up). In React those surfaced as the bare CSRF 403 and got the standing
 *  sentence. "Try again" is the wrong advice for them: what fixes it is a
 *  reload and a fresh sign-in, and a second press would go out on the new
 *  session's token (the accepted gap described in ticketTransport.ts).
 */
export function ticketRefusalReason(error: unknown): string | undefined {
  if (error instanceof TicketSessionError) return sessionRefusal(error)
  if (!(error instanceof ApiError)) return undefined
  if (!WRITTEN_FOR_A_PERSON.includes(error.code)) return undefined
  const reason = typeof error.body.error === 'string' ? error.body.error.trim() : ''
  // A stale CSRF token arrives as permission_denied as well, worded
  // "CSRF Failed: CSRF cookie not set." That is DRF talking about the request
  // machinery, not about this person's access. ticketTransport.ts retries
  // that once with a fresh token (after checking the session is still this
  // person's), so anything reaching here has already failed twice and the
  // words help nobody.
  if (reason === '' || /^csrf/i.test(reason)) return undefined
  return reason
}

/** The server's own explanation of a refusal on the roster, when it gave one.
 *
 *  The roster endpoints answer `{msg, data}` and return 400 with a useful
 *  `msg` when they decline a write: "Students cannot be given support queue
 *  access. Change their role first if this is not a student account." A
 *  caller that falls back to a generic string shows the generic string for
 *  every one of those, and the admin presses Grant again on a row the server
 *  has already explained. serverMessage and not ticketRefusalReason: these
 *  endpoints answer the msg/data envelope directly rather than raising, so the
 *  reason is in msg and not in the error/code shape the ticket write path
 *  uses. The transport's own refusals (TicketSessionError) come through for
 *  the same reason as there.
 */
export function serverMessage(error: unknown): string | undefined {
  if (error instanceof TicketSessionError) return sessionRefusal(error)
  if (!(error instanceof ApiError)) return undefined
  const msg = error.body.msg
  return typeof msg === 'string' && msg.trim() !== '' ? msg : undefined
}

/** Whether a failed read was a refusal rather than a fault.
 *
 *  Reporting a 403 as "could not be loaded" tells the reader the product is
 *  broken when it is working exactly as intended. Signed out is a 403 here
 *  too, not a 401 (SessionAuthentication sends no WWW-Authenticate), and the
 *  body's code is what tells the two apart. A signed-out agent is not being
 *  refused anything: telling them "You do not have access" sends them to an
 *  administrator for a problem a reload and sign-in fixes, so
 *  `not_authenticated` falls through to the page's "could not be loaded"
 *  sentence instead.
 */
export function wasRefused(error: unknown): boolean {
  return error instanceof ApiError && error.status === 403 && error.code !== 'not_authenticated'
}
