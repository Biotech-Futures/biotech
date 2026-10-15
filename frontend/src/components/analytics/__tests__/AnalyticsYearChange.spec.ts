import { mount } from '@vue/test-utils'
import { describe, expect, it } from 'vitest'

import AnalyticsYearChange from '@/components/analytics/AnalyticsYearChange.vue'

describe('AnalyticsYearChange', () => {
  it('shows only the compact percentage increase', () => {
    const wrapper = mount(AnalyticsYearChange, { props: { current: 125, previous: 100, label: 'vs 2025' } })
    expect(wrapper.text()).toBe('↑25%')
    expect(wrapper.attributes('aria-label')).toBe('Increased by 25% vs 2025')
  })

  it('shows a decrease without producing a negative percentage label', () => {
    const wrapper = mount(AnalyticsYearChange, { props: { current: 75, previous: 100 } })
    expect(wrapper.text()).toBe('↓25%')
  })

  it('does not render a comparison without previous-period data', () => {
    expect(mount(AnalyticsYearChange, { props: { current: 5, previous: 0 } }).find('.analytics-year-change').exists()).toBe(false)
    expect(mount(AnalyticsYearChange, { props: { current: 0, previous: 0 } }).find('.analytics-year-change').exists()).toBe(false)
  })
})
