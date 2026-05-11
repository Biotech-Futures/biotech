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
                :class="{ active: route.path === '/events' }"
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
      </aside>

      <main class="main-content">
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
import logo from '@/assets/btf-logo.png'

const route = useRoute()
const router = useRouter()
const auth = useAuthStore()

const handleLogout = async () => {
  await auth.logout()
  go('/login')
}

const isLoginPage = computed(() =>
  ['/login', '/auth/callback', '/auth/reset-password'].includes(route.path),
)

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

watch(
  () => route.fullPath,
  () => {
    showUserMenu.value = false
  },
)

onMounted(() => {
  document.addEventListener('click', handleClickOutside)
  document.addEventListener('keydown', handleKeydown)
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

.main-content {
  flex: 1;
  min-width: 0;
  padding: 1rem;
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

  .main-content {
    width: 100%;
    margin-left: 0;
    padding: 0.85rem;
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
