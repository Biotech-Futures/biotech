import { describe, expect, it, vi } from 'vitest'
import { mount } from '@vue/test-utils'
import ManagementPage from '@/views/management/ManagementPage.vue'

const routePath = { value: '/management/submission-deadline' }
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
  it('offers every section but the hidden Registration as a tab', () => {
    const wrapper = mountPage()
    const tabs = wrapper.findAll('[role="tab"]')
    const paths = [
      ['Late Registration', 'late-registration'],
      ['Known Universities', 'known-universities'],
      ['Email Checks', 'email-checks'],
      ['Challenge Start', 'challenge-start'],
      ['Submission Deadline', 'submission-deadline'],
      ['Notify Finalists', 'notify-finalists'],
      ['Finalist Presentation', 'finalist-presentation'],
      ['Results', 'results'],
      ['Release Results', 'release-results'],
      ['Document Setup', 'document-setup'],
      ['New Year', 'new-year'],
    ]
    expect(tabs.map((t) => t.text())).toEqual(paths.map(([label]) => label))
    expect(tabs.map((t) => t.attributes('href'))).toEqual(paths.map(([, path]) => `/management/${path}`))
  })

  it('marks only the open tab, Late Registration, as selected', () => {
    routePath.value = '/management/late-registration'
    const tabs = mountPage().findAll('[role="tab"]')
    expect(tabs.map((tab) => tab.attributes('aria-selected'))).toEqual(
      tabs.map((_, index) => String(index === 0)),
    )
  })

  it('marks the tab for the current route as selected', () => {
    routePath.value = '/management/submission-deadline'
    const wrapper = mountPage()
    const tabs = wrapper.findAll('[role="tab"]')
    expect(tabs[0]!.attributes('aria-selected')).toBe('false')
    expect(tabs[4]!.attributes('aria-selected')).toBe('true')
    expect(tabs[4]!.classes()).toContain('active')
  })

  it('renders the section content through the nested router view', () => {
    routePath.value = '/management/submission-deadline'
    const wrapper = mountPage()
    expect(wrapper.find('router-view-stub').exists()).toBe(true)
    expect(wrapper.find('h1').text()).toBe('Management')
  })
})
