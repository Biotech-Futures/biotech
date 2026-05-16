/**
 * @file routes.ts
 * @description routes.ts is the centralized route definition file that declares all frontend page paths, route names, lazy-loaded view components, redirects, dynamic routes, and fallback navigation rules for the application.
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
 * File Type: Route Table Definition File
 * Route Scope: Frontend page mapping
 * Purpose: Provide a unified route configuration table that maps URL paths to corresponding frontend view components.
 * Structure: Route array containing root redirect, public routes, protected routes, dynamic detail routes, and wildcard fallback redirect.
 * Responsibilities:
 * - Define all frontend route paths and route names
 * - Map each route to its corresponding Vue page component
 * - Support lazy loading for page-level components
 * - Handle root path redirection and unmatched path fallback
 * - Provide dynamic route parameters for detail pages such as groups and resources
 *
 * Main Features:
 * - Centralized route definition
 * - Root path redirect to login
 * - Public and protected page routing
 * - Dynamic detail page routing
 * - Lazy-loaded page components
 * - Wildcard fallback redirect
 *
 * Dependencies:
 * - Vue Router Type Definitions
 * - Vue Page Components
 *
 * Revision Summary:
 * - Major revisions: 1
 * - Minor revisions: 1
 *
 * Last Modified: 2026-04-01
 * Modified By: CS17-1 Frontend Team
 * Modification Notes:
 * - Standardized the file header for the CS17-1 frontend router files
 * - Clarified the route table purpose, path mapping logic, and page coverage
 *
 * Notes:
 * - Keep comments in English.
 * - Keep naming consistent with the project convention.
 * - Update Last Modified, Modified By, and Modification Notes after meaningful changes.
 */

import type { RouteRecordRaw } from 'vue-router';
import { useGroupsStore } from '@/stores/groups';

const NO_GROUP_MEMBERSHIP_MESSAGE =
  'You have not been assigned to a group yet. Please contact your mentor.';

// /groups has no id of its own — resolve the user's first group from the
// store and forward there. Falls back to /dashboard when the user has no
// groups, instead of rendering a half-loaded placeholder.
const resolveGroupsLanding = async () => {
  const store = useGroupsStore();
  await store.ensureLoaded();
  const first = store.firstGroup;
  if (first) return { name: 'group-detail', params: { id: first.id }, replace: true };
  window.alert(NO_GROUP_MEMBERSHIP_MESSAGE);
  return { name: 'dashboard', replace: true };
};

const routes: RouteRecordRaw[] = [

  { path: '/', redirect: '/login' },
  { path: '/login', name: 'login', component: () => import('@/views/LoginPage.vue') },
  { path: '/auth/callback', name: 'auth-callback', component: () => import('@/views/AuthCallbackPage.vue') },
  { path: '/auth/reset-password', name: 'password-reset', component: () => import('@/views/PasswordResetPage.vue') },
  { path: '/auth/set-password', name: 'set-password', component: () => import('@/views/SetPasswordPage.vue') },
  { path: '/dashboard', name: 'dashboard', component: () => import('@/views/DashboardPage.vue') },
  { path: '/groups', name: 'groups', component: () => import('@/views/GroupDetailPage.vue'), beforeEnter: resolveGroupsLanding },
  { path: '/groups/:id', name: 'group-detail', component: () => import('@/views/GroupDetailPage.vue') },
  { path: '/resources', name: 'resources', component: () => import('@/views/ResourcesPage.vue') },
  { path: '/resources/:id(\\d+)', name: 'resource-detail', component: () => import('@/views/ResourceDetailPage.vue') },
  { path: '/events', name: 'events', component: () => import('@/views/EventsPage.vue') },
  { path: '/events/:id(\\d+)', name: 'event-detail', component: () => import('@/views/EventsPage.vue') },
  { path: '/profile', name: 'profile', component: () => import('@/views/ProfilePage.vue') },
  { path: '/admin', redirect: '/dashboard' },
  { path: '/announcements', name: 'announcements', component: () => import('@/views/AnnouncementsPage.vue') },
  { path: '/announcements/:id', name: 'announcement-detail', component: () => import('@/views/AnnouncementDetailPage.vue') },
  { path: '/:pathMatch(.*)*', redirect: '/login' }
];

export default routes;
