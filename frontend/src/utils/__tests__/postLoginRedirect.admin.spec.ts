import { afterEach, describe, expect, it, vi } from 'vitest'
import type { Router } from 'vue-router'
import { redirectAfterLogin } from '@/utils/postLoginRedirect'

const makeRouter = () => {
  const replace = vi.fn().mockResolvedValue(undefined)
  return { replace } as unknown as Router
}

describe('redirectAfterLogin for admins', () => {
  afterEach(() => {
    vi.unstubAllGlobals()
  })

  it('routes admins into the merged SPA admin dashboard instead of the external portal', async () => {
    const router = makeRouter()
    const auth = {
      isAdmin: true,
      mustChangePassword: false,
      user: { id: 1, timezone: 'UTC' }
    }

    await redirectAfterLogin(auth, router)

    expect(router.replace).toHaveBeenCalledWith('/admin')
  })

  it('routes non-admins to /dashboard', async () => {
    const router = makeRouter()
    // jsdom does not implement window.confirm; prevent the timezone-mismatch
    // prompt so redirectAfterLogin completes cleanly.
    vi.stubGlobal('confirm', vi.fn(() => false))
    const auth = {
      isAdmin: false,
      mustChangePassword: false,
      timeZone: 'UTC',
      user: { id: 2, timezone: 'UTC' }
    }

    await redirectAfterLogin(auth, router)

    expect(router.replace).toHaveBeenCalledWith('/dashboard')
  })
})
