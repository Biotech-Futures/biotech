<script setup lang="ts">
import { computed, ref } from 'vue'
import { useRoute, useRouter, RouterLink, RouterView } from 'vue-router'
import { useAuthStore } from './stores/auth'

const route = useRoute()
const router = useRouter()
const auth = useAuthStore()

const isLoginPage = computed(() => route.path === '/login')

const showNotifications = ref(false)
const hasNotifications = ref(true)
const toggleNotifications = () => {
  showNotifications.value = !showNotifications.value
  if (showNotifications.value) hasNotifications.value = false
}

// Quick jump: close panel after clicking menu item
const go = (path: string) => {
  showNotifications.value = false
  router.push(path)
}
</script>

<template>
  <div class="app-container">
    <!-- Header: hidden on login page -->
    <header class="header" v-if="!isLoginPage">
      <div class="header-content">
        <div class="logo-section">
          <RouterLink to="/dashboard" class="logo">
            <div class="logo-icon">BTF</div>
            <span class="logo-text">BIOTech Futures Hub</span>
          </RouterLink>
        </div>

        <div class="header-nav">
          <input type="text" class="search-bar" placeholder="Search Program" />
          <div class="user-menu">
            <div style="position: relative;">
              <div class="user-avatar" @click="toggleNotifications">
                {{ auth.initials }}
                <span v-if="hasNotifications" class="notification-badge"></span>
              </div>
            </div>
          </div>
        </div>
      </div>
    </header>

    <!-- Main layout: hidden on login page -->
    <div class="main-layout" v-if="!isLoginPage">
      <!-- Sidebar -->
      <aside class="sidebar">
        <nav class="sidebar-nav">
          <ul>
            <li class="sidebar-item">
              <RouterLink
                to="/dashboard"
                class="sidebar-link"
                :class="{ active: route.path === '/dashboard' }"
              >
                <i class="fas fa-home sidebar-icon"></i><span>Home</span>
              </RouterLink>
            </li>

            <li class="sidebar-item">
              <RouterLink
                to="/groups"
                class="sidebar-link"
                :class="{ active: route.path.includes('/groups') }"
              >
                <i class="fas fa-users sidebar-icon"></i><span>Groups</span>
              </RouterLink>
            </li>

            <li class="sidebar-item">
              <RouterLink
                to="/events"
                class="sidebar-link"
                :class="{ active: route.path === '/events' }"
              >
                <i class="fas fa-calendar sidebar-icon"></i><span>Events</span>
              </RouterLink>
            </li>

            <li class="sidebar-item">
              <RouterLink
                to="/resources"
                class="sidebar-link"
                :class="{ active: route.path === '/resources' }"
              >
                <i class="fas fa-book sidebar-icon"></i><span>Resources</span>
              </RouterLink>
            </li>

            <li class="sidebar-item">
              <RouterLink
                to="/announcements"
                class="sidebar-link"
                :class="{ active: route.path === '/announcements' }"
              >
                <i class="fas fa-bullhorn sidebar-icon"></i><span>Announcements</span>
              </RouterLink>
            </li>

            <li class="sidebar-item" v-if="auth.isAdmin">
              <RouterLink
                to="/admin"
                class="sidebar-link"
                :class="{ active: route.path === '/admin' }"
              >
                <i class="fas fa-cog sidebar-icon"></i><span>Admin Panel</span>
              </RouterLink>
            </li>
          </ul>
        </nav>
      </aside>

      <!-- Content area -->
      <RouterView />
    </div>

    <!-- Login page (fullscreen) -->
    <RouterView v-else />

    <!-- Notification Panel (only two menu items kept) -->
    <div :class="['notification-panel', { show: showNotifications }]" v-if="!isLoginPage">
      <div class="notification-header">
        <h4 style="margin: 0;">Notifications</h4>
        <button
          @click="showNotifications = false"
          style="background: none; border: none; color: white; cursor: pointer;"
          aria-label="Close"
        >
          <i class="fas fa-times"></i>
        </button>
      </div>

      <div class="notification-list">
        <div
          class="notification-item"
          role="button"
          tabindex="0"
          @click="go('/profile')"
          @keydown.enter="go('/profile')"
        >
          <i class="fas fa-user" style="margin-right: 0.5rem; color: var(--dark-green);"></i>
          <strong>Edit your profile</strong>
        </div>

        <div
          class="notification-item"
          role="button"
          tabindex="0"
          @click="go('/contact')"
          @keydown.enter="go('/contact')"
        >
          <i class="fas fa-headset" style="margin-right: 0.5rem; color: var(--dark-green);"></i>
          <strong>Contact administrator</strong>
        </div>

        <!-- Optional: Logout -->
        <div
          class="notification-item"
          role="button"
          tabindex="0"
          @click="auth.logout(); go('/login')"
          @keydown.enter="auth.logout(); go('/login')"
        >
          <i class="fas fa-sign-out-alt" style="margin-right: 0.5rem; color: var(--dark-green);"></i>
          <strong>Log out</strong>
        </div>
      </div>
    </div>
  </div>
</template>

<style scoped>
.app-container {
  min-height: 100vh;
  background: #f7f9fa;
}
.header {
  background: #fff;
  border-bottom: 1px solid #e5e5e5;
  padding: 0.5rem 2rem;
  display: flex;
  align-items: center;
  justify-content: space-between;
}
.header-content {
  width: 100%;
  display: flex;
  align-items: center;
  justify-content: space-between;
}
.logo-section {
  display: flex;
  align-items: center;
}
.logo {
  display: flex;
  align-items: center;
  text-decoration: none;
}
.logo-icon {
  background: var(--dark-green, #1b5e20);
  color: #fff;
  font-weight: bold;
  font-size: 1.5rem;
  border-radius: 50%;
  width: 2.5rem;
  height: 2.5rem;
  display: flex;
  align-items: center;
  justify-content: center;
  margin-right: 0.75rem;
}
.logo-text {
  font-size: 1.2rem;
  font-weight: 600;
  color: #222;
}
.header-nav {
  display: flex;
  align-items: center;
}
.search-bar {
  border: 1px solid #e5e5e5;
  border-radius: 4px;
  padding: 0.5rem 1rem;
  margin-right: 1.5rem;
  font-size: 1rem;
}
.user-menu {
  display: flex;
  align-items: center;
}
.user-avatar {
  background: var(--dark-green, #1b5e20);
  color: #fff;
  border-radius: 50%;
  width: 2.2rem;
  height: 2.2rem;
  display: flex;
  align-items: center;
  justify-content: center;
  font-weight: bold;
  font-size: 1.1rem;
  cursor: pointer;
  position: relative;
}
.notification-badge {
  position: absolute;
  top: 0.2rem;
  right: 0.2rem;
  width: 0.7rem;
  height: 0.7rem;
  background: #e53935;
  border-radius: 50%;
  border: 2px solid #fff;
}
.main-layout {
  display: flex;
  min-height: calc(100vh - 60px);
}
.sidebar {
  width: 220px;
  background: #fff;
  border-right: 1px solid #e5e5e5;
  padding: 2rem 0.5rem 2rem 1.5rem;
}
.sidebar-nav {
  list-style: none;
  padding: 0;
  margin: 0;
}
.sidebar-item {
  margin-bottom: 1.2rem;
}
.sidebar-link {
  display: flex;
  align-items: center;
  color: #222;
  text-decoration: none;
  font-size: 1.05rem;
  padding: 0.5rem 1rem;
  border-radius: 6px;
  transition: background 0.2s, color 0.2s;
}
.sidebar-link.active,
.sidebar-link:hover {
  background: var(--light-green, #e8f5e9);
  color: var(--dark-green, #1b5e20);
}
.sidebar-icon {
  margin-right: 0.7rem;
  font-size: 1.2rem;
}
.notification-panel {
  position: fixed;
  top: 70px;
  right: -350px;
  width: 320px;
  background: var(--dark-green, #1b5e20);
  color: #fff;
  border-radius: 10px 0 0 10px;
  box-shadow: 0 2px 16px rgba(0,0,0,0.12);
  z-index: 1000;
  transition: right 0.3s cubic-bezier(.4,0,.2,1);
  padding: 0 0 1rem 0;
}
.notification-panel.show {
  right: 0;
}
.notification-header {
  display: flex;
  align-items: center;
  justify-content: space-between;
  background: #145a32;
  padding: 1rem 1.2rem 0.7rem 1.2rem;
  border-radius: 10px 0 0 0;
}
.notification-list {
  padding: 1rem 1.2rem 0 1.2rem;
}
.notification-item {
  background: #fff;
  color: #222;
  border-radius: 6px;
  padding: 0.7rem 1rem;
  margin-bottom: 0.7rem;
  display: flex;
  align-items: center;
  cursor: pointer;
  transition: background 0.2s;
}
.notification-item:hover {
  background: #e8f5e9;
}
</style>
