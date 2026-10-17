import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest'
import { mount } from '@vue/test-utils'
import { nextTick } from 'vue'
import ChartTooltip from '@/components/analytics/ChartTooltip.vue'

describe('ChartTooltip', () => {
  beforeEach(() => {
    Object.defineProperty(window, 'innerWidth', { configurable: true, value: 1440 })
    Object.defineProperty(window, 'innerHeight', { configurable: true, value: 900 })
    Object.defineProperty(HTMLElement.prototype, 'offsetWidth', {
      configurable: true,
      get() { return this.classList.contains('chart-tooltip') ? 220 : 0 },
    })
    Object.defineProperty(HTMLElement.prototype, 'offsetHeight', {
      configurable: true,
      get() { return this.classList.contains('chart-tooltip') ? 84 : 0 },
    })
    vi.spyOn(HTMLElement.prototype, 'getBoundingClientRect').mockImplementation(function (this: HTMLElement) {
      const width = this.classList.contains('chart-tooltip') ? 198 : 0
      const height = this.classList.contains('chart-tooltip') ? 75.6 : 0
      return {
        x: 0,
        y: 0,
        left: 0,
        top: 0,
        right: width,
        bottom: height,
        width,
        height,
        toJSON: () => ({}),
      }
    })
  })

  afterEach(() => {
    vi.restoreAllMocks()
  })

  it('compensates for the Analytics desktop zoom before positioning', async () => {
    const wrapper = mount(ChartTooltip, {
      props: {
        visible: false,
        x: 1113,
        y: 450,
        title: 'Jul 2026',
        value: '222 student registrations',
      },
    })

    await wrapper.setProps({ visible: true })
    await nextTick()
    await nextTick()

    const tooltip = wrapper.get('.chart-tooltip').element as HTMLElement
    expect(tooltip.style.left).toBe('1013px')
    expect(tooltip.style.top).toBe('412px')
  })
})
