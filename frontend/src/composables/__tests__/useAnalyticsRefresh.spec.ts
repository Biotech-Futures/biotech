import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest'
import { defineComponent } from 'vue'
import { mount } from '@vue/test-utils'
import { useAnalyticsRefresh } from '@/composables/useAnalyticsRefresh'
import { ANALYTICS_REFRESH_INTERVAL_MS } from '@/utils/analyticsRefresh'

function mountRefresh(refresh: () => Promise<unknown>) {
  return mount(defineComponent({
    setup() {
      useAnalyticsRefresh(refresh)
      return () => null
    },
  }))
}

beforeEach(() => {
  vi.useFakeTimers()
  Object.defineProperty(window, 'scrollX', { configurable: true, value: 48 })
  Object.defineProperty(window, 'scrollY', { configurable: true, value: 720 })
  vi.spyOn(window, 'scrollTo').mockImplementation(() => {})
})

afterEach(() => {
  vi.restoreAllMocks()
  vi.useRealTimers()
})

describe('useAnalyticsRefresh', () => {
  it('refreshes after five minutes and restores the current viewport', async () => {
    const refresh = vi.fn().mockResolvedValue(undefined)
    mountRefresh(refresh)

    await vi.advanceTimersByTimeAsync(ANALYTICS_REFRESH_INTERVAL_MS)

    expect(refresh).toHaveBeenCalledTimes(1)
    expect(window.scrollTo).toHaveBeenCalledWith({
      left: 48,
      top: 720,
      behavior: 'auto',
    })
  })

  it('stops refreshing after the analytics page is left', async () => {
    const refresh = vi.fn().mockResolvedValue(undefined)
    const wrapper = mountRefresh(refresh)

    wrapper.unmount()
    await vi.advanceTimersByTimeAsync(ANALYTICS_REFRESH_INTERVAL_MS)

    expect(refresh).not.toHaveBeenCalled()
  })
})
