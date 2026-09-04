export interface RegistrationAccessState {
  isAuthenticated: boolean
  isSupervisor: boolean
  isAdmin: boolean
}

export const resolveSupervisorRegistrationAccess = (
  auth: RegistrationAccessState,
): true | '/login' | '/dashboard' => {
  if (!auth.isAuthenticated) return '/login'
  if (!auth.isSupervisor && !auth.isAdmin) return '/dashboard'
  return true
}

export const shouldShowSupervisorRegistrationNavigation = (
  auth: Pick<RegistrationAccessState, 'isAuthenticated' | 'isSupervisor'>,
): boolean => auth.isAuthenticated && auth.isSupervisor
