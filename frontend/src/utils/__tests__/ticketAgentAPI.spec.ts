import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest'
import { createPinia, setActivePinia } from 'pinia'

import { useAuthStore } from '@/stores/auth'
import { ApiError } from '@/utils/apiError'
import { resetCsrfToken, setCsrfToken } from '@/utils/csrf'
import { TicketSessionError } from '@/utils/ticketTransport'
import {
  attachmentErrorMessage,
  bulkAssignTickets,
  deleteTicket,
  downloadTicketAttachment,
  exportTickets,
  fetchAssignees,
  fetchSupportRoster,
  fetchTicketAnalytics,
  fetchTicketAudit,
  fetchTicketDetail,
  fetchTicketHistory,
  fetchTicketQueue,
  fetchTicketRegions,
  fetchTicketSummary,
  grantSupport,
  revokeSupport,
  saveTicketExport,
  sendTicketMessage,
  serverMessage,
  ticketRefusalReason,
  updateTicket,
  wasRefused
} from '@/utils/ticketAgentAPI'
import type { TicketFilters } from '@/utils/ticketAgentSchema'

/**
 * Every agent endpoint, through the real transport and the real csrf.ts, with
 * only `fetch` replaced. Each case pins the method, the literal URL and the
 * body the backend reads, and parses a response shaped like the one the view
 * really sends (backend/apps/tickets/views_admin.py).
 *
 * The CSRF cache starts warm, as it is after signing in. The transport asks
 * /users/me/ about a token before the first write that carries it; the stub
 * below answers that, and the token fetch, and keeps both out of `sent`, so a
 * write is one entry in `sent`. The takeover check has its own suite
 * (ticketTransport.spec.ts); the T01 cases here only prove the agent writes
 * go through it at all.
 */

type Sent = { method: string; url: string; headers: Headers; body: BodyInit | null | undefined }

let sent: Sent[] = []
let answers: Response[] = []
let meId = 7
// Django hands out a differently masked token on every fetch. The transport
// keeps track of which token it has checked, so no two fetches here may hand
// out the same string either, or one case would inherit another's check.
let tokenFetches = 0

const json = (body: unknown, status = 200, headers: Record<string, string> = {}) =>
  new Response(JSON.stringify(body), {
    status,
    headers: { 'Content-Type': 'application/json', ...headers }
  })
const ok = (data: unknown, status = 200) => json({ msg: 'ok', data }, status)
const answer = (...responses: Response[]) => answers.push(...responses)

const fetchMock = vi.fn(async (input: RequestInfo | URL, init: RequestInit = {}) => {
  const url = String(input)
  const path = new URL(url).pathname
  // The token fetch and the identity check are csrf.ts's and the transport's
  // business; they are answered here and left out of `sent`.
  if (path === '/services/csrf/') {
    tokenFetches += 1
    return json({ csrfToken: `fresh-token-${tokenFetches}` })
  }
  if (path === '/api/v1/users/me/') return json({ id: meId })
  sent.push({
    method: String(init.method ?? 'GET').toUpperCase(),
    url,
    headers: new Headers(init.headers),
    body: init.body
  })
  const next = answers.shift()
  if (!next) throw new Error(`no answer queued for ${url}`)
  return next
})

const last = () => sent[sent.length - 1]
const jsonBody = () => JSON.parse(String(last().body))
const formEntries = () =>
  [...(last().body as FormData).entries()].map(([key, value]) => [
    key,
    typeof value === 'string' ? value : (value as File).name
  ])

beforeEach(() => {
  sent = []
  answers = []
  meId = 7
  fetchMock.mockClear()
  vi.stubGlobal('fetch', fetchMock)
  setActivePinia(createPinia())
  useAuthStore().user = { id: 7, email: 'sam@x.test', first_name: 'Sam', last_name: 'Reid' }
  setCsrfToken('test-token')
})

afterEach(() => {
  vi.unstubAllGlobals()
  vi.useRealTimers()
  resetCsrfToken()
})

// Shapes as views_admin.py builds them.
const SCREENING_ROW = {
  id: 88,
  ticketNumber: 'SUP-2026-00042',
  user: { name: null, region: '', anonymous: false },
  subject: 'AI screening: personal_contact',
  status: 'open',
  priority: 'high',
  assignee: null,
  supportUpdatedAt: '2026-08-25T09:58:00Z',
  overdue: false
}
const HUMAN_ROW = {
  ...SCREENING_ROW,
  id: 89,
  ticketNumber: 'SUP-2026-00043',
  user: { name: 'Mia Thompson', region: 'Australia', anonymous: false },
  subject: 'Cannot access group workspace',
  priority: 'normal',
  assignee: { id: 4, name: 'Sam Reid' },
  overdue: true
}
const QUEUE_PAGE = {
  items: [SCREENING_ROW, HUMAN_ROW],
  total: 2,
  page: 1,
  limit: 10,
  hasMore: false,
  asOf: '2026-09-02T04:00:00.000000Z',
  after: '2026-08-25T09:58:00.000000Z_89'
}
const DETAIL = {
  id: 42,
  ticketNumber: 'SUP-2026-00042',
  subject: 'Cannot access group workspace',
  body: 'I get an error opening my group.',
  category: 'help_student_group',
  status: 'in_progress',
  priority: 'normal',
  channel: 'portal',
  region: 'Australia',
  requester: {
    id: 1,
    name: 'Mia Thompson',
    email: 'mia@example.com',
    region: 'Australia',
    registeredAt: '2026-05-01T00:00:00Z'
  },
  assignee: { id: 4, name: 'Sam Reid' },
  createdAt: '2026-08-25T09:00:00Z',
  updatedAt: '2026-08-25T09:30:00Z',
  supportUpdatedAt: '2026-08-25T09:40:00Z',
  firstResponseAt: '2026-08-25T09:30:00Z',
  resolvedAt: null,
  overdue: false,
  messages: [
    {
      id: 1,
      messageType: 'user_message',
      body: 'I get an error opening my group.',
      author: { id: 1, name: 'Mia Thompson' },
      createdAt: '2026-08-25T09:00:00Z',
      attachments: [{ id: 7, filename: 'error.png', mimeType: 'image/png', size: 2048 }]
    },
    {
      id: 2,
      messageType: 'internal_note',
      body: 'Checking the group membership.',
      author: { id: 4, name: 'Sam Reid' },
      createdAt: '2026-08-25T09:40:00Z',
      attachments: []
    }
  ]
}

describe('the queue list', () => {
  it('sends the page, the filters and both halves of the walk, percent-encoded', async () => {
    answer(ok(QUEUE_PAGE))

    await fetchTicketQueue(
      2,
      25,
      { status: 'open', region: 'Australia', assignee: '4' },
      { asOf: '2026-09-02T04:00:00+00:00', after: '2026-09-02T04:00:00+00:00_7' }
    )

    expect(last().method).toBe('GET')
    // An un-encoded "+" reaches the server as a space and the stamp stops
    // parsing, silently. Both halves carry one.
    expect(last().url).toBe(
      'http://localhost:8000/api/v1/admin/tickets/?page=2&limit=25&region=Australia&status=open' +
        '&assignee=4&asOf=2026-09-02T04%3A00%3A00%2B00%3A00&after=2026-09-02T04%3A00%3A00%2B00%3A00_7'
    )
  })

  it('reads a fresh look without a walk, and an empty filter as no filter', async () => {
    answer(ok(QUEUE_PAGE))

    await fetchTicketQueue(1, 10, { status: '', search: '', priority: 'high' })

    expect(last().url).toBe('http://localhost:8000/api/v1/admin/tickets/?page=1&limit=10&priority=high')
  })

  it('parses a page with a screening row that has no requester', async () => {
    answer(ok(QUEUE_PAGE))

    const page = await fetchTicketQueue(1, 10)

    expect(page.items.map((row) => row.user.name)).toEqual([null, 'Mia Thompson'])
    expect(page.after).toBe('2026-08-25T09:58:00.000000Z_89')
  })

  it('refuses a page with no snapshot stamp instead of paging without it', async () => {
    const withoutStamp: Record<string, unknown> = { ...QUEUE_PAGE }
    delete withoutStamp.asOf
    answer(ok(withoutStamp))

    await expect(fetchTicketQueue(1, 10)).rejects.toThrow()
  })

  it('reads the four counters', async () => {
    answer(ok({ unassigned: 12, open: 38, pendingUser: 17, overdue: 4 }))

    await expect(fetchTicketSummary()).resolves.toEqual({
      unassigned: 12,
      open: 38,
      pendingUser: 17,
      overdue: 4
    })
    expect(last().url).toBe('http://localhost:8000/api/v1/admin/tickets/summary/')
  })

  it('reads the assignees with their assignable flag', async () => {
    answer(
      ok([
        { id: 3, name: 'Ada Byron', assignable: true },
        { id: 7, name: 'Rex Voke', assignable: false }
      ])
    )

    await expect(fetchAssignees()).resolves.toEqual([
      { id: 3, name: 'Ada Byron', assignable: true },
      { id: 7, name: 'Rex Voke', assignable: false }
    ])
    expect(last().url).toBe('http://localhost:8000/api/v1/admin/tickets/assignees/')
  })

  it('reads the regions, the unknown bucket last', async () => {
    answer(
      ok([
        { value: 'Australia', label: 'Australia' },
        { value: '__unknown__', label: 'Unknown' }
      ])
    )

    await expect(fetchTicketRegions()).resolves.toEqual([
      { value: 'Australia', label: 'Australia' },
      { value: '__unknown__', label: 'Unknown' }
    ])
    expect(last().url).toBe('http://localhost:8000/api/v1/admin/tickets/regions/')
  })

  it('bulk-assigns with a null assignee kept as null, and reads per-ticket results', async () => {
    answer(
      ok({
        results: [
          { ticketId: 3, ok: true },
          { ticketId: 4, ok: false, error: 'not found' }
        ]
      })
    )

    const result = await bulkAssignTickets([3, 4], null)

    expect(last().method).toBe('POST')
    expect(last().url).toBe('http://localhost:8000/api/v1/admin/tickets/bulk-assign/')
    // The serializer refuses the key being absent; null is "back to the pool".
    expect(String(last().body)).toBe('{"ticketIds":[3,4],"assigneeId":null}')
    expect(last().headers.get('Content-Type')).toBe('application/json')
    expect(last().headers.get('X-CSRFToken')).toBe('test-token')
    expect(result.results).toEqual([
      { ticketId: 3, ok: true },
      { ticketId: 4, ok: false, error: 'not found' }
    ])
  })
})

describe('exporting the queue (C-09)', () => {
  const xlsx = (headers: Record<string, string> = {}) =>
    new Response('PK', {
      status: 200,
      headers: {
        'Content-Type': 'application/vnd.openxmlformats-officedocument.spreadsheetml.sheet',
        ...headers
      }
    })

  it('sends the queue filters and nothing about paging', async () => {
    answer(xlsx())

    await exportTickets({
      search: 'Mia Thompson',
      assignee: '__unassigned__',
      status: 'open',
      // What a page might spread in from its own state. Not a filter.
      page: '3',
      asOf: '2026-09-02T04:00:00Z'
    } as TicketFilters)

    expect(last().method).toBe('GET')
    expect(last().url).toBe(
      'http://localhost:8000/api/v1/admin/tickets/export/?status=open&assignee=__unassigned__&search=Mia+Thompson'
    )
    expect(last().headers.get('Accept')).toBe('application/json')
  })

  it('asks for everything when nothing is filtered', async () => {
    answer(xlsx())

    await exportTickets()

    expect(last().url).toBe('http://localhost:8000/api/v1/admin/tickets/export/')
  })

  it('names the file the way the server did', async () => {
    answer(xlsx({ 'Content-Disposition': 'attachment; filename="tickets-2026-09-28.xlsx"' }))

    const file = await exportTickets()

    expect(file.filename).toBe('tickets-2026-09-28.xlsx')
    expect(file.blob.size).toBe(2)
  })

  it("falls back to tickets-YYYY-MM-DD.xlsx on the reader's own calendar", async () => {
    // Pinned to a zone ahead of UTC. On a machine that runs in UTC (CI does)
    // the local and UTC calendars agree and this case could not tell them
    // apart. Node reads TZ again when it changes.
    const savedTZ = process.env.TZ
    process.env.TZ = 'Australia/Sydney'
    try {
      vi.useFakeTimers({ toFake: ['Date'] })
      // Local time, early on the 5th: 13:15 on the 4th in UTC.
      vi.setSystemTime(new Date(2026, 0, 5, 0, 15))
      expect(new Date().toISOString()).toBe('2026-01-04T13:15:00.000Z')
      answer(xlsx())

      await expect(exportTickets()).resolves.toMatchObject({ filename: 'tickets-2026-01-05.xlsx' })
    } finally {
      if (savedTZ === undefined) delete process.env.TZ
      else process.env.TZ = savedTZ
    }
  })

  it('surfaces a refused filter as a sentence the page can show', async () => {
    answer(
      json(
        {
          error: 'assignee must be an integer.',
          code: 'invalid',
          fields: { assignee: ['assignee must be an integer.'] },
          request_id: 'r1'
        },
        400
      )
    )

    const error = await exportTickets({ assignee: 'x' }).catch((caught: unknown) => caught)

    expect(ticketRefusalReason(error)).toBe('assignee must be an integer.')
  })

  it('saves the file under its name', async () => {
    const created: string[] = []
    URL.createObjectURL = vi.fn(() => {
      created.push('blob:mock/0')
      return 'blob:mock/0'
    }) as unknown as typeof URL.createObjectURL
    URL.revokeObjectURL = vi.fn() as unknown as typeof URL.revokeObjectURL
    const clicked: string[] = []
    const click = vi
      .spyOn(HTMLAnchorElement.prototype, 'click')
      .mockImplementation(function (this: HTMLAnchorElement) {
        clicked.push(this.download)
      })

    saveTicketExport({ blob: new Blob(['PK']), filename: 'tickets-2026-09-29.xlsx' })

    expect(clicked).toEqual(['tickets-2026-09-29.xlsx'])
    expect(created).toEqual(['blob:mock/0'])
    click.mockRestore()
  })
})

describe('one ticket', () => {
  it('reads the detail, internal notes included', async () => {
    answer(ok(DETAIL))

    const ticket = await fetchTicketDetail(42)

    expect(last().url).toBe('http://localhost:8000/api/v1/admin/tickets/42/')
    expect(ticket.messages.map((message) => message.messageType)).toEqual([
      'user_message',
      'internal_note'
    ])
    expect(ticket.messages[1].author).toEqual({ id: 4, name: 'Sam Reid' })
  })

  it('reads the history', async () => {
    answer(
      ok([
        {
          id: 5,
          action: 'assign',
          actor: { id: 4, name: 'Sam Reid' },
          beforeState: { assignee_id: null },
          afterState: { assignee_id: 4 },
          createdAt: '2026-08-25T09:10:00Z'
        }
      ])
    )

    const history = await fetchTicketHistory(42)

    expect(last().url).toBe('http://localhost:8000/api/v1/admin/tickets/42/history/')
    expect(history[0].afterState).toEqual({ assignee_id: 4 })
  })

  it('PATCHes JSON, keeping a null assignee as null', async () => {
    answer(ok({ ...DETAIL, assignee: null }))

    const ticket = await updateTicket(42, { assignee: null })

    expect(last().method).toBe('PATCH')
    expect(last().url).toBe('http://localhost:8000/api/v1/admin/tickets/42/')
    expect(String(last().body)).toBe('{"assignee":null}')
    expect(last().headers.get('Content-Type')).toBe('application/json')
    expect(last().headers.get('X-CSRFToken')).toBe('test-token')
    expect(ticket.assignee).toBeNull()
  })

  it('leaves out a field that is not changing', async () => {
    answer(ok({ ...DETAIL, priority: 'high', category: 'flagged_content' }))

    await updateTicket(42, { priority: 'high', category: 'flagged_content', assignee: undefined })

    expect(jsonBody()).toEqual({ priority: 'high', category: 'flagged_content' })
  })

  it('sends a reply as multipart with every file under one key', async () => {
    answer(ok(DETAIL, 201))

    await sendTicketMessage(42, {
      messageType: 'support_reply',
      body: 'We have reset it.',
      files: [
        new File(['a'], 'one.pdf', { type: 'application/pdf' }),
        new File(['b'], 'two.png', { type: 'image/png' })
      ]
    })

    expect(last().method).toBe('POST')
    expect(last().url).toBe('http://localhost:8000/api/v1/admin/tickets/42/messages/')
    expect(formEntries()).toEqual([
      ['messageType', 'support_reply'],
      ['body', 'We have reset it.'],
      ['files', 'one.pdf'],
      ['files', 'two.png']
    ])
    // The browser writes the multipart boundary; a JSON Content-Type here
    // would make the server read the form as JSON.
    expect(last().headers.get('Content-Type')).toBeNull()
  })

  it('folds "reply and wait for their reply" into the same request', async () => {
    answer(ok({ ...DETAIL, status: 'pending_user' }, 201))

    const ticket = await sendTicketMessage(42, {
      messageType: 'support_reply',
      body: 'Can you send a screenshot?',
      moveToPending: true
    })

    expect(sent).toHaveLength(1)
    expect(formEntries()).toEqual([
      ['messageType', 'support_reply'],
      ['body', 'Can you send a screenshot?'],
      ['moveToPending', 'true']
    ])
    expect(ticket.status).toBe('pending_user')
  })

  it('sends an internal note without the pending key at all', async () => {
    answer(ok(DETAIL, 201))

    await sendTicketMessage(42, {
      messageType: 'internal_note',
      body: 'Checking the group membership.',
      moveToPending: false
    })

    expect(formEntries()).toEqual([
      ['messageType', 'internal_note'],
      ['body', 'Checking the group membership.']
    ])
  })

  it('deletes through the delete route and hands the id back', async () => {
    answer(json({ msg: 'Ticket deleted', data: null }))

    await expect(deleteTicket(42)).resolves.toBe(42)

    expect(last().method).toBe('DELETE')
    expect(last().url).toBe('http://localhost:8000/api/v1/admin/tickets/42/delete/')
  })
})

describe('downloading an attachment', () => {
  let clicked: HTMLAnchorElement[] = []

  beforeEach(() => {
    clicked = []
    URL.createObjectURL = vi.fn(() => 'blob:mock/0') as unknown as typeof URL.createObjectURL
    URL.revokeObjectURL = vi.fn() as unknown as typeof URL.revokeObjectURL
    vi.spyOn(HTMLAnchorElement.prototype, 'click').mockImplementation(function (
      this: HTMLAnchorElement
    ) {
      clicked.push(this)
    })
  })

  afterEach(() => {
    vi.restoreAllMocks()
  })

  it('fetches the admin endpoint as JSON-negotiated bytes and saves them under the shown name', async () => {
    answer(new Response('%PDF-1.4', { status: 200 }))

    await downloadTicketAttachment(42, 7, 'error.png')

    expect(last().method).toBe('GET')
    expect(last().url).toBe('http://localhost:8000/api/v1/admin/tickets/42/attachments/7/')
    expect(last().headers.get('Accept')).toBe('application/json')
    expect(clicked.map((link) => link.download)).toEqual(['error.png'])
  })

  it('lets the refusal out instead of saving an error page as the file', async () => {
    answer(json({ msg: 'Attachment not found', data: null }, 404))

    const error = await downloadTicketAttachment(42, 7, 'error.png').catch(
      (caught: unknown) => caught
    )

    expect(clicked).toEqual([])
    expect(attachmentErrorMessage(error)).toBe(
      'This file is gone. The ticket or the message it belonged to was deleted. Reload the queue.'
    )
  })

  const SENTENCES: Array<[string, unknown, string]> = [
    [
      '401',
      new ApiError({ error: 'x', code: 'not_authenticated', request_id: 'r' }, 401),
      'Your session has expired. Reload this page and sign in again to open this file.'
    ],
    [
      '403',
      new ApiError({ error: 'x', code: 'permission_denied', request_id: 'r' }, 403),
      'Your session has expired. Reload this page and sign in again to open this file.'
    ],
    [
      '500',
      new ApiError({ error: 'x', code: 'internal_server_error', request_id: 'r' }, 500),
      'Could not download that file. Try again.'
    ],
    ['a network failure', new TypeError('Failed to fetch'), 'Could not download that file. Try again.']
  ]
  for (const [name, error, sentence] of SENTENCES) {
    it(`explains ${name} in words, with no em-dash`, () => {
      expect(attachmentErrorMessage(error)).toBe(sentence)
    })
  }
})

describe('audit and analytics', () => {
  const AUDIT_PAGE = {
    items: [
      {
        id: 9,
        ticketId: 42,
        action: 'delete',
        actor: null,
        beforeState: {
          ticket_number: 'SUP-2026-00042',
          subject: 'Cannot access group workspace',
          status: 'open',
          created_by_id: 1
        },
        afterState: { deleted_at: '2026-09-01T00:00:00Z' },
        createdAt: '2026-09-01T00:00:00Z'
      }
    ],
    total: 1,
    page: 1,
    limit: 20,
    hasMore: false
  }

  it('asks for a page of the audit list with its two filters', async () => {
    answer(ok(AUDIT_PAGE))

    const page = await fetchTicketAudit(1, 20, { action: 'status', actor: '4' })

    expect(last().url).toBe(
      'http://localhost:8000/api/v1/admin/tickets/audit/?page=1&limit=20&action=status&actor=4'
    )
    expect(page.items[0].beforeState).toMatchObject({ ticket_number: 'SUP-2026-00042' })
  })

  it('leaves unset audit filters off the URL', async () => {
    answer(ok(AUDIT_PAGE))

    await fetchTicketAudit(3, 50, { action: '', actor: undefined })

    expect(last().url).toBe('http://localhost:8000/api/v1/admin/tickets/audit/?page=3&limit=50')
  })

  const ANALYTICS = {
    window: { from: '2026-09-01T00:00:00+00:00', to: '2026-09-08T00:00:00+00:00' },
    demand: {
      volume: 3,
      categoryMix: [{ value: 'registration', count: 3 }],
      channelMix: [{ value: 'portal', count: 3 }]
    },
    flow: {
      unassignedBacklog: 1,
      ageByStatus: [{ status: 'open', averageSeconds: 7199 }],
      reopens: 0,
      handOffs: 1
    },
    service: {
      firstResponseSeconds: 3600,
      answeredCount: 2,
      resolutionSeconds: null,
      resolvedCount: 0,
      overdue: 1
    },
    quality: {
      resolutionRate: null,
      resolvedCount: 0,
      totalCount: 3,
      repeatContacts: 0,
      satisfaction: null,
      satisfactionAvailable: false
    },
    segment: { dimension: 'assignee', buckets: [{ value: '4', count: 2 }, { value: '', count: 1 }] },
    dimensions: ['region', 'userType', 'category', 'status', 'assignee', 'channel', 'priority']
  }

  it('sends the picked dates exactly as picked; the server adds the day', async () => {
    answer(ok(ANALYTICS))

    const report = await fetchTicketAnalytics({
      from: '2026-09-01',
      to: '2026-09-07',
      dimension: 'assignee'
    })

    expect(last().url).toBe(
      'http://localhost:8000/api/v1/admin/tickets/analytics/?from=2026-09-01&to=2026-09-07&dimension=assignee'
    )
    // Bucket values are strings, assignee ids included.
    expect(report.segment?.buckets).toEqual([
      { value: '4', count: 2 },
      { value: '', count: 1 }
    ])
  })

  it('asks for the default window with no query string at all', async () => {
    answer(ok({ ...ANALYTICS, window: { from: null, to: null }, segment: null }))

    await fetchTicketAnalytics()

    expect(last().url).toBe('http://localhost:8000/api/v1/admin/tickets/analytics/')
  })
})

describe('the support roster', () => {
  it('reads the roster with each account status', async () => {
    answer(
      ok([
        { id: 4, name: 'Sam Reid', email: 'sam@x.test', openTickets: 3, accountStatus: 'suspended' }
      ])
    )

    await expect(fetchSupportRoster()).resolves.toEqual([
      { id: 4, name: 'Sam Reid', email: 'sam@x.test', openTickets: 3, accountStatus: 'suspended' }
    ])
    expect(last().url).toBe('http://localhost:8000/api/v1/admin/tickets/support-scope/')
  })

  it('grants by user id', async () => {
    answer(json({ msg: 'Support access granted', data: { id: 9, name: 'Ada Byron', email: 'a@x.test' } }, 201))

    await grantSupport(9)

    expect(last().method).toBe('POST')
    expect(last().url).toBe('http://localhost:8000/api/v1/admin/tickets/support-scope/')
    expect(String(last().body)).toBe('{"userId":9}')
  })

  it('revokes by user id', async () => {
    answer(json({ msg: 'Support access revoked', data: null }))

    await revokeSupport(9)

    expect(last().method).toBe('DELETE')
    expect(last().url).toBe('http://localhost:8000/api/v1/admin/tickets/support-scope/9/')
  })

  it("shows the server's sentence when a grant is refused (RO-07)", async () => {
    const sentence =
      'Students cannot be given support queue access. Change their role first if this is not a student account.'
    answer(json({ msg: sentence, data: null }, 400))

    const error = await grantSupport(9).catch((caught: unknown) => caught)

    expect(serverMessage(error)).toBe(sentence)
    // The ticket reader would miss it: the sentence is in msg, not error/code.
    expect(ticketRefusalReason(error)).toBeUndefined()
  })

  it('shows the server sentence for a revoke of somebody no longer on it', async () => {
    answer(json({ msg: 'Support access not found', data: null }, 404))

    const error = await revokeSupport(9).catch((caught: unknown) => caught)

    expect(serverMessage(error)).toBe('Support access not found')
  })

  it('has no server sentence for a network failure or a blank msg', () => {
    expect(serverMessage(new TypeError('Failed to fetch'))).toBeUndefined()
    expect(
      serverMessage(new ApiError({ error: 'x', code: 'http_400', request_id: 'r', msg: '   ' }, 400))
    ).toBeUndefined()
  })
})

describe('reading a refused ticket write', () => {
  const refuse = (body: Record<string, unknown>, status: number) =>
    json({ request_id: 'r1', ...body }, status)

  it('shows an attachment refusal the agent can act on', async () => {
    answer(refuse({ error: 'Attach at most 5 files to one message.', code: 'invalid' }, 400))

    const error = await sendTicketMessage(42, { messageType: 'support_reply', body: 'x' }).catch(
      (caught: unknown) => caught
    )

    expect(ticketRefusalReason(error)).toBe('Attach at most 5 files to one message.')
  })

  it('shows why an assignee was refused (T03)', async () => {
    // The real sentence: serializers_admin.py overrides DRF's `Invalid pk`
    // wording for both assignee fields, and keeps the code does_not_exist.
    const sentence =
      'Cannot assign to user "18". They need an active account with support queue access.'
    answer(
      refuse({ error: sentence, code: 'does_not_exist', fields: { assignee: [sentence] } }, 400)
    )

    const error = await updateTicket(42, { assignee: 18 }).catch((caught: unknown) => caught)

    expect(ticketRefusalReason(error)).toBe(sentence)
  })

  it("shows the permission classes' own sentence", async () => {
    answer(refuse({ error: 'You do not have admin privileges.', code: 'permission_denied' }, 403))

    const error = await deleteTicket(42).catch((caught: unknown) => caught)

    expect(ticketRefusalReason(error)).toBe('You do not have admin privileges.')
    expect(wasRefused(error)).toBe(true)
  })

  it("leaves DRF's machine English and the not-found envelope to the caller's own sentence", async () => {
    answer(
      refuse({ error: '"nope" is not a valid choice.', code: 'invalid_choice' }, 400),
      json({ msg: 'Ticket not found', data: null }, 404),
      refuse({ error: 'Internal server error', code: 'internal_server_error' }, 500)
    )

    const errors = [
      await updateTicket(42, { status: 'nope' }).catch((caught: unknown) => caught),
      await updateTicket(42, { status: 'open' }).catch((caught: unknown) => caught),
      await updateTicket(42, { status: 'open' }).catch((caught: unknown) => caught)
    ]

    expect(errors.map(ticketRefusalReason)).toEqual([undefined, undefined, undefined])
    expect(errors.map(wasRefused)).toEqual([false, false, false])
  })

  it('does not show a stale-token refusal as if it were about access', () => {
    const csrf = new ApiError(
      { error: 'CSRF Failed: CSRF cookie not set.', code: 'permission_denied', request_id: 'r' },
      403
    )
    expect(ticketRefusalReason(csrf)).toBeUndefined()
    expect(
      ticketRefusalReason(new ApiError({ error: '  ', code: 'invalid', request_id: 'r' }, 400))
    ).toBeUndefined()
    expect(ticketRefusalReason(new TypeError('Failed to fetch'))).toBeUndefined()
  })
})

describe('every agent write goes through the takeover check (T01)', () => {
  // The agent endpoints live under /api/v1/admin/, where adminAPI.ts's
  // adminRequest would reach them without either guard. This is the case that
  // tells the two apart: a cold cache, and somebody else signed in since the
  // page loaded. Through the ticket transport the write never leaves the
  // browser; through adminRequest it would be filed under that person.
  const WRITES: Array<[string, () => Promise<unknown>]> = [
    ['a status change', () => updateTicket(42, { status: 'resolved' })],
    ['a reply', () => sendTicketMessage(42, { messageType: 'support_reply', body: 'Done.' })],
    ['an internal note', () => sendTicketMessage(42, { messageType: 'internal_note', body: 'x' })],
    ['a delete', () => deleteTicket(42)],
    ['a bulk assignment', () => bulkAssignTickets([42], 4)],
    ['a roster grant', () => grantSupport(9)],
    ['a roster revoke', () => revokeSupport(9)]
  ]

  // The requester's sentence with its dash taken out: the agent pages are new
  // screens, and the port's rule is no dashes in UI strings.
  const REFUSAL =
    'You appear to be signed in as someone else now. This can happen if you signed in to ' +
    'another BIOTech page in the same browser. Please reload and sign in again.'

  for (const [name, write] of WRITES) {
    it(`never sends ${name} once the session is somebody else's`, async () => {
      resetCsrfToken()
      meId = 99

      const error = await write().catch((caught: unknown) => caught)

      expect(error).toBeInstanceOf(TicketSessionError)
      expect(sent).toEqual([])
      // And the pages have a sentence to show for it, not "try again".
      expect(ticketRefusalReason(error)).toBe(REFUSAL)
      expect(serverMessage(error)).toBe(REFUSAL)
    })
  }

  it('refuses an agent who has already written once, with the same sentence', async () => {
    // The commoner shape mid-shift: this page has written before, so the
    // token is one the server accepted for this agent. Somebody else signs in,
    // the token is rotated, the next write comes back as a stale CSRF token,
    // and the branch that handles that asks who is signed in and refuses. The
    // page must get the same sentence as on the first write, not its own
    // "try again".
    answer(ok(DETAIL, 201))
    await sendTicketMessage(42, { messageType: 'internal_note', body: 'Checked the logs.' })
    meId = 99
    answer(json({ error: 'CSRF Failed: CSRF token incorrect.', code: 'permission_denied' }, 403))

    const error = await sendTicketMessage(42, {
      messageType: 'support_reply',
      body: 'We have reset it.'
    }).catch((caught: unknown) => caught)

    expect(error).toBeInstanceOf(TicketSessionError)
    expect(ticketRefusalReason(error)).toBe(REFUSAL)
    expect(serverMessage(error)).toBe(REFUSAL)
    // Sent once, refused as a stale token, never replayed.
    expect(sent.map((request) => `${request.method} ${request.url}`)).toEqual([
      'POST http://localhost:8000/api/v1/admin/tickets/42/messages/',
      'POST http://localhost:8000/api/v1/admin/tickets/42/messages/'
    ])
  })

  it('shows the other session sentence as it is when no token can be had', async () => {
    // The other refusal the transport makes. It has no dash in it to begin
    // with, and it is not about somebody else, so it is not reworded.
    resetCsrfToken()
    const down = vi.fn(async () => new Response('down', { status: 503 }))
    vi.stubGlobal('fetch', down)

    const error = await updateTicket(42, { status: 'open' }).catch((caught: unknown) => caught)

    expect(error).toBeInstanceOf(TicketSessionError)
    // Only the token fetch went out.
    expect(down).toHaveBeenCalledTimes(1)
    expect(ticketRefusalReason(error)).toBe(
      'Could not initialize a secure session. Please refresh and try again.'
    )
    expect(serverMessage(error)).toBe(
      'Could not initialize a secure session. Please refresh and try again.'
    )
  })
})
