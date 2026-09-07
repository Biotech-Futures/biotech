import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest'

import {
  MAX_ATTACHMENTS,
  TICKET_CATEGORIES,
  attachmentUrl,
  categoryLabel,
  fetchMyTickets,
  priorityLabel,
  statusLabel,
  submitTicket
} from '@/utils/supportAPI'

vi.mock('@/utils/csrf', () => ({
  ensureCsrfCookie: () => Promise.resolve(true),
  buildSessionHeaders: () => new Headers({ Accept: 'application/json' }),
  resetCsrfToken: () => {}
}))

// Whoever THIS TAB thinks it is. The retry guard must read this and not
// localStorage — see the test block at the bottom for why that distinction is
// the whole point.
const tabUser = { value: null as { id: number } | null }
vi.mock('@/stores/auth', () => ({
  useAuthStore: () => ({ user: tabUser.value })
}))

function jsonResponse(payload: unknown) {
  return {
    ok: true,
    text: () => Promise.resolve(JSON.stringify(payload)),
    headers: new Headers()
  } as unknown as Response
}

describe('the requester-facing category list', () => {
  // The client gave this list on 2026-09-04, in this order, after telling us
  // the three we had were "just an AI byproduct". Values and labels are both
  // pinned: the label is what a requester reads, the value is what the backend
  // stores, and the order is what the dropdown renders. It must stay identical
  // to PUBLIC_TICKET_CATEGORIES in backend/apps/tickets/serializers.py — a
  // value here the backend does not accept is a form that 400s on submit.
  const EXPECTED = [
    ['account_access', 'Account and access'],
    ['registration', 'Registration'],
    ['help_student_group', 'Help with a student or group'],
    ['help_mentor', 'Help with a mentor'],
    ['technical_issue', 'Technical issue'],
    ['certificates_records', 'Certificates and records'],
    // Title case while the other seven are sentence case. That is the client's
    // own capitalisation, not a slip. Do not tidy it without telling them.
    ['general_question', 'General Question'],
    ['other', 'Other']
  ]

  it('offers exactly the eight categories the client asked for', () => {
    expect(TICKET_CATEGORIES.map((c) => [c.value, c.label])).toEqual(EXPECTED)
  })

  it('no longer offers the category the client replaced', () => {
    const values = TICKET_CATEGORIES.map((c) => c.value) as string[]
    expect(values).not.toContain('programs_groups')
  })

  it('keeps "Other" last, where a person looks for it', () => {
    expect(TICKET_CATEGORIES[TICKET_CATEGORIES.length - 1].value).toBe('other')
  })

  it('does not offer any category the platform raises tickets under itself', () => {
    // Spelled out rather than derived from the backend enum on purpose.
    // 'flagged_content' is the real one: message screening files its tickets
    // under it, and the admin queue lists it so support can filter for it.
    // A student must never be able to file their own enquiry as a moderation
    // case, so it must not reach this dropdown. The backend refuses it too —
    // see test_handoff.test_a_requester_cannot_file_their_own_enquiry_under_it
    // — and this is the half that keeps it out of the form in the first place.
    const values = TICKET_CATEGORIES.map((c) => c.value) as string[]
    expect(values).not.toContain('flagged_content')
    expect(values).toHaveLength(8)
  })

  it('labels a known category and passes an unknown one through untouched', () => {
    expect(categoryLabel('help_mentor')).toBe('Help with a mentor')
    // A ticket filed under the retired category before migration 0005 ran
    // still has to render as something.
    expect(categoryLabel('programs_groups')).toBe('programs_groups')
    expect(categoryLabel('something_new')).toBe('something_new')
  })

  it('names screening\'s category rather than printing the database key', () => {
    // Support can re-file a ticket into it, so a requester can be shown a
    // category the dropdown never offered. Before this the page printed the
    // raw key `flagged_content` on a student's own ticket.
    expect(categoryLabel('flagged_content')).toBe('Under review')
    // Never the queue's own word, and never an accusation. See supportAPI.ts.
    expect(categoryLabel('flagged_content').toLowerCase()).not.toContain('report')
    expect(categoryLabel('flagged_content').toLowerCase()).not.toContain('flag')
  })

  it('does not offer that category on the form', () => {
    // Showable and offerable are different things, and the whole reason this
    // label exists is that support can put a ticket there. It must still not
    // be something a person can file their own enquiry under.
    const values = TICKET_CATEGORIES.map((c) => c.value) as string[]
    expect(values).not.toContain('flagged_content')
  })
})

describe('priorityLabel', () => {
  // The short form, used on the badge beside a ticket. It had no test at all:
  // changing high to 'Low' left all 110 green, which is the same shape as the
  // option-order tautology found in TicketForm.spec.ts.
  //
  // Written out rather than derived from TICKET_PRIORITIES, and deliberately
  // NOT the same strings as the form's options: the form asks about the
  // person's situation, the badge names the level the queue works in. Two
  // vocabularies on purpose, so neither can be checked against the other.
  it('names each level as the queue does', () => {
    expect(priorityLabel('high')).toBe('High')
    expect(priorityLabel('normal')).toBe('Normal')
    expect(priorityLabel('low')).toBe('Low')
  })

  it('passes an unknown value through rather than rendering blank', () => {
    expect(priorityLabel('critical')).toBe('critical')
  })
})

describe('statusLabel', () => {
  it('covers all four states the backend can return', () => {
    expect(statusLabel('open')).toBe('Open')
    expect(statusLabel('in_progress')).toBe('In progress')
    expect(statusLabel('pending_user')).toBe('Pending user')
    expect(statusLabel('resolved')).toBe('Resolved')
  })
})

describe('attachmentUrl', () => {
  it('points at the requester endpoint, which is scoped to their own tickets', () => {
    expect(attachmentUrl(88, 5)).toContain('/api/v1/tickets/88/attachments/5/')
  })
})

describe('talking to the backend', () => {
  let fetchMock: ReturnType<typeof vi.fn>

  beforeEach(() => {
    fetchMock = vi.fn()
    vi.stubGlobal('fetch', fetchMock)
  })

  afterEach(() => {
    vi.unstubAllGlobals()
  })

  it('unwraps the {msg, data} envelope so callers never see it', async () => {
    const page = { items: [], total: 0, page: 1, limit: 10, hasMore: false }
    fetchMock.mockResolvedValue(jsonResponse({ msg: 'Tickets retrieved successfully', data: page }))

    await expect(fetchMyTickets()).resolves.toEqual(page)
  })

  it('percent-encodes the snapshot stamp instead of pasting it into the URL', async () => {
    /**
     * The trap this closes, and it has caught somebody once already.
     *
     * An ISO timestamp ends "+00:00". Pasted straight into a query string,
     * the "+" decodes on the server as a SPACE, the stamp fails to parse, and
     * the snapshot silently stops applying — while every test that only
     * checks "no row went missing" stays green, because not applying it loses
     * no rows either.
     *
     * Replacing URLSearchParams with plain string concatenation used to leave
     * the whole suite passing. This is the assertion that fails.
     */
    const page = {
      items: [], total: 0, page: 1, limit: 10, hasMore: false,
      asOf: 'x', after: 'x_1',
    }
    fetchMock.mockResolvedValue(jsonResponse({ msg: 'ok', data: page }))

    await fetchMyTickets(2, 10, {
      asOf: '2026-09-02T04:00:00+00:00',
      after: '2026-09-02T04:00:00+00:00_7',
    })

    const url = String(fetchMock.mock.calls[0][0])
    expect(url).toContain('asOf=2026-09-02T04%3A00%3A00%2B00%3A00')
    // The cursor carries a timestamp too, so it has the same trap in it.
    expect(url).toContain('after=2026-09-02T04%3A00%3A00%2B00%3A00_7')
    expect(url).not.toContain('+00:00')
  })

  it('sends the snapshot and the cursor together or not at all', async () => {
    /**
     * The server refuses a cursor with no snapshot and ignores a snapshot with
     * no cursor, so a caller that sent one alone would either get a 400 or
     * silently fall back to offset paging — which is the defect the cursor was
     * added to close.
     */
    const page = {
      items: [], total: 0, page: 1, limit: 10, hasMore: false,
      asOf: 'x', after: 'x_1',
    }
    fetchMock.mockResolvedValue(jsonResponse({ msg: 'ok', data: page }))

    await fetchMyTickets(1, 10)

    const url = String(fetchMock.mock.calls[0][0])
    expect(url).not.toContain('asOf=')
    expect(url).not.toContain('after=')
  })

  it('sends attachments repeated under one key, which is what the backend reads', async () => {
    fetchMock.mockResolvedValue(jsonResponse({ msg: 'ok', data: { id: 1 } }))

    await submitTicket({
      category: 'account_access',
      priority: 'normal',
      subject: 'Cannot sign in',
      body: 'The login code never arrives.',
      files: [
        new File(['a'], 'one.pdf', { type: 'application/pdf' }),
        new File(['b'], 'two.pdf', { type: 'application/pdf' })
      ]
    })

    const body = fetchMock.mock.calls[0][1].body as FormData
    // getlist("files") on the server side depends on this being repeated
    // rather than files[0] / files[1].
    expect(body.getAll('files')).toHaveLength(2)
    expect(body.get('category')).toBe('account_access')
    expect(body.get('subject')).toBe('Cannot sign in')
  })

  it('raises the backend message rather than a generic failure', async () => {
    fetchMock.mockResolvedValue({
      ok: false,
      status: 404,
      text: () => Promise.resolve(JSON.stringify({ msg: 'Ticket not found', data: null })),
      headers: new Headers()
    } as unknown as Response)

    await expect(fetchMyTickets()).rejects.toThrow('Ticket not found')
  })
})

describe('attachment limits', () => {
  // This asserts the constant this app ships, and nothing more — it cannot
  // see the backend and an assertion here would not notice if the two drifted.
  // The cap the server actually enforces is pinned in
  // backend/tests/apps/tickets/test_api_user.py, which posts six files and
  // expects a 400. Both are needed; neither replaces the other.
  it('caps a message at five files, matching MAX_ATTACHMENTS_PER_MESSAGE in the backend', () => {
    expect(MAX_ATTACHMENTS).toBe(5)
  })
})

describe('the CSRF retry guard', () => {
  // Django rotates the CSRF token on every login, and both front ends share
  // one cookie jar. So a stale token has two causes that look identical on the
  // wire and must be treated oppositely: my own token rotated (retry), or
  // somebody else signed in and took the session (never retry — the write
  // would be filed under their name, and on this platform that name belongs
  // to a school student).
  const csrf403 = {
    ok: false,
    status: 403,
    clone: () => ({
      text: () => Promise.resolve('{"error":"CSRF Failed: CSRF token incorrect."}')
    }),
    text: () => Promise.resolve('{"error":"CSRF Failed: CSRF token incorrect."}'),
    headers: new Headers()
  } as unknown as Response

  beforeEach(() => {
    tabUser.value = { id: 7 }
    // localStorage deliberately names somebody else, standing in for another
    // tab having just signed in. The guard must ignore it.
    localStorage.setItem('auth.user', JSON.stringify({ id: 99 }))
  })

  afterEach(() => {
    localStorage.clear()
    vi.unstubAllGlobals()
  })

  it('retries once when the session still belongs to this tab', async () => {
    const fetchMock = vi
      .fn()
      .mockResolvedValueOnce(csrf403)
      .mockResolvedValueOnce({ ok: true, json: () => Promise.resolve({ id: 7 }) })
      .mockResolvedValueOnce(
        jsonResponse({ msg: 'ok', data: { id: 1, ticketNumber: 'SUP-1' } })
      )
    vi.stubGlobal('fetch', fetchMock)

    await submitTicket({ category: 'account_access', subject: 's', body: 'b', priority: 'normal' })

    // first attempt, identity check, replay
    expect(fetchMock).toHaveBeenCalledTimes(3)
  })

  it('judges by who this tab was when the request went out', async () => {
    // Defence in depth for the window between sending and the 403 arriving.
    // Reading the identity only after the failure would compare the new
    // person against the new person and agree.
    const fetchMock = vi
      .fn()
      .mockImplementationOnce(() => {
        tabUser.value = { id: 99 } // this tab changed hands mid-flight
        return Promise.resolve(csrf403)
      })
      .mockResolvedValueOnce({ ok: true, json: () => Promise.resolve({ id: 99 }) })
    vi.stubGlobal('fetch', fetchMock)

    await expect(
      submitTicket({ category: 'account_access', subject: 's', body: 'b', priority: 'normal' })
    ).rejects.toThrow(/signed in as someone else/i)

    expect(fetchMock).toHaveBeenCalledTimes(2)
  })

  it('refuses to retry once somebody else owns the session', async () => {
    const fetchMock = vi
      .fn()
      .mockResolvedValueOnce(csrf403)
      // /users/me/ now answers with the other person
      .mockResolvedValueOnce({ ok: true, json: () => Promise.resolve({ id: 99 }) })
    vi.stubGlobal('fetch', fetchMock)

    await expect(
      submitTicket({ category: 'account_access', subject: 's', body: 'b', priority: 'normal' })
    ).rejects.toThrow(/signed in as someone else/i)

    // Never replayed: the third call would have been the write.
    expect(fetchMock).toHaveBeenCalledTimes(2)
  })
})

