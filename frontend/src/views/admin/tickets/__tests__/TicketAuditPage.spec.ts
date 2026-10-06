import { flushPromises, mount, type VueWrapper } from '@vue/test-utils'
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest'
import { createRouter, createWebHashHistory } from 'vue-router'

/**
 * The ticket audit page, ported from adminweb's TicketAuditPage.tsx. Each
 * React test is here under the same name; the ones marked "new" pin
 * behaviour the React suite left untested (U4 map, section 5).
 *
 * The API module is mocked at its boundary and nothing else. Its real
 * helpers stay (wasRefused reads the ApiError the transport throws), and
 * every fixture is run through the real schema on its way out of the mock,
 * which is what the real fetchTicketAudit does with an answer: a fixture the
 * backend could not have sent fails here instead of passing on air.
 *
 * The router is a real one on the real route table, so a ticket link that
 * names a route the table does not have fails here too.
 */

vi.mock('@/utils/ticketAgentAPI', async () => {
  const actual = await vi.importActual<typeof import('@/utils/ticketAgentAPI')>('@/utils/ticketAgentAPI')
  return { ...actual, fetchTicketAudit: vi.fn(), fetchAssignees: vi.fn() }
})

import routes from '@/router/routes'
import { ApiError } from '@/utils/apiError'
import { fetchAssignees, fetchTicketAudit } from '@/utils/ticketAgentAPI'
import { ticketAuditPageSchema, type TicketAuditPage as AuditPage } from '@/utils/ticketAgentSchema'
import TicketAuditPage from '../TicketAuditPage.vue'

const auditMock = vi.mocked(fetchTicketAudit)
const assigneesMock = vi.mocked(fetchAssignees)

// Generated from, not hand-picked: every action the ticket module writes,
// read off the code that writes them. handoff.py writes create, lifecycle.py
// writes assign, status, priority, category, resolve and reopen, and
// views_admin.py writes delete. A pair of sample rows is how a column that
// has to work on all eight ends up covered on two.
const EVERY_ACTION = [
  'create',
  'assign',
  'status',
  'priority',
  'category',
  'resolve',
  'reopen',
  'delete'
] as const

const PLAIN_ENGLISH = [
  [
    'a status change',
    { action: 'status', beforeState: { status: 'in_progress' }, afterState: { status: 'pending_user' } },
    'In progress → Pending user'
  ],
  [
    'a priority change',
    { action: 'priority', beforeState: { priority: 'low' }, afterState: { priority: 'high' } },
    'Low → High'
  ]
] as const

function row(overrides: Record<string, unknown> = {}) {
  return {
    id: 1,
    ticketId: 42,
    action: 'status',
    actor: { id: 4, name: 'Sam Reid' },
    beforeState: { status: 'open' },
    afterState: { status: 'in_progress' },
    createdAt: '2026-09-01T09:00:00Z',
    ...overrides
  }
}

function page(items: unknown[], extra: Record<string, unknown> = {}): AuditPage {
  return ticketAuditPageSchema.parse({
    items,
    total: items.length,
    page: 1,
    limit: 25,
    hasMore: false,
    ...extra
  })
}

// One row per action, each about a different ticket.
function oneOfEach() {
  return EVERY_ACTION.map((action, index) =>
    row({ id: index + 1, ticketId: 100 + index, action, beforeState: {}, afterState: {} })
  )
}

/** A page of the log with more behind it than one page holds. */
function bigLog(servedLimit: number) {
  return page([row()], { total: 300, limit: servedLimit, hasMore: true })
}

/** An answer the test hands over when it chooses to. */
function deferred<T>() {
  let resolve!: (value: T) => void
  let reject!: (reason: unknown) => void
  const promise = new Promise<T>((res, rej) => {
    resolve = res
    reject = rej
  })
  return { promise, resolve, reject }
}

let wrapper: VueWrapper | null = null

// `attach` puts the page in the document, which focus needs: jsdom moves
// focus only between elements that are in it.
async function open({ attach = false } = {}) {
  const router = createRouter({ history: createWebHashHistory(), routes })
  await router.push('/admin/tickets/audit')
  wrapper = mount(TicketAuditPage, {
    global: { plugins: [router] },
    attachTo: attach ? document.body : undefined
  })
  await flushPromises()
  return wrapper
}

const view = () => wrapper as VueWrapper

function cellsOfEachRow() {
  return view()
    .findAll('tbody tr')
    .map((line) => line.findAll('td').map((cell) => cell.text()))
}

const actionSelect = () => view().find('select[aria-label="Filter by action"]')
const whoSelect = () => view().find('select[aria-label="Filter by who did it"]')
const sizeSelect = () => view().find('.audit-pager select')
const optionNames = (select: ReturnType<typeof actionSelect>) =>
  select.findAll('option').map((option) => option.text())

/** What the page last asked the server for: page, limit, filters. */
const lastAsked = () => auditMock.mock.calls.at(-1)

beforeEach(() => {
  auditMock.mockReset()
  assigneesMock.mockReset()
  assigneesMock.mockResolvedValue([{ id: 4, name: 'Sam Reid', assignable: true }])
})

afterEach(() => {
  wrapper?.unmount()
  wrapper = null
  vi.restoreAllMocks()
})

describe('TicketAuditPage', () => {
  it('names a deleted ticket from the snapshot the deletion wrote', async () => {
    /**
     * This is the whole reason the screen exists. The delete dialog promises
     * "a record of the deletion is kept in the history", and that history
     * used to live only inside the ticket's own detail panel, which 404s the
     * moment the ticket is gone. So the promise was true of the database and
     * false of the interface.
     *
     * The number cannot be read back off the ticket, because no queryset
     * returns it any more. It has to come out of the before-state the
     * deletion recorded, which is what this asserts.
     */
    auditMock.mockResolvedValue(
      page([
        row({
          action: 'delete',
          beforeState: {
            ticket_number: 'SUP-2026-00042',
            subject: 'Cannot access group workspace'
          },
          afterState: null
        })
      ])
    )
    await open()

    const [cells] = cellsOfEachRow()
    expect(cells[1]).toBe('#42')
    expect(cells[4]).toBe('SUP-2026-00042 · Cannot access group workspace')
    // And it is the one row with nothing to open. This row records the
    // ticket going away, so a link would send the reader after the very
    // thing the row says is gone. Rows about a ticket deleted later do link,
    // and land on the detail panel's "That ticket could not be opened. It
    // may have been deleted.", which is that panel answering on purpose.
    expect(view().findAll('tbody a')).toEqual([])
  })

  it('still says something when a deletion recorded no snapshot', async () => {
    // Older rows, or a deletion whose snapshot failed to write. A blank cell
    // reads like the screen is broken; this says what is known.
    auditMock.mockResolvedValue(
      page([
        row({ id: 1, action: 'delete', beforeState: null, afterState: null }),
        // Half a snapshot. Whichever half survived is still worth printing.
        row({
          id: 2,
          action: 'delete',
          afterState: null,
          beforeState: { subject: 'Cannot access group workspace' }
        })
      ])
    )
    await open()

    expect(cellsOfEachRow().map((cells) => cells[4])).toEqual([
      'Ticket removed from the queue',
      'Cannot access group workspace'
    ])
  })

  it.each(PLAIN_ENGLISH)(
    'writes %s the way the rest of the product writes it',
    async (_what, overrides, expected) => {
      /**
       * This screen exists to be read, so it must not be the one place that
       * prints database values. Every other place a status appears (the
       * queue badge, the dashboard axis, all three emails) says
       * "In progress", not "in_progress".
       */
      auditMock.mockResolvedValue(page([row(overrides as Record<string, unknown>)]))
      await open()

      expect(cellsOfEachRow().map((cells) => cells[4])).toEqual([expected])
    }
  )

  it('names the new owner instead of printing their id', async () => {
    // The Who column beside this one already prints names, so "#4" here reads
    // as a different kind of thing entirely.
    auditMock.mockResolvedValue(
      page([
        row({
          action: 'assign',
          beforeState: { assignee_id: null },
          afterState: { assignee_id: 4 }
        })
      ])
    )
    await open()

    expect(cellsOfEachRow().map((cells) => cells[4])).toEqual(['Owner set to Sam Reid'])
  })

  it('falls back to the id when that person is no longer on the roster', async () => {
    // Poor, but better than a blank cell: the row still says what happened.
    auditMock.mockResolvedValue(
      page([
        row({
          action: 'assign',
          beforeState: { assignee_id: null },
          afterState: { assignee_id: 99 }
        })
      ])
    )
    await open()

    expect(cellsOfEachRow().map((cells) => cells[4])).toEqual(['Owner set to #99'])
  })

  it('distinguishes handing a ticket back from picking one up', async () => {
    /**
     * Both are an "assign" row, and reading the second as the first would
     * tell an agent somebody took a ticket that in fact nobody owns.
     *
     * Both directions in one render on purpose. With only the hand-back row
     * in the fixture, a summariser that called every assign row "Handed back
     * to the pool" passed this test: the sample it would have got wrong was
     * not there to get wrong.
     */
    auditMock.mockResolvedValue(
      page([
        row({
          id: 1,
          action: 'assign',
          beforeState: { assignee_id: 4 },
          afterState: { assignee_id: null }
        }),
        row({
          id: 2,
          action: 'assign',
          beforeState: { assignee_id: null },
          afterState: { assignee_id: 4 }
        })
      ])
    )
    await open()

    expect(cellsOfEachRow().map((cells) => cells[4])).toEqual([
      'Handed back to the pool',
      'Owner set to Sam Reid'
    ])
  })

  it('says which ticket every row is about, whatever the action was', async () => {
    /**
     * The page listed when, what, who and what changed, and never which
     * ticket. "Resolved · Sana Reid · Pending user → Resolved" is a sentence
     * with no subject, and every row was one except the deletions, which name
     * their ticket out of the snapshot they had to write anyway.
     *
     * One row per action rather than a couple of samples. The number lives in
     * the snapshot for two of the eight and nowhere for the other six, so a
     * fixture of hand-picked rows is exactly how six of them stay uncovered.
     */
    auditMock.mockResolvedValue(page(oneOfEach()))
    await open()

    expect(cellsOfEachRow().map((cells) => cells[1])).toEqual([
      '#100',
      '#101',
      '#102',
      '#103',
      '#104',
      '#105',
      '#106',
      '#107'
    ])
    // A column, not an extra cell per row. Dropping the heading alone leaves
    // five cells under four headings, which slides every value one column to
    // the left of the word that names it.
    expect(view().findAll('thead th').map((head) => head.text())).toEqual([
      'When',
      'Ticket',
      'Action',
      'Who',
      'What changed'
    ])
  })

  it('opens the ticket a row is about', async () => {
    // The id was in the response all along and the queue reads ?ticket=, so
    // the log needed the one thing that joins them up. In the portal the queue
    // is the admin-tickets route, and the hash router puts it after a #.
    auditMock.mockResolvedValue(page(oneOfEach()))
    await open()

    const links = view().findAll('tbody a')
    expect(links.map((link) => link.attributes('href'))).toEqual([
      '#/admin/tickets?ticket=100',
      '#/admin/tickets?ticket=101',
      '#/admin/tickets?ticket=102',
      '#/admin/tickets?ticket=103',
      '#/admin/tickets?ticket=104',
      '#/admin/tickets?ticket=105',
      '#/admin/tickets?ticket=106'
    ])
    expect(links[0]!.attributes('title')).toBe('Open ticket #100')
  })

  it('gives one ticket one name, whatever the row records', async () => {
    /**
     * The number is in the snapshot of a creation and of a deletion and
     * nowhere else. Naming those two by number and the other six by id
     * printed one ticket as SUP-2026-00250 on one row and #250 on the next,
     * with nothing on the screen saying the two rows were the same ticket.
     * The id is also the only one of the pair that every row carries, and the
     * two are not the same value: the counter restarts each year.
     *
     * The number is not dropped. A deletion still prints it under what
     * changed, that being the row whose ticket cannot be opened to read it.
     */
    auditMock.mockResolvedValue(
      page([
        row({
          id: 1,
          ticketId: 250,
          action: 'resolve',
          beforeState: { status: 'in_progress' },
          afterState: { status: 'resolved' }
        }),
        row({
          id: 2,
          ticketId: 250,
          action: 'delete',
          beforeState: { ticket_number: 'SUP-2026-00250', subject: 'Cannot access group workspace' },
          afterState: null
        }),
        row({
          id: 3,
          ticketId: 251,
          action: 'create',
          actor: null,
          beforeState: null,
          afterState: {
            channel: 'ai_screening',
            ticket_number: 'SUP-2026-00251',
            screening_category: 'self_harm'
          }
        })
      ])
    )
    await open()

    expect(cellsOfEachRow().map((cells) => cells[1])).toEqual(['#250', '#250', '#251'])
    expect(cellsOfEachRow().map((cells) => cells[4])).toEqual([
      'In progress → Resolved',
      'SUP-2026-00250 · Cannot access group workspace',
      'Flagged as Self harm'
    ])
  })

  it('spans the whole table with the rows that stand in for data', async () => {
    // Loading and empty each print one cell across the table. Both spans
    // were written for four columns, and the Ticket column made five: a span
    // left behind stops one column short of the edge.
    const answer = deferred<AuditPage>()
    auditMock.mockReturnValue(answer.promise)
    await open()

    const loadingCell = view().find('tbody td')
    expect(loadingCell.text()).toBe('Loading…')
    expect(loadingCell.attributes('colspan')).toBe('5')

    answer.resolve(page([]))
    await flushPromises()

    const emptyCell = view().find('tbody td')
    expect(emptyCell.text()).toBe('Nothing recorded for this filter.')
    expect(emptyCell.attributes('colspan')).toBe('5')
  })

  it('tells a row the platform wrote apart from one whose account is gone', async () => {
    /**
     * Two different things arrive as an empty actor. actor_user is SET_NULL,
     * so a row outlives the account that made it; and the screening handoff
     * writes its rows with no actor on purpose, because no person opened
     * those tickets. Calling the second one "Account removed" invented a
     * deleted account on the child-safety rows.
     *
     * Both kinds in one render on purpose. With only the screening row in the
     * fixture, printing "Automated screening" for every empty actor passes.
     */
    auditMock.mockResolvedValue(
      page([
        row({
          id: 1,
          action: 'create',
          actor: null,
          beforeState: null,
          afterState: {
            channel: 'ai_screening',
            ticket_number: 'SUP-2026-00262',
            screening_category: 'self_harm'
          }
        }),
        row({
          id: 2,
          action: 'resolve',
          actor: null,
          beforeState: { status: 'in_progress' },
          afterState: { status: 'resolved' }
        })
      ])
    )
    await open()

    expect(cellsOfEachRow().map((cells) => cells[3])).toEqual([
      'Automated screening',
      'Account removed'
    ])
  })

  it('says why the screener raised a ticket', async () => {
    // The row that most needs reading said "—". The verdict that raised it is
    // in the snapshot, and it is the only thing about that ticket this page
    // can show.
    auditMock.mockResolvedValue(
      page([
        row({
          action: 'create',
          actor: null,
          beforeState: null,
          afterState: {
            channel: 'ai_screening',
            ticket_number: 'SUP-2026-00262',
            screening_category: 'self_harm'
          }
        })
      ])
    )
    await open()

    expect(cellsOfEachRow().map((cells) => cells[4])).toEqual(['Flagged as Self harm'])
  })

  it('offers the requester who reopened their own ticket in the who filter', async () => {
    /**
     * The list came from the assignee roster, which answers a different
     * question: who can be handed a ticket. A requester is never on it, and a
     * requester replying to a resolved ticket is what writes a reopen row, so
     * every reopen row named somebody the filter beside it could not select.
     */
    auditMock.mockResolvedValue(
      page([
        row({
          action: 'reopen',
          actor: { id: 7, name: 'Grace Okafor' },
          beforeState: { status: 'resolved' },
          afterState: { status: 'open' }
        })
      ])
    )
    await open()

    // Added to the roster, not swapped for it: an agent with no rows on this
    // page is still somebody worth filtering for. Sorted by name.
    expect(optionNames(whoSelect())).toEqual(['Anyone', 'Grace Okafor', 'Sam Reid'])
  })

  it('asks the server for the person the reader picked, and for anyone again', async () => {
    auditMock.mockResolvedValue(
      page([row({ action: 'reopen', actor: { id: 7, name: 'Grace Okafor' } })])
    )
    await open()

    await whoSelect().setValue('7')
    await flushPromises()
    expect(lastAsked()).toEqual([1, 25, { action: '', actor: '7' }])

    await whoSelect().setValue('')
    await flushPromises()
    expect(lastAsked()).toEqual([1, 25, { action: '', actor: '' }])
  })

  it('keeps the person just picked on the list when nothing matches', async () => {
    // Picking somebody leaves only their rows on screen, and picking them
    // with an action they never did leaves none at all. The list is built
    // from the rows, so the selection has to be held separately or the option
    // disappears out of the control it was picked in.
    auditMock.mockResolvedValue(
      page([row({ action: 'reopen', actor: { id: 7, name: 'Grace Okafor' } })])
    )
    await open()

    auditMock.mockResolvedValue(page([]))
    await whoSelect().setValue('7')
    await flushPromises()

    expect(cellsOfEachRow()).toEqual([['Nothing recorded for this filter.']])
    expect(optionNames(whoSelect())).toEqual(['Anyone', 'Grace Okafor', 'Sam Reid'])
    expect((whoSelect().element as HTMLSelectElement).value).toBe('7')
  })

  it('says why the Created filter is the empty one', async () => {
    /**
     * Only the screening handoff writes a Created row. A ticket a requester
     * submits writes none, so this filter answers "nothing" on a platform
     * with a hundred tickets on it, and a bare empty table reads as a log
     * that has stopped recording.
     *
     * Both filters in one test: the sentence has to be about Created and not
     * about every empty result.
     */
    auditMock.mockResolvedValue(page([]))
    await open()

    await actionSelect().setValue('create')
    await flushPromises()

    expect(view().find('tbody td').text()).toBe(
      'Nothing recorded for this filter. Only the automated screening writes a Created row. A ticket somebody submitted from the portal does not write one.'
    )

    await actionSelect().setValue('delete')
    await flushPromises()

    expect(view().find('tbody td').text()).toBe('Nothing recorded for this filter.')
  })

  it('tells the reader the record is about deletions surviving the ticket', async () => {
    auditMock.mockResolvedValue(page([]))
    await open()

    // An h2, not a second h1: TicketsSection's h1 is the page's only one.
    expect(view().find('h1').exists()).toBe(false)
    expect(view().find('h2').text()).toBe('Ticket audit')
    expect(view().find('.ticket-audit__subtitle').text()).toBe(
      'Every recorded action, including deletions. A deleted ticket keeps its record here after it has left the queue.'
    )
  })

  it('tells a refused reader they lack access, not that something broke', async () => {
    /**
     * A student who types this address reaches the page and the server
     * answers 403. "The audit log could not be loaded" sends them looking for
     * a fault in a product that is working exactly as intended.
     */
    vi.spyOn(console, 'warn').mockImplementation(() => {})
    auditMock.mockRejectedValue(
      new ApiError(
        {
          error: 'You do not have support privileges.',
          code: 'permission_denied',
          request_id: 'r-403'
        },
        403
      )
    )
    await open()

    expect(view().find('[role="alert"]').text()).toBe(
      'You do not have access to the ticket audit. It is open to the support team and to administrators.'
    )
    // The line replaces the table and its footer rather than sitting above an
    // empty table that reads as "nothing happened".
    expect(view().find('table').exists()).toBe(false)
    expect(view().find('.audit-pager').exists()).toBe(false)
  })

  it('still reports a real fault as a fault', async () => {
    vi.spyOn(console, 'warn').mockImplementation(() => {})
    auditMock.mockRejectedValue(
      new ApiError(
        { error: 'Internal server error', code: 'server_error', request_id: 'r-500' },
        500
      )
    )
    await open()

    expect(view().find('[role="alert"]').text()).toBe('The audit log could not be loaded.')
    // The filters stay on screen, outside the alert's reach, as they did in
    // React: changing one is the only way to ask again from this page.
    expect(actionSelect().exists()).toBe(true)
    expect(whoSelect().exists()).toBe(true)
  })

  it('treats an answer that does not parse as a fault, not a refusal (new)', async () => {
    // The real fetchTicketAudit parses the answer, and a row the schema does
    // not accept throws there. That is a fault on our side, and it must not
    // blank the page or read as an access problem.
    vi.spyOn(console, 'warn').mockImplementation(() => {})
    auditMock.mockImplementation(async () =>
      ticketAuditPageSchema.parse({
        items: [{ ...row(), ticketId: '42' }],
        total: 1,
        page: 1,
        limit: 25,
        hasMore: false
      })
    )
    await open()

    expect(view().find('[role="alert"]').text()).toBe('The audit log could not be loaded.')
  })
})

describe('what changed, read off each row (new)', () => {
  it('runs the summary rules in the order delete, create, status, owner, priority, category', async () => {
    /**
     * The order is load-bearing and the backend depends on it. lifecycle.py
     * writes only the owner on an assign row because "the audit page
     * summarises a row by the first field it recognises, so a status key on
     * an assign row would print the status change and hide the change of
     * owner the row exists for".
     *
     * A cascade, so that swapping any two rules that can both match one row
     * turns this red, not only neighbours. Row n carries a key for its own
     * rule and for every rule after it, and nothing for the rules before it;
     * it must read as rule n. If rule j were moved in front of an earlier
     * rule i, the row for i also carries j's key and would read as j.
     *
     * The one pair this cannot tell apart is delete and create, and nothing
     * can: both key on the action itself, a row has one action, so no row
     * matches both and their order between themselves changes no output.
     */
    const everyKeyBefore = {
      ticket_number: 'SUP-2026-00042',
      subject: 'Cannot access group workspace',
      status: 'resolved',
      assignee_id: 4,
      priority: 'low',
      category: 'technical_issue'
    }
    const everyKeyAfter = {
      screening_category: 'self_harm',
      status: 'open',
      assignee_id: null,
      priority: 'high',
      category: 'registration'
    }
    auditMock.mockResolvedValue(
      page([
        // 1. delete, with every other rule's keys on it too.
        row({ id: 1, action: 'delete', beforeState: everyKeyBefore, afterState: everyKeyAfter }),
        // 2. create, likewise.
        row({ id: 2, action: 'create', beforeState: everyKeyBefore, afterState: everyKeyAfter }),
        // 3. status, carrying owner, priority and category as well.
        row({
          id: 3,
          action: 'status',
          beforeState: { status: 'resolved', assignee_id: 4, priority: 'low', category: 'technical_issue' },
          afterState: { status: 'open', assignee_id: null, priority: 'high', category: 'registration' }
        }),
        // 4. owner, carrying priority and category.
        row({
          id: 4,
          action: 'assign',
          beforeState: { assignee_id: null, priority: 'low', category: 'technical_issue' },
          afterState: { assignee_id: 4, priority: 'high', category: 'registration' }
        }),
        // 5. priority, carrying category.
        row({
          id: 5,
          action: 'priority',
          beforeState: { priority: 'low', category: 'technical_issue' },
          afterState: { priority: 'high', category: 'registration' }
        }),
        // 6. category alone.
        row({
          id: 6,
          action: 'category',
          beforeState: { category: 'technical_issue' },
          afterState: { category: 'registration' }
        })
      ])
    )
    await open()

    expect(cellsOfEachRow().map((cells) => cells[4])).toEqual([
      'SUP-2026-00042 · Cannot access group workspace',
      'Flagged as Self harm',
      'Resolved → Open',
      'Owner set to Sam Reid',
      'Low → High',
      'Technical issue → Registration'
    ])
  })

  it('reads a real reopen row as the status change and a real delete row as the deletion', async () => {
    // The two row shapes the backend actually writes with more than one
    // recognised key (lifecycle.py reopen and delete, as read on 2026-09-29).
    // A reopen clears the owner as well, and that is not what the row shows.
    auditMock.mockResolvedValue(
      page([
        row({
          id: 1,
          action: 'reopen',
          actor: { id: 7, name: 'Grace Okafor' },
          beforeState: { status: 'resolved', assignee_id: 4, resolved_at: '2026-09-01T09:00:00Z' },
          afterState: { status: 'open', assignee_id: null, resolved_at: null }
        }),
        row({
          id: 2,
          action: 'delete',
          beforeState: {
            ticket_number: 'SUP-2026-00042',
            subject: 'Cannot access group workspace',
            status: 'open',
            created_by_id: 7
          },
          afterState: { deleted_at: '2026-09-02T09:00:00Z' }
        })
      ])
    )
    await open()

    expect(cellsOfEachRow().map((cells) => cells[4])).toEqual([
      'Resolved → Open',
      'SUP-2026-00042 · Cannot access group workspace'
    ])
  })

  it('says what a re-filed ticket moved from and to', async () => {
    // Without this branch the row fell through to "—", so the one screen
    // whose job is being read said a change had happened and refused to say
    // what it was. Category words are the client's, not the stored keys, and
    // an empty side (a row from before screening carried a category) still
    // reads as something.
    auditMock.mockResolvedValue(
      page([
        row({
          id: 1,
          action: 'category',
          beforeState: { category: 'technical_issue' },
          afterState: { category: 'registration' }
        }),
        row({
          id: 2,
          action: 'category',
          beforeState: { category: 'flagged_content' },
          afterState: { category: 'help_student_group' }
        }),
        row({
          id: 3,
          action: 'category',
          beforeState: { category: '' },
          afterState: { category: 'general_question' }
        }),
        row({
          id: 4,
          action: 'category',
          beforeState: { category: 'other' },
          afterState: {}
        })
      ])
    )
    await open()

    expect(cellsOfEachRow().map((cells) => cells[4])).toEqual([
      'Technical issue → Registration',
      'Flagged content → Help with a student or group',
      'Not categorised → General Question',
      'Other → Not categorised'
    ])
  })

  it('writes a missing side of a status change as a dash, and an unknown status as stored', async () => {
    // Rule 3 reads the status off either side, so a row with one side only
    // still reads as a status change instead of falling through to "—". A
    // status this page has no word for is printed as the server sent it,
    // which beats a dash on the one screen that exists to be read.
    auditMock.mockResolvedValue(
      page([
        row({ id: 1, action: 'status', beforeState: null, afterState: { status: 'open' } }),
        row({ id: 2, action: 'status', beforeState: { status: 'resolved' }, afterState: {} }),
        row({
          id: 3,
          action: 'status',
          beforeState: { status: 'escalated' },
          afterState: { status: 'open' }
        })
      ])
    )
    await open()

    expect(cellsOfEachRow().map((cells) => cells[4])).toEqual([
      '— → Open',
      'Resolved → —',
      'escalated → Open'
    ])
  })

  it('says a ticket was opened when a creation carries no verdict, and a dash when nothing is recognised', async () => {
    // "Ticket opened" is unreachable while only screening writes Created rows,
    // but a creation row without a verdict must still read as one. A row no
    // rule recognises reads as a dash rather than as a blank cell. And a
    // priority on the after side alone is not a change: screening puts one
    // on every Created row, and rule 5 reads the before side only.
    auditMock.mockResolvedValue(
      page([
        row({ id: 1, action: 'create', beforeState: null, afterState: { channel: 'portal' } }),
        row({ id: 2, action: 'escalate', beforeState: {}, afterState: {} }),
        row({ id: 3, action: 'priority', beforeState: null, afterState: { priority: 'high' } })
      ])
    )
    await open()

    expect(cellsOfEachRow().map((cells) => cells[4])).toEqual(['Ticket opened', '—', '—'])
  })

  it('writes every action in words, and an unknown one as it was stored', async () => {
    // The Action column shares its wording with the detail panel's History
    // list. An unrecognised value comes back unchanged rather than as a
    // dash: the column exists to be read, and a stored word beats nothing.
    auditMock.mockResolvedValue(
      page([...oneOfEach(), row({ id: 9, ticketId: 109, action: 'escalate' })])
    )
    await open()

    expect(cellsOfEachRow().map((cells) => cells[2])).toEqual([
      'Created',
      'Assigned',
      'Status changed',
      'Priority changed',
      'Category changed',
      'Resolved',
      'Reopened',
      'Deleted',
      'escalate'
    ])
  })
})

describe('the filters above the audit table (new)', () => {
  it('starts on page 1 of 25 rows with no filter', async () => {
    auditMock.mockResolvedValue(page([]))
    await open()

    expect(auditMock.mock.calls).toEqual([[1, 25, { action: '', actor: '' }]])
  })

  it('offers every action the ticket module writes, and any action', async () => {
    auditMock.mockResolvedValue(page([]))
    await open()

    expect(optionNames(actionSelect())).toEqual([
      'Any action',
      'Created',
      'Assigned',
      'Status changed',
      'Priority changed',
      'Category changed',
      'Resolved',
      'Reopened',
      'Deleted'
    ])

    await actionSelect().setValue('status')
    await flushPromises()
    expect(lastAsked()).toEqual([1, 25, { action: 'status', actor: '' }])

    // "Any action" is an empty value, never a sentinel the server would
    // filter on and answer nothing for.
    await actionSelect().setValue('')
    await flushPromises()
    expect(lastAsked()).toEqual([1, 25, { action: '', actor: '' }])
  })

  it('sends both filters in one request, so they narrow together', async () => {
    // The server ANDs them. That only helps if both reach it at once: an
    // actor filter dropped when an action is picked would answer "anyone who
    // deleted something" to "did this person delete anything".
    auditMock.mockResolvedValue(
      page([row({ action: 'reopen', actor: { id: 7, name: 'Grace Okafor' } })])
    )
    await open()

    await whoSelect().setValue('7')
    await flushPromises()
    await actionSelect().setValue('delete')
    await flushPromises()

    expect(lastAsked()).toEqual([1, 25, { action: 'delete', actor: '7' }])
  })

  it('goes back to page 1 when either filter changes', async () => {
    // Page 3 of the old filter is rarely page 3 of the new one.
    auditMock.mockResolvedValue(page([row()], { total: 300, limit: 25, hasMore: true }))
    await open()

    await view().find('button[aria-label="Go to page 3"]').trigger('click')
    await flushPromises()
    expect(lastAsked()).toEqual([3, 25, { action: '', actor: '' }])

    await actionSelect().setValue('status')
    await flushPromises()
    expect(lastAsked()).toEqual([1, 25, { action: 'status', actor: '' }])

    await view().find('button[aria-label="Go to page 2"]').trigger('click')
    await flushPromises()
    expect(lastAsked()).toEqual([2, 25, { action: 'status', actor: '' }])

    await whoSelect().setValue('4')
    await flushPromises()
    expect(lastAsked()).toEqual([1, 25, { action: 'status', actor: '4' }])
  })
})

describe('the footer under the audit table', () => {
  it('counts the pages on the size the server served, not the one asked for', async () => {
    /**
     * views.py clamps limit to MAX_PAGE_SIZE, which is 100, and answers with
     * the size it actually used. The rows-per-page control offers 200.
     *
     * Counting on the asked-for size called 300 rows two pages of 200 while
     * the server was sending three pages of 100, and the hundred rows past
     * the end of page 2 could be reached from nowhere in the footer.
     */
    auditMock.mockResolvedValue(bigLog(100))
    await open()

    await sizeSelect().setValue('200')
    await flushPromises()

    expect(lastAsked()).toEqual([1, 200, { action: '', actor: '' }])
    expect(view().find('.audit-pager__info').text()).toBe('Page 1 of 3')
  })

  it('shows the served size in the control, rather than the size refused', async () => {
    // Left on 200 the control stands there naming a page size the server is
    // not honouring, on the same line as a page count that disagrees with it.
    auditMock.mockResolvedValue(bigLog(100))
    await open()

    await sizeSelect().setValue('200')
    await flushPromises()

    expect((sizeSelect().element as HTMLSelectElement).value).toBe('100')
  })

  it('goes back to the served size when the refused size is picked a second time (new)', async () => {
    // Asking for 200 again is asking for what is already asked for, so
    // nothing reloads and nothing re-renders the footer. The React Select was
    // controlled and kept reading 100; a select left to itself keeps the 200
    // the reader clicked, over a page of 100 rows.
    auditMock.mockResolvedValue(bigLog(100))
    await open()

    await sizeSelect().setValue('200')
    await flushPromises()
    expect((sizeSelect().element as HTMLSelectElement).value).toBe('100')

    await sizeSelect().setValue('200')
    await flushPromises()

    expect(auditMock).toHaveBeenCalledTimes(2)
    expect((sizeSelect().element as HTMLSelectElement).value).toBe('100')
  })

  it('names the size just picked while that page loads (new)', async () => {
    // What React showed: a new query had no served size yet and fell back to
    // the asked one. The previous answer's size would put the control back on
    // 25 for the length of the request, right after the reader picked 50.
    auditMock.mockResolvedValueOnce(page([row()], { total: 300, limit: 25, hasMore: true }))
    await open()
    const answer = deferred<AuditPage>()
    auditMock.mockReturnValueOnce(answer.promise)

    await sizeSelect().setValue('50')
    await flushPromises()
    expect(lastAsked()).toEqual([1, 50, { action: '', actor: '' }])
    expect((sizeSelect().element as HTMLSelectElement).value).toBe('50')

    answer.resolve(page([row()], { total: 300, limit: 50, hasMore: true }))
    await flushPromises()
    expect((sizeSelect().element as HTMLSelectElement).value).toBe('50')
    expect(view().find('.audit-pager__info').text()).toBe('Page 1 of 6')
  })

  it('keeps naming the served size while another page of that size loads (new)', async () => {
    // React fell back to the asked size whenever it had no answer for the
    // query, so after asking for 200 its control flicked to 200 while any
    // page it had not fetched before was on its way. Nothing about the size
    // changed, and the control has no reason to.
    auditMock.mockResolvedValue(bigLog(100))
    await open()
    await sizeSelect().setValue('200')
    await flushPromises()
    expect((sizeSelect().element as HTMLSelectElement).value).toBe('100')

    auditMock.mockReturnValue(new Promise<AuditPage>(() => {}))
    await view().find('button[aria-label="Go to page 2"]').trigger('click')
    await flushPromises()

    expect(lastAsked()).toEqual([2, 200, { action: '', actor: '' }])
    expect(cellsOfEachRow()).toEqual([['Loading…']])
    expect((sizeSelect().element as HTMLSelectElement).value).toBe('100')
  })

  it('asks for a custom size, and names the size the server served for it (new)', async () => {
    // The React control's Custom… box reaches 500 while the server stops at
    // 100. A size under the cap is served as asked and stays in the box; a
    // size over it comes back as 100, a preset, and the select returns to
    // name it.
    auditMock.mockImplementation(async (_page, limit) =>
      page([row()], { total: 300, limit: Math.min(limit, 100), hasMore: true })
    )
    await open()
    const box = () => view().find('.audit-pager input[type="number"]')

    await sizeSelect().setValue('custom')
    await flushPromises()
    await box().setValue('75')
    await box().trigger('keydown', { key: 'Enter' })
    await flushPromises()

    expect(lastAsked()).toEqual([1, 75, { action: '', actor: '' }])
    expect((box().element as HTMLInputElement).value).toBe('75')
    expect(view().find('.audit-pager__info').text()).toBe('Page 1 of 4')

    await box().setValue('300')
    await box().trigger('keydown', { key: 'Enter' })
    await flushPromises()

    expect(lastAsked()).toEqual([1, 300, { action: '', actor: '' }])
    expect(box().exists()).toBe(false)
    expect((sizeSelect().element as HTMLSelectElement).value).toBe('100')
    expect(view().find('.audit-pager__info').text()).toBe('Page 1 of 3')
  })

  it('counts on the size asked for when the server has not answered yet', async () => {
    // ⚠️ Load-bearing. There is no served size before the first response, and
    // a fallback of zero divides the total by nothing and offers Infinity
    // pages.
    auditMock.mockReturnValue(new Promise<AuditPage>(() => {}))
    await open()

    expect(view().find('.audit-pager__info').text()).toBe('Page 1 of 1')
    expect((sizeSelect().element as HTMLSelectElement).value).toBe('25')
  })

  it('keeps counting pages while the next page loads (new)', async () => {
    // React started every page from nothing, so going to page 3 of 12 read
    // "Page 3 of 1" until the answer came. The previous answer's rows are
    // still never shown meanwhile: the table says "Loading…" instead.
    auditMock.mockResolvedValueOnce(page([row()], { total: 300, limit: 25, hasMore: true }))
    await open()
    auditMock.mockReturnValue(new Promise<AuditPage>(() => {}))

    await view().find('button[aria-label="Go to page 3"]').trigger('click')
    await flushPromises()

    expect(view().find('.audit-pager__info').text()).toBe('Page 3 of 12')
    expect(cellsOfEachRow()).toEqual([['Loading…']])
  })

  it('still gives a page to a log with nothing in it', async () => {
    auditMock.mockResolvedValue(page([], { total: 0, limit: 25 }))
    await open()

    expect(view().find('.audit-pager__info').text()).toBe('Page 1 of 1')
  })

  it('goes back to page 1 when the page size changes (new)', async () => {
    auditMock.mockResolvedValue(page([row()], { total: 300, limit: 25, hasMore: true }))
    await open()

    await view().find('button[aria-label="Go to page 4"]').trigger('click')
    await flushPromises()
    expect(lastAsked()).toEqual([4, 25, { action: '', actor: '' }])

    await sizeSelect().setValue('50')
    await flushPromises()
    expect(lastAsked()).toEqual([1, 50, { action: '', actor: '' }])
  })

  it('holds the page buttons still while a page loads (new)', async () => {
    // One click, one request. The buttons stay focusable (aria-disabled, not
    // disabled) so a keyboard reader who pressed Next keeps their place.
    auditMock.mockResolvedValueOnce(page([row()], { total: 300, limit: 25, hasMore: true }))
    await open()
    auditMock.mockReturnValue(new Promise<AuditPage>(() => {}))

    await view().find('button[aria-label="Go to page 2"]').trigger('click')
    await flushPromises()
    expect(auditMock).toHaveBeenCalledTimes(2)

    const buttons = view().findAll('.audit-pager button')
    expect(buttons.map((button) => [button.text(), button.attributes('aria-disabled')])).toEqual([
      ['Previous', 'true'],
      ['1', 'true'],
      ['2', 'true'],
      ['3', 'true'],
      ['4', 'true'],
      ['12', 'true'],
      ['Next', 'true']
    ])
    expect(buttons.every((button) => button.attributes('disabled') === undefined)).toBe(true)

    for (const button of buttons) await button.trigger('click')
    await flushPromises()
    expect(auditMock).toHaveBeenCalledTimes(2)
  })
})

describe('loading the audit log (new)', () => {
  it('asks again every time the page opens, rather than showing a remembered answer', async () => {
    // The React page cached each answer for the session, so coming back to a
    // page already seen showed it without a deletion made in the meantime.
    auditMock.mockResolvedValue(page([row({ id: 1, ticketId: 42 })]))
    await open()
    wrapper!.unmount()

    auditMock.mockResolvedValue(
      page([
        row({
          id: 2,
          ticketId: 42,
          action: 'delete',
          beforeState: { ticket_number: 'SUP-2026-00042', subject: 'Cannot access group workspace' },
          afterState: null
        }),
        row({ id: 1, ticketId: 42 })
      ])
    )
    await open()

    expect(auditMock).toHaveBeenCalledTimes(2)
    expect(cellsOfEachRow().map((cells) => cells[2])).toEqual(['Deleted', 'Status changed'])
  })

  it('keeps a slower, older answer from painting over a newer one', async () => {
    // Two filter changes in a row leave two requests in flight. If the first
    // one answers last it must not win: that would put one filter's rows
    // under another filter's name.
    auditMock.mockResolvedValueOnce(page([]))
    await open()

    const slow = deferred<AuditPage>()
    const fast = deferred<AuditPage>()
    auditMock.mockReturnValueOnce(slow.promise).mockReturnValueOnce(fast.promise)

    await actionSelect().setValue('status')
    await actionSelect().setValue('delete')

    fast.resolve(
      page([
        row({
          id: 2,
          action: 'delete',
          beforeState: { ticket_number: 'SUP-2026-00042', subject: 'Cannot access group workspace' },
          afterState: null
        })
      ])
    )
    await flushPromises()
    slow.resolve(page([row({ id: 1, action: 'status' })]))
    await flushPromises()

    expect(cellsOfEachRow().map((cells) => cells[2])).toEqual(['Deleted'])
  })

  it('recovers from a failed load as soon as a filter changes', async () => {
    // The filters are the only way to try again from this page. React
    // recovered because a new filter was a new query with no error on it;
    // here the alert has to be taken down by hand at the start of every load,
    // or one failure leaves "could not be loaded" on screen until the reader
    // navigates away, whatever the server answers next.
    vi.spyOn(console, 'warn').mockImplementation(() => {})
    auditMock.mockRejectedValueOnce(
      new ApiError({ error: 'Internal server error', code: 'server_error', request_id: 'r' }, 500)
    )
    await open()
    expect(view().find('[role="alert"]').text()).toBe('The audit log could not be loaded.')

    const retry = deferred<AuditPage>()
    auditMock.mockReturnValueOnce(retry.promise)
    await actionSelect().setValue('status')
    await flushPromises()

    // Gone while the new answer is on its way, not only once it lands.
    expect(view().find('[role="alert"]').exists()).toBe(false)
    expect(cellsOfEachRow()).toEqual([['Loading…']])

    retry.resolve(page([row({ id: 1, action: 'status' })]))
    await flushPromises()

    expect(view().find('[role="alert"]').exists()).toBe(false)
    expect(cellsOfEachRow().map((cells) => cells[2])).toEqual(['Status changed'])
  })

  it('does not let an older request that fails late replace a newer answer', async () => {
    // The failing half of the race above. The newer filter's rows are what
    // the reader asked for last, and an error from a request they have since
    // moved on from would take the table away from under them.
    vi.spyOn(console, 'warn').mockImplementation(() => {})
    auditMock.mockResolvedValueOnce(page([]))
    await open()

    const slow = deferred<AuditPage>()
    const fast = deferred<AuditPage>()
    auditMock.mockReturnValueOnce(slow.promise).mockReturnValueOnce(fast.promise)

    await actionSelect().setValue('status')
    await actionSelect().setValue('delete')

    fast.resolve(
      page([
        row({
          id: 2,
          action: 'delete',
          beforeState: { ticket_number: 'SUP-2026-00042', subject: 'Cannot access group workspace' },
          afterState: null
        })
      ])
    )
    await flushPromises()
    slow.reject(
      new ApiError({ error: 'Internal server error', code: 'server_error', request_id: 'r' }, 500)
    )
    await flushPromises()

    expect(view().find('[role="alert"]').exists()).toBe(false)
    expect(cellsOfEachRow().map((cells) => cells[2])).toEqual(['Deleted'])
  })

  it('keeps loading until the newest request answers, even when an older one lands first', async () => {
    // An older answer that arrives first is thrown away, and it must not end
    // the loading state on its way out either. If it did, the rows from
    // before the change would come back on screen under the new filter's
    // name while the request for that filter is still out.
    auditMock.mockResolvedValueOnce(
      page([row({ id: 9, action: 'reopen', actor: { id: 7, name: 'Grace Okafor' } })])
    )
    await open()

    const slow = deferred<AuditPage>()
    const fast = deferred<AuditPage>()
    auditMock.mockReturnValueOnce(slow.promise).mockReturnValueOnce(fast.promise)

    await actionSelect().setValue('status')
    await actionSelect().setValue('delete')

    slow.resolve(page([row({ id: 1, action: 'status' })]))
    await flushPromises()

    expect(cellsOfEachRow()).toEqual([['Loading…']])
    expect(view().find('table').attributes('aria-busy')).toBe('true')

    fast.resolve(
      page([
        row({
          id: 2,
          action: 'delete',
          beforeState: { ticket_number: 'SUP-2026-00042', subject: 'Cannot access group workspace' },
          afterState: null
        })
      ])
    )
    await flushPromises()

    expect(cellsOfEachRow().map((cells) => cells[2])).toEqual(['Deleted'])
    expect(view().find('table').attributes('aria-busy')).toBeUndefined()
  })

  it('hands focus to the alert when a failed page change takes the footer away', async () => {
    // The alert replaces the footer, so the page button the reader pressed is
    // removed from under them. Left there, focus falls to the top of the
    // document and a keyboard reader starts the page over.
    vi.spyOn(console, 'warn').mockImplementation(() => {})
    auditMock.mockResolvedValueOnce(page([row()], { total: 300, limit: 25, hasMore: true }))
    await open({ attach: true })
    auditMock.mockRejectedValueOnce(
      new ApiError({ error: 'Internal server error', code: 'server_error', request_id: 'r' }, 500)
    )

    const three = view().find('button[aria-label="Go to page 3"]')
    ;(three.element as HTMLButtonElement).focus()
    await three.trigger('click')
    await flushPromises()

    const alert = view().find('[role="alert"]')
    expect(alert.text()).toBe('The audit log could not be loaded.')
    expect(alert.attributes('tabindex')).toBe('-1')
    expect(document.activeElement).toBe(alert.element)
  })

  it('leaves focus on the filter when a filter change fails', async () => {
    // The filters stay on screen through a failure, so there is nothing to
    // rescue, and pulling focus off the control the reader is using would be
    // a move they did not make.
    vi.spyOn(console, 'warn').mockImplementation(() => {})
    auditMock.mockResolvedValueOnce(page([row()], { total: 300, limit: 25, hasMore: true }))
    await open({ attach: true })
    auditMock.mockRejectedValueOnce(
      new ApiError({ error: 'Internal server error', code: 'server_error', request_id: 'r' }, 500)
    )

    ;(actionSelect().element as HTMLSelectElement).focus()
    await actionSelect().setValue('status')
    await flushPromises()

    expect(view().find('[role="alert"]').exists()).toBe(true)
    expect(document.activeElement).toBe(actionSelect().element)
  })

  it('still names owners by id when the roster cannot be loaded', async () => {
    // The roster only turns ids into names. Losing it costs the names, not
    // the page, and it is not worth an alert over rows that still read.
    vi.spyOn(console, 'warn').mockImplementation(() => {})
    assigneesMock.mockRejectedValue(
      new ApiError({ error: 'Internal server error', code: 'server_error', request_id: 'r' }, 500)
    )
    auditMock.mockResolvedValue(
      page([
        row({
          action: 'assign',
          actor: { id: 5, name: 'Ada Lin' },
          beforeState: { assignee_id: null },
          afterState: { assignee_id: 4 }
        })
      ])
    )
    await open()

    expect(cellsOfEachRow().map((cells) => cells[4])).toEqual(['Owner set to #4'])
    expect(view().find('[role="alert"]').exists()).toBe(false)
    expect(optionNames(whoSelect())).toEqual(['Anyone', 'Ada Lin'])
  })
})

describe('the times the audit table prints', () => {
  it('names the time zone', async () => {
    // Rendered in whatever zone the reader's machine is in, so the same row
    // reads 03:37 pm in Sydney and 02:37 am in Sao Paulo. This is the screen
    // people quote timestamps off when they compare notes about what
    // happened and when.
    const WHEN = '2026-09-01T09:00:00Z'
    auditMock.mockResolvedValue(page([row({ createdAt: WHEN })]))
    await open()

    const stamp = {
      day: 'numeric',
      month: 'short',
      year: 'numeric',
      hour: '2-digit',
      minute: '2-digit'
    } as const
    // Built from the clock this machine is on rather than matched against a
    // list of zone spellings. The short name is "UTC" here, "AEST" in Sydney,
    // "GMT-3" in Sao Paulo and "GMT+5:30" in Kolkata, and a hand-written list
    // of those turns the suite red on whichever machine it happens to miss.
    const withoutZone = new Date(WHEN).toLocaleString('en-AU', stamp)
    const withZone = new Date(WHEN).toLocaleString('en-AU', { ...stamp, timeZoneName: 'short' })

    const printed = view().find('tbody td').element.textContent ?? ''
    expect(printed).toBe(withZone)
    // The zone name is an addition, not a replacement: the timestamp is still
    // in front of it, and there is something after it.
    expect(withZone.startsWith(withoutZone)).toBe(true)
    expect(printed).not.toBe(withoutZone)
  })
})
