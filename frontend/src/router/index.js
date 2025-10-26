import { createRouter, createWebHashHistory } from 'vue-router'
import LoginPage from '../views/LoginPage.vue'
import DashboardPage from '../views/DashboardPage.vue'
import GroupsPage from '../views/GroupsPage.vue'
import GroupDetailPage from '../views/GroupDetailPage.vue'
import ResourcesPage from '../views/ResourcesPage.vue'
import EventsPage from '../views/EventsPage.vue'
import ProfilePage from '../views/ProfilePage.vue'
import AdminPage from '../views/AdminPage.vue'
import AnnouncementsPage from '../views/AnnouncementsPage.vue'

const router = createRouter({
  history: createWebHashHistory(),
  routes: [
    { path: '/', redirect: '/login' },
    { path: '/login', component: LoginPage },

    { path: '/dashboard', component: DashboardPage },
    { path: '/groups', component: GroupsPage },
    { path: '/groups/:id', component: GroupDetailPage },

    { path: '/resources', component: ResourcesPage },
    { path: '/resources/:id', component: ResourcesPage },
    { path: '/events', component: EventsPage },
    { path: '/profile', component: ProfilePage },
    { path: '/admin', component: AdminPage },

    { path: '/announcements', component: AnnouncementsPage },

    { path: '/:pathMatch(.*)*', redirect: '/login' }
  ]
})

// 登录守卫
import { useAuthStore } from '../stores/auth'
router.beforeEach((to, from, next) => {
  const publicPaths = ['/login']
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
