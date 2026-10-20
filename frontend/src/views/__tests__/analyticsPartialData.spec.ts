import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest'
import { flushPromises, mount, type VueWrapper } from '@vue/test-utils'
import * as api from '@/utils/liveAnalyticsApi'
import * as data from '@/utils/liveAnalyticsData'
import GroupsPage from '@/views/GroupsAnalyticsPage.vue'
import MentorsPage from '@/views/MentorsAnalyticsPage.vue'
import MessagesPage from '@/views/MessagesAnalyticsPage.vue'
import ResourcesPage from '@/views/ResourcesAnalyticsPage.vue'
import ActivityPage from '@/views/ActivityAnalyticsPage.vue'
import UsersPage from '@/views/UsersAnalyticsPage.vue'

vi.mock('@/utils/liveAnalyticsApi', () => ({
  fetchAllUsers: vi.fn(), fetchAllGroups: vi.fn(), fetchMentors: vi.fn(),
  fetchGroupActivity: vi.fn(), fetchLoginActivity: vi.fn(),
  fetchResourceAnalytics: vi.fn(), fetchEmailDeliveryAnalytics: vi.fn(), fetchAllResources: vi.fn(),
}))
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
    {
      year: 2025, group_count: 3, groups_with_mentor: 2, groups_without_mentor: 1,
      mentor_count: 2, student_count: 12, students_per_mentor: 5,
      group_size_distribution: [
        { student_count: 0, group_count: 0 }, { student_count: 1, group_count: 0 },
        { student_count: 2, group_count: 0 }, { student_count: 3, group_count: 0 },
        { student_count: 4, group_count: 3 }, { student_count: 5, group_count: 0 },
      ],
      small_groups: 0, full_groups: 0, over_capacity_groups: 0,
      active_groups: 1, inactive_groups: 2, not_started_groups: 0,
    },
    {
      year: 2026, group_count: 1, groups_with_mentor: 1, groups_without_mentor: 0,
      mentor_count: 1, student_count: 1, students_per_mentor: 1,
      group_size_distribution: [
        { student_count: 0, group_count: 0 }, { student_count: 1, group_count: 1 },
        { student_count: 2, group_count: 0 }, { student_count: 3, group_count: 0 },
        { student_count: 4, group_count: 0 }, { student_count: 5, group_count: 0 },
      ],
      small_groups: 1, full_groups: 0, over_capacity_groups: 0,
      active_groups: 1, inactive_groups: 0, not_started_groups: 0,
    },
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
    isActive: true, hasLoggedIn: true, lastLogin: '2026-10-15T00:00:00Z', institution: 'Sample Institute',
    countryName: 'Australia', maxGroupCount: 2, currentAssignedCount: 1, remainingCapacity: 1,
    interests: ['Biotechnology'], lastMessageAt: '2026-10-15T00:00:00Z',
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
// Opens the Export CSV menu, picks the option whose label starts with
// `option` (or exports directly when the page offers one file) and returns the CSV.
async function downloadedCsv(wrapper: VueWrapper, option = 'Summary') {
  let captured: Blob | undefined
  const BrowserURL = URL
  vi.stubGlobal('URL', class extends BrowserURL {
    static createObjectURL = vi.fn((blob: Blob) => { captured = blob; return 'blob:analytics' })
    static revokeObjectURL = vi.fn()
  })
  vi.spyOn(HTMLAnchorElement.prototype, 'click').mockImplementation(() => {})
  expect(wrapper.get('.export-button').attributes('disabled')).toBeUndefined()
  await wrapper.get('.export-button').trigger('click')
  const item = wrapper.findAll('[role="menuitem"]').find((node) => node.text().startsWith(option))
  if (item) await item.trigger('click')
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

    const historicalParticipantComparison = data.participantYearComparison([
      student,
      { ...student, id: 2, role: 'mentor', invitedAt: '2025-08-01T00:00:00Z', activatedAt: '2025-08-01T00:00:00Z' },
      { ...student, id: 3, role: 'supervisor', invitedAt: '2024-08-01T00:00:00Z', activatedAt: '2024-08-01T00:00:00Z' },
    ], 2025)
    expect(historicalParticipantComparison.current).toEqual({ total: 2, students: 0, mentors: 1, supervisors: 1 })
    expect(historicalParticipantComparison.previous).toEqual({ total: 1, students: 0, mentors: 0, supervisors: 1 })

    const groupComparison = data.groupYearComparison([
      groups[0]!,
      { ...groups[0]!, id: '8', createdAt: '2025-01-01T00:00:00Z' },
    ], 2026)
    expect(groupComparison).toMatchObject({ current: 2, previous: 1, previousYear: 2025 })
  })

  it('lists recorded user years, defaults to the current year and rebuilds users for a selected year', async () => {
    vi.mocked(api.fetchAllUsers).mockResolvedValue([
      student,
      {
        ...student,
        id: 2,
        role: 'mentor',
        invitedAt: '2025-08-01T00:00:00Z',
        activatedAt: '2025-08-01T00:00:00Z',
        lastLogin: '2025-09-01T00:00:00Z',
      },
    ])
    vi.mocked(api.fetchLoginActivity).mockResolvedValue({
      by_day: [
        { date: '2025-09-01', students: 0, mentors: 1, supervisors: 0, total: 1 },
        { date: '2026-10-15', students: 1, mentors: 0, supervisors: 0, total: 1 },
      ],
      by_year: [
        { year: 2025, students: 0, mentors: 1, supervisors: 0, total: 1 },
        { year: 2026, students: 1, mentors: 0, supervisors: 0, total: 1 },
      ],
      active_users: { daily: 1, weekly: 1, monthly: 1 },
      latest_activity_date: '2026-10-15',
      query_range: { start: null, end: null },
    })

    const w = await show(UsersPage)
    const yearSelect = w.get('[aria-label="Select analytics year"]')
    expect((yearSelect.element as HTMLSelectElement).value).toBe('2026')
    expect(yearSelect.findAll('option').map((option) => option.text())).toEqual(['2026', '2025'])

    await yearSelect.setValue('2025')
    expect(w.get('.kpi-grid').text()).toContain('Total Users1')
    expect(w.get('.kpi-grid').text()).toContain('Mentors1')
    expect(w.get('.kpi-grid').text()).toContain('Students0')
  })

  it('does not label a later login as Never in an earlier year', () => {
    const futureLogin = {
      ...student,
      id: 2,
      role: 'mentor',
      invitedAt: '2025-08-01T00:00:00Z',
      activatedAt: '2025-08-01T00:00:00Z',
      lastLogin: '2026-10-15T00:00:00Z',
    }
    const historical = data.buildUsersAnalytics({
      users: [futureLogin],
      groupActivity: activity,
      loginActivity: {
        by_day: [{ date: '2025-09-01', students: 0, mentors: 1, supervisors: 0, total: 1 }],
        by_year: [{ year: 2025, students: 0, mentors: 1, supervisors: 0, total: 1 }],
        active_users: { daily: 0, weekly: 0, monthly: 0 },
        latest_activity_date: '2025-09-01', query_range: { start: null, end: null },
      },
    }, 2025)

    expect(historical.lastLogin.find((row) => row.label === 'Never')?.value).toBe(0)
    expect(historical.userLastLogins).toEqual([])
    expect(historical.loginRates.mentors).toBe(100)
  })

  it('lists historical group years and rebuilds the group summary for the selected year', async () => {
    const bundle = { users, groups, groupActivity: activity }
    expect(data.groupAnalyticsYears(bundle)).toEqual([2026, 2025])

    const historical = data.buildGroupsAnalytics(bundle, 2025)
    expect(historical.totalGroups).toBe(3)
    expect(historical.averageGroupSize).toBe(4)
    expect(historical.groupsWithMentor).toBe(2)
    expect(historical.groupsWithoutMentor).toBe(1)
    expect(historical.mentorStudentRatio).toBe(5)
    expect(historical.groupSizeDistribution.find((bucket) => bucket.label === '4')?.value).toBe(3)
    expect(historical.smallGroups).toBe(0)
    expect(historical.inactiveRecent).toBe(2)

    const w = await show(GroupsPage)
    const yearSelect = w.get('[aria-label="Select analytics year"]')
    expect(yearSelect.findAll('option').map((option) => option.text())).toEqual(['2026', '2025'])
    await yearSelect.setValue('2025')
    const summary = w.get('[aria-label="Groups analytics summary"]')
    expect(summary.findAll('.kpi-card')).toHaveLength(5)
    expect(summary.text()).toContain('Total Groups3')
    expect(summary.text()).toContain('Mentor-to-Student Ratio1 : 5')
    expect(w.find('.mentor-ratio-card').exists()).toBe(false)
    expect(w.get('.compact-insights-card').text()).not.toContain('do not have a mentor assigned')
    const assignmentCoverage = w.get('.student-assignment-card')
    expect(assignmentCoverage.text()).toContain('Student Assignment Coverage')
    expect(assignmentCoverage.text()).toContain('Assigned12 (100%)')
    expect(assignmentCoverage.text()).toContain('Unassigned0 (0%)')
    const statusArcTotal = w.findAll('.group-status-card .group-donut-segment')
      .reduce((sum, segment) => sum + Number(segment.attributes('stroke-dasharray')?.split(' ')[0] ?? 0), 0)
    expect(statusArcTotal).toBeCloseTo(100)
  })

  it('draws role donuts from exact shares while keeping rounded legend percentages', async () => {
    vi.mocked(api.fetchAllUsers).mockResolvedValue([
      student,
      { ...student, id: 2, role: 'mentor' },
      { ...student, id: 3, role: 'supervisor' },
    ])

    const w = await show(UsersPage)
    const arcs = w.findAll('.role-donut-segment')
    const arcTotal = arcs.reduce(
      (sum, segment) => sum + Number(segment.attributes('stroke-dasharray')?.split(' ')[0] ?? 0),
      0,
    )

    expect(arcTotal).toBeCloseTo(100)
    expect(w.get('.role-content .legend-list').text()).toContain('Students1 (33.3%)')
    expect(w.get('.role-content .legend-list').text()).toContain('Mentors1 (33.3%)')
    expect(w.get('.role-content .legend-list').text()).toContain('Supervisors1 (33.3%)')
  })

  it('uses timestamp-based membership history for average group size comparison', () => {
    const result = data.buildGroupsAnalytics({ users, groups, groupActivity: activity }, 2026)
    expect(result.averageGroupSize).toBe(1)
    expect(result.averageGroupSizePrevious).toBe(4)
    expect(result.averageGroupSizePreviousYear).toBe(2025)
    expect(result.avgSizeChange).toBe(-75)
    expect(result.groupsWithMentorPrevious).toBe(2)
    expect(result.groupsWithoutMentorPrevious).toBe(1)
    expect(result.mentorStudentRatioPrevious).toBe(5)
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

  it('shows Activity before a ranged login comparison returns', async () => {
    const loginActivity = await api.fetchLoginActivity()
    vi.mocked(api.fetchLoginActivity).mockImplementation((start?: string) => start
      ? new Promise(() => {})
      : Promise.resolve({ ...loginActivity, latest_activity_date: '2026-10-14' }))

    const w = await show(ActivityPage)
    expect(api.fetchLoginActivity).toHaveBeenCalledWith('2026-08-17', '2026-10-15')
    expect(w.find('#user-activity-details').exists()).toBe(true)
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
    expect(w.get('.student-assignment-card').text()).toContain('Student assignment data is unavailable')
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
    expect(w.find('.student-assignment-card').exists()).toBe(true)
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
  it('opens the available-capacity mentor table from the capacity chart', async () => {
    const w = await show(MentorsPage)
    const capacityTable = w.get('#mentors-with-capacity')

    expect(capacityTable.text()).toContain('1 activated mentor has room')
    expect(capacityTable.find('table').exists()).toBe(false)

    await w.get('.capacity-table-shortcut').trigger('click')
    await flushPromises()

    expect(capacityTable.find('table').exists()).toBe(true)
    expect(capacityTable.text()).toContain('Sample Mentor')
    expect(capacityTable.text()).toContain('Australia')
    expect(capacityTable.text()).toContain('Biotechnology')
    expect(capacityTable.text()).toContain('Industry')
    expect(capacityTable.text()).toContain('1 / 2')

    await capacityTable.get('tbody tr').trigger('click')
    expect(routerPush).toHaveBeenCalledWith({
      path: '/admin/users',
      query: { tab: 'mentors', capacity: 'available', search: 'Sample Mentor' },
      hash: '#admin-mentors-table',
    })
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
  it('labels Activity key insights with the latest available data date', async () => {
    vi.mocked(api.fetchAllUsers).mockResolvedValue(users.map((user) => ({
      ...user,
      activatedAt: '2026-10-20T00:00:00Z',
    })))
    const w = await show(ActivityPage)
    const insights = w.get('.insights-card')

    // A newer account activation must not replace the latest login-activity date.
    expect(insights.get('.key-insights-subtitle').text()).toBe('Data as at 15 Oct 2026')
    expect(insights.text()).toContain('have logged in at least once')
    expect(insights.text()).toContain('have never logged in')
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
    // The default end date is the latest login date, so the loaded response is reused.
    expect(api.fetchLoginActivity).toHaveBeenCalledTimes(1)
    expect(api.fetchLoginActivity).toHaveBeenCalledWith()
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

  it('exports group summaries and details even if the user endpoint fails', async () => {
    vi.mocked(api.fetchAllUsers).mockRejectedValue(error)
    const w = await show(GroupsPage)
    expect(w.get('.export-button').attributes('disabled')).toBeUndefined()
    const summary = await downloadedCsv(w)
    expect(summary).toContain('Section,Metric,Value,Unit,Notes\r\n')
    expect(summary).toContain('Groups,Total groups,1,groups,')
    expect(summary).toContain('Report,Unavailable data,participant details,')
    expect(await downloadedCsv(w, 'Details')).toContain('\r\n7,Sample group,')
  })
  it('turns off the students-without-a-group export when participants are unavailable', async () => {
    vi.mocked(api.fetchAllUsers).mockRejectedValue(error)
    const w = await show(GroupsPage)
    await w.get('.export-button').trigger('click')
    const item = w.findAll('[role="menuitem"]').find((node) => node.text().startsWith('Students without a group'))
    expect(item?.attributes('disabled')).toBeDefined()
  })
  it('exports group messages independently and blocks user details with missing role metadata', async () => {
    vi.mocked(api.fetchAllUsers).mockRejectedValue(error)
    const w = await show(MessagesPage)
    expect(await downloadedCsv(w)).toContain('Messages,Messages (all time),23,messages,')
    expect(await downloadedCsv(w, 'Details')).toContain('\r\n7,Sample group,23,')
    await w.get('[aria-label="Select message analytics view"]').setValue('users')
    await w.get('.export-button').trigger('click')
    const details = w.findAll('[role="menuitem"]').find((node) => node.text().startsWith('Details'))
    expect(details?.attributes('disabled')).toBeDefined()
  })
  it('exports available resources and leaves missing activity empty instead of zero', async () => {
    vi.mocked(api.fetchResourceAnalytics).mockRejectedValue(error)
    const w = await show(ResourcesPage)
    expect(await downloadedCsv(w, 'Details')).toMatch(/\r\n8,Sample handbook,Document,[^\r\n]*,,\r\n/)
    expect(await downloadedCsv(w)).toContain('Report,Unavailable data,resource activity,')
  })
  it('exports mentor allocation without treating unavailable background data as Unknown counts', async () => {
    vi.mocked(api.fetchAllUsers).mockRejectedValue(error)
    const csv = await downloadedCsv(await show(MentorsPage))
    expect(csv).toContain('Mentors,Mentors with a group,1,mentors,')
    expect(csv).toContain('Background,Availability,,,The data for this section could not be loaded')
    expect(csv).not.toContain('Background,Unknown,1')
  })
  it('exports mentor counts with explicit unavailable allocation when groups fail', async () => {
    vi.mocked(api.fetchAllGroups).mockRejectedValue(error)
    const csv = await downloadedCsv(await show(MentorsPage))
    expect(csv).toContain('Mentors,Total mentors,1,mentors,')
    expect(csv).not.toContain('Mentors with a group')
    expect(csv).toContain('Capacity pool,Availability,,,The data for this section could not be loaded')
    expect(csv).toContain('Capacity split,Availability,,,')
  })
  it('exports group activity without requiring participant data', async () => {
    vi.mocked(api.fetchAllUsers).mockRejectedValue(error)
    const csv = await downloadedCsv(await show(ActivityPage), 'Details')
    expect(csv).toContain('Group ID,Group,Mentors,')
    expect(csv).toContain('\r\n7,Sample group,Sample Mentor,')
  })
  it('exports participant details with contact, account and activity status', async () => {
    const csv = await downloadedCsv(await show(UsersPage), 'Details')
    expect(csv).toContain(
      'User ID,Name,Email,Role,Account Status,Activity Status (14 days),Last Login (UTC),Days Since Last Login,'
      + 'Registered (UTC),Group,School,Country,State,Interests',
    )
    expect(csv).toContain('\r\n1,Sample Student,student@example.test,Student,Active,Active,2026-10-15T00:00:00Z,0,2026-08-01T00:00:00Z,Sample group,')
  })
  it('reports account status and login recency separately in Activity details', async () => {
    vi.mocked(api.fetchAllUsers).mockResolvedValue([
      { ...student, isActive: false, accountStatus: 'deactivated' },
      { ...student, id: 2, role: 'mentor', mentorBackground: 'industry' },
    ])
    const csv = await downloadedCsv(await show(ActivityPage), 'Details')
    expect(csv).toContain('User ID,Name,Email,Role,Account Status,Activity Status (14 days),Last Login (UTC),Days Since Last Login')
    // Deactivated, yet logged in on the latest recorded day.
    expect(csv).toContain('\r\n1,Sample Student,student@example.test,Student,Deactivated,Active,2026-10-15T00:00:00Z,0')
  })

})
