import { afterEach, describe, expect, it } from 'vitest'
import { mount, type VueWrapper } from '@vue/test-utils'
import AnalyticsExportMenu from '@/components/analytics/AnalyticsExportMenu.vue'
import { DETAILS_OPTION, SUMMARY_OPTION } from '@/utils/analyticsExport'

let wrapper: VueWrapper | undefined
afterEach(() => wrapper?.unmount())

describe('AnalyticsExportMenu', () => {
  it('exports directly when there is one file to offer', async () => {
    wrapper = mount(AnalyticsExportMenu, { props: { options: [SUMMARY_OPTION] } })
    await wrapper.get('.export-button').trigger('click')
    expect(wrapper.emitted('select')).toEqual([['summary']])
    expect(wrapper.find('[role="menu"]').exists()).toBe(false)
  })

  it('lets the admin choose a file and closes afterwards', async () => {
    wrapper = mount(AnalyticsExportMenu, { props: { options: [SUMMARY_OPTION, DETAILS_OPTION] }, attachTo: document.body })
    const button = wrapper.get('.export-button')
    expect(button.attributes('aria-expanded')).toBe('false')
    await button.trigger('click')
    expect(button.attributes('aria-expanded')).toBe('true')
    const items = wrapper.findAll('[role="menuitem"]')
    expect(items.map((item) => item.find('strong').text())).toEqual(['Summary', 'Details'])
    await items[1]!.trigger('click')
    expect(wrapper.emitted('select')).toEqual([['details']])
    expect(wrapper.find('[role="menu"]').exists()).toBe(false)
  })

  it('closes on Escape and on a click outside', async () => {
    wrapper = mount(AnalyticsExportMenu, { props: { options: [SUMMARY_OPTION, DETAILS_OPTION] }, attachTo: document.body })
    await wrapper.get('.export-button').trigger('click')
    document.dispatchEvent(new KeyboardEvent('keydown', { key: 'Escape' }))
    await wrapper.vm.$nextTick()
    expect(wrapper.find('[role="menu"]').exists()).toBe(false)
    await wrapper.get('.export-button').trigger('click')
    document.body.dispatchEvent(new MouseEvent('click', { bubbles: true }))
    await wrapper.vm.$nextTick()
    expect(wrapper.find('[role="menu"]').exists()).toBe(false)
  })

  it('does nothing while disabled or for a disabled option', async () => {
    wrapper = mount(AnalyticsExportMenu, { props: { options: [{ ...SUMMARY_OPTION, disabled: true }] } })
    await wrapper.get('.export-button').trigger('click')
    expect(wrapper.emitted('select')).toBeUndefined()
    await wrapper.setProps({ disabled: true, options: [SUMMARY_OPTION, DETAILS_OPTION] })
    expect(wrapper.get('.export-button').attributes('disabled')).toBeDefined()
  })
})
