import { createMemoryHistory, createRouter } from 'vue-router'
import { describe, expect, it } from 'vitest'

import {
  isShellFreeRoute,
  resolveSupervisorRegistrationAccess,
  resolveSupervisorRegistrationRouteAccess,
  shouldShowSupervisorRegistrationNavigation,
} from '@/router/registrationAccess'
import routes from '@/router/routes'
import {
  SUPERVISOR_REGISTRATION_PATH,
  supervisorRegistrationRoute,
} from '@/router/supervisorRegistrationRoute'

describe('supervisor registration access', () => {
  const router = createRouter({
    history: createMemoryHistory(),
    routes,
  })

  it('declares the supervisor intake as a non-public route', () => {
    expect(SUPERVISOR_REGISTRATION_PATH).toBe('/supervisor/registration')
    expect(supervisorRegistrationRoute.path).toBe(SUPERVISOR_REGISTRATION_PATH)
    expect(supervisorRegistrationRoute.name).toBe('supervisor-registration')
    expect(supervisorRegistrationRoute.props).toEqual({ mode: 'supervisor' })
  })

  it('shows supervisor navigation only for an authenticated supervisor', () => {
    expect(
      shouldShowSupervisorRegistrationNavigation({
        isAuthenticated: true,
        isSupervisor: true,
      }),
    ).toBe(true)
    expect(
      shouldShowSupervisorRegistrationNavigation({
        isAuthenticated: false,
        isSupervisor: true,
      }),
    ).toBe(false)
    expect(
      shouldShowSupervisorRegistrationNavigation({
        isAuthenticated: true,
        isSupervisor: false,
      }),
    ).toBe(false)
  })

  it('allows supervisors and administrators', () => {
    expect(
      resolveSupervisorRegistrationAccess({
        isAuthenticated: true,
        isSupervisor: true,
        isAdmin: false,
      }),
    ).toBe(true)
    expect(
      resolveSupervisorRegistrationAccess({
        isAuthenticated: true,
        isSupervisor: false,
        isAdmin: true,
      }),
    ).toBe(true)
  })

  it('redirects unauthenticated and unauthorized accounts', () => {
    expect(
      resolveSupervisorRegistrationAccess({
        isAuthenticated: false,
        isSupervisor: false,
        isAdmin: false,
      }),
    ).toBe('/login')
    expect(
      resolveSupervisorRegistrationAccess({
        isAuthenticated: true,
        isSupervisor: false,
        isAdmin: false,
      }),
    ).toBe('/dashboard')
  })

  it.each(['/supervisor/registration', '/supervisor/registration/'])(
    'guards the normalized supervisor route at %s',
    (path) => {
      const route = router.resolve(path)

      expect(
        resolveSupervisorRegistrationRouteAccess(route, {
          isAuthenticated: false,
          isSupervisor: false,
          isAdmin: false,
        }),
      ).toBe('/login')
      expect(
        resolveSupervisorRegistrationRouteAccess(route, {
          isAuthenticated: true,
          isSupervisor: false,
          isAdmin: false,
        }),
      ).toBe('/dashboard')
      expect(
        resolveSupervisorRegistrationRouteAccess(route, {
          isAuthenticated: true,
          isSupervisor: true,
          isAdmin: false,
        }),
      ).toBe(true)
      expect(
        resolveSupervisorRegistrationRouteAccess(route, {
          isAuthenticated: true,
          isSupervisor: false,
          isAdmin: true,
        }),
      ).toBe(true)
    },
  )

  it.each(['/register', '/register/'])(
    'keeps public registration shell-free at %s',
    (path) => {
      const route = router.resolve(path)

      expect(route.name).toBe('register')
      expect(route.meta.public).toBe(true)
      expect(isShellFreeRoute(route)).toBe(true)
    },
  )

  it('preserves shell treatment for public and authenticated routes', () => {
    expect(isShellFreeRoute(router.resolve('/login'))).toBe(true)
    expect(isShellFreeRoute(router.resolve('/dashboard'))).toBe(false)
    expect(isShellFreeRoute(router.resolve('/supervisor/registration'))).toBe(false)
  })
})
