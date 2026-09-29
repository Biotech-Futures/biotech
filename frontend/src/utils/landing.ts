// Where a signed-in user belongs when nothing else says where to go: after
// signing in, after setting a first password, when they open /login while
// signed in, and when the guard turns them away from a page. One function,
// because those places used to hard-code '/dashboard' each on their own, and
// a support agent was sent to a student dashboard by all of them.
//
// The fields are the auth store's getters of the same names (stores/auth.ts);
// the store itself satisfies this interface.
export interface LandingAuth {
  mustChangePassword: boolean
  // The role-name isAdmin, the same one the guard checks for /admin. Using the
  // server's AdminScope flag here instead would send an account where the two
  // disagree to a page the guard then refuses, and back again.
  isAdmin: boolean
  isSupportOnly: boolean
  canWorkTickets: boolean
}

export const SET_PASSWORD_PATH = '/auth/set-password'
export const ADMIN_LANDING_PATH = '/admin'
export const TICKET_QUEUE_PATH = '/admin/tickets'
export const SUPPORT_ACCESS_PATH = '/support-access'
export const MEMBER_LANDING_PATH = '/dashboard'

export function landingPath(auth: LandingAuth): string {
  if (auth.mustChangePassword) return SET_PASSWORD_PATH
  if (auth.isAdmin) return ADMIN_LANDING_PATH
  // A support agent who is not an admin gets the queue and nothing else. A
  // role-support account without queue access (revoked on the roster, or
  // never granted) gets a page that says so: an empty app, or a queue link
  // that ends in 403, reads as a broken page rather than as "this is not for
  // you" (adminweb Nav.tsx and AdminHomePage.tsx made the same call).
  if (auth.isSupportOnly) {
    return auth.canWorkTickets ? TICKET_QUEUE_PATH : SUPPORT_ACCESS_PATH
  }
  return MEMBER_LANDING_PATH
}
