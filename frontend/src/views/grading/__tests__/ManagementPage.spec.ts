import { describe, expect, it, vi } from 'vitest'
import { mount } from '@vue/test-utils'
import ManagementPage from '@/views/grading/ManagementPage.vue'

const routePath = { value: '/management/extend-deadline' }
vi.mock('vue-router', () => ({
  useRoute: () => ({
    get path() {
      return routePath.value
    }
  })
}))

const mountPage = () =>
  mount(ManagementPage, {
    global: {
      stubs: {
        RouterLink: {
          props: ['to'],
          template: '<a :href="to" v-bind="$attrs"><slot /></a>'
        },
        'router-view': true
      }
    }
  })

describe('the management shell', () => {
  it('offers only the two live sections as tabs', () => {
    const wrapper = mountPage()
    const tabs = wrapper.findAll('[role="tab"]')
    expect(tabs.map((t) => t.text())).toEqual(['Submission Deadline', 'Extend Deadline'])
    // The parked sections stay routed but must not be offered.
    expect(wrapper.text()).not.toContain('Document Setup')
    expect(wrapper.text()).not.toContain('Release Marks')
  })

  it('marks the tab for the current route as selected', () => {
    routePath.value = '/management/extend-deadline'
    const wrapper = mountPage()
    const tabs = wrapper.findAll('[role="tab"]')
    expect(tabs[0]!.attributes('aria-selected')).toBe('false')
    expect(tabs[1]!.attributes('aria-selected')).toBe('true')
    expect(tabs[1]!.classes()).toContain('active')
  })

  it('renders the section content through the nested router view', () => {
    routePath.value = '/management/submission-deadline'
    const wrapper = mountPage()
    expect(wrapper.find('router-view-stub').exists()).toBe(true)
    expect(wrapper.find('h1').text()).toBe('Management')
  })
})
