import { describe, expect, it } from 'vitest'

import {
  TICKET_CATEGORIES,
  categoryLabel as requesterCategoryLabel,
  priorityLabel as requesterPriorityLabel
} from '@/utils/supportAPI'
import {
  TICKET_CATEGORY_OPTIONS,
  TICKET_PRIORITY_LABELS,
  TICKET_STATUS_LABELS,
  UNASSIGNED,
  UNKNOWN_REGION,
  accountStatusNote,
  assigneeOptionSchema,
  auditActionLabel,
  auditActorName,
  categoryLabel,
  supportAgentSchema,
  ticketDetailSchema,
  ticketQueueSchema,
  ticketRowSchema,
  ticketSummarySchema
} from '@/utils/ticketAgentSchema'

// Ported from adminweb/src/schema/ticket.test.ts, case for case, plus the two
// checks that only became possible once both vocabularies lived in one app.

// A ticket raised by the platform's own message screening has no requester at
// all: created_by is null, so the row comes back with user.name === null. A
// non-nullable name here would fail the whole array and empty the queue with
// no error anyone would see.
const SCREENING_ROW = {
  id: 88,
  ticketNumber: 'SUP-2026-00042',
  user: { name: null, region: '', anonymous: false },
  subject: 'AI screening: personal_contact — group "Team Photosynthesis"',
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
  assignee: { id: 4, name: 'Sam Reid' }
}

describe('the queue row tolerates a ticket with no requester', () => {
  it('accepts a screening-raised row', () => {
    expect(() => ticketRowSchema.parse(SCREENING_ROW)).not.toThrow()
  })

  it('does not let one such row empty the whole page', () => {
    const parsed = ticketQueueSchema.parse({
      items: [SCREENING_ROW, HUMAN_ROW],
      total: 2,
      page: 1,
      limit: 10,
      hasMore: false,
      asOf: '2026-09-02T04:00:00Z',
      after: '2026-09-02T04:00:00Z_89'
    })
    expect(parsed.items).toHaveLength(2)
  })

  // Each half of the walk gets its own case, and each case leaves the other
  // half present. Dropping one key from a payload that is missing both proves
  // nothing: the parse throws either way, so a test written that way goes on
  // passing after the key it names has been made optional.
  it('requires the snapshot stamp, because paging without it loses rows', () => {
    expect(() =>
      ticketQueueSchema.parse({
        items: [],
        total: 0,
        page: 1,
        limit: 10,
        hasMore: false,
        after: null
      })
    ).toThrow()
  })

  it('requires the cursor, because a snapshot alone does not hold a place', () => {
    // The server ignores a snapshot that arrives without a cursor: it will not
    // page by offset inside a frozen set, because a frozen set still shrinks
    // when somebody works a ticket. A payload with no cursor leaves Next with
    // nothing to send, and the walk silently becomes what it was before.
    expect(() =>
      ticketQueueSchema.parse({
        items: [],
        total: 0,
        page: 1,
        limit: 10,
        hasMore: false,
        asOf: '2026-09-02T04:00:00Z'
      })
    ).toThrow()
  })

  it('accepts a null cursor on an empty page', () => {
    // There is no last row to continue from, and inventing one would point the
    // next request at something that does not exist.
    expect(() =>
      ticketQueueSchema.parse({
        items: [],
        total: 0,
        page: 1,
        limit: 10,
        hasMore: false,
        asOf: '2026-09-02T04:00:00Z',
        after: null
      })
    ).not.toThrow()
  })

  it('keeps anonymous false on a screening row', () => {
    // Anonymous submission was never built. The only tickets without a
    // requester are the ones the platform raises, and labelling those
    // "anonymous" in the queue would be telling agents something untrue.
    expect(ticketRowSchema.parse(SCREENING_ROW).user.anonymous).toBe(false)
  })

  it('refuses a status nobody has handled, instead of rendering a blank cell', () => {
    expect(() => ticketRowSchema.parse({ ...HUMAN_ROW, status: 'escalated' })).toThrow()
  })
})

describe('the detail schema', () => {
  it('accepts a ticket that has never been answered or resolved', () => {
    const detail = {
      ...HUMAN_ROW,
      body: 'I get an error opening my group.',
      category: 'help_student_group',
      channel: 'portal',
      region: 'Australia',
      requester: {
        id: 1,
        name: 'Mia Thompson',
        email: 'mia@example.com',
        region: 'Australia',
        registeredAt: '2026-05-01T00:00:00Z'
      },
      createdAt: '2026-08-25T09:00:00Z',
      updatedAt: '2026-08-25T09:00:00Z',
      supportUpdatedAt: '2026-08-25T09:00:00Z',
      firstResponseAt: null,
      resolvedAt: null,
      messages: []
    }
    expect(() => ticketDetailSchema.parse(detail)).not.toThrow()
  })
})

describe('the counter cards', () => {
  it('expects the four keys the summary endpoint returns', () => {
    const parsed = ticketSummarySchema.parse({
      unassigned: 12,
      open: 38,
      pendingUser: 17,
      overdue: 4
    })
    expect(Object.keys(parsed).sort()).toEqual(['open', 'overdue', 'pendingUser', 'unassigned'])
  })
})

describe('the category filter', () => {
  /**
   * This list drives the queue's category filter, so it holds every category
   * a ticket can carry — including the one no requester can pick.
   *
   * What this list must not do is *omit* a category, because a bucket support
   * cannot filter for is a bucket they cannot work through — which is exactly
   * what happened while screening tickets carried an empty category.
   */
  it("offers every category a ticket can carry, screening's included", () => {
    const values = TICKET_CATEGORY_OPTIONS.map((c) => c.value)
    expect(values).toEqual([
      'account_access',
      'registration',
      'help_student_group',
      'help_mentor',
      'technical_issue',
      'certificates_records',
      'general_question',
      'other',
      'flagged_content'
    ])
  })

  it("matches the portal's eight, plus screening's one", () => {
    /* The first eight must be the requester's list in the requester's order:
     * this array builds the queue's category filter AND the re-file control on
     * the detail panel, so a value here the backend does not accept is a
     * dropdown entry that 400s when an agent picks it. In adminweb this was a
     * triangle checked from three places; with both lists in the portal the
     * two front-end corners can now be compared directly. */
    expect(TICKET_CATEGORY_OPTIONS.slice(0, 8)).toEqual(
      TICKET_CATEGORIES.map(({ value, label }) => ({ value, label }))
    )
    expect(TICKET_CATEGORY_OPTIONS[8].value).toBe('flagged_content')
    expect(TICKET_CATEGORY_OPTIONS.map((c) => c.value)).not.toContain('programs_groups')
  })
})

describe('categoryLabel', () => {
  it('gives the wording the requester chose from, not the stored value', () => {
    expect(categoryLabel('account_access')).toBe('Account and access')
    expect(categoryLabel('help_student_group')).toBe('Help with a student or group')
    // The client's own capitalisation. Sentence case everywhere else.
    expect(categoryLabel('general_question')).toBe('General Question')
  })

  it('names the empty case instead of showing a dash', () => {
    // Screening raises tickets with no category yet. A dash there reads like
    // something failed to load.
    expect(categoryLabel('')).toBe('Not categorised')
  })

  it('falls back to the raw value if a category is added server-side first', () => {
    expect(categoryLabel('safeguarding')).toBe('safeguarding')
  })
})

describe('two vocabularies, on purpose', () => {
  // The queue speaks triage; the requester's own page does not. Both labels
  // for the same stored value are pinned here so neither side can quietly
  // borrow the other's.
  it('calls screening\'s category "Flagged content" in the queue and never on a student\'s page', () => {
    expect(categoryLabel('flagged_content')).toBe('Flagged content')
    expect(requesterCategoryLabel('flagged_content')).toBe('Under review')
  })

  it('names priority and status as the queue does', () => {
    expect(TICKET_PRIORITY_LABELS).toEqual({ high: 'High', normal: 'Normal', low: 'Low' })
    expect(TICKET_STATUS_LABELS).toEqual({
      open: 'Open',
      in_progress: 'In progress',
      pending_user: 'Pending user',
      resolved: 'Resolved'
    })
    // The short badge form on the requester side agrees on priority; the
    // form's long wording ("I cannot continue") is not the queue's business.
    expect(requesterPriorityLabel('high')).toBe(TICKET_PRIORITY_LABELS.high)
  })
})

describe('the assignee option', () => {
  // `assignable` is the only thing standing between the assign dropdown and a
  // name the write path will refuse with a 400.
  const ROW = { id: 7, name: 'Rex Voke', assignable: false }

  it('keeps a false through the parse instead of widening it', () => {
    expect(assigneeOptionSchema.parse(ROW).assignable).toBe(false)
  })

  it('refuses a row with no assignable rather than assuming yes', () => {
    // It used to be `z.boolean().default(true)`. The endpoint always sends the
    // key, so that default could only fire when something upstream broke — and
    // it answered "assignable" for everybody, silently re-offering the people
    // the flag exists to keep out. Failing here is the safe direction.
    const withoutTheFlag: Record<string, unknown> = { ...ROW }
    delete withoutTheFlag.assignable
    expect(assigneeOptionSchema.safeParse(withoutTheFlag).success).toBe(false)
  })

  it('accepts the shape the endpoint actually sends', () => {
    expect(assigneeOptionSchema.parse({ id: 3, name: 'Ada Byron', assignable: true })).toEqual({
      id: 3,
      name: 'Ada Byron',
      assignable: true
    })
  })
})

describe('the support roster row', () => {
  const ROW = {
    id: 4,
    name: 'Sam Reid',
    email: 'sam@example.com',
    openTickets: 3,
    accountStatus: 'active'
  }

  it('keeps the account status instead of dropping it on the floor', () => {
    // zod strips a key the schema does not name, silently. The endpoint has
    // sent accountStatus since the grant guard went in, and the schema not
    // naming it meant the roster screen could not have shown it if it had
    // tried: nothing downstream ever saw the field.
    expect(supportAgentSchema.parse(ROW).accountStatus).toBe('active')
  })

  it('refuses a row with no status rather than treating it as fine', () => {
    // The alternative was a default of "active", which is the answer that
    // hides the case the field exists for.
    const withoutIt: Record<string, unknown> = { ...ROW }
    delete withoutIt.accountStatus
    expect(supportAgentSchema.safeParse(withoutIt).success).toBe(false)
  })

  it('takes a status it has no word for, rather than emptying the table', () => {
    // Not an enum on purpose. account_status belongs to the users app and may
    // gain a value for reasons that have nothing to do with support; failing
    // the parse would take the whole roster off the screen over a word this
    // page only reads.
    expect(supportAgentSchema.parse({ ...ROW, accountStatus: 'archived' }).accountStatus).toBe(
      'archived'
    )
  })
})

describe('accountStatusNote', () => {
  it('marks the statuses that cannot sign in', () => {
    expect(accountStatusNote('deactivated')).toBe('Deactivated')
    expect(accountStatusNote('suspended')).toBe('Suspended')
  })

  it('leaves invited and pending unmarked, because they can sign in', () => {
    // is_active is false for these two as well, which is why the mark cannot
    // be driven off is_active. INACTIVE_LOGIN_STATUSES leaves them out and
    // the grant endpoint accepts them, so marking them invents a problem and
    // contradicts the server in the same breath.
    expect(accountStatusNote('invited')).toBeNull()
    expect(accountStatusNote('pending')).toBeNull()
  })

  it('says nothing about an ordinary account or an unknown status', () => {
    expect(accountStatusNote('active')).toBeNull()
    expect(accountStatusNote('archived')).toBeNull()
  })
})

describe('naming the actor on an audit row', () => {
  // One function because two screens print these rows: the audit page's Who
  // column and the History list on the detail panel. They said "Account
  // removed" and "system" about the same row before this existed.

  it('names the person when the row still has one', () => {
    expect(auditActorName({ name: 'Ada Lin' }, null)).toBe('Ada Lin')
  })

  it('does not invent a deleted account on a row the platform wrote', () => {
    // handoff.py is the only writer in the ticket module that passes
    // actor=None, and its rows carry the channel in their own snapshot. These
    // are the child-safety rows.
    expect(auditActorName(null, { channel: 'ai_screening' })).toBe('Automated screening')
  })

  it('says the account is gone on a row that had a person', () => {
    // Every other row had a real actor when it was written, so an empty one
    // here is AuditLog.actor_user having been SET_NULL by the delete.
    expect(auditActorName(null, { status: 'resolved' })).toBe('Account removed')
  })

  it('survives a row with no snapshot at all', () => {
    expect(auditActorName(null, null)).toBe('Account removed')
  })
})

describe('auditActionLabel', () => {
  it('gives the stored action as words', () => {
    expect(auditActionLabel('status')).toBe('Status changed')
    expect(auditActionLabel('create')).toBe('Created')
  })

  it('falls back to the stored value rather than to a dash', () => {
    // log_audit_event does not validate against the model's own choices, so a
    // value nobody listed here is possible. A screen whose job is being read
    // prints the word it was given rather than nothing.
    expect(auditActionLabel('escalate')).toBe('escalate')
  })
})

describe('the filter sentinels', () => {
  // Both must match backend/apps/tickets/services/queue.py character for
  // character: they travel as ordinary query values.
  it('spells the unassigned and unknown-region buckets as the server does', () => {
    expect(UNASSIGNED).toBe('__unassigned__')
    expect(UNKNOWN_REGION).toBe('__unknown__')
  })
})
