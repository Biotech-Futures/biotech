/**
 * @file index.ts
 * @description index.ts is the central router entry file that creates the Vue Router instance, applies hash-based history mode, registers the predefined route table, and manages global authentication guards for route access control.
 * @author Shiqi Fang
 * @author Jiachen Ding
 * @author Qin Chen
 * @version 1.1.0
 *
 * Project: Group Based 5703 Capstone Project
 * Group: CS17-1
 * Team: Frontend
 *
 * Main Frontend Contributors:
 * - Shiqi Fang
 * - Jiachen Ding
 * - Qin Chen
 *
 * File Type: Router Configuration File
 * Route Scope: Global router entry
 * Purpose: Initialize the frontend routing system and control page access based on authentication status.
 * Structure: Router instance creation with hash history mode, predefined route injection, and global beforeEach route guard logic.
 * Responsibilities:
 * - Create and export the global Vue Router instance
 * - Register the predefined route table imported from routes.ts
 * - Apply global authentication guard logic before every route navigation
 * - Restore local authentication state and fetch user role information when required
 * - Redirect unauthenticated users to the login page and redirect authenticated users away from the login page
 * Dependencies:
 * - Vue Router
 * - Pinia Auth Store
 *
 * Revision Summary:
 * - Major revisions: 1
 * - Minor revisions: 1
 *
 * Last Modified: 2026-04-01
 * Modified By: CS17-1 Frontend Team
 * Modification Notes:
 * - Standardized the file header for the CS17-1 frontend router files
 * - Clarified the file purpose, route guard logic, and responsibility scope
 *
 * Notes:
 * - Keep comments in English.
 * - Keep naming consistent with the project convention.
 * - Update Last Modified, Modified By, and Modification Notes after meaningful changes.
 */


import { createRouter, createWebHashHistory } from 'vue-router'

import routes from './routes'
import { normalizeDirectAuthRedirect } from './normalizeAuthRedirect'

normalizeDirectAuthRedirect()

const router = createRouter({
  history: createWebHashHistory(),
  routes: routes
})

import { useAuthStore } from '../stores/auth'
import { landingPath, SUPPORT_ACCESS_PATH } from '@/utils/landing'

// Pages a support-only account may open besides the ticket routes: its own
// profile (the timezone prompt after sign-in sends people there) and the page
// that explains a missing queue grant.
const SUPPORT_ONLY_EXTRA_PATHS = ['/profile', SUPPORT_ACCESS_PATH]

router.beforeEach((to, from, next) => {

  const publicPaths = ['/login', '/auth/callback', '/auth/reset-password']
  const passwordSetupPath = '/auth/set-password'
  const auth = useAuthStore()
  const isPublicPath = publicPaths.includes(to.path)
  const isPasswordSetupPath = to.path === passwordSetupPath
  const requiresAdmin = to.meta.requiresAdmin === true
  // meta.requiresSupport sits on the /admin/tickets parent and Vue Router
  // merges it into every child's meta, so this covers the whole section.
  const isTicketRoute = to.meta.requiresSupport === true

  if (isPasswordSetupPath && !auth.isAuthenticated) {
    next('/login')

  } else if (auth.isAuthenticated && auth.mustChangePassword && !isPasswordSetupPath) {
    next(passwordSetupPath)

  } else if (isPasswordSetupPath && auth.isAuthenticated && !auth.mustChangePassword) {
    next(landingPath(auth))

  } else if (!isPublicPath && !auth.isAuthenticated) {
    next('/login')

  } else if (isTicketRoute && !auth.canWorkTickets) {
    // Queue access is the server's isSupport flag, not the role: a student
    // goes home, a role-support account without access goes to the page that
    // says why.
    next(landingPath(auth))

  } else if (
    auth.isSupportOnly &&
    !isPublicPath &&
    !isTicketRoute &&
    !SUPPORT_ONLY_EXTRA_PATHS.includes(to.path) &&
    !to.path.startsWith('/auth/')
  ) {
    // A support agent who is not an admin gets the queue and nothing else.
    // Hiding the rest is a courtesy, not the control: the member and admin
    // endpoints refuse them at the server (adminweb Nav.tsx). The /auth
    // clause is load-bearing: an agent who still owes a password is sent to
    // /auth/set-password by the rules above, and without it this rule would
    // send them straight back to the landing, which sends them there again.
    next(landingPath(auth))

  } else if ((requiresAdmin || to.meta.adminOnly) && !auth.isAdmin) {
    // Admin-only routes are off-limits to non-admins; send them to their own
    // start page (members home, a support agent to the queue).
    next(landingPath(auth))

  } else if (to.path === '/login' && auth.isAuthenticated) {
    // landingPath() answers the set-password case first, as this branch did.
    next(landingPath(auth))
  } else {
    next()
  }
})

export default router
