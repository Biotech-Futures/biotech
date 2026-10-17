import { describe, expect, it, vi } from 'vitest'
import { mount } from '@vue/test-utils'
import ManagementPage from '@/views/management/ManagementPage.vue'

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
  it('offers every section as a tab', () => {
    const wrapper = mountPage()
    const tabs = wrapper.findAll('[role="tab"]')
    const paths = [
      ['Registration', 'registration'],
      ['Registration Visibility', 'registration-visibility'],
      ['Submission Deadline', 'submission-deadline'],
      ['Extend Deadline', 'extend-deadline'],
      ['Notify Finalists', 'notify-finalists'],
      ['Notify Nonfinalist', 'email-nonfinalist'],
      ['Finalist Presentation', 'finalist-presentation'],
      ['Results', 'results'],
      ['Release Results', 'release-results'],
      ['Document Setup', 'document-setup'],
      ['New Year', 'new-year'],
    ]
    expect(tabs.map((t) => t.text())).toEqual(paths.map(([label]) => label))
    expect(tabs.map((t) => t.attributes('href'))).toEqual(paths.map(([, path]) => `/management/${path}`))
  })

  it("doesn't mark Registration open on Registration Visibility", () => {
    routePath.value = '/management/registration-visibility'
    const tabs = mountPage().findAll('[role="tab"]')
    expect(tabs.map((tab) => tab.attributes('aria-selected'))).toEqual(
      tabs.map((_, index) => String(index === 1)),
    )
  })

  it('marks the tab for the current route as selected', () => {
    routePath.value = '/management/extend-deadline'
    const wrapper = mountPage()
    const tabs = wrapper.findAll('[role="tab"]')
    expect(tabs[0]!.attributes('aria-selected')).toBe('false')
    expect(tabs[3]!.attributes('aria-selected')).toBe('true')
    expect(tabs[3]!.classes()).toContain('active')
  })

  it('renders the section content through the nested router view', () => {
    routePath.value = '/management/submission-deadline'
    const wrapper = mountPage()
    expect(wrapper.find('router-view-stub').exists()).toBe(true)
    expect(wrapper.find('h1').text()).toBe('Management')
  })
})
