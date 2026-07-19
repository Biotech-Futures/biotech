import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest'
import { createPinia, setActivePinia, type Pinia } from 'pinia'
import { flushPromises, mount, type VueWrapper } from '@vue/test-utils'
import { createRouter, createWebHashHistory } from 'vue-router'
import AuthCallbackPage from '../AuthCallbackPage.vue'
import LoginPage from '../LoginPage.vue'
import { SUPPORT_EMAIL } from '@/constants/brand'
import { LOGIN_MESSAGES } from '@/data/login_language'
import { normalizeDirectAuthRedirect } from '@/router/normalizeAuthRedirect'
import { useAuthStore } from '@/stores/auth'

const en = LOGIN_MESSAGES.en
const LOCALES = ['en', 'zh-CN', 'ja', 'ko', 'ar'] as const
const MAGIC_LINK_KEYS = [
  'errorMagicLinkExpired',
  'errorMagicLinkThrottled',
  'errorMagicLinkFailed',
  'accountInactiveContact',
] as const

const stub = { template: '<div />' }

// Deliberately without the app's global auth guard: these specs cover the error mapping, not access control.
const buildRouter = () =>
  createRouter({
    history: createWebHashHistory(),
    routes: [
      { path: '/', redirect: '/login' },
      { path: '/login', name: 'login', component: LoginPage },
      { path: '/auth/callback', name: 'auth-callback', component: AuthCallbackPage },
      { path: '/dashboard', name: 'dashboard', component: stub },
      { path: '/auth/set-password', name: 'set-password', component: stub },
      { path: '/profile', name: 'profile', component: stub },
    ],
  })

const Harness = { template: '<router-view />' }

// The callback view forwards to the login page, so settle the whole redirect chain.
const settle = async () => {
  for (let i = 0; i < 4; i += 1) await flushPromises()
}

let pinia: Pinia
let wrapper: VueWrapper | null = null

const mountLogin = async (query = '') => {
  const router = buildRouter()
  await router.push(`/login${query}`)
  await router.isReady()
  wrapper = mount(LoginPage, { global: { plugins: [router, pinia] } })
  await settle()
  return { wrapper, router }
}

const mountCallback = async (query = '') => {
  const router = buildRouter()
  await router.push(`/auth/callback${query}`)
  await router.isReady()
  wrapper = mount(Harness, { global: { plugins: [router, pinia] } })
  await settle()
  return { wrapper, router }
}

const errorText = () => wrapper?.find('.error-message').text()

const modeButton = (label: string) =>
  wrapper!.findAll('button.login-mode-button').find((item) => item.text() === label)!

// The router runs this once at import; call it directly so the spec does not pull in the whole route graph.
const normalizeAt = (url: string) => {
  window.history.replaceState(null, '', url)
  normalizeDirectAuthRedirect()
}

beforeEach(() => {
  pinia = createPinia()
  setActivePinia(pinia)
  vi.stubGlobal('fetch', vi.fn().mockResolvedValue({ ok: false, json: async () => ({}) }))
  vi.stubGlobal('confirm', vi.fn().mockReturnValue(false))
})

afterEach(() => {
  wrapper?.unmount() // LoginPage clears its cooldown interval on unmount; leaking it hangs the run.
  wrapper = null
  vi.unstubAllGlobals()
})

describe('magic-link error copy', () => {
  it('tells a throttled user to wait and blocks the submit button', async () => {
    await mountLogin('?error=too_many_attempts')

    expect(errorText()).toBe(en.errorMagicLinkThrottled)
    expect(errorText()).toBe('Too many sign-in attempts. Please wait a few minutes before requesting another code.')

    // The headline bug: the old copy told a rate-limited user their link was broken.
    expect(wrapper?.html()).not.toContain('Invalid authentication link')

    const submit = wrapper!.find('button.primary-button')
    expect(submit.attributes('disabled')).toBeDefined()
    expect(submit.text()).toContain('300s')
    expect(submit.text()).toContain(en.resendIn)
  })

  it('explains an expired or already-used link without blocking a retry', async () => {
    await mountLogin('?error=invalid_or_expired_code')

    expect(errorText()).toBe(en.errorMagicLinkExpired)
    expect(errorText()).toBe(
      'This sign-in link is no longer valid. Links expire and can only be used once. Please request a new code.',
    )

    // Must not hint at whether the address is registered: the backend folds User.DoesNotExist into this code.
    expect(errorText()?.toLowerCase()).not.toMatch(/no account|not registered|does not exist/)
    expect(wrapper!.find('button.primary-button').attributes('disabled')).toBeUndefined()
  })

  it('shows the dedicated inactive step and keeps its query', async () => {
    const { router } = await mountLogin('?error=account_inactive')

    expect(wrapper?.text()).toContain(en.accountInactiveTitle)
    expect(wrapper?.text()).toContain(en.accountInactiveBody)

    // The support address has to be readable, not just linked: it is the only way off this screen.
    const support = wrapper!.find('.support-row a')
    expect(support.text()).toBe(SUPPORT_EMAIL)
    expect(support.attributes('href')).toBe(`mailto:${SUPPORT_EMAIL}`)
    expect(wrapper?.text()).toContain(en.accountInactiveContact)

    expect(router.currentRoute.value.query.error).toBe('account_inactive')
    expect(wrapper?.find('.error-message').exists()).toBe(false)
    expect(wrapper?.find('.auth-progress').exists()).toBe(false)
  })

  it('degrades an unrecognised code to the generic message', async () => {
    await mountLogin('?error=some_future_backend_code')

    expect(errorText()).toBe(en.errorMagicLinkFailed)
    expect(errorText()).toBe('We could not complete that sign-in link. Please request a new code.')
  })

  it('does not resolve inherited Object properties as copy', async () => {
    for (const code of ['constructor', 'toString', '__proto__']) {
      await mountLogin(`?error=${code}`)

      expect(errorText()).toBe(en.errorMagicLinkFailed)
      expect(wrapper?.html()).not.toContain('native code')

      wrapper?.unmount()
      wrapper = null
    }
  })

  it('never renders a hostile code into the DOM', async () => {
    const hostile = `<img src=x onerror=alert(1)>${'z'.repeat(3000)}`
    await mountLogin(`?error=${encodeURIComponent(hostile)}`)

    expect(errorText()).toBe(en.errorMagicLinkFailed)
    expect(wrapper?.find('img[onerror]').exists()).toBe(false)
    expect(wrapper?.html()).not.toContain('onerror=alert')
    expect(wrapper?.html()).not.toContain('zzzz')
  })

  it('handles a repeated error param by taking the first value', async () => {
    await mountLogin('?error=too_many_attempts&error=zzz')
    expect(errorText()).toBe(en.errorMagicLinkThrottled)
    wrapper?.unmount()

    const { router } = await mountLogin('?error=account_inactive&error=zzz')
    expect(wrapper?.text()).toContain(en.accountInactiveTitle)
    expect(router.currentRoute.value.query.error).toEqual(['account_inactive', 'zzz'])
  })

  it('strips the error param so a refresh does not replay the failure', async () => {
    const { router } = await mountLogin('?error=too_many_attempts')

    expect(router.currentRoute.value.query.error).toBeUndefined()
    expect(errorText()).toBe(en.errorMagicLinkThrottled) // same-route replace must not wipe the message
  })

  it('shows a clean form when there is no error param', async () => {
    await mountLogin()

    expect(wrapper?.find('.error-message').exists()).toBe(false)
    expect(wrapper?.find('button.primary-button').exists()).toBe(true)
    expect(wrapper?.text()).toContain(en.emailLabel)
  })

  it('leaves password sign-in usable while the code cooldown runs', async () => {
    const auth = useAuthStore()
    auth.loginWithPassword = vi.fn(async () => {
      auth.user = {
        id: 1,
        email: 'someone@example.com',
        first_name: 'Test',
        last_name: 'Student',
        current_role_name: 'student',
        must_change_password: false,
      }
      return auth.user
    })

    await mountLogin('?error=too_many_attempts')
    await modeButton(en.passwordSignIn).trigger('click')
    await settle()

    // The OTP throttle must not gate password auth, which the backend limits separately.
    const submit = wrapper!.find('button.primary-button')
    expect(submit.attributes('disabled')).toBeUndefined()
    expect(submit.text()).toBe(en.signIn)
    expect(submit.text()).not.toContain('300s')

    await wrapper!.find('input[type="email"]').setValue('someone@example.com')
    await wrapper!.find('input[type="password"]').setValue('correct-horse')
    await wrapper!.find('form.auth-form').trigger('submit')
    await settle()

    expect(auth.loginWithPassword).toHaveBeenCalledWith('someone@example.com', 'correct-horse')
  })

  it('still blocks a fresh code request while the cooldown runs', async () => {
    await mountLogin('?error=too_many_attempts')
    await modeButton(en.passwordSignIn).trigger('click')
    await modeButton(en.emailCodeSignIn).trigger('click')
    await settle()

    const submit = wrapper!.find('button.primary-button')
    expect(submit.attributes('disabled')).toBeDefined()
    expect(submit.text()).toContain(en.resendIn)
  })

  it('defines every magic-link key in all five locales', () => {
    for (const locale of LOCALES) {
      for (const key of MAGIC_LINK_KEYS) {
        const value = LOGIN_MESSAGES[locale][key]
        expect(typeof value, `${locale}.${key}`).toBe('string')
        expect(value.length, `${locale}.${key}`).toBeGreaterThan(0)
      }
    }
  })
})

describe('auth callback forwarding', () => {
  it('forwards a backend error to the login page instead of rendering its own screen', async () => {
    const { router } = await mountCallback('?error=too_many_attempts')

    expect(router.currentRoute.value.path).toBe('/login')
    expect(errorText()).toBe(en.errorMagicLinkThrottled)
    expect(wrapper?.html()).not.toContain('Authentication Failed')
    expect(wrapper?.html()).not.toContain('Invalid authentication link')
    expect(wrapper?.find('.error-state').exists()).toBe(false)
  })

  it('forwards an inactive account exactly as before', async () => {
    const { router } = await mountCallback('?error=account_inactive')

    expect(router.currentRoute.value.path).toBe('/login')
    expect(router.currentRoute.value.query.error).toBe('account_inactive')
    expect(wrapper?.text()).toContain(en.accountInactiveTitle)
  })

  it('treats a callback with no params as a generic failure, not a blank screen', async () => {
    await mountCallback()

    expect(errorText()).toBe(en.errorMagicLinkFailed)
  })

  it('gives a distinct message when the session cannot be loaded', async () => {
    const auth = useAuthStore()
    auth.fetchUserData = vi.fn().mockResolvedValue(null)

    await mountCallback('?success=true&email=someone@example.com')

    expect(errorText()).toBe(en.errorUserLoadFailed)
    expect(errorText()).toBe('Signed in, but your profile could not be loaded. Please try again.')
    expect(wrapper?.html()).not.toContain('someone@example.com') // do not echo the address back
  })

  it('still completes the happy path', async () => {
    const auth = useAuthStore()
    auth.fetchUserData = vi.fn(async () => {
      auth.user = {
        id: 1,
        email: 'someone@example.com',
        first_name: 'Test',
        last_name: 'Student',
        current_role_name: 'student',
        must_change_password: false,
      }
      return auth.user
    })

    const { router } = await mountCallback('?success=true&email=someone@example.com')

    expect(auth.fetchUserData).toHaveBeenCalled()
    expect(router.currentRoute.value.path).toBe('/dashboard')
  })
})

describe('auth redirect normalisation', () => {
  it('rescues an error redirect that arrived without the hash', () => {
    // The backend builds error redirects from a fragment-stripped base, so the code lands in location.search.
    normalizeAt('/?error=too_many_attempts')

    expect(window.location.hash).toBe('#/auth/callback?error=too_many_attempts')
    expect(window.location.search).toBe('')
  })

  it('still rewrites a path-style callback and leaves a correct hash URL alone', () => {
    normalizeAt('/auth/callback?error=account_inactive')
    expect(window.location.hash).toBe('#/auth/callback?error=account_inactive')

    normalizeAt('/#/auth/callback?error=too_many_attempts')
    expect(window.location.hash).toBe('#/auth/callback?error=too_many_attempts')
  })

  it('does not hijack an ordinary visit with no error param', () => {
    normalizeAt('/')
    expect(window.location.hash).toBe('')

    normalizeAt('/?next=%2Fgroups')
    expect(window.location.hash).toBe('')
    expect(window.location.search).toBe('?next=%2Fgroups')
  })
})
