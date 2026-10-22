import { beforeEach, describe, expect, it, vi } from 'vitest'
import { flushPromises, mount } from '@vue/test-utils'

import EmailChecksPage from '@/views/management/EmailChecksPage.vue'
import { fetchEmailCheckCredits, type EmailCheckCredits } from '@/utils/adminAPI'
import { ApiError } from '@/utils/apiError'

vi.mock('@/utils/adminAPI', () => ({ fetchEmailCheckCredits: vi.fn() }))

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
})
