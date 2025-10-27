import { createRouter, createWebHashHistory } from 'vue-router'
import routes from './routes'

const router = createRouter({
  history: createWebHashHistory(),
  routes
})

// Auth guard
import { useAuthStore } from '../stores/auth'
router.beforeEach(async (to, from, next) => {
  const publicPaths = ['/login', '/auth/callback']
  const auth = useAuthStore()

  // Always try to hydrate from localStorage first
  auth.hydrate()

  // For protected routes, check if we have a session by fetching user data
  if (!publicPaths.includes(to.path)) {
    // If no user in store, try to fetch from backend session
    if (!auth.user) {
      await auth.fetchUserData()
    }
    // If user exists but doesn't have role info, refresh it
    else if (!auth.user.current_role_name) {
      await auth.fetchUserData()
    }
  }

  if (!publicPaths.includes(to.path) && !auth.isAuthenticated) {
    next('/login')
  } else if (to.path === '/login' && auth.isAuthenticated) {
    next('/dashboard')
  } else {
    next()
  }
})

export default router
