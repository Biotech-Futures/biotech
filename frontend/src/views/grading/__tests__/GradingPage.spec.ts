import { describe, expect, it, vi } from 'vitest'
import { mount } from '@vue/test-utils'
import GradingPage from '@/views/grading/GradingPage.vue'

const routePath = { value: '/grading/components/SAQ' }
vi.mock('vue-router', () => ({
  useRoute: () => ({
    get path() {
      return routePath.value
    }
  })
}))

const mountPage = () =>
  mount(GradingPage, {
    global: {
      stubs: {
        RouterLink: { props: ['to'], template: '<a :href="to"><slot /></a>' },
        'router-view': true
      }
    }
  })

describe('the grading shell', () => {
  it('offers the three marking sections, with Management moved elsewhere', () => {
    routePath.value = '/grading/components/SAQ'
    const wrapper = mountPage()
    const tabs = wrapper.findAll('.grading__tab')
    expect(tabs.map((t) => t.text())).toEqual(['By component', 'By group', 'Select Finalists'])
    expect(wrapper.text()).not.toContain('Management')
  })

  it('highlights the tab owning the current route', () => {
    routePath.value = '/grading/by-group'
    const wrapper = mountPage()
    const active = wrapper.findAll('.grading__tab--active')
    expect(active).toHaveLength(1)
    expect(active[0]!.text()).toBe('By group')
  })

  it('keeps a tab lit on its deeper sibling routes', () => {
    // The per-group marking detail lives under /grading/groups/…, which
    // belongs to the By group tab even though its link points elsewhere.
    routePath.value = '/grading/groups/7'
    expect(mountPage().find('.grading__tab--active').text()).toBe('By group')

    routePath.value = '/grading/components/POSTER'
    expect(mountPage().find('.grading__tab--active').text()).toBe('By component')
  })
})
