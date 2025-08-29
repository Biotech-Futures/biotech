import type { RouteRecordRaw } from 'vue-router';

const routes: RouteRecordRaw[] = [
  {
    path: '/login',
    name: 'login',
    component: import('@/features/auth/pages/LoginPage.vue'),
  },
  {
    path: '/',
    name: 'home',
    component: import('@/components/HomeView.vue'),
  },
  {
    path: '/dashboard',
    name: 'dashboard',
    component: import('@/features/dashboard/pages/UserDashboardPage.vue'),
  },
]

export default routes;
