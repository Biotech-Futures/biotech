import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest'
import { flushPromises, type VueWrapper } from '@vue/test-utils'
import * as api from '@/utils/liveAnalyticsApi'
import * as data from '@/utils/liveAnalyticsData'
import ChartTooltip from '@/components/analytics/ChartTooltip.vue'
import EmailPage from '@/views/EmailMonitoringAnalyticsPage.vue'
import { captureCsv, downloadedCsv, show, unmountPages } from './analyticsPages.shared'

vi.mock('@/utils/liveAnalyticsApi', () => ({
  fetchAllUsers: vi.fn(), fetchAllGroups: vi.fn(), fetchMentors: vi.fn(),
  fetchGroupActivity: vi.fn(), fetchLoginActivity: vi.fn(),
  fetchResourceAnalytics: vi.fn(), fetchEmailDeliveryAnalytics: vi.fn(), fetchAllResources: vi.fn(),
  searchEmailsToRecipient: vi.fn(), downloadEmailRecipientsCsv: vi.fn(),
}))
const routeState = vi.hoisted(() => ({ query: {} as Record<string, string>, hash: '' }))
vi.mock('vue-router', () => ({
  useRoute: () => routeState,
  useRouter: () => ({ push: vi.fn() }),
}))
vi.mock('@/composables/useAnalyticsRefreshState', () => ({ useAnalyticsRefreshState: vi.fn() }))

type RecentSend = NonNullable<api.EmailDeliveryAnalyticsResponse['recent_sends']>[number]
const send = (overrides: Partial<RecentSend> = {}): RecentSend => ({
  id: 11, email_type: 'announcement', email_type_label: 'Announcement notification', title: 'Week 3 update',
  announcement_id: 5, source_mailbox: 'info@biotechfutures.org', started_at: '2026-10-20T10:00:00Z',
  status: 'success', attempted: 40, delivered: 40, failed: 0,
  initiated_by_name: 'Ada Admin', initiated_by_email: 'ada@example.test', recipients_recorded: 40,
  ...overrides,
})
const signInLink = {
  id: 12, email_type: 'magic_link', email_type_label: 'Sign-in link', title: null, started_at: '2026-10-20T09:30:00Z',
  status: 'failed', attempted: 1, delivered: 0, failed: 1, initiated_by_name: '', initiated_by_email: '', recipients_recorded: 1,
} satisfies Partial<RecentSend>

// info@ is at 83% of its quota; the busiest hour is 09:00 UTC.
const emailAnalytics: api.EmailDeliveryAnalyticsResponse = {
  snapshot_at: '2026-10-20T12:00:00Z',
  mailboxes: [
    {
      email: 'info@biotechfutures.org', quota_limit: 3000,
      totals: { attempted: 2500, delivered: 2490, failed: 10, delivery_runs: 4 },
      hourly: [
        { hour: '2026-10-20T09:00:00Z', attempted: 2000, delivered: 1995, failed: 5 },
        { hour: '2026-10-20T11:00:00Z', attempted: 500, delivered: 495, failed: 5 },
      ],
      daily: [
        { date: '2026-10-19', attempted: 100, delivered: 100, failed: 0 },
        { date: '2026-10-20', attempted: 2500, delivered: 2490, failed: 10 },
      ],
    },
    {
      email: 'connect@biotechfutures.org', quota_limit: 3000,
      totals: { attempted: 300, delivered: 300, failed: 0, delivery_runs: 1 },
      hourly: [{ hour: '2026-10-20T11:00:00Z', attempted: 300, delivered: 300, failed: 0 }],
      daily: [{ date: '2026-10-20', attempted: 300, delivered: 300, failed: 0 }],
    },
  ],
  totals: { attempted: 2800, delivered: 2790, failed: 10, delivery_runs: 5 },
  hourly: [], daily: [], recent_deliveries: [],
  status_by_role: [{ role: 'Student', attempted: 40, delivered: 38, opened: null, failed: 2, tracked_deliveries: 1 }],
  role_attribution: {
    basis: 'current_single_role_audience', available: true, complete: false,
    tracked_delivery_runs: 1, unattributed_delivery_runs: 4,
    tracked_attempted: 40, unattributed_attempted: 2760,
    tracked_delivered: 38, unattributed_delivered: 2752,
    tracked_failed: 2, unattributed_failed: 8,
  },
  recent_sends: [
    send(),
    send(signInLink),
    send({ id: 13, title: 'Week 2 update', status: 'partial', attempted: 10, delivered: 8, failed: 2, recipients_recorded: 0, started_at: '2026-10-13T10:00:00Z' }),
  ],
}

const toAmy = (row: Partial<RecentSend>, recipient: Partial<api.EmailRecipient> = {}): api.EmailSendToRecipient => {
  const { id, status, initiated_by_name, initiated_by_email, email_type, email_type_label, title, started_at, attempted, delivered, failed } = send(row)
  return {
    id: id!, status: status === 'sending' ? 'success' : status, initiated_by_name, initiated_by_email,
    email_type, email_type_label, title, started_at, attempted, delivered, failed,
    announcement_id: null, source_mailbox: 'info@biotechfutures.org',
    recipient: { email: 'amy@example.test', user_id: 21, name: 'Amy Chen', status: 'delivered', reason: '', ...recipient },
  }
}

beforeEach(() => {
  vi.resetAllMocks()
  routeState.query = {}
  routeState.hash = ''
  data.clearLiveAnalyticsCache()
  vi.mocked(api.fetchEmailDeliveryAnalytics).mockResolvedValue(structuredClone(emailAnalytics))
})
afterEach(() => {
  unmountPages()
  vi.useRealTimers()
  vi.unstubAllGlobals()
  vi.restoreAllMocks()
})

const cards = (w: VueWrapper) => w.findAll('.kpi-card').map((card) => [
  card.get('.kpi-label').text(), card.get('strong').text(), card.get('small').text(),
])
// Every column except Sent At, which is shown in the viewer's time zone.
const logRows = (w: VueWrapper) => w.findAll('.email-log-table tbody tr').map((row) =>
  row.findAll('td').map((cell) => cell.text()).filter((_, index) => index !== 6))
const select = (w: VueWrapper, label: string) => w.get(`select[aria-label="${label}"]`)
const statusTitles = (w: VueWrapper) => w.findAll('.email-log-table .log-status').map((status) => status.attributes('title'))
// The key insights card has a tooltip of its own; the page's comes last.
const pageTooltip = (w: VueWrapper) => w.findAllComponents(ChartTooltip).at(-1)!

async function searchRecipients(w: VueWrapper, query: string) {
  await w.get('.recipient-search').setValue(query)
  await vi.advanceTimersByTimeAsync(350)
  await flushPromises()
}

describe('Email Monitoring analytics page', () => {
  it('shows mailbox usage, the latest and busiest hours and delivery totals', async () => {
    const w = await show(EmailPage)

    expect(cards(w)).toEqual([
      ['info@biotechfutures.org', '2,500', '83% of 3,000 rolling 24-hour quota'],
      ['connect@biotechfutures.org', '300', '10% of 3,000 rolling 24-hour quota'],
      ['Combined 24-Hour Usage', '2,800', 'Across tracked sending mailboxes'],
      ['Latest Recorded UTC Hour', '800', '2026-10-20 11:00 UTC · attempted recipients'],
      ['Peak Hour', '09:00 UTC', '2026-10-20 · 2000 attempted recipients'],
    ])
    const stats = w.get('.overall-stats-grid').text()
    expect(stats).toContain('Emails Delivered2,790')
    expect(stats).toContain('Sent2,800')
    expect(stats).toContain('Failed10')
    expect(stats).toContain('Emails ClickedUnavailable')
    expect(stats).toContain('Average attempted recipients per delivery run560')

    const quotaRows = w.findAll('.mailbox-quota-row')
    expect(quotaRows.map((row) => row.classes().includes('low-remaining'))).toEqual([true, false])
    expect(quotaRows[1]!.get('.mailbox-stat-row').text()).toContain('Remaining 2,700')
    expect(w.get('.categories-card').text()).toContain('All tracked email2800')
    expect(w.findAll('.mailbox-hour-column')).toHaveLength(2)
    expect(w.findAll('.verification-bars .bar-value').map((bar) => bar.text())).toEqual(['100', '2800'])
    expect(w.get('.alerts-card tbody').text()).toContain('info@biotechfutures.org has used 2,500 of 3,000 messages in the rolling 24-hour window.')
    expect(w.get('.insight-card').text()).toContain('2026-10-20 09:00 UTC')

    await w.get('.info-mailbox-bar').trigger('mouseenter')
    expect(pageTooltip(w).props()).toMatchObject({ visible: true, title: '2026-10-20 09:00 UTC', value: '2000 emails' })
    await w.get('.info-mailbox-bar').trigger('mouseleave')
    expect(pageTooltip(w).props('visible')).toBe(false)
  })

  it('shows delivery by role with the attributed and unattributed counts', async () => {
    const w = await show(EmailPage)
    const card = w.get('.email-status-role-card')

    expect(card.get('.role-attribution-badge').text()).toBe('Partial under current-audience basis')
    expect(card.get('h2 + p').text()).toContain('ending 2026-10-20 12:00 UTC')
    expect(card.get('.role-attribution-summary').text()).toContain('1 attributed delivery run')
    expect(card.get('.role-attribution-summary').text()).toContain('4 unattributed delivery runs')
    expect(card.get('.role-attribution-summary').text()).toContain('2,752 unattributed delivered')
    expect(card.find('.role-attribution-note.partial').exists()).toBe(true)
    expect(card.get('.status-role-row').text()).toBe('Students1 delivery run40 attempted')
    expect(card.findAll('.status-role-segment').map((segment) => segment.attributes('style'))).toEqual(['width: 95%;', 'width: 5%;'])
  })

  it('lists recent sends with their delivery status and recorded recipients', async () => {
    const w = await show(EmailPage)

    expect(w.get('.logs-heading p').text()).toBe('The latest 100 sends of each email type, newest first.')
    expect(logRows(w)).toEqual([
      ['Ada Admin', 'ada@example.test', '40 recipients', '—', 'Announcement notification', 'Week 3 update', 'Delivered', 'CSV'],
      ['System', '—', '1 recipient', '—', 'Sign-in link', 'Sign-in link', 'Failed', 'CSV'],
      ['Ada Admin', 'ada@example.test', '10 recipients', '—', 'Announcement notification', 'Week 2 update', 'Partial', 'Not recorded'],
    ])
    expect(statusTitles(w)).toEqual([
      '40 of 40 delivered, 0 not delivered.',
      'Failed: no recipient received this email. 0 of 1 delivered, 1 not delivered.',
      'Partial: not every recipient received this email. 8 of 10 delivered, 2 not delivered.',
    ])
    expect(w.get('.logs-footer').text()).toBe('3 log entries shown')
  })

  it('filters the logs by status, email type and search text', async () => {
    const w = await show(EmailPage)
    const titles = () => logRows(w).map((row) => row[5])

    await select(w, 'Filter email logs by status').setValue('Failed')
    expect(titles()).toEqual(['Sign-in link'])
    await select(w, 'Filter email logs by status').setValue('Partial')
    expect(titles()).toEqual(['Week 2 update'])
    await select(w, 'Filter email logs by status').setValue('Sending')
    expect(titles()).toEqual([])
    expect(w.get('.logs-footer').text()).toBe('0 log entries shown')
    await select(w, 'Filter email logs by status').setValue('all')

    expect(select(w, 'Filter email logs by email type').findAll('option').map((option) => option.text()))
      .toEqual(['All email types', 'Announcement notification', 'Sign-in link'])
    await select(w, 'Filter email logs by email type').setValue('Announcement notification')
    expect(titles()).toEqual(['Week 3 update', 'Week 2 update'])

    await w.get('input[aria-label="Search email logs"]').setValue('  WEEK 2 ')
    expect(titles()).toEqual(['Week 2 update'])
  })

  it('downloads the recorded recipients of one send', async () => {
    let finish!: () => void
    vi.mocked(api.downloadEmailRecipientsCsv).mockReturnValue(new Promise((resolve) => {
      finish = () => resolve('biotech-email-recipients-send-11.csv')
    }))
    const w = await show(EmailPage)
    const button = () => w.get('button[aria-label="Download recipients of Week 3 update"]')

    expect(button().attributes('title')).toBe('Download the 40 recorded recipients of this email as CSV')
    await button().trigger('click')
    expect(api.downloadEmailRecipientsCsv).toHaveBeenCalledWith(11)
    expect(button().attributes('disabled')).toBeDefined()
    finish()
    await flushPromises()
    expect(button().attributes('disabled')).toBeUndefined()
    expect(w.find('.recipient-error').exists()).toBe(false)

    vi.mocked(api.downloadEmailRecipientsCsv).mockRejectedValue(new Error('HTTP 404'))
    await w.get('button[aria-label="Download recipients of Sign-in link"]').trigger('click')
    await flushPromises()
    expect(api.downloadEmailRecipientsCsv).toHaveBeenLastCalledWith(12)
    expect(w.get('.recipient-error').text()).toBe('The recipient list could not be downloaded.')
  })

  it('finds every recorded email sent to a recipient once three characters are typed', async () => {
    vi.useFakeTimers({ toFake: ['setTimeout', 'clearTimeout'] })
    vi.mocked(api.searchEmailsToRecipient).mockResolvedValue([
      toAmy({}),
      toAmy(signInLink, { status: 'failed', reason: 'mailbox full' }),
    ])
    const w = await show(EmailPage)

    await searchRecipients(w, 'am')
    expect(api.searchEmailsToRecipient).not.toHaveBeenCalled()

    await w.get('.recipient-search').setValue(' amy ')
    await vi.advanceTimersByTimeAsync(349)
    expect(api.searchEmailsToRecipient).not.toHaveBeenCalled()
    await vi.advanceTimersByTimeAsync(1)
    await flushPromises()
    expect(api.searchEmailsToRecipient).toHaveBeenCalledOnce()
    expect(api.searchEmailsToRecipient).toHaveBeenCalledWith('amy')

    expect(w.get('.logs-heading p').text()).toBe('Emails sent to recipients matching “amy”, newest first. Each row is one recipient\'s copy.')
    expect(logRows(w)).toEqual([
      ['Ada Admin', 'ada@example.test', 'Amy Chen', 'amy@example.test', 'Announcement notification', 'Week 3 update', 'Delivered', 'CSV'],
      ['System', '—', 'Amy Chen', 'amy@example.test', 'Sign-in link', 'Sign-in link', 'Failed', 'CSV'],
    ])
    expect(statusTitles(w)).toEqual([
      'Delivered to this recipient.',
      'Not delivered to this recipient: mailbox full.',
    ])
    // Status and type filters still apply to the recipient's emails.
    await select(w, 'Filter email logs by status').setValue('Failed')
    expect(logRows(w).map((row) => row[5])).toEqual(['Sign-in link'])

    // Fewer than three characters goes back to the recent sends.
    await w.get('.recipient-search').setValue('a')
    await select(w, 'Filter email logs by status').setValue('all')
    expect(w.get('.logs-heading p').text()).toBe('The latest 100 sends of each email type, newest first.')
    expect(logRows(w)).toHaveLength(3)
  })

  it('keeps only the latest recipient search and reports one that fails', async () => {
    vi.useFakeTimers({ toFake: ['setTimeout', 'clearTimeout'] })
    let answerFirst!: (rows: api.EmailSendToRecipient[]) => void
    vi.mocked(api.searchEmailsToRecipient)
      .mockReturnValueOnce(new Promise((resolve) => { answerFirst = resolve }))
      .mockRejectedValueOnce(new Error('HTTP 500'))
    const w = await show(EmailPage)

    await searchRecipients(w, 'amy')
    expect(w.get('.logs-footer').text()).toContain('Searching recipients…')

    await searchRecipients(w, 'amy chen')
    expect(w.get('.recipient-error').text()).toBe('Emails to this recipient could not be loaded.')
    expect(logRows(w)).toEqual([])

    // The first search answers last and must not replace the newer result.
    answerFirst([toAmy({})])
    await flushPromises()
    expect(logRows(w)).toEqual([])
    expect(w.get('.logs-heading p').text()).toContain('matching “amy chen”')
  })

  it('exports one row per recipient while searching by recipient', async () => {
    vi.useFakeTimers({ toFake: ['setTimeout', 'clearTimeout'] })
    vi.mocked(api.searchEmailsToRecipient).mockResolvedValue([
      toAmy({}),
      toAmy(signInLink, { status: 'failed', reason: 'mailbox full' }),
    ])
    const w = await show(EmailPage)
    await searchRecipients(w, 'amy')
    vi.useRealTimers()

    const csv = captureCsv()
    await w.get('.download-logs-button').trigger('click')
    const logs = await csv()
    expect(logs).toContain('Send ID,Sent At (UTC),Email Type,Title,Sender,Initiating Admin Email,Recipient,Recipient Email,Status,Reason Not Delivered\r\n')
    expect(logs).toContain('\r\n11,2026-10-20T10:00:00Z,Announcement notification,Week 3 update,Ada Admin,ada@example.test,Amy Chen,amy@example.test,Delivered,\r\n')
    // A system email's title repeats its type, so the Title cell is left empty.
    expect(logs).toMatch(/\r\n12,2026-10-20T09:30:00Z,Sign-in link,,System,[^,]*,Amy Chen,amy@example.test,Failed,mailbox full\r\n/)
  })

  it('exports the recent sends shown with the current filters', async () => {
    const w = await show(EmailPage)
    const header = 'Send ID,Sent At (UTC),Email Type,Title,Sender,Initiating Admin Email,Status,Recipients,Delivered,Not Delivered,Recipients Recorded\r\n'

    const all = await downloadedCsv(w, 'Details')
    expect(all).toContain(header)
    expect(all).toContain('\r\n11,2026-10-20T10:00:00Z,Announcement notification,Week 3 update,Ada Admin,ada@example.test,Delivered,40,40,0,40\r\n')
    expect(all.trim().split('\r\n')).toHaveLength(4)

    await select(w, 'Filter email logs by status').setValue('Partial')
    expect(await downloadedCsv(w, 'Details')).toBe(
      `${header}13,2026-10-13T10:00:00Z,Announcement notification,Week 2 update,Ada Admin,ada@example.test,Partial,10,8,2,0\r\n`,
    )
  })

  it('exports every mailbox, hourly and role figure as a summary', async () => {
    const csv = await downloadedCsv(await show(EmailPage))

    expect(csv).toContain('Report,Page,Email Monitoring Analytics,,\r\n')
    expect(csv).toContain('Report,Covers,Rolling 24 hours to 2026-10-20T12:00:00Z; daily attempts for the last 14 days,,\r\n')
    expect(csv).toContain('Mailbox info@biotechfutures.org,Rolling 24-hour usage,2500,recipients,\r\n')
    expect(csv).toContain('Mailbox info@biotechfutures.org,Quota used,83,%,\r\n')
    expect(csv).toContain('Mailbox connect@biotechfutures.org,Remaining,2700,recipients,\r\n')
    expect(csv).toContain('Rolling 24 hours,Combined usage,2800,recipients,\r\n')
    expect(csv).toContain('Rolling 24 hours,Latest recorded hour,2026-10-20T11:00:00Z,UTC,\r\n')
    expect(csv).toContain('Rolling 24 hours,Peak hour,2026-10-20T09:00:00Z,UTC,\r\n')
    expect(csv).toContain('Rolling 24 hours,Peak hour attempts,2000,recipients,\r\n')
    expect(csv).toContain('Emails,Average recipients per send,560,recipients,\r\n')
    expect(csv).toContain('Attempts per day,2026-10-20,2800,recipients,\r\n')
    expect(csv).toContain('Attempts per hour (connect mailbox),2026-10-20T11:00:00Z,300,recipients,\r\n')
    expect(csv).toContain('Role attribution,Coverage,Partial,,\r\n')
    expect(csv).toContain('Delivery by role (Students),Not delivered,2,recipients,\r\n')
  })

  it('shows idle mailboxes at zero and role attribution as unavailable', async () => {
    const idle = { attempted: 0, delivered: 0, failed: 0, delivery_runs: 0 }
    vi.mocked(api.fetchEmailDeliveryAnalytics).mockResolvedValue({
      snapshot_at: '2026-10-20T12:00:00Z',
      mailboxes: emailAnalytics.mailboxes.map((mailbox) => ({ ...mailbox, totals: idle, hourly: [], daily: [] })),
      totals: idle, hourly: [], daily: [], recent_deliveries: [], recent_sends: [],
    })
    const w = await show(EmailPage)

    // The API always lists both mailboxes, so an idle day is not the empty state.
    expect(w.find('[data-testid="analytics-empty-state"]').exists()).toBe(false)
    expect(cards(w)[3]).toEqual(['Latest Recorded UTC Hour', '0', 'Unavailable · attempted recipients'])
    expect(cards(w)[4]).toEqual(['Peak Hour', '—', '0 attempted recipients'])
    expect(w.get('.overall-stats-grid').text()).toContain('Average attempted recipients per delivery runUnavailable')
    const roles = w.get('.email-status-role-card')
    expect(roles.get('.role-attribution-badge').text()).toBe('Unavailable under current-audience basis')
    expect(roles.get('.role-attribution-note.unavailable').text()).toContain('ending 2026-10-20 12:00 UTC can be attributed')
    expect(w.findAll('.email-log-table tbody tr')).toHaveLength(0)
    expect(await downloadedCsv(w)).toContain('Role attribution,Coverage,,,Unavailable\r\n')
  })

  it('shows a loading state until email delivery data arrives', async () => {
    vi.mocked(api.fetchEmailDeliveryAnalytics).mockReturnValue(new Promise(() => {}))
    const w = await show(EmailPage)
    expect(w.find('[data-testid="analytics-loading-state"]').exists()).toBe(true)
    expect(w.find('.kpi-grid').exists()).toBe(false)
    expect(w.get('.export-button').attributes('disabled')).toBeDefined()
  })

  it('shows an empty state when no delivery has been recorded', async () => {
    vi.mocked(api.fetchEmailDeliveryAnalytics).mockResolvedValue({
      snapshot_at: null, mailboxes: [], totals: { attempted: 0, delivered: 0, failed: 0, delivery_runs: 0 },
      hourly: [], daily: [], recent_deliveries: [],
    })
    const w = await show(EmailPage)
    expect(w.get('[data-testid="analytics-empty-state"]').text()).toContain('No tracked email delivery records are available')
    expect(w.get('.export-button').attributes('disabled')).toBeDefined()
  })

  it('reports a failed email request and recovers on retry', async () => {
    vi.spyOn(console, 'error').mockImplementation(() => {})
    vi.mocked(api.fetchEmailDeliveryAnalytics).mockRejectedValue(new Error('HTTP 500'))
    const w = await show(EmailPage)
    expect(w.get('[data-testid="analytics-error-state"]').text()).toContain('Email analytics could not be loaded from the backend.')
    expect(w.get('.export-button').attributes('disabled')).toBeDefined()

    vi.mocked(api.fetchEmailDeliveryAnalytics).mockResolvedValue(structuredClone(emailAnalytics))
    await w.get('[data-testid="analytics-error-state"] button').trigger('click')
    await flushPromises()
    expect(cards(w)[2]).toEqual(['Combined 24-Hour Usage', '2,800', 'Across tracked sending mailboxes'])
    expect(w.get('.export-button').attributes('disabled')).toBeUndefined()
  })

  it('scrolls to the mailbox usage linked from the Overview', async () => {
    routeState.hash = '#rolling-mailbox-usage'
    vi.useFakeTimers({ toFake: ['setTimeout', 'clearTimeout'] })
    vi.stubGlobal('requestAnimationFrame', (callback: FrameRequestCallback) => { callback(0); return 0 })
    const scrollIntoView = vi.fn()
    Object.defineProperty(HTMLElement.prototype, 'scrollIntoView', { configurable: true, value: scrollIntoView })
    try {
      await show(EmailPage, { attach: true })
      // The section appears once the data loads, so the later retries find it.
      await vi.advanceTimersByTimeAsync(320)
      expect(scrollIntoView).toHaveBeenCalledWith({ behavior: 'smooth', block: 'start' })
    } finally {
      delete (HTMLElement.prototype as Partial<HTMLElement>).scrollIntoView
    }
  })
})
