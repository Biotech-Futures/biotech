import type { RouteLocationNormalized } from 'vue-router'

export interface RegistrationAccessState {
  isAuthenticated: boolean
  isSupervisor: boolean
  isAdmin: boolean
}

type RouteAccessTarget = Pick<RouteLocationNormalized, 'meta'>

export const isSupervisorRegistrationRoute = (route: RouteAccessTarget): boolean =>
  route.meta.supervisorRegistration === true

export const isShellFreeRoute = (route: RouteAccessTarget): boolean =>
  route.meta.shellFree === true

export const resolveSupervisorRegistrationAccess = (
  auth: RegistrationAccessState,
): true | '/login' | '/dashboard' => {
  if (!auth.isAuthenticated) return '/login'
  if (!auth.isSupervisor && !auth.isAdmin) return '/dashboard'
  return true
}

export const resolveSupervisorRegistrationRouteAccess = (
  route: RouteAccessTarget,
  auth: RegistrationAccessState,
): true | '/login' | '/dashboard' =>
  isSupervisorRegistrationRoute(route) ? resolveSupervisorRegistrationAccess(auth) : true

export const shouldShowSupervisorRegistrationNavigation = (
  auth: Pick<RegistrationAccessState, 'isAuthenticated' | 'isSupervisor'>,
): boolean => auth.isAuthenticated && auth.isSupervisor
