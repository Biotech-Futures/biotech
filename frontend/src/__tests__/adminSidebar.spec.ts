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

const adminSubLinks = [
  '/admin/users',
  '/admin/groups',
  '/admin/matching',
  '/admin/events',
  '/admin/resources',
  '/admin/announcements',
  '/admin/mentors',
  '/admin/tasks'
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

  it('renders the Admin nav and all eight sub-links for admins', async () => {
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
