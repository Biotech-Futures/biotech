import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest'
import { createPinia, setActivePinia } from 'pinia'
import { mount, flushPromises, type VueWrapper } from '@vue/test-utils'
import App from '@/App.vue'
import router from '@/router'
import { useAuthStore } from '@/stores/auth'
import {
  mentorWithAccess,
  pureAgent,
  student,
  supportWithoutAccess,
  ticketAdmin
} from '@/__tests__/supportAccountFixtures'

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

const adminUser = {
  id: 1,
  email: 'admin@example.com',
  first_name: 'Admin',
  last_name: 'User',
  current_role_name: 'admin'
} as never

const memberUser = {
  id: 2,
  email: 'member@example.com',
  first_name: 'Member',
  last_name: 'User',
  current_role_name: 'student'
} as never

// No '/admin/matching' entry: student and mentor matching are tabs on the
// Groups & Matching page, so the sidebar links to /admin/groups instead.
const adminSubLinks = [
  '/admin/users',
  '/admin/groups',
  '/admin/tasks',
]

let wrapper: VueWrapper | null = null
let pinia: ReturnType<typeof createPinia>

const mountApp = async (options: { viewport?: 'mobile' | 'desktop' } = {}) => {
  globalThis.fetch = vi
    .fn()
    .mockImplementation(() => Promise.resolve(new Response('[]', { status: 200 })))
  const ric = globalThis.requestIdleCallback
  if (!ric) {
    ;(globalThis as unknown as { requestIdleCallback: (cb: () => void) => void }).requestIdleCallback = (cb) => {
      cb()
      return 0
    }
  }

  const mobile = options.viewport !== 'desktop'
  const mediaQuery = {
    matches: mobile,
    media: '(max-width: 768px)',
    onchange: null,
    addEventListener: vi.fn(),
    removeEventListener: vi.fn(),
    addListener: vi.fn(),
    removeListener: vi.fn(),
    dispatchEvent: vi.fn(),
  }
  vi.stubGlobal('matchMedia', vi.fn().mockReturnValue(mediaQuery))

  wrapper = mount(App, {
    global: { plugins: [router, pinia] }
  })
  await router.isReady()
  // Now authenticated, drive into the app shell so the sidebar renders.
  await router.push('/dashboard')
  await router.isReady()
  await flushPromises()
  return mediaQuery
}

describe('App sidebar admin section', () => {
  beforeEach(async () => {
    pinia = createPinia()
    setActivePinia(pinia)
    await router.push('/dashboard')
    await router.isReady()
  })

  afterEach(() => {
    wrapper?.unmount()
    wrapper = null
    vi.unstubAllGlobals()
  })

  it('does not render the Admin nav for non-admins', async () => {
    const auth = useAuthStore()
    auth.loginWithUser(memberUser)
    await mountApp()

    expect(wrapper!.find('a[href="#/admin"]').exists()).toBe(false)
    expect(wrapper!.find('a[href="#/admin/users"]').exists()).toBe(false)
  })

  it('renders the Admin nav and all expected sub-links for admins', async () => {
    const auth = useAuthStore()
    auth.loginWithUser(adminUser)
    await mountApp({ viewport: 'desktop' })

    const text = wrapper!.text()
    expect(text).toContain('Admin')

    const links = wrapper!.findAll('a')
    for (const sub of adminSubLinks) {
      const found = links.some((a) => a.attributes('href') === `#${sub}`)
      expect(found, `expected a sidebar link to ${sub}`).toBe(true)
    }
  })

  it('collapses the Admin submenu by default on small screens', async () => {
    const auth = useAuthStore()
    auth.loginWithUser(adminUser)
    const mediaQuery = await mountApp({ viewport: 'mobile' })

    const text = wrapper!.text()
    expect(text).toContain('Admin')

    const links = wrapper!.findAll('a')
    for (const sub of adminSubLinks) {
      const found = links.some((a) => a.attributes('href') === `#${sub}`)
      expect(found, `expected sub-link ${sub} to be hidden on mobile`).toBe(false)
    }

    const toggle = wrapper!.find('button.sidebar-subnav-toggle')
    expect(toggle.exists()).toBe(true)
    expect(toggle.attributes('aria-expanded')).toBe('false')

    expect(mediaQuery.addEventListener).toHaveBeenCalled()
  })
})

// port-design.md section 4: who sees what, for the five accounts the guard is
// tested with. Desktop viewport, so the Admin submenu is open and its
// sub-links are rendered when the Admin block is. Links are looked up inside
// the sidebar only: the header logo also points at a start page.
describe('App sidebar support entries', () => {
  const memberLinks = ['/dashboard', '/groups', '/events', '/announcements', '/resources', '/support']

  beforeEach(async () => {
    pinia = createPinia()
    setActivePinia(pinia)
    await router.push('/dashboard')
    await router.isReady()
  })

  afterEach(() => {
    wrapper?.unmount()
    wrapper = null
    vi.unstubAllGlobals()
    localStorage.clear()
  })

  const sidebarHas = (path: string) => wrapper!.find(`.sidebar-nav a[href="#${path}"]`).exists()

  // [account, member items, Support queue, Admin block, Support agents, logo target, /users/me/]
  const table: Array<[string, boolean, boolean, boolean, boolean, string, object]> = [
    ['pure support agent', false, true, false, false, '/admin/tickets', pureAgent],
    ['mentor granted access', true, true, false, false, '/dashboard', mentorWithAccess],
    ['role-support account without access', false, false, false, false, '/support-access', supportWithoutAccess],
    ['admin', true, true, true, true, '/dashboard', ticketAdmin],
    ['student', true, false, false, false, '/dashboard', student]
  ]

  it.each(table)(
    '%s: member items %s, Support queue %s, Admin %s, Support agents %s, logo to %s',
    async (_label, members, queue, admin, agents, logo, fixture) => {
      useAuthStore().loginWithUser(fixture as never)
      await mountApp({ viewport: 'desktop' })

      for (const path of memberLinks) {
        expect(sidebarHas(path), `member link ${path}`).toBe(members)
      }
      expect(sidebarHas('/admin/tickets'), 'Support queue').toBe(queue)
      expect(sidebarHas('/admin'), 'Admin').toBe(admin)
      expect(sidebarHas('/admin/support-agents'), 'Support agents').toBe(agents)
      expect(wrapper!.find('a.logo').attributes('href')).toBe(`#${logo}`)
    }
  )

  it('offers the queue once, as a top-level item, and never inside the Admin submenu', async () => {
    useAuthStore().loginWithUser(ticketAdmin as never)
    await mountApp({ viewport: 'desktop' })

    const queueLinks = wrapper!.findAll('.sidebar-nav a[href="#/admin/tickets"]')
    expect(queueLinks).toHaveLength(1)
    expect(queueLinks[0]!.text()).toBe('Support queue')
    expect(queueLinks[0]!.classes()).toContain('sidebar-link')
    expect(wrapper!.find('#admin-subnav a[href="#/admin/tickets"]').exists()).toBe(false)
    expect(wrapper!.find('#admin-subnav a[href="#/admin/support-agents"]').text()).toBe('Support agents')
  })

  it('marks Support queue active on every ticket tab', async () => {
    useAuthStore().loginWithUser(pureAgent as never)
    await mountApp({ viewport: 'desktop' })

    for (const path of ['/admin/tickets', '/admin/tickets/audit', '/admin/tickets/analytics']) {
      await router.push(path)
      await flushPromises()
      expect(router.currentRoute.value.path).toBe(path)
      expect(wrapper!.find('.sidebar-nav a[href="#/admin/tickets"]').classes(), `on ${path}`).toContain('active')
    }
  })

  it('names a support account "Support access" in the account menu, not "Student access"', async () => {
    useAuthStore().loginWithUser(pureAgent as never)
    await mountApp({ viewport: 'desktop' })

    await wrapper!.find('button.user-avatar').trigger('click')
    expect(wrapper!.find('.account-subtitle').text()).toBe('Support access')
    // The way out of an app that offers nothing else.
    expect(wrapper!.find('button.logout-button').exists()).toBe(true)
  })
})
