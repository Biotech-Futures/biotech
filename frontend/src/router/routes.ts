import type { RouteRecordRaw } from 'vue-router';

const routes: RouteRecordRaw[] = [
  { path: '/', redirect: '/login' },
  { path: '/login', name: 'login', component: () => import('@/views/LoginPage.vue') },
  { path: '/auth/callback', name: 'auth-callback', component: () => import('@/views/AuthCallbackPage.vue') },
  { path: '/dashboard', name: 'dashboard', component: () => import('@/views/DashboardPage.vue') },
  { path: '/groups', name: 'groups', component: () => import('@/views/DashboardPage.vue') },
  { path: '/groups/:id', name: 'group-detail', component: () => import('@/views/GroupDetailPage.vue') },
  { path: '/resources', name: 'resources', component: () => import('@/views/ResourcesPage.vue') },
  { path: '/resources/:id', name: 'resource-detail', component: () => import('@/views/ResourcesPage.vue') },
  { path: '/events', name: 'events', component: () => import('@/views/EventsPage.vue') },
  { path: '/profile', name: 'profile', component: () => import('@/views/ProfilePage.vue') },
  { path: '/admin', name: 'admin', component: () => import('@/views/AdminPage.vue') },
  { path: '/announcements', name: 'announcements', component: () => import('@/views/AnnouncementsPage.vue') },
  { path: '/:pathMatch(.*)*', redirect: '/login' }
];

export default routes;
