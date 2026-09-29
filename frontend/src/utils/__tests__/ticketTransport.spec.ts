import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest'
import { createPinia, setActivePinia } from 'pinia'

import { useAuthStore } from '@/stores/auth'
import { ApiError } from '@/utils/apiError'
import { getCSRFToken, resetCsrfToken } from '@/utils/csrf'
import {
  TicketSessionError,
  fetchBlob,
  filenameFromDisposition,
  requestBlob,
  requestJson,
  saveBlob,
  ticketFormData
} from '@/utils/ticketTransport'

/**
 * The ticket transport against a pretend backend, with the REAL csrf.ts.
 *
 * supportAPI.spec.ts stubs csrf.ts with an ensureCsrfCookie that never fetches
 * and never fills the cache. Here nothing in csrf.ts is replaced. The cache is
 * its real module state, and every case starts with it empty
 * (`resetCsrfToken()`), as a page that has just loaded does.
 *
 * The backend below models the two facts the stale-session guard is about,
 * and nothing else:
 *   - one cookie jar per browser, so a sign-in in any tab changes whose
 *     session every tab's next request carries;
 *   - login() rotates the CSRF secret, so a token fetched before a sign-in is
 *     refused after it, and /services/csrf/ hands out a token for whoever the
 *     jar belongs to at that moment.
 * A write is "filed" only if it reaches the server with the current token, and
 * it is filed under whoever owns the session then, which is what Django does.
 * The queue export is one of those writes: a POST that needs the token, whose
 * audit row names whoever owns the session, and whose answer is the file. A
 * GET to it is refused with a 405, as the export view refuses one.
 *
 * The guard only runs when the token a write carries is older than somebody
 * else's sign-in. A write whose token was fetched after that sign-in goes out
 * under the other person (T01). The owner ruled that out of scope on
 * 2026-09-29 (see send in ticketTransport.ts), so no case here covers it.
 *
 * Tokens are unique across the whole file, as Django's are (it masks the
 * secret afresh on every fetch).
 */
let backends = 0

const EXPORT_PATH = '/api/v1/admin/tickets/export/'

function fakeBackend() {
  backends += 1
  const instance = backends
  const server = {
    sessionUser: 7 as number | null,
    secret: 1,
    // Every request the server saw, in order: "METHOD /path".
    seen: [] as string[],
    // Writes the server accepted, and whose name they went under.
    filed: [] as Array<{ path: string; by: number | null }>,
    // /users/me/ failing for a reason of its own (a gateway in the way).
    meFailsWith: null as null | number,
    // /services/csrf/ down, so no token can be had.
    csrfDown: false,
    signIn(userId: number) {
      server.sessionUser = userId
      server.secret += 1
    },
    token() {
      return `secret-${instance}-${server.secret}`
    }
  }

  const json = (body: unknown, status = 200) =>
    new Response(JSON.stringify(body), {
      status,
      headers: { 'Content-Type': 'application/json' }
    })

  const fetchMock = vi.fn(async (input: RequestInfo | URL, init: RequestInit = {}) => {
    const url = new URL(String(input))
    const method = String(init.method ?? 'GET').toUpperCase()
    server.seen.push(`${method} ${url.pathname}`)

    if (url.pathname === '/services/csrf/') {
      if (server.csrfDown) return new Response('down', { status: 503 })
      return json({ csrfToken: server.token() })
    }
    if (url.pathname === '/api/v1/users/me/') {
      if (server.meFailsWith !== null) {
        return new Response('<html><body>Bad Gateway</body></html>', {
          status: server.meFailsWith
        })
      }
      if (server.sessionUser === null) {
        return json(
          { error: 'Authentication credentials were not provided.', code: 'not_authenticated' },
          403
        )
      }
      return json({ id: server.sessionUser, email: `user${server.sessionUser}@x.test` })
    }
    if (method === 'GET') {
      if (url.pathname === EXPORT_PATH) {
        return json({ error: 'Method "GET" not allowed.', code: 'method_not_allowed' }, 405)
      }
      return json({ msg: 'ok', data: { readAs: server.sessionUser } })
    }
    if (new Headers(init.headers).get('X-CSRFToken') !== server.token()) {
      return json({ error: 'CSRF Failed: CSRF token incorrect.', code: 'permission_denied' }, 403)
    }
    server.filed.push({ path: url.pathname, by: server.sessionUser })
    if (url.pathname === EXPORT_PATH) {
      // TicketQueueExportView: the audit row above, then the file.
      return new Response('PK', {
        status: 200,
        headers: { 'Content-Disposition': 'attachment; filename="tickets-2026-09-29.xlsx"' }
      })
    }
    return json({ msg: 'created', data: { filedUnder: server.sessionUser } }, 201)
  })

  return { server, fetchMock }
}

// The agent's reply, as the transport would be handed it by ticketAgentAPI.ts.
const REPLY_PATH = '/api/v1/admin/tickets/42/messages/'
function sendReply() {
  return requestJson<{ filedUnder: number }>(REPLY_PATH, {
    method: 'POST',
    body: ticketFormData({ messageType: 'support_reply', body: 'We have reset it.' })
  })
}

function signInThisTabAs(userId: number | null) {
  const auth = useAuthStore()
  auth.user =
    userId === null
      ? null
      : { id: userId, email: `user${userId}@x.test`, first_name: 'Tab', last_name: 'User' }
}

let backend: ReturnType<typeof fakeBackend>

beforeEach(() => {
  setActivePinia(createPinia())
  signInThisTabAs(7)
  backend = fakeBackend()
  vi.stubGlobal('fetch', backend.fetchMock)
  // Every case starts from a page that has just loaded: nothing cached.
  resetCsrfToken()
})

afterEach(() => {
  vi.unstubAllGlobals()
  resetCsrfToken()
})

describe('a write whose token went stale (the guard that predates the port)', () => {
  // This page has already written once since it loaded, so the cache holds a
  // token fetched before anything below happens. That first write is made for
  // real here; then the server's log is cleared.
  beforeEach(async () => {
    await sendReply()
    backend.server.seen = []
    backend.server.filed = []
  })

  it('goes straight out, with no identity check in front of it', async () => {
    const { server } = backend

    await expect(sendReply()).resolves.toEqual({ filedUnder: 7 })

    expect(server.seen).toEqual([`POST ${REPLY_PATH}`])
  })

  it('retries once when the same person signed in again elsewhere', async () => {
    // Rotated token, same owner: the retry is safe and is what saves the
    // reply the agent just typed.
    const { server } = backend
    server.signIn(7)

    await expect(sendReply()).resolves.toEqual({ filedUnder: 7 })

    expect(server.filed).toEqual([{ path: REPLY_PATH, by: 7 }])
    expect(server.seen).toEqual([
      `POST ${REPLY_PATH}`,
      'GET /services/csrf/',
      'GET /api/v1/users/me/',
      `POST ${REPLY_PATH}`
    ])

    // The fresh token stays in the cache, so the next write goes straight
    // out on it.
    server.seen = []
    await expect(sendReply()).resolves.toEqual({ filedUnder: 7 })
    expect(server.seen).toEqual([`POST ${REPLY_PATH}`])
  })

  it('refuses without asking when no fresh token can be had after a stale one', async () => {
    // Rotated token, and the token endpoint is down: there is nothing to
    // retry with, and nothing to ask about. Not sent again.
    const { server } = backend
    server.signIn(7)
    server.csrfDown = true

    const error = await sendReply().catch((caught: unknown) => caught)

    expect(error).toBeInstanceOf(TicketSessionError)
    expect(server.filed).toEqual([])
    expect(server.seen).toEqual([`POST ${REPLY_PATH}`, 'GET /services/csrf/'])
  })

  it('does not replay once somebody else owns the session', async () => {
    const { server } = backend
    server.signIn(99)

    const error = await sendReply().catch((caught: unknown) => caught)

    // The refusal the agent pages show their own sentence for, rather than
    // "try again". This branch is how a takeover is refused.
    expect(error).toBeInstanceOf(TicketSessionError)
    expect((error as TicketSessionError).reason).toBe('signed-in-as-someone-else')
    expect(server.filed).toEqual([])
    expect(server.seen).toEqual([
      `POST ${REPLY_PATH}`,
      'GET /services/csrf/',
      'GET /api/v1/users/me/'
    ])
  })

  it('says why it refused in a way the agent pages can tell from a fault', async () => {
    backend.server.signIn(99)

    const error = await sendReply().catch((caught: unknown) => caught)

    expect(error).toBeInstanceOf(TicketSessionError)
    expect((error as TicketSessionError).reason).toBe('signed-in-as-someone-else')
    // The requester's sentence, byte for byte what supportAPI.ts always threw.
    expect((error as Error).message).toBe(
      'You appear to be signed in as someone else now — this can happen if you ' +
        'signed in to another BIOTech page in the same browser. Please reload and sign in again.'
    )
  })

  it('refuses when /users/me/ answers with a failure instead of a person', async () => {
    // "Cannot confirm" is not "same person". A gateway error on the question
    // says nothing about whose session the fresh token belongs to, and the
    // session may well be somebody else's by now: sending again would be a
    // guess.
    const { server } = backend
    server.signIn(99)
    server.meFailsWith = 502

    const error = await sendReply().catch((caught: unknown) => caught)

    expect(error).toBeInstanceOf(TicketSessionError)
    expect((error as TicketSessionError).reason).toBe('signed-in-as-someone-else')
    expect(server.filed).toEqual([])
    expect(server.seen).toEqual([
      `POST ${REPLY_PATH}`,
      'GET /services/csrf/',
      'GET /api/v1/users/me/'
    ])
  })

  it('refuses when this tab does not know who it is', async () => {
    // Unknown identity is not a match, even when the session is in fact still
    // 7's. There is nobody to compare /users/me/ with, so it is not asked,
    // and nothing is sent again.
    const { server } = backend
    server.signIn(7)
    signInThisTabAs(null)

    const error = await sendReply().catch((caught: unknown) => caught)

    expect(error).toBeInstanceOf(TicketSessionError)
    expect((error as TicketSessionError).reason).toBe('signed-in-as-someone-else')
    expect(server.filed).toEqual([])
    expect(server.seen).toEqual([`POST ${REPLY_PATH}`, 'GET /services/csrf/'])
  })

  it('does not treat a 403 that is not about CSRF as a stale token', async () => {
    // A genuine refusal (an account without queue access) is the server's
    // answer to the person, not a token problem. No refetch, no retry, and the
    // server's own sentence comes through.
    const refusal = new Response(
      JSON.stringify({ error: 'You do not have support privileges.', code: 'permission_denied' }),
      { status: 403, headers: { 'Content-Type': 'application/json' } }
    )
    const fetchMock = vi.fn(async () => refusal)
    vi.stubGlobal('fetch', fetchMock)

    const error = await sendReply().catch((caught: unknown) => caught)

    expect(error).toBeInstanceOf(ApiError)
    expect((error as ApiError).status).toBe(403)
    expect((error as ApiError).message).toBe('You do not have support privileges.')
    expect(fetchMock).toHaveBeenCalledTimes(1)
  })
})

describe('reads', () => {
  it('never fetch a token or ask who is signed in', async () => {
    // GETs carry no CSRF token and are not guarded. That is unchanged: the
    // consequence the guard is about is a write filed under the wrong name.
    const { server } = backend

    await expect(requestJson('/api/v1/admin/tickets/summary/')).resolves.toEqual({ readAs: 7 })

    expect(server.seen).toEqual(['GET /api/v1/admin/tickets/summary/'])
    const headers = new Headers(backend.fetchMock.mock.calls[0][1]?.headers)
    expect(headers.get('X-CSRFToken')).toBeNull()
    expect(getCSRFToken()).toBeNull()
  })
})

describe('what every request carries and how failures read', () => {
  it('asks for JSON on reads and writes alike', async () => {
    // Without it DRF negotiates a browser's Accept header to the browsable-API
    // HTML page, and a refusal arrives as a document with nothing to read.
    await requestJson('/api/v1/admin/tickets/summary/')
    await sendReply()

    const acceptOf = (call: number) =>
      new Headers(backend.fetchMock.mock.calls[call][1]?.headers).get('Accept')
    // calls: summary, csrf (made by csrf.ts), the reply
    expect(acceptOf(0)).toBe('application/json')
    expect(acceptOf(2)).toBe('application/json')
  })

  it('sends the session cookie', async () => {
    await requestJson('/api/v1/admin/tickets/summary/')

    expect(backend.fetchMock.mock.calls[0][1]?.credentials).toBe('include')
  })

  it('reads a written sentence when the failure carries no message of its own', async () => {
    // A gateway timeout or Django's own error page: HTML, nothing to quote.
    vi.stubGlobal(
      'fetch',
      vi.fn(async () => new Response('<html><body>Bad Gateway</body></html>', { status: 502 }))
    )

    const error = await requestJson('/api/v1/admin/tickets/summary/').catch(
      (caught: unknown) => caught
    )

    expect(error).toBeInstanceOf(ApiError)
    expect((error as ApiError).status).toBe(502)
    expect((error as ApiError).message).toBe(
      'Something went wrong at our end. Please try again in a moment.'
    )
  })

  it('returns null for an answer with no body at all', async () => {
    vi.stubGlobal('fetch', vi.fn(async () => new Response(null, { status: 204 })))

    await expect(requestJson('/api/v1/admin/tickets/summary/')).resolves.toBeNull()
  })

  it('says the session could not be secured when no token can be had', async () => {
    const fetchMock = vi.fn(async () => new Response('down', { status: 503 }))
    vi.stubGlobal('fetch', fetchMock)

    const error = await sendReply().catch((caught: unknown) => caught)

    expect(error).toBeInstanceOf(TicketSessionError)
    expect((error as TicketSessionError).reason).toBe('no-secure-session')
    expect((error as Error).message).toBe(
      'Could not initialize a secure session. Please refresh and try again.'
    )
    // Only the token fetch: the write did not go out without a token.
    expect(fetchMock).toHaveBeenCalledTimes(1)
  })
})

describe('ticketFormData', () => {
  it('repeats files under one key, which is what request.FILES.getlist reads', () => {
    const form = ticketFormData({ body: 'See attached.' }, [
      new File(['a'], 'one.pdf', { type: 'application/pdf' }),
      new File(['b'], 'two.png', { type: 'image/png' })
    ])

    expect(form.get('body')).toBe('See attached.')
    expect(form.getAll('files').map((file) => (file as File).name)).toEqual(['one.pdf', 'two.png'])
    expect(form.has('files[0]')).toBe(false)
  })
})

describe('fetchBlob', () => {
  // A string body, not a Blob: in this jsdom setup `new Response(blob)`
  // stringifies the Blob to "[object Blob]", and the Blob that comes back has
  // no .text(), hence the FileReader below.
  const fileResponse = (headers: Record<string, string> = {}) =>
    new Response('PK', { status: 200, headers })

  const readText = (blob: Blob) =>
    new Promise<string>((resolve) => {
      const reader = new FileReader()
      reader.onload = () => resolve(String(reader.result))
      reader.readAsText(blob)
    })

  it('asks for JSON with the session cookie, so a refusal is data and not a page', async () => {
    const fetchMock = vi.fn(async () => fileResponse())
    vi.stubGlobal('fetch', fetchMock)

    await fetchBlob('/api/v1/admin/tickets/42/attachments/7/', 'We could not download that file.')

    const [url, init] = fetchMock.mock.calls[0] as unknown as [string, RequestInit]
    expect(url).toBe('http://localhost:8000/api/v1/admin/tickets/42/attachments/7/')
    expect(init.method).toBe('GET')
    expect(init.credentials).toBe('include')
    expect(new Headers(init.headers).get('Accept')).toBe('application/json')
    expect(new Headers(init.headers).get('X-CSRFToken')).toBeNull()
  })

  it('hands back the bytes and the name the server offered', async () => {
    vi.stubGlobal(
      'fetch',
      vi.fn(async () => fileResponse({ 'Content-Disposition': 'attachment; filename="error.png"' }))
    )

    const { blob, filename } = await fetchBlob('/api/v1/admin/tickets/42/attachments/7/', 'x')

    expect(await readText(blob)).toBe('PK')
    expect(filename).toBe('error.png')
  })

  it('offers no name when the server sent none', async () => {
    vi.stubGlobal('fetch', vi.fn(async () => fileResponse()))

    await expect(fetchBlob('/api/v1/admin/tickets/42/attachments/7/', 'x')).resolves.toMatchObject({
      filename: null
    })
  })

  it('throws the refusal with its status, and the caller\'s sentence when it carries none', async () => {
    vi.stubGlobal(
      'fetch',
      vi.fn(async () => new Response('<h1>Server Error</h1>', { status: 500 }))
    )

    const error = await fetchBlob('/x/', 'We could not download that file.').catch(
      (caught: unknown) => caught
    )

    expect(error).toBeInstanceOf(ApiError)
    expect((error as ApiError).status).toBe(500)
    expect((error as ApiError).message).toBe('We could not download that file.')
  })
})

describe('requestBlob: a write whose answer is a file (the queue export)', () => {
  // The export changes no ticket, but the server records it under whoever
  // owns the session, so it is a POST that needs the token. It goes through
  // the same path as a reply and gets the same stale-token guard. The page
  // loaded as 7.
  const EXPORT_BODY = '{"status":"open"}'

  function exportQueue() {
    return requestBlob(
      EXPORT_PATH,
      { method: 'POST', body: EXPORT_BODY },
      'Could not export the tickets. Please try again.'
    )
  }

  // The init the export itself went out with, the token fetch and the
  // identity check aside.
  function exportCalls() {
    return backend.fetchMock.mock.calls
      .filter(([input]) => new URL(String(input)).pathname === EXPORT_PATH)
      .map(([, init]) => init as RequestInit)
  }

  it('is sent exactly once, as a POST carrying the token, when it is still the same person', async () => {
    const { server } = backend

    const { blob, filename } = await exportQueue()

    expect(blob.size).toBe(2)
    expect(filename).toBe('tickets-2026-09-29.xlsx')
    expect(server.filed).toEqual([{ path: EXPORT_PATH, by: 7 }])
    expect(server.seen).toEqual(['GET /services/csrf/', `POST ${EXPORT_PATH}`])
    const [init] = exportCalls()
    expect(init.body).toBe(EXPORT_BODY)
    const headers = new Headers(init.headers)
    expect(headers.get('X-CSRFToken')).toBe(server.token())
    expect(headers.get('Content-Type')).toBe('application/json')
    expect(headers.get('Accept')).toBe('application/json')
    expect(init.credentials).toBe('include')
  })

  it('is refused, not replayed, once somebody else signed in since its token was fetched', async () => {
    // The page has written once, so its token is from before the takeover.
    // 99 signs in, which rotates it. The server refuses the POST as a stale
    // token, and the transport asks who is signed in and stops.
    const { server } = backend
    await sendReply()
    server.signIn(99)
    server.seen = []
    server.filed = []

    const error = await exportQueue().catch((caught: unknown) => caught)

    expect(error).toBeInstanceOf(TicketSessionError)
    expect((error as TicketSessionError).reason).toBe('signed-in-as-someone-else')
    // The same sentence a refused reply carries, so every page that already
    // words that refusal words this one too.
    expect((error as Error).message).toBe(
      'You appear to be signed in as someone else now — this can happen if you ' +
        'signed in to another BIOTech page in the same browser. Please reload and sign in again.'
    )
    expect(server.filed).toEqual([])
    expect(server.seen).toEqual([
      `POST ${EXPORT_PATH}`,
      'GET /services/csrf/',
      'GET /api/v1/users/me/'
    ])
  })

  it('is sent again, once, with its body, when the same person signed in again elsewhere', async () => {
    // A rotated token with the same owner: safe to retry, as for a reply.
    // The body is a string, so the retry carries the same filters.
    const { server } = backend
    await sendReply()
    server.signIn(7)
    server.seen = []
    server.filed = []

    const { filename } = await exportQueue()

    expect(filename).toBe('tickets-2026-09-29.xlsx')
    expect(server.filed).toEqual([{ path: EXPORT_PATH, by: 7 }])
    expect(server.seen).toEqual([
      `POST ${EXPORT_PATH}`,
      'GET /services/csrf/',
      'GET /api/v1/users/me/',
      `POST ${EXPORT_PATH}`
    ])
    expect(exportCalls().map((init) => init.body)).toEqual([EXPORT_BODY, EXPORT_BODY])
  })

  it("judges by this tab's own memory, not by what the other tab wrote to localStorage", async () => {
    // Signing in on the other tab writes the new person to localStorage,
    // which every tab shares. Compared with /users/me/, that would be 99
    // against 99, and the export would be sent again under 99.
    const { server } = backend
    await sendReply()
    server.signIn(99)
    server.filed = []
    localStorage.setItem('auth.user', JSON.stringify({ id: 99 }))

    try {
      const error = await exportQueue().catch((caught: unknown) => caught)

      expect(error).toBeInstanceOf(TicketSessionError)
      expect(server.filed).toEqual([])
    } finally {
      localStorage.removeItem('auth.user')
    }
  })

  it("reads a failure with no message of its own as the caller's sentence", async () => {
    // Sent, then the build fails with Django's own error page.
    vi.stubGlobal(
      'fetch',
      vi.fn(async (input: RequestInfo | URL) => {
        const path = new URL(String(input)).pathname
        if (path === '/services/csrf/') return new Response('{"csrfToken":"t-500"}')
        if (path === '/api/v1/users/me/') return new Response('{"id":7}')
        return new Response('<h1>Server Error</h1>', { status: 500 })
      })
    )

    const error = await exportQueue().catch((caught: unknown) => caught)

    expect(error).toBeInstanceOf(ApiError)
    expect((error as ApiError).status).toBe(500)
    expect((error as ApiError).message).toBe('Could not export the tickets. Please try again.')
  })

  it('is not asked for on a plain download, which the server does not record', async () => {
    // An attachment download changes nothing and writes no audit row, so it
    // stays a GET: no token, and nobody asked first, even on a session that
    // has changed hands.
    const { server } = backend
    server.signIn(99)

    await fetchBlob('/api/v1/admin/tickets/42/attachments/7/', 'Could not download that file.')

    expect(server.seen).toEqual(['GET /api/v1/admin/tickets/42/attachments/7/'])
    expect(getCSRFToken()).toBeNull()
  })
})

describe('filenameFromDisposition', () => {
  // Both forms django.utils.http.content_disposition_header writes.
  it('reads the quoted form Django uses for a plain ASCII name', () => {
    expect(filenameFromDisposition('attachment; filename="tickets-2026-09-29.xlsx"')).toBe(
      'tickets-2026-09-29.xlsx'
    )
  })

  it('undoes the escaping Django applies inside the quotes', () => {
    expect(filenameFromDisposition('attachment; filename="say \\"hi\\" \\\\ bye.xlsx"')).toBe(
      'say "hi" \\ bye.xlsx'
    )
  })

  it('decodes the percent-encoded form Django uses for anything else', () => {
    expect(
      filenameFromDisposition("attachment; filename*=utf-8''%E5%B7%A5%E5%8D%95%20%C3%A9.xlsx")
    ).toBe('工单 é.xlsx')
  })

  it('prefers the encoded form when both are present', () => {
    expect(
      filenameFromDisposition(
        "attachment; filename=\"fallback.xlsx\"; filename*=UTF-8''r%C3%A9sum%C3%A9.xlsx"
      )
    ).toBe('résumé.xlsx')
  })

  it('falls back to the plain form when the encoded one is malformed', () => {
    expect(
      filenameFromDisposition("attachment; filename=\"plain.xlsx\"; filename*=utf-8''%E0%A4%A.xlsx")
    ).toBe('plain.xlsx')
  })

  it('reads an unquoted name', () => {
    expect(filenameFromDisposition('attachment; filename=plain.xlsx')).toBe('plain.xlsx')
  })

  it('has nothing to offer without the header or without a name in it', () => {
    expect(filenameFromDisposition(null)).toBeNull()
    expect(filenameFromDisposition('')).toBeNull()
    expect(filenameFromDisposition('attachment')).toBeNull()
  })
})

describe('saveBlob', () => {
  let created: string[] = []
  let revoked: string[] = []
  let clicked: HTMLAnchorElement[] = []

  beforeEach(() => {
    created = []
    revoked = []
    clicked = []
    URL.createObjectURL = vi.fn(() => {
      const url = `blob:mock/${created.length}`
      created.push(url)
      return url
    }) as unknown as typeof URL.createObjectURL
    URL.revokeObjectURL = vi.fn((url: string) => {
      revoked.push(url)
    }) as unknown as typeof URL.revokeObjectURL
    vi.spyOn(HTMLAnchorElement.prototype, 'click').mockImplementation(function (
      this: HTMLAnchorElement
    ) {
      clicked.push(this)
    })
  })

  afterEach(() => {
    vi.restoreAllMocks()
  })

  it('downloads under the given name through a same-origin blob: URL and cleans up', () => {
    saveBlob(new Blob(['x']), 'tickets-2026-09-29.xlsx')

    expect(clicked).toHaveLength(1)
    expect(clicked[0].download).toBe('tickets-2026-09-29.xlsx')
    expect(clicked[0].getAttribute('href')).toBe('blob:mock/0')
    expect(revoked).toEqual(['blob:mock/0'])
    expect(document.querySelectorAll('a[download]')).toHaveLength(0)
  })
})
