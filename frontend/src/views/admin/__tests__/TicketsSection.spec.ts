import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest'
import { createPinia, setActivePinia } from 'pinia'
import { flushPromises, mount, type VueWrapper } from '@vue/test-utils'
import { defineComponent, h } from 'vue'
import { RouterView } from 'vue-router'
import router from '@/router'
import { useAuthStore } from '@/stores/auth'
import { pureAgent } from '@/__tests__/supportAccountFixtures'

// These specs mount the real app shell or ticket pages to check routing and
// navigation, not what the pages load. The pages' reads never settle here, so
// they sit in their loading state instead of logging network errors from a
// test that is not about them.
vi.mock('@/utils/ticketAgentAPI', async (importActual) => {
  const actual = await importActual<typeof import('@/utils/ticketAgentAPI')>()
  const pending = () => new Promise<never>(() => {})
  return {
    ...actual,
    fetchTicketQueue: vi.fn(pending),
    fetchTicketSummary: vi.fn(pending),
    fetchAssignees: vi.fn(pending),
    fetchTicketRegions: vi.fn(pending),
    fetchTicketDetail: vi.fn(pending),
    fetchTicketHistory: vi.fn(pending),
    fetchTicketAudit: vi.fn(pending),
    fetchTicketAnalytics: vi.fn(pending),
    fetchSupportRoster: vi.fn(pending)
  }
})

// The section shell rendered through the real route table: the parent
// /admin/tickets record and its child pages, on the real router, signed in as
// a support agent who is not an admin (the account the section exists for).
const Host = defineComponent({ render: () => h(RouterView) })

describe('TicketsSection tab shell', () => {
  let pinia: ReturnType<typeof createPinia>
  let wrapper: VueWrapper | null = null

  const open = async (path: string) => {
    await router.push(path)
    wrapper = mount(Host, { global: { plugins: [router, pinia] } })
    await flushPromises()
  }

  const tabs = () =>
    wrapper!.findAll('[role="tab"]').map((tab) => ({
      label: tab.text(),
      href: tab.attributes('href'),
      selected: tab.attributes('aria-selected'),
      active: tab.classes().includes('active')
    }))

  beforeEach(async () => {
    pinia = createPinia()
    setActivePinia(pinia)
    await router.push('/login')
    useAuthStore().loginWithUser(pureAgent as never)
  })

  afterEach(() => {
    wrapper?.unmount()
    wrapper = null
    vi.restoreAllMocks()
    localStorage.clear()
  })

  it('offers Queue, Audit and Analytics, and never the roster', async () => {
    await open('/admin/tickets/audit')

    expect(wrapper!.find('h1').text()).toBe('Support queue')
    expect(wrapper!.find('[role="tablist"]').attributes('aria-label')).toBe('Support queue sections')
    expect(tabs()).toEqual([
      { label: 'Queue', href: '#/admin/tickets', selected: 'false', active: false },
      { label: 'Audit', href: '#/admin/tickets/audit', selected: 'true', active: true },
      { label: 'Analytics', href: '#/admin/tickets/analytics', selected: 'false', active: false }
    ])
    expect(wrapper!.find('a[href="#/admin/support-agents"]').exists()).toBe(false)
    // The child route renders inside the shell.
    expect(wrapper!.findAll('h1').map((h1) => h1.text())).toEqual(['Support queue', 'Ticket audit'])
  })

  it('lights only Queue on the queue, although its path is a prefix of the other two', async () => {
    await open('/admin/tickets')

    expect(tabs().map((tab) => [tab.label, tab.selected, tab.active])).toEqual([
      ['Queue', 'true', true],
      ['Audit', 'false', false],
      ['Analytics', 'false', false]
    ])
    expect(wrapper!.findAll('h1').map((h1) => h1.text())).toEqual(['Support queue', 'Ticket queue'])
  })

  it('keeps Queue lit when the queue is opened from a ticket link', async () => {
    await open('/admin/tickets?ticket=42')

    expect(tabs().map((tab) => tab.selected)).toEqual(['true', 'false', 'false'])
  })

  it('moves the selection when another tab is clicked', async () => {
    await open('/admin/tickets')
    const push = vi.spyOn(router, 'push')

    await wrapper!.findAll('[role="tab"]')[2]!.trigger('click')
    // The navigation the click started, finished (lazy route components).
    await push.mock.results[0]?.value
    await flushPromises()

    expect(router.currentRoute.value.path).toBe('/admin/tickets/analytics')
    expect(tabs().map((tab) => tab.selected)).toEqual(['false', 'false', 'true'])
    expect(wrapper!.findAll('h1').map((h1) => h1.text())).toEqual(['Support queue', 'Ticket analytics'])
  })
})
