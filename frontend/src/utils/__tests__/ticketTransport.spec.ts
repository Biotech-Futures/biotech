import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest'
import { createPinia, setActivePinia } from 'pinia'

import { useAuthStore } from '@/stores/auth'
import { adminPost } from '@/utils/adminAPI'
import { ApiError } from '@/utils/apiError'
import { getCSRFToken, resetCsrfToken, setCsrfToken } from '@/utils/csrf'
import { setEventRsvp } from '@/utils/eventsAPI'
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
 * and never fills the cache, so every case there is a warm cache. That is why
 * the takeover guard passed all its tests while T01 was open: the defect is a
 * token fetched after somebody else signed in, and a stub that never fetches
 * cannot hand one out. Here nothing in csrf.ts is replaced. The cache is its real module state, a
 * cold cache is `resetCsrfToken()`, and a warm one is `setCsrfToken(...)`, the
 * same call the login flow makes (stores/auth.ts).
 *
 * The backend below models the two facts T01 is made of, and nothing else:
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
 * Tokens are unique across the whole file, as Django's are (it masks the
 * secret afresh on every fetch). The transport keeps track of which token it
 * has checked, and a later case must not inherit an earlier case's check by
 * being handed the same string.
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
    // "Somebody signs in right after the server answered this", once.
    afterCsrf: null as null | (() => void),
    afterMe: null as null | (() => void),
    // /users/me/ failing for a reason of its own (a gateway in the way).
    meFailsWith: null as null | number,
    // /services/csrf/ down, so no token can be had.
    csrfDown: false,
    // While set, /users/me/ holds its answer until the promise settles: a
    // slow answer, so a second write can start while the first one waits.
    meHeldUntil: null as null | Promise<void>,
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
      const answer = json({ csrfToken: server.token() })
      const hook = server.afterCsrf
      server.afterCsrf = null
      hook?.()
      return answer
    }
    if (url.pathname === '/api/v1/users/me/') {
      if (server.meFailsWith !== null) {
        return new Response('<html><body>Bad Gateway</body></html>', {
          status: server.meFailsWith
        })
      }
      if (server.meHeldUntil) await server.meHeldUntil
      if (server.sessionUser === null) {
        return json(
          { error: 'Authentication credentials were not provided.', code: 'not_authenticated' },
          403
        )
      }
      const answer = json({ id: server.sessionUser, email: `user${server.sessionUser}@x.test` })
      const hook = server.afterMe
      server.afterMe = null
      hook?.()
      return answer
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

// Lets pending fetches and their continuations run until `done` holds.
async function until(done: () => boolean) {
  for (let turn = 0; turn < 50 && !done(); turn += 1) {
    await new Promise((resolve) => setTimeout(resolve, 0))
  }
  expect(done()).toBe(true)
}

// How a write ended, in words a test can compare.
function outcome(write: Promise<unknown>): Promise<string> {
  return write.then(
    () => 'sent',
    (error: unknown) => (error instanceof TicketSessionError ? 'refused' : `failed: ${error}`)
  )
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

describe('the first write after the page loaded (a cold cache, T01)', () => {
  it('is never sent once /users/me/ says somebody else owns the session', async () => {
    // The page loaded as 7. Then somebody signed in as 99 in another tab of
    // the same browser, and nobody reloaded this one. Before the fix the token
    // fetch handed this tab 99's valid token and the reply was filed as 99's.
    const { server } = backend
    server.signIn(99)

    await expect(sendReply()).rejects.toThrow(/signed in as someone else/i)

    expect(server.filed).toEqual([])
    // The write itself never left the browser.
    expect(server.seen).toEqual(['GET /services/csrf/', 'GET /api/v1/users/me/'])
  })

  it('is sent exactly once when it is still the same person', async () => {
    const { server } = backend

    await expect(sendReply()).resolves.toEqual({ filedUnder: 7 })

    expect(server.filed).toEqual([{ path: REPLY_PATH, by: 7 }])
    expect(server.seen).toEqual([
      'GET /services/csrf/',
      'GET /api/v1/users/me/',
      `POST ${REPLY_PATH}`
    ])
  })

  it('asks who is signed in once per page load, not once per write', async () => {
    // The cost of the fix after a page load: one GET, on the first write only.
    // The second write carries the token that was just checked and goes
    // straight out, exactly as before.
    const { server } = backend

    await sendReply()
    await sendReply()

    expect(server.seen).toEqual([
      'GET /services/csrf/',
      'GET /api/v1/users/me/',
      `POST ${REPLY_PATH}`,
      `POST ${REPLY_PATH}`
    ])
    expect(server.filed).toEqual([
      { path: REPLY_PATH, by: 7 },
      { path: REPLY_PATH, by: 7 }
    ])
  })

  it('refuses the second press of Send as well as the first', async () => {
    // The check that refused the first attempt fetched a token for 99's
    // session to do it, a valid one. Pressing Send again is exactly what
    // somebody does after a refusal, and that click must not go out on 99's
    // token: T01 again, one click later. The refusal empties the cache, so
    // the second attempt fetches afresh and is asked about in turn.
    const { server } = backend
    server.signIn(99)

    await expect(sendReply()).rejects.toThrow(/signed in as someone else/i)
    await expect(sendReply()).rejects.toThrow(/signed in as someone else/i)

    expect(server.filed).toEqual([])
    expect(getCSRFToken()).toBeNull()
  })

  it('refuses when this tab does not know who it is', async () => {
    // Unknown identity is not a match. There is nobody to compare /users/me/
    // with, so nothing can vouch for the session the token belongs to.
    const { server } = backend
    signInThisTabAs(null)

    const error = await sendReply().catch((caught: unknown) => caught)

    expect(error).toBeInstanceOf(TicketSessionError)
    expect((error as TicketSessionError).reason).toBe('signed-in-as-someone-else')
    expect(server.filed).toEqual([])
    expect(server.seen).toEqual(['GET /services/csrf/'])
  })

  it('refuses when /users/me/ answers with a failure instead of a person', async () => {
    // "Cannot confirm" is not "same person". A gateway error on the question
    // says nothing about whose session the token belongs to, and the session
    // may well be somebody else's by now: sending would be a guess.
    const { server } = backend
    server.signIn(99)
    server.meFailsWith = 502

    const error = await sendReply().catch((caught: unknown) => caught)

    expect(error).toBeInstanceOf(TicketSessionError)
    expect(server.filed).toEqual([])
    expect(server.seen).toEqual(['GET /services/csrf/', 'GET /api/v1/users/me/'])
  })

  it('refuses when /users/me/ says nobody is signed in', async () => {
    // Signed out in another tab: /users/me/ answers 403 not_authenticated.
    // Nobody this tab could be is on the session, so the write does not go.
    const { server } = backend
    server.sessionUser = null

    const error = await sendReply().catch((caught: unknown) => caught)

    expect(error).toBeInstanceOf(TicketSessionError)
    expect(server.filed).toEqual([])
    expect(server.seen).toEqual(['GET /services/csrf/', 'GET /api/v1/users/me/'])
  })

  it('catches a sign-in that lands between the token fetch and the check, before sending', async () => {
    // The token this tab just fetched is 7's, and a moment later 99 signs in.
    // The check sees 99 and the write never goes out. Without the check the
    // write would still be refused, but only after it had been sent: the
    // rotated token 403s and the stale-token branch catches it. The assertion
    // on `seen` is what tells the two apart.
    const { server } = backend
    server.afterCsrf = () => server.signIn(99)

    await expect(sendReply()).rejects.toThrow(/signed in as someone else/i)

    expect(server.filed).toEqual([])
    expect(server.seen).toEqual(['GET /services/csrf/', 'GET /api/v1/users/me/'])
  })

  it('catches a sign-in that lands after the check, through the stale-token branch', async () => {
    // The last ordering. /users/me/ said 7, then 99 signed in before the write
    // went out. The token fetched for 7 is now rotated, so the write is
    // refused as a stale CSRF token, and the branch below the send asks again
    // and does not replay it.
    const { server } = backend
    server.afterMe = () => server.signIn(99)

    await expect(sendReply()).rejects.toThrow(/signed in as someone else/i)

    expect(server.filed).toEqual([])
    expect(server.seen).toEqual([
      'GET /services/csrf/',
      'GET /api/v1/users/me/',
      `POST ${REPLY_PATH}`,
      'GET /services/csrf/',
      'GET /api/v1/users/me/'
    ])
  })

  it('sends the token it checked, not one put in the cache while it asked', async () => {
    // /users/me/ said 7. Before the write leaves, 99 signs in and some other
    // module refills the shared cache with a token for 99's session. The
    // write must carry the token that was checked, which the sign-in has
    // rotated, so it 403s and is refused. Reading the cache at send time
    // instead would pick up 99's valid token and file the reply as 99's.
    const { server } = backend
    server.afterMe = () => {
      server.signIn(99)
      setCsrfToken(server.token())
    }

    await expect(sendReply()).rejects.toThrow(/signed in as someone else/i)

    expect(server.filed).toEqual([])
    expect(server.seen).toEqual([
      'GET /services/csrf/',
      'GET /api/v1/users/me/',
      `POST ${REPLY_PATH}`,
      'GET /services/csrf/',
      'GET /api/v1/users/me/'
    ])
  })

  it('judges by who this tab was before the token fetch started', async () => {
    // Defence in depth, the same shape as the 403-window case in
    // supportAPI.spec.ts. This tab's own identity changes while the token is
    // being fetched. The person who pressed Send was 7, so 99's session must
    // not carry the write.
    const { server } = backend
    server.afterCsrf = () => {
      server.signIn(99)
      signInThisTabAs(99)
    }

    await expect(sendReply()).rejects.toThrow(/signed in as someone else/i)

    expect(server.filed).toEqual([])
    expect(server.seen).toEqual(['GET /services/csrf/', 'GET /api/v1/users/me/'])
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
})

describe('two writes started together on a cold cache', () => {
  // The first write fetched a token and is still waiting for /users/me/ to
  // answer. The second starts in that window: a double click, or a reply and
  // a status change sent together. The cache is not empty any more, but the
  // token in it is one nobody has checked yet.
  function holdTheAnswer() {
    let release!: () => void
    backend.server.meHeldUntil = new Promise<void>((resolve) => {
      release = resolve
    })
    return () => {
      backend.server.meHeldUntil = null
      release()
    }
  }

  it('sends neither once somebody else owns the session', async () => {
    const { server } = backend
    server.signIn(99)
    const release = holdTheAnswer()

    const first = outcome(sendReply())
    await until(() => server.seen.includes('GET /api/v1/users/me/'))
    const second = outcome(sendReply())
    await until(() => server.seen.length === 3)
    release()

    expect([await first, await second]).toEqual(['refused', 'refused'])
    expect(server.filed).toEqual([])
    // The second write asked too, instead of going out on 99's token.
    expect(server.seen).toEqual([
      'GET /services/csrf/',
      'GET /api/v1/users/me/',
      'GET /api/v1/users/me/'
    ])
  })

  it('sends both, each once, when it is still the same person', async () => {
    const { server } = backend
    const release = holdTheAnswer()

    const first = outcome(sendReply())
    await until(() => server.seen.includes('GET /api/v1/users/me/'))
    const second = outcome(sendReply())
    await until(() => server.seen.length === 3)
    release()

    expect([await first, await second]).toEqual(['sent', 'sent'])
    expect(server.filed).toEqual([
      { path: REPLY_PATH, by: 7 },
      { path: REPLY_PATH, by: 7 }
    ])
    expect(server.seen).toEqual([
      'GET /services/csrf/',
      'GET /api/v1/users/me/',
      'GET /api/v1/users/me/',
      `POST ${REPLY_PATH}`,
      `POST ${REPLY_PATH}`
    ])
  })
})

describe('a write on a token this module has already checked (unchanged from before the fix)', () => {
  // This page has already written once since it loaded, so the token in the
  // cache is the one the transport asked /users/me/ about. That first write
  // is made for real here; then the server's log is cleared.
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

    // The fresh token was checked on the way, so the next write goes
    // straight out on it.
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

    // The same refusal as on the cold path, so the agent pages show their
    // sentence for it rather than "try again". This branch is how a takeover
    // is refused for anybody who has already written since the page loaded.
    expect(error).toBeInstanceOf(TicketSessionError)
    expect((error as TicketSessionError).reason).toBe('signed-in-as-someone-else')
    expect(server.filed).toEqual([])
    expect(server.seen).toEqual([
      `POST ${REPLY_PATH}`,
      'GET /services/csrf/',
      'GET /api/v1/users/me/'
    ])
  })

  it('refuses the second press of Send as well, instead of using the token it just fetched', async () => {
    // The refusal above fetched a fresh token to ask its question, and that
    // token is 99's and valid. The same trap as on the cold path, closed the
    // same way.
    const { server } = backend
    server.signIn(99)

    await expect(sendReply()).rejects.toThrow(/signed in as someone else/i)
    await expect(sendReply()).rejects.toThrow(/signed in as someone else/i)

    expect(server.filed).toEqual([])
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

describe('a write on a token this module has not checked (T01, the other way in)', () => {
  // The cache is warm, but nothing here asked who the token belongs to. Two
  // ways that happens mid-session: this tab signed in (stores/auth.ts caches
  // the login response's token), or some other module fetched a token into
  // an empty cache. Every other module that writes does that for whoever owns
  // the session at the time, and none of them asks who that is.

  it("asks once about the login response's token, then goes straight out", async () => {
    const { server } = backend
    setCsrfToken(server.token())

    await sendReply()
    await sendReply()

    expect(server.seen).toEqual([
      'GET /api/v1/users/me/',
      `POST ${REPLY_PATH}`,
      `POST ${REPLY_PATH}`
    ])
    expect(server.filed).toEqual([
      { path: REPLY_PATH, by: 7 },
      { path: REPLY_PATH, by: 7 }
    ])
  })

  it('never sends a write on a token a Team 1 admin page fetched after somebody else signed in', async () => {
    // The page loaded as 7 and has not written yet. 99 signs in in another
    // tab. The admin saves a note on the People page first (Team 1's
    // adminAPI.ts, the real one): it fetches a token for the session as it is
    // now, 99's, and its own write goes out under 99, which is Team 1's code
    // and not this module's to stop. That token is now in the shared cache.
    // Before this check the next ticket write went straight out on it and
    // was filed as 99's.
    const { server } = backend
    server.signIn(99)
    await adminPost('/users/5/notes/', { body: 'Called them back.' })

    const error = await sendReply().catch((caught: unknown) => caught)

    expect(error).toBeInstanceOf(TicketSessionError)
    expect(server.filed).toEqual([{ path: '/api/v1/admin/users/5/notes/', by: 99 }])
    expect(server.seen).toEqual([
      'GET /services/csrf/',
      'POST /api/v1/admin/users/5/notes/',
      'GET /api/v1/users/me/'
    ])
  })

  it('never sends a write on a token a student page fetched after somebody else signed in', async () => {
    // The same on the requester's side: an event RSVP (eventsAPI.ts, the real
    // one) fills the cache for 99, then the student replies on a ticket.
    const { server } = backend
    server.signIn(99)
    await setEventRsvp(3, 'accepted')

    const error = await requestJson('/api/v1/tickets/11/messages/', {
      method: 'POST',
      body: ticketFormData({ body: 'Still broken.' })
    }).catch((caught: unknown) => caught)

    expect(error).toBeInstanceOf(TicketSessionError)
    expect(server.filed).toEqual([{ path: '/events/v1/3/rsvp/', by: 99 }])
    expect(server.seen).toEqual([
      'GET /services/csrf/',
      'POST /events/v1/3/rsvp/',
      'GET /api/v1/users/me/'
    ])
  })

  it('never sends on such a token after an earlier write was checked, either', async () => {
    // Mid-shift. The agent has written once, so one token has been checked.
    // 99 signs in; the next reply is refused, which empties the cache. The
    // agent saves a note on a Team 1 page, which fetches a token for 99, and
    // comes back to reply again. Having checked a token before is no reason
    // to trust a different one now.
    const { server } = backend
    await sendReply()
    server.signIn(99)
    await expect(sendReply()).rejects.toThrow(/signed in as someone else/i)
    await adminPost('/users/5/notes/', { body: 'Called them back.' })
    server.seen = []

    const error = await sendReply().catch((caught: unknown) => caught)

    expect(error).toBeInstanceOf(TicketSessionError)
    expect(server.filed).toEqual([
      { path: REPLY_PATH, by: 7 },
      { path: '/api/v1/admin/users/5/notes/', by: 99 }
    ])
    expect(server.seen).toEqual(['GET /api/v1/users/me/'])
  })

  it('asks once about a token another module fetched for the same person, then sends', async () => {
    // The price of the check when nothing is wrong: one GET.
    const { server } = backend
    await adminPost('/users/5/notes/', { body: 'Called them back.' })

    await expect(sendReply()).resolves.toEqual({ filedUnder: 7 })

    expect(server.seen).toEqual([
      'GET /services/csrf/',
      'POST /api/v1/admin/users/5/notes/',
      'GET /api/v1/users/me/',
      `POST ${REPLY_PATH}`
    ])
    expect(server.filed).toEqual([
      { path: '/api/v1/admin/users/5/notes/', by: 7 },
      { path: REPLY_PATH, by: 7 }
    ])
  })
})

describe('reads', () => {
  it('never fetch a token or ask who is signed in', async () => {
    // GETs carry no CSRF token and are not guarded. That is unchanged: the
    // consequence T01 is about is a write filed under the wrong name.
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
    // calls: summary, csrf (made by csrf.ts), me, the reply
    expect(acceptOf(0)).toBe('application/json')
    expect(acceptOf(3)).toBe('application/json')
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
  // the same path as a reply. The page loaded as 7. Every case below is about
  // whether an export can go out on a session that is not 7's, and whether it
  // costs anything more than a reply when nothing is wrong.
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

  it('is never sent once /users/me/ says somebody else owns the session', async () => {
    // 99 signed in on another tab of the same browser. As a GET the export
    // went straight out and the audit row said 99 took the file.
    const { server } = backend
    server.signIn(99)

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
    expect(server.seen).toEqual(['GET /services/csrf/', 'GET /api/v1/users/me/'])
  })

  it('is never sent when /users/me/ answers with a failure instead of a person', async () => {
    // "Cannot confirm" is not "same person". Sending here would be a guess,
    // and this session is in fact 99's.
    const { server } = backend
    server.signIn(99)
    server.meFailsWith = 502

    const error = await exportQueue().catch((caught: unknown) => caught)

    expect(error).toBeInstanceOf(TicketSessionError)
    expect((error as TicketSessionError).reason).toBe('signed-in-as-someone-else')
    expect(server.filed).toEqual([])
    expect(server.seen).toEqual(['GET /services/csrf/', 'GET /api/v1/users/me/'])
  })

  it('is never sent when this tab does not know who it is', async () => {
    // Nobody to compare /users/me/ with, so nothing is asked and nothing goes.
    const { server } = backend
    signInThisTabAs(null)

    const error = await exportQueue().catch((caught: unknown) => caught)

    expect(error).toBeInstanceOf(TicketSessionError)
    expect((error as TicketSessionError).reason).toBe('signed-in-as-someone-else')
    expect(server.filed).toEqual([])
    expect(server.seen).toEqual(['GET /services/csrf/'])
  })

  it('is sent exactly once, as a POST carrying the checked token, when it is still the same person', async () => {
    const { server } = backend

    const { blob, filename } = await exportQueue()

    expect(blob.size).toBe(2)
    expect(filename).toBe('tickets-2026-09-29.xlsx')
    expect(server.filed).toEqual([{ path: EXPORT_PATH, by: 7 }])
    expect(server.seen).toEqual([
      'GET /services/csrf/',
      'GET /api/v1/users/me/',
      `POST ${EXPORT_PATH}`
    ])
    const [init] = exportCalls()
    expect(init.body).toBe(EXPORT_BODY)
    const headers = new Headers(init.headers)
    expect(headers.get('X-CSRFToken')).toBe(server.token())
    expect(headers.get('Content-Type')).toBe('application/json')
    expect(headers.get('Accept')).toBe('application/json')
    expect(init.credentials).toBe('include')
  })

  it('goes straight out on a token a reply already checked, and a reply on one it checked', async () => {
    // One rule for both. The token the reply's check vouched for is good for
    // the export, and the other way round: no second check of its own.
    const { server } = backend
    await sendReply()
    await exportQueue()
    await sendReply()

    expect(server.seen).toEqual([
      'GET /services/csrf/',
      'GET /api/v1/users/me/',
      `POST ${REPLY_PATH}`,
      `POST ${EXPORT_PATH}`,
      `POST ${REPLY_PATH}`
    ])
    expect(server.filed).toEqual([
      { path: REPLY_PATH, by: 7 },
      { path: EXPORT_PATH, by: 7 },
      { path: REPLY_PATH, by: 7 }
    ])
  })

  it('is refused, not replayed, when somebody else signs in after the check', async () => {
    // The window the GET version left open. /users/me/ said 7, then 99 signed
    // in before the export landed. The token that was checked is rotated, so
    // the server refuses the POST, and the transport asks again and stops.
    const { server } = backend
    server.afterMe = () => server.signIn(99)

    const error = await exportQueue().catch((caught: unknown) => caught)

    expect(error).toBeInstanceOf(TicketSessionError)
    expect((error as TicketSessionError).reason).toBe('signed-in-as-someone-else')
    expect(server.filed).toEqual([])
    expect(server.seen).toEqual([
      'GET /services/csrf/',
      'GET /api/v1/users/me/',
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
    // against 99, and the export would go out under 99.
    const { server } = backend
    server.signIn(99)
    localStorage.setItem('auth.user', JSON.stringify({ id: 99 }))

    try {
      const error = await exportQueue().catch((caught: unknown) => caught)

      expect(error).toBeInstanceOf(TicketSessionError)
      expect(server.filed).toEqual([])
    } finally {
      localStorage.removeItem('auth.user')
    }
  })

  it('judges by who this tab was when Export was pressed, not when the answer came back', async () => {
    // This tab signs out and back in as 99 while /users/me/ is still on its
    // way. The person who pressed Export was 7, and the session is 99's.
    const { server } = backend
    let release!: () => void
    server.meHeldUntil = new Promise<void>((resolve) => {
      release = resolve
    })

    const result = outcome(exportQueue())
    await until(() => server.seen.includes('GET /api/v1/users/me/'))
    server.signIn(99)
    signInThisTabAs(99)
    server.meHeldUntil = null
    release()

    expect(await result).toBe('refused')
    expect(server.filed).toEqual([])
  })

  it("reads a failure with no message of its own as the caller's sentence", async () => {
    // Checked and sent, then the build fails with Django's own error page.
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
