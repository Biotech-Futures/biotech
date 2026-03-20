<script setup>
/* Vue 3 的一种更简洁写法，叫 Composition API 的 setup 语法糖
  写在这里面的变量、函数、import 进来的内容，都可以直接在当前组件里使用，
  而且通常不需要再手动 return。
*/

// Import reactive utilities from Vue
// 从 Vue 导入响应式工具，用来定义响应式变量。只要依赖的数据变了，变量的结果也会自动更新。
import { ref, computed } from 'vue'

// Import router link component for declarative navigation
// 导入路由链接组件，用于声明式页面跳转
import { RouterLink } from 'vue-router'

/*
  1.登录时，前端将登录信息发送给厚度但，后端验证成功将相关信息传递给前端，一般都是：
  token，用户基本信息 user，可能还有 refresh token
  2.前端拿到返回结果后，保存到前端状态里，这时通常是前端的 auth store 或登录逻辑负责保存：
  存到 Pinia store 里，方便当前页面直接用
  存到 localStorage / sessionStorage / cookie，防止刷新页面就丢失
  3.当前没刷新页面时，直接从 Pinia store 取
  页面刷新之后，Pinia 里的内存数据通常会丢，所以这时一般：
  先从 localStorage 取 token，然后再用这个 token 去请求后端，然后前端再重新写回 store
*/

// Import Pinia helper to keep extracted store fields reactive
// 导入 Pinia 辅助方法，保证解构后的 store 字段仍然保持响应式
// const authStore = useAuthStore()
// const { user, token, isAuthenticated } = storeToRefs(authStore)
// 方便在组件里解构仓库字段，并且不丢失响应式。
import { storeToRefs } from 'pinia'

// Import authentication store
// 连接仓库本体，这样后续可以通过变量访问读取里面的数据：const authStore = useAuthStore()
import { useAuthStore } from '@/stores/auth'

// Import temporary mock data for groups, resources, and announcements
// 从本地的 mock.js 文件里导入模拟数据。当前组件展示的内容暂时不是从后端接口拿，而是先用本地假数据。
// 1.mockGroups 模拟的小组/群组数据
// 2.mockResources 模拟的资源数据，比如文件、链接、学习材料之类
// 3.mockAnnouncements 模拟的公告数据
// 真正上线后：前端 Vue 页面 → 发请求给 云端后端接口 → 后端去查 云端数据库 → 再把结果返回给前端
import { mockGroups, mockResources, mockAnnouncements } from '../data/mock.js'


// Get auth store instance
const auth = useAuthStore()
// Extract reactive user info and admin flag from the store
const { user, isAdmin } = storeToRefs(auth)

// groups，resources，announcements，adminWorkFlow都是目前写死在前端里的临时数据，等到正式上线
// 需要前端调取后端接口，通过后端访问云端数据库再返回这些内容。
const groups = ref(Array.isArray(mockGroups) ? mockGroups : [])
const resources = ref(Array.isArray(mockResources) ? mockResources : [])
const announcements = ref(Array.isArray(mockAnnouncements) ? mockAnnouncements : [])

// events需要后端返回，这里写死方便调试
const events = ref([
  {
    id: 101,
    title: 'Mentor Kickoff Workshop',
    date: '2026-03-25',
    time: '5:30 PM',
    location: 'Online',
    mode: 'Live session'
  },
  {
    id: 102,
    title: 'Group Check-in Session',
    date: '2026-03-28',
    time: '4:00 PM',
    location: 'Zoom',
    mode: 'Mentoring session'
  },
  {
    id: 103,
    title: 'Program Q&A',
    date: '2026-04-02',
    time: '6:00 PM',
    location: 'Online',
    mode: 'Open event'
  }
])

// 保存管理员待处理事项统计，同样需要后端接口返回，后台数据库统计数据
const adminWorkflow = ref({
  pendingMatches: 5,
  pendingReassignments: 2,
  pendingApprovals: 4,
  draftBulkMessages: 1
})


// Normalize role values so the dashboard can branch consistently
// 把当前用户各种可能的角色标记，统一归一化成前端更容易处理的三类角色：admin、teacher、student
// 无需后端返回，但是依赖后端返回的数据比如user.value
const normalizedRole = computed(() => {
  const rawRole = String(user.value?.role || '').toLowerCase()

  if (
    isAdmin?.value ||
    ['admin', 'administrator', 'local_admin', 'global_admin', 'local administrator', 'global administrator'].includes(rawRole)
  ) {
    return 'admin'
  }

  if (['teacher', 'mentor', 'supervisor'].includes(rawRole)) {
    return 'teacher'
  }

  return 'student'
})

// Expose whether the current user is a student or teacher or admin
// 标记当前用户是否为 student
const isStudent = computed(() => normalizedRole.value === 'student')
const isTeacher = computed(() => normalizedRole.value === 'teacher')
const isPlatformAdmin = computed(() => normalizedRole.value === 'admin')


// Format the current date once as a computed value for cleaner template usage
// 将当前日期做成计算属性，便于模板更清晰地使用
// 无需后端返回，依赖当前浏览器时间
const currentDateText = computed(() => {
  return new Date().toLocaleDateString('en-AU', {
    weekday: 'long',
    year: 'numeric',
    month: 'long',
    day: 'numeric'
  })
})

// Provide a clean fallback for the display
const displayName = computed(() => user.value?.name || 'User')
const displayTrack = computed(() => user.value?.track || user.value?.region || '—')
const roleLabel = computed(() => {
  if (isPlatformAdmin.value) return 'Administrator'
  if (isTeacher.value) return 'Teacher / Mentor'
  return 'Student'
})

/* Core dashboard data */

// Count
// 计算数量，用于概览
const announcementsCount = computed(() => announcements.value.length)
const resourcesCount = computed(() => resources.value.length)
const upcomingEventsCount = computed(() => events.value.length)
const groupsCount = computed(() => groups.value.length)

// Pick the next event for the highlighted schedule card
// 取出下一场活动，用于重点展示的 schedule 卡片
const nextEvent = computed(() => events.value[0] || null)

// Preview only the latest few announcements on the dashboard
// 只在 dashboard 上预览最新几条公告
const announcementsPreview = computed(() => announcements.value.slice(0, 3))

// Preview only a subset of resources to keep the first screen focused
// 只预览部分资源，避免首页首屏信息过载
const resourcesPreview = computed(() => resources.value.slice(0, 6))

// Preview only a few groups to keep the section compact
// 只预览少量 group，使该区域保持紧凑
const groupsPreview = computed(() => {
  // Let admins see a bit more overview than other roles
  // 让 admin 比其他角色看到略多一点的概览
  return groups.value.slice(0, isPlatformAdmin.value ? 4 : 3)
})

/* Role-aware labels */

// Change the groups section heading according to the user's role
// 根据用户角色动态调整 groups 区域标题
const groupsSectionTitle = computed(() => {
  if (isPlatformAdmin.value) return `Active Mentoring Groups (${groupsCount.value})`
  if (isTeacher.value) return `My Mentoring Groups (${groupsCount.value})`
  return `My Active Groups (${groupsCount.value})`
})

// Change the workflow card title according to the user's role
// 根据用户角色动态调整 workflow 卡片标题
const workflowSectionTitle = computed(() => {
  if (isPlatformAdmin.value) return 'Administrative Workflow'
  if (isTeacher.value) return 'Mentoring Checklist'
  return 'My Next Steps'
})

// Change the quick actions title according to the user's role
// 根据用户角色动态调整快捷操作区域标题
const quickActionsTitle = computed(() => {
  if (isPlatformAdmin.value) return 'Admin Quick Actions'
  if (isTeacher.value) return 'Mentor Quick Actions'
  return 'Student Quick Actions'
})

// Build a short hero message so the dashboard feels role-aware at first glance
// 构建一个简短的角色化欢迎说明，让用户进入页面时立刻知道重点
const heroMessage = computed(() => {
  if (isPlatformAdmin.value) {
    return 'Monitor matching, approvals, communication, and active program operations from one place.'
  }

  if (isTeacher.value) {
    return 'Keep track of your mentoring groups, upcoming sessions, support materials, and latest updates.'
  }

  return 'See your next event, group space, learning resources, and key program updates in one overview.'
})

// Resolve the headline of the event section based on role
// 根据角色动态调整活动模块标题
const eventSectionTitle = computed(() => {
  if (isPlatformAdmin.value) return 'Program Event Snapshot'
  if (isTeacher.value) return 'Next Mentoring Session'
  return 'Next Event'
})

// Resolve the label of the resource section based on role
// 根据角色动态调整资源模块标题
const resourcesSectionTitle = computed(() => {
  if (isPlatformAdmin.value) return 'Resource Library Snapshot'
  if (isTeacher.value) return 'Mentoring Resources'
  return 'Learn more with resources'
})

// Resolve the label of the announcement section based on role
// 根据角色动态调整公告模块标题
const announcementsSectionTitle = computed(() => {
  if (isPlatformAdmin.value) return 'Program Announcements'
  if (isTeacher.value) return 'Latest Program Updates'
  return 'Recent Announcements'
})

// Resolve the main destination in the header area
// 计算欢迎区主入口链接
const primaryHeaderLink = computed(() => {
  if (isPlatformAdmin.value) return '/groups'
  if (isTeacher.value) return '/events'
  return '/groups'
})

// Resolve the main destination label in the header area
// 计算欢迎区主入口文案
const primaryHeaderLabel = computed(() => {
  if (isPlatformAdmin.value) return 'Open admin area'
  if (isTeacher.value) return 'Open mentoring area'
  return 'Open my group'
})

// Provide a short list of top-line status pills for the hero section
// 为欢迎区生成一组简短状态标签，让首屏信息更完整
const headerHighlights = computed(() => {
  if (isPlatformAdmin.value) {
    return [
      { key: 'groups', label: `${groupsCount.value} active groups` },
      { key: 'matches', label: `${adminWorkflow.value.pendingMatches} pending matches` },
      { key: 'approvals', label: `${adminWorkflow.value.pendingApprovals} open approvals` }
    ]
  }

  if (isTeacher.value) {
    return [
      { key: 'groups', label: `${groupsCount.value} mentoring groups` },
      { key: 'events', label: `${upcomingEventsCount.value} upcoming sessions` },
      { key: 'resources', label: `${resourcesCount.value} support resources` }
    ]
  }

  return [
    { key: 'groups', label: `${groupsCount.value} active groups` },
    { key: 'events', label: `${upcomingEventsCount.value} upcoming events` },
    { key: 'resources', label: `${resourcesCount.value} learning resources` }
  ]
})


// Generate role-specific summary widgets so each role sees the right priorities
// 生成按角色区分的概览卡片，让不同角色看到不同重点
const summaryWidgets = computed(() => {
  if (isPlatformAdmin.value) {
    return [
      {
        key: 'groups',
        title: 'Active Groups',
        value: groupsCount.value,
        subtext: 'All mentoring groups currently active',
        icon: 'fas fa-users',
        color: 'var(--eucalypt)',
        to: '/groups'
      },
      {
        key: 'events',
        title: 'Upcoming Events',
        value: upcomingEventsCount.value,
        subtext: nextEvent.value ? `Next: ${nextEvent.value.title}` : 'No scheduled event yet',
        icon: 'fas fa-calendar',
        color: 'var(--mint-green)',
        to: '/events'
      },
      {
        key: 'matches',
        title: 'Pending Matches',
        value: adminWorkflow.value.pendingMatches,
        subtext: 'Mentor allocation requests to review',
        icon: 'fas fa-random',
        color: 'var(--air-force-blue)',
        to: '/groups'
      },
      {
        key: 'announcements',
        title: 'Announcements',
        value: announcementsCount.value,
        subtext: 'Program updates and broadcast posts',
        icon: 'fas fa-bullhorn',
        color: 'var(--dark-green)',
        to: '/announcements'
      }
    ]
  }

  if (isTeacher.value) {
    return [
      {
        key: 'groups',
        title: 'My Groups',
        value: groupsCount.value,
        subtext: 'Groups you are mentoring',
        icon: 'fas fa-users',
        color: 'var(--eucalypt)',
        to: '/groups'
      },
      {
        key: 'sessions',
        title: 'Upcoming Sessions',
        value: upcomingEventsCount.value,
        subtext: nextEvent.value ? `Next: ${nextEvent.value.title}` : 'No scheduled session yet',
        icon: 'fas fa-calendar',
        color: 'var(--mint-green)',
        to: '/events'
      },
      {
        key: 'resources',
        title: 'Resources',
        value: resourcesCount.value,
        subtext: 'Guides, templates, and support materials',
        icon: 'fas fa-book',
        color: 'var(--air-force-blue)',
        to: '/resources'
      },
      {
        key: 'announcements',
        title: 'Announcements',
        value: announcementsCount.value,
        subtext: 'Latest program-wide updates',
        icon: 'fas fa-bullhorn',
        color: 'var(--dark-green)',
        to: '/announcements'
      }
    ]
  }

  return [
    {
      key: 'groups',
      title: 'My Groups',
      value: groupsCount.value,
      subtext: 'Your active mentoring groups',
      icon: 'fas fa-users',
      color: 'var(--eucalypt)',
      to: '/groups'
    },
    {
      key: 'events',
      title: 'Upcoming Events',
      value: upcomingEventsCount.value,
      subtext: nextEvent.value ? `Next: ${nextEvent.value.title}` : 'No upcoming event yet',
      icon: 'fas fa-calendar',
      color: 'var(--mint-green)',
      to: '/events'
    },
    {
      key: 'announcements',
      title: 'Announcements',
      value: announcementsCount.value,
      subtext: 'Stay up to date with the program',
      icon: 'fas fa-bullhorn',
      color: 'var(--air-force-blue)',
      to: '/announcements'
    },
    {
      key: 'resources',
      title: 'Resources',
      value: resourcesCount.value,
      subtext: 'Learning and mentoring materials',
      icon: 'fas fa-book',
      color: 'var(--dark-green)',
      to: '/resources'
    }
  ]
})

/* Quick actions */
/* 快捷操作 */

// Provide role-specific quick actions so the dashboard drives action, not only browsing
// 提供按角色区分的快捷操作，让 dashboard 不只是浏览入口，而是行动入口
const quickActions = computed(() => {
  if (isPlatformAdmin.value) {
    return [
      { key: 'manage-groups', label: 'Manage Groups', to: '/groups' },
      { key: 'matching', label: 'Review Matching Queue', to: '/groups' },
      { key: 'events', label: 'Manage Events', to: '/events' },
      { key: 'announce', label: 'Post Announcement', to: '/announcements' },
      { key: 'resources', label: 'Review Resources', to: '/resources' },
      { key: 'users', label: 'Review Users', to: '/groups' }
    ]
  }

  if (isTeacher.value) {
    return [
      { key: 'groups', label: 'Open My Groups', to: '/groups' },
      { key: 'events', label: 'View Sessions', to: '/events' },
      { key: 'resources', label: 'Share Resources', to: '/resources' },
      { key: 'announcements', label: 'Check Updates', to: '/announcements' },
      { key: 'profile', label: 'Open Profile', to: '/profile' }
    ]
  }

  return [
    { key: 'events', label: 'View Next Event', to: '/events' },
    { key: 'groups', label: 'Open My Group', to: '/groups' },
    { key: 'resources', label: 'Explore Resources', to: '/resources' },
    { key: 'announcements', label: 'Read Updates', to: '/announcements' },
    { key: 'profile', label: 'View My Profile', to: '/profile' }
  ]
})

/* Role-specific workflow content */
/* 角色专属工作流内容 */

// Build a role-specific checklist or workflow summary for the lower dashboard card
// 构建按角色区分的 checklist 或工作流摘要，用于下方卡片
const workflowItems = computed(() => {
  if (isPlatformAdmin.value) {
    return [
      {
        key: 'matches',
        title: 'Pending mentor matches',
        meta: `${adminWorkflow.value.pendingMatches} items waiting for review`,
        to: '/groups'
      },
      {
        key: 'reassignments',
        title: 'Reassignment requests',
        meta: `${adminWorkflow.value.pendingReassignments} mentor reassignments to process`,
        to: '/groups'
      },
      {
        key: 'approvals',
        title: 'Approvals and user review',
        meta: `${adminWorkflow.value.pendingApprovals} approvals currently open`,
        to: '/groups'
      },
      {
        key: 'messages',
        title: 'Bulk communication drafts',
        meta: `${adminWorkflow.value.draftBulkMessages} draft broadcast ready`,
        to: '/announcements'
      }
    ]
  }

  if (isTeacher.value) {
    return [
      {
        key: 'session',
        title: 'Confirm your next mentoring session',
        meta: nextEvent.value ? `${nextEvent.value.title} · ${formatEventDate(nextEvent.value.date)}` : 'No next session available',
        to: '/events'
      },
      {
        key: 'groups',
        title: 'Check in with your groups',
        meta: `${groupsCount.value} group spaces available`,
        to: '/groups'
      },
      {
        key: 'resources',
        title: 'Review support resources',
        meta: `${resourcesCount.value} mentoring materials in the library`,
        to: '/resources'
      }
    ]
  }

  return [
    {
      key: 'event',
      title: 'Review your next event',
      meta: nextEvent.value ? `${nextEvent.value.title} · ${formatEventDate(nextEvent.value.date)}` : 'No upcoming event available',
      to: '/events'
    },
    {
      key: 'group',
      title: 'Check your mentoring group',
      meta: `${groupsCount.value} active group spaces available`,
      to: '/groups'
    },
    {
      key: 'resource',
      title: 'Continue with program resources',
      meta: `${resourcesCount.value} resources ready to explore`,
      to: '/resources'
    }
  ]
})

// Add a compact admin-only insight panel so admins see operational signals beyond the top widgets
// 增加一个仅管理员可见的运营摘要区，让管理端首页更接近真正的 admin dashboard
const adminInsightCards = computed(() => {
  if (!isPlatformAdmin.value) return []

  return [
    {
      key: 'reassignments',
      title: 'Pending Reassignments',
      value: adminWorkflow.value.pendingReassignments,
      meta: 'Requests that may require manual mentor reallocation',
      icon: 'fas fa-exchange-alt',
      to: '/groups'
    },
    {
      key: 'approvals',
      title: 'Open Approvals',
      value: adminWorkflow.value.pendingApprovals,
      meta: 'Items awaiting review before they move forward',
      icon: 'fas fa-user-check',
      to: '/groups'
    },
    {
      key: 'messages',
      title: 'Draft Broadcasts',
      value: adminWorkflow.value.draftBulkMessages,
      meta: 'Prepared communication drafts ready for final review',
      icon: 'fas fa-paper-plane',
      to: '/announcements'
    }
  ]
})

/* Helper functions */
/* 辅助函数 */

// Format an event date for a shorter dashboard display
// 将活动日期格式化为更适合 dashboard 的短格式
function formatEventDate(dateString) {
  // Return a safe fallback when no date is provided
  // 当没有日期时返回安全兜底文本
  if (!dateString) return 'TBC'

  // Format the date in a compact Australian English style
  // 以紧凑的澳洲英语格式输出日期
  return new Date(dateString).toLocaleDateString('en-AU', {
    day: 'numeric',
    month: 'short',
    year: 'numeric'
  })
}

// Resolve a resource icon based on the resource type
// 根据资源类型返回对应图标
function getResourceIcon(type) {
  // Map known resource types to Font Awesome icons
  // 将已知资源类型映射到 Font Awesome 图标
  const icons = {
    document: 'fas fa-file-alt',
    video: 'fas fa-video',
    link: 'fas fa-link',
    pdf: 'fas fa-file-pdf',
    article: 'fas fa-newspaper'
  }

  // Fallback to a generic file icon when type is unknown
  // 当类型未知时回退到通用文件图标
  return icons[type] || 'fas fa-file'
}

// Resolve a readable announcement title using safe fallbacks
// 使用安全兜底方式获取可读的公告标题
function getAnnouncementTitle(item) {
  // Try common title-like fields from different possible data shapes
  // 尝试兼容不同数据结构里常见的标题字段
  return item?.title || item?.name || item?.subject || 'Untitled announcement'
}

// Resolve readable announcement meta text using safe fallbacks
// 使用安全兜底方式获取公告的辅助信息文本
function getAnnouncementMeta(item) {
  // Try common time-related fields from different possible data shapes
  // 尝试兼容不同数据结构里常见的时间字段
  return item?.updated || item?.date || item?.created_at || 'Recently posted'
}

// Resolve a readable announcement snippet using safe fallbacks
// 使用安全兜底方式获取公告摘要文本
function getAnnouncementSnippet(item) {
  // Try common description-like fields from different possible data shapes
  // 尝试兼容不同数据结构里常见的摘要字段
  return item?.summary || item?.description || item?.content || item?.excerpt || 'Open the announcement to read more details.'
}

// Resolve a readable resource title using safe fallbacks
// 使用安全兜底方式获取资源标题
function getResourceTitle(item) {
  // Try common resource title fields from different possible data shapes
  // 尝试兼容不同数据结构里常见的资源标题字段
  return item?.title || item?.name || 'Untitled resource'
}

// Resolve readable resource update text using safe fallbacks
// 使用安全兜底方式获取资源更新时间文本
function getResourceMeta(item) {
  // Try common time-related fields from different possible data shapes
  // 尝试兼容不同数据结构里常见的时间字段
  return item?.updated || item?.date || item?.created_at || 'Recently updated'
}

// Resolve a readable resource category using safe fallbacks
// 使用安全兜底方式获取资源分类文本
function getResourceCategory(item) {
  // Try common category-like fields from different possible data shapes
  // 尝试兼容不同数据结构里常见的资源分类字段
  return item?.type || item?.category || item?.tag || 'General'
}

// Resolve a readable group name using safe fallbacks
// 使用安全兜底方式获取 group 名称
function getGroupName(group) {
  // Try common group title fields from different possible data shapes
  // 尝试兼容不同数据结构里常见的 group 名称字段
  return group?.name || group?.title || 'Untitled group'
}

// Resolve a safe member count from different possible field names
// 从不同可能的字段名中获取安全的成员数量
function getGroupMemberCount(group) {
  // Convert common member count fields into a number
  // 将常见成员数字段统一转换为 number
  return Number(group?.members || group?.memberCount || 0)
}

// Resolve a readable mentor or lead label for group cards
// 为 group 卡片生成可读的导师或负责人标签
function getGroupLead(group) {
  // Try common lead-like fields from different possible data shapes
  // 尝试兼容不同数据结构里常见的导师字段
  return group?.mentor || group?.lead || group?.supervisor || group?.owner || 'Mentor team'
}

// Build initials from text for avatar placeholders
// 从文本中生成首字母，用于头像占位
function getInitials(text) {
  // Return a generic fallback when text is missing
  // 当文本为空时返回通用兜底值
  if (!text) return 'GR'

  // Split text into words and take at most two initials
  // 将文本拆成单词并最多取两个首字母
  const words = String(text).trim().split(/\s+/).slice(0, 2)

  // Join uppercase initials for a simple avatar label
  // 拼接大写首字母，形成简洁头像标签
  return words.map(word => word[0]?.toUpperCase() || '').join('') || 'GR'
}

// Build a secondary badge label for group cards
// 为 group 卡片生成第二个辅助标签
function getGroupSecondaryLabel(group) {
  // Prefer track, category, or status when available
  // 优先使用 track、category 或 status 作为辅助标签
  const source = group?.track || group?.category || group?.status || 'BF'
  return String(source).slice(0, 2).toUpperCase()
}
</script>

<template>
  <!-- Main dashboard content wrapper -->
  <div class="content-area">
    <!-- Header section that introduces the dashboard context -->
    <!-- 顶部欢迎区，用于建立当前 dashboard 的上下文 -->
    <div class="dashboard-header dashboard-hero card" style="margin-bottom: 2rem;">
      <div class="dashboard-hero-main">
        <div class="dashboard-hero-copy">
          <h1>Welcome back, {{ displayName }}!</h1>

          <!-- Secondary context line with date, track, and role -->
          <!-- 次级上下文信息，展示日期、track 和角色 -->
          <p class="dashboard-subtext" style="color:#6c757d;">
            {{ currentDateText }} · Track: {{ displayTrack }} · Role: {{ roleLabel }}
          </p>

          <!-- Short role-aware dashboard description -->
          <!-- 按角色变化的 dashboard 说明文字 -->
          <p class="dashboard-hero-message">
            {{ heroMessage }}
          </p>

          <!-- Small highlight pills to make the first screen more informative -->
          <!-- 首屏信息标签，让用户快速感知当前状态 -->
          <div class="hero-highlight-wrap">
            <span
              v-for="item in headerHighlights"
              :key="item.key"
              class="status-pill"
            >
              {{ item.label }}
            </span>
          </div>
        </div>
      </div>
    </div>

    <!-- Role-aware summary widgets -->
    <!-- 按角色变化的概览卡片区域 -->
    <div class="grid grid-2 dashboard-summary-grid" style="margin-bottom: 2rem;">
      <!-- Render each widget based on the current role -->
      <!-- 根据当前角色渲染不同的概览卡片 -->
      <RouterLink
        v-for="item in summaryWidgets"
        :key="item.key"
        :to="item.to"
        class="widget widget-link"
      >
        <div class="widget-header">
          <!-- Widget title -->
          <!-- 卡片标题 -->
          <span class="widget-title">{{ item.title }}</span>

          <!-- Widget icon -->
          <!-- 卡片图标 -->
          <i :class="item.icon" :style="{ color: item.color }"></i>
        </div>

        <!-- Main numeric or headline value -->
        <!-- 主要数值或核心信息 -->
        <div class="widget-value">{{ item.value }}</div>

        <!-- Supporting explanation for the widget -->
        <!-- 卡片辅助说明文字 -->
        <div class="widget-subtext">{{ item.subtext }}</div>

        <!-- Footer link for deeper navigation -->
        <!-- 底部跳转入口，用于进入更详细页面 -->
        <div class="widget-footer">
          <span style="color: var(--dark-green);">
            Open →
          </span>
        </div>
      </RouterLink>
    </div>

    <!-- Quick action card to make the dashboard more action-oriented -->
    <!-- 快捷操作卡片，让 dashboard 更偏向“行动入口”而不是“目录入口” -->
    <div class="card" style="margin-bottom: 2rem;">
      <div class="card-header">
        <!-- Section title for quick actions -->
        <!-- 快捷操作区域标题 -->
        <h3 class="card-title">{{ quickActionsTitle }}</h3>

        <!-- Link to a relevant destination based on role -->
        <!-- 根据角色提供一个相关入口 -->
        <RouterLink
          :to="isPlatformAdmin ? '/groups' : '/events'"
          style="color: var(--dark-green);"
        >
          Open main area
        </RouterLink>
      </div>

      <!-- Action chips container -->
      <!-- 快捷操作按钮容器 -->
      <div class="actions-wrap">
        <!-- Render role-specific quick actions -->
        <!-- 渲染按角色区分的快捷操作 -->
        <RouterLink
          v-for="action in quickActions"
          :key="action.key"
          :to="action.to"
          class="chip-action"
        >
          {{ action.label }}
        </RouterLink>
      </div>
    </div>

    <!-- Mid-page dashboard content area -->
    <!-- 中部核心内容区域 -->
    <div class="grid grid-2" style="margin-bottom: 2rem;">
      <!-- Next event card for schedule awareness -->
      <!-- 下一场活动卡片，用于建立时间感和优先级 -->
      <div class="card">
        <div class="card-header">
          <!-- Event card title -->
          <!-- 活动卡片标题 -->
          <h3 class="card-title">{{ eventSectionTitle }}</h3>

          <!-- Link to the full event calendar -->
          <!-- 跳转到完整活动日历 -->
          <RouterLink to="/events" style="color: var(--dark-green);">View calendar</RouterLink>
        </div>

        <!-- Show the highlighted next event when available -->
        <!-- 当存在下一场活动时显示重点活动信息 -->
        <div v-if="nextEvent" class="event-detail">
          <!-- Event headline -->
          <!-- 活动主标题 -->
          <div class="event-title">{{ nextEvent.title }}</div>

          <!-- Event timing and mode -->
          <!-- 活动时间与形式 -->
          <div class="event-meta">
            {{ formatEventDate(nextEvent.date) }} · {{ nextEvent.time }} · {{ nextEvent.mode }}
          </div>

          <!-- Event location -->
          <!-- 活动地点 -->
          <div class="event-meta">Location: {{ nextEvent.location }}</div>

          <!-- Role-sensitive event action -->
          <!-- 按角色变化的活动操作入口 -->
          <div style="margin-top: 1rem;">
            <RouterLink to="/events" class="chip-action">
              {{ isPlatformAdmin ? 'Manage event' : isTeacher ? 'Open session details' : 'View event details' }}
            </RouterLink>
          </div>
        </div>

        <!-- Empty state for missing event data -->
        <!-- 当没有活动数据时显示空状态 -->
        <div v-else class="empty-hint">
          No upcoming event is available yet.
        </div>
      </div>

      <!-- Announcement preview card for stronger information visibility -->
      <!-- 公告预览卡片，增强信息可见性，而不仅仅显示数量 -->
      <div class="card">
        <div class="card-header">
          <!-- Announcements section title -->
          <!-- 公告区域标题 -->
          <h3 class="card-title">{{ announcementsSectionTitle }}</h3>

          <!-- Link to the full announcements page -->
          <!-- 跳转到全部公告页面 -->
          <RouterLink to="/announcements" style="color: var(--dark-green);">
            View all
          </RouterLink>
        </div>

        <!-- Show announcement preview items when available -->
        <!-- 当有公告数据时显示预览列表 -->
        <div v-if="announcementsPreview.length" class="list-stack">
          <RouterLink
            v-for="announcement in announcementsPreview"
            :key="announcement.id || getAnnouncementTitle(announcement)"
            to="/announcements"
            class="list-row"
          >
            <div class="list-row-icon">
              <i class="fas fa-bullhorn" style="color: var(--air-force-blue);"></i>
            </div>

            <div class="list-row-content">
              <div class="list-row-title">{{ getAnnouncementTitle(announcement) }}</div>
              <div class="list-row-meta">{{ getAnnouncementMeta(announcement) }}</div>
              <div class="list-row-description">{{ getAnnouncementSnippet(announcement) }}</div>
            </div>
          </RouterLink>
        </div>

        <!-- Empty state for missing announcement data -->
        <!-- 当没有公告数据时显示空状态 -->
        <div v-else class="empty-hint">
          No recent announcements are available yet.
        </div>
      </div>
    </div>

    <!-- Groups section for role-specific group visibility -->
    <!-- groups 区域，用于角色化展示 group 相关内容 -->
    <div class="card" style="margin-bottom: 2rem;">
      <div class="card-header">
        <!-- Dynamic groups section title -->
        <!-- 动态 groups 区域标题 -->
        <h3 class="card-title">{{ groupsSectionTitle }}</h3>

        <!-- Link to the full groups page -->
        <!-- 跳转到全部 groups 页面 -->
        <RouterLink to="/groups" style="color: var(--dark-green);">View all</RouterLink>
      </div>

      <!-- Show group cards when groups are available -->
      <!-- 当有 group 数据时显示 group 卡片 -->
      <div v-if="groupsPreview.length" class="grid grid-2">
        <RouterLink
          v-for="group in groupsPreview"
          :key="group.id || getGroupName(group)"
          :to="group.id ? '/groups/' + group.id : '/groups'"
          class="group-card group-card-link"
        >
          <div class="group-header">
            <!-- Group avatars are now generated dynamically rather than hard-coded -->
            <!-- group 头像现在改为动态生成，而不是写死占位 -->
            <div class="group-avatars">
              <div class="group-avatar">
                {{ getInitials(getGroupName(group)) }}
              </div>

              <div class="group-avatar" style="background-color: var(--mint-green);">
                {{ getGroupSecondaryLabel(group) }}
              </div>

              <div class="group-avatar" style="background-color: var(--air-force-blue);">
                +{{ Math.max(getGroupMemberCount(group) - 2, 0) }}
              </div>
            </div>

            <!-- Group textual information -->
            <!-- group 文本信息 -->
            <div class="group-info">
              <div class="group-name">{{ getGroupName(group) }}</div>
              <div class="group-meta">{{ getGroupMemberCount(group) }} members · Lead: {{ getGroupLead(group) }}</div>
            </div>
          </div>
        </RouterLink>
      </div>

      <!-- Empty state for missing group data -->
      <!-- 当没有 group 数据时显示空状态 -->
      <div v-else class="empty-hint">
        No group is available yet.
      </div>
    </div>

    <!-- Resource preview section for learning and support materials -->
    <!-- 资源预览区域，用于展示学习和支持材料 -->
    <div class="card" style="margin-bottom: 2rem;">
      <div class="card-header">
        <!-- Resource section title -->
        <!-- 资源区域标题 -->
        <h3 class="card-title">{{ resourcesSectionTitle }}</h3>

        <!-- Link to the full resources page -->
        <!-- 跳转到全部资源页面 -->
        <RouterLink to="/resources" style="color: var(--dark-green);">View all</RouterLink>
      </div>

      <!-- Resource card grid -->
      <!-- 资源卡片网格 -->
      <div v-if="resourcesPreview.length" class="resource-grid">
        <RouterLink
          v-for="resource in resourcesPreview"
          :key="resource.id || getResourceTitle(resource)"
          :to="resource.id ? '/resources/' + resource.id : '/resources'"
          class="resource-card resource-card-link"
        >
          <div class="resource-icon">
            <i :class="getResourceIcon(resource.type)"></i>
          </div>

          <div class="resource-content">
            <div class="resource-title">{{ getResourceTitle(resource) }}</div>
            <div class="resource-meta">{{ getResourceCategory(resource) }} · Updated {{ getResourceMeta(resource) }}</div>
          </div>
        </RouterLink>
      </div>

      <!-- Empty state for missing resource data -->
      <!-- 当没有资源数据时显示空状态 -->
      <div v-else class="empty-hint">
        No resource is available yet.
      </div>
    </div>

    <!-- Role-specific workflow or checklist section -->
    <!-- 角色专属工作流或 checklist 区域 -->
    <div class="card" style="margin-bottom: 2rem;">
      <div class="card-header">
        <!-- Dynamic workflow section title -->
        <!-- 动态工作流区域标题 -->
        <h3 class="card-title">{{ workflowSectionTitle }}</h3>

        <!-- Link to a likely related page -->
        <!-- 跳转到更相关的功能页面 -->
        <RouterLink
          :to="isPlatformAdmin ? '/groups' : isTeacher ? '/events' : '/resources'"
          style="color: var(--dark-green);"
        >
          Open
        </RouterLink>
      </div>

      <!-- List of workflow or next-step items -->
      <!-- 工作流或下一步事项列表 -->
      <div class="list-stack">
        <RouterLink
          v-for="item in workflowItems"
          :key="item.key"
          :to="item.to"
          class="list-row"
        >
          <div class="list-row-icon">
            <i class="fas fa-chevron-right" style="color: var(--dark-green);"></i>
          </div>

          <div class="list-row-content">
            <div class="list-row-title">{{ item.title }}</div>
            <div class="list-row-meta">{{ item.meta }}</div>
          </div>
        </RouterLink>
      </div>
    </div>

    <!-- Admin-only operational insight area -->
    <!-- 仅管理员可见的运营摘要区域 -->
    <div v-if="isPlatformAdmin" class="card">
      <div class="card-header">
        <h3 class="card-title">Operational Insights</h3>
        <RouterLink to="/groups" style="color: var(--dark-green);">Open admin tools</RouterLink>
      </div>

      <div class="grid grid-3 admin-insights-grid">
        <RouterLink
          v-for="item in adminInsightCards"
          :key="item.key"
          :to="item.to"
          class="admin-mini-card"
        >
          <div class="admin-mini-card-header">
            <span class="admin-mini-card-title">{{ item.title }}</span>
            <i :class="item.icon" style="color: var(--dark-green);"></i>
          </div>
          <div class="admin-mini-card-value">{{ item.value }}</div>
          <div class="admin-mini-card-meta">{{ item.meta }}</div>
        </RouterLink>
      </div>
    </div>
  </div>
</template>

<style scoped>
/* Keep the new dashboard helpers visually close to the existing style system */
/* 让新增的 dashboard 辅助样式尽量贴近你们现有的样式体系 */

.dashboard-subtext {
  margin-top: 0.4rem;
}

.dashboard-hero {
  padding: 1.5rem;
}

.dashboard-hero-main {
  display: flex;
  justify-content: space-between;
  align-items: flex-start;
  gap: 1.5rem;
  flex-wrap: wrap;
}

.dashboard-hero-copy {
  min-width: 0;
  flex: 1 1 520px;
}

.dashboard-hero-message {
  margin-top: 0.85rem;
  color: #4f5d60;
  line-height: 1.6;
  max-width: 820px;
}

.dashboard-hero-actions {
  display: flex;
  flex-wrap: wrap;
  gap: 0.75rem;
  align-items: center;
}

.hero-highlight-wrap {
  display: flex;
  flex-wrap: wrap;
  gap: 0.65rem;
  margin-top: 1rem;
}

.status-pill {
  display: inline-flex;
  align-items: center;
  padding: 0.35rem 0.7rem;
  border-radius: 999px;
  background-color: var(--light-green);
  color: var(--dark-green);
  font-size: 0.8125rem;
  font-weight: 600;
  border: 1px solid rgba(0, 0, 0, 0.06);
}

.dashboard-summary-grid {
  gap: 1rem;
}

.widget-link {
  display: block;
  text-decoration: none;
  color: inherit;
  transition: transform 0.2s ease, box-shadow 0.2s ease;
}

.widget-link:hover {
  transform: translateY(-2px);
  box-shadow: 0 4px 12px var(--shadow);
}

.widget-subtext {
  margin-top: 0.5rem;
  color: #6c757d;
  font-size: 0.92rem;
  line-height: 1.45;
}

.actions-wrap {
  display: flex;
  flex-wrap: wrap;
  gap: 0.75rem;
}

.event-detail {
  display: flex;
  flex-direction: column;
  gap: 0.45rem;
}

.event-title {
  font-size: 1.05rem;
  font-weight: 700;
  color: var(--dark-green);
}

.event-meta {
  color: #6c757d;
  line-height: 1.45;
}

.list-stack {
  display: flex;
  flex-direction: column;
  gap: 0.85rem;
}

.list-row {
  display: flex;
  align-items: flex-start;
  gap: 0.85rem;
  text-decoration: none;
  color: inherit;
}

.list-row-icon {
  width: 1.25rem;
  flex-shrink: 0;
  display: flex;
  align-items: center;
  justify-content: center;
  margin-top: 0.1rem;
}

.list-row-content {
  min-width: 0;
}

.list-row-title {
  font-weight: 600;
  color: var(--dark-green);
  line-height: 1.4;
}

.list-row-meta {
  margin-top: 0.2rem;
  color: #6c757d;
  font-size: 0.92rem;
  line-height: 1.45;
}

.list-row-description {
  margin-top: 0.25rem;
  color: #6c757d;
  font-size: 0.9rem;
  line-height: 1.5;
}

.group-card-link,
.resource-card-link {
  text-decoration: none;
  color: inherit;
  display: block;
}

.group-meta {
  margin-top: 0.25rem;
  color: #6c757d;
  font-size: 0.92rem;
}

.empty-hint {
  color: #6c757d;
  line-height: 1.5;
}

/* Capsule-style action button prepared for quick operations */
/* 用于快捷操作的胶囊按钮样式 */
.chip-action {
  display: inline-flex;
  align-items: center;
  gap: 0.35rem;
  padding: 0.35rem 0.65rem;
  font-size: 0.8125rem;
  font-weight: 600;
  line-height: 1;
  border-radius: 999px;
  background-color: var(--light-green);
  color: var(--dark-green);
  border: 1px solid var(--dark-green);
  cursor: pointer;
  transition: all 0.2s ease;
  text-decoration: none;
}

/* Hover effect for action chips */
/* 胶囊按钮的悬停效果 */
.chip-action:hover {
  background-color: var(--dark-green);
  color: var(--white);
  transform: translateY(-1px);
  box-shadow: 0 2px 4px var(--shadow);
}

/* Secondary chip variant for less dominant actions */
/* 次级胶囊按钮样式，用于弱化的辅助操作 */
.chip-action-secondary {
  background-color: var(--white);
  color: var(--dark-green);
}

/* Compact admin insight area so admin-only information does not dominate the entire page */
/* 紧凑型管理员摘要区，避免管理信息占满整页 */
.admin-insights-grid {
  gap: 1rem;
}

.admin-mini-card {
  display: block;
  text-decoration: none;
  color: inherit;
  padding: 1rem;
  border-radius: 14px;
  background-color: var(--light-green);
  border: 1px solid rgba(0, 0, 0, 0.06);
  transition: transform 0.2s ease, box-shadow 0.2s ease;
}

.admin-mini-card:hover {
  transform: translateY(-2px);
  box-shadow: 0 4px 12px var(--shadow);
}

.admin-mini-card-header {
  display: flex;
  justify-content: space-between;
  align-items: center;
  gap: 0.75rem;
}

.admin-mini-card-title {
  font-size: 0.95rem;
  font-weight: 600;
  color: var(--dark-green);
}

.admin-mini-card-value {
  margin-top: 0.75rem;
  font-size: 1.6rem;
  font-weight: 700;
  color: var(--dark-green);
}

.admin-mini-card-meta {
  margin-top: 0.4rem;
  font-size: 0.9rem;
  line-height: 1.5;
  color: #6c757d;
}
</style>