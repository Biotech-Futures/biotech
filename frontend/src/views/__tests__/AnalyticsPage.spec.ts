import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest'
import { flushPromises, type VueWrapper } from '@vue/test-utils'
import * as api from '@/utils/liveAnalyticsApi'
import * as data from '@/utils/liveAnalyticsData'
import ChartTooltip from '@/components/analytics/ChartTooltip.vue'
import OverviewPage from '@/views/AnalyticsPage.vue'
import { downloadedCsv, registeredUser, show, student, unmountPages } from './analyticsPages.shared'

vi.mock('@/utils/liveAnalyticsApi', () => ({
  fetchAllUsers: vi.fn(), fetchAllGroups: vi.fn(), fetchMentors: vi.fn(),
  fetchGroupActivity: vi.fn(), fetchLoginActivity: vi.fn(),
  fetchResourceAnalytics: vi.fn(), fetchEmailDeliveryAnalytics: vi.fn(), fetchAllResources: vi.fn(),
}))
const routerPush = vi.hoisted(() => vi.fn())
vi.mock('vue-router', () => ({
  useRoute: () => ({ query: {}, hash: '' }),
  useRouter: () => ({ push: routerPush }),
}))
vi.mock('@/composables/useAnalyticsRefreshState', () => ({ useAnalyticsRefreshState: vi.fn() }))

// 2026 is the data year. One student is unplaced and has no guardian details,
// the supervisor's account is deactivated and one group has no mentor.
const users: api.AdminUser[] = [
  student,
  registeredUser(2, 'mentor', '2026-09-01T00:00:00Z', { hasLoggedIn: true, lastLogin: '2026-10-15T00:00:00Z' }),
  registeredUser(3, 'student', '2025-03-10T00:00:00Z', { groupId: null, groupName: null, guardianEmail: null }),
  registeredUser(4, 'supervisor', '2025-02-01T00:00:00Z', {
    hasLoggedIn: true, lastLogin: '2026-10-15T00:00:00Z', isActive: false, accountStatus: 'deactivated',
  }),
  registeredUser(9, 'student', '2024-01-01T00:00:00Z', { isAdmin: true }),
]
const mentor = { id: '2', name: 'Mentor 2', email: 'mentor2@example.test', role: 'mentor', membershipId: 2 }
const groups: api.AdminGroup[] = [
  {
    id: '7', name: 'Sample group', mentor, createdAt: '2026-08-01T00:00:00Z', updatedAt: '2026-10-15T00:00:00Z',
    members: [{ id: '1', name: 'Sample Student', email: 'student@example.test', role: 'student', membershipId: 1 }],
  },
  { id: '8', name: 'Second group', mentor: null, members: [], createdAt: '2026-09-01T00:00:00Z', updatedAt: '2026-09-01T00:00:00Z' },
]
const activity: api.GroupActivityResponse = {
  messages_by_group: [{ group_id: 7, group_name: 'Sample group', message_count: 23 }],
  messages_by_user: [{ user_id: 1, name: 'Sample Student', message_count: 23 }],
  messages_by_day: [{ date: '2026-10-14', message_count: 20 }, { date: '2026-10-15', message_count: 3 }],
  messages_by_group_by_day: [
    { date: '2026-10-14', group_id: 7, group_name: 'Sample group', message_count: 20 },
    { date: '2026-10-15', group_id: 7, group_name: 'Sample group', message_count: 3 },
  ],
  mentor_count: 1, student_count: 1, students_per_mentor: 1,
  query_range: { start: null, end: null },
}
const loginActivity: api.LoginActivityResponse = {
  by_day: [
    { date: '2026-10-14', students: 1, mentors: 0, supervisors: 0, total: 1 },
    { date: '2026-10-15', students: 1, mentors: 1, supervisors: 1, total: 3 },
  ],
  by_year: [
    { year: 2025, students: 0, mentors: 0, supervisors: 1, total: 1 },
    { year: 2026, students: 1, mentors: 1, supervisors: 1, total: 3 },
  ],
  active_users: { daily: 3, weekly: 3, monthly: 3 },
  latest_activity_date: '2026-10-15', query_range: { start: null, end: null },
}
const resourceAnalytics: api.ResourceAnalyticsResponse = {
  total_clicks: 5, unique_users: 2, active_resources: 1,
  top_resources: [{ resource_id: 8, resource_name: 'Sample handbook', click_count: 5, unique_users: 2 }],
  clicks_by_day: [{ date: '2026-10-15', click_count: 5 }], clicks_by_category: [], query_range: { start: null, end: null },
}
const mailbox = (email: string, attempted: number): api.EmailMailboxAnalytics => ({
  email, quota_limit: 3000, totals: { attempted, delivered: attempted, failed: 0, delivery_runs: attempted ? 1 : 0 }, hourly: [], daily: [],
})
// info@ is past 80% of its rolling quota.
const emailAnalytics: api.EmailDeliveryAnalyticsResponse = {
  snapshot_at: '2026-10-15T12:00:00Z',
  mailboxes: [mailbox('info@biotechfutures.org', 2500), mailbox('connect@biotechfutures.org', 300)],
  totals: { attempted: 2800, delivered: 2800, failed: 0, delivery_runs: 2 },
  hourly: [], daily: [], recent_deliveries: [],
}
const error = new Error('HTTP 500')

function mockSources() {
  vi.mocked(api.fetchAllUsers).mockResolvedValue(structuredClone(users))
  vi.mocked(api.fetchAllGroups).mockResolvedValue(structuredClone(groups))
  vi.mocked(api.fetchGroupActivity).mockResolvedValue(structuredClone(activity))
  vi.mocked(api.fetchLoginActivity).mockResolvedValue(structuredClone(loginActivity))
  vi.mocked(api.fetchResourceAnalytics).mockResolvedValue(structuredClone(resourceAnalytics))
  vi.mocked(api.fetchEmailDeliveryAnalytics).mockResolvedValue(structuredClone(emailAnalytics))
  vi.mocked(api.fetchAllResources).mockResolvedValue([{ resource_id: 8, resource_name: 'Sample handbook', resource_type: 'Document' }])
}

beforeEach(() => {
  vi.resetAllMocks()
  data.clearLiveAnalyticsCache()
  mockSources()
})
afterEach(() => {
  unmountPages()
  vi.unstubAllGlobals()
  vi.restoreAllMocks()
})

const summaryCards = (w: VueWrapper) => w.findAll('.summary-card').map((card) => [
  card.get('.card-label').text(),
  card.get('.summary-value').text(),
  card.find('.analytics-year-change').exists() ? card.get('.analytics-year-change').attributes('aria-label') : null,
  card.get('.summary-helper').text(),
])
const moduleCard = (w: VueWrapper, title: string) => w.findAll('.module-card').find((card) => card.get('h2').text() === title)!
const moduleValue = (w: VueWrapper, title: string) => moduleCard(w, title).get('.metric-line strong').text()
const attention = (w: VueWrapper) => w.findAll('.attention-detail-row').map((row) => [
  row.get('.attention-detail-title').text(), row.get('.attention-detail-button').attributes('to'),
])

describe('Analytics overview page', () => {
  it('shows participant headlines for the data year, compared with the year before', async () => {
    const w = await show(OverviewPage)

    const yearSelect = w.get('select[aria-label="Analytics year"]')
    expect(yearSelect.findAll('option').map((option) => option.text())).toEqual(['2026'])
    expect((yearSelect.element as HTMLSelectElement).value).toBe('2026')
    expect(summaryCards(w)).toEqual([
      ['Total Students', '2', 'Increased by 100% vs 2025', 'Registered student participants'],
      // No mentors were registered by 2025, so there is no change to show.
      ['Total Mentors', '1', null, 'Registered mentors'],
      ['Total Supervisors', '1', 'No change vs 2025', 'Registered supervisors'],
      ['Logged In', '75%', 'Increased by 50% vs 2025', '3 of 4 participants have logged in'],
    ])
  })

  it('lists the issues that need attention with links to the matching page', async () => {
    const w = await show(OverviewPage)

    expect(attention(w)).toEqual([
      ['1Students not assigned to groups', '/analytics/groups#students-not-assigned'],
      ['1Groups without mentors', '/analytics/groups#groups-without-mentors'],
      ['1Inactive accounts', '/analytics/activity?status=Inactive#user-activity-details'],
      ['1Missing guardian details', '/analytics/registration?issue=missing_guardian#registration-follow-up'],
      ['1Email usage approaching limit', '/analytics/email#rolling-mailbox-usage'],
    ])
    expect(w.findAll('.attention-detail-row')[0]!.text()).toContain('1 students currently need a group assignment.')
    expect(w.find('.attention-empty-state').exists()).toBe(false)
  })

  it('summarises every analytics area and opens its page from View details', async () => {
    const w = await show(OverviewPage)

    expect(w.findAll('.module-card h2').map((title) => title.text())).toEqual([
      'New Registrations', 'Users', 'Groups', 'Mentor Coverage', 'Activity', 'Messages', 'Resources', 'Email Monitoring',
    ])
    expect(w.findAll('.module-unavailable')).toHaveLength(0)
    expect(moduleValue(w, 'Users')).toBe('4')
    expect(moduleCard(w, 'Users').findAll('.breakdown-label').map((row) => row.text())).toEqual(['Active75%', 'Inactive25%'])
    expect(moduleValue(w, 'Groups')).toBe('2')
    expect(moduleCard(w, 'Groups').get('.module-helper').text()).toBe('1 groups currently have a mentor.')
    expect(moduleValue(w, 'Mentor Coverage')).toBe('100%')
    // Daily active users on the latest login day.
    expect(moduleValue(w, 'Activity')).toBe('3')
    expect(moduleValue(w, 'Messages')).toBe('23')
    expect(moduleCard(w, 'Messages').findAll('.overview-bar-value').map((bar) => bar.text())).toEqual(['20', '3'])
    expect(moduleValue(w, 'Resources')).toBe('5')
    expect(moduleCard(w, 'Resources').get('.breakdown-label').text()).toBe('Sample handbook5')
    expect(moduleValue(w, 'Email Monitoring')).toBe('2,800')
    expect(moduleCard(w, 'Email Monitoring').get('.quota-ring strong').text()).toBe('83%')

    await moduleCard(w, 'Users').get('.breakdown-row').trigger('mouseenter')
    expect(w.findComponent(ChartTooltip).props()).toMatchObject({ visible: true, title: 'Active', value: '75%', detail: 'Users' })
    await moduleCard(w, 'Users').get('.breakdown-row').trigger('mouseleave')
    expect(w.findComponent(ChartTooltip).props('visible')).toBe(false)

    for (const button of w.findAll('.view-details-button')) await button.trigger('click')
    expect(routerPush.mock.calls.map(([path]) => path)).toEqual([
      '/analytics/registration', '/analytics/users', '/analytics/groups', '/analytics/mentors',
      '/analytics/activity', '/analytics/messages', '/analytics/resources', '/analytics/email',
    ])
  })

  it('charts new student and mentor registrations by year, month, week or day', async () => {
    const w = await show(OverviewPage)
    const card = () => moduleCard(w, 'New Registrations')
    const period = () => card().get('select[aria-label="Registration chart period"]')
    const points = () => card().findAll('.overview-point-value').map((point) => Number(point.text()))

    // Supervisors and admins are not counted as registrations.
    expect((period().element as HTMLSelectElement).value).toBe('year')
    expect(points()).toEqual([1, 2])
    expect(card().get('.metric-line strong').text()).toBe('2')
    expect(card().get('.analytics-year-change').attributes('aria-label')).toBe('Increased by 100% vs 2025')

    await period().setValue('month')
    // January to September, the month of the latest registration.
    expect(points()).toEqual([0, 0, 0, 0, 0, 0, 0, 1, 1])
    expect(card().get('.module-helper').text()).toBe('Monthly registrations stored for 2026.')
    expect(card().find('.analytics-year-change').exists()).toBe(false)

    await period().setValue('week')
    expect(points()).toEqual([0, 0, 0, 1, 0, 0, 0, 1])
    expect(card().get('.module-helper').text()).toBe('New registrations over the most recent 8 database weeks.')

    await period().setValue('day')
    expect(points()).toEqual([0, 0, 0, 0, 0, 0, 1])
    await card().findAll('.module-line-point').at(-1)!.trigger('mouseenter')
    expect(w.findComponent(ChartTooltip).props()).toMatchObject({ visible: true, value: '1', detail: 'latest day' })
    // ICU versions differ on "Sep" or "Sept" for en-AU.
    expect(w.findComponent(ChartTooltip).props('title')).toMatch(/^New Registrations · 01 Sep/)
  })

  it('keeps the available areas and marks the rest unavailable when some sources fail, then retries', async () => {
    vi.spyOn(console, 'error').mockImplementation(() => {})
    vi.mocked(api.fetchAllUsers).mockRejectedValue(error)
    vi.mocked(api.fetchResourceAnalytics).mockRejectedValue(error)
    const w = await show(OverviewPage)

    expect(w.get('.analytics-partial-notice').text()).toContain('Some data could not be loaded: participant details, resource activity.')
    expect(w.find('[data-testid="analytics-error-state"]').exists()).toBe(false)
    expect(summaryCards(w).map(([label, value]) => [label, value])).toEqual([
      ['Total Students', '—'], ['Total Mentors', '—'], ['Total Supervisors', '—'], ['Logged In', '—'],
    ])
    expect(w.findAll('.module-card').filter((card) => card.find('.module-unavailable').exists()).map((card) => card.get('.module-unavailable').text())).toEqual([
      'Registration data is currently unavailable. Other modules remain available.',
      'Users data is currently unavailable. Other modules remain available.',
      'Mentors data is currently unavailable. Other modules remain available.',
      'Resources data is currently unavailable. Other modules remain available.',
    ])
    expect(moduleValue(w, 'Groups')).toBe('2')
    expect(moduleValue(w, 'Messages')).toBe('23')
    expect(moduleValue(w, 'Email Monitoring')).toBe('2,800')
    // Issues that need participant details cannot be checked.
    expect(attention(w).map(([label]) => label)).toEqual(['1Groups without mentors', '1Email usage approaching limit'])

    vi.mocked(api.fetchAllUsers).mockResolvedValue(structuredClone(users))
    vi.mocked(api.fetchResourceAnalytics).mockResolvedValue(structuredClone(resourceAnalytics))
    await w.get('.analytics-partial-notice button').trigger('click')
    await flushPromises()
    expect(w.find('.analytics-partial-notice').exists()).toBe(false)
    expect(summaryCards(w)[0]![1]).toBe('2')
    expect(w.findAll('.module-unavailable')).toHaveLength(0)
  })

  it('says some checks could not run when the available data has no issues', async () => {
    vi.mocked(api.fetchAllUsers).mockRejectedValue(error)
    vi.mocked(api.fetchAllGroups).mockResolvedValue([groups[0]!])
    vi.mocked(api.fetchEmailDeliveryAnalytics).mockResolvedValue({ ...emailAnalytics, mailboxes: [mailbox('info@biotechfutures.org', 100)] })
    const w = await show(OverviewPage)

    expect(w.get('.attention-empty-state').text()).toBe('No issues in the available data. Some modules could not be checked.')
  })

  it('marks Activity unavailable when no login history was recorded', async () => {
    vi.mocked(api.fetchLoginActivity).mockResolvedValue({ ...loginActivity, by_day: [], by_year: [] })
    const w = await show(OverviewPage)

    expect(moduleCard(w, 'Activity').get('.module-unavailable').text()).toBe('No recorded login history is available.')
    expect(w.find('.analytics-partial-notice').exists()).toBe(false)
  })

  it('shows a loading state until every source has answered', async () => {
    vi.mocked(api.fetchAllUsers).mockReturnValue(new Promise(() => {}))
    const w = await show(OverviewPage)
    expect(w.find('[data-testid="analytics-loading-state"]').exists()).toBe(true)
    expect(w.find('.summary-grid').exists()).toBe(false)
    expect(w.get('.export-button').attributes('disabled')).toBeDefined()
  })

  it('shows an empty state when the database has no programme records', async () => {
    vi.mocked(api.fetchAllUsers).mockResolvedValue([])
    vi.mocked(api.fetchAllGroups).mockResolvedValue([])
    vi.mocked(api.fetchGroupActivity).mockResolvedValue({ ...activity, messages_by_group: [], messages_by_user: [], messages_by_day: [], messages_by_group_by_day: [] })
    vi.mocked(api.fetchLoginActivity).mockResolvedValue({ ...loginActivity, by_day: [], by_year: [], latest_activity_date: null })
    vi.mocked(api.fetchResourceAnalytics).mockResolvedValue({ ...resourceAnalytics, total_clicks: 0, unique_users: 0, active_resources: 0, top_resources: [], clicks_by_day: [] })
    vi.mocked(api.fetchEmailDeliveryAnalytics).mockResolvedValue({ ...emailAnalytics, mailboxes: [mailbox('info@biotechfutures.org', 0)] })
    vi.mocked(api.fetchAllResources).mockResolvedValue([])
    const w = await show(OverviewPage)

    expect(w.get('[data-testid="analytics-empty-state"]').text()).toContain('No participant, group, resource or delivery records are available')
    expect(w.get('.export-button').attributes('disabled')).toBeDefined()
  })

  it('reports that the overview could not load when every source fails, and recovers on retry', async () => {
    vi.spyOn(console, 'error').mockImplementation(() => {})
    for (const fetcher of [
      api.fetchAllUsers, api.fetchAllGroups, api.fetchGroupActivity, api.fetchLoginActivity,
      api.fetchResourceAnalytics, api.fetchEmailDeliveryAnalytics, api.fetchAllResources,
    ]) vi.mocked(fetcher).mockRejectedValue(error)
    const w = await show(OverviewPage)

    expect(w.get('[data-testid="analytics-error-state"]').text()).toContain('Analytics data could not be loaded from the backend.')
    expect(w.get('.export-button').attributes('disabled')).toBeDefined()

    mockSources()
    await w.get('[data-testid="analytics-error-state"] button').trigger('click')
    await flushPromises()
    expect(w.find('[data-testid="analytics-error-state"]').exists()).toBe(false)
    expect(summaryCards(w)[0]![1]).toBe('2')
  })

  it('exports the headlines, issues and every area as a summary', async () => {
    const csv = await downloadedCsv(await show(OverviewPage))

    expect(csv).toContain('Report,Page,Overview Analytics,,\r\n')
    expect(csv).toContain('Report,Covers,Year 2026,,\r\n')
    expect(csv).toContain('Report,Filter: Registration period,year,,\r\n')
    expect(csv).not.toContain('Unavailable data')
    expect(csv).toContain('Headline,Total Students,2,,Registered student participants\r\n')
    expect(csv).toContain('Headline,Total Students (2025),1,,Previous year\r\n')
    expect(csv).toContain('Headline,Logged In (2025),50,%,Previous year\r\n')
    expect(csv).toContain('Headline,Logged In,75,%,3 of 4 participants have logged in\r\n')
    expect(csv).toContain('Attention required,Groups without mentors,1,,1 groups currently have no mentor assigned. Review group allocation and mentor coverage.\r\n')
    expect(csv).toContain('New Registrations,New Registrations,2,latest year,Account creation dates for current participants by year.\r\n')
    expect(csv).toContain('New Registrations,Trend: 2025,1,,\r\n')
    expect(csv).toContain('Users,Inactive,25,%,\r\n')
    expect(csv).toContain('Messages,Messages,23,Messages,Messages stored in the live database\r\n')
    expect(csv).toContain('Email Monitoring,Email Monitoring,2800,24h recipients,')
  })

  it('names the sources that could not load and leaves their figures empty in the export', async () => {
    vi.mocked(api.fetchAllUsers).mockRejectedValue(error)
    vi.mocked(api.fetchResourceAnalytics).mockRejectedValue(error)
    const csv = await downloadedCsv(await show(OverviewPage))

    expect(csv).toContain('Report,Unavailable data,participant details; resource activity,,Could not be loaded; related figures are left out\r\n')
    expect(csv).toContain('Headline,Total Students,,,Registered student participants\r\n')
    expect(csv).toContain('Users,Users,,,Unavailable\r\n')
    expect(csv).toContain('Resources,Resources,,,Unavailable\r\n')
    expect(csv).toContain('Messages,Messages,23,Messages,Messages stored in the live database\r\n')
    expect(csv).not.toContain('Attention required,Students not assigned to groups')
    // Without participants there is no previous year to compare with, not a year of zeros.
    expect(csv).not.toContain('(2025)')
  })

  it('leaves out the login comparison when login history fails, keeping the participant ones', async () => {
    vi.mocked(api.fetchLoginActivity).mockRejectedValue(error)
    const w = await show(OverviewPage)

    expect(summaryCards(w).map(([label, value, change]) => [label, value, change])).toEqual([
      ['Total Students', '2', 'Increased by 100% vs 2025'],
      ['Total Mentors', '1', null],
      ['Total Supervisors', '1', 'No change vs 2025'],
      ['Logged In', '75%', null],
    ])
    const csv = await downloadedCsv(w)
    expect(csv).toContain('Headline,Total Students (2025),1,,Previous year\r\n')
    expect(csv).toContain('Headline,Logged In,75,%,3 of 4 participants have logged in\r\n')
    expect(csv).not.toContain('Logged In (2025)')
  })

  it('exports the previous-year login rate as a whole percentage', async () => {
    // Three participants by 2025, one of whom logged in that year: 33.3%.
    vi.mocked(api.fetchAllUsers).mockResolvedValue([
      ...structuredClone(users),
      registeredUser(5, 'mentor', '2025-05-01T00:00:00Z'),
    ])
    const csv = await downloadedCsv(await show(OverviewPage))

    expect(csv).toContain('Headline,Logged In (2025),33,%,Previous year\r\n')
  })
})
