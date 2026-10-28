<template>
  <div
    class="app-container"
    :class="{
      'student-dashboard-colours': auth.isStudent && ['/dashboard', '/profile'].includes(route.path),
      'app-container--authenticated': !isLoginPage
    }"
  >
    <!-- Hidden on the marking pages, so the preview and rubric get the
         height; the arrow below brings it back. -->
    <header class="header" v-if="!isLoginPage && !(onMarkingPage && isHeaderHidden)">
      <div class="header-content">
        <div class="logo-section">
          <RouterLink :to="logoTarget" class="logo">
            <div class="logo-icon">
              <img :src="logo" :alt="BRAND_NAME" />
            </div>
            <span class="logo-text">{{ BRAND_CONNECT }}</span>
          </RouterLink>
        </div>

        <div class="header-nav">
          <form class="program-search" role="search" @submit.prevent="handleProgramSearch">
            <i class="fas fa-search" aria-hidden="true"></i>
            <input
              v-model="programSearchQuery"
              type="search"
              class="search-bar"
              placeholder="Search Program"
              aria-label="Search Program"
            />
          </form>

          <button
            type="button"
            class="theme-toggle"
            :aria-label="isDark ? 'Switch to light mode' : 'Switch to dark mode'"
            :aria-pressed="isDark"
            @click="toggleTheme"
          >
            <i :class="isDark ? 'fas fa-sun' : 'fas fa-moon'" aria-hidden="true"></i>
          </button>

          <div class="user-menu">
            <button
              class="user-avatar"
              ref="avatarRef"
              @click="toggleUserMenu"
              type="button"
              aria-label="Open account menu"
            >
              <img v-if="profileAvatarUrl" class="user-avatar-image" :src="profileAvatarUrl" alt="" />
              <span v-else class="user-avatar-text">{{ auth.initials }}</span>
<!--              <span v-if="hasUserMenuBadge" class="notification-badge"></span>-->
            </button>
          </div>
        </div>
      </div>
      <button
        v-if="onMarkingPage"
        type="button"
        class="header-collapse-toggle"
        aria-label="Hide top bar"
        title="Hide top bar"
        :aria-expanded="true"
        @click="isHeaderHidden = true"
      >
        <i class="fas fa-chevron-up" aria-hidden="true"></i>
      </button>
    </header>
    <!-- A public page in the site (meta.siteHeader): the same top bar, with
         just the logo, as its visitor isn't signed in; Registration's
         (meta.siteHeaderSignIn) has Sign in on the right. -->
    <header v-else-if="isLoginPage && route.meta.siteHeader === true" class="header">
      <div class="header-content">
        <div class="logo-section">
          <span class="logo">
            <span class="logo-icon">
              <img :src="logo" :alt="BRAND_NAME" />
            </span>
            <span class="logo-text">{{ BRAND_CONNECT }}</span>
          </span>
        </div>
        <div v-if="route.meta.siteHeaderSignIn === true" class="header-nav">
          <span class="header-note">Already registered?</span>
          <RouterLink to="/login" class="header-sign-in">Sign in</RouterLink>
        </div>
      </div>
    </header>
    <button
      v-if="!isLoginPage && onMarkingPage && isHeaderHidden"
      type="button"
      class="header-collapse-toggle header-collapse-toggle--pinned"
      aria-label="Show top bar"
      title="Show top bar"
      :aria-expanded="false"
      @click="isHeaderHidden = false"
    >
      <i class="fas fa-chevron-down" aria-hidden="true"></i>
    </button>

    <div
      class="main-layout"
      v-if="!isLoginPage"
      :class="{ 'main-layout--full': markingFullWidth }"
    >
      <aside
        class="sidebar"
        :class="{
          'is-collapsed': isSidebarCollapsed,
          'is-marking': onMarkingPage,
          'is-header-hidden': onMarkingPage && isHeaderHidden,
        }"
      >
        <nav class="sidebar-nav">
          <ul class="sidebar-list">
            <!-- The member pages, Support among them (mainNavLinks). -->
            <template v-for="entry in mainNavLinks" :key="entry.to">
              <li v-if="!entry.links" class="sidebar-item">
                <RouterLink :to="entry.to" class="sidebar-link" :class="{ active: entry.active }">
                  <i :class="['fas', entry.icon, 'sidebar-icon']"></i>
                  <span>{{ entry.label }}</span>
                </RouterLink>
              </li>

              <li v-else class="sidebar-item">
                <div class="sidebar-link sidebar-link--admin" :class="{ active: entry.active }">
                  <RouterLink :to="entry.to" class="sidebar-link__main">
                    <i :class="['fas', entry.icon, 'sidebar-icon']"></i>
                    <span>{{ entry.label }}</span>
                  </RouterLink>
                  <button
                    type="button"
                    class="sidebar-subnav-toggle"
                    :class="{ 'is-open': !entry.collapsed }"
                    :aria-expanded="!entry.collapsed"
                    :aria-controls="entry.id"
                    :aria-label="`${entry.collapsed ? 'Expand' : 'Collapse'} ${entry.label.toLowerCase()} submenu`"
                    @click="toggleSidebarSection(entry.key)"
                  >
                    <i
                      :class="entry.collapsed ? 'fas fa-chevron-down' : 'fas fa-chevron-up'"
                      aria-hidden="true"
                    ></i>
                  </button>
                </div>
                <ul
                  :id="entry.id"
                  class="sidebar-subnav"
                  v-if="!isSidebarCollapsed && !entry.collapsed"
                >
                  <li v-for="link in entry.links" :key="link.label" class="sidebar-subitem">
                    <RouterLink
                      :to="link.to!"
                      class="sidebar-sublink"
                      :class="{ active: link.active }"
                    >
                      <span>{{ link.label }}</span>
                    </RouterLink>
                  </li>
                </ul>
              </li>
            </template>

            <li class="sidebar-item" v-if="auth.isStudent">
              <a href="mailto:support@biotechfutures.org" class="sidebar-link">
                <i class="fas fa-envelope sidebar-icon" aria-hidden="true"></i>
                <span>Contact Support</span>
              </a>
            </li>

            <!-- The agent side of support tickets, on the server's isSupport
                 flag: admins, support agents, and anyone else the server has
                 given queue access. One entry point for all of them, so it is
                 not also an Admin sub-item. -->
            <li class="sidebar-item" v-if="auth.canWorkTickets">
              <RouterLink
                to="/admin/tickets"
                class="sidebar-link"
                :class="{ active: route.path.startsWith('/admin/tickets') }"
              >
                <i class="fas fa-headset sidebar-icon" aria-hidden="true"></i>
                <span>Support queue</span>
              </RouterLink>
            </li>

            <!-- Admin's and a supervisor's own pages: one entry each that folds open. -->
            <li v-for="section in sidebarSections" :key="section.key" class="sidebar-item">
              <div class="sidebar-link sidebar-link--admin" :class="{ active: section.active }">
                <RouterLink :to="section.to" class="sidebar-link__main">
                  <i :class="['fas', section.icon, 'sidebar-icon']"></i>
                  <span>{{ section.label }}</span>
                </RouterLink>
                <button
                  type="button"
                  class="sidebar-subnav-toggle"
                  :class="{ 'is-open': !section.collapsed }"
                  :aria-expanded="!section.collapsed"
                  :aria-controls="section.id"
                  :aria-label="`${section.collapsed ? 'Expand' : 'Collapse'} ${section.label.toLowerCase()} submenu`"
                  @click="toggleSidebarSection(section.key)"
                >
                  <i
                    :class="section.collapsed ? 'fas fa-chevron-down' : 'fas fa-chevron-up'"
                    aria-hidden="true"
                  ></i>
                </button>
              </div>
              <ul
                :id="section.id"
                class="sidebar-subnav"
                v-if="!isSidebarCollapsed && !section.collapsed"
              >
                <li v-for="link in section.links" :key="link.label" class="sidebar-subitem">
                  <RouterLink
                    v-if="link.to"
                    :to="link.to"
                    class="sidebar-sublink"
                    :class="{ active: link.active }"
                  >
                    <span>{{ link.label }}</span>
                  </RouterLink>
                  <a v-else :href="link.href" class="sidebar-sublink">
                    <span>{{ link.label }}</span>
                  </a>
                </li>
              </ul>
            </li>
            <!-- Last, while the pages are hidden: when this year's challenge
                 starts (Management > Challenge Start), in its own box. -->
            <li v-if="challengeStartNote && !isSidebarCollapsed" class="sidebar-note" data-test="challenge-start-note">
              <i class="fas fa-calendar-day sidebar-note__icon" aria-hidden="true"></i>
              <span>This year's challenge will start on <strong>{{ challengeStartNote }}</strong>.</span>
            </li>
          </ul>
        </nav>

        <button
          v-if="!isNoGroupNotice"
          type="button"
          class="sidebar-collapse-toggle"
          :aria-label="isSidebarCollapsed ? 'Expand sidebar' : 'Collapse sidebar'"
          :aria-pressed="isSidebarCollapsed"
          :title="isSidebarCollapsed ? 'Expand sidebar' : 'Collapse sidebar'"
          @click="toggleSidebarCollapsed"
        >
          <i
            :class="isSidebarCollapsed ? 'fas fa-chevron-right' : 'fas fa-chevron-left'"
            aria-hidden="true"
          ></i>
        </button>

        <section
          v-if="showSidebarGroupSwitcher"
          class="sidebar-group-switcher"
          aria-label="Group switcher"
        >
          <div class="sidebar-group-switcher-header">
            <label for="sidebar-group-select">Groups</label>
            <!-- Another group has messages this user hasn't read. -->
            <span v-if="hasOtherGroupUnread" class="sidebar-group-badge">New</span>
            <i v-if="isLoadingSidebarGroups" class="fas fa-circle-notch fa-spin"></i>
          </div>

          <p v-if="sidebarGroupError" class="sidebar-group-message">
            {{ sidebarGroupError }}
          </p>
          <p
            v-else-if="!isLoadingSidebarGroups && !sidebarGroups.length"
            class="sidebar-group-message"
          >
            No groups available
          </p>

          <!-- One dropdown however many groups there are: an admin's is every
               group. Picking one opens it. -->
          <AppSelect
            v-else
            id="sidebar-group-select"
            class="sidebar-group-select"
            :model-value="activeSidebarGroupId"
            :options="sidebarGroupOptions"
            placeholder="Choose a group"
            @update:model-value="openSidebarGroup"
          />
        </section>
      </aside>

      <main
        class="main-content"
        :class="{ 'main-content--events': route.path.startsWith('/events') }"
      >
        <RouterView />
      </main>
    </div>

    <RouterView v-else />

    <transition name="menu-fade">
      <div
        ref="userMenuPanelRef"
        :class="['notification-panel', { show: showUserMenu }]"
        v-if="!isLoginPage && showUserMenu"
      >
        <div class="notification-header">
          <div class="account-summary">
            <div class="account-avatar"><img v-if="profileAvatarUrl" class="account-avatar-image" :src="profileAvatarUrl" alt="" /><span v-else>{{ auth.initials }}</span></div>

            <div class="account-copy">
              <h4 class="notification-title">My account</h4>
              <p class="account-subtitle">
                {{ auth.roleLabel ? `${auth.roleLabel} access` : 'Member access' }}
              </p>
            </div>
          </div>

          <button
            @click="showUserMenu = false"
            class="close-button account-close-button"
            aria-label="Close"
          >
            <i class="fas fa-times"></i>
          </button>
        </div>

        <div class="notification-panel-section">
          <button class="panel-quick-link" type="button" @click="go('/profile')">
            <span class="panel-quick-icon"><i class="fas fa-user"></i></span>
            <span class="panel-quick-copy">
              <strong>Profile</strong>
              <small>View profile</small>
            </span>
          </button>
        </div>

        <div class="notification-panel-footer">
          <button class="logout-button" type="button" @click="handleLogout">
            <i class="fas fa-sign-out-alt"></i>
            <span>Log out</span>
          </button>
        </div>
      </div>
    </transition>
  </div>
</template>

<script setup lang="ts">
import { computed, ref, watch, onMounted, onBeforeUnmount } from 'vue'
import { useRoute, useRouter, RouterLink, RouterView } from 'vue-router'
import { useAuthStore } from './stores/auth'
import { useGroupsStore } from './stores/groups'
import { buildSessionHeaders } from '@/utils/csrf'
import AppSelect, { type AppSelectOption, type AppSelectValue } from '@/components/AppSelect.vue'
import { markingFullWidth } from '@/composables/markingLayout'
import { loadSupervisorPages, useSupervisorPages } from '@/composables/useSupervisorPages'
import { formatOrdinalDate, SYDNEY_TIME_ZONE } from '@/utils/date'
import { loadSupervisorResults, useSupervisorResults } from '@/composables/useSupervisorResults'
import { apiErrorFromResponse } from '@/utils/apiError'
import { landingPath } from '@/utils/landing'
import { clearLiveAnalyticsCache, prefetchAnalytics } from '@/utils/liveAnalyticsData'
import logo from '@/assets/btf-logo.png'
import { BRAND_NAME, BRAND_CONNECT, SUPPORT_EMAIL } from '@/constants/brand'

const route = useRoute()
const isNoGroupNotice = computed(() =>
  route.path === '/dashboard' &&
  route.query.notice === 'no-group'
)
const router = useRouter()
const auth = useAuthStore()
const groupsStore = useGroupsStore()
const API_BASE_URL = import.meta.env.VITE_API_BASE_URL || 'http://localhost:8000'
const SIDEBAR_GROUP_READ_EVENT = 'biotech:group-chat-read'

interface CollectionResponse {
  results?: unknown[]
  items?: unknown[]
}

interface SidebarGroupOption {
  id: string
  name: string
  memberCount: number
  hasUnread: boolean
  latestAt: string
}

const handleLogout = async () => {
  await auth.logout()
  // Drop the previous user's group cache so the next session re-fetches.
  groupsStore.reset()
  clearLiveAnalyticsCache()
  go('/login')
}

const THEME_STORAGE_KEY = 'biotech-theme'
const isDark = ref(false)

const applyTheme = (dark: boolean) => {
  document.documentElement.setAttribute('data-theme', dark ? 'dark' : 'light')
}

const toggleTheme = () => {
  isDark.value = !isDark.value
  applyTheme(isDark.value)
  try {
    window.localStorage.setItem(THEME_STORAGE_KEY, isDark.value ? 'dark' : 'light')
  } catch {
    // localStorage may be unavailable (private mode, quota); fail silently.
  }
}

const isLoginPage = computed(() =>
  ['/login', '/auth/callback', '/auth/reset-password', '/auth/set-password'].includes(route.path) ||
  route.meta.public === true,
)
const isAdminLandingActive = computed(() => route.path === '/admin')
// A support-only account's start page is the queue (or the page explaining
// why it has none), not the member dashboard it cannot open. A supervisor's
// is their profile.
const logoTarget = computed(() => {
  if (auth.isSupportOnly) return landingPath(auth)
  return auth.isSupervisor ? '/profile' : '/dashboard'
})
// Support-only accounts belong to no group and cannot open /groups; skipping
// the switcher also skips its group list and per-group unread requests.
const showSidebarGroupSwitcher = computed(
  () => !isLoginPage.value && !auth.isSupportOnly && route.path.startsWith('/groups'),
)

const sidebarGroups = ref<SidebarGroupOption[]>([])
const isLoadingSidebarGroups = ref(false)
const sidebarGroupError = ref('')
let sidebarGroupLoadSequence = 0

const showUserMenu = ref(false)
const hasUserMenuBadge = ref(true)
const userMenuPanelRef = ref<HTMLElement | null>(null)
const avatarRef = ref<HTMLElement | null>(null)
const profileAvatarUrl = computed(() => auth.user?.profile_image_url || '')
const isSidebarCollapsed = ref(false)

// Marking pages start with the sidebar collapsed (meta.hideSidebar on the
// route) so the preview/rubric split gets the width — the toggle stays, so
// it can still be opened. Leaving restores how the user had it.
const onMarkingPage = computed(() => route.meta.hideSidebar === true)
// They hide the top bar too, until its arrow brings it back.
const isHeaderHidden = ref(true)
let sidebarStateBeforeMarking = false
watch(
  onMarkingPage,
  (entering, was) => {
    if (entering) {
      isHeaderHidden.value = true
      sidebarStateBeforeMarking = isSidebarCollapsed.value
      isSidebarCollapsed.value = true
    } else if (was) {
      isSidebarCollapsed.value = sidebarStateBeforeMarking
    }
  },
  { immediate: true }
)
const programSearchQuery = ref('')

// Tracks whether each collapsible submenu is hidden, so the stacked
// (mobile) sidebar stays compact. Defaults to collapsed on small screens and
// expanded on large ones, matching the layout the user sees. Keeps in sync
// with viewport changes (e.g. loading at desktop width then resizing down).
type SidebarSectionKey = 'analytics' | 'supervisor' | 'admin'
// On large screens Admin starts open and Analytics folded. A supervisor's
// own pages always start open, whatever the screen: they're the pages a
// supervisor has.
const collapsedSidebarSections = ref<Record<SidebarSectionKey, boolean>>({
  analytics: true,
  supervisor: false,
  admin: false,
})
let adminSubnavMediaQuery: MediaQueryList | null = null

const syncAdminSubnavViewport = (event: MediaQueryList | MediaQueryListEvent) => {
  if (event.matches) {
    collapsedSidebarSections.value = { analytics: true, supervisor: false, admin: true }
  }
}

const toggleSidebarSection = (key: SidebarSectionKey) => {
  collapsedSidebarSections.value[key] = !collapsedSidebarSections.value[key]
}

type SidebarLink = { label: string; to?: string; href?: string; active: boolean }
type MainNavEntry =
  | {
      to: string
      label: string
      icon: string
      active: boolean
      links?: never
    }
  | {
      key: SidebarSectionKey
      to: string
      label: string
      icon: string
      active: boolean
      links: Array<SidebarLink & { to: string }>
      id: string
      collapsed: boolean
    }

const { shown: supervisorPagesShown, challengeStartsAt, now: pagesClock } = useSupervisorPages()
// While the pages are hidden from a student, mentor or supervisor, the menu
// says when this year's challenge starts (its date, in Sydney), once it's
// set and still to come.
const challengeStartNote = computed(() => {
  if (auth.isAdmin || auth.isSupportOnly || supervisorPagesShown.value || !challengeStartsAt.value) return ''
  if (Date.parse(challengeStartsAt.value) <= pagesClock.value) return ''
  return formatOrdinalDate(challengeStartsAt.value, SYDNEY_TIME_ZONE)
})
// Results, once marks or certificates are released.
const { shown: supervisorResultsShown } = useSupervisorResults()
watch(
  () => auth.isAuthenticated && !auth.isAdmin,
  (followsVisibility) => {
    if (followsVisibility) void loadSupervisorPages()
  },
  { immediate: true },
)
watch(
  () => auth.isSupervisor,
  (isSupervisor) => {
    if (isSupervisor) void loadSupervisorResults()
  },
  { immediate: true },
)

// The top-level links. A support agent who is not an admin gets the queue and
// none of these: the guard sends them back from these anyway, so offering the
// links would only be a detour. The rest come once Management > Challenge
// Start > Pages Visibility's date comes (admins always see them); until then
// a supervisor has their own pages below and a student or mentor their
// profile. Support is not one of the hidden pages, so everybody keeps it. The
// list is the router guard's own, so the menu never offers a page the guard
// refuses or hides one it allows.
const mainNavLinks = computed(() => {
  if (auth.isSupportOnly) return []
  const support: MainNavEntry = {
    to: '/support',
    label: 'Support',
    icon: 'fa-life-ring',
    active: route.path.startsWith('/support'),
  }
  if (!auth.isAdmin && !supervisorPagesShown.value) {
    return auth.isSupervisor
      ? [support]
      : [{ to: '/profile', label: 'My Profile', icon: 'fa-user', active: route.path === '/profile' }, support]
  }
  const links: MainNavEntry[] = [
    { to: '/dashboard', label: 'Home', icon: 'fa-home', active: route.path === '/dashboard' },
  ]
  links.push(
    { to: '/groups', label: 'Groups', icon: 'fa-users', active: route.path.startsWith('/groups') },
    { to: '/events', label: 'Events', icon: 'fa-calendar', active: route.path.startsWith('/events') },
    { to: '/announcements', label: 'Announcements', icon: 'fa-bullhorn', active: route.path === '/announcements' },
    { to: '/resources', label: 'Resources', icon: 'fa-book', active: route.path === '/resources' },
    support,
  )
  return links
})

// The folding entries: a supervisor's own pages and the admin pages, drawn
// by the same template. The roles never overlap, so a user gets one at most.
const sidebarSections = computed(() => {
  const path = route.path
  const sections: Array<{
    key: SidebarSectionKey
    label: string
    icon: string
    to: string
    active: boolean
    links: SidebarLink[]
  }> = []
  if (auth.isSupervisor) {
    sections.push({
      key: 'supervisor',
      label: 'Supervisor',
      icon: 'fa-chalkboard-user',
      to: '/my-students',
      active: false,
      links: [
        { label: 'My Profile', to: '/profile', active: path === '/profile' },
        { label: 'Registration', to: '/supervisor/registration', active: path === '/supervisor/registration' },
        { label: 'Students', to: '/my-students', active: path.startsWith('/my-students') },
        { label: 'Groups', to: '/my-groups', active: path === '/my-groups' },
        ...(supervisorResultsShown.value
          ? [{ label: 'Results', to: '/my-results', active: path === '/my-results' }]
          : []),
        { label: 'Contact Support', href: `mailto:${SUPPORT_EMAIL}`, active: false },
      ],
    })
  }
  if (auth.isAdmin) {
    sections.push({
      key: 'admin',
      label: 'Admin',
      icon: 'fa-cog',
      to: '/admin',
      active: isAdminLandingActive.value,
      links: [
        { label: 'Users', to: '/admin/users', active: path === '/admin/users' },
        { label: 'Guardians', to: '/admin/guardians', active: path === '/admin/guardians' },
        { label: 'Views', to: '/admin/views', active: path.startsWith('/admin/views') },
        { label: 'Groups', to: '/admin/groups', active: path === '/admin/groups' },
        { label: 'Tasks', to: '/admin/tasks', active: path === '/admin/tasks' },
        { label: 'Role Tasks', to: '/admin/role-tasks', active: path.startsWith('/admin/role-tasks') },
        { label: 'Group Plans', to: '/admin/plan', active: path === '/admin/plan' || path.startsWith('/admin/plan/') },
        { label: 'System Emails', to: '/admin/emails', active: path === '/admin/emails' },
        { label: 'System Logs', to: '/admin/logs', active: path === '/admin/logs' },
        { label: 'Grading', to: '/grading', active: path.startsWith('/grading') },
        { label: 'Management', to: '/management', active: path.startsWith('/management') },
      ],
    })
    sections.push({
      key: 'analytics',
      label: 'Analytics',
      icon: 'fa-chart-column',
      to: '/analytics',
      active: path === '/analytics',
      links: [
        { label: 'Users', to: '/analytics/users', active: path === '/analytics/users' },
        { label: 'Registration', to: '/analytics/registration', active: path === '/analytics/registration' },
        { label: 'Groups', to: '/analytics/groups', active: path === '/analytics/groups' },
        { label: 'Mentors', to: '/analytics/mentors', active: path === '/analytics/mentors' },
        { label: 'Activity', to: '/analytics/activity', active: path === '/analytics/activity' },
        { label: 'Messages', to: '/analytics/messages', active: path === '/analytics/messages' },
        { label: 'Resources', to: '/analytics/resources', active: path === '/analytics/resources' },
        { label: 'Email Monitoring', to: '/analytics/email', active: path === '/analytics/email' },
      ],
    })
  }
  return sections.map((section) => ({
    ...section,
    id: `${section.key}-subnav`,
    collapsed: collapsedSidebarSections.value[section.key],
  }))
})

const programSearchTargets = [
  { path: '/dashboard', terms: ['home', 'dashboard', 'overview', 'program'] },
  { path: '/analytics', terms: ['analytics', 'report', 'reports', 'statistics', 'metrics'] },
  { path: '/groups', terms: ['group', 'groups', 'team', 'teams', 'mentor', 'mentoring'] },
  { path: '/events', terms: ['event', 'events', 'calendar', 'session', 'sessions', 'workshop'] },
  { path: '/announcements', terms: ['announcement', 'announcements', 'news', 'updates', 'notice'] },
  { path: '/resources', terms: ['resource', 'resources', 'library', 'guide', 'material'] },
  { path: '/profile', terms: ['profile', 'account', 'me', 'settings'] },
  { path: '/my-students', terms: ['student', 'students', 'registered'] },
  { path: '/my-groups', terms: ['my groups', 'waiting area'] },
]

const toggleSidebarCollapsed = () => {
  isSidebarCollapsed.value = !isSidebarCollapsed.value
}

const toggleUserMenu = () => {
  showUserMenu.value = !showUserMenu.value
  if (showUserMenu.value) hasUserMenuBadge.value = false
}

const go = (path: string) => {
  showUserMenu.value = false
  router.push(path)
}

const handleProgramSearch = () => {
  const query = programSearchQuery.value.trim().toLowerCase()
  if (!query) return

  const target =
    programSearchTargets.find((item) => item.terms.some((term) => term.includes(query))) ??
    programSearchTargets.find((item) => item.terms.some((term) => query.includes(term)))

  if (target) {
    showUserMenu.value = false
    programSearchQuery.value = ''
    router.push(target.path)
  }
}

const isRecord = (value: unknown): value is Record<string, unknown> =>
  typeof value === 'object' && value !== null && !Array.isArray(value)

const extractCollectionItems = (data: unknown): Record<string, unknown>[] => {
  if (Array.isArray(data)) return data.filter(isRecord)
  if (!isRecord(data)) return []
  const collection = data as CollectionResponse
  if (Array.isArray(collection.results)) return collection.results.filter(isRecord)
  if (Array.isArray(collection.items)) return collection.items.filter(isRecord)
  return []
}

const requestJson = async (url: string, options: RequestInit = {}) => {
  const headers = buildSessionHeaders({ headers: options.headers })
  if (!headers.has('Accept')) headers.set('Accept', 'application/json')

  const response = await fetch(url, {
    credentials: 'include',
    ...options,
    headers,
  })

  if (!response.ok) {
    throw await apiErrorFromResponse(response)
  }

  if (response.status === 204) return null
  return response.json()
}

const getCurrentUserDisplayNames = () =>
  new Set(
    [
      auth.displayName,
      auth.user?.email,
      [auth.user?.first_name, auth.user?.last_name].filter(Boolean).join(' '),
    ]
      .map((value) => String(value || '').trim())
      .filter(Boolean),
  )

const loadSidebarLatestMessageState = async (
  groups: SidebarGroupOption[],
  sequence: number,
) => {
  if (!groups.length) return

  const currentUserId = Number(auth.user?.id || 0)
  const currentNames = getCurrentUserDisplayNames()
  const results = await Promise.allSettled(
    groups.map(async (groupOption) => {
      const data = await requestJson(
        `${API_BASE_URL}/api/v1/chat/groups/${groupOption.id}/messages/?limit=1`,
      )
      const latest = extractCollectionItems(data)[0]
      if (!latest) return { ...groupOption, hasUnread: false, latestAt: '' }

      const senderId = Number(
        latest.sender_user ?? latest.sender_id ?? latest.sender_user_id ?? 0,
      )
      const senderName = String(latest.sender_name ?? latest.author ?? '').trim()
      const isOwn =
        (currentUserId > 0 && senderId === currentUserId) ||
        (senderName && currentNames.has(senderName))
      const latestAt = String(latest.sent_at ?? latest.created_at ?? latest.sent_datetime ?? '')
      const hasUnread = latest.is_read_by_me === false && !isOwn

      return { ...groupOption, hasUnread, latestAt }
    }),
  )

  if (sequence !== sidebarGroupLoadSequence) return

  sidebarGroups.value = groups.map((groupOption, index) => {
    const result = results[index]
    return result?.status === 'fulfilled' ? result.value : groupOption
  })
}

const loadSidebarGroups = async () => {
  if (!showSidebarGroupSwitcher.value) {
    sidebarGroupLoadSequence += 1
    sidebarGroups.value = []
    sidebarGroupError.value = ''
    isLoadingSidebarGroups.value = false
    return
  }

  const sequence = ++sidebarGroupLoadSequence
  isLoadingSidebarGroups.value = true
  sidebarGroupError.value = ''

  await groupsStore.ensureLoaded()
  if (sequence !== sidebarGroupLoadSequence) return

  if (groupsStore.error) {
    sidebarGroups.value = []
    sidebarGroupError.value = groupsStore.error
    isLoadingSidebarGroups.value = false
    return
  }

  const groups: SidebarGroupOption[] = groupsStore.sorted.map((g) => ({
    id: g.id,
    name: g.name,
    memberCount: g.memberCount,
    hasUnread: false,
    latestAt: '',
  }))
  sidebarGroups.value = groups
  isLoadingSidebarGroups.value = false
  // An admin's list is every group, and they're in none of them: no unread
  // dots, and no request per group to work them out.
  if (auth.isAdmin) return

  // N requests (one per group) — defer behind idle so the page is
  // interactive before unread/latest-at indicators light up.
  const runLatest = () => void loadSidebarLatestMessageState(groups, sequence)
  const ric = (window as unknown as { requestIdleCallback?: (cb: () => void) => void })
    .requestIdleCallback
  if (typeof ric === 'function') ric(runLatest)
  else window.setTimeout(runLatest, 250)
}

const isSidebarGroupActive = (groupId: string) => String(route.params.id || '') === groupId

const clearSidebarGroupUnread = (groupId: string | number | undefined | null) => {
  const targetGroupId = String(groupId || '')
  if (!targetGroupId) return

  sidebarGroups.value = sidebarGroups.value.map((groupOption) =>
    groupOption.id === targetGroupId && groupOption.hasUnread
      ? { ...groupOption, hasUnread: false }
      : groupOption,
  )
}

const handleSidebarGroupRead = (event: Event) => {
  const detail = (event as CustomEvent<{ groupId?: string | number }>).detail
  clearSidebarGroupUnread(detail?.groupId)
}

// The group open now, when it's one of the listed ones.
const activeSidebarGroupId = computed(() => {
  const id = String(route.params.id || '')
  return sidebarGroups.value.some((groupOption) => groupOption.id === id) ? id : ''
})

const hasOtherGroupUnread = computed(() =>
  sidebarGroups.value.some(
    (groupOption) => groupOption.hasUnread && !isSidebarGroupActive(groupOption.id),
  ),
)

// Each group, marked New when it has unread messages and isn't the one open.
const sidebarGroupOptions = computed<AppSelectOption[]>(() =>
  sidebarGroups.value.map((groupOption) => ({
    value: groupOption.id,
    label: `${groupOption.name}${groupOption.hasUnread && !isSidebarGroupActive(groupOption.id) ? ' • New' : ''}`,
  })),
)

const openSidebarGroup = (id: AppSelectValue) => {
  if (id) void router.push({ name: 'group-detail', params: { id: String(id) } })
}

const handleClickOutside = (event: MouseEvent) => {
  if (!showUserMenu.value) return

  const target = event.target as Node | null
  if (!target) return

  const clickedInsidePanel = userMenuPanelRef.value?.contains(target)
  const clickedAvatar = avatarRef.value?.contains(target)

  if (!clickedInsidePanel && !clickedAvatar) {
    showUserMenu.value = false
  }
}

const handleKeydown = (event: KeyboardEvent) => {
  if (event.key === 'Escape' && showUserMenu.value) {
    showUserMenu.value = false
    avatarRef.value?.focus?.()
  }
}

// Warm the Analytics cache for admins once the rest of the site has loaded,
// so opening Analytics does not wait. It runs after the page's own requests
// (window load, then idle time) and again for each newly signed-in admin.
let analyticsPrefetchUserId: number | string | null = null
const scheduleAnalyticsPrefetch = () => {
  const userId = auth.user?.id ?? null
  if (!auth.isAdmin || userId === null || analyticsPrefetchUserId === userId) return
  analyticsPrefetchUserId = userId
  const run = () => {
    if (!auth.isAdmin || auth.user?.id !== userId) return
    void prefetchAnalytics()
  }
  const whenIdle = () => {
    const ric = (window as unknown as {
      requestIdleCallback?: (cb: () => void, options?: { timeout: number }) => void
    }).requestIdleCallback
    if (typeof ric === 'function') ric(run, { timeout: 5000 })
    else window.setTimeout(run, 1500)
  }
  if (document.readyState === 'complete') whenIdle()
  else window.addEventListener('load', whenIdle, { once: true })
}

watch(
  () => [auth.user?.id, auth.isAdmin],
  () => {
    if (!auth.isAdmin) analyticsPrefetchUserId = null
    scheduleAnalyticsPrefetch()
  },
  { immediate: true },
)

// Sidebar group list is non-critical — defer behind requestIdleCallback
// so we don't fight the main page's fetches for connection budget.
const scheduleSidebarLoad = () => {
  const run = () => loadSidebarGroups()
  const ric = (window as unknown as { requestIdleCallback?: (cb: () => void) => void })
    .requestIdleCallback
  if (typeof ric === 'function') ric(run)
  else window.setTimeout(run, 200)
}

watch(
  () => route.fullPath,
  () => {
    // Only close the user menu — the sidebar group list doesn't change
    // per-route, so re-fetching here is pure waste.
    showUserMenu.value = false
  },
)

watch(showSidebarGroupSwitcher, (isVisible) => {
  if (isVisible) {
    scheduleSidebarLoad()
    return
  }
  sidebarGroupLoadSequence += 1
  sidebarGroups.value = []
  sidebarGroupError.value = ''
  isLoadingSidebarGroups.value = false
})

watch(
  () => [auth.user?.id, auth.isAdmin, showSidebarGroupSwitcher.value],
  ([newUserId, , nowVisible], old) => {
    const oldUserId = Array.isArray(old) ? old[0] : undefined
    const wasVisible = Array.isArray(old) ? old[2] : undefined
    // The cached list belongs to whoever was logged in. If the identity
    // changes (login, account switch) drop it so the next load fetches fresh.
    if (oldUserId !== undefined && oldUserId !== newUserId) {
      groupsStore.reset()
      clearLiveAnalyticsCache()
    }
    // Skip the no-op transition where the switcher stays hidden — avoids
    // refetching while the user is bouncing between non-/groups routes.
    if (wasVisible === false && nowVisible === false) return
    scheduleSidebarLoad()
  },
)

onMounted(() => {
  try {
    isDark.value = window.localStorage.getItem(THEME_STORAGE_KEY) === 'dark'
  } catch {
    isDark.value = false
  }
  applyTheme(isDark.value)

  if (typeof window.matchMedia === 'function') {
    adminSubnavMediaQuery = window.matchMedia('(max-width: 768px)')
    syncAdminSubnavViewport(adminSubnavMediaQuery)
    adminSubnavMediaQuery.addEventListener('change', syncAdminSubnavViewport)
  }

  document.addEventListener('click', handleClickOutside)
  document.addEventListener('keydown', handleKeydown)
  window.addEventListener(SIDEBAR_GROUP_READ_EVENT, handleSidebarGroupRead)
  scheduleSidebarLoad()
})

onBeforeUnmount(() => {
  document.removeEventListener('click', handleClickOutside)
  document.removeEventListener('keydown', handleKeydown)
  window.removeEventListener(SIDEBAR_GROUP_READ_EVENT, handleSidebarGroupRead)
  adminSubnavMediaQuery?.removeEventListener('change', syncAdminSubnavViewport)
})
</script>

<style scoped>
/* BTF light green, matching the brand email buttons. Keep the change within
   student dashboard/profile pages, including their navigation and account panel. */
.student-dashboard-colours {
  --light-green: #c3ecca;
  --accent-green-soft: #c3ecca;
}

:global(html[data-theme="dark"] .student-dashboard-colours) {
  --light-green: rgba(1, 113, 81, 0.18);
  --accent-green-soft: rgba(1, 113, 81, 0.18);
}

:global(html),
:global(body),
:global(#app) {
  width: 100%;
  height: 100%;
  max-width: none;
  margin: 0;
  padding: 0;
}

:global(body) {
  overflow-x: hidden;
  overflow-y: auto;
  background: var(--bg-light);
}

:deep(:root) {
  --surface-0: #f7f9f8;
  --surface-1: #eef2f0;
  --surface-2: #e5ebe8;
  --surface-3: #d9e2de;

  --text-strong: #10201b;
  --text-main: #253730;
  --text-soft: #66756f;

  --line-soft: rgba(14, 31, 25, 0.08);
  --line-mid: rgba(14, 31, 25, 0.14);

  --brand-950: #07110f;
  --brand-900: #0c1815;
  --brand-850: #11211c;
  --brand-800: #173029;
  --brand-700: #23463b;
  --brand-600: #3d6a5b;
  --brand-500: #5f8c7c;
  --brand-400: #88aea0;

  --shadow-soft: 0 12px 28px rgba(7, 17, 15, 0.06);
  --shadow-panel: 0 24px 60px rgba(7, 17, 15, 0.16);
}

* {
  box-sizing: border-box;
}

button,
input,
select {
  font: inherit;
}

.app-container {
  width: 100%;
  max-width: none;
  min-height: 100vh;
  margin: 0;
  background-color: var(--bg-light);
}

/* Dashboard pages: keep sidebar fixed and scroll main content only */
.app-container--authenticated {
  height: 100vh;
  overflow: hidden;
}

.header {
  position: sticky;
  top: 0;
  z-index: 1000;
  padding: 0.75rem 0;
  background-color: var(--dark-green);
  color: var(--white);
  box-shadow: 0 2px 4px var(--shadow);
}

/* The marking pages' arrow for the top bar, shaped as the sidebar's and in
   the bar's green: it hangs below the bar's middle, or sits at the top while
   the bar is hidden. */
.header-collapse-toggle {
  position: absolute;
  bottom: -9px;
  left: 50%;
  z-index: 900;
  width: 32px;
  height: 18px;
  border: 1px solid var(--dark-green);
  border-radius: 6px;
  font-size: 0.7rem;
  background: var(--dark-green);
  color: #ffffff;
  cursor: pointer;
  display: inline-flex;
  align-items: center;
  justify-content: center;
  box-shadow: 0 8px 18px rgba(17, 30, 25, 0.08);
  transform: translateX(-50%);
  transition:
    background-color 0.2s ease,
    color 0.2s ease,
    border-color 0.2s ease,
    box-shadow 0.2s ease;
}

/* Hangs from the top edge, as a tab. */
.header-collapse-toggle--pinned {
  position: fixed;
  top: 0;
  bottom: auto;
  z-index: 1000;
  border-top: none;
  border-radius: 0 0 6px 6px;
}

.header-collapse-toggle:hover {
  border-color: #015c42;
  background: #015c42;
  box-shadow: 0 10px 22px rgba(17, 30, 25, 0.18);
}

.header-collapse-toggle:focus-visible {
  outline: 2px solid var(--dark-green);
  outline-offset: 2px;
}

.header-content {
  width: 100%;
  max-width: 1680px;
  margin: 0 auto;
  padding: 0 1.5rem;
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 1rem;
  /* As tall as the signed-in bar's search box, so every top bar (a public
     page's too) is the same height. */
  min-height: 2.875rem;
}

/* A public page's way to sign in: a white button on the bar, as the
   signed-in bar's search box is white, with a note before it. */
.header-note {
  color: rgba(255, 255, 255, 0.85);
  font-size: 0.9rem;
}

.header-sign-in {
  display: inline-flex;
  align-items: center;
  padding: 0.5rem 1rem;
  border-radius: 8px;
  background: var(--white);
  color: var(--dark-green);
  font-size: 0.9rem;
  font-weight: 600;
  text-decoration: none;
  transition: background-color 0.18s ease;
}

.header-sign-in:hover,
.header-sign-in:focus-visible {
  background: var(--light-green);
}

.logo-section {
  display: flex;
  align-items: center;
  gap: 1rem;
}

.logo {
  display: inline-flex;
  align-items: center;
  gap: 0.75rem;
  text-decoration: none;
  color: var(--white);
}

.logo-icon {
  width: 40px;
  height: 40px;
  border-radius: 50%;
  background-color: var(--white);
  display: flex;
  align-items: center;
  justify-content: center;
}

.logo-icon img {
  width: 70%;
  height: 70%;
  object-fit: contain;
}

.logo-text {
  color: var(--white);
  font-size: 1.25rem;
  font-weight: 600;
  white-space: nowrap;
}

.header-nav {
  display: flex;
  align-items: center;
  gap: 0.75rem;
}

.program-search {
  position: relative;
  display: flex;
  align-items: center;
  width: min(320px, 34vw);
}

.program-search i {
  position: absolute;
  left: 0.9rem;
  color: rgba(23, 66, 67, 0.58);
  font-size: 0.86rem;
  pointer-events: none;
}

.search-bar {
  width: 100%;
  min-height: 40px;
  border: 1px solid rgba(255, 255, 255, 0.42);
  border-radius: 8px;
  padding: 0.58rem 0.9rem 0.58rem 2.35rem;
  background: rgba(255, 255, 255, 0.96);
  color: var(--teal);
  outline: none;
  box-shadow: 0 1px 2px rgba(7, 17, 15, 0.08);
  transition:
    border-color 0.18s ease,
    box-shadow 0.18s ease,
    background-color 0.18s ease;
}

.search-bar::placeholder {
  color: #6c757d;
}

.search-bar:focus {
  border-color: var(--white);
  background: var(--white);
  box-shadow: 0 0 0 3px rgba(255, 255, 255, 0.24);
}

/* Dark theme: grey like other pages' inputs, rather than white. */
:root[data-theme='dark'] .search-bar {
  border-color: var(--border-light);
  background: var(--surface-elevated);
}

:root[data-theme='dark'] .search-bar:focus {
  border-color: var(--text-muted);
}

:root[data-theme='dark'] .search-bar::placeholder,
:root[data-theme='dark'] .program-search i {
  color: var(--teal);
}

/* Dark theme: the account menu on the dark grey cards, with light text,
   rather than staying white. */
:root[data-theme='dark'] .notification-panel {
  background: var(--surface-elevated);
  border-color: var(--border-light);
  box-shadow: 0 24px 48px rgba(0, 0, 0, 0.5);
}

:root[data-theme='dark'] .notification-header {
  border-bottom-color: var(--border-light);
}

:root[data-theme='dark'] .panel-quick-copy strong {
  color: var(--teal);
}

:root[data-theme='dark'] .panel-quick-copy small {
  color: var(--text-muted);
}

:root[data-theme='dark'] .panel-quick-link {
  background: var(--white);
  border-color: var(--border-light);
}

:root[data-theme='dark'] .panel-quick-icon,
:root[data-theme='dark'] .account-close-button {
  background: rgba(255, 255, 255, 0.06);
  color: var(--teal);
}

:root[data-theme='dark'] .account-close-button:hover {
  background: rgba(255, 255, 255, 0.1);
}

:root[data-theme='dark'] .logout-button {
  background: var(--dark-green);
}

.theme-toggle {
  width: 40px;
  height: 40px;
  border: 2px solid rgba(255, 255, 255, 0.4);
  border-radius: 50%;
  background: transparent;
  color: var(--white);
  font-size: 0.95rem;
  display: inline-flex;
  align-items: center;
  justify-content: center;
  cursor: pointer;
  transition: background-color 0.18s ease, border-color 0.18s ease, transform 0.18s ease;
}

.theme-toggle:hover {
  background: rgba(255, 255, 255, 0.12);
  border-color: var(--white);
}

.theme-toggle:focus-visible {
  outline: 2px solid var(--white);
  outline-offset: 2px;
}

@media (prefers-reduced-motion: reduce) {
  .theme-toggle {
    transition: none;
  }
}

.user-menu {
  display: flex;
  align-items: center;
  gap: 1rem;
}

.user-avatar {
  position: relative;
  width: 40px;
  height: 40px;
  border: 2px solid var(--white);
  border-radius: 50%;
  background-color: var(--white);
  color: var(--dark-green);
  font-weight: 600;
  cursor: pointer;
  transition: background-color 0.2s ease;
}

.user-avatar:hover {
  background-color: rgba(255, 255, 255, 0.9);
}

.user-avatar-text {
  font-size: 0.95rem;
}

.user-avatar-image { width: 100%; height: 100%; border-radius: inherit; object-fit: cover; display: block; }

.notification-badge {
  position: absolute;
  top: -2px;
  right: -2px;
  width: 10px;
  height: 10px;
  border-radius: 999px;
  background: var(--danger);
  border: 2px solid var(--white);
}

.main-layout {
  display: flex;
  flex: 1;
  max-width: 1680px;
  margin: 0 auto;
  width: 100%;
  height: calc(100vh - 64px);
  overflow: hidden;
  background-color: var(--white);
}

/* Marking pages spread edge to edge — the preview/rubric splits want every
   pixel a wide monitor offers. */
.main-layout.main-layout--full {
  max-width: none;
}

.sidebar {
  --sidebar-toggle-offset: 250px;

  position: sticky;
  top: 64px;
  display: flex;
  flex-direction: column;
  align-self: flex-start;
  width: 250px;
  min-width: 250px;
  flex-shrink: 0;
  height: calc(100vh - 64px);
  min-height: 0;
  padding: 1.5rem 0;
  overflow-y: auto;
  overscroll-behavior: contain;
  scrollbar-width: none;
  -ms-overflow-style: none;
  background-color: var(--white);
  border-right: 1px solid var(--border-light);
  transition:
    width 0.2s ease,
    min-width 0.2s ease;
}

.sidebar::-webkit-scrollbar {
  display: none;
  width: 0;
  height: 0;
}

.sidebar.is-header-hidden {
  top: 0;
  height: 100vh;
}

.sidebar.is-collapsed {
  --sidebar-toggle-offset: 72px;

  width: 72px;
  min-width: 72px;
}

/* Marking pages: collapsed, the sidebar gives up its strip of icons too,
   leaving only its arrow at the page's edge. Not on phones, where it stacks
   above the page without an arrow. */
@media (min-width: 769px) {
  .sidebar.is-collapsed.is-marking {
    --sidebar-toggle-offset: 20px;

    width: 0;
    min-width: 0;
    padding: 0;
    border-right: none;
  }

  .sidebar.is-collapsed.is-marking > :not(.sidebar-collapse-toggle) {
    display: none;
  }

  /* Its arrow becomes a tab against the page's left edge, as the top bar's
     is against the top. */
  .sidebar.is-collapsed.is-marking .sidebar-collapse-toggle,
  .main-layout--full .sidebar.is-collapsed.is-marking .sidebar-collapse-toggle {
    left: 0;
    width: 18px;
    height: 32px;
    border-left: none;
    border-radius: 0 6px 6px 0;
    font-size: 0.7rem;
  }
}

.sidebar-collapse-toggle {
  position: fixed;
  top: 50vh;
  left: calc(var(--sidebar-toggle-offset) - 14px);
  right: auto;
  z-index: 900;
  width: 28px;
  height: 44px;
  border: 1px solid var(--border-light);
  border-radius: 8px;
  background: var(--white);
  color: var(--teal);
  cursor: pointer;
  display: inline-flex;
  align-items: center;
  justify-content: center;
  box-shadow: 0 8px 18px rgba(17, 30, 25, 0.08);
  transform: translateY(-50%);
  transition:
    left 0.2s ease,
    background-color 0.2s ease,
    color 0.2s ease,
    border-color 0.2s ease,
    box-shadow 0.2s ease;
}

.sidebar-collapse-toggle:hover {
  border-color: rgba(35, 70, 59, 0.24);
  background: var(--light-green);
  color: var(--dark-green);
  box-shadow: 0 10px 22px rgba(17, 30, 25, 0.12);
}

.sidebar-collapse-toggle:focus-visible {
  outline: 2px solid var(--dark-green);
  outline-offset: 2px;
}

@media (min-width: 1680px) {
  .sidebar-collapse-toggle {
    left: calc(50vw - 840px + var(--sidebar-toggle-offset) - 14px);
  }

  /* Full-width marking pages pin the sidebar to the viewport edge, so the
     centred-layout shift above would float the toggle over the content. */
  .main-layout--full .sidebar-collapse-toggle {
    left: calc(var(--sidebar-toggle-offset) - 14px);
  }

  /* A marking tab that keeps the centred layout (Prototype): the edge tab
     sits at the layout's edge, not the screen's. */
  .main-layout:not(.main-layout--full) .sidebar.is-collapsed.is-marking .sidebar-collapse-toggle {
    left: calc(50vw - 840px);
  }
}

.sidebar-nav {
  list-style: none;
}

.sidebar-list {
  list-style: none;
  margin: 0;
  padding: 0;
}

.sidebar-item {
  margin-bottom: 0.25rem;
}

.sidebar-link {
  display: flex;
  align-items: center;
  gap: 0.75rem;
  padding: 0.75rem 1.5rem;
  text-decoration: none;
  color: var(--teal);
  border-left: 3px solid transparent;
  transition:
    background-color 0.2s ease,
    color 0.2s ease,
    border-color 0.2s ease;
}

.sidebar.is-collapsed .sidebar-link {
  justify-content: center;
  gap: 0;
  padding: 0.78rem 0;
}

.sidebar.is-collapsed .sidebar-link span {
  display: none;
}

/* When this year's challenge starts: a box of its own, below the menu. */
.sidebar-note {
  display: flex;
  align-items: flex-start;
  gap: 0.75rem;
  margin: 1.25rem 1rem 0.5rem;
  padding: 1rem 1.1rem;
  border: 1px solid rgba(1, 113, 81, 0.22);
  border-radius: 8px;
  background: var(--light-green);
  color: var(--teal);
  font-size: 0.95rem;
  line-height: 1.5;
}

.sidebar-note__icon {
  flex: none;
  margin-top: 0.2rem;
  color: var(--dark-green);
  font-size: 1.1rem;
}

.sidebar-icon {
  width: 20px;
  text-align: center;
}

.sidebar-link:hover {
  background-color: var(--light-green);
  color: var(--dark-green);
  border-left-color: var(--dark-green);
}

.sidebar-link.active {
  background-color: var(--light-green);
  color: var(--dark-green);
  border-left-color: var(--dark-green);
  font-weight: 500;
}

.sidebar-link--admin {
  display: flex;
  align-items: stretch;
  padding: 0;
  border-left: 3px solid transparent;
}

.sidebar-link--admin .sidebar-link__main {
  display: flex;
  align-items: center;
  gap: 0.75rem;
  flex: 1;
  padding: 0.75rem 1.5rem;
  color: inherit;
  text-decoration: none;
}

.sidebar-link--admin:hover,
.sidebar-link--admin.active {
  background-color: var(--light-green);
  border-left-color: var(--dark-green);
}

.sidebar-link--admin.active .sidebar-link__main span {
  font-weight: 500;
  color: var(--dark-green);
}

.sidebar-subnav-toggle {
  display: flex;
  align-items: center;
  justify-content: center;
  width: 2.25rem;
  flex: 0 0 auto;
  padding: 0;
  border: none;
  border-left: 1px solid var(--border-light);
  background: transparent;
  color: var(--teal);
  opacity: 0.7;
  cursor: pointer;
  transition:
    opacity 0.2s ease,
    color 0.2s ease,
    background-color 0.2s ease;
}

.sidebar-subnav-toggle:hover,
.sidebar-subnav-toggle:focus-visible {
  opacity: 1;
  color: var(--dark-green);
  outline: 2px solid var(--dark-green);
  outline-offset: -2px;
}

.sidebar.is-collapsed .sidebar-subnav-toggle {
  display: none;
}

.sidebar.is-collapsed .sidebar-link--admin {
  justify-content: center;
  border-left-color: transparent;
}

.sidebar.is-collapsed .sidebar-link--admin .sidebar-link__main {
  justify-content: center;
  gap: 0;
  padding: 0.78rem 0;
}

.sidebar.is-collapsed .sidebar-link--admin .sidebar-link__main span {
  display: none;
}

.sidebar-subnav {
  list-style: none;
  margin: 0;
  /* No left inset: a sub-link's bar runs to the sidebar's edge, as the
     Admin and Supervisor rows' do. The sub-link pads its own text instead. */
  padding: 0.15rem 0 0.4rem;
}

.sidebar-subitem {
  margin: 0;
}

.sidebar-sublink {
  display: flex;
  align-items: center;
  gap: 0.75rem;
  padding: 0.5rem 1.5rem 0.5rem 2.8rem;
  border-left: 3px solid transparent;
  color: var(--teal);
  text-decoration: none;
  font-size: 0.9rem;
  transition:
    background-color 0.2s ease,
    color 0.2s ease,
    border-color 0.2s ease;
}

.sidebar-sublink:hover {
  background-color: var(--light-green);
  color: var(--dark-green);
  border-left-color: var(--dark-green);
}

.sidebar-sublink.active {
  background-color: var(--light-green);
  color: var(--dark-green);
  border-left-color: var(--dark-green);
  font-weight: 500;
}

.sidebar-group-switcher {
  margin-top: auto;
  padding: 1rem 0.85rem 0;
}

.sidebar-nav,
.sidebar-list {
  flex: 0 0 auto;
}

.sidebar-group-switcher {
  flex-shrink: 0;
}

.sidebar.is-collapsed .sidebar-group-switcher {
  display: none;
}

.sidebar-group-switcher-header {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 0.5rem;
  /* No left padding, so the label lines up with the dropdown's edge. */
  padding: 0 0.65rem 0.5rem 0;
  color: var(--text-soft);
  font-size: 0.72rem;
  /* 700, as Windows shows heavier Arial as Arial Black. */
  font-weight: 700;
  letter-spacing: 0.08em;
  text-transform: uppercase;
}

/* The header's own weight and case, whatever a label would bring. */
.sidebar-group-switcher-header label {
  margin: 0;
  font: inherit;
  cursor: pointer;
}

.sidebar-group-switcher-header .sidebar-group-badge {
  margin-right: auto;
}

.sidebar-group-select {
  width: 100%;
  padding: 0.45rem 0.6rem;
  border: 1px solid var(--border-light);
  border-radius: 8px;
  background: var(--surface-elevated);
  color: var(--teal);
  font-family: inherit;
  font-size: 0.88rem;
  font-weight: 600;
  cursor: pointer;
}

.sidebar-group-select:focus-within {
  outline: 2px solid var(--dark-green);
  outline-offset: 1px;
}

.sidebar-group-badge {
  flex: 0 0 auto;
  border-radius: 999px;
  padding: 0.14rem 0.42rem;
  background: var(--dark-green);
  color: var(--white);
  font-size: 0.64rem;
  font-weight: 800;
}

.sidebar-group-message {
  margin: 0;
  padding: 0.55rem 0.65rem;
  color: #6c757d;
  font-size: 0.78rem;
  font-weight: 600;
}

.main-content {
  flex: 1;
  min-width: 0;
  height: 100%;
  overflow-y: auto;
  padding: 1rem;
}

:global(html[data-theme='dark'] .main-content) {
  scrollbar-color: #53615d #111d1a;
  scrollbar-width: thin;
}

:global(html[data-theme='dark'] .main-content::-webkit-scrollbar) {
  width: 10px;
}

:global(html[data-theme='dark'] .main-content::-webkit-scrollbar-track) {
  background: #111d1a;
}

:global(html[data-theme='dark'] .main-content::-webkit-scrollbar-thumb) {
  background: #53615d;
  border: 2px solid #111d1a;
  border-radius: 999px;
}

:global(html[data-theme='dark'] .main-content::-webkit-scrollbar-thumb:hover) {
  background: #687773;
}

.main-content--events {
  padding: 0;
  background-color: var(--bg-light);
}

.close-button {
  width: 32px;
  height: 32px;
  border: none;
  border-radius: 12px;
  background: rgba(17, 30, 25, 0.05);
  color: var(--text-main);
  cursor: pointer;
  transition:
    transform 180ms ease,
    background 180ms ease;
}

.close-button:hover {
  transform: translateY(-1px);
  background: rgba(17, 30, 25, 0.08);
}

.notification-panel {
  position: fixed;
  top: 88px;
  right: 18px;
  width: 320px;
  max-width: calc(100vw - 36px);
  border-radius: 22px;
  background: linear-gradient(180deg, rgba(255, 255, 255, 0.72) 0%, rgba(245, 248, 247, 0.94) 100%);
  border: 1px solid rgba(17, 30, 25, 0.08);
  backdrop-filter: blur(18px);
  -webkit-backdrop-filter: blur(18px);
  box-shadow: 0 24px 48px rgba(7, 17, 15, 0.12);
  overflow: hidden;
  z-index: 40;
}

.notification-header {
  display: flex;
  align-items: flex-start;
  justify-content: space-between;
  gap: 0.8rem;
  padding: 0.95rem 0.95rem 0.75rem;
  border-bottom: 1px solid rgba(17, 30, 25, 0.06);
}

.account-summary {
  display: flex;
  align-items: center;
  gap: 0.7rem;
  min-width: 0;
}

/* The header is the platform's dark green (.notification-header): the
   avatar white with green initials, as in the top bar, and the text and
   close button in white. */
.account-avatar {
  width: 42px;
  height: 42px;
  border-radius: 14px;
  display: grid;
  place-items: center;
  background: #ffffff;
  color: var(--dark-green);
  font-size: 0.9rem;
  font-weight: 700;
}

.account-avatar-image { width: 100%; height: 100%; border-radius: inherit; object-fit: cover; display: block; }

.account-copy {
  min-width: 0;
}

.notification-title {
  margin: 0;
  font-size: 0.9rem;
  color: #ffffff;
}

.account-subtitle {
  margin: 0.16rem 0 0;
  font-size: 0.74rem;
  color: rgba(255, 255, 255, 0.8);
  line-height: 1.4;
}

.account-close-button {
  flex-shrink: 0;
  background: rgba(255, 255, 255, 0.15);
  color: #ffffff;
}

.account-close-button:hover {
  background: rgba(255, 255, 255, 0.25);
}

.notification-panel-section {
  padding: 0.85rem 0.85rem 0.4rem;
  display: grid;
  gap: 0.55rem;
}

.panel-quick-link {
  width: 100%;
  border: none;
  border-radius: 18px;
  padding: 0.76rem 0.8rem;
  background: rgba(255, 255, 255, 0.78);
  border: 1px solid rgba(17, 30, 25, 0.05);
  display: flex;
  align-items: center;
  gap: 0.7rem;
  cursor: pointer;
  text-align: left;
  transition:
    transform 180ms ease,
    box-shadow 180ms ease,
    background 180ms ease;
}

.panel-quick-link:hover {
  transform: translateY(-1px);
  box-shadow: 0 12px 24px rgba(12, 18, 16, 0.06);
}

.panel-quick-icon {
  width: 38px;
  height: 38px;
  border-radius: 14px;
  background: rgba(17, 30, 25, 0.05);
  display: grid;
  place-items: center;
  color: var(--brand-700);
  flex-shrink: 0;
}

.panel-quick-copy {
  display: flex;
  flex-direction: column;
  min-width: 0;
}

.panel-quick-copy strong {
  font-size: 0.82rem;
  color: var(--text-strong);
  line-height: 1.2;
}

.panel-quick-copy small {
  margin-top: 0.16rem;
  font-size: 0.7rem;
  color: var(--text-soft);
  line-height: 1.3;
}

.notification-panel-footer {
  padding: 0 0.8rem 0.9rem;
}

.logout-button {
  width: 100%;
  border: none;
  border-radius: 16px;
  padding: 0.82rem 0.95rem;
  background: linear-gradient(180deg, #274039 0%, #1b2d28 100%);
  color: #ffffff;
  font-weight: 800;
  font-size: 0.78rem;
  cursor: pointer;
  display: inline-flex;
  align-items: center;
  justify-content: center;
  gap: 0.48rem;
  box-shadow: 0 12px 28px rgba(16, 26, 23, 0.18);
  transition:
    transform 0.18s ease,
    box-shadow 0.18s ease;
}

.logout-button:hover {
  transform: translateY(-1px);
  box-shadow: 0 14px 30px rgba(16, 26, 23, 0.24);
}

.menu-fade-enter-active,
.menu-fade-leave-active {
  transition:
    opacity 0.18s ease,
    transform 0.18s ease;
}

.menu-fade-enter-from,
.menu-fade-leave-to {
  opacity: 0;
  transform: translateY(4px) scale(0.985);
}

@media (max-width: 768px) {
  .header-content {
    flex-wrap: wrap;
    padding: 0.75rem 0.85rem;
    min-height: auto;
  }

  .header-nav {
    margin-left: 0;
    justify-content: flex-end;
    flex: 1;
  }

  .program-search {
    order: 3;
    width: 100%;
    flex-basis: 100%;
  }

  .main-layout {
    display: flex;
    flex-direction: column;
    flex: 1;
    width: 100%;
    max-width: 1680px;
    margin: 0 auto;
    height: calc(100vh - 64px);
    min-height: 0;
    overflow: hidden;
    background-color: var(--white);
  }

  .sidebar {
    --sidebar-toggle-offset: 0px;

    position: static;
    top: auto;
    display: flex;
    flex-direction: column;
    align-self: stretch;
    width: 100%;
    min-width: 0;
    height: auto;
    min-height: 0;
    max-height: 45vh;
    flex: 0 0 auto;
    overflow-y: auto;
    padding: 0.75rem 0;
    background-color: var(--white);
    border-right: none;
    border-bottom: 1px solid var(--border-light);
  }

  .sidebar.is-collapsed {
    width: 100%;
    min-width: 100%;
  }

  .sidebar-collapse-toggle {
    display: none;
  }

  .sidebar.is-collapsed .sidebar-link {
    justify-content: flex-start;
    gap: 0.75rem;
    padding: 0.75rem 1.5rem;
  }

  .sidebar.is-collapsed .sidebar-link span {
    display: inline;
  }

  .sidebar.is-collapsed .sidebar-link--admin {
    justify-content: flex-start;
  }

  .sidebar.is-collapsed .sidebar-link--admin .sidebar-link__main {
    justify-content: flex-start;
    gap: 0.75rem;
    padding: 0.75rem 1.5rem;
  }

  .sidebar.is-collapsed .sidebar-link--admin .sidebar-link__main span {
    display: inline;
  }

  .sidebar.is-collapsed .sidebar-subnav-toggle,
  .sidebar-subnav-toggle {
    display: flex;
  }

  .sidebar.is-collapsed .sidebar-group-switcher {
    display: block;
  }

  .sidebar-group-switcher {
    margin-top: 0.75rem;
    padding: 0.75rem 0 0;
    border-top: 1px solid var(--border-light);
  }

  .main-content {
    flex: 1 1 auto;
    min-width: 0;
    min-height: 0;
    width: 100%;
    height: auto;
    overflow-y: auto;
    padding: 1rem;
  }

  .main-content--events {
    padding: 0;
  }

  .notification-panel {
    top: 88px;
    right: 12px;
    left: 12px;
    width: auto;
    max-width: none;
  }
}

/* =========================================================
   Dark mode — header search bar
   ========================================================= */

html[data-theme='dark'] .search-bar {
  background: #18231f;
  color: #e8eeee;
  border-color: #34413d;
  box-shadow: 0 1px 2px rgba(0, 0, 0, 0.25);
}

html[data-theme='dark'] .search-bar::placeholder {
  color: #899793;
}

html[data-theme='dark'] .search-bar:focus {
  background: #18231f;
  color: #ffffff;
  border-color: #4d625d;
  box-shadow: 0 0 0 3px rgba(32, 201, 166, 0.15);
}

</style>
