import { createRouter, createWebHashHistory } from 'vue-router'
import routes from './routes'

const router = createRouter({
  history: createWebHashHistory(),
  routes
})

// Auth guard
import { useAuthStore } from '../stores/auth'
router.beforeEach((to, from, next) => {
  const publicPaths = ['/login', '/auth/callback']
  const auth = useAuthStore()
  if (!auth.user) auth.hydrate()

  if (!publicPaths.includes(to.path) && !auth.isAuthenticated) {
    next('/login')
  } else if (to.path === '/login' && auth.isAuthenticated) {
    next('/dashboard')
  } else {
    next()
  }
})

export default router
