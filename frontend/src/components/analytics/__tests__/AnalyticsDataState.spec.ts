import { describe, expect, it } from 'vitest'
import { mount } from '@vue/test-utils'

import AnalyticsDataState from '@/components/analytics/AnalyticsDataState.vue'

function mountState(props: { loading: boolean; error?: string; empty: boolean }) {
  return mount(AnalyticsDataState, {
    props,
    slots: { default: '<div data-testid="analytics-ready-state">Ready, including valid zeroes</div>' },
  })
}

describe('AnalyticsDataState', () => {
  it('keeps loading, failure, empty and ready states mutually exclusive', async () => {
    const wrapper = mountState({ loading: true, empty: false })
    expect(wrapper.find('[data-testid="analytics-loading-state"]').exists()).toBe(true)
    expect(wrapper.find('[data-testid="analytics-ready-state"]').exists()).toBe(false)

    await wrapper.setProps({ loading: false, error: 'The API is unavailable.', empty: false })
    expect(wrapper.get('[data-testid="analytics-error-state"]').text()).toContain('The API is unavailable.')
    expect(wrapper.find('[data-testid="analytics-ready-state"]').exists()).toBe(false)

    await wrapper.setProps({ loading: false, error: '', empty: true })
    expect(wrapper.find('[data-testid="analytics-empty-state"]').exists()).toBe(true)
    expect(wrapper.find('[data-testid="analytics-ready-state"]').exists()).toBe(false)

    await wrapper.setProps({ loading: false, error: '', empty: false })
    expect(wrapper.get('[data-testid="analytics-ready-state"]').text()).toContain('valid zeroes')
  })

  it('emits retry from both error and empty states', async () => {
    const wrapper = mountState({ loading: false, error: 'Offline', empty: false })
    await wrapper.get('button').trigger('click')
    expect(wrapper.emitted('retry')).toHaveLength(1)

    await wrapper.setProps({ error: '', empty: true })
    await wrapper.get('button').trigger('click')
    expect(wrapper.emitted('retry')).toHaveLength(2)
  })
})
