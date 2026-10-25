import { apiErrorFromResponse } from './apiError'
import { useAuthStore } from '@/stores/auth'
import { buildSessionHeaders, ensureCsrfCookie, resetCsrfToken } from './csrf'

// The one transport every ticket endpoint goes through: the requester's side
// (supportAPI.ts, /api/v1/tickets/) and the agent's side (ticketAgentAPI.ts,
// /api/v1/admin/tickets/). One guard, one test suite.
//
// The agent endpoints sit under the admin prefix, which makes adminAPI.ts's
// adminRequest look like the natural client for them. It is not. adminRequest
// has neither the stale-token retry nor the takeover check below. A reply sent
// through it on a rotated token fails instead of being sent again, and when
// the token went stale because somebody else signed in on the same browser,
// the agent gets a bare CSRF refusal instead of being told to sign in again.
// The guard has a known gap, accepted by the owner: see send.
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
 * that advice is wrong: a session that changed hands needs a reload and a
 * fresh sign-in, and pressing Send again is not the fix. After this refusal
 * it would not even be refused: the token fetched while checking belongs to
 * the new session (the accepted gap described at `send`). The requester pages
 * read `.message`, which is the same sentence it always was.
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

// Every ticket request goes out through here, and comes back only when the
// answer is a success. requestJson opens that answer as JSON and requestBlob
// reads it as a file. The rules for a write live here once, so a write whose
// answer is a file (the queue export) carries the same token and gets the
// same identity check as a reply does.
//
// `fallback` is the sentence a failure carries when the answer has none of
// its own. Anything the API itself says still comes through ahead of it.
//
// What the identity check does NOT catch, accepted as a known limitation
// (T01). The check only runs when the server refuses this tab's token as
// stale, which means somebody signed in after this tab got its token. It
// never runs when this tab got its token after somebody else signed in: that
// token is valid for the other person's session, so the write passes and is
// filed under their name. A tab whose session changed hands before its first
// write since the page loaded is therefore not caught, because csrf.ts keeps
// the token in module state and every page load starts with an empty cache
// (a cold cache). The same goes for the next write after a refusal below,
// which leaves the token it fetched for the new session in the cache, and for
// a token another module (adminAPI.ts, eventsAPI.ts and the rest) fetched
// into an empty cache after the takeover.
//
// A fix for this (asking /users/me/ before a write whose token this module
// had not confirmed yet) was written on 2026-09-29 and taken out again the
// same day. The owner ruled it out of scope as too edge-case: "不会出现这种问题
// 的，不用特意改，你把改的东西改回去吧，这种太边界了我们不用管" (this will not
// happen in practice, it does not need a special fix, change back what was
// changed; this is too much of an edge case for us to handle). Jinqi, 2026-09-29.
async function send(path: string, options: RequestInit, fallback: string): Promise<Response> {
  const method = String(options.method || 'GET').toUpperCase()
  const includeCSRF = !['GET', 'HEAD', 'OPTIONS'].includes(method)

  if (includeCSRF) {
    const csrfReady = await ensureCsrfCookie(API_BASE_URL)
    if (!csrfReady) {
      throw new TicketSessionError(
        'no-secure-session',
        'Could not initialize a secure session. Please refresh and try again.'
      )
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
        // Somebody else, or nobody can say: refused, never replayed.
        throw new TicketSessionError('signed-in-as-someone-else', SIGNED_IN_AS_SOMEONE_ELSE)
      }
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
 * CSRF token and gets the same stale-token guard. The queue export
 * (exportTickets in ticketAgentAPI.ts) is the write that comes through here.
 * It changes no ticket, but the export view writes an audit row naming
 * whoever owns the session, so the backend takes it as a POST and checks the
 * token. When that token went stale because somebody else signed in, the
 * export is refused and never replayed. It shares the known gap described at
 * send: a token fetched after the takeover is valid, and the export goes out
 * under the other person. Another site cannot start one, because it cannot
 * read the token.
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
