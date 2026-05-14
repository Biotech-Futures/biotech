<template>
  <div class="app-container">
    <header class="header" v-if="!isLoginPage">
      <div class="header-content">
        <div class="logo-section">
          <RouterLink to="/dashboard" class="logo">
            <div class="logo-icon">
              <img :src="logo" alt="BIOTech Futures" />
            </div>
            <span class="logo-text">BIOTech Futures Hub</span>
          </RouterLink>
        </div>

        <div class="header-nav">
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
              <span class="user-avatar-text">{{ auth.initials }}</span>
              <span v-if="hasUserMenuBadge" class="notification-badge"></span>
            </button>
          </div>
        </div>
      </div>
    </header>

    <div class="main-layout" v-if="!isLoginPage">
      <aside class="sidebar">
        <nav class="sidebar-nav">
          <ul class="sidebar-list">
            <li class="sidebar-item">
              <RouterLink
                to="/dashboard"
                class="sidebar-link"
                :class="{ active: route.path === '/dashboard' }"
              >
                <i class="fas fa-home sidebar-icon"></i>
                <span>Home</span>
              </RouterLink>
            </li>

            <li class="sidebar-item">
              <RouterLink
                to="/groups"
                class="sidebar-link"
                :class="{ active: route.path.includes('/groups') }"
              >
                <i class="fas fa-users sidebar-icon"></i>
                <span>Groups</span>
              </RouterLink>
            </li>

            <li class="sidebar-item">
              <RouterLink
                to="/events"
                class="sidebar-link"
                :class="{ active: route.path.startsWith('/events') }"
              >
                <i class="fas fa-calendar sidebar-icon"></i>
                <span>Events</span>
              </RouterLink>
            </li>

            <li class="sidebar-item">
              <RouterLink
                to="/announcements"
                class="sidebar-link"
                :class="{ active: route.path === '/announcements' }"
              >
                <i class="fas fa-bullhorn sidebar-icon"></i>
                <span>Announcements</span>
              </RouterLink>
            </li>

            <li class="sidebar-item">
              <RouterLink
                to="/resources"
                class="sidebar-link"
                :class="{ active: route.path === '/resources' }"
              >
                <i class="fas fa-book sidebar-icon"></i>
                <span>Resources</span>
              </RouterLink>
            </li>

            <li class="sidebar-item" v-if="auth.isAdmin">
              <RouterLink
                to="/admin"
                class="sidebar-link"
                :class="{ active: route.path === '/admin' }"
              >
                <i class="fas fa-cog sidebar-icon"></i>
                <span>Admin Panel</span>
              </RouterLink>
            </li>
          </ul>
        </nav>

        <section
          v-if="showSidebarGroupSwitcher"
          class="sidebar-group-switcher"
          aria-label="Group switcher"
        >
          <div class="sidebar-group-switcher-header">
            <span>Groups</span>
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

          <div v-else class="sidebar-group-list">
            <RouterLink
              v-for="groupOption in sidebarGroups"
              :key="groupOption.id"
              :to="`/groups/${groupOption.id}`"
              class="sidebar-group-link"
              :class="{
                active: isSidebarGroupActive(groupOption.id),
                unread: groupOption.hasUnread && !isSidebarGroupActive(groupOption.id),
              }"
            >
              <span class="sidebar-group-copy">
                <span class="sidebar-group-name">{{ groupOption.name }}</span>
                <small>{{ formatSidebarGroupMeta(groupOption) }}</small>
              </span>
              <span
                v-if="groupOption.hasUnread && !isSidebarGroupActive(groupOption.id)"
                class="sidebar-group-badge"
              >
                New
              </span>
            </RouterLink>
          </div>
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
            <div class="account-avatar">{{ auth.initials }}</div>

            <div class="account-copy">
              <h4 class="notification-title">My account</h4>
              <p class="account-subtitle">
                {{ auth.isAdmin ? 'Administrator access' : 'Standard member access' }}
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
              <small>Update your account details</small>
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
import { buildSessionHeaders } from '@/utils/csrf'
import { apiErrorFromResponse } from '@/utils/apiError'
import logo from '@/assets/btf-logo.png'

const route = useRoute()
const router = useRouter()
const auth = useAuthStore()
const API_BASE_URL = import.meta.env.VITE_API_BASE_URL || 'http://localhost:8000'

interface CollectionResponse {
  results?: unknown[]
  items?: unknown[]
}

interface GroupMembership {
  groupId: string
  userId: string
  leftAt: string
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
  ['/login', '/auth/callback', '/auth/reset-password', '/auth/set-password'].includes(route.path),
)
const showSidebarGroupSwitcher = computed(
  () => !isLoginPage.value && route.path.startsWith('/groups'),
)
const sidebarGroups = ref<SidebarGroupOption[]>([])
const isLoadingSidebarGroups = ref(false)
const sidebarGroupError = ref('')
let sidebarGroupLoadSequence = 0

const showUserMenu = ref(false)
const hasUserMenuBadge = ref(true)
const userMenuPanelRef = ref<HTMLElement | null>(null)
const avatarRef = ref<HTMLElement | null>(null)

const toggleUserMenu = () => {
  showUserMenu.value = !showUserMenu.value
  if (showUserMenu.value) hasUserMenuBadge.value = false
}

const go = (path: string) => {
  showUserMenu.value = false
  router.push(path)
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

const normalizeSidebarMembership = (item: Record<string, unknown>): GroupMembership => ({
  groupId: String(item.group ?? item.group_id ?? item.groupId ?? ''),
  userId: String(item.user ?? item.user_id ?? item.userId ?? ''),
  leftAt: String(item.left_at ?? item.leftAt ?? ''),
})

const normalizeSidebarGroup = (
  item: Record<string, unknown>,
  memberCount = 0,
): SidebarGroupOption => ({
  id: String(item.id ?? ''),
  name: String(item.group_name ?? item.name ?? item.title ?? (item.id ? `Group ${item.id}` : 'Group')),
  memberCount,
  hasUnread: false,
  latestAt: '',
})

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

  try {
    const [groupsData, membershipsData] = await Promise.all([
      requestJson(`${API_BASE_URL}/groups/groups/?page_size=100`),
      requestJson(`${API_BASE_URL}/groups/group-members/?page_size=100`),
    ])
    if (sequence !== sidebarGroupLoadSequence) return

    const memberships = extractCollectionItems(membershipsData)
      .map(normalizeSidebarMembership)
      .filter((item) => item.groupId && !item.leftAt)
    const currentUserId = String(auth.user?.id || '')
    const visibleGroupIds = auth.isAdmin
      ? null
      : new Set(
          memberships
            .filter((item) => currentUserId && item.userId === currentUserId)
            .map((item) => item.groupId),
        )
    const memberCounts = new Map<string, number>()

    memberships.forEach((item) => {
      memberCounts.set(item.groupId, (memberCounts.get(item.groupId) || 0) + 1)
    })

    const groups = extractCollectionItems(groupsData)
      .filter((item) => {
        const groupId = String(item.id ?? '')
        return groupId && (visibleGroupIds === null || visibleGroupIds.has(groupId))
      })
      .map((item) => normalizeSidebarGroup(item, memberCounts.get(String(item.id ?? '')) || 0))
      .sort((a, b) => a.name.localeCompare(b.name))

    sidebarGroups.value = groups
    // N requests (one per group) — defer behind idle so the page is
    // interactive before unread/latest-at indicators light up.
    const runLatest = () => void loadSidebarLatestMessageState(groups, sequence)
    const ric = (window as unknown as { requestIdleCallback?: (cb: () => void) => void })
      .requestIdleCallback
    if (typeof ric === 'function') ric(runLatest)
    else window.setTimeout(runLatest, 250)
  } catch (error) {
    if (sequence === sidebarGroupLoadSequence) {
      sidebarGroups.value = []
      sidebarGroupError.value =
        error instanceof Error ? error.message : 'Group list unavailable'
    }
  } finally {
    if (sequence === sidebarGroupLoadSequence) {
      isLoadingSidebarGroups.value = false
    }
  }
}

const isSidebarGroupActive = (groupId: string) => String(route.params.id || '') === groupId

const formatSidebarGroupMeta = (groupOption: SidebarGroupOption) => {
  const count = groupOption.memberCount
  if (count > 0) return `${count} ${count === 1 ? 'member' : 'members'}`
  return 'Group workspace'
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

watch(
  () => [auth.user?.id, auth.isAdmin],
  () => {
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

  document.addEventListener('click', handleClickOutside)
  document.addEventListener('keydown', handleKeydown)
  scheduleSidebarLoad()
})

onBeforeUnmount(() => {
  document.removeEventListener('click', handleClickOutside)
  document.removeEventListener('keydown', handleKeydown)
})
</script>

<style scoped>
:global(html),
:global(body),
:global(#app) {
  width: 100%;
  max-width: none;
  margin: 0;
  padding: 0;
}

:global(body) {
  overflow-x: hidden;
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

.header {
  position: sticky;
  top: 0;
  z-index: 1000;
  padding: 0.75rem 0;
  background-color: var(--dark-green);
  color: var(--white);
  box-shadow: 0 2px 4px var(--shadow);
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
  background-color: var(--white);
}

.sidebar {
  display: flex;
  flex-direction: column;
  width: 250px;
  min-width: 250px;
  flex-shrink: 0;
  min-height: calc(100vh - 64px);
  padding: 1.5rem 0;
  background-color: var(--white);
  border-right: 1px solid var(--border-light);
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
  color: var(--charcoal);
  border-left: 3px solid transparent;
  transition:
    background-color 0.2s ease,
    color 0.2s ease,
    border-color 0.2s ease;
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

.sidebar-group-switcher {
  margin-top: auto;
  padding: 1rem 0.85rem 0;
}

.sidebar-group-switcher-header {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 0.5rem;
  padding: 0 0.65rem 0.5rem;
  color: var(--text-soft);
  font-size: 0.72rem;
  font-weight: 800;
  letter-spacing: 0.08em;
  text-transform: uppercase;
}

.sidebar-group-list {
  display: grid;
  gap: 0.25rem;
  max-height: min(360px, 42vh);
  overflow-y: auto;
}

.sidebar-group-link {
  position: relative;
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 0.55rem;
  min-height: 52px;
  padding: 0.55rem 0.65rem;
  border: 1px solid transparent;
  border-radius: 8px;
  color: var(--charcoal);
  text-decoration: none;
  transition:
    background-color 0.2s ease,
    border-color 0.2s ease,
    color 0.2s ease;
}

.sidebar-group-link:hover {
  border-color: var(--line-mid);
  background: #f4f8f6;
  color: var(--dark-green);
}

.sidebar-group-link.active {
  border-color: rgba(35, 70, 59, 0.2);
  background: var(--light-green);
  color: var(--dark-green);
}

.sidebar-group-link.unread {
  border-color: rgba(61, 106, 91, 0.24);
  background: #eef7f2;
}

.sidebar-group-copy {
  min-width: 0;
  display: grid;
  gap: 0.12rem;
}

.sidebar-group-name {
  overflow: hidden;
  color: inherit;
  font-size: 0.88rem;
  font-weight: 650;
  text-overflow: ellipsis;
  white-space: nowrap;
}

.sidebar-group-link.unread .sidebar-group-name {
  font-weight: 800;
}

.sidebar-group-copy small {
  overflow: hidden;
  color: #6c757d;
  font-size: 0.72rem;
  font-weight: 600;
  text-overflow: ellipsis;
  white-space: nowrap;
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
  padding: 1rem;
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

.account-avatar {
  width: 42px;
  height: 42px;
  border-radius: 14px;
  display: grid;
  place-items: center;
  background: linear-gradient(180deg, #314e43 0%, #22362f 100%);
  color: #ffffff;
  font-size: 0.9rem;
  font-weight: 800;
  box-shadow: 0 10px 24px rgba(8, 14, 13, 0.16);
}

.account-copy {
  min-width: 0;
}

.notification-title {
  margin: 0;
  font-size: 0.9rem;
  color: var(--text-strong);
}

.account-subtitle {
  margin: 0.16rem 0 0;
  font-size: 0.74rem;
  color: var(--text-soft);
  line-height: 1.4;
}

.account-close-button {
  flex-shrink: 0;
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
  }

  .main-layout {
    flex-direction: column;
    min-height: auto;
  }

  .sidebar {
    position: static;
    top: auto;
    left: auto;
    height: auto;
    width: 100%;
    min-width: 100%;
    overflow-y: visible;
    padding: 0.75rem;
    z-index: auto;
  }

  .sidebar-group-switcher {
    margin-top: 0.75rem;
    padding: 0.75rem 0 0;
    border-top: 1px solid var(--border-light);
  }

  .sidebar-group-list {
    display: flex;
    gap: 0.5rem;
    max-height: none;
    overflow-x: auto;
    overflow-y: hidden;
    padding-bottom: 0.15rem;
  }

  .sidebar-group-link {
    flex: 0 0 min(220px, 78vw);
  }

  .main-content {
    width: 100%;
    margin-left: 0;
    padding: 0.85rem;
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
</style>
