import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest'
import { flushPromises, type VueWrapper } from '@vue/test-utils'
import * as api from '@/utils/liveAnalyticsApi'
import * as data from '@/utils/liveAnalyticsData'
import AnalyticsDatePicker from '@/components/analytics/AnalyticsDatePicker.vue'
import ChartTooltip from '@/components/analytics/ChartTooltip.vue'
import RegistrationPage from '@/views/RegistrationAnalyticsPage.vue'
import { downloadedCsv, registeredUser, show, unmountPages } from './analyticsPages.shared'

vi.mock('@/utils/liveAnalyticsApi', () => ({
  fetchAllUsers: vi.fn(), fetchAllGroups: vi.fn(), fetchMentors: vi.fn(),
  fetchGroupActivity: vi.fn(), fetchLoginActivity: vi.fn(),
  fetchResourceAnalytics: vi.fn(), fetchEmailDeliveryAnalytics: vi.fn(), fetchAllResources: vi.fn(),
}))
const routeState = vi.hoisted(() => ({ query: {} as Record<string, string>, hash: '' }))
vi.mock('vue-router', () => ({
  // The page imports RouterLink directly; the mount stubs it by name.
  RouterLink: { name: 'RouterLink', render: () => null },
  useRoute: () => routeState,
  useRouter: () => ({ push: vi.fn() }),
}))
vi.mock('@/composables/useAnalyticsRefreshState', () => ({ useAnalyticsRefreshState: vi.fn() }))

// The latest recorded date is 15 Oct 2026, so the default trend covers 8–15 Oct.
const users = [
  registeredUser(1, 'student', '2026-10-14T00:00:00Z', {
    firstName: 'Complete', lastName: 'Student', hasLoggedIn: true, lastLogin: '2026-10-15T00:00:00Z',
  }),
  registeredUser(2, 'student', '2026-10-10T00:00:00Z', {
    firstName: 'Missing', lastName: 'Guardian', guardianEmail: null, supervisorName: 'Sam Supervisor',
  }),
  registeredUser(3, 'student', '2026-08-31T00:00:00Z', {
    firstName: 'Awaiting', lastName: 'Approval', joinPermissionReceived: false,
  }),
  registeredUser(4, 'mentor', '2026-10-15T00:00:00Z'),
  registeredUser(5, 'mentor', '2025-08-01T00:00:00Z'),
  registeredUser(6, 'supervisor', '2026-10-12T00:00:00Z'),
]

beforeEach(() => {
  vi.resetAllMocks()
  routeState.query = {}
  routeState.hash = ''
  data.clearLiveAnalyticsCache()
  vi.mocked(api.fetchAllUsers).mockResolvedValue(structuredClone(users))
})
afterEach(() => {
  unmountPages()
  vi.unstubAllGlobals()
  vi.restoreAllMocks()
})

const cards = (w: VueWrapper) => w.findAll('.kpi-card').map((card) => [
  card.get('.kpi-label').text(), card.get('strong').text(), card.get('small').text(),
])
const tableRows = (w: VueWrapper) => w.findAll('#registration-follow-up tbody tr').map((row) => row.findAll('td').map((cell) => cell.text()))
const issueChart = (w: VueWrapper, title: string) => w.findAll('.issue-card').find((card) => card.get('h2').text() === title)!
const datePickers = (w: VueWrapper) => w.findAllComponents(AnalyticsDatePicker)

describe('Registration analytics page', () => {
  it('shows recent registrations, guardian completion and outstanding follow-ups', async () => {
    const w = await show(RegistrationPage)

    expect(cards(w)).toEqual([
      ['Latest recorded day', '1', '0 students · 1 mentors'],
      ['Last 7 days', '3', '2 students · 1 mentors'],
      ['Last 14 days', '3', '2 students · 1 mentors'],
      ['Fully registered students', '1', '33.3% have guardian approval'],
    ])
    expect(w.findAll('.funnel-step').map((step) => [step.get('.funnel-copy span').text(), step.get('strong').text(), step.get('small').text()])).toEqual([
      ['Students registered', '3', 'Current programme-year students'],
      ['Guardian details provided', '2', '67% of registered students · 1 outstanding'],
      ['Guardian approval received', '1', '33% of registered students · 2 outstanding'],
    ])
    expect(w.get('.source-card').text()).toContain('Registration source is not stored')
    expect(w.findAll('.follow-up-summary button').map((button) => button.text())).toEqual([
      '1Missing guardian details',
      '1Awaiting guardian approval',
    ])

    // Five days since registration on 10 Oct; 45 days since 31 Aug.
    expect(issueChart(w, 'Missing guardian contact details').findAll('.bar-value').map((bar) => bar.text())).toEqual(['0', '1', '0', '0', '0', '0'])
    expect(issueChart(w, 'Awaiting guardian approval').findAll('.bar-value').map((bar) => bar.text())).toEqual(['0', '0', '0', '0', '0', '1'])
    expect(tableRows(w)).toEqual([
      ['Missing Guardianstudent2@example.test', 'Sam Supervisor', '10 Oct 2026', 'Unavailable', 'Missing details', '5 days'],
    ])
    expect(w.get('.table-footer').text()).toContain('Showing 1–1 of 1')
  })

  it('draws the default trend over the last recorded week, one point per day', async () => {
    const w = await show(RegistrationPage)

    expect(datePickers(w).map((picker) => picker.props('modelValue'))).toEqual(['2026-10-08', '2026-10-15'])
    expect(datePickers(w)[0]!.props('availableYears')).toEqual([2025, 2026])
    expect((w.get('[aria-label="Registration filters"] select').element as HTMLSelectElement).value).toBe('day')
    expect(w.findAll('.chart-labels span').map((label) => label.text())).toEqual(['10 Oct', '14 Oct', '15 Oct'])
    expect(w.findAll('.trend-dot')).toHaveLength(6)

    await w.findAll('.students-dot')[1]!.trigger('mouseenter')
    expect(w.findComponent(ChartTooltip).props()).toMatchObject({ visible: true, title: '14 Oct 2026', value: '1 students' })
    await w.findAll('.students-dot')[1]!.trigger('mouseleave')
    expect(w.findComponent(ChartTooltip).props('visible')).toBe(false)

    await w.get('.series-controls input[value="mentors"]').setValue(false)
    expect(w.find('.mentor-line').exists()).toBe(false)
    expect(w.findAll('.trend-dot')).toHaveLength(3)
  })

  it('groups a long date range by month and keeps dates inside the recorded data', async () => {
    const w = await show(RegistrationPage)

    datePickers(w)[0]!.vm.$emit('update:model-value', '2025-08-01')
    await flushPromises()
    expect((w.get('[aria-label="Registration filters"] select').element as HTMLSelectElement).value).toBe('month')
    expect(w.findAll('.chart-labels span').map((label) => label.text())).toEqual(['Aug', 'Aug', 'Oct'])
    const csv = await downloadedCsv(w)
    expect(csv).toContain('Report,Filter: Trend interval,month,,\r\n')
    expect(csv).toContain('Registration trend (Students),2026-08,1,users,\r\n')
    expect(csv).toContain('Registration trend (Students),2026-10,2,users,\r\n')
    expect(csv).toContain('Registration trend (Mentors),2025-08,1,users,\r\n')

    // Dates outside the recorded registrations move back to its first and last day.
    datePickers(w)[1]!.vm.$emit('update:model-value', '2027-01-01')
    datePickers(w)[0]!.vm.$emit('update:model-value', '2020-01-01')
    await flushPromises()
    expect(datePickers(w).map((picker) => picker.props('modelValue'))).toEqual(['2025-08-01', '2026-10-15'])

    // A start after the end moves the end with it.
    datePickers(w)[1]!.vm.$emit('update:model-value', '2026-09-30')
    datePickers(w)[0]!.vm.$emit('update:model-value', '2026-10-12')
    await flushPromises()
    expect(datePickers(w).map((picker) => picker.props('modelValue'))).toEqual(['2026-10-12', '2026-10-12'])
  })

  it('says when the selected dates have no registrations and counts recent cards up to the end date', async () => {
    const w = await show(RegistrationPage)

    datePickers(w)[0]!.vm.$emit('update:model-value', '2026-09-02')
    datePickers(w)[1]!.vm.$emit('update:model-value', '2026-09-30')
    await flushPromises()
    expect(w.get('.trend-card').text()).toContain('No registrations are available for this date range.')
    expect(cards(w)[1]).toEqual(['Last 7 days', '0', '0 students · 0 mentors'])

    await w.get('.reset-button').trigger('click')
    expect(datePickers(w).map((picker) => picker.props('modelValue'))).toEqual(['2026-10-08', '2026-10-15'])
    expect(w.find('.trend-card .empty-state').exists()).toBe(false)
  })

  it('filters the follow-up table by issue, days outstanding and search', async () => {
    const w = await show(RegistrationPage)
    const statusFilter = w.findAll('[aria-label="Registration filters"] select')[1]!

    await w.findAll('.table-tabs button')[1]!.trigger('click')
    expect((statusFilter.element as HTMLSelectElement).value).toBe('awaiting_approval')
    expect(tableRows(w)).toEqual([
      ['Awaiting Approvalstudent3@example.test', '—', '31 Aug 2026', 'Unavailable', 'Awaiting approval', '45 days'],
    ])
    expect(w.find('#registration-follow-up .overdue').exists()).toBe(true)

    const awaitingBars = issueChart(w, 'Awaiting guardian approval').findAll('.bar-column')
    await awaitingBars[0]!.trigger('click')
    expect(awaitingBars[0]!.classes()).toContain('selected')
    expect(w.get('#registration-follow-up tbody').text()).toBe('No follow-up records match these filters.')
    // Selecting the same bar again clears the days filter.
    await awaitingBars[0]!.trigger('click')
    expect(tableRows(w)).toHaveLength(1)

    await w.findAll('.follow-up-summary button')[0]!.trigger('click')
    expect((statusFilter.element as HTMLSelectElement).value).toBe('missing_guardian')
    await w.get('.table-search input').setValue('sam super')
    expect(tableRows(w)).toHaveLength(1)
    await w.get('.table-search input').setValue('nobody')
    expect(w.get('#registration-follow-up').text()).toContain('0 records match the current filters.')

    await w.get('.reset-button').trigger('click')
    expect((statusFilter.element as HTMLSelectElement).value).toBe('all')
    expect(tableRows(w)[0]![0]).toBe('Missing Guardianstudent2@example.test')
  })

  it('pages the follow-up table seven rows at a time and sorts by days outstanding', async () => {
    vi.mocked(api.fetchAllUsers).mockResolvedValue([
      ...Array.from({ length: 9 }, (_, index) => registeredUser(index + 1, 'student', `2026-10-0${index + 1}T00:00:00Z`, {
        guardianEmail: null,
      })),
      registeredUser(10, 'mentor', '2026-10-15T00:00:00Z'),
    ])
    const w = await show(RegistrationPage)
    const days = () => tableRows(w).map((row) => row[5])

    expect(days()).toEqual(['14 days', '13 days', '12 days', '11 days', '10 days', '9 days', '8 days'])
    expect(w.get('.table-footer').text()).toContain('Showing 1–7 of 9')
    expect(w.get('.table-footer').text()).toContain('Page 1 of 2')

    await w.findAll('.table-footer button')[1]!.trigger('click')
    expect(days()).toEqual(['7 days', '6 days'])
    expect(w.get('.table-footer').text()).toContain('Showing 8–9 of 9')
    expect(w.findAll('.table-footer button')[1]!.attributes('disabled')).toBeDefined()

    // Sorting goes back to the first page.
    await w.get('.sort-button').trigger('click')
    expect(days()).toEqual(['6 days', '7 days', '8 days', '9 days', '10 days', '11 days', '12 days'])
    expect(w.get('.table-footer').text()).toContain('Page 1 of 2')
  })

  it('opens the follow-up type named in the link from the Overview', async () => {
    routeState.query = { issue: 'awaiting_approval' }
    routeState.hash = '#registration-follow-up'
    const scrollIntoView = vi.fn()
    Object.defineProperty(HTMLElement.prototype, 'scrollIntoView', { configurable: true, value: scrollIntoView })
    vi.stubGlobal('requestAnimationFrame', (callback: FrameRequestCallback) => { callback(0); return 0 })
    try {
      const w = await show(RegistrationPage, { attach: true })
      expect(tableRows(w)[0]![0]).toBe('Awaiting Approvalstudent3@example.test')
      expect(scrollIntoView).toHaveBeenCalledWith({ behavior: 'smooth', block: 'start' })
    } finally {
      delete (HTMLElement.prototype as Partial<HTMLElement>).scrollIntoView
    }
  })

  it('shows a loading state until participants arrive', async () => {
    vi.mocked(api.fetchAllUsers).mockReturnValue(new Promise(() => {}))
    const w = await show(RegistrationPage)
    expect(w.find('[data-testid="analytics-loading-state"]').exists()).toBe(true)
    expect(w.find('.kpi-grid').exists()).toBe(false)
    expect(w.get('.export-button').attributes('disabled')).toBeDefined()
  })

  it('shows an empty state when there are no student or mentor registrations', async () => {
    vi.mocked(api.fetchAllUsers).mockResolvedValue([
      registeredUser(6, 'supervisor', '2026-10-12T00:00:00Z'),
      registeredUser(7, 'student', '2026-10-12T00:00:00Z', { isAdmin: true }),
    ])
    const w = await show(RegistrationPage)
    expect(w.get('[data-testid="analytics-empty-state"]').text()).toContain('No student or mentor registration records are available')
    expect(w.get('.export-button').attributes('disabled')).toBeDefined()
  })

  it('reports a failed participant request and recovers on retry', async () => {
    vi.spyOn(console, 'error').mockImplementation(() => {})
    vi.mocked(api.fetchAllUsers).mockRejectedValue(new Error('HTTP 500'))
    const w = await show(RegistrationPage)
    expect(w.get('[data-testid="analytics-error-state"]').text()).toContain('Registration analytics could not be loaded from the backend.')
    expect(w.get('.export-button').attributes('disabled')).toBeDefined()

    vi.mocked(api.fetchAllUsers).mockResolvedValue(structuredClone(users))
    await w.get('[data-testid="analytics-error-state"] button').trigger('click')
    await flushPromises()
    expect(w.find('[data-testid="analytics-error-state"]').exists()).toBe(false)
    expect(cards(w)[3]).toEqual(['Fully registered students', '1', '33.3% have guardian approval'])
  })

  it('exports every figure on the page as a summary', async () => {
    const csv = await downloadedCsv(await show(RegistrationPage))

    expect(csv).toContain('Section,Metric,Value,Unit,Notes\r\n')
    expect(csv).toContain('Report,Page,Registration Analytics,,\r\n')
    expect(csv).toContain('Report,Covers,Trend 2026-10-08 to 2026-10-15 (UTC); completion and follow-up are current,,\r\n')
    expect(csv).toContain('Report,Filter: Trend interval,day,,\r\n')
    expect(csv).toContain('New registrations,Last 7 days: total,3,users,Up to 2026-10-15\r\n')
    expect(csv).toContain('New registrations,Last 7 days: mentors,1,users,\r\n')
    expect(csv).toContain('Registration completion,Guardian details provided (%),67,%,1 still missing\r\n')
    expect(csv).toContain('Registration completion,Fully registered,33.3,%,Guardian approval received\r\n')
    expect(csv).toContain('Follow-up,Awaiting guardian approval,1,students,\r\n')
    expect(csv).toContain('Follow-up: Awaiting guardian approval,>28 days outstanding,1,students,\r\n')
    expect(csv).toContain('Registration trend (Students),2026-10-14,1,users,\r\n')
    expect(csv).toContain('Registration trend (Mentors),2026-10-15,1,users,\r\n')
    expect(csv).not.toContain('2025-08-01')
  })

  it('exports the follow-up rows shown in the table', async () => {
    const w = await show(RegistrationPage)
    const header = 'Student ID,Student,Email,Supervisor,Registered,Follow-up,Days Outstanding,Source\r\n'

    const missing = await downloadedCsv(w, 'Details')
    expect(missing).toContain(header)
    expect(missing).toContain('\r\n2,Missing Guardian,student2@example.test,Sam Supervisor,2026-10-10,Missing details,5,\r\n')
    expect(missing).not.toContain('student3@example.test')

    await w.findAll('.table-tabs button')[1]!.trigger('click')
    const awaiting = await downloadedCsv(w, 'Details')
    // FileReader drops the byte order mark when it decodes the file.
    expect(awaiting).toBe(`${header}3,Awaiting Approval,student3@example.test,,2026-08-31,Awaiting approval,45,\r\n`)
  })
})
