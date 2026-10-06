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

  // The switcher is a labelled nav of links, not ARIA tabs (GradingPage.vue
  // is the pattern). `current` is the link's aria-current, absent on every
  // link but the one for the page on screen.
  const switcher = () => wrapper!.get('nav[aria-label="Support queue sections"]')
  const tabs = () =>
    switcher()
      .findAll('a')
      .map((tab) => ({
        label: tab.text(),
        href: tab.attributes('href'),
        current: tab.attributes('aria-current'),
        active: tab.classes().includes('active')
      }))

  // Every heading on the page, in order, with its level.
  const headings = () =>
    wrapper!.findAll('h1, h2, h3, h4, h5, h6').map((h) => [h.element.tagName, h.text()])

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

    expect(tabs()).toEqual([
      { label: 'Queue', href: '#/admin/tickets', current: undefined, active: false },
      { label: 'Audit', href: '#/admin/tickets/audit', current: 'page', active: true },
      { label: 'Analytics', href: '#/admin/tickets/analytics', current: undefined, active: false }
    ])
    expect(wrapper!.find('a[href="#/admin/support-agents"]').exists()).toBe(false)
    // The child route renders inside the shell, its title one level under
    // the shell's h1, which is the only h1 on the page.
    expect(headings()).toEqual([
      ['H1', 'Support queue'],
      ['H2', 'Ticket audit']
    ])
  })

  it('is a navigation landmark of links, not a set of ARIA tabs', async () => {
    // role="tablist" on the nav took its landmark away, and role="tab"
    // promised arrow keys and a tab panel that links to other addresses do
    // not have.
    await open('/admin/tickets/audit')

    expect(switcher().element.tagName).toBe('NAV')
    expect(switcher().attributes('role')).toBeUndefined()
    expect(wrapper!.find('[role="tablist"]').exists()).toBe(false)
    expect(wrapper!.find('[role="tab"]').exists()).toBe(false)
    expect(wrapper!.find('[aria-selected]').exists()).toBe(false)
  })

  it('lights only Queue on the queue, although its path is a prefix of the other two', async () => {
    await open('/admin/tickets')

    expect(tabs().map((tab) => [tab.label, tab.current, tab.active])).toEqual([
      ['Queue', 'page', true],
      ['Audit', undefined, false],
      ['Analytics', undefined, false]
    ])
    // One h1 for the section; the queue tab's own title sits under it.
    expect(wrapper!.findAll('h1').map((h1) => h1.text())).toEqual(['Support queue'])
    expect(wrapper!.findAll('h2').map((h2) => h2.text())).toEqual(['Ticket queue'])
  })

  it('keeps Queue lit when the queue is opened from a ticket link', async () => {
    await open('/admin/tickets?ticket=42')

    expect(tabs().map((tab) => tab.current)).toEqual(['page', undefined, undefined])
  })

  it('moves the selection when another tab is clicked', async () => {
    await open('/admin/tickets')
    const push = vi.spyOn(router, 'push')

    await switcher().findAll('a')[2]!.trigger('click')
    // The navigation the click started, finished (lazy route components).
    await push.mock.results[0]?.value
    await flushPromises()

    expect(router.currentRoute.value.path).toBe('/admin/tickets/analytics')
    expect(tabs().map((tab) => tab.current)).toEqual([undefined, undefined, 'page'])
    // The analytics answer never arrives here, so there are no card headings.
    expect(headings()).toEqual([
      ['H1', 'Support queue'],
      ['H2', 'Ticket analytics']
    ])
  })
})
