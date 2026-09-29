import { apiErrorFromResponse } from './apiError'
import { useAuthStore } from '@/stores/auth'
import { buildSessionHeaders, ensureCsrfCookie, getCSRFToken, resetCsrfToken } from './csrf'

// The one transport every ticket endpoint goes through: the requester's side
// (supportAPI.ts, /api/v1/tickets/) and the agent's side (ticketAgentAPI.ts,
// /api/v1/admin/tickets/). One guard, one test suite.
//
// The agent endpoints sit under the admin prefix, which makes adminAPI.ts's
// adminRequest look like the natural client for them. It is not. adminRequest
// has neither the stale-token retry nor the takeover check below, so a reply
// sent through it after somebody else signed in on the same browser goes out
// under their name, and on the agent side that name lands in the audit trail.
// adminAPI.ts and csrf.ts are platform code and stay as they are.
export const API_BASE_URL = import.meta.env.VITE_API_BASE_URL || 'http://localhost:8000'

// Every ticket endpoint answers {msg, data}. Callers only ever want `data`,
// so the envelope is opened here rather than at each call site.
interface Envelope<T> {
  msg: string
  data: T
}

/**
 * A request this transport would not send, or could not send safely, with a
 * sentence written for whoever is at the keyboard.
 *
 * Its own class so the agent pages can tell it from a fault. They answer a
 * fault with a standing sentence of their own ("try again"), and for these two
 * that advice is wrong: pressing Send again on a session that changed hands
 * gets refused again, every time. The requester pages read `.message`, which
 * is the same sentence it always was.
 *
 * `reason` says which of the two it is, so a page can word it its own way
 * without matching on the sentence. The agent side does: see
 * ticketAgentAPI.ts's sessionRefusal.
 */
export type TicketSessionRefusal = 'signed-in-as-someone-else' | 'no-secure-session'

export class TicketSessionError extends Error {
  readonly reason: TicketSessionRefusal

  constructor(reason: TicketSessionRefusal, message: string) {
    super(message)
    this.name = 'TicketSessionError'
    this.reason = reason
  }
}

// The requester's wording, unchanged since supportAPI.ts first shipped it.
const SIGNED_IN_AS_SOMEONE_ELSE =
  'You appear to be signed in as someone else now — this can happen if you ' +
  'signed in to another BIOTech page in the same browser. Please reload and sign in again.'

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
// would be filed under their name). It is also asked before a write goes out
// on a token this module has not checked yet: see send (T01).
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

// Refuse a write because the session is no longer this tab's person.
//
// The cache is emptied on the way out. What it holds now was fetched for the
// other person's session. Left in place it could not slip through (it has
// not been checked, so the next write here asks about it first), but the next
// attempt would ask about a token whose answer is already known. Emptied, the
// next attempt fetches a token for whoever owns the session by then and asks
// about that one.
function refuseChangedSession(): never {
  resetCsrfToken()
  throw new TicketSessionError('signed-in-as-someone-else', SIGNED_IN_AS_SOMEONE_ELSE)
}

// The last token /users/me/ vouched for: fetched, then found to belong to the
// session of the person this tab thinks it is. See send for why a write
// only goes out on this token. Only the token is kept, not whose it was: the
// session cannot change hands while the token still works, because changing
// hands means a sign-in, and a sign-in rotates the token.
let checkedToken: string | null = null

// Asks whether the session belongs to `expected`, and refuses the write if it
// does not (or if nobody can say). On a yes, `token`, which was fetched before
// the question was asked, is remembered as checked.
async function checkSessionFor(token: string, expected: number | null) {
  if (!(await sessionStillBelongsTo(expected))) {
    refuseChangedSession()
  }
  checkedToken = token
}

// `csrfToken` goes out as the write's X-CSRFToken: the token that was
// checked, not whatever the shared cache holds by the time the request
// leaves. Another module can empty and refill the cache while a write waits
// for /users/me/ to answer, and a token fetched then is not the one that was
// checked.
async function sendOnce(path: string, options: RequestInit, csrfToken: string | null) {
  const isFormData = options.body instanceof FormData
  const headers = buildSessionHeaders({
    isFormData,
    headers: {
      Accept: 'application/json',
      ...(options.headers || {})
    }
  })
  if (csrfToken !== null) headers.set('X-CSRFToken', csrfToken)
  return fetch(`${API_BASE_URL}${path}`, {
    credentials: 'include',
    ...options,
    headers
  })
}

// Every ticket request goes out through here, and comes back only when the
// answer is a success. requestJson opens that answer as JSON and requestBlob
// reads it as a file. The rules for a write live here once, so a write whose
// answer is a file (the queue export) carries the same token and gets the
// same identity check as a reply does.
//
// `fallback` is the sentence a failure carries when the answer has none of
// its own. Anything the API itself says still comes through ahead of it.
async function send(path: string, options: RequestInit, fallback: string): Promise<Response> {
  const method = String(options.method || 'GET').toUpperCase()
  const includeCSRF = !['GET', 'HEAD', 'OPTIONS'].includes(method)

  // Captured before the request goes out, not after it comes back: the gap
  // between the two is exactly when somebody else's sign-in would land. That
  // gap now starts before the token fetch below, which is a request too.
  const expected = includeCSRF ? currentUserId() : null

  // Reads carry no token.
  let token: string | null = null

  if (includeCSRF) {
    // T01. The identity check in the 403 branch below only runs when the
    // token this tab sends is older than somebody else's sign-in. A token
    // fetched AFTER that sign-in is valid for the other person's session: the
    // write passes and is filed under their name. That was reproduced end to
    // end with a real ticket filed under another student.
    //
    // Such a token reaches the cache two ways. This module fetches it into an
    // empty cache: every page load starts with one (csrf.ts keeps the token in
    // module state), and logout and this module's own refusals empty it. Or
    // some other module does: every other module that writes (adminAPI.ts on
    // any Team 1 admin page, eventsAPI.ts, gradingAPI.ts and the rest) fills
    // an empty cache for whoever owns the session at that moment and asks
    // nobody who that is, and adminAPI.ts's refreshCsrf empties the cache and
    // refills it in the same call. The cache cannot say who filled it. A first
    // version of this check only asked when the cache was empty, and let the
    // second kind through.
    //
    // So a write asks /users/me/ before it goes out whenever the token it is
    // about to send is not the one this module last checked. Every ordering
    // is then covered. A sign-in before the token was fetched, or between the
    // fetch and the check, is seen by the check. One after the check rotates
    // the token, so the write 403s and the branch below refuses it. And a
    // checked token stays safe for as long as the server accepts it: Django
    // rotates the token on every login, so a token that still works means
    // nobody has signed in since it was fetched, which was before the check.
    //
    // Two writes that start together on the same unchecked token each ask for
    // themselves, so the second cannot go out while the first is waiting.
    //
    // The cost is one GET per token new to this module: the first write after
    // each page load, after this tab signs in (the login response's token is
    // new here), and after another module fetches one.
    const csrfReady = await ensureCsrfCookie(API_BASE_URL)
    token = getCSRFToken()
    if (!csrfReady || token === null) {
      throw new TicketSessionError(
        'no-secure-session',
        'Could not initialize a secure session. Please refresh and try again.'
      )
    }
    if (token !== checkedToken) {
      await checkSessionFor(token, expected)
    }
  }

  let response = await sendOnce(path, options, token)

  if (token !== null && response.status === 403) {
    // Read the body to tell a CSRF rejection from a genuine permission denial.
    // The response is consumed either way, so keep the text for the error.
    const body = await response.clone().text()
    if (looksLikeStaleCsrf(response.status, body)) {
      resetCsrfToken()
      const csrfReady = await ensureCsrfCookie(API_BASE_URL)
      const fresh = getCSRFToken()
      if (!csrfReady || fresh === null) refuseChangedSession()
      // Same person, rotated token: retry once with the fresh one. A body
      // that is a FormData or a string can be sent again as-is. Somebody
      // else: refused, never replayed.
      await checkSessionFor(fresh, expected)
      response = await sendOnce(path, options, fresh)
    }
  }

  if (!response.ok) {
    throw await apiErrorFromResponse(response, fallback)
  }
  return response
}

export async function requestJson<T>(path: string, options: RequestInit = {}): Promise<T> {
  // The fallback is only reached when the answer carries no message of its
  // own, which is what a gateway timeout or Django's own error page looks
  // like: not JSON, nothing to quote. Without it the reader gets
  // apiError.ts's placeholder, "Request failed: 502".
  const response = await send(
    path,
    options,
    'Something went wrong at our end. Please try again in a moment.'
  )

  const text = await response.text()
  const payload = (text ? JSON.parse(text) : null) as Envelope<T> | null
  return (payload ? payload.data : null) as T
}

export function ticketFormData(fields: Record<string, string>, files: File[] = []): FormData {
  const form = new FormData()
  Object.entries(fields).forEach(([key, value]) => form.set(key, value))
  // Repeated under one key: the backend reads request.FILES.getlist("files").
  files.forEach((file) => form.append('files', file))
  return form
}

/**
 * A request whose answer is a file: sent the way requestJson sends it, then
 * read back as bytes, with the name the server offered.
 *
 * A write goes out under the same rules as a reply (see send). It carries a
 * CSRF token, and only a token this tab has confirmed is its own. The queue
 * export (exportTickets in ticketAgentAPI.ts) is the write that comes through
 * here. It changes no ticket, but the export view writes an audit row naming
 * whoever owns the session, so the backend takes it as a POST and checks the
 * token. On a session that changed hands it is refused before it is sent, or
 * the rotated token is refused by the server, and it is never replayed. And
 * another site cannot start one, because it cannot read the token.
 *
 * The request asks for JSON (sendOnce). That is load-bearing here too: the
 * backend declares no DEFAULT_RENDERER_CLASSES, so a refusal sent to a
 * browser's own Accept header comes back as DRF's browsable-API HTML page,
 * and the status is all this side could read.
 *
 * Never followed as a link: see downloadTicketAttachment in supportAPI.ts and
 * ticketAgentAPI.ts for what a followed link does to the page when the answer
 * is a refusal.
 */
export async function requestBlob(
  path: string,
  options: RequestInit,
  fallback: string
): Promise<{ blob: Blob; filename: string | null }> {
  const response = await send(path, options, fallback)
  const blob = await response.blob()
  return { blob, filename: filenameFromDisposition(response.headers.get('Content-Disposition')) }
}

/**
 * A file read with a plain GET: the attachment downloads on both sides.
 *
 * A read, so no token goes with it and nobody is asked who is signed in. The
 * download views change nothing and write no audit row, so a download on a
 * session that changed hands leaves no record under the wrong name. A request
 * the server records is a write and goes through requestBlob, as the queue
 * export does.
 */
export function fetchBlob(
  path: string,
  fallback: string
): Promise<{ blob: Blob; filename: string | null }> {
  return requestBlob(path, { method: 'GET' }, fallback)
}

/**
 * The file name a Content-Disposition header offers, or null.
 *
 * Readable cross-origin only because settings.py lists Content-Disposition in
 * CORS_EXPOSE_HEADERS; without that the header reads as null here and the
 * caller's own name is used.
 *
 * Both of the forms Django's content_disposition_header writes: a quoted
 * `filename="..."` (with `\"` and `\\` escaped) for a plain ASCII name, and
 * `filename*=utf-8''<percent-encoded>` for anything else. RFC 6266 says the
 * second wins when a server sends both.
 */
export function filenameFromDisposition(header: string | null): string | null {
  if (!header) return null

  const extended = /filename\*\s*=\s*[^']*'[^']*'([^;]+)/i.exec(header)
  if (extended) {
    try {
      const decoded = decodeURIComponent(extended[1].trim())
      if (decoded) return decoded
    } catch {
      // A malformed escape. Fall through to the plain form, if there is one.
    }
  }

  const quoted = /filename\s*=\s*"((?:\\.|[^"\\])*)"/i.exec(header)
  if (quoted) return quoted[1].replace(/\\(.)/g, '$1') || null

  const bare = /filename\s*=\s*([^;]+)/i.exec(header)
  return bare ? bare[1].trim() || null : null
}

// Hands a blob to the browser as a download. The blob: URL is same-origin and
// so honours `download`; the API's own URL never did, being cross-origin.
// Neither the object URL nor the anchor is left behind.
export function saveBlob(blob: Blob, filename: string): void {
  const objectUrl = URL.createObjectURL(blob)
  const link = document.createElement('a')
  link.href = objectUrl
  link.download = filename
  document.body.appendChild(link)
  link.click()
  link.remove()
  URL.revokeObjectURL(objectUrl)
}
