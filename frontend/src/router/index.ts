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

  // If user exists but doesn't have role info, fetch it from backend
  if (auth.user && !auth.user.current_role_name && !publicPaths.includes(to.path)) {
    await auth.fetchUserData()
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
