import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest'
import { createPinia, setActivePinia } from 'pinia'
import { mount, flushPromises, type VueWrapper } from '@vue/test-utils'
import App from '@/App.vue'
import router from '@/router'
import { useAuthStore } from '@/stores/auth'
import { setSupervisorPages } from '@/composables/useSupervisorPages'
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
    fetchTicketAnalytics: vi.fn(pending)
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
  '/admin/logs',
  '/admin/plan',
]

const analyticsSubLinks = [
  '/analytics/users',
  '/analytics/registration',
  '/analytics/groups',
  '/analytics/mentors',
  '/analytics/activity',
  '/analytics/messages',
  '/analytics/resources',
  '/analytics/email',
]

let wrapper: VueWrapper | null = null
let pinia: ReturnType<typeof createPinia>

const mountApp = async (options: { viewport?: 'mobile' | 'desktop'; start?: string } = {}) => {
  vi.stubGlobal('scrollTo', vi.fn())
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
  await router.push(options.start ?? '/dashboard')
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
    expect(wrapper!.find('a[href="#/admin/logs"]').exists()).toBe(false)
    expect(wrapper!.find('a[href="#/analytics"]').exists()).toBe(false)
  })

  it('keeps Admin expanded and Analytics collapsed by default, and folds Admin on request', async () => {
    const auth = useAuthStore()
    auth.loginWithUser(adminUser)
    await mountApp({ viewport: 'desktop' })

    const text = wrapper!.text()
    expect(text).toContain('Admin')

    let links = wrapper!.findAll('a')
    for (const sub of adminSubLinks) {
      const found = links.some((a) => a.attributes('href') === `#${sub}`)
      expect(found, `expected sub-link ${sub} to be shown initially`).toBe(true)
    }

    const sidebarLinks = wrapper!.findAll('.sidebar-list a')
    const analyticsLinks = sidebarLinks.filter((a) => a.attributes('href') === '#/analytics')
    expect(analyticsLinks).toHaveLength(1)
    // Analytics comes after Admin's own entries, folded.
    const adminIndex = sidebarLinks.findIndex((a) => a.attributes('href') === '#/admin')
    const analyticsIndex = sidebarLinks.findIndex((a) => a.attributes('href') === '#/analytics')
    expect(analyticsIndex).toBeGreaterThan(adminIndex)
    for (const sub of analyticsSubLinks) {
      expect(sidebarLinks.some((a) => a.attributes('href') === `#${sub}`)).toBe(false)
    }

    const toggle = wrapper!.find('button[aria-controls="admin-subnav"]')
    expect(toggle.attributes('aria-expanded')).toBe('true')
    await toggle.trigger('click')

    links = wrapper!.findAll('a')
    for (const sub of adminSubLinks) {
      expect(links.some((a) => a.attributes('href') === `#${sub}`)).toBe(false)
    }
    expect(toggle.attributes('aria-expanded')).toBe('false')

    const adminItem = wrapper!.find('a[href="#/admin"]').element.closest('.sidebar-item')
    expect(adminItem?.textContent).not.toContain('Analytics')
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

    const toggle = wrapper!.find('button[aria-controls="admin-subnav"]')
    expect(toggle.exists()).toBe(true)
    expect(toggle.attributes('aria-expanded')).toBe('false')

    expect(mediaQuery.addEventListener).toHaveBeenCalled()
  })

  it('keeps the Admin submenu in the state selected by the user while navigating', async () => {
    const auth = useAuthStore()
    auth.loginWithUser(adminUser)
    await mountApp({ viewport: 'desktop' })

    const toggle = wrapper!.find('button[aria-controls="admin-subnav"]')
    expect(toggle.attributes('aria-expanded')).toBe('true')

    await toggle.trigger('click')
    expect(toggle.attributes('aria-expanded')).toBe('false')
    await router.push('/analytics')
    await flushPromises()
    expect(toggle.attributes('aria-expanded')).toBe('false')
    expect(wrapper!.find('a[href="#/admin/users"]').exists()).toBe(false)
  })

  it('keeps Group Plans highlighted on the progress route', async () => {
    const auth = useAuthStore()
    auth.loginWithUser(adminUser)
    await mountApp({ viewport: 'desktop' })
    await router.push('/admin/plan/progress')
    await flushPromises()
    expect(router.currentRoute.value.name).toBe('admin-plan-progress')
    expect(router.currentRoute.value.meta.requiresAdmin).toBe(true)
    expect(wrapper!.get('a[href="#/admin/plan"]').classes()).toContain('active')
  })

})

// port-design.md section 4: who sees what, for the five accounts the guard is
// tested with. Desktop viewport, so the Admin submenu is open and its
// sub-links are rendered when the Admin block is. Links are looked up inside
// the sidebar only: the header logo also points at a start page.
describe('App sidebar support entries', () => {
  const memberLinks = ['/dashboard', '/groups', '/events', '/announcements', '/resources', '/support']
  // Management > Challenge Start > Pages Visibility: the date that shows the
  // member pages to students, mentors and supervisors (admins always see
  // them). The table below is who sees what once it has come; the hidden
  // state, which is where it starts, has its own tests at the end.
  const PAGES_SHOWN = { shown: true, shown_from: '2020-01-01T00:00:00Z' }
  const PAGES_HIDDEN = { shown: false, shown_from: null }
  const hiddenPages = ['/dashboard', '/groups', '/events', '/announcements', '/resources']

  beforeEach(async () => {
    pinia = createPinia()
    setActivePinia(pinia)
    setSupervisorPages(PAGES_SHOWN)
    await router.push('/dashboard')
    await router.isReady()
  })

  afterEach(() => {
    wrapper?.unmount()
    wrapper = null
    vi.unstubAllGlobals()
    localStorage.clear()
  })

  afterEach(() => setSupervisorPages(PAGES_HIDDEN))

  const sidebarHas = (path: string) => wrapper!.find(`.sidebar-nav a[href="#${path}"]`).exists()

  // [account, member items, Support queue, Admin block, Support agents, logo target, /users/me/]
  // Support agents is offered to nobody since the roster page went (C-15): the
  // client wants queue access given and taken in the Users tab, by role.
  const table: Array<[string, boolean, boolean, boolean, boolean, string, object]> = [
    ['pure support agent', false, true, false, false, '/admin/tickets', pureAgent],
    ['mentor granted access', true, true, false, false, '/dashboard', mentorWithAccess],
    ['role-support account without access', false, false, false, false, '/support-access', supportWithoutAccess],
    ['admin', true, true, true, false, '/dashboard', ticketAdmin],
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
    expect(wrapper!.find('#admin-subnav a[href="#/admin/support-agents"]').exists()).toBe(false)
  })

  it('names the queue link by its words alone, with the icon hidden from screen readers', async () => {
    // Font Awesome draws the glyph as text, so an icon left exposed puts a
    // private-use character at the front of the link's accessible name.
    useAuthStore().loginWithUser(pureAgent as never)
    await mountApp({ viewport: 'desktop' })

    const link = wrapper!.get('.sidebar-nav a[href="#/admin/tickets"]')
    const icons = link.findAll('i')
    expect(icons.map((icon) => [icon.classes('fa-headset'), icon.attributes('aria-hidden')])).toEqual(
      [[true, 'true']]
    )
    // What a screen reader is left with: the words, and nothing else.
    const exposed = link
      .findAll('*')
      .filter((node) => node.element.closest('[aria-hidden="true"]') === null)
    expect(exposed.map((node) => [node.element.tagName, node.text()])).toEqual([
      ['SPAN', 'Support queue']
    ])
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

  // Support is not one of the pages Pages Visibility hides, so it stays in
  // the menu while the others are hidden: a student or mentor keeps their
  // profile and Support, a supervisor Support beside their own pages. Both
  // start on Support, which the guard lets them open; /dashboard would send
  // them on to /profile, whose loads outlive the test and sign the next one
  // out.
  it('a student while the pages are hidden: My Profile and Support, none of the rest', async () => {
    setSupervisorPages(PAGES_HIDDEN)
    useAuthStore().loginWithUser(student as never)
    await mountApp({ viewport: 'desktop', start: '/support' })

    expect(router.currentRoute.value.path).toBe('/support')
    expect(sidebarHas('/profile'), 'My Profile').toBe(true)
    expect(sidebarHas('/support'), 'Support').toBe(true)
    for (const path of hiddenPages) {
      expect(sidebarHas(path), `hidden page ${path}`).toBe(false)
    }
  })

  it('says below the menu when this year\'s challenge starts, while the pages are hidden and it is still to come', async () => {
    // 00:01 on 27 July in Sydney (AEST, UTC+10).
    const starts = { ...PAGES_HIDDEN, challenge_starts_at: '2099-07-26T14:01:00Z' }
    const note = () => wrapper!.find('[data-test="challenge-start-note"]')

    setSupervisorPages(starts)
    useAuthStore().loginWithUser(student as never)
    await mountApp({ viewport: 'desktop', start: '/support' })
    expect(note().text()).toBe("This year's challenge will start on 27th July 2099.")
    expect(note().get('strong').text()).toBe('27th July 2099')
    // In its own box, below the menu's links.
    const items = wrapper!.findAll('.sidebar-list > li')
    expect(items.at(-1)!.attributes('data-test')).toBe('challenge-start-note')
    wrapper!.unmount()

    // Not once the pages are shown, nor before a date is set, nor for an admin.
    for (const [state, user] of [
      [{ ...PAGES_SHOWN, challenge_starts_at: starts.challenge_starts_at }, student],
      [PAGES_HIDDEN, student],
      [starts, ticketAdmin],
    ] as const) {
      setSupervisorPages(state)
      setActivePinia((pinia = createPinia()))
      useAuthStore().loginWithUser(user as never)
      await mountApp({ viewport: 'desktop', start: '/support' })
      expect(note().exists()).toBe(false)
      wrapper!.unmount()
    }
    wrapper = null
  })

  it('a pure support agent while the pages are hidden: still the queue and nothing else', async () => {
    setSupervisorPages(PAGES_HIDDEN)
    useAuthStore().loginWithUser(pureAgent as never)
    await mountApp({ viewport: 'desktop', start: '/admin/tickets' })

    expect(sidebarHas('/admin/tickets'), 'Support queue').toBe(true)
    for (const path of [...memberLinks, '/profile']) {
      expect(sidebarHas(path), `member link ${path}`).toBe(false)
    }
  })

  describe('a supervisor', () => {
    const supervisor = {
      id: 31,
      email: 'supervisor@example.com',
      first_name: 'Sue',
      last_name: 'Park',
      current_role_name: 'supervisor',
      timezone: 'UTC',
      must_change_password: false,
      isAdmin: false,
      isSupport: false
    }

    it('while the pages are hidden, as they start: Support and none of the rest', async () => {
      setSupervisorPages(PAGES_HIDDEN)
      useAuthStore().loginWithUser(supervisor as never)
      await mountApp({ viewport: 'desktop', start: '/support' })

      expect(router.currentRoute.value.path).toBe('/support')
      expect(sidebarHas('/support'), 'Support').toBe(true)
      for (const path of hiddenPages) {
        expect(sidebarHas(path), `hidden page ${path}`).toBe(false)
      }
    })

    it('once the date has come: every member item, Support among them', async () => {
      useAuthStore().loginWithUser(supervisor as never)
      await mountApp({ viewport: 'desktop' })

      for (const path of memberLinks) {
        expect(sidebarHas(path), `member link ${path}`).toBe(true)
      }
    })
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
