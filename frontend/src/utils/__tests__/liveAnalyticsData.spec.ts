import { beforeEach, describe, expect, it, vi } from 'vitest'
import * as api from '@/utils/liveAnalyticsApi'
import * as data from '@/utils/liveAnalyticsData'

vi.mock('@/utils/liveAnalyticsApi', () => ({
  fetchAllUsers: vi.fn(), fetchAllGroups: vi.fn(), fetchMentors: vi.fn(),
  fetchGroupActivity: vi.fn(), fetchLoginActivity: vi.fn(),
  fetchResourceAnalytics: vi.fn(), fetchEmailDeliveryAnalytics: vi.fn(), fetchAllResources: vi.fn(),
}))

const fullActivity: api.GroupActivityResponse = {
  messages_by_group: [
    { group_id: 1, group_name: 'Alpha', message_count: 5 },
    { group_id: 2, group_name: 'Beta', message_count: 0 },
  ],
  messages_by_user: [
    { user_id: 10, name: 'Ava', message_count: 5 },
    { user_id: 11, name: 'Ben', message_count: 0 },
  ],
  messages_by_day: [
    { date: '2026-10-01', message_count: 2 },
    { date: '2026-10-05', message_count: 3 },
  ],
  messages_by_group_by_day: [
    { date: '2026-10-01', group_id: 1, group_name: 'Alpha', message_count: 2 },
    { date: '2026-10-05', group_id: 1, group_name: 'Alpha', message_count: 3 },
  ],
  messages_by_user_by_group_by_day: [
    { date: '2026-10-01', user_id: 10, name: 'Ava', group_id: 1, group_name: 'Alpha', message_count: 2 },
    { date: '2026-10-05', user_id: 10, name: 'Ava', group_id: 1, group_name: 'Alpha', message_count: 3 },
  ],
  mentor_activity_by_day: [
    { mentor_id: 20, date: '2026-10-01', messages: 1, logins: 0 },
    { mentor_id: 20, date: '2026-10-05', messages: 1, logins: 1 },
  ],
  mentor_count: 1,
  student_count: 1,
  students_per_mentor: 1,
  query_range: { start: null, end: null },
}

beforeEach(() => {
  vi.resetAllMocks()
  data.clearLiveAnalyticsCache()
})

describe('sliceGroupActivity', () => {
  it('derives a date range like the API, keeping zero-count groups and members', () => {
    const range = data.sliceGroupActivity(fullActivity, '2026-10-04', '2026-10-10')!

    expect(range.messages_by_group).toEqual([
      { group_id: 1, group_name: 'Alpha', message_count: 3 },
      { group_id: 2, group_name: 'Beta', message_count: 0 },
    ])
    expect(range.messages_by_user).toEqual([
      { user_id: 10, name: 'Ava', message_count: 3 },
      { user_id: 11, name: 'Ben', message_count: 0 },
    ])
    expect(range.messages_by_day).toEqual([{ date: '2026-10-05', message_count: 3 }])
    expect(range.mentor_activity_by_day).toEqual([{ mentor_id: 20, date: '2026-10-05', messages: 1, logins: 1 }])
    expect(range.query_range).toEqual({ start: '2026-10-04', end: '2026-10-10' })
  })

  it('needs the per-user daily breakdown to slice on the client', () => {
    const older = { ...fullActivity, messages_by_user_by_group_by_day: undefined }
    expect(data.sliceGroupActivity(older, '2026-10-04', '2026-10-10')).toBeNull()
  })

  it('answers range changes without a request when the full data is loaded', async () => {
    await data.groupActivityForRange(fullActivity, '2026-10-01', '2026-10-01')
    expect(api.fetchGroupActivity).not.toHaveBeenCalled()
  })
})

describe('shared analytics cache', () => {
  it('lets pages share a source instead of requesting it again', async () => {
    vi.mocked(api.fetchAllUsers).mockResolvedValue([])
    vi.mocked(api.fetchAllGroups).mockResolvedValue([])
    vi.mocked(api.fetchGroupActivity).mockResolvedValue(fullActivity)
    vi.mocked(api.fetchLoginActivity).mockRejectedValue(new Error('offline'))

    await data.loadGroupsAnalyticsBundle()
    await data.loadMessagesAnalyticsBundle()
    await data.loadActivityAnalyticsBundle()

    expect(api.fetchAllUsers).toHaveBeenCalledTimes(1)
    expect(api.fetchAllGroups).toHaveBeenCalledTimes(1)
    expect(api.fetchGroupActivity).toHaveBeenCalledTimes(1)
  })

  it('reuses a date range response and retries a failed one', async () => {
    vi.mocked(api.fetchLoginActivity)
      .mockRejectedValueOnce(new Error('offline'))
      .mockResolvedValue({
        by_day: [], by_year: [], active_users: { daily: 0, weekly: 0, monthly: 0 },
        latest_activity_date: null, query_range: { start: '2026-08-01', end: '2026-10-01' },
      })

    await expect(data.loadLoginActivityRange('2026-08-01', '2026-10-01')).rejects.toThrow('offline')
    await data.loadLoginActivityRange('2026-08-01', '2026-10-01')
    await data.loadLoginActivityRange('2026-08-01', '2026-10-01')

    expect(api.fetchLoginActivity).toHaveBeenCalledTimes(2)
    expect(api.fetchLoginActivity).toHaveBeenLastCalledWith('2026-08-01', '2026-10-01')
  })

  it('warms every source so Analytics pages open from the cache', async () => {
    for (const fetcher of [
      api.fetchAllUsers, api.fetchAllGroups, api.fetchMentors, api.fetchAllResources,
    ]) vi.mocked(fetcher).mockResolvedValue([])
    vi.mocked(api.fetchGroupActivity).mockResolvedValue(fullActivity)
    vi.mocked(api.fetchLoginActivity).mockRejectedValue(new Error('offline'))
    vi.mocked(api.fetchResourceAnalytics).mockRejectedValue(new Error('offline'))
    vi.mocked(api.fetchEmailDeliveryAnalytics).mockRejectedValue(new Error('offline'))

    await data.prefetchAnalytics()
    await data.loadMentorsAnalyticsBundle()

    expect(api.fetchMentors).toHaveBeenCalledTimes(1)
    expect(api.fetchAllUsers).toHaveBeenCalledTimes(1)
  })
})

describe('buildGroupsAnalytics', () => {
  it('buckets group size from 0 to 5 students and flags groups above the limit', () => {
    const member = (id: number, role = 'student') => ({ id: String(id), name: `M${id}`, email: '', role, membershipId: id })
    const group = (id: string, studentCount: number) => ({
      id, name: id, createdAt: '', updatedAt: '', mentor: null,
      members: [...Array.from({ length: studentCount }, (_, index) => member(index)), member(99, 'mentor')],
    })
    const result = data.buildGroupsAnalytics({
      users: [],
      groups: [group('a', 0), group('b', 5), group('c', 6)],
      groupActivity: fullActivity,
    }, 2026)

    expect(result.groupSizeDistribution.map((bucket) => bucket.label)).toEqual(['0', '1', '2', '3', '4', '5', 'Over 5'])
    expect(result.groupSizeDistribution.map((bucket) => bucket.value)).toEqual([1, 0, 0, 0, 0, 1, 1])
    expect(result.nearCapacity).toBe(1)
    expect(result.overCapacity).toBe(1)
  })
})

describe('buildRegistrationAnalytics', () => {
  const user = (id: number, role: string | null, registered: string | null, overrides: Partial<api.AdminUser> = {}): api.AdminUser => ({
    id, firstName: 'User', lastName: String(id), email: `user${id}@example.test`, role,
    country: null, state: null, groupId: null, groupName: null, schoolName: null,
    mentorBackground: null, mentorInstitution: null, mentorReason: null, mentorMaxGroupCount: null,
    yearLevel: null, joinPermissionReceived: true, guardianEmail: `guardian${id}@example.test`, interests: [],
    isAdmin: false, isActive: true, hasLoggedIn: false, lastLogin: null,
    // The API's createdAt (date_joined) is the only registration date.
    accountStatus: 'active', createdAt: registered, invitedAt: null, activatedAt: null,
    supervisorName: null, supervisorEmail: null,
    ...overrides,
  })
  const bundle = (users: api.AdminUser[], messageDays: string[] = []): data.ParticipantAnalyticsBundle => ({
    users,
    groupActivity: { ...fullActivity, messages_by_day: messageDays.map((date) => ({ date, message_count: 1 })) },
  })

  it('counts student and mentor registrations per UTC day in every year, leaving out other roles', () => {
    const result = data.buildRegistrationAnalytics(bundle([
      user(1, 'student', '2025-09-01T03:00:00Z'),
      user(2, 'Student', '2026-03-31T23:30:00Z'),
      user(3, 'mentor', '2026-03-31T08:00:00Z'),
      // 1 April in Sydney is still 31 March in UTC.
      user(4, 'mentor', '2026-04-01T00:00:00+10:00'),
      user(5, 'supervisor', '2026-03-31T09:00:00Z'),
      user(6, 'student', '2026-03-31T10:00:00Z', { isAdmin: true }),
      user(7, 'teacher', '2026-03-31T10:00:00Z'),
      user(8, null, '2026-03-31T10:00:00Z'),
    ]))

    // No year filter: the Registration page narrows the trend by date range.
    expect(result.trend).toEqual([
      { date: '2025-09-01', students: 1, mentors: 0 },
      { date: '2026-03-31', students: 1, mentors: 2 },
    ])
    expect(result.completion.registered).toBe(2)
    expect(result.sources).toEqual([])
  })

  it('leaves accounts without a valid creation time out of the trend but still counts those students', () => {
    const result = data.buildRegistrationAnalytics(bundle([
      user(1, 'student', '2026-05-02T00:00:00Z'),
      user(2, 'student', null, { invitedAt: '2026-06-01T00:00:00Z', activatedAt: '2026-06-03T00:00:00Z' }),
      user(3, 'mentor', 'not a date'),
    ]))

    expect(result.trend).toEqual([{ date: '2026-05-02', students: 1, mentors: 0 }])
    expect(result.completion.registered).toBe(2)
  })

  it('lists students missing guardian details or approval, counting days from the latest recorded date', () => {
    const result = data.buildRegistrationAnalytics(bundle([
      user(1, 'student', '2026-10-01T00:00:00Z'),
      user(2, 'student', '2026-10-06T00:00:00Z', {
        guardianEmail: null, supervisorName: 'Sam Supervisor', firstName: 'Missing', lastName: 'Guardian',
      }),
      user(3, 'student', '2026-09-20T00:00:00Z', { joinPermissionReceived: false }),
      user(4, 'student', '2026-09-20T00:00:00Z', { guardianEmail: null, joinPermissionReceived: false }),
      user(5, 'student', '2026-10-20T00:00:00Z', { guardianEmail: null, firstName: '', lastName: '' }),
      user(6, 'mentor', '2026-10-01T00:00:00Z', { guardianEmail: null }),
      // Counted, but not listed: there is no registration date to count days from.
      user(7, 'student', null, { guardianEmail: null }),
    ], ['2026-10-20']))

    expect(result.completion).toEqual({ registered: 6, guardianDetails: 2, guardianApproved: 1 })
    // The latest message day (20 Oct) is the latest recorded date.
    expect(result.followUps.map((row) => [
      row.id, row.issue, row.student, row.supervisor, row.registrationDate, row.daysOutstanding, row.source,
    ])).toEqual([
      [2, 'missing_guardian', 'Missing Guardian', 'Sam Supervisor', '2026-10-06', 14, null],
      [3, 'awaiting_approval', 'User 3', '—', '2026-09-20', 30, null],
      [4, 'missing_guardian', 'User 4', '—', '2026-09-20', 30, null],
      [5, 'missing_guardian', 'user5@example.test', '—', '2026-10-20', 0, null],
    ])
  })

  it('uses account creation time instead of invitation or activation time', () => {
    const user = (overrides: Partial<api.AdminUser>) => ({
      id: 1,
      firstName: 'Sample',
      lastName: 'Participant',
      email: 'participant@example.test',
      role: 'student',
      isAdmin: false,
      guardianEmail: 'guardian@example.test',
      joinPermissionReceived: true,
      createdAt: '2025-03-04T05:06:00Z',
      invitedAt: '2026-02-01T00:00:00Z',
      activatedAt: '2026-02-02T00:00:00Z',
      ...overrides,
    } as api.AdminUser)

    const result = data.buildRegistrationAnalytics({
      users: [
        user({}),
        user({
          id: 2,
          role: 'mentor',
          createdAt: null,
          invitedAt: '2024-01-01T00:00:00Z',
          activatedAt: '2024-01-02T00:00:00Z',
        }),
        user({
          id: 3,
          createdAt: null,
          guardianEmail: null,
          invitedAt: '2024-02-01T00:00:00Z',
          activatedAt: '2024-02-02T00:00:00Z',
        }),
      ],
      groupActivity: fullActivity,
    })

    expect(result.trend).toEqual([
      { date: '2025-03-04', students: 1, mentors: 0 },
    ])
    expect(result.followUps).toEqual([])
    expect(data.registeredByYear(user({ createdAt: null }), 2026)).toBe(false)
  })
})

describe('buildRecipientEmailLogs', () => {
  it('turns each recipient search result into that recipient\'s copy of the email', () => {
    const base = {
      email_type: 'announcement', email_type_label: 'Announcement notification', title: 'Week 3',
      announcement_id: 9, source_mailbox: 'info@biotechfutures.org', started_at: '2026-10-18T01:00:00Z',
      status: 'partial' as const, attempted: 2, delivered: 1, failed: 1,
      initiated_by_name: '', initiated_by_email: '',
    }
    const logs = data.buildRecipientEmailLogs([
      { ...base, id: 7, recipient: { email: 'amy@example.com', user_id: 1, name: 'Amy Chen', status: 'delivered', reason: '' } },
      { ...base, id: 8, recipient: { email: 'bo@example.com', user_id: null, name: '', status: 'failed', reason: 'address refused' } },
    ])

    expect(logs.map((log) => [log.sendId, log.recipient, log.recipientEmail, log.status, log.recipientReason])).toEqual([
      [7, 'Amy Chen', 'amy@example.com', 'Delivered', ''],
      [8, '—', 'bo@example.com', 'Failed', 'address refused'],
    ])
    expect(logs[0]).toMatchObject({ sender: 'System', senderEmail: '—', title: 'Week 3' })
  })
})

describe('buildEmailMonitoring', () => {
  const baseEmailAnalytics: api.EmailDeliveryAnalyticsResponse = {
    snapshot_at: '2026-10-20T00:00:00Z',
    mailboxes: [],
    totals: { attempted: 0, delivered: 0, failed: 0, delivery_runs: 0 },
    hourly: [],
    daily: [],
    recent_deliveries: [],
  }

  const bundle = (emailAnalytics: api.EmailDeliveryAnalyticsResponse): data.EmailAnalyticsBundle => ({
    users: [],
    groupActivity: fullActivity,
    loginActivity: undefined,
    emailAnalytics,
  })

  it('maps unique first-party engagement totals and per-run averages', () => {
    const result = data.buildEmailMonitoring(bundle({
      ...baseEmailAnalytics,
      totals: { attempted: 20, delivered: 18, failed: 2, delivery_runs: 4 },
      engagement: {
        tracked_messages: 18,
        opened: 10,
        clicked: 6,
        open_events: 24,
        click_events: 9,
      },
    }))

    expect(result.overallStats).toMatchObject({
      opened: 10,
      clicked: 6,
      averageOpenedPerUser: 2.5,
      averageClickedPerUser: 1.5,
    })
  })

  it('uses completed counts instead of a stale failed status', () => {
    const result = data.buildEmailMonitoring(bundle({
      ...baseEmailAnalytics,
      recent_sends: [{
        id: 1,
        email_type: 'announcement',
        email_type_label: 'Announcement notification',
        title: 'Programme update',
        announcement_id: 5,
        source_mailbox: 'info@biotechfutures.org',
        started_at: '2026-10-20T00:00:00Z',
        status: 'failed',
        attempted: 1,
        delivered: 1,
        failed: 0,
        initiated_by_name: 'System',
        initiated_by_email: '',
      }],
    }))

    expect(result.logs[0]).toMatchObject({ status: 'Delivered', senderEmail: '—' })
  })

  it('shows partial when a completed send has unaccounted or failed recipients', () => {
    const result = data.buildEmailMonitoring(bundle({
      ...baseEmailAnalytics,
      recent_sends: [{
        id: 2,
        email_type: 'registration_student',
        email_type_label: 'Student registration',
        title: null,
        announcement_id: null,
        source_mailbox: 'info@biotechfutures.org',
        started_at: '2026-10-20T00:00:00Z',
        status: 'success',
        attempted: 3,
        delivered: 2,
        failed: 0,
        initiated_by_name: 'System',
        initiated_by_email: '',
      }],
    }))

    expect(result.logs[0]).toMatchObject({ status: 'Partial', attempted: 3, delivered: 2 })
  })

  it('shows failed when no recipient server accepted a completed send', () => {
    const result = data.buildEmailMonitoring(bundle({
      ...baseEmailAnalytics,
      recent_sends: [{
        id: 3,
        email_type: 'registration_student',
        email_type_label: 'Student registration',
        title: null,
        announcement_id: null,
        source_mailbox: 'info@biotechfutures.org',
        started_at: '2026-10-20T00:00:00Z',
        status: 'success',
        attempted: 1,
        delivered: 0,
        failed: 0,
        initiated_by_name: 'System',
        initiated_by_email: '',
      }],
    }))

    expect(result.logs[0]).toMatchObject({ status: 'Failed', attempted: 1, delivered: 0 })
  })

  it('shows an announcement send still going as sending, with no recipients to export yet', () => {
    const result = data.buildEmailMonitoring(bundle({
      ...baseEmailAnalytics,
      recent_sends: [{
        id: null,
        delivery_id: 4,
        email_type: 'announcement',
        email_type_label: 'Announcement notification',
        title: 'Programme update',
        announcement_id: 5,
        source_mailbox: 'info@biotechfutures.org',
        started_at: '2026-10-20T00:00:00Z',
        status: 'sending',
        attempted: 12,
        delivered: 0,
        failed: 0,
        initiated_by_name: 'Ada Admin',
        initiated_by_email: 'ada@example.com',
        recipients_recorded: 0,
      }, {
        id: 4,
        email_type: 'announcement',
        email_type_label: 'Announcement notification',
        title: 'Earlier update',
        announcement_id: 3,
        source_mailbox: 'info@biotechfutures.org',
        started_at: '2026-10-19T00:00:00Z',
        status: 'success',
        attempted: 2,
        delivered: 2,
        failed: 0,
        initiated_by_name: 'Ada Admin',
        initiated_by_email: 'ada@example.com',
        recipients_recorded: 2,
      }],
    }))

    expect(result.logs[0]).toMatchObject({ status: 'Sending', recipient: '12 recipients', sendId: null })
    expect(result.logs[1]).toMatchObject({ status: 'Delivered', sendId: 4 })
    expect(result.logs[0]!.id).not.toBe(result.logs[1]!.id)
  })

  it('shows an unfinished legacy announcement send as sending, not failed', () => {
    const result = data.buildEmailMonitoring(bundle({
      ...baseEmailAnalytics,
      recent_deliveries: [{
        id: 2,
        announcement_id: 5,
        title: 'Programme update',
        started_at: '2026-10-20T00:00:00Z',
        completed_at: null,
        status: 'failed',
        recipient_count: 12,
        success_count: 0,
        failure_count: 0,
        initiated_by_name: 'Ada Admin',
        initiated_by_email: 'ada@example.com',
      }],
    }))

    expect(result.logs[0]).toMatchObject({ status: 'Sending', senderEmail: 'ada@example.com' })
  })

  it('shows an abandoned legacy announcement send as failed after 30 minutes', () => {
    const result = data.buildEmailMonitoring(bundle({
      ...baseEmailAnalytics,
      recent_deliveries: [{
        id: 3,
        announcement_id: 5,
        title: 'Programme update',
        started_at: '2026-10-19T23:00:00Z',
        completed_at: null,
        status: 'failed',
        recipient_count: 12,
        success_count: 0,
        failure_count: 0,
        initiated_by_name: 'Ada Admin',
        initiated_by_email: 'ada@example.com',
      }],
    }))

    expect(result.logs[0]).toMatchObject({ status: 'Failed' })
  })
})
