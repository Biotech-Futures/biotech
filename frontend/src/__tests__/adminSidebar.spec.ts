import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest'
import { createPinia, setActivePinia } from 'pinia'
import { mount, flushPromises, type VueWrapper } from '@vue/test-utils'
import App from '@/App.vue'
import router from '@/router'
import { useAuthStore } from '@/stores/auth'

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

const mountApp = async (options: { viewport?: 'mobile' | 'desktop' } = {}) => {
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
