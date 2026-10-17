import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest'
import { flushPromises, mount, type VueWrapper } from '@vue/test-utils'
import * as api from '@/utils/liveAnalyticsApi'
import * as data from '@/utils/liveAnalyticsData'
import { downloadReportCsv } from '@/utils/reportExport'
import GroupsPage from '@/views/GroupsAnalyticsPage.vue'
import MentorsPage from '@/views/MentorsAnalyticsPage.vue'
import MessagesPage from '@/views/MessagesAnalyticsPage.vue'
import ResourcesPage from '@/views/ResourcesAnalyticsPage.vue'
import ActivityPage from '@/views/ActivityAnalyticsPage.vue'

vi.mock('@/utils/liveAnalyticsApi', () => ({
  fetchAllUsers: vi.fn(), fetchAllGroups: vi.fn(), fetchMentors: vi.fn(),
  fetchGroupActivity: vi.fn(), fetchLoginActivity: vi.fn(),
  fetchResourceAnalytics: vi.fn(), fetchEmailDeliveryAnalytics: vi.fn(), fetchAllResources: vi.fn(),
}))
vi.mock('@/utils/reportExport', () => ({ downloadReportCsv: vi.fn().mockResolvedValue('report.csv') }))
const routerPush = vi.hoisted(() => vi.fn())
const routeState = vi.hoisted(() => ({ query: {} as Record<string, string>, hash: '' }))
vi.mock('vue-router', () => ({
  useRoute: () => routeState,
  useRouter: () => ({ push: routerPush }),
}))
vi.mock('@/composables/useAnalyticsRefreshState', () => ({ useAnalyticsRefreshState: vi.fn() }))

const student: api.AdminUser = {
  id: 1, firstName: 'Sample', lastName: 'Student', email: 'student@example.test', role: 'student',
  country: null, state: null, groupId: 7, groupName: 'Sample group', schoolName: null,
  mentorBackground: null, mentorInstitution: null, mentorReason: null, mentorMaxGroupCount: null,
  yearLevel: null, joinPermissionReceived: true, guardianEmail: 'guardian@example.test', interests: [],
  isAdmin: false, isActive: true, hasLoggedIn: true, lastLogin: '2026-10-15T00:00:00Z',
  accountStatus: 'active', invitedAt: '2026-08-01T00:00:00Z', activatedAt: '2026-08-01T00:00:00Z',
  supervisorName: null, supervisorEmail: null,
}
const users = [student, { ...student, id: 2, role: 'mentor', mentorBackground: 'industry' }]
const groups: api.AdminGroup[] = [{
  id: '7', name: 'Sample group',
  members: [{ id: '1', name: 'Sample Student', email: 'student@example.test', role: 'student', membershipId: 1 }],
  mentor: { id: '2', name: 'Sample Mentor', email: 'mentor@example.test', role: 'mentor', membershipId: 2 },
  createdAt: '2026-08-01T00:00:00Z', updatedAt: '2026-10-15T00:00:00Z',
}]
const activity: api.GroupActivityResponse = {
  messages_by_group: [{ group_id: 7, group_name: 'Sample group', message_count: 23 }],
  messages_by_user: [{ user_id: 1, name: 'Sample Student', message_count: 23 }],
  messages_by_day: [{ date: '2026-10-15', message_count: 23 }],
  messages_by_group_by_day: [{ date: '2026-10-15', group_id: 7, group_name: 'Sample group', message_count: 23 }],
  messages_by_user_by_group_by_day: [{ date: '2026-10-15', user_id: 1, name: 'Sample Student', group_id: 7, group_name: 'Sample group', message_count: 23 }],
  mentor_activity_by_day: [{ mentor_id: 2, date: '2026-10-15', logins: 1, messages: 2 }],
  mentor_count: 1, student_count: 1, students_per_mentor: 1,
  average_group_size_by_year: [
    { year: 2025, group_count: 3, student_memberships: 12, average_group_size: 4 },
    { year: 2026, group_count: 1, student_memberships: 1, average_group_size: 1 },
  ],
  group_summary_by_year: [
    { year: 2025, group_count: 3, groups_with_mentor: 2, groups_without_mentor: 1, mentor_count: 2, student_count: 12, students_per_mentor: 6 },
    { year: 2026, group_count: 1, groups_with_mentor: 1, groups_without_mentor: 0, mentor_count: 1, student_count: 1, students_per_mentor: 1 },
  ],
  query_range: { start: null, end: null },
}
let wrappers: VueWrapper[] = []
beforeEach(() => {
  vi.resetAllMocks()
  routeState.query = {}
  routeState.hash = ''
  data.clearLiveAnalyticsCache()
  vi.mocked(api.fetchAllUsers).mockResolvedValue(structuredClone(users))
  vi.mocked(api.fetchAllGroups).mockResolvedValue(structuredClone(groups))
  vi.mocked(api.fetchMentors).mockResolvedValue([{
    mentorId: 2, firstName: 'Sample', lastName: 'Mentor', name: 'Sample Mentor', email: 'mentor@example.test',
    isActive: true, hasLoggedIn: true, lastLogin: '2026-10-15T00:00:00Z', institution: null,
    countryName: null, maxGroupCount: 2, currentAssignedCount: 1, remainingCapacity: 1,
    interests: [], lastMessageAt: '2026-10-15T00:00:00Z',
  }])
  vi.mocked(api.fetchGroupActivity).mockResolvedValue(structuredClone(activity))
  vi.mocked(api.fetchLoginActivity).mockResolvedValue({
    by_day: [{ date: '2026-10-15', students: 1, mentors: 1, supervisors: 0, total: 2 }],
    by_year: [{ year: 2026, students: 1, mentors: 1, supervisors: 0, total: 2 }],
    active_users: { daily: 2, weekly: 2, monthly: 2 },
    active_user_comparison: {
      daily: { current: 2, previous: 1 },
      weekly: { current: 2, previous: 1 },
      monthly: { current: 2, previous: 1 },
    },
    latest_activity_date: '2026-10-15', query_range: { start: null, end: null },
  })
  vi.mocked(api.fetchResourceAnalytics).mockResolvedValue({
    total_clicks: 5, unique_users: 2, active_resources: 1,
    top_resources: [{ resource_id: 8, resource_name: 'Sample handbook', click_count: 5, unique_users: 2 }],
    clicks_by_day: [{ date: '2026-10-15', click_count: 5 }], clicks_by_category: [], query_range: { start: null, end: null },
  })
  vi.mocked(api.fetchAllResources).mockResolvedValue([{ resource_id: 8, resource_name: 'Sample handbook', resource_type: 'Document', audiences: [{ role: { slug: 'student' } }] }])
  vi.mocked(api.fetchEmailDeliveryAnalytics).mockResolvedValue({ snapshot_at: null, mailboxes: [], totals: { attempted: 0, delivered: 0, failed: 0, delivery_runs: 0 }, hourly: [], daily: [], recent_deliveries: [] })
})
afterEach(() => {
  wrappers.forEach((wrapper) => wrapper.unmount())
  wrappers = []
  vi.useRealTimers()
  vi.unstubAllGlobals()
  vi.restoreAllMocks()
})
async function show(component: Parameters<typeof mount>[0]) {
  const wrapper = mount(component, { global: { stubs: { RouterLink: true, AnalyticsDatePicker: true, ChartTooltip: true } } })
  wrappers.push(wrapper)
  await flushPromises()
  await flushPromises()
  return wrapper
}
async function downloadedCsv(wrapper: VueWrapper) {
  let captured: Blob | undefined
  const BrowserURL = URL
  vi.stubGlobal('URL', class extends BrowserURL {
    static createObjectURL = vi.fn((blob: Blob) => { captured = blob; return 'blob:analytics' })
    static revokeObjectURL = vi.fn()
  })
  vi.spyOn(HTMLAnchorElement.prototype, 'click').mockImplementation(() => {})
  expect(wrapper.get('.export-button').attributes('disabled')).toBeUndefined()
  await wrapper.get('.export-button').trigger('click')
  expect(captured).toBeInstanceOf(Blob)
  return new Promise<string>((resolve, reject) => {
    const reader = new FileReader()
    reader.onload = () => resolve(String(reader.result))
    reader.onerror = () => reject(reader.error)
    reader.readAsText(captured!)
  })
}
const error = new Error('HTTP 500')

describe('independent analytics sources', () => {
  it('derives participant and group year comparisons from creation dates', () => {
    const participantComparison = data.participantYearComparison([
      student,
      { ...student, id: 2, role: 'mentor', invitedAt: '2025-08-01T00:00:00Z', activatedAt: '2025-08-01T00:00:00Z' },
      { ...student, id: 3, role: 'supervisor', invitedAt: '2024-08-01T00:00:00Z', activatedAt: '2024-08-01T00:00:00Z' },
    ], 2026)
    expect(participantComparison.current).toEqual({ total: 3, students: 1, mentors: 1, supervisors: 1 })
    expect(participantComparison.previous).toEqual({ total: 2, students: 0, mentors: 1, supervisors: 1 })

    const groupComparison = data.groupYearComparison([
      groups[0]!,
      { ...groups[0]!, id: '8', createdAt: '2025-01-01T00:00:00Z' },
    ], 2026)
    expect(groupComparison).toMatchObject({ current: 2, previous: 1, previousYear: 2025 })
  })

  it('sorts mentor-to-student ratios numerically and keeps unmentored groups last', () => {
    const ratioGroups: api.AdminGroup[] = [4, 5, 3, 2, 1].map((studentCount) => ({
      id: String(studentCount),
      name: `Ratio ${studentCount}`,
      members: Array.from({ length: studentCount }, (_, index) => ({
        id: `${studentCount}-${index}`,
        name: `Student ${index}`,
        email: `student-${studentCount}-${index}@example.test`,
        role: 'student',
        membershipId: studentCount * 10 + index,
      })),
      mentor: { id: 'mentor', name: 'Mentor', email: 'mentor@example.test', role: 'mentor', membershipId: 999 },
      createdAt: '2026-08-01T00:00:00Z',
      updatedAt: '2026-10-15T00:00:00Z',
    }))
    ratioGroups.push({
      id: 'none', name: 'No mentor', members: [], mentor: null,
      createdAt: '2026-08-01T00:00:00Z', updatedAt: '2026-10-15T00:00:00Z',
    })

    const result = data.buildGroupsAnalytics({
      users: [], groups: ratioGroups, groupActivity: { ...structuredClone(activity), messages_by_group: [] },
    })

    expect(result.ratioDistribution.map((item) => item.label)).toEqual([
      '1:5', '1:4', '1:3', '1:2', '1:1', 'No mentor',
    ])
  })

  it('uses timestamp-based membership history for average group size comparison', () => {
    const result = data.buildGroupsAnalytics({ users, groups, groupActivity: activity }, 2026)
    expect(result.averageGroupSize).toBe(1)
    expect(result.averageGroupSizePrevious).toBe(4)
    expect(result.averageGroupSizePreviousYear).toBe(2025)
    expect(result.avgSizeChange).toBe(-75)
    expect(result.groupsWithMentorPrevious).toBe(2)
    expect(result.groupsWithoutMentorPrevious).toBe(1)
    expect(result.mentorStudentRatioPrevious).toBe(6)
    expect(result.comparisonPreviousYear).toBe(2025)
  })

  it('keeps groups, mentors, activity and messages when users fail', async () => {
    vi.mocked(api.fetchAllUsers).mockRejectedValue(error)
    const [g, m, msg, a] = await Promise.all([data.loadGroupsAnalyticsBundle(), data.loadMentorsAnalyticsBundle(), data.loadMessagesAnalyticsBundle(), data.loadActivityAnalyticsBundle()])
    expect(data.buildGroupsAnalytics(g).totalGroups).toBe(1)
    expect(m.mentors).toHaveLength(1)
    expect(data.buildMessagesAnalytics(msg).totalMessages).toBe(23)
    expect(a.loginActivity?.active_users.daily).toBe(2)
    for (const bundle of [g, m, msg, a]) expect(bundle.unavailableSources).toEqual(['users'])
    await expect(data.loadUsersAnalyticsBundle()).rejects.toThrow('required for this view')
    expect(data.buildMessagesAnalytics(await data.loadMessagesAnalyticsBundle()).totalMessages).toBe(23)
  })
  it('keeps messages without groups, and group structure without activity', async () => {
    vi.mocked(api.fetchAllGroups).mockRejectedValue(error)
    expect(data.buildMessagesAnalytics(await data.loadMessagesAnalyticsBundle()).totalMessages).toBe(23)
    // Pages share cached sources, so start the second scenario from a cold cache.
    data.clearLiveAnalyticsCache()
    vi.mocked(api.fetchAllGroups).mockResolvedValue(groups)
    vi.mocked(api.fetchGroupActivity).mockRejectedValue(error)
    const bundle = await data.loadGroupsAnalyticsBundle()
    expect(data.buildGroupsAnalytics(bundle).groupsWithMentor).toBe(1)
    expect(bundle.unavailableSources).toEqual(['groupActivity'])
  })
  it('keeps participant counts without login history', async () => {
    vi.mocked(api.fetchLoginActivity).mockRejectedValue(error)
    const bundle = await data.loadUsersAnalyticsBundle()
    expect(bundle.users).toHaveLength(2)
    expect(bundle.loginActivity).toBeUndefined()
    expect(bundle.unavailableSources).toEqual(['loginActivity'])
  })
  it('keeps overview messages and marks failed statistics unavailable', async () => {
    vi.mocked(api.fetchAllUsers).mockRejectedValue(error)
    vi.mocked(api.fetchResourceAnalytics).mockRejectedValue(error)
    const overview = data.buildOverviewAnalytics(await data.loadOverviewAnalyticsBundle())
    expect(overview.modules.find((m) => m.key === 'messages')).toMatchObject({ value: '23' })
    for (const key of ['groups', 'activity', 'messages']) expect(overview.modules.find((m) => m.key === key)?.unavailable).not.toBe(true)
    for (const key of ['users', 'resources']) expect(overview.modules.find((m) => m.key === key)).toMatchObject({ value: '—', unavailable: true })
  })
  it('recovers partial sources on retry and expires the cache after five minutes', async () => {
    vi.useFakeTimers()
    vi.mocked(api.fetchAllUsers).mockRejectedValueOnce(error)
    expect((await data.loadGroupsAnalyticsBundle()).unavailableSources).toEqual(['users'])
    await data.loadGroupsAnalyticsBundle()
    expect(api.fetchAllUsers).toHaveBeenCalledTimes(1)
    expect((await data.loadGroupsAnalyticsBundle(true)).unavailableSources).toEqual([])
    vi.advanceTimersByTime(data.ANALYTICS_CACHE_TTL_MS + 1)
    await data.loadGroupsAnalyticsBundle()
    expect(api.fetchAllUsers).toHaveBeenCalledTimes(3)
  })
  it('reports total failure rather than an empty dataset, and retries without a cached error', async () => {
    for (const fetcher of [api.fetchAllUsers, api.fetchAllGroups, api.fetchGroupActivity]) vi.mocked(fetcher).mockRejectedValue(error)
    await expect(data.loadMessagesAnalyticsBundle()).rejects.toThrow('required for this view')
    vi.mocked(api.fetchGroupActivity).mockResolvedValue(activity)
    expect(data.buildMessagesAnalytics(await data.loadMessagesAnalyticsBundle()).totalMessages).toBe(23)
  })
})

describe('partial analytics pages', () => {
  it('opens inactive mentors in Activity with visible filters and matching rows', async () => {
    routeState.query = { role: 'Mentor', status: 'Inactive' }
    routeState.hash = '#user-activity-details'
    vi.mocked(api.fetchAllUsers).mockResolvedValue([
      student,
      {
        ...student,
        id: 2,
        firstName: 'Inactive',
        lastName: 'Mentor',
        role: 'mentor',
        isActive: false,
        hasLoggedIn: false,
        lastLogin: null,
        accountStatus: 'deactivated',
        mentorBackground: 'industry',
      },
    ])

    const w = await show(ActivityPage)
    expect(w.get('[aria-label="Filter by user role"]').element).toHaveProperty('value', 'Mentor')
    expect(w.get('[aria-label="Filter by activity status"]').element).toHaveProperty('value', 'Inactive')
    expect(w.get('#user-activity-details tbody').text()).toContain('Inactive Mentor')
    expect(w.find('.activity-issue-context').exists()).toBe(false)
  })

  it('opens the matching Admin filters from group issue rows', async () => {
    vi.mocked(api.fetchAllUsers).mockResolvedValue([
      { ...student, groupId: null, groupName: null },
      { ...student, id: 2, role: 'mentor', mentorBackground: 'industry' },
    ])
    vi.mocked(api.fetchAllGroups).mockResolvedValue([
      { ...groups[0]!, mentor: null },
    ])

    const w = await show(GroupsPage)
    const issueRows = w.findAll('.group-issue-table-row--clickable')
    expect(issueRows).toHaveLength(2)

    await issueRows[0]!.trigger('click')
    expect(routerPush).toHaveBeenLastCalledWith({
      path: '/admin/users',
      query: { tab: 'students', inGroup: 'no', search: student.email },
      hash: '#admin-users-table',
    })

    await issueRows[1]!.trigger('click')
    expect(routerPush).toHaveBeenLastCalledWith({
      path: '/admin/groups',
      query: { mentorStatus: 'unmatched', search: 'Sample group' },
      hash: '#admin-groups-table',
    })
  })

  it('shows group structure and unavailable student allocation, then recovers on retry', async () => {
    vi.mocked(api.fetchAllUsers).mockRejectedValue(error)
    const w = await show(GroupsPage)
    expect(w.find('[aria-label="Groups analytics summary"]').exists()).toBe(true)
    expect(w.get('#students-not-assigned').text()).toContain('Student allocation details are unavailable')
    expect(w.text()).not.toContain('No unassigned students.')
    expect(w.get('.export-button').attributes('disabled')).toBeUndefined()
    vi.mocked(api.fetchAllUsers).mockResolvedValue(users)
    await w.get('.analytics-partial-notice button').trigger('click')
    await flushPromises()
    expect(w.find('.analytics-partial-notice').exists()).toBe(false)
    expect(w.get('.export-button').attributes('disabled')).toBeUndefined()
  })
  it('does not classify groups as inactive when activity fails', async () => {
    vi.mocked(api.fetchGroupActivity).mockRejectedValue(error)
    const w = await show(GroupsPage)
    expect(w.find('.group-status-card').exists()).toBe(false)
    expect(w.find('.mentor-coverage-card').exists()).toBe(true)
    expect(w.text()).not.toContain('groups have had no activity')
  })
  it('shows mentor allocation without inventing background statistics when users fail', async () => {
    vi.mocked(api.fetchAllUsers).mockRejectedValue(error)
    const w = await show(MentorsPage)
    expect(w.find('[aria-label="Mentor snapshot summary"]').exists()).toBe(true)
    expect(w.text()).toContain('1 of 1 mentors assigned')
    expect(w.text()).not.toContain('Mentor Background')
    expect(w.text()).not.toContain('Mentor analytics could not be loaded')
  })
  it('shows messages with unavailable roles when user metadata fails', async () => {
    vi.mocked(api.fetchAllUsers).mockRejectedValue(error)
    const w = await show(MessagesPage)
    expect(w.get('[aria-label="Messages analytics summary"]').text()).toContain('23')
    expect(w.text()).not.toContain('Message analytics could not be loaded')
    await w.get('[aria-label="Select message analytics view"]').setValue('users')
    expect(w.text()).toContain('Unavailable')
  })
  it('shows catalogue rows with unknown clicks when resource activity fails', async () => {
    vi.mocked(api.fetchResourceAnalytics).mockRejectedValue(error)
    const w = await show(ResourcesPage)
    const row = w.get('.resource-usage-table tbody tr')
    expect(row.text()).toContain('Sample handbook')
    expect(row.findAll('td').slice(2).map((cell) => cell.text())).toEqual(['—', '—'])
    expect(w.find('.top-grid').exists()).toBe(false)
    expect(w.find('[data-testid="analytics-empty-state"]').exists()).toBe(false)
  })
  it('shows group activity and masks participant metrics when users fail', async () => {
    vi.mocked(api.fetchAllUsers).mockRejectedValue(error)
    const w = await show(ActivityPage)
    expect(w.text()).toContain('Group Activity Trend')
    expect(w.text()).toContain('Participant details are unavailable')
    expect(w.text()).not.toContain('0 of 0 current users')
    expect(w.find('[data-testid="analytics-error-state"]').exists()).toBe(false)
  })
  it('compares activity windows ending on the selected date with the preceding windows', async () => {
    const w = await show(ActivityPage)
    const labels = w.findAll('.analytics-year-change').map((node) => node.attributes('aria-label'))

    expect(labels).toContain('Increased by 100% vs previous day')
    expect(labels).toContain('Increased by 100% vs previous 7 days')
    expect(labels).toContain('Increased by 100% vs previous 30 days')
    expect(w.text()).toContain('Selected day')
    expect(w.text()).toContain('7 days ending on selected date')
    expect(w.text()).toContain('30 days ending on selected date')
    expect(api.fetchLoginActivity).toHaveBeenCalledWith('2026-08-17', '2026-10-15')
  })
  it('keeps resource activity without inventing category or audience metadata', async () => {
    vi.mocked(api.fetchAllResources).mockRejectedValue(error)
    const w = await show(ResourcesPage)
    expect(w.find('.top-grid').exists()).toBe(true)
    const row = w.get('.resource-usage-table tbody tr')
    expect(row.text()).toContain('Unavailable')
    expect(row.findAll('td').slice(2).map((cell) => cell.text())).toEqual(['5', '2'])
    expect(w.get('[aria-label="Filter resources by configured audience"]').attributes('disabled')).toBeDefined()
  })
  it('masks mentor allocation and related charts if group metadata fails', async () => {
    vi.mocked(api.fetchAllGroups).mockRejectedValue(error)
    const w = await show(MentorsPage)
    const summary = w.get('[aria-label="Mentor snapshot summary"]')
    expect(summary.text()).toContain('Total Mentors1')
    expect(summary.text()).toContain('Group allocation data is unavailable')
    expect(w.text()).not.toContain('1 of 1 mentors assigned')
    expect(w.text()).not.toContain('Over capacity')
  })
  it('keeps account last logins when message activity fails', async () => {
    vi.mocked(api.fetchGroupActivity).mockRejectedValue(error)
    const w = await show(MentorsPage)
    expect(w.find('[aria-label="Mentor snapshot summary"]').exists()).toBe(true)
    // Last login comes from the mentor account, not from message activity.
    expect(w.text()).toContain('Last Login Distribution')
    const neverLoggedIn = w.findAll('.key-insights-row').find((row) => row.text().includes('Never logged in'))
    expect(neverLoggedIn?.get('strong').text()).toBe('0')
  })

  it('exports group summaries even if the user endpoint fails', async () => {
    vi.mocked(api.fetchAllUsers).mockRejectedValue(error)
    const w = await show(GroupsPage)
    expect(w.text()).not.toContain('CSV export is disabled')
    expect(w.get('.export-button').attributes('disabled')).toBeUndefined()
    await w.get('.export-button').trigger('click')
    expect(downloadReportCsv).toHaveBeenCalledOnce()
    const [params, report] = vi.mocked(downloadReportCsv).mock.calls[0]!
    expect(report).toBe('groups')
    expect(params.get('report')).toBe('groups')
  })
  it('exports group messages independently and blocks user reports with missing role metadata', async () => {
    vi.mocked(api.fetchAllUsers).mockRejectedValue(error)
    const w = await show(MessagesPage)
    expect(w.get('.export-button').attributes('disabled')).toBeUndefined()
    await w.get('.export-button').trigger('click')
    expect(vi.mocked(downloadReportCsv).mock.calls[0]?.[0].get('mode')).toBe('groups')
    await w.get('[aria-label="Select message analytics view"]').setValue('users')
    expect(w.get('.export-button').attributes('disabled')).toBeDefined()
  })
  it('exports available resources and explicitly marks missing activity instead of zero', async () => {
    vi.mocked(api.fetchResourceAnalytics).mockRejectedValue(error)
    const csv = await downloadedCsv(await show(ResourcesPage))
    expect(csv).toContain('"Sample handbook","Document","Unavailable","Unavailable"')
  })
  it('exports mentor allocation without treating unavailable background data as Unknown counts', async () => {
    vi.mocked(api.fetchAllUsers).mockRejectedValue(error)
    const csv = await downloadedCsv(await show(MentorsPage))
    expect(csv).toContain('"Summary","Assigned Mentors","1"')
    expect(csv).toContain('"Background","Availability","Unavailable"')
    expect(csv).not.toContain('"Background","Unknown","1"')
  })
  it('exports mentor counts with explicit unavailable allocation when groups fail', async () => {
    vi.mocked(api.fetchAllGroups).mockRejectedValue(error)
    const csv = await downloadedCsv(await show(MentorsPage))
    expect(csv).toContain('"Summary","Total Mentors","1"')
    expect(csv).toContain('"Summary","Assigned Mentors","Unavailable"')
    expect(csv).toContain('"Capacity","Availability","Unavailable"')
  })
  it('exports group activity without requiring participant data', async () => {
    vi.mocked(api.fetchAllUsers).mockRejectedValue(error)
    const csv = await downloadedCsv(await show(ActivityPage))
    expect(csv).toContain('"7","Sample group","Sample Mentor"')
  })

})
