import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest'

import {
  MAX_ATTACHMENTS,
  TICKET_CATEGORIES,
  attachmentUrl,
  categoryLabel,
  fetchMyTickets,
  statusLabel,
  submitTicket
} from '@/utils/supportAPI'

vi.mock('@/utils/csrf', () => ({
  ensureCsrfCookie: () => Promise.resolve(true),
  buildSessionHeaders: () => new Headers({ Accept: 'application/json' })
}))

function jsonResponse(payload: unknown) {
  return {
    ok: true,
    text: () => Promise.resolve(JSON.stringify(payload)),
    headers: new Headers()
  } as unknown as Response
}

describe('the requester-facing category list', () => {
  it('offers exactly the three topics the client specified', () => {
    expect(TICKET_CATEGORIES.map((c) => c.value)).toEqual([
      'account_access',
      'programs_groups',
      'certificates_records'
    ])
  })

  it('does not offer any category the platform raises tickets under itself', () => {
    // Spelled out rather than derived from the backend enum on purpose. If a
    // category is added for tickets the platform raises (AI screening, say),
    // it must not appear in a student's dropdown — and this fails if it does.
    const values = TICKET_CATEGORIES.map((c) => c.value) as string[]
    expect(values).not.toContain('safety_screening')
    expect(values).toHaveLength(3)
  })

  it('labels a known category and passes an unknown one through untouched', () => {
    expect(categoryLabel('programs_groups')).toBe('Programs & Groups')
    expect(categoryLabel('something_new')).toBe('something_new')
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

  it('sends attachments repeated under one key, which is what the backend reads', async () => {
    fetchMock.mockResolvedValue(jsonResponse({ msg: 'ok', data: { id: 1 } }))

    await submitTicket({
      category: 'account_access',
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
  it('agrees with the backend cap of five per message', () => {
    expect(MAX_ATTACHMENTS).toBe(5)
  })
})
