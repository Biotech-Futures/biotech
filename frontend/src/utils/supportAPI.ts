import { apiErrorFromUnknown } from './apiError'
// The transport (CSRF, the stale-token retry and its takeover check, the
// {msg, data} unwrap, file downloads) lives in ticketTransport.ts, shared with
// the agent side's ticketAgentAPI.ts so both run the same guard.
import { API_BASE_URL, fetchBlob, requestJson, saveBlob, ticketFormData } from './ticketTransport'

// Kept in step with the backend's PUBLIC_TICKET_CATEGORIES, in the same order.
// The eight the requester can pick are spelled out rather than fetched,
// because the backend also carries a category it raises tickets under itself
// (flagged_content, written by message screening) and that must never appear
// in this dropdown.
//
// The list and its wording are the client's own, given 2026-09-04. "General
// Question" is title case while the rest are sentence case; that is how they
// wrote it. Do not tidy it here without telling them.
export const TICKET_CATEGORIES = [
  { value: 'account_access', label: 'Account and access' },
  { value: 'registration', label: 'Registration' },
  { value: 'help_student_group', label: 'Help with a student or group' },
  { value: 'help_mentor', label: 'Help with a mentor' },
  { value: 'technical_issue', label: 'Technical issue' },
  { value: 'certificates_records', label: 'Certificates and records' },
  { value: 'general_question', label: 'General Question' },
  { value: 'other', label: 'Other' }
] as const

export type TicketCategory = (typeof TICKET_CATEGORIES)[number]['value']

// How urgent the requester says it is. They pick it when they raise the
// enquiry and a support agent may change it afterwards (client, 2026-09-04).
//
// The wording asks about their situation and never names the level, and that
// is the whole design. The first version read "High - I am blocked right now",
// which keeps the level word in front of the explanation: the word is what a
// person answers, the explanation does not argue against choosing it, and a
// student who cannot submit their work honestly IS blocked right now. Picking
// the top of a scale costs nothing, so a scale with a visible top is a scale
// everything arrives at the top of.
//
// Removing the level words leaves three statements a person can only answer
// truthfully about themselves. The middle one is preselected, which is the
// strongest lever here, and the third is worded so that somebody who really
// is just reporting something has a sentence that fits them — the old
// "Low - no rush" was a label nobody would ever choose about their own
// problem, which made the scale effectively two-valued.
//
// Short enough to survive a phone, which the first two attempts at this were
// not. A closed <select> does not wrap: at 320px the control is 178.8px wide
// and has about 132px of drawable text in it, so "I need this sorted, but I
// can keep working" rendered as "I need this sorted, b" and the shorter "I can
// keep working for now" (180.8px) still rendered as "I can keep working f".
// The default is the one line every student who never opens the dropdown will
// read, so it is the line that must fit, and now it does: all three labels are
// under the budget with room to spare. The fuller wording lives under the
// control, where it can wrap (TicketForm.vue).
//
// The budget and the check on it live in
// components/support/__tests__/priorityLabelWidth.spec.ts.
//
// The stored values are unchanged, and the queue still says High/Normal/Low.
// The two vocabularies are deliberate: triage language belongs to the people
// doing triage.
export const TICKET_PRIORITIES = [
  { value: 'high', label: 'I cannot continue' },
  { value: 'normal', label: 'I can keep working' },
  { value: 'low', label: 'It can wait' }
] as const

export type TicketPriority = (typeof TICKET_PRIORITIES)[number]['value']
export type TicketStatus = 'open' | 'in_progress' | 'pending_user' | 'resolved'
export type TicketMessageType = 'user_message' | 'support_reply' | 'system'

export const MAX_BODY_LENGTH = 2000
export const MAX_ATTACHMENT_BYTES = 10 * 1024 * 1024
export const MAX_ATTACHMENTS = 5
export const ATTACHMENT_HINT = 'Max file size 10 MB (PDF, PNG, JPG, DOCX)'

export interface TicketAttachment {
  id: number
  filename: string
  mimeType: string
  size: number
}

export interface TicketMessage {
  id: number
  messageType: TicketMessageType
  body: string
  // A role, not a person: support replies come back as "Support".
  author: string | null
  createdAt: string
  attachments: TicketAttachment[]
}

export interface TicketRow {
  id: number
  ticketNumber: string
  subject: string
  category: TicketCategory
  status: TicketStatus
  priority: TicketPriority
  lastUpdated: string
}

export interface TicketDetail extends Omit<TicketRow, 'lastUpdated'> {
  body: string
  createdAt: string
  lastUpdated: string
  messages: TicketMessage[]
}

export interface PaginatedTickets {
  items: TicketRow[]
  total: number
  page: number
  limit: number
  hasMore: boolean
  // The two halves of one walk. `asOf` is the moment this walk is a picture of
  // — which enquiries are in it and in what order — and `after` is the place
  // the reader has reached, the sort key of the last row loaded. "Show more"
  // sends both back and gets the rows strictly after that place.
  //
  // Neither works alone, and the server enforces it: a cursor without its
  // snapshot is refused, a snapshot without a cursor is ignored. The list is
  // ordered by last update, so its order moves while somebody reads it, and
  // no offset is safe against that — an enquiry that gets a reply mid-walk
  // would land on no page at all.
  //
  // `after` is null on an empty page: nothing to continue from.
  asOf: string
  after: string | null
}

export interface SubmitTicketPayload {
  category: TicketCategory
  subject: string
  body: string
  priority: TicketPriority
  files?: File[]
}

export function fetchMyTickets(
  page = 1,
  limit = 10,
  walk?: { asOf: string; after: string },
) {
  const params = new URLSearchParams({ page: String(page), limit: String(limit) })
  // Both halves or neither — see PaginatedTickets.
  //
  // Encoded, not interpolated. An un-encoded "+" in a timestamp reaches the
  // server as a space, and both of these carry one.
  if (walk) {
    params.set('asOf', walk.asOf)
    params.set('after', walk.after)
  }
  return requestJson<PaginatedTickets>(`/api/v1/tickets/?${params.toString()}`)
}

export function fetchTicket(ticketId: number | string) {
  return requestJson<TicketDetail>(`/api/v1/tickets/${ticketId}/`)
}

export function submitTicket(payload: SubmitTicketPayload) {
  return requestJson<TicketDetail>('/api/v1/tickets/', {
    method: 'POST',
    body: ticketFormData(
      {
        category: payload.category,
        subject: payload.subject,
        body: payload.body,
        priority: payload.priority
      },
      payload.files
    )
  })
}

export function replyToTicket(ticketId: number | string, body: string, files: File[] = []) {
  return requestJson<TicketDetail>(`/api/v1/tickets/${ticketId}/messages/`, {
    method: 'POST',
    body: ticketFormData({ body }, files)
  })
}

function attachmentPath(ticketId: number | string, attachmentId: number | string) {
  return `/api/v1/tickets/${ticketId}/attachments/${attachmentId}/`
}

// The download endpoint's URL, the one the fetch below asks. Not for an href:
// see downloadTicketAttachment for why nothing points the browser at it.
export function attachmentUrl(ticketId: number | string, attachmentId: number | string) {
  return `${API_BASE_URL}${attachmentPath(ticketId, attachmentId)}`
}

// Fetched, not followed.
//
// A link click is a top-level navigation the browser commits to before it
// knows what is coming back. When the answer is a file the navigation is
// cancelled and the page stays, which is why an <a href> to this endpoint
// looked like it worked. When the answer is a 403 or a 404 it is an ordinary
// document and it REPLACES this one: the Support Centre is gone and the reply
// the student was half-way through typing goes with it, because that text only
// ever lived in the component. Their Back button does not rescue it either —
// the page rebuilds from scratch.
//
// None of the refusals are exotic. A support agent deleting the enquiry as a
// duplicate, a session that aged out (24 h from login, not from last activity),
// or a blob missing from the container all land here with a file still on
// screen and still clickable.
//
// Fetching leaves the page alone: the refusal becomes a value the caller can
// render beside the file. The bytes come back as a blob and go to disk through
// a blob: URL, which is same-origin and therefore honours `download` — the
// API's own URL never did, being cross-origin.
//
// The fetch itself, and its load-bearing Accept: application/json, is
// fetchBlob in ticketTransport.ts, shared with the agent side's download.
//
// The backend streams this endpoint rather than redirecting to a signed Azure
// URL (prefer_stream=True in apps/tickets/views.py) precisely so this fetch has
// one hop to make. Do not put that redirect back without giving the blob
// container a CORS rule for this origin first: a fetch re-applies CORS at the
// second hop and fails with a bare TypeError carrying no status at all.
export async function downloadTicketAttachment(
  ticketId: number | string,
  attachmentId: number | string,
  filename: string
) {
  const { blob } = await fetchBlob(
    attachmentPath(ticketId, attachmentId),
    'We could not download that file.'
  )
  // The name the timeline is already showing, not the one in
  // Content-Disposition. When this was written the header could not be read
  // cross-origin at all; settings.py now lists it in CORS_EXPOSE_HEADERS, but
  // it only repeats the stored original filename, and the name the student
  // clicked is already in hand and cannot disagree with what they saw.
  saveBlob(blob, filename)
}

// What to put in front of a student when the download is refused. The server's
// own sentences ("Attachment not found") describe a database row, not a
// situation, and neither of them was written for a fifteen-year-old.
export function attachmentErrorMessage(error: unknown): string {
  const status = apiErrorFromUnknown(error).status
  if (status === 401 || status === 403) {
    return 'Your sign-in has expired. Reload this page and sign in again to open this file.'
  }
  if (status === 404) {
    return 'That file is not available any more. Reload this page to see the latest version of this enquiry.'
  }
  return 'We could not download that file. Please check your connection and try again.'
}

// Categories a requester can be SHOWN but never OFFERED.
//
// Support can re-file a ticket into any category, screening's included, which
// is deliberate: a genuine child-safety report that came in through the form
// needs a way in, and a mis-screened one needs a way out. The moment they do,
// the requester's own ticket page renders a category that is not in the
// dropdown above — and without an entry here it printed the raw database key
// `flagged_content` at a fifteen-year-old.
//
// The wording is deliberately neither the queue's word for it ("Flagged
// content") nor anything with "reported" in it. Only two kinds of person ever
// see this label: someone whose own words genuinely need escalating, and
// someone a support agent mis-filed. "Reported" tells the first they have
// been informed on and tells the second something untrue. "Under review" is
// accurate for both and accuses nobody.
const EXTRA_CATEGORY_LABELS: Record<string, string> = {
  flagged_content: 'Under review'
}

export function categoryLabel(value: string): string {
  return (
    TICKET_CATEGORIES.find((c) => c.value === value)?.label ||
    EXTRA_CATEGORY_LABELS[value] ||
    value
  )
}

// The short form, for a badge beside a ticket. The long labels above explain
// the choice at the moment it is made; once it is made, the ticket only needs
// the word.
export function priorityLabel(value: TicketPriority | string): string {
  const labels: Record<string, string> = {
    high: 'High',
    normal: 'Normal',
    low: 'Low'
  }
  return labels[value] || value
}

export function statusLabel(value: TicketStatus | string): string {
  const labels: Record<string, string> = {
    open: 'Open',
    in_progress: 'In progress',
    pending_user: 'Pending user',
    resolved: 'Resolved'
  }
  return labels[value] || value
}
