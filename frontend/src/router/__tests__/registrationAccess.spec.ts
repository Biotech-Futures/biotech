import { describe, expect, it } from 'vitest'

import {
  resolveSupervisorRegistrationAccess,
  shouldShowSupervisorRegistrationNavigation,
} from '@/router/registrationAccess'
import {
  SUPERVISOR_REGISTRATION_PATH,
  supervisorRegistrationRoute,
} from '@/router/supervisorRegistrationRoute'

describe('supervisor registration access', () => {
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
})
