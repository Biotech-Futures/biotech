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

const normalizeDirectAuthRedirect = () => {
  const directAuthPaths = ['/auth/callback', '/auth/reset-password']

  if (!directAuthPaths.includes(window.location.pathname) || window.location.hash) {
    return
  }

  window.history.replaceState(
    null,
    '',
    `/#${window.location.pathname}${window.location.search}`
  )
}

normalizeDirectAuthRedirect()

const router = createRouter({
  history: createWebHashHistory(),
  routes: routes
})

import { useAuthStore } from '../stores/auth'

const ADMIN_FRONTEND_URL = 'https://mentoringadmin.biotechfutures.org'

router.beforeEach((to, from, next) => {

  const publicPaths = ['/login', '/auth/callback', '/auth/reset-password']
  const auth = useAuthStore()

  if (!publicPaths.includes(to.path) && !auth.isAuthenticated) {
    next('/login')

  } else if (auth.isAuthenticated && auth.isAdmin) {
    window.location.assign(ADMIN_FRONTEND_URL)
    return
  } else if (to.path === '/login' && auth.isAuthenticated) {
    next('/dashboard')
  } else {
    next()
  }
})

export default router
