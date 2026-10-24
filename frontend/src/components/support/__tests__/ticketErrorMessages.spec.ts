import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest'

import { apiErrorFromUnknown } from '@/utils/apiError'
import { fetchMyTickets, fetchTicket } from '@/utils/supportAPI'

vi.mock('@/utils/csrf', () => ({
  ensureCsrfCookie: () => Promise.resolve(true),
  buildSessionHeaders: () => new Headers({ Accept: 'application/json' }),
  resetCsrfToken: () => {},
}))

vi.mock('@/stores/auth', () => ({ useAuthStore: () => ({ user: null }) }))

/**
 * What a student reads when a Support Centre request fails.
 *
 * Scope note, because the gap this file used to cover is still open on
 * purpose. A dropped connection rejects with a TypeError whose message is the
 * engine's own wording, and apiErrorFromUnknown prefers a thrown error's
 * message over the caller's fallback, so a fifteen-year-old on a train reads
 * "Failed to fetch", or "Load failed" on an iPhone. The written sentences the
 * Support Centre passes as fallbacks are unreachable for that case.
 *
 * Closing it means changing @/utils/apiError, which twenty-four files across
 * the whole portal import: login, dashboard, groups, resources, events,
 * tasks. That is a platform-wide behaviour change driven by a low-severity
 * finding on one feature, so it was reverted and left for its own issue.
 * apiError.ts is byte-identical to origin/main and is to stay that way here.
 *
 * What is left below is the part that lives in this feature's own files and
 * holds without touching the shared helper.
 */

function abortError(): Error {
  const controller = new AbortController()
  controller.abort()
  // Same shape the platform hands a caller of an aborted fetch.
  return new DOMException('The user aborted a request.', 'AbortError')
}

const FALLBACK = 'Could not load your enquiries.'

describe('a failure a student can read', () => {
  // Only the failures that do not need the shared helper changed. A rejected
  // fetch and a parser error are the two that do, and they are named in the
  // scope note above rather than left out silently.
  const REACHES_THE_FALLBACK: Array<[string, unknown]> = [
    ['a cancelled request', abortError()],
    ['something that is not an Error at all', 'boom'],
  ]

  for (const [name, thrown] of REACHES_THE_FALLBACK) {
    it(`${name} shows the written sentence`, () => {
      expect(apiErrorFromUnknown(thrown, FALLBACK).message).toBe(FALLBACK)
    })
  }

  it('keeps a sentence this app wrote on purpose', () => {
    // supportAPI throws two of these itself, and replacing them with the
    // caller's fallback would lose the only explanation the student gets for
    // a session that changed underneath them.
    const written =
      'You appear to be signed in as someone else now. Please reload and sign in again.'
    expect(apiErrorFromUnknown(new Error(written), FALLBACK).message).toBe(written)
  })
})

describe('the two ticket reads, end to end', () => {
  const fetchMock = vi.fn()

  beforeEach(() => {
    fetchMock.mockReset()
    vi.stubGlobal('fetch', fetchMock)
  })

  afterEach(() => {
    vi.unstubAllGlobals()
  })

  const READS: Array<[string, () => Promise<unknown>, string]> = [
    ['the list', () => fetchMyTickets(), 'Could not load your enquiries.'],
    [
      'one enquiry',
      () => fetchTicket(152),
      'We could not load this enquiry. Check your connection and try again.',
    ],
  ]

  for (const [name, call, fallback] of READS) {
    it(`${name} says something readable when a gateway answers instead`, async () => {
      // What a 502 looks like from outside Django: an HTML page, no JSON, no
      // message to quote. requestJson used to let apiError.ts name it, and
      // "Request failed: 502" went on screen. The sentence comes from
      // supportAPI, which is this feature's own file, so this one holds.
      fetchMock.mockResolvedValue(
        new Response('<html><head><title>502 Bad Gateway</title></head></html>', {
          status: 502,
          headers: { 'Content-Type': 'text/html' },
        })
      )
      try {
        await call()
        throw new Error('the call should not have resolved')
      } catch (error) {
        const message = apiErrorFromUnknown(error, fallback).message
        expect(message).not.toMatch(/Request failed/)
        expect(message).toBe('Something went wrong at our end. Please try again in a moment.')
      }
    })
  }

  it('an enquiry that is not yours keeps the answer the backend wrote', async () => {
    // TicketDetailView answers {"msg": "Ticket not found", "data": null} with
    // a 404, for a ticket that does not exist and for one that belongs to
    // somebody else alike, so the page never has to word that case itself.
    fetchMock.mockResolvedValue(
      new Response('{"msg": "Ticket not found", "data": null}', {
        status: 404,
        headers: { 'Content-Type': 'application/json' },
      })
    )
    try {
      await fetchTicket(152)
      throw new Error('the call should not have resolved')
    } catch (error) {
      const message = apiErrorFromUnknown(
        error,
        'We could not load this enquiry. Check your connection and try again.'
      ).message
      expect(message).toBe('Ticket not found')
    }
  })
})
