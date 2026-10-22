import { beforeEach, describe, expect, it, vi } from 'vitest'
import { flushPromises, mount } from '@vue/test-utils'

import EmailChecksPage from '@/views/management/EmailChecksPage.vue'
import { fetchEmailCheckCredits, fetchScheduledJobs, type EmailCheckCredits, type ScheduledJobs } from '@/utils/adminAPI'
import { ApiError } from '@/utils/apiError'

vi.mock('@/utils/adminAPI', () => ({ fetchEmailCheckCredits: vi.fn(), fetchScheduledJobs: vi.fn() }))

const scheduled = (overrides: Partial<ScheduledJobs> = {}): ScheduledJobs => ({
  enabled: true,
  jobs: [
    {
      name: 'bounce_check', label: 'Bounced email check', every: 10, at: 3,
      lastStartedAt: '2026-10-22T01:03:00Z', lastFinishedAt: '2026-10-22T01:03:02Z',
      ok: false, error: 'MailApiError: The Mail API answered 401.'
    },
    {
      name: 'auto_submit', label: 'Submission auto-submit', every: 60, at: 7,
      lastStartedAt: '2026-10-22T01:07:00Z', lastFinishedAt: '2026-10-22T01:07:01Z', ok: true, error: ''
    },
    {
      name: 'guardian_details_reminders', label: 'Guardian details reminders', every: 1440, at: 401,
      lastStartedAt: null, lastFinishedAt: null, ok: null, error: ''
    }
  ],
  ...overrides
})

const credits = (overrides: Partial<EmailCheckCredits> = {}): EmailCheckCredits => ({
  free: {
    configured: true,
    remaining: 412,
    updatedAt: '2026-10-20T01:00:00Z',
    exhausted: false,
    exhaustedAt: null,
    retryAt: null
  },
  paid: {
    configured: true,
    remaining: 9800,
    updatedAt: '2026-10-19T23:00:00Z',
    exhausted: false,
    exhaustedAt: null,
    retryAt: null,
    alertedThresholds: [500]
  },
  thresholds: [500, 100],
  lookupsToday: 37,
  lookupsOn: '2026-10-20',
  dailyCap: 1000,
  sandbox: false,
  ...overrides
})

const mountPage = async () => {
  const wrapper = mount(EmailChecksPage)
  await flushPromises()
  return wrapper
}

beforeEach(() => {
  vi.mocked(fetchScheduledJobs).mockReset().mockResolvedValue(scheduled())
})

describe('Email Checks', () => {
  beforeEach(() => {
    vi.mocked(fetchEmailCheckCredits).mockReset().mockResolvedValue(credits())
  })

  it("shows each key's credit and status, and today's lookups against the limit", async () => {
    const wrapper = await mountPage()

    const free = wrapper.get('[data-test="email-checks-free"]').text()
    expect(free).toContain('Tried first.')
    expect(free).toContain('Working')
    expect(free).toContain('412')
    const paid = wrapper.get('[data-test="email-checks-paid"]').text()
    expect(paid).toContain('9,800')
    expect(paid).toContain('500 (sent)')
    expect(paid).toContain('100')
    expect(wrapper.get('[data-test="email-checks-today"]').text()).toContain('37 of 1,000')
    expect(wrapper.find('[data-test="email-checks-sandbox"]').exists()).toBe(false)
  })

  it('says when a key is not set, out of credit, or not reported yet', async () => {
    vi.mocked(fetchEmailCheckCredits).mockResolvedValue(
      credits({
        free: {
          configured: true,
          remaining: 0,
          updatedAt: null,
          exhausted: true,
          exhaustedAt: '2026-10-20T00:00:00Z',
          retryAt: '2026-10-21T00:00:00Z'
        },
        paid: {
          configured: false,
          remaining: null,
          updatedAt: null,
          exhausted: false,
          exhaustedAt: null,
          retryAt: null,
          alertedThresholds: []
        },
        dailyCap: 0,
        sandbox: true
      })
    )
    const wrapper = await mountPage()

    expect(wrapper.get('[data-test="email-checks-free"]').text()).toMatch(/Out of credit until \d\d\/\d\d\/\d\d/)
    const paid = wrapper.get('[data-test="email-checks-paid"]').text()
    expect(paid).toContain('Not set')
    expect(paid).toContain('Not reported yet')
    expect(wrapper.get('[data-test="email-checks-today"]').text()).toContain('37 (no daily limit)')
    expect(wrapper.find('[data-test="email-checks-sandbox"]').exists()).toBe(true)
  })

  it('reads them again on Refresh, and says why when it cannot', async () => {
    const wrapper = await mountPage()
    vi.mocked(fetchEmailCheckCredits).mockRejectedValueOnce(
      new ApiError({ error: 'Server error', code: 'http_500', request_id: 'x' }, 500)
    )

    await wrapper.get('[data-test="email-checks-refresh"]').trigger('click')
    await flushPromises()

    expect(fetchEmailCheckCredits).toHaveBeenCalledTimes(2)
    expect(wrapper.get('[role="alert"]').text()).toBe('Server error')
    // What was read before stays shown.
    expect(wrapper.get('[data-test="email-checks-free"]').text()).toContain('412')
  })

  it('lists each scheduled job, how often it runs, and how its last run went', async () => {
    vi.mocked(fetchEmailCheckCredits).mockResolvedValue(credits())
    const wrapper = await mountPage()

    const table = wrapper.find('[data-test="scheduled-jobs"]').text()
    expect(table).toContain('Bounced email check')
    expect(table).toContain('Every 10 minutes')
    expect(table).toContain('Failed: MailApiError: The Mail API answered 401.')
    expect(table).toContain('Hourly at :07')
    expect(table).toContain('OK')
    expect(table).toContain('Daily at')
    expect(table).toContain('Not run yet')
    expect(wrapper.find('[data-test="scheduled-jobs-mode"]').text()).toContain('The backend runs these itself')
  })

  it("says when the backend's timer is off", async () => {
    vi.mocked(fetchEmailCheckCredits).mockResolvedValue(credits())
    vi.mocked(fetchScheduledJobs).mockResolvedValue(scheduled({ enabled: false }))
    const wrapper = await mountPage()

    expect(wrapper.find('[data-test="scheduled-jobs-mode"]').text()).toContain("SCHEDULER_ENABLED isn't set")
  })
})
