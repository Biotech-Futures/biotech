import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest'
import { createPinia, setActivePinia } from 'pinia'
import router from '@/router'
import { useAuthStore } from '@/stores/auth'
import { getBrowserTimeZone } from '@/utils/date'
import { redirectAfterLogin } from '@/utils/postLoginRedirect'
import {
  mentorWithAccess,
  pureAgent,
  student,
  supportWithoutAccess,
  ticketAdmin
} from '@/__tests__/supportAccountFixtures'

// The real store and the real router, as LoginPage and AuthCallbackPage call
// it. Two assertions per case on purpose: what redirectAfterLogin asked for,
// and where the guard then left the user. The second alone would pass even if
// redirectAfterLogin still asked for /dashboard, because the guard corrects a
// support agent on the way.
describe('redirectAfterLogin for support accounts', () => {
  beforeEach(async () => {
    setActivePinia(createPinia())
    await router.push('/login')
    sessionStorage.clear()
  })

  afterEach(() => {
    vi.restoreAllMocks()
    vi.unstubAllGlobals()
    localStorage.clear()
    sessionStorage.clear()
  })

  const landings: Array<[string, string, object]> = [
    ['pure support agent', '/admin/tickets', pureAgent],
    ['mentor granted access', '/dashboard', mentorWithAccess],
    ['role-support account without access', '/support-access', supportWithoutAccess],
    ['admin', '/admin', ticketAdmin],
    ['student', '/dashboard', student]
  ]

  it.each(landings)('%s: lands on %s after signing in', async (_label, expected, fixture) => {
    const auth = useAuthStore()
    // The account's timezone is this device's, so no timezone prompt.
    auth.loginWithUser({ ...fixture, timezone: getBrowserTimeZone() } as never)
    const replace = vi.spyOn(router, 'replace')

    await redirectAfterLogin(auth, router)

    expect(replace).toHaveBeenCalledTimes(1)
    expect(replace).toHaveBeenCalledWith(expected)
    expect(router.currentRoute.value.path).toBe(expected)
  })

  it('sends a new support agent to set a password before the queue', async () => {
    const auth = useAuthStore()
    auth.loginWithUser({ ...pureAgent, must_change_password: true } as never)
    const replace = vi.spyOn(router, 'replace')

    await redirectAfterLogin(auth, router)

    expect(replace).toHaveBeenCalledWith('/auth/set-password')
    expect(router.currentRoute.value.path).toBe('/auth/set-password')
  })

  it('still asks a support agent about a timezone mismatch, and lets them open their profile', async () => {
    const auth = useAuthStore()
    const otherZone = getBrowserTimeZone() === 'Pacific/Chatham' ? 'UTC' : 'Pacific/Chatham'
    auth.loginWithUser({ ...pureAgent, timezone: otherZone } as never)
    const confirm = vi.fn(() => true)
    vi.stubGlobal('confirm', confirm)
    const replace = vi.spyOn(router, 'replace')

    await redirectAfterLogin(auth, router)

    expect(confirm).toHaveBeenCalledTimes(1)
    expect(replace).toHaveBeenCalledWith('/profile')
    expect(router.currentRoute.value.path).toBe('/profile')
  })

  it('goes on to the queue when a support agent declines the timezone prompt', async () => {
    const auth = useAuthStore()
    const otherZone = getBrowserTimeZone() === 'Pacific/Chatham' ? 'UTC' : 'Pacific/Chatham'
    auth.loginWithUser({ ...pureAgent, timezone: otherZone } as never)
    vi.stubGlobal('confirm', vi.fn(() => false))
    const replace = vi.spyOn(router, 'replace')

    await redirectAfterLogin(auth, router)

    expect(replace).toHaveBeenCalledWith('/admin/tickets')
    expect(router.currentRoute.value.path).toBe('/admin/tickets')
  })
})
