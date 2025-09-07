<script setup>
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

// 快捷跳转：点完菜单项自动关闭面板
const go = (path) => {
  showNotifications.value = false
  router.push(path)
}
</script>

<template>
  <div class="app-container">
    <!-- Header：登录页隐藏 -->
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

    <!-- 主布局：登录页隐藏 -->
    <div class="main-layout" v-if="!isLoginPage">
      <!-- Sidebar -->
      <aside class="sidebar">
        <nav class="sidebar-nav">
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
              <i class="fas fa-calendar sidebar-icon"></i><span>Workshops</span>
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

          <li class="sidebar-item">
            <RouterLink
              to="/admin"
              class="sidebar-link"
              :class="{ active: route.path === '/admin' }"
            >
              <i class="fas fa-cog sidebar-icon"></i><span>Admin Panel</span>
            </RouterLink>
          </li>
        </nav>
      </aside>

      <!-- 内容区 -->
      <RouterView />
    </div>

    <!-- 登录页（全屏） -->
    <RouterView v-else />

    <!-- Notification Panel（仅保留两个菜单项） -->
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

        <!-- 可选：登出 -->
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
