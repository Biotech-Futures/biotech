import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest'
import { createMemoryHistory, createRouter, type Router } from 'vue-router'
import { createPinia, setActivePinia } from 'pinia'
import routes from '@/router/routes'
import { redirectAfterLogin, rememberReturnTo, takeReturnTo } from '@/utils/postLoginRedirect'

// A link from an email, e.g. the guardian details email's.
const GUARDIAN_LINK = '/profile?guardian=edit'

const makeRouter = () => {
  const router = createRouter({ history: createMemoryHistory(), routes })
  vi.spyOn(router, 'replace').mockResolvedValue(undefined)
  return router
}

const student = { isAdmin: false, mustChangePassword: false, timeZone: 'UTC', user: { id: 2, timezone: 'UTC' } }

describe('coming back to the page asked for before signing in', () => {
  let router: Router

  beforeEach(() => {
    window.localStorage.clear()
    // jsdom has no window.confirm; no timezone prompt.
    vi.stubGlobal('confirm', vi.fn(() => false))
    router = makeRouter()
  })

  afterEach(() => {
    vi.unstubAllGlobals()
    vi.useRealTimers()
  })

  it('takes a student to the page an email linked to, once', async () => {
    rememberReturnTo(GUARDIAN_LINK)

    await redirectAfterLogin(student, router)
    expect(router.replace).toHaveBeenLastCalledWith(GUARDIAN_LINK)

    // Signing in again later goes to the dashboard as usual.
    await redirectAfterLogin(student, router)
    expect(router.replace).toHaveBeenLastCalledWith('/dashboard')
  })

  it('takes a supervisor there too, else to their profile', async () => {
    const supervisor = { ...student, isSupervisor: true }
    rememberReturnTo('/groups/7')

    await redirectAfterLogin(supervisor, router)
    expect(router.replace).toHaveBeenLastCalledWith('/groups/7')

    await redirectAfterLogin(supervisor, router)
    expect(router.replace).toHaveBeenLastCalledWith('/profile')
  })

  it('takes an admin there too', async () => {
    rememberReturnTo('/admin/emails')
    await redirectAfterLogin({ ...student, isAdmin: true }, router)
    expect(router.replace).toHaveBeenLastCalledWith('/admin/emails')
  })

  it('sets a new password first, then goes there', async () => {
    rememberReturnTo(GUARDIAN_LINK)

    await redirectAfterLogin({ ...student, mustChangePassword: true }, router)

    expect(router.replace).toHaveBeenLastCalledWith('/auth/set-password')
    expect(takeReturnTo(router)).toBe(GUARDIAN_LINK)
  })

  it('keeps the link when the timezone prompt sends them to their profile', async () => {
    vi.stubGlobal('confirm', vi.fn(() => true))
    rememberReturnTo(GUARDIAN_LINK)

    await redirectAfterLogin({ ...student, timeZone: 'Australia/Perth', user: { id: 9, timezone: 'Australia/Perth' } }, router)

    expect(router.replace).toHaveBeenLastCalledWith(GUARDIAN_LINK)
  })

  it('forgets a page asked for over an hour ago', async () => {
    vi.useFakeTimers()
    rememberReturnTo(GUARDIAN_LINK)
    vi.advanceTimersByTime(61 * 60 * 1000)

    await redirectAfterLogin(student, router)

    expect(router.replace).toHaveBeenLastCalledWith('/dashboard')
  })

  it('never remembers sign-in pages, the usual homes, other sites or unknown pages', () => {
    for (const path of ['/login', '/auth/callback?code=1', '/', '/dashboard', '//evil.example', 'https://evil.example']) {
      rememberReturnTo(path)
      expect(takeReturnTo(router)).toBeNull()
    }
    rememberReturnTo('/no-such-page')
    expect(takeReturnTo(router)).toBeNull()
  })
})

describe('the router, for someone signed out', () => {
  beforeEach(() => {
    window.localStorage.clear()
    setActivePinia(createPinia())
  })

  it('sends them to sign in and remembers the page they asked for', async () => {
    const { default: router } = await import('@/router')

    await router.push(GUARDIAN_LINK)

    expect(router.currentRoute.value.path).toBe('/login')
    expect(takeReturnTo(router)).toBe(GUARDIAN_LINK)
  })
})
