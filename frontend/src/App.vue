<script setup lang="ts">

/*
    lang='ts'说明这里用的是Typescript
    Vue 3 根布局组件 / App layout component
    负责控制整个页面的全局框架
    包括：
        1.顶部导航栏 header
        2.左侧侧边栏 sidebar（会随着页面滑动导致被遮盖，已修改2026/03/19）
        3.中间主内容区域 RouterView
        4.登录页是否隐藏导航
        5.右上角头像点击后弹出的用户菜单面板 user menu panel
        6.根据用户身份决定是否显示管理员入口 Admin Panel
*/
//ref表明创建响应式变量的工具
//computed表明用来创建计算属性，是根据已有状态推导出来的
import { computed, ref, watch, onMounted, onBeforeUnmount } from 'vue'

// useRoute()用于获取当前路由信息，/login或者/dashboard
// 例如：const route = useRoute()，route.path === '/dashboard'判断，router.push(path)跳转
import { useRoute, useRouter, RouterLink, RouterView } from 'vue-router'

// 导入认证store,auth一般会包含当前用户信息，是否登录，是否是管理员等等
import { useAuthStore } from './stores/auth'
import logo from '@/assets/btf-logo.png'

// 获取当前路由对象，即当前页面的信息
const route = useRoute()

// 路由跳转对象，在函数里主动切换页面
const router = useRouter()

// 认证状态对象，获取当前用户登陆状态以及权限信息
const auth = useAuthStore()

// 这个值决定了header和sidebar是否显示，即包裹整个网页的导航栏和标题
const isLoginPage = computed(() => route.path === '/login')

// 控制右侧的用户菜单面板是显示还是隐藏
const showUserMenu = ref(false)

// 右上角未读标记（小红点）是否显示：<span v-if="hasUserMenuBadge" class="notification-badge"></span>
const hasUserMenuBadge = ref(true)

// 用户菜单面板和头像按钮的引用，用于点击外部关闭和Esc关闭后聚焦
const userMenuPanelRef = ref<HTMLElement | null>(null)
const avatarRef = ref<HTMLElement | null>(null)

// 切换用户菜单面板的函数
const toggleUserMenu = () => {
  // 如果之前关闭，就打开。如果之前打开，就关闭。
  showUserMenu.value = !showUserMenu.value

  // 用户点开了用户菜单，就默认认为“已经看过了”，于是把小红点消掉
  if (showUserMenu.value) hasUserMenuBadge.value = false
}

// Quick jump: close panel after clicking menu item
// 快速跳转界面，即从右上方的用户菜单面板跳转，需要执行关闭面板和页面跳转两个动作
const go = (path: string) => {
  showUserMenu.value = false
  router.push(path)
}

// 点击空白处自动关闭面板
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

// 按下Esc关闭面板
const handleKeydown = (event: KeyboardEvent) => {
  if (event.key === 'Escape' && showUserMenu.value) {
    showUserMenu.value = false
    avatarRef.value?.focus?.()
  }
}

// 路由切换时自动关闭面板
watch(
  () => route.fullPath,
  () => {
    showUserMenu.value = false
  }
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

<template>
  <div class="app-container">
    <!-- Header: hidden on login page -->
    <!-- 登陆时隐藏header -->
    <header class="header" v-if="!isLoginPage">
      <!-- Header的内部容器，也就是最上方绿色的一层 -->
      <div class="header-content">
        <!-- 左侧logo区域 -->
        <div class="logo-section">
          <!-- 跳转，点击logo或者文字部分，会返回首页 -->
          <RouterLink to="/dashboard" class="logo">
            <div class="logo-icon"><img :src="logo" alt="BIOTech Futures" /></div>
            <span class="logo-text">BIOTech Futures Hub</span>
          </RouterLink>
        </div>
        <!-- 右侧搜索框区域，纯静态搜索，没有绑定任何事件 -->
        <div class="header-nav">
          <input type="text" class="search-bar" placeholder="Search Program" />
          <!-- 用户头像区域 -->
          <div class="user-menu">
            <div style="position: relative;">
              <!-- 点击头像触发用户菜单面板，{{ auth.initials }}显示用户名首字母 -->
              <div class="user-avatar" ref="avatarRef" @click="toggleUserMenu" tabindex="0">
                {{ auth.initials }}
                <!-- 有标记就显示右上角小红点 -->
                <span v-if="hasUserMenuBadge" class="notification-badge"></span>
              </div>
            </div>
          </div>
        </div>
      </div>
    </header>

    <!-- 下方主要布局，不是登录页才显示 -->
    <div class="main-layout" v-if="!isLoginPage">
      <!-- Sidebar -->
      <!-- 左侧导航栏 -->
      <aside class="sidebar">
        <nav class="sidebar-nav">
          <!-- 所有菜单都是统一模式 -->
          <!-- :class="{ active: route.path === '/dashboard' }"动态 class 绑定，高亮菜单链接 -->
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
        </nav>
      </aside>

      <!-- 内容区 -->
      <main class="main-content">
        <RouterView />
      </main>
    </div>

    <!-- 登录页（全屏） -->
    <RouterView v-else />

    <!-- User Menu Panel -->
    <div
      ref="userMenuPanelRef"
      :class="['notification-panel', { show: showUserMenu }]"
      v-if="!isLoginPage"
    >
      <div class="notification-header">
        <h4 style="margin: 0;">Account</h4>
        <button
          @click="showUserMenu = false"
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
.main-layout {
  display: flex;
  align-items: flex-start;
  min-height: calc(100vh - 80px);
}

.sidebar {
  position: sticky;
  top: 80px;
  align-self: flex-start;
  height: calc(100vh - 80px);
  overflow-y: auto;
  flex-shrink: 0;
  background: #fff;
}

.main-content {
  flex: 1;
  min-width: 0;
}

/* 小屏幕下取消 sticky，避免移动端布局异常 */
@media (max-width: 768px) {
  .main-layout {
    flex-direction: column;
    min-height: auto;
  }

  .sidebar {
    position: static;
    top: auto;
    align-self: auto;
    height: auto;
    width: 100%;
    overflow-y: visible;
  }

  .main-content {
    width: 100%;
  }
}
</style>