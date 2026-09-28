import { apiErrorFromResponse } from './apiError'
import { useAuthStore } from '@/stores/auth'
import { buildSessionHeaders, ensureCsrfCookie, resetCsrfToken } from './csrf'

const API_BASE_URL = import.meta.env.VITE_API_BASE_URL || 'http://localhost:8000'

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

// Every ticket endpoint answers {msg, data}. Callers only ever want `data`,
// so the envelope is opened here rather than at each call site.
interface Envelope<T> {
  msg: string
  data: T
}

// Django rotates the CSRF token on every login, and the token lives in a
// module-level cache (utils/csrf.ts) that nothing invalidates. So a cached
// token goes stale whenever a login happens after this module first read it —
// including a login in another tab, because both front ends talk to the same
// backend origin and therefore share one cookie jar.
function looksLikeStaleCsrf(status: number, body: string): boolean {
  return status === 403 && body.toLowerCase().includes('csrf')
}

// Whether the person the browser is signed in as is still the person this app
// thinks it is. A stale CSRF token has two very different causes and only one
// of them is safe to retry: the same user's token was rotated (retry), or
// somebody else signed in and took over the session (do not retry — the write
// would be filed under their name).
async function sessionStillBelongsTo(expectedUserId: number | null): Promise<boolean> {
  if (expectedUserId === null) return false
  try {
    const response = await fetch(`${API_BASE_URL}/api/v1/users/me/`, {
      credentials: 'include',
      headers: buildSessionHeaders()
    })
    if (!response.ok) return false
    const me = await response.json()
    return me?.id === expectedUserId
  } catch {
    return false
  }
}

// 🔴 Deliberately NOT localStorage.
//
// localStorage is shared by every tab on this origin and the login flow writes
// it (stores/auth.ts). So by the time a 403 comes back, localStorage may already
// name whoever just signed in somewhere else — and comparing that against
// /users/me/ would compare the new person with the new person, agree, and wave
// through the exact write this check exists to stop.
//
// The Pinia store lives in THIS tab's memory. Another tab signing in does not
// touch it, which is what makes it the right answer to "who does this page
// think it is".
function currentUserId(): number | null {
  try {
    return useAuthStore().user?.id ?? null
  } catch {
    // No active Pinia (unit tests, or a call before the app mounts). Unknown
    // identity is not the same as a matching one: the caller treats null as
    // "cannot confirm" and refuses to retry.
    return null
  }
}

async function sendOnce(path: string, options: RequestInit, includeCSRF: boolean) {
  const isFormData = options.body instanceof FormData
  return fetch(`${API_BASE_URL}${path}`, {
    credentials: 'include',
    ...options,
    headers: buildSessionHeaders({
      includeCSRF,
      isFormData,
      headers: {
        Accept: 'application/json',
        ...(options.headers || {})
      }
    })
  })
}

async function requestJson<T>(path: string, options: RequestInit = {}): Promise<T> {
  const method = String(options.method || 'GET').toUpperCase()
  const includeCSRF = !['GET', 'HEAD', 'OPTIONS'].includes(method)

  if (includeCSRF) {
    const csrfReady = await ensureCsrfCookie(API_BASE_URL)
    if (!csrfReady) {
      throw new Error('Could not initialize a secure session. Please refresh and try again.')
    }
  }

  // Captured before the request goes out, not after it comes back: the gap
  // between the two is exactly when somebody else's sign-in would land.
  const expected = includeCSRF ? currentUserId() : null

  let response = await sendOnce(path, options, includeCSRF)

  if (includeCSRF && response.status === 403) {
    // Read the body to tell a CSRF rejection from a genuine permission denial.
    // The response is consumed either way, so keep the text for the error.
    const body = await response.clone().text()
    if (looksLikeStaleCsrf(response.status, body)) {
      resetCsrfToken()
      const csrfReady = await ensureCsrfCookie(API_BASE_URL)
      if (csrfReady && (await sessionStillBelongsTo(expected))) {
        // Same person, rotated token: retry once with the fresh one. A body
        // that is a FormData or a string can be sent again as-is.
        response = await sendOnce(path, options, includeCSRF)
      } else {
        throw new Error(
          'You appear to be signed in as someone else now — this can happen if you ' +
            'signed in to another BIOTech page in the same browser. Please reload and sign in again.'
        )
      }
    }
  }

  if (!response.ok) {
    // The fallback is only reached when the answer carries no message of its
    // own, which is what a gateway timeout or Django's own error page looks
    // like: not JSON, nothing to quote. Without it the student reads
    // apiError.ts's placeholder, "Request failed: 502". Anything the API
    // itself says still comes through ahead of this sentence.
    throw await apiErrorFromResponse(
      response,
      'Something went wrong at our end. Please try again in a moment.'
    )
  }

  const text = await response.text()
  const payload = (text ? JSON.parse(text) : null) as Envelope<T> | null
  return (payload ? payload.data : null) as T
}

function ticketFormData(fields: Record<string, string>, files: File[] = []): FormData {
  const form = new FormData()
  Object.entries(fields).forEach(([key, value]) => form.set(key, value))
  // Repeated under one key: the backend reads request.FILES.getlist("files").
  files.forEach((file) => form.append('files', file))
  return form
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

// A plain URL rather than a fetch: the browser follows it with the session
// cookie attached, and the backend either streams the file or redirects to a
// signed one.
export function attachmentUrl(ticketId: number | string, attachmentId: number | string) {
  return `${API_BASE_URL}/api/v1/tickets/${ticketId}/attachments/${attachmentId}/`
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
