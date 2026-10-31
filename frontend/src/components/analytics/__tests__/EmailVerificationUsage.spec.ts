import { beforeEach, describe, expect, it, vi } from 'vitest'
import { flushPromises, mount } from '@vue/test-utils'

import EmailVerificationUsage from '@/components/analytics/EmailVerificationUsage.vue'
import {
  fetchEmailCheckCredits,
  fetchEmailVerificationRequests,
  type EmailCheckCredits,
  type EmailVerificationRequestUsage,
} from '@/utils/adminAPI'
import { ApiError } from '@/utils/apiError'

vi.mock('@/utils/adminAPI', () => ({
  fetchEmailCheckCredits: vi.fn(),
  fetchEmailVerificationRequests: vi.fn(),
}))

const response = (overrides: Partial<EmailCheckCredits> = {}): EmailCheckCredits => ({
  free: {
    configured: true,
    remaining: 72,
    updatedAt: '2026-10-26T01:00:00Z',
    exhausted: false,
    exhaustedAt: null,
    retryAt: null,
  },
  paid: {
    configured: true,
    remaining: 9_650,
    updatedAt: '2026-10-26T00:30:00Z',
    exhausted: false,
    exhaustedAt: null,
    retryAt: null,
    alertedThresholds: [],
  },
  thresholds: [500, 100],
  lookupsToday: 28,
  lookupsOn: '2026-10-26',
  dailyCap: 100,
  sandbox: false,
  ...overrides,
})

const today = new Date().toISOString().slice(0, 10)
const usageResponse = (overrides: Partial<EmailVerificationRequestUsage> = {}): EmailVerificationRequestUsage => ({
  from: '2026-10-01',
  to: today,
  timezone: 'UTC',
  days: [
    { date: today, key: 'free', outcome: 'valid', requests: 3, credits: 3 },
    { date: today, key: 'paid', outcome: 'invalid', requests: 1, credits: 1 },
  ],
  totals: { requests: 4, credits: 4 },
  ...overrides,
})

describe('EmailVerificationUsage', () => {
  beforeEach(() => {
    vi.mocked(fetchEmailCheckCredits).mockReset().mockResolvedValue(response())
    vi.mocked(fetchEmailVerificationRequests).mockReset().mockResolvedValue(usageResponse())
  })

  it('shows request logging totals and last-reported balances', async () => {
    const wrapper = mount(EmailVerificationUsage)
    await flushPromises()

    expect(wrapper.get('[data-test="verification-daily"]').text()).toContain('4 of 100')
    expect(wrapper.get('[data-test="verification-free"]').text()).toContain('72')
    expect(wrapper.get('[data-test="verification-paid"]').text()).toContain('9,650')
    expect(wrapper.text()).toContain('Balance from last verification')
    expect(wrapper.get('[data-test="verification-paid"]').text()).toContain('500')
    expect(wrapper.get('[data-test="verification-paid"]').text()).toContain('100')
    expect(wrapper.get('[data-test="verification-history"]').text()).toContain('4 requests')
    expect(wrapper.get('[data-test="verification-history"]').text()).toContain('4 credits used')
  })

  it('uses the persistent request log even when no legacy daily cap is configured', async () => {
    vi.mocked(fetchEmailCheckCredits).mockResolvedValue(response({
      lookupsToday: 0,
      dailyCap: 0,
      free: { ...response().free, remaining: null, updatedAt: null },
    }))

    const wrapper = mount(EmailVerificationUsage)
    await flushPromises()

    expect(wrapper.get('[data-test="verification-daily"]').text()).toContain('4')
    expect(wrapper.get('[data-test="verification-daily"]').text()).toContain('3 free')
    expect(wrapper.get('[data-test="verification-daily"]').text()).toContain('1 paid')
    expect(wrapper.get('[data-test="verification-free"]').text()).toContain('Not reported yet')
  })

  it('keeps existing data visible when refresh fails', async () => {
    const wrapper = mount(EmailVerificationUsage)
    await flushPromises()
    vi.mocked(fetchEmailCheckCredits).mockRejectedValueOnce(
      new ApiError({ error: 'Server error', code: 'http_500', request_id: 'x' }, 500),
    )

    await wrapper.setProps({ refreshToken: 1 })
    await flushPromises()

    expect(wrapper.get('[role="alert"]').text()).toBe('Server error')
    expect(wrapper.get('[data-test="verification-paid"]').text()).toContain('9,650')
  })

  it('keeps balances visible and explains when request history fails', async () => {
    vi.mocked(fetchEmailVerificationRequests).mockRejectedValue(
      new ApiError({ error: 'Request history unavailable', code: 'http_500', request_id: 'y' }, 500),
    )

    const wrapper = mount(EmailVerificationUsage)
    await flushPromises()

    expect(wrapper.get('[role="alert"]').text()).toBe('Request history unavailable')
    expect(wrapper.get('[data-test="verification-daily"]').text()).toContain('Unavailable')
    expect(wrapper.get('[data-test="verification-paid"]').text()).toContain('9,650')
  })

})
