import { describe, expect, it } from 'vitest'

import { resolveSupervisorRegistrationAccess } from '@/router/registrationAccess'
import {
  EMBEDDED_SUPERVISOR_REGISTRATION_PATH,
  embeddedSupervisorRegistrationRoute,
  SUPERVISOR_REGISTRATION_PATH,
  SUPERVISOR_REGISTRATION_PATHS,
  supervisorRegistrationRoute,
} from '@/router/supervisorRegistrationRoute'
import { resolveRegistrationUiTestAccess } from '@/router/registrationUiTestRoute'

describe('supervisor registration access', () => {
  it('declares the supervisor intake as a non-public route', () => {
    expect(SUPERVISOR_REGISTRATION_PATH).toBe('/supervisor/registration')
    expect(supervisorRegistrationRoute.path).toBe(SUPERVISOR_REGISTRATION_PATH)
    expect(supervisorRegistrationRoute.name).toBe('supervisor-registration')
    expect(supervisorRegistrationRoute.props).toEqual({ mode: 'supervisor' })
    expect(embeddedSupervisorRegistrationRoute.path).toBe(
      EMBEDDED_SUPERVISOR_REGISTRATION_PATH,
    )
    expect(embeddedSupervisorRegistrationRoute.name).toBe('embedded-supervisor-registration')
    expect(embeddedSupervisorRegistrationRoute.props).toEqual({ mode: 'embedded-supervisor' })
    expect(SUPERVISOR_REGISTRATION_PATHS).toEqual([
      '/supervisor/registration',
      '/supervisor/registration/embed',
    ])
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

  it('keeps the UI test route development-only without changing public or supervisor access', () => {
    expect(resolveRegistrationUiTestAccess(false)).toBe('/register')
    expect(resolveRegistrationUiTestAccess(true)).toBe(true)
    expect(SUPERVISOR_REGISTRATION_PATH).toBe('/supervisor/registration')
    expect(EMBEDDED_SUPERVISOR_REGISTRATION_PATH).toBe('/supervisor/registration/embed')
  })
})
