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
import { useAuthStore } from '@/stores/auth';
import { SUPPORT_EMAIL } from '@/constants/brand';
import { loadSupervisorResults } from '@/composables/useSupervisorResults';
import { publicRegistrationRoute } from './publicRegistrationRoute';
import { supervisorRegistrationRoute } from './supervisorRegistrationRoute';

const NO_GROUP_MEMBERSHIP_MESSAGE =
  `Please contact the administrator via ${SUPPORT_EMAIL}`;

const requireSupervisor = () => {
  const auth = useAuthStore();
  if (!auth.isSupervisor) return { name: 'dashboard', replace: true };
  return true;
};

// Results opens once marks or certificates are released; till then, My Students.
const requireSupervisorResults = async () => {
  const supervisor = requireSupervisor();
  if (supervisor !== true) return supervisor;
  return (await loadSupervisorResults(true)) ? true : { name: 'my-students', replace: true };
};

// /groups has no id of its own — resolve the user's first group from the
// store and forward there (an admin's list is every group). Falls back to
// /dashboard when the user has no groups, instead of rendering a
// half-loaded placeholder; an admin goes to Admin > Groups to make one.
const resolveGroupsLanding = async () => {
  const auth = useAuthStore();
  const store = useGroupsStore();
  await store.ensureLoaded();
  const first = store.firstGroup;
  if (first) return { name: 'group-detail', params: { id: first.id }, replace: true };
  if (auth.isAdmin) return { name: 'admin-groups', replace: true };
  // A supervisor in no group yet has their students to place, under My Groups.
  if (auth.isSupervisor) return { name: 'my-groups', replace: true };
  window.alert(NO_GROUP_MEMBERSHIP_MESSAGE);
  return { name: 'dashboard', replace: true };
};

const routes: RouteRecordRaw[] = [

  { path: '/', redirect: '/login' },
  { path: '/login', name: 'login', component: () => import('@/views/LoginPage.vue') },
  publicRegistrationRoute,
  supervisorRegistrationRoute,
  { path: '/auth/callback', name: 'auth-callback', component: () => import('@/views/AuthCallbackPage.vue') },
  { path: '/auth/reset-password', name: 'password-reset', component: () => import('@/views/PasswordResetPage.vue') },
  { path: '/reset-password', redirect: (to) => ({ path: '/auth/reset-password', query: to.query }) },
  { path: '/auth/set-password', name: 'set-password', component: () => import('@/views/SetPasswordPage.vue') },
  // Guardians open this from the consent email; no account needed.
  { path: '/consent/:token', name: 'guardian-consent', component: () => import('@/views/ConsentPage.vue'), meta: { public: true, siteHeader: true } },
  // Opened from a supervisor's Copy Details Link; no account needed.
  { path: '/guardian-details/:token', name: 'guardian-details-form', component: () => import('@/views/GuardianDetailsPage.vue'), meta: { public: true, siteHeader: true } },
  { path: '/dashboard', name: 'dashboard', component: () => import('@/views/DashboardPage.vue') },
  { path: '/analytics', name: 'analytics', component: () => import('@/views/AnalyticsPage.vue'), meta: { requiresAdmin: true } },
  { path: '/analytics/users', name: 'users-analytics', component: () => import('@/views/UsersAnalyticsPage.vue'), meta: { requiresAdmin: true } },
  { path: '/analytics/mentors', name: 'mentors-analytics', component: () => import('@/views/MentorsAnalyticsPage.vue'), meta: { requiresAdmin: true } },
  { path: '/analytics/registration', name: 'registration-analytics', component: () => import('@/views/RegistrationAnalyticsPage.vue'), meta: { requiresAdmin: true } },
  { path: '/analytics/groups', name: 'groups-analytics', component: () => import('@/views/GroupsAnalyticsPage.vue'), meta: { requiresAdmin: true } },
  { path: '/analytics/activity', name: 'activity-analytics', component: () => import('@/views/ActivityAnalyticsPage.vue'), meta: { requiresAdmin: true } },
  { path: '/analytics/messages', name: 'messages-analytics', component: () => import('@/views/MessagesAnalyticsPage.vue'), meta: { requiresAdmin: true } },
  { path: '/analytics/resources', name: 'resources-analytics', component: () => import('@/views/ResourcesAnalyticsPage.vue'), meta: { requiresAdmin: true } },
  { path: '/analytics/email', name: 'email-monitoring-analytics', component: () => import('@/views/EmailMonitoringAnalyticsPage.vue'), meta: { requiresAdmin: true } },
  { path: '/my-students', name: 'my-students', component: () => import('@/views/SupervisorStudentsPage.vue'), beforeEnter: requireSupervisor },
  { path: '/my-groups', name: 'my-groups', component: () => import('@/views/SupervisorGroupsPage.vue'), beforeEnter: requireSupervisor },
  { path: '/my-results', name: 'my-results', component: () => import('@/views/SupervisorResultsPage.vue'), beforeEnter: requireSupervisorResults },
  { path: '/groups', name: 'groups', component: () => import('@/views/GroupDetailPage.vue'), beforeEnter: resolveGroupsLanding },
  { path: '/groups/:id', name: 'group-detail', component: () => import('@/views/GroupDetailPage.vue') },
  { path: '/groups/:id/submission', name: 'group-submission', component: () => import('@/views/GroupDetailPage.vue') },
  { path: '/groups/:id/finalist', name: 'group-finalist', component: () => import('@/views/GroupDetailPage.vue') },
  { path: '/groups/:id/results', name: 'group-results', component: () => import('@/views/GroupDetailPage.vue') },
  { path: '/groups/:id/plan', name: 'group-plan', component: () => import('@/views/GroupDetailPage.vue') },
  { path: '/submission/:id', redirect: (to) => `/groups/${to.params.id}/submission` },
  { path: '/resources', name: 'resources', component: () => import('@/views/ResourcesPage.vue') },
  { path: '/resources/:id(\\d+)', name: 'resource-detail', component: () => import('@/views/ResourceDetailPage.vue') },
  { path: '/events', name: 'events', component: () => import('@/views/EventsPage.vue') },
  { path: '/events/:id(\\d+)', name: 'event-detail', component: () => import('@/views/EventsPage.vue') },
  { path: '/profile', name: 'profile', component: () => import('@/views/ProfilePage.vue') },
  { path: '/admin', name: 'admin', component: () => import('@/views/admin/AdminDashboardPage.vue'), meta: { requiresAdmin: true } },
  { path: '/admin/users', name: 'admin-users', component: () => import('@/views/admin/AdminPeoplePage.vue'), meta: { requiresAdmin: true } },
  // My Students, for every student.
  { path: '/admin/guardians', name: 'admin-guardians', component: () => import('@/views/SupervisorStudentsPage.vue'), props: { admin: true }, meta: { requiresAdmin: true } },
  { path: '/admin/groups', name: 'admin-groups', component: () => import('@/views/admin/AdminGroupsPage.vue'), meta: { requiresAdmin: true } },
  { path: '/admin/tasks', name: 'admin-tasks', component: () => import('@/views/admin/AdminTasksPage.vue'), meta: { requiresAdmin: true } },
  // The Group Plans builder (GP2). `/admin/plan/progress` belongs to GP5.
  { path: '/admin/plan', name: 'admin-plan', component: () => import('@/views/admin/AdminPlanTasksPage.vue'), meta: { requiresAdmin: true } },
  {
    path: '/admin/views',
    name: 'admin-views',
    component: () => import('@/views/admin/AdminViewsDirectoryPage.vue'),
    meta: { requiresAdmin: true }
  },
  { path: '/admin/views/:id(\\d+)', name: 'admin-view-detail', component: () => import('@/views/admin/AdminViewExecutedPage.vue'), meta: { requiresAdmin: true } },
  { path: '/admin/emails', name: 'admin-emails', component: () => import('@/views/admin/AdminEmailsPage.vue'), meta: { requiresAdmin: true } },
  { path: '/announcements', name: 'announcements', component: () => import('@/views/AnnouncementsPage.vue') },
  { path: '/announcements/:id', name: 'announcement-detail', component: () => import('@/views/AnnouncementDetailPage.vue') },
  {
    // Admin-only grading section. meta.adminOnly is merged into every child
    // route's meta by Vue Router, so the global guard covers the whole tree.
    path: '/grading',
    component: () => import('@/views/grading/GradingPage.vue'),
    meta: { adminOnly: true },
    children: [
      { path: '', redirect: '/grading/components/SAQ' },
      { path: 'by-group', name: 'grading-by-group', component: () => import('@/views/grading/ByGroupPage.vue') },
      { path: 'components/:code', name: 'grading-component', component: () => import('@/views/grading/ComponentTablePage.vue') },
      // Both marking routes render the same page — the route name decides the
      // chrome (jump card, Download all, tab navigation). They hide the app's
      // side navigation (meta.hideSidebar): the preview/rubric split wants
      // the full width.
      { path: 'components/:code/:groupId(\\d+)', name: 'grading-component-group', component: () => import('@/views/grading/GroupMarkingPage.vue'), meta: { hideSidebar: true } },
      { path: 'groups/:groupId(\\d+)', name: 'grading-group', component: () => import('@/views/grading/GroupMarkingPage.vue'), meta: { hideSidebar: true } },
      { path: 'finalists', name: 'grading-finalists', component: () => import('@/views/grading/FinalistsPage.vue') }
    ]
  },
  {
    // Admin-only management section — the run-the-competition levers. Same
    // adminOnly meta merge as /grading above.
    path: '/management',
    component: () => import('@/views/management/ManagementPage.vue'),
    meta: { adminOnly: true },
    children: [
      { path: '', redirect: '/management/submission-deadline' },
      { path: 'new-year', name: 'management-new-year', component: () => import('@/views/management/YearPage.vue') },
      // The deadline, then extending it for some groups (Extend Deadline's
      // old path still leads here).
      { path: 'submission-deadline', name: 'management-deadline', component: () => import('@/views/management/SubmissionDeadlineTabPage.vue') },
      { path: 'extend-deadline', redirect: '/management/submission-deadline' },
      // Every group's marks and certificates, released or not: the supervisor Results page's.
      { path: 'results', name: 'management-results', component: () => import('@/views/SupervisorResultsPage.vue'), props: { admin: true } },
      { path: 'release-results', name: 'management-release-results', component: () => import('@/views/management/ReleaseResultsPage.vue') },
      { path: 'document-setup', name: 'management-settings', component: () => import('@/views/management/DocumentSetupPage.vue') },
      // The finalists' email, then the nonfinalists' and nonsubmissions' (Notify
      // Nonfinalist's old path still leads here).
      { path: 'notify-finalists', name: 'management-notify-finalists', component: () => import('@/views/management/NotifyTabPage.vue') },
      { path: 'email-nonfinalist', redirect: '/management/notify-finalists' },
      { path: 'finalist-presentation', name: 'management-finalist-presentation', component: () => import('@/views/management/FinalistPresentationPage.vue') },
      // The registration dates, then registering students as a supervisor does.
      { path: 'registration', name: 'management-registration', component: () => import('@/views/management/ManagementRegistrationPage.vue') },
      // Late Registration: late links, Supervisor Pages Visibility and
      // supervisors after close. Its old paths still lead to it.
      { path: 'late-registration', name: 'management-late-registration', component: () => import('@/views/management/LateRegistrationPage.vue') },
      { path: 'registration-visibility', redirect: '/management/late-registration' },
      // The names registration treats as a university, not a school.
      { path: 'known-universities', name: 'management-known-universities', component: () => import('@/views/management/KnownUniversitiesPage.vue') },
      // How much email-checking credit is left, and today's lookups.
      { path: 'email-checks', name: 'management-email-checks', component: () => import('@/views/management/EmailChecksPage.vue') },
      // The day this year's challenge starts, for the supervisors' daily email.
      { path: 'challenge-start', name: 'management-challenge-start', component: () => import('@/views/management/ChallengeStartPage.vue') },
      { path: 'supervisor-visibility', redirect: '/management/late-registration' }
    ]
  },
  { path: '/:pathMatch(.*)*', redirect: '/login' }
];

export default routes;
