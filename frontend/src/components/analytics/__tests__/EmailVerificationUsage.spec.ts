import { beforeEach, describe, expect, it, vi } from 'vitest'
import { flushPromises, mount } from '@vue/test-utils'

import EmailVerificationUsage from '@/components/analytics/EmailVerificationUsage.vue'
import { fetchEmailCheckCredits, type EmailCheckCredits } from '@/utils/adminAPI'
import { ApiError } from '@/utils/apiError'

vi.mock('@/utils/adminAPI', () => ({ fetchEmailCheckCredits: vi.fn() }))

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

describe('EmailVerificationUsage', () => {
  beforeEach(() => {
    vi.mocked(fetchEmailCheckCredits).mockReset().mockResolvedValue(response())
  })

  it('shows last-reported balances and configured daily usage', async () => {
    const wrapper = mount(EmailVerificationUsage)
    await flushPromises()

    expect(wrapper.get('[data-test="verification-daily"]').text()).toContain('28 of 100')
    expect(wrapper.get('[data-test="verification-free"]').text()).toContain('72')
    expect(wrapper.get('[data-test="verification-paid"]').text()).toContain('9,650')
    expect(wrapper.text()).toContain('Balance from last verification')
    expect(wrapper.get('[data-test="verification-paid"]').text()).toContain('500')
    expect(wrapper.get('[data-test="verification-paid"]').text()).toContain('100')
  })

  it('does not present zero as accurate usage when daily counting is disabled', async () => {
    vi.mocked(fetchEmailCheckCredits).mockResolvedValue(response({
      lookupsToday: 0,
      dailyCap: 0,
      free: { ...response().free, remaining: null, updatedAt: null },
    }))

    const wrapper = mount(EmailVerificationUsage)
    await flushPromises()

    expect(wrapper.get('[data-test="verification-daily"]').text()).toContain('Unavailable')
    expect(wrapper.get('[data-test="verification-daily"]').text()).toContain('not enabled yet')
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

})
