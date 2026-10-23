import { describe, expect, it, vi } from 'vitest'
import { mount } from '@vue/test-utils'
import ManagementPage from '@/views/management/ManagementPage.vue'

const routePath = { value: '/management/registration' }
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

const sectionsOf = (wrapper: ReturnType<typeof mountPage>) => wrapper.findAll('[data-test="management-section"]')
const pagesOf = (wrapper: ReturnType<typeof mountPage>) => wrapper.findAll('[role="tab"]')

describe('the management shell', () => {
  it("offers its sections as Grading's tabs, the year's steps then More, each opening its first page", () => {
    routePath.value = '/management/registration'
    const sections = sectionsOf(mountPage())
    const expected = [
      ['Registration', 'registration'],
      ['Challenge Start', 'challenge-start'],
      ['Submission Deadline', 'submission-deadline'],
      ['Symposium', 'notify-finalists'],
      ['Results', 'results'],
      ['New Year', 'new-year'],
      ['More', 'email-checks'],
    ]
    expect(sections.map((section) => section.text())).toEqual(expected.map(([label]) => label))
    expect(sections.map((section) => section.attributes('href'))).toEqual(
      expected.map(([, path]) => `/management/${path}`),
    )
    expect(mountPage().get('nav.tab-bar--main').attributes('aria-label')).toBe('Management sections')
    // Each with its icon, as Grading's.
    expect(sections.every((section) => section.find('i.fas').exists())).toBe(true)
  })

  it.each([
    ['/management/late-registration', 'Registration', ['Registration', 'Late Registration'], 'Late Registration'],
    ['/management/finalist-presentation', 'Symposium', ['Notify Finalists', 'Finalist Presentation'], 'Finalist Presentation'],
    ['/management/release-results', 'Results', ['Results', 'Release Results', 'Document Setup'], 'Release Results'],
    ['/management/known-universities', 'More', ['Email Checks', 'Known Universities'], 'Known Universities'],
  ])('on %s highlights %s and shows its pages, the open one selected', (path, section, pages, open) => {
    routePath.value = path
    const wrapper = mountPage()
    const active = sectionsOf(wrapper).filter((tab) => tab.classes().includes('active'))
    expect(active.map((tab) => tab.text())).toEqual([section])
    expect(active[0]!.attributes('aria-current')).toBe('true')

    const tabs = pagesOf(wrapper)
    expect(tabs.map((tab) => tab.text())).toEqual(pages)
    expect(tabs.filter((tab) => tab.attributes('aria-selected') === 'true').map((tab) => tab.text())).toEqual([open])
  })

  it('shows no second row for a section with one page', () => {
    for (const path of ['/management/challenge-start', '/management/submission-deadline', '/management/new-year']) {
      routePath.value = path
      const wrapper = mountPage()
      expect(pagesOf(wrapper)).toHaveLength(0)
      expect(sectionsOf(wrapper).filter((tab) => tab.classes().includes('active'))).toHaveLength(1)
    }
  })

  it('renders the section content through the nested router view', () => {
    routePath.value = '/management/submission-deadline'
    const wrapper = mountPage()
    expect(wrapper.find('router-view-stub').exists()).toBe(true)
    expect(wrapper.find('h1').text()).toBe('Management')
  })
})
