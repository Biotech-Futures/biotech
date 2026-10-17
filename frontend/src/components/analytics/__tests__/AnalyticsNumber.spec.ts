import { mount } from '@vue/test-utils'
import { describe, expect, it } from 'vitest'
import AnalyticsNumber from '@/components/analytics/AnalyticsNumber.vue'

describe('AnalyticsNumber', () => {
  it('keeps values below 10,000 in full', () => {
    const wrapper = mount(AnalyticsNumber, { props: { value: 9999 } })
    expect(wrapper.text()).toBe('9,999')
    expect(wrapper.attributes('title')).toBeUndefined()
  })

  it('compacts values from 10,000 and exposes the exact value', () => {
    const wrapper = mount(AnalyticsNumber, { props: { value: 12_345 } })
    expect(wrapper.text()).toBe('12.3k')
    expect(wrapper.attributes('title')).toBe('12,345')
    expect(wrapper.attributes('aria-label')).toBe('12,345')
  })

  it('does not alter labels or percentages', () => {
    expect(mount(AnalyticsNumber, { props: { value: '87.5%' } }).text()).toBe('87.5%')
    expect(mount(AnalyticsNumber, { props: { value: 'N/A' } }).text()).toBe('N/A')
  })
})
