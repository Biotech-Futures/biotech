<template>
  <div
    class="content-area group-detail"
    :data-active="activeTab"
  >
    <!-- Header -->
    <div class="group-hero-card">
      <div class="gd-head">
        <div class="gd-head-left">
          <div class="group-avatars">
            <div class="group-avatar" style="width:48px;height:48px;font-size:1.1rem;">{{ groupInitials }}</div>
          </div>
          <div>
            <h2 class="gd-title">{{ group.name }}</h2>
            <p class="gd-subtitle">{{ groupSubtitle }}</p>
            <div v-if="groupMetaItems.length" class="gd-meta-row">
              <span v-for="item in groupMetaItems" :key="item">{{ item }}</span>
            </div>
          </div>
        </div>
        <div class="gd-head-actions">
          <label class="group-switcher" for="group-switcher">
            <span>Group</span>
            <select
              id="group-switcher"
              :value="backendGroupId"
              :disabled="isLoadingGroupOptions || availableGroups.length <= 1"
              @change="switchGroup"
            >
              <option v-if="isLoadingGroupOptions" value="">Loading groups...</option>
              <option
                v-for="option in availableGroups"
                :key="option.id"
                :value="option.id"
              >
                {{ option.memberCount ? `${option.name} (${option.memberCount})` : option.name }}
              </option>
            </select>
          </label>
          <span v-if="groupOptionsError" class="group-switcher-error">{{ groupOptionsError }}</span>
        </div>
      </div>
    </div>

    <!-- Mobile tabs (hidden on desktop) -->
    <nav class="mobile-tabs">
      <button
        class="tab-btn"
        :class="{ active: activeTab === 'tasks' }"
        @click="activeTab = 'tasks'"
      >
        Tasks
      </button>
      <button
        class="tab-btn"
        :class="{ active: activeTab === 'discussion' }"
        @click="activeTab = 'discussion'"
      >
        Discussion
      </button>
    </nav>

    <!-- Desktop: two columns; mobile: single column via tabs -->
    <div class="split" :data-active="activeTab">
      <!-- Left column: Tasks -->
      <section class="pane pane--tasks card">
        <div class="card-header">
          <h3 class="card-title">Tasks</h3>
          <div class="task-header-actions">
            <button
              v-if="canCreateGroupTasks"
              type="button"
              class="btn btn-primary btn-sm"
              :disabled="!backendGroupId || isLoadingTasks"
              title="Create a shared group task"
              @click="createTask('group')"
            >
              <i class="fas fa-plus"></i> Group Task
            </button>
            <button
              v-if="canCreateIndividualTasks"
              type="button"
              class="btn btn-outline btn-sm"
              :disabled="!backendGroupId || isLoadingTasks"
              title="Create an individual task"
              @click="createTask('individual')"
            >
              <i class="fas fa-user-plus"></i> Individual Task
            </button>
          </div>
        </div>
        <div class="card-content tasks-content">
          <div v-if="taskError" class="chat-alert" style="margin-bottom:1rem;">
            {{ taskError }}
          </div>
          <div v-if="isLoadingTasks" class="chat-alert" style="margin-bottom:1rem;">
            Loading tasks...
          </div>

          <div
            v-for="section in taskSections"
            :key="section.key"
            class="task-section"
          >
            <div class="task-section-header">
              <div class="task-section-title">
                <i :class="section.icon"></i>
                {{ section.title }}
              </div>
              <div class="task-section-status">
                {{ section.completed }}/{{ section.total }} Completed
              </div>
            </div>
            <div class="task-list">
              <div
                v-for="row in section.rows"
                :key="row.task.id"
                class="task-item"
                :class="{ 'is-subtask': row.depth > 0 }"
                :style="{ paddingLeft: `${0.85 + row.depth * 1.35}rem` }"
              >
                <button
                  type="button"
                  :class="['task-checkbox', { checked: row.task.completed }]"
                  :disabled="isUpdatingTask(row.task.id) || (auth.isStudent && row.task.taskType === 'group')"
                  :title="auth.isStudent && row.task.taskType === 'group' ? 'Students can view group task status only' : 'Toggle task status'"
                  @click="toggleTask(row.task)"
                />
                <div class="task-body">
                  <div :class="['task-label', { completed: row.task.completed }]">{{ row.task.name }}</div>
                  <div v-if="row.task.description" class="task-description">{{ row.task.description }}</div>
                  <div class="task-meta">
                    <span v-if="row.task.dueDate"><i class="fas fa-calendar"></i> {{ formatDate(row.task.dueDate) }}</span>
                    <span v-if="row.task.status"><i class="fas fa-circle"></i> {{ formatTaskStatus(row.task.status) }}</span>
                    <span v-if="row.task.assignedUser"><i class="fas fa-user"></i> User {{ row.task.assignedUser }}</span>
                    <span v-if="row.task.creatorRole"><i class="fas fa-id-badge"></i> {{ formatTaskStatus(row.task.creatorRole) }}</span>
                  </div>
                </div>
                <button
                  type="button"
                  class="btn btn-outline btn-sm add-subtask-btn"
                  :disabled="isLoadingTasks"
                  title="Add a sub-task"
                  @click="createTask(row.task.taskType, row.task)"
                >
                  <i class="fas fa-plus"></i>
                  Sub-task
                </button>
              </div>

              <div v-if="!section.rows.length" class="task-empty-state">
                No {{ section.title.toLowerCase() }} are available yet.
              </div>
            </div>
          </div>
        </div>
      </section>

      <!-- Right column: Discussion -->
      <section class="pane pane--discussion">
        <div class="chat-container">
          <!-- Discussion header -->
          <div class="chat-header">
            <h3 style="margin:0;">Discussion Board</h3>
            <span class="chat-status">
              <template v-if="isLoadingMessages">Loading...</template>
              <template v-else-if="wsConnectionState === 'connected'">Live</template>
              <template v-else>Offline</template>
            </span>
          </div>

          <div v-if="chatError" class="chat-alert">
            {{ chatError }}
          </div>

          <div class="chat-messages" ref="msgList">
            <div
              v-for="message in messages"
              :key="message.id"
              :class="['message', { own: message.isOwn }]"
            >
              <div class="message-avatar">{{ getInitials(message.author) }}</div>
              <div class="message-content">
                <div class="message-header">
                  <span class="message-author">{{ message.author }}</span>
                  <span class="message-meta">
                    <span v-if="message.editedAt" class="message-edited">edited</span>
                    <span class="message-date">{{ formatDate(message.date) }}</span>
                    <span class="message-time">{{ message.time }}</span>
                  </span>
                </div>
                <img
                  v-if="message.messageType === 'gif' && message.gifUrl"
                  :src="message.gifUrl"
                  :alt="message.text || 'GIF message'"
                  class="message-gif"
                />
                <div v-else class="message-text">{{ message.text }}</div>

                <div v-if="message.attachments?.length" class="message-attachments">
                  <a
                    v-for="attachment in message.attachments"
                    :key="attachment.id || attachment.attachment_filename"
                    href="#"
                    class="attachment-chip"
                    @click.prevent
                  >
                    <i class="fas fa-paperclip"></i>
                    {{ getAttachmentLabel(attachment) }}
                  </a>
                </div>

                <div v-if="message.preview?.title" class="message-preview">
                  <strong>{{ message.preview.title }}</strong>
                </div>

                <div class="message-reactions">
                  <button
                    v-for="emoji in CHAT_REACTION_OPTIONS"
                    :key="`${message.id}-${emoji}`"
                  type="button"
                  class="reaction-btn"
                  :disabled="!supportsMessageReactions"
                  :title="supportsMessageReactions ? 'Add reaction' : 'Reactions are not available yet'"
                  @click="reactToMessage(message.id, emoji)"
                >
                  <span>{{ emoji }}</span>
                  <span v-if="message.reactions?.[emoji]" class="reaction-count">{{ message.reactions[emoji] }}</span>
                </button>
                </div>
              </div>
            </div>
          </div>

          <div v-if="typingIndicatorText" class="typing-indicator">
            {{ typingIndicatorText }}
          </div>

          <div class="chat-input">
            <div v-if="supportsGifs && showGifPanel" class="gif-panel">
              <div class="gif-panel-header">
                <input
                  v-model.trim="gifQuery"
                  type="text"
                  class="gif-search-input"
                  placeholder="Search GIFs"
                  @keydown.enter.prevent="searchGifs"
                />
                <button type="button" class="btn btn-outline btn-sm" @click="searchGifs">Search</button>
              </div>
              <div v-if="gifError" class="gif-status">{{ gifError }}</div>
              <div class="gif-grid">
                <button
                  v-for="gif in gifResults"
                  :key="gif.id"
                  type="button"
                  class="gif-card"
                  @click="sendGifMessage(gif)"
                >
                  <img :src="gif.previewUrl || gif.url" :alt="gif.title" />
                  <span>{{ gif.title }}</span>
                </button>
              </div>
              <div v-if="isLoadingGifs" class="gif-status">Loading GIFs...</div>
            </div>

            <div class="chat-input-group">
              <textarea
                ref="composer"
                v-model="newMessage"
                class="chat-input-field"
                placeholder="Type your message..."
                rows="2"
                @keydown.enter.exact.prevent="sendMessage"
                @input="handleComposerInput"
              ></textarea>
              <div class="chat-actions">
                <button
                  class="chat-btn"
                  type="button"
                  :title="supportsGifs ? 'GIF picker' : 'GIF search is not available yet'"
                  :disabled="!supportsGifs"
                  @click="toggleGifPanel"
                >
                  <i class="fas fa-image"></i>
                </button>
                <button
                  class="chat-btn"
                  type="button"
                  title="Attach file"
                  :disabled="isUploadingFile || !supportsAttachments"
                  @click="openFilePicker"
                >
                  <i class="fas fa-paperclip"></i>
                </button>
                <input ref="fileInputRef" type="file" class="hidden-file-input" @change="uploadAttachment" />
                <button class="chat-btn" :disabled="isSendingMessage || !newMessage.trim()" @click="sendMessage" title="Send">
                  <i class="fas fa-paper-plane"></i>
                </button>
              </div>
            </div>
          </div>
        </div>
      </section>
    </div>
  </div>
</template>

<script setup>
import { ref, onMounted, onBeforeUnmount, nextTick, computed, watch } from 'vue'
import { useRoute, useRouter } from 'vue-router'
import { useAuthStore } from '@/stores/auth'
import { buildSessionHeaders, ensureCsrfCookie } from '@/utils/csrf'
import { apiErrorFromResponse } from '@/utils/apiError'

const route = useRoute()
const router = useRouter()
const auth = useAuthStore()
const API_BASE_URL = import.meta.env.VITE_API_BASE_URL || 'http://localhost:8000'
const supportsGifs = false
const supportsAttachments = false
const supportsMessageReactions = false
const CHAT_REACTION_OPTIONS = ['👍', '❤️', '🎉']
const routeGroupId = computed(() => route.params.id ? String(route.params.id) : '')
const group = ref({
  id: routeGroupId.value || null,
  name: routeGroupId.value ? `Group ${routeGroupId.value}` : 'Group',
  members: 0,
  createdAt: ''
})
const groupMemberships = ref([])
const isLoadingMembers = ref(false)
const membersError = ref('')
const availableGroups = ref([])
const isLoadingGroupOptions = ref(false)
const groupOptionsError = ref('')

// Active mobile tab
const activeTab = ref('tasks')

// Live task state
const tasks = ref([])
const isLoadingTasks = ref(false)
const taskError = ref('')
const updatingTaskIds = ref(new Set())

const messages = ref([])

const newMessage = ref('')
const composer = ref(null)
const msgList = ref(null)
const fileInputRef = ref(null)
const isLoadingMessages = ref(false)
const isSendingMessage = ref(false)
const isUploadingFile = ref(false)
const isLoadingGifs = ref(false)
const chatError = ref('')
const gifError = ref('')
const showGifPanel = ref(false)
const gifQuery = ref('')
const gifResults = ref([])
const typingUsers = ref([])
const wsConnectionState = ref('offline')

let chatSocket = null
let typingStopTimer = null
let hasSentTypingStart = false

const getInitials = (name) => String(name || 'U').split(' ').map(n => n[0]).join('').toUpperCase()

const formatDate = (d) => {
  const date = new Date(d)
  if (Number.isNaN(date.getTime())) return d
  return date.toLocaleDateString('en-AU', { year: 'numeric', month: 'short', day: 'numeric' })
}

const formatTime = (value) => {
  const date = new Date(value)
  if (Number.isNaN(date.getTime())) return ''
  return date.toLocaleTimeString([], { hour: '2-digit', minute: '2-digit' })
}

const formatTaskStatus = (value) => {
  const label = String(value || '').replace(/_/g, ' ').trim()
  return label ? label.charAt(0).toUpperCase() + label.slice(1) : ''
}

const groupInitials = computed(() => {
  const initials = getInitials(group.value?.name)
  return initials.slice(0, 2) || 'G'
})

const groupSubtitle = computed(() => {
  const memberCount = Number(group.value?.members || 0)
  const memberLabel = memberCount === 1 ? '1 member' : `${memberCount} members`
  const createdLabel = group.value?.createdAt ? formatDate(group.value.createdAt) : 'unknown date'
  return `${memberLabel} - Group since ${createdLabel}`
})

const groupMetaItems = computed(() => {
  const mentorIds = groupMemberships.value
    .filter(item => String(item.role || '').toLowerCase().includes('mentor'))
    .map(item => item.userId)
    .filter(Boolean)
  const items = []

  if (mentorIds.length) {
    items.push(`Mentor: ${mentorIds.map(id => `User ${id}`).join(', ')}`)
  }
  if (isLoadingMembers.value) {
    items.push('Loading members...')
  } else if (membersError.value) {
    items.push(membersError.value)
  }

  return items
})

const extractCollectionItems = (data) => {
  if (Array.isArray(data)) return data
  if (Array.isArray(data?.results)) return data.results
  if (Array.isArray(data?.items)) return data.items
  return []
}

const buildChatMessageCollectionUrls = (groupId, suffix = '') => {
  return [
    `${API_BASE_URL}/api/v1/chat/groups/${groupId}/messages/${suffix}`,
    `${API_BASE_URL}/chat/groups/${groupId}/messages/${suffix}`
  ]
}

const buildChatUploadUrls = (groupId) => {
  return [
    `${API_BASE_URL}/api/v1/chat/groups/${groupId}/messages/upload/`,
    `${API_BASE_URL}/chat/groups/${groupId}/messages/upload/`
  ]
}

const buildChatReactionUrls = (groupId, messageId) => {
  return [
    `${API_BASE_URL}/api/v1/chat/groups/${groupId}/messages/${messageId}/react/`,
    `${API_BASE_URL}/chat/groups/${groupId}/messages/${messageId}/react/`
  ]
}

const buildGifSearchUrls = (query) => {
  const encoded = encodeURIComponent(query)
  return [
    `${API_BASE_URL}/api/v1/chat/gifs/search?q=${encoded}`,
    `${API_BASE_URL}/chat/gifs/search?q=${encoded}`
  ]
}

const buildGifTrendingUrls = () => {
  return [
    `${API_BASE_URL}/api/v1/chat/gifs/trending`,
    `${API_BASE_URL}/chat/gifs/trending`
  ]
}

const buildChatWebSocketUrl = (groupId) => {
  try {
    const apiUrl = new URL(API_BASE_URL)
    const protocol = apiUrl.protocol === 'https:' ? 'wss:' : 'ws:'
    return `${protocol}//${apiUrl.host}/ws/chat/groups/${groupId}/`
  } catch {
    const protocol = window.location.protocol === 'https:' ? 'wss:' : 'ws:'
    return `${protocol}//${window.location.host}/ws/chat/groups/${groupId}/`
  }
}

const requestJson = async (url, options = {}) => {
  const isFormData = options.body instanceof FormData
  const method = String(options.method || 'GET').toUpperCase()
  const shouldIncludeCSRF = !['GET', 'HEAD', 'OPTIONS'].includes(method)

  if (shouldIncludeCSRF) {
    const csrfReady = await ensureCsrfCookie(API_BASE_URL)
    if (!csrfReady) {
      throw new Error('Could not initialize a secure session. Please refresh and try again.')
    }
  }

  const response = await fetch(url, {
    credentials: 'include',
    ...options,
    headers: buildSessionHeaders({
      includeCSRF: shouldIncludeCSRF,
      isFormData,
      headers: {
        Accept: 'application/json',
        ...(options.headers || {})
      }
    })
  })

  if (!response.ok) {
    throw await apiErrorFromResponse(response)
  }

  const text = await response.text()
  let data = null
  try {
    data = text ? JSON.parse(text) : null
  } catch {
    data = null
  }

  return data
}

const requestJsonFirst = async (urls, options = {}) => {
  let lastError = null

  for (const url of urls) {
    try {
      return await requestJson(url, options)
    } catch (error) {
      lastError = error
    }
  }

  if (lastError) {
    throw lastError
  }

  return null
}

const normalizeGroup = (item) => {
  return {
    ...group.value,
    ...item,
    id: item?.id,
    name: item?.group_name || item?.name || item?.title || group.value?.name || 'Untitled group',
    members: Number(item?.member_count ?? item?.memberCount ?? item?.members ?? group.value?.members ?? 0),
    createdAt: item?.created_at || item?.createdAt || ''
  }
}

const normalizeMembership = (item) => ({
  id: item?.id,
  groupId: item?.group,
  userId: item?.user,
  role: item?.membership_role || '',
  joinedAt: item?.joined_at || '',
  leftAt: item?.left_at || ''
})

const normalizeGroupOption = (item, memberCount = 0) => ({
  id: String(item?.id || ''),
  name: item?.group_name || item?.name || item?.title || (item?.id ? `Group ${item.id}` : 'Untitled group'),
  memberCount: Number(memberCount || 0),
  createdAt: item?.created_at || item?.createdAt || ''
})

const ensureAuthUser = async () => {
  if (auth.user?.id) return

  try {
    await auth.fetchUserData?.()
  } catch {
    // Keep the current page usable; group option loading will show its own fallback.
  }
}

const loadGroupOptions = async () => {
  isLoadingGroupOptions.value = true
  groupOptionsError.value = ''

  try {
    const [groupsData, membershipsData] = await Promise.all([
      requestJson(`${API_BASE_URL}/groups/groups/?page_size=100`),
      requestJson(`${API_BASE_URL}/groups/group-members/?page_size=100`)
    ])
    const groupItems = extractCollectionItems(groupsData)
    const memberships = extractCollectionItems(membershipsData)
      .map(normalizeMembership)
      .filter(item => !item.leftAt)
    const currentUserId = Number(auth.user?.id || 0)
    const visibleGroupIds = auth.isAdmin
      ? null
      : new Set(
          memberships
            .filter(item => currentUserId > 0 && String(item.userId) === String(currentUserId))
            .map(item => String(item.groupId))
        )
    const memberCounts = new Map()

    memberships.forEach((item) => {
      const groupId = String(item.groupId || '')
      if (!groupId) return
      memberCounts.set(groupId, Number(memberCounts.get(groupId) || 0) + 1)
    })

    let options = groupItems
      .filter(item => {
        const groupId = String(item?.id || '')
        return groupId && (visibleGroupIds === null || visibleGroupIds.has(groupId))
      })
      .map(item => normalizeGroupOption(item, memberCounts.get(String(item?.id || ''))))
      .sort((a, b) => a.name.localeCompare(b.name))

    const currentGroupId = getBackendGroupId() || routeGroupId.value
    if (currentGroupId && !options.some(option => String(option.id) === String(currentGroupId))) {
      options = [
        normalizeGroupOption({
          id: currentGroupId,
          group_name: group.value?.name || `Group ${currentGroupId}`,
          created_at: group.value?.createdAt
        }, group.value?.members),
        ...options
      ]
    }

    availableGroups.value = options
    if (!options.length) {
      groupOptionsError.value = auth.isAdmin ? 'No groups available' : 'No groups assigned'
    }
  } catch {
    const currentGroupId = getBackendGroupId() || routeGroupId.value
    availableGroups.value = currentGroupId
      ? [normalizeGroupOption({ id: currentGroupId, group_name: group.value?.name || `Group ${currentGroupId}` }, group.value?.members)]
      : []
    groupOptionsError.value = 'Group list unavailable'
  } finally {
    isLoadingGroupOptions.value = false
  }
}

const loadGroupMembers = async () => {
  const currentGroupId = getBackendGroupId()
  if (!currentGroupId) {
    groupMemberships.value = []
    membersError.value = ''
    return
  }

  isLoadingMembers.value = true
  membersError.value = ''

  try {
    const data = await requestJson(`${API_BASE_URL}/groups/group-members/by-group/${currentGroupId}/`)
    const activeMemberships = extractCollectionItems(data)
      .map(normalizeMembership)
      .filter(item => !item.leftAt)

    groupMemberships.value = activeMemberships
    group.value = {
      ...group.value,
      members: activeMemberships.length
    }
  } catch {
    groupMemberships.value = []
    membersError.value = 'Members unavailable'
  } finally {
    isLoadingMembers.value = false
  }
}

const normalizeReactionMap = (reactions) => {
  if (!reactions || typeof reactions !== 'object' || Array.isArray(reactions)) {
    return {}
  }

  return Object.fromEntries(
    Object.entries(reactions)
      .map(([emoji, count]) => [emoji, Number(count) || 0])
      .filter(([, count]) => count > 0)
  )
}

const normalizeGifResults = (data) => {
  const items = extractCollectionItems(data)
  const normalized = items.map((item, index) => ({
    id: item?.id || item?.media_id || item?.url || `gif-${index}`,
    url: item?.gif_url || item?.url || item?.media?.gif?.url || item?.media_formats?.gif?.url || item?.itemurl || '',
    previewUrl: item?.preview_url || item?.preview || item?.media_formats?.tinygif?.url || item?.media_formats?.nanogif?.url || item?.gif_url || item?.url || '',
    title: item?.title || item?.content_description || 'GIF'
  })).filter(item => item.url)

  return normalized
}

const loadGroup = async () => {
  try {
    const currentRouteGroupId = routeGroupId.value
    if (currentRouteGroupId) {
      const data = await requestJson(`${API_BASE_URL}/groups/groups/${currentRouteGroupId}/`)
      group.value = normalizeGroup(data)
      return
    }

    const data = await requestJson(`${API_BASE_URL}/groups/groups/?page_size=1`)
    const firstGroup = extractCollectionItems(data)[0]
    if (firstGroup) {
      group.value = normalizeGroup(firstGroup)
    }
  } catch (error) {
    group.value = {
      id: routeGroupId.value || null,
      name: routeGroupId.value ? `Group ${routeGroupId.value}` : 'Group unavailable',
      members: 0,
      createdAt: ''
    }
  }
}

const normalizeTask = (task) => ({
  id: task?.id,
  name: task?.name || task?.task_name || 'Untitled task',
  description: task?.description || task?.task_description || '',
  dueDate: task?.due_date || '',
  status: task?.status || '',
  completed: task?.completed === true || String(task?.status || '').toLowerCase() === 'done',
  parent: task?.parent ?? null,
  taskType: task?.task_type || 'group',
  group: task?.group ?? null,
  assignedUser: task?.assigned_user ?? null,
  creatorRole: task?.creator_role || '',
  createdBy: task?.created_by || null
})

const groupMemberUserIds = computed(() => new Set(
  groupMemberships.value
    .filter(item => !item.leftAt)
    .map(item => Number(item.userId))
    .filter(Number.isFinite)
))

const isTaskRelevantToCurrentGroup = (task) => {
  const currentGroupId = getBackendGroupId()
  if (!currentGroupId) return false

  if (task.taskType === 'group') {
    return String(task.group) === String(currentGroupId)
  }

  return groupMemberUserIds.value.has(Number(task.assignedUser))
}

const buildTaskRows = (items) => {
  const byId = new Map()
  const childrenByParent = new Map()

  items.forEach((task) => {
    byId.set(Number(task.id), task)
  })

  items.forEach((task) => {
    const parentId = Number(task.parent)
    if (!parentId || !byId.has(parentId)) return
    if (!childrenByParent.has(parentId)) childrenByParent.set(parentId, [])
    childrenByParent.get(parentId).push(task)
  })

  const roots = items.filter(task => {
    const parentId = Number(task.parent)
    return !parentId || !byId.has(parentId)
  })

  const rows = []
  const appendRows = (task, depth = 0) => {
    rows.push({ task, depth })
    ;(childrenByParent.get(Number(task.id)) || []).forEach(child => appendRows(child, depth + 1))
  }

  roots.forEach(task => appendRows(task))
  return rows
}

const createTaskSection = (key, title, icon, sectionTasks) => {
  const rows = buildTaskRows(sectionTasks)
  const total = sectionTasks.length
  const completed = sectionTasks.filter(task => task.completed).length

  return {
    key,
    title,
    icon,
    rows,
    total,
    completed
  }
}

const taskSections = computed(() => {
  const relevantTasks = tasks.value.filter(isTaskRelevantToCurrentGroup)
  const groupTasks = relevantTasks.filter(task => task.taskType === 'group')
  const individualTasks = relevantTasks.filter(task => task.taskType === 'individual')

  return [
    createTaskSection('group', 'Group Tasks', 'fas fa-users', groupTasks),
    createTaskSection('individual', 'Individual Tasks', 'fas fa-user-check', individualTasks)
  ]
})

const canCreateGroupTasks = computed(() => auth.isMentor || auth.isSupervisor)
const canCreateIndividualTasks = computed(() => auth.isStudent || auth.isMentor || auth.isSupervisor)

const isUpdatingTask = (taskId) => updatingTaskIds.value.has(Number(taskId))

const setTaskUpdating = (taskId, value) => {
  const next = new Set(updatingTaskIds.value)
  const id = Number(taskId)
  if (value) next.add(id)
  else next.delete(id)
  updatingTaskIds.value = next
}

const loadTasks = async () => {
  const currentGroupId = getBackendGroupId()
  if (!currentGroupId) {
    tasks.value = []
    taskError.value = 'Live task data needs a backend numeric group id.'
    return
  }

  isLoadingTasks.value = true
  taskError.value = ''

  try {
    const data = await requestJson(`${API_BASE_URL}/api/v1/tasks/?page_size=100&deleted=false`)
    tasks.value = extractCollectionItems(data).map(normalizeTask)
    if (!tasks.value.filter(isTaskRelevantToCurrentGroup).length) {
      taskError.value = 'No tasks have been created for this group yet.'
    }
  } catch (error) {
    tasks.value = []
    taskError.value = error instanceof Error ? error.message : 'Task data could not be loaded.'
  } finally {
    isLoadingTasks.value = false
  }
}

const normalizeMessage = (item) => {
  const raw = item?.message ? item.message : item
  const sentAt = raw?.sent_at || raw?.sent_datetime || raw?.created_at || new Date().toISOString()
  const senderId = Number(raw?.sender_user || raw?.sender_id || raw?.sender_user_id || 0)
  const currentUserId = Number(auth.user?.id || 0)
  const isOwn = raw?.isOwn === true || (currentUserId > 0 && senderId === currentUserId)
  const messageText = raw?.message_text || raw?.text || ''
  const messageType = raw?.message_type || 'text'
  const attachments = [
    ...(Array.isArray(raw?.attachments) ? raw.attachments : []),
    ...(Array.isArray(raw?.resources) ? raw.resources : [])
  ]
  const author = isOwn
    ? 'You'
    : (raw?.sender_name || raw?.author || (senderId ? `User ${senderId}` : 'Team member'))

  return {
    id: raw?.id || `${senderId}-${sentAt}`,
    author,
    text: messageText,
    time: formatTime(sentAt),
    date: sentAt,
    isOwn,
    messageType,
    gifUrl: messageType === 'gif' ? messageText : '',
    attachments,
    reactions: normalizeReactionMap(raw?.reactions),
    preview: raw?.preview || null,
    editedAt: raw?.edited_at || null,
    readBy: Array.isArray(raw?.read_by) ? raw.read_by : [],
    isLocalOnly: Boolean(raw?.isLocalOnly)
  }
}

const getAttachmentLabel = (attachment) => {
  return attachment?.attachment_filename ||
    attachment?.resource_name ||
    attachment?.name ||
    (attachment?.resource_id ? `Resource ${attachment.resource_id}` : 'Attachment')
}

const getBackendGroupId = () => {
  const id = group.value?.id || routeGroupId.value
  return /^\d+$/.test(String(id || '')) ? String(id) : ''
}

const backendGroupId = computed(() => getBackendGroupId())

const resolveIndividualTaskAssignee = (parentTask = null) => {
  if (parentTask?.assignedUser) return Number(parentTask.assignedUser)
  if (auth.isStudent && auth.user?.id) return Number(auth.user.id)

  const studentMemberships = groupMemberships.value.filter(item => {
    const role = String(item.role || '').toLowerCase()
    return !item.leftAt && role.includes('student')
  })
  const defaultAssignee = studentMemberships[0]?.userId || ''
  const assignee = window.prompt('Assignee user id', defaultAssignee ? String(defaultAssignee) : '')
  const assigneeId = Number(assignee)
  return Number.isFinite(assigneeId) && assigneeId > 0 ? assigneeId : null
}

const createTask = async (taskType, parentTask = null) => {
  const currentGroupId = getBackendGroupId()
  if (!currentGroupId) {
    taskError.value = 'A backend numeric group id is required before tasks can be added.'
    return
  }

  const label = parentTask ? 'New sub-task name' : taskType === 'group' ? 'New group task name' : 'New individual task name'
  const taskName = window.prompt(label)
  if (!taskName || !taskName.trim()) return

  const payload = {
    name: taskName.trim(),
    description: '',
    status: 'todo',
    task_type: taskType
  }

  if (parentTask?.id) {
    payload.parent = Number(parentTask.id)
  }

  if (taskType === 'group') {
    payload.group = Number(currentGroupId)
  } else {
    const assigneeId = resolveIndividualTaskAssignee(parentTask)
    if (!assigneeId) return
    payload.assigned_user = assigneeId
  }

  try {
    await requestJson(`${API_BASE_URL}/api/v1/tasks/`, {
      method: 'POST',
      body: JSON.stringify(payload)
    })

    await loadTasks()
  } catch (error) {
    taskError.value = error instanceof Error ? error.message : 'Task could not be created.'
  }
}

const toggleTask = async (task) => {
  if (!task?.id || isUpdatingTask(task.id)) return

  setTaskUpdating(task.id, true)
  taskError.value = ''

  try {
    const updatedTask = await requestJson(`${API_BASE_URL}/api/v1/tasks/${task.id}/check/`, {
      method: 'POST',
      body: JSON.stringify({
        completed: !task.completed
      })
    })
    const normalized = normalizeTask(updatedTask)
    const index = tasks.value.findIndex(item => Number(item.id) === Number(task.id))
    if (index === -1) {
      tasks.value.push(normalized)
    } else {
      tasks.value.splice(index, 1, normalized)
    }
  } catch (error) {
    taskError.value = error instanceof Error ? error.message : 'Task status could not be updated.'
  } finally {
    setTaskUpdating(task.id, false)
  }
}

const typingIndicatorText = computed(() => {
  if (!typingUsers.value.length) return ''
  if (typingUsers.value.length === 1) return `${typingUsers.value[0]} is typing...`
  return `${typingUsers.value[0]} and others are typing...`
})

const applyMessageUpdate = (messageId, updater) => {
  const index = messages.value.findIndex(message => String(message.id) === String(messageId))
  if (index === -1) return

  const current = messages.value[index]
  const nextValue = typeof updater === 'function' ? updater(current) : updater
  messages.value.splice(index, 1, nextValue)
}

const isPendingMessage = (message) => String(message?.id || '').startsWith('pending-') || Boolean(message?.isLocalOnly)

const findMatchingPendingMessageIndex = (message) => {
  if (!message?.isOwn) return -1

  return messages.value.findIndex(item =>
    isPendingMessage(item) &&
    item.isOwn &&
    item.text === message.text &&
    item.messageType === message.messageType
  )
}

const upsertMessage = (message) => {
  const normalized = normalizeMessage(message)
  const index = messages.value.findIndex(item => String(item.id) === String(normalized.id))
  if (index === -1) {
    const pendingIndex = findMatchingPendingMessageIndex(normalized)
    if (pendingIndex !== -1) {
      messages.value.splice(pendingIndex, 1, normalized)
      return
    }

    messages.value.push(normalized)
    return
  }

  messages.value.splice(index, 1, {
    ...messages.value[index],
    ...normalized
  })
}

const removeTypingUser = (name) => {
  typingUsers.value = typingUsers.value.filter(item => item !== name)
}

const sendSocketAction = (payload) => {
  if (!chatSocket || chatSocket.readyState !== WebSocket.OPEN) return
  chatSocket.send(JSON.stringify(payload))
}

const stopTypingIndicator = () => {
  clearTimeout(typingStopTimer)
  if (hasSentTypingStart) {
    sendSocketAction({ action: 'client.typing', status: 'stopped' })
    hasSentTypingStart = false
  }
}

const scheduleTypingStop = () => {
  clearTimeout(typingStopTimer)
  typingStopTimer = setTimeout(() => {
    stopTypingIndicator()
  }, 1400)
}

const handleComposerInput = () => {
  if (!newMessage.value.trim()) {
    stopTypingIndicator()
    return
  }

  if (!hasSentTypingStart) {
    sendSocketAction({ action: 'client.typing', status: 'started' })
    hasSentTypingStart = true
  }

  scheduleTypingStop()
}

const markMessagesAsRead = (messageIds) => {
  const ids = (messageIds || []).map(id => Number(id)).filter(id => Number.isFinite(id))
  if (!ids.length) return
  sendSocketAction({ action: 'client.mark_read', message_ids: ids })
}

const scrollMessagesToBottom = async () => {
  await nextTick()
  if (msgList.value) msgList.value.scrollTop = msgList.value.scrollHeight
}

const disconnectChatSocket = () => {
  if (chatSocket) {
    chatSocket.close()
    chatSocket = null
  }
  wsConnectionState.value = 'offline'
  typingUsers.value = []
  stopTypingIndicator()
}

const handleSocketPayload = async (payload) => {
  if (!payload || typeof payload !== 'object') return

  if (payload.type === 'typing.updated') {
    const currentUserId = Number(auth.user?.id || 0)
    if (Number(payload.user_id) === currentUserId) return

    const displayName = payload.user_name || `User ${payload.user_id}`
    if (payload.status === 'started') {
      if (!typingUsers.value.includes(displayName)) {
        typingUsers.value = [...typingUsers.value, displayName]
      }
    } else {
      removeTypingUser(displayName)
    }
    return
  }

  if (payload.type === 'message.reaction_updated') {
    applyMessageUpdate(payload.message_id, (message) => ({
      ...message,
      reactions: normalizeReactionMap(payload.reactions)
    }))
    return
  }

  if (payload.type === 'message.read') {
    const ids = Array.isArray(payload.message_ids) ? payload.message_ids : []
    ids.forEach((id) => {
      applyMessageUpdate(id, (message) => ({
        ...message,
        readBy: Array.from(new Set([...(message.readBy || []), payload.read_by]))
      }))
    })
    return
  }

  if (payload.type === 'message.preview_ready') {
    applyMessageUpdate(payload.message_id, (message) => ({
      ...message,
      preview: payload.preview || null
    }))
    return
  }

  const eventName = payload.event
  if (eventName === 'message.created' && payload.message) {
    upsertMessage(payload.message)
    removeTypingUser(payload.user_name || payload.message.sender_name || '')
    await scrollMessagesToBottom()
    if (Number(payload.message.sender_id) !== Number(auth.user?.id || 0)) {
      markMessagesAsRead([payload.message.id])
    }
    return
  }

  if (eventName === 'message.edited') {
    applyMessageUpdate(payload.message_id, (message) => ({
      ...message,
      text: payload.message_text || message.text,
      editedAt: payload.edited_at || message.editedAt
    }))
    return
  }

  if (eventName === 'message.deleted') {
    messages.value = messages.value.filter(message => String(message.id) !== String(payload.message_id))
  }
}

const connectChatSocket = () => {
  const backendGroupId = getBackendGroupId()
  if (!backendGroupId || typeof WebSocket === 'undefined') return

  disconnectChatSocket()

  try {
    chatSocket = new WebSocket(buildChatWebSocketUrl(backendGroupId))
  } catch {
    wsConnectionState.value = 'offline'
    return
  }

  wsConnectionState.value = 'connecting'

  chatSocket.addEventListener('open', () => {
    wsConnectionState.value = 'connected'
    markMessagesAsRead(messages.value.filter(message => !message.isOwn).map(message => message.id))
  })

  chatSocket.addEventListener('message', async (event) => {
    try {
      const payload = JSON.parse(event.data)
      await handleSocketPayload(payload)
    } catch (error) {
      console.error('Failed to parse chat socket payload:', error)
    }
  })

  chatSocket.addEventListener('close', () => {
    wsConnectionState.value = 'offline'
    typingUsers.value = []
  })

  chatSocket.addEventListener('error', () => {
    wsConnectionState.value = 'offline'
  })
}

const loadMessages = async () => {
  const backendGroupId = getBackendGroupId()
  if (!backendGroupId) {
    chatError.value = 'Live discussion needs a backend numeric group id.'
    messages.value = []
    await scrollMessagesToBottom()
    return
  }

  isLoadingMessages.value = true
  chatError.value = ''

  try {
    const data = await requestJsonFirst(
      buildChatMessageCollectionUrls(backendGroupId, '?limit=50')
    )
    const liveMessages = extractCollectionItems(data)
      .map(normalizeMessage)
      .reverse()

    messages.value = liveMessages.length ? liveMessages : []
  } catch (error) {
    chatError.value = error instanceof Error ? error.message : 'Live discussion is unavailable right now.'
    messages.value = []
  } finally {
    isLoadingMessages.value = false
    await scrollMessagesToBottom()
    markMessagesAsRead(messages.value.filter(message => !message.isOwn).map(message => message.id))
  }
}

const sendMessagePayload = async ({ body, requestOptions, optimisticMessage, pendingId, keepLocalOnFailure = false }) => {
  const backendGroupId = getBackendGroupId()
  if (!backendGroupId) {
    chatError.value = 'Live discussion needs a backend numeric group id.'
    throw new Error(chatError.value)
  }

  chatError.value = ''

  try {
    const savedMessage = await requestJsonFirst(body === 'upload'
      ? buildChatUploadUrls(backendGroupId)
      : buildChatMessageCollectionUrls(backendGroupId), requestOptions)

    if (!savedMessage) {
      return null
    }

    if (pendingId) {
      const index = messages.value.findIndex(message => message.id === pendingId)
      const normalizedSavedMessage = normalizeMessage(savedMessage)
      const existingIndex = messages.value.findIndex(message => String(message.id) === String(normalizedSavedMessage.id))

      if (index !== -1 && existingIndex !== -1 && index !== existingIndex) {
        messages.value.splice(index, 1)
        messages.value.splice(existingIndex > index ? existingIndex - 1 : existingIndex, 1, {
          ...messages.value[existingIndex > index ? existingIndex - 1 : existingIndex],
          ...normalizedSavedMessage
        })
      } else if (index !== -1) {
        messages.value.splice(index, 1, normalizedSavedMessage)
      } else if (existingIndex !== -1) {
        messages.value.splice(existingIndex, 1, {
          ...messages.value[existingIndex],
          ...normalizedSavedMessage
        })
      } else {
        upsertMessage(savedMessage)
      }
    } else if (savedMessage) {
      upsertMessage(savedMessage)
    }
    return savedMessage
  } catch (error) {
    chatError.value = error instanceof Error ? error.message : 'Message could not be sent.'
    if (pendingId && !keepLocalOnFailure) {
      messages.value = messages.value.filter(message => message.id !== pendingId)
    }
    throw error
  } finally {
    await scrollMessagesToBottom()
  }
}

const sendMessage = async () => {
  const text = newMessage.value.trim()
  if (!text || isSendingMessage.value) return
  if (!getBackendGroupId()) {
    chatError.value = 'Live discussion needs a backend numeric group id.'
    return
  }

  const now = new Date()
  const pendingId = `pending-${Date.now()}`
  const draftMessage = {
    id: pendingId,
    author: 'You',
    text,
    time: now.toLocaleTimeString([], { hour: '2-digit', minute: '2-digit' }),
    date: now.toISOString(),
    isOwn: true,
    message_type: 'text'
  }

  messages.value.push(normalizeMessage(draftMessage))
  newMessage.value = ''
  stopTypingIndicator()
  await scrollMessagesToBottom()

  isSendingMessage.value = true
  try {
    await sendMessagePayload({
      body: 'message',
      pendingId,
      optimisticMessage: draftMessage,
      requestOptions: {
        method: 'POST',
        body: JSON.stringify({
          message_text: text,
          message_type: 'text'
        })
      }
    })
  } catch {
    newMessage.value = text
  } finally {
    isSendingMessage.value = false
    composer.value?.focus()
  }
}

const sendGifMessage = async (gif) => {
  if (!supportsGifs) {
    gifError.value = 'GIF search is not available in the backend yet.'
    return
  }
  if (!gif?.url || isSendingMessage.value) return
}

const openFilePicker = () => {
  if (!supportsAttachments) {
    chatError.value = 'File upload is not available in the backend yet.'
    return
  }
  fileInputRef.value?.click()
}

const uploadAttachment = async (event) => {
  if (!supportsAttachments) {
    chatError.value = 'File upload is not available in the backend yet.'
    return
  }
  const input = event?.target
  const file = input?.files?.[0]
  if (!file || isUploadingFile.value) return
  chatError.value = `Upload for ${file.name} is not available in the backend yet.`
  if (input) input.value = ''
}

const fetchGifResults = async (mode = 'trending') => {
  if (!supportsGifs) {
    gifResults.value = []
    gifError.value = 'GIF search is not available in the backend yet.'
    return
  }

  isLoadingGifs.value = true
  gifError.value = ''

  try {
    const data = await requestJsonFirst(
      mode === 'search'
        ? buildGifSearchUrls(gifQuery.value.trim())
        : buildGifTrendingUrls(),
      {
        method: 'GET'
      }
    )
    gifResults.value = normalizeGifResults(data)
  } catch {
    gifResults.value = []
    gifError.value = 'Live GIF search is unavailable right now.'
  } finally {
    isLoadingGifs.value = false
  }
}

const toggleGifPanel = async () => {
  if (!supportsGifs) {
    gifError.value = 'GIF search is not available in the backend yet.'
    return
  }
  showGifPanel.value = !showGifPanel.value
  if (showGifPanel.value) {
    await fetchGifResults('trending')
  }
}

const searchGifs = async () => {
  if (!gifQuery.value.trim()) {
    await fetchGifResults('trending')
    return
  }

  await fetchGifResults('search')
}

const reactToMessage = async (messageId, emoji) => {
  if (!supportsMessageReactions) {
    chatError.value = 'Message reactions are not available in the backend yet.'
    return
  }

  const backendGroupId = getBackendGroupId()
  if (!backendGroupId) return

  applyMessageUpdate(messageId, (message) => ({
    ...message,
    reactions: {
      ...(message.reactions || {}),
      [emoji]: Number(message.reactions?.[emoji] || 0) + 1
    }
  }))

  try {
    await requestJsonFirst(buildChatReactionUrls(backendGroupId, messageId), {
      method: 'POST',
      body: JSON.stringify({
        emoji_string: emoji
      })
    })
  } catch {
    chatError.value = 'Reaction endpoint is not available yet.'
  }
}

const focusComposer = () => composer.value?.focus()

let loadSequence = 0

const switchGroup = async (event) => {
  const selectedGroupId = event?.target?.value
  if (!selectedGroupId || String(selectedGroupId) === String(backendGroupId.value)) return
  await router.push(`/groups/${selectedGroupId}`)
}

const reloadGroupDetail = async () => {
  const sequence = ++loadSequence

  disconnectChatSocket()
  tasks.value = []
  messages.value = []
  taskError.value = ''
  chatError.value = ''

  await loadGroup()
  if (sequence !== loadSequence) return

  await loadGroupMembers()
  if (sequence !== loadSequence) return

  await Promise.all([
    loadTasks(),
    loadMessages()
  ])
  if (sequence !== loadSequence) return

  connectChatSocket()
}

watch(routeGroupId, async () => {
  await reloadGroupDetail()
})

watch(
  () => auth.user?.id,
  async (userId, previousUserId) => {
    if (userId && userId !== previousUserId) {
      await loadGroupOptions()
    }
  }
)

onMounted(async () => {
  await ensureAuthUser()
  await loadGroupOptions()
  if (!routeGroupId.value && availableGroups.value.length) {
    await router.replace(`/groups/${availableGroups.value[0].id}`)
    return
  }

  await reloadGroupDetail()
})

onBeforeUnmount(() => {
  disconnectChatSocket()
  clearTimeout(typingStopTimer)
})
</script>

<style scoped>
/* Header */
.gd-head {
  display: flex;
  justify-content: space-between;
  align-items: center;
  gap: 1rem;
  margin-bottom: 1.25rem;
}
.gd-head-left {
  display: flex;
  align-items: center;
  gap: 0.9rem;
}
.gd-title { margin: 0; color: var(--charcoal); }
.gd-subtitle { color: #6c757d; margin-top: 0.15rem; }
.gd-meta-row {
  display: flex;
  flex-wrap: wrap;
  gap: 0.45rem;
  margin-top: 0.35rem;
  color: #6c757d;
  font-size: 0.85rem;
  font-weight: 600;
}
.gd-meta-row span {
  padding: 0.2rem 0.5rem;
  border: 1px solid var(--border-light);
  border-radius: 999px;
  background: rgba(255, 255, 255, 0.65);
}
.gd-head-actions {
  display: flex;
  flex-direction: column;
  align-items: flex-end;
  gap: 0.35rem;
  min-width: 180px;
}
.group-switcher {
  display: flex;
  align-items: center;
  gap: 0.5rem;
  color: #6c757d;
  font-size: 0.85rem;
  font-weight: 700;
}
.group-switcher select {
  min-width: 150px;
  max-width: 240px;
  border: 1px solid var(--border-light);
  border-radius: 8px;
  padding: 0.45rem 0.65rem;
  background: rgba(255, 255, 255, 0.9);
  color: var(--charcoal);
  font-weight: 600;
}
.group-switcher select:disabled {
  opacity: 0.65;
  cursor: not-allowed;
}
.group-switcher-error {
  color: #8a5a00;
  font-size: 0.78rem;
  font-weight: 600;
}

/* Mobile tabs */
.mobile-tabs {
  display: none;
  gap: 0.75rem;
  margin-bottom: 1rem;
  border-bottom: 1px solid var(--border-light);
  padding-bottom: 0.5rem;
}
.tab-btn {
  background: transparent;
  border: none;
  padding: 0.5rem 0.25rem;
  color: var(--charcoal);
  font-weight: 500;
  border-bottom: 3px solid transparent;
  cursor: pointer;
}
.tab-btn.active {
  color: var(--dark-green);
  border-bottom-color: var(--dark-green);
}

/* Split layout */
.split {
  display: grid;
  grid-template-columns: 1.15fr 1fr;
  gap: 1.5rem;
  align-items: stretch;
  max-height: 70vh;
  height: 70vh;
}

/* Tasks pane */
.pane--tasks {
  display: flex;
  flex-direction: column;
  height: 100%;
  min-height: 320px;
}

/* Discussion pane */
.pane--discussion {
  display: flex;
  flex-direction: column;
  height: 100%;
  min-height: 320px;
}

/* Card layout */
.card {
  height: 100%;
  min-height: 320px;
  display: flex;
  flex-direction: column;
  overflow: hidden;
}
.card-content {
  flex: 1 1 0;
  min-height: 0;
  overflow-y: auto;
}
.tasks-content {
  padding-right: 2px; /* for visible scrollbar */
}

.task-header-actions {
  display: flex;
  align-items: center;
  gap: 0.55rem;
  flex-wrap: wrap;
}

.task-section {
  border-bottom: 1px solid var(--border-light);
  padding: 0.9rem 0;
}

.task-section:last-child {
  border-bottom: 0;
}

.task-section-header {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 0.8rem;
  margin-bottom: 0.7rem;
}

.task-section-title {
  color: var(--charcoal);
  font-weight: 700;
}

.task-section-title i {
  margin-right: 0.45rem;
  color: var(--air-force-blue);
}

.task-section-status {
  color: #6c757d;
  font-size: 0.84rem;
  font-weight: 700;
}

.task-body {
  flex: 1;
  min-width: 0;
}

.task-description {
  margin-top: 0.18rem;
  color: #6c757d;
  font-size: 0.82rem;
  line-height: 1.45;
}

.task-meta {
  display: flex;
  flex-wrap: wrap;
  gap: 0.6rem;
  margin-top: 0.2rem;
  color: #6c757d;
  font-size: 0.78rem;
}

.task-meta i {
  margin-right: 0.25rem;
}

/* Discussion board: chat-container fills card, chat-messages scrolls */
.chat-status {
  color: #6c757d;
  font-size: 0.85rem;
  font-weight: 600;
}

.chat-alert {
  padding: 0.65rem 0.9rem;
  color: #6c4b00;
  background: #fff7d6;
  border-bottom: 1px solid #f1dd97;
  font-size: 0.9rem;
}

.typing-indicator,
.gif-status {
  padding: 0.55rem 0.9rem;
  color: var(--text-muted);
  font-size: 0.85rem;
}

.gif-panel {
  border-top: 1px solid var(--border-default);
  border-bottom: 1px solid var(--border-default);
  background: rgba(255, 255, 255, 0.04);
  padding: 0.85rem;
}

.gif-panel-header {
  display: flex;
  gap: 0.6rem;
  margin-bottom: 0.8rem;
}

.gif-search-input {
  flex: 1;
  border: 1px solid var(--border-default);
  border-radius: 12px;
  padding: 0.65rem 0.8rem;
  background: rgba(255, 255, 255, 0.9);
}

.gif-grid {
  display: grid;
  grid-template-columns: repeat(3, minmax(0, 1fr));
  gap: 0.65rem;
}

.gif-card {
  border: 1px solid var(--border-default);
  border-radius: 16px;
  overflow: hidden;
  background: rgba(255, 255, 255, 0.08);
  color: var(--text-primary);
  cursor: pointer;
  padding: 0;
}

.gif-card img {
  width: 100%;
  aspect-ratio: 1 / 1;
  object-fit: cover;
  display: block;
}

.gif-card span {
  display: block;
  padding: 0.45rem 0.55rem 0.6rem;
  font-size: 0.78rem;
  text-align: left;
}

.chat-btn:disabled {
  cursor: not-allowed;
  opacity: 0.48;
}

.pane--discussion .chat-container {
  display: flex;
  flex-direction: column;
  flex: 1 1 0;
  height: 100%;
  min-height: 0;
}

.pane--discussion .chat-messages {
  flex: 1 1 0;
  min-height: 0;
  overflow-y: auto;
}

.add-subtask-btn {
  display: inline-flex;
  align-items: center;
  gap: 0.4rem;
  border-color: var(--border-light);
  flex-shrink: 0;
}

.task-empty-state {
  padding: 0.8rem;
  color: #6c757d;
  background: #f8f9fa;
  border: 1px dashed var(--border-light);
  border-radius: 8px;
  font-size: 0.88rem;
}

/* Discussion header */
.pane--discussion .chat-header {
  display: flex;
  align-items: center;
  justify-content: space-between;
  background-color: var(--white) !important;
  color: var(--charcoal) !important;
  border-bottom: 1px solid var(--border-light);
}

/* Fill available chat space */
.pane--discussion .chat-container {
  display: flex;
  flex-direction: column;
  flex: 1 1 0;
  height: 100%;
  min-height: 0;
}

/* Message scroller */
.chat-messages {
  flex: 1 1 0;
  min-height: 0;
  overflow-y: auto;
}

/* Message date and time layout */
.message-meta {
  display: flex;
  align-items: center;
  gap: 0.5rem;
}
.message-date {
  color: #6c757d;
  font-weight: 500;
}

/* Own-message date contrast */
.pane--discussion .message.own .message-date {
  color: #fff !important;
  opacity: 0.95;
}

/* Message text color for own messages */
.pane--discussion .message.own .message-text {
  color: #fff !important;
}

.message-edited {
  display: inline-flex;
  align-items: center;
  padding: 0.1rem 0.4rem;
  border-radius: 999px;
  background: color-mix(in srgb, var(--accent-blue) 18%, transparent);
  color: var(--text-primary);
  font-size: 0.72rem;
  font-weight: 700;
  text-transform: uppercase;
  letter-spacing: 0.04em;
}

.message-gif {
  width: min(100%, 280px);
  border-radius: 18px;
  display: block;
  margin-top: 0.4rem;
  box-shadow: var(--shadow-sm);
}

.message-attachments {
  display: flex;
  flex-wrap: wrap;
  gap: 0.5rem;
  margin-top: 0.7rem;
}

.attachment-chip {
  display: inline-flex;
  align-items: center;
  gap: 0.4rem;
  padding: 0.45rem 0.7rem;
  border-radius: 999px;
  border: 1px solid var(--border-default);
  background: color-mix(in srgb, var(--surface-elevated) 92%, transparent);
  color: var(--text-primary);
  text-decoration: none;
  font-size: 0.84rem;
}

.message-preview {
  margin-top: 0.7rem;
  padding: 0.75rem 0.85rem;
  border-radius: 16px;
  border: 1px solid var(--border-default);
  background: color-mix(in srgb, var(--surface-base) 86%, transparent);
  color: var(--text-primary);
}

.message-reactions {
  display: flex;
  flex-wrap: wrap;
  gap: 0.45rem;
  margin-top: 0.75rem;
}

.reaction-btn {
  display: inline-flex;
  align-items: center;
  gap: 0.35rem;
  border-radius: 999px;
  border: 1px solid var(--border-default);
  background: color-mix(in srgb, var(--surface-elevated) 94%, transparent);
  color: var(--text-primary);
  padding: 0.35rem 0.6rem;
  font-size: 0.9rem;
  cursor: pointer;
  transition:
    border-color 0.18s ease,
    background 0.18s ease;
}

.reaction-btn:hover {
  border-color: var(--border-strong);
}

.reaction-count {
  font-size: 0.78rem;
  font-weight: 700;
}

.hidden-file-input {
  display: none;
}

/* Mobile layout */
@media (max-width: 900px) {
  .gd-head {
    align-items: flex-start;
    flex-direction: column;
  }
  .gd-head-actions {
    align-items: stretch;
    width: 100%;
  }
  .group-switcher {
    justify-content: space-between;
    width: 100%;
  }
  .group-switcher select {
    flex: 1;
    max-width: none;
  }
  .split {
    grid-template-columns: 1fr;
    max-height: 80vh;
    height: 80vh;
  }
  .mobile-tabs { display: flex; }
  .split .pane { display: none; }
  .split[data-active="tasks"] .pane--tasks { display: block; }
  .split[data-active="discussion"] .pane--discussion { display: block; }
  .card {
    min-height: 220px;
  }

  .gif-grid {
    grid-template-columns: repeat(2, minmax(0, 1fr));
  }
}
.group-detail {
  position: relative;
  isolation: isolate;
  min-height: 100%;
  overflow: visible;
  padding: 1.5rem 1.2rem 3rem;
  color: var(--text-primary);
  background:
    radial-gradient(circle at 10% 8%, var(--page-glow-one), transparent 26%),
    radial-gradient(circle at 86% 12%, var(--page-glow-two), transparent 24%),
    radial-gradient(circle at 68% 84%, var(--page-glow-three), transparent 26%);
}

.group-detail::before {
  content: '';
  position: absolute;
  inset: 0;
  z-index: -1;
  background: var(--group-shell-backdrop);
}

.group-detail--night {
  --text-primary: #f2fff7;
  --text-secondary: #b8d8c8;
  --text-muted: #84a997;
  --text-link: #8ee7c0;
  --surface-base: rgba(6, 18, 12, 0.82);
  --surface-elevated: rgba(8, 22, 16, 0.90);
  --border-default: rgba(255, 255, 255, 0.09);
  --border-strong: rgba(255, 255, 255, 0.16);
  --accent-blue: #60a5fa;
  --accent-teal: #2dd4bf;
  --accent-violet: #a78bfa;
  --accent-amber: #fbbf24;
  --accent-rose: #f87171;
  --shadow-lg: 0 24px 64px rgba(0, 6, 2, 0.52);
  --shadow-md: 0 14px 38px rgba(0, 6, 2, 0.40);
  --shadow-sm: 0 8px 22px rgba(0, 6, 2, 0.30);
  --page-glow-one: rgba(96, 165, 250, 0.14);
  --page-glow-two: rgba(45, 212, 191, 0.12);
  --page-glow-three: rgba(167, 139, 250, 0.10);
  --group-shell-backdrop: linear-gradient(135deg, #060c1a, #0a1224);
}

.group-detail--day {
  --text-primary: #1a3818;
  --text-secondary: #3a5e2c;
  --text-muted: #5e8040;
  --text-link: #265c3c;
  --surface-base: rgba(182, 214, 142, 0.84);
  --surface-elevated: rgba(196, 226, 158, 0.94);
  --surface-soft: rgba(80, 140, 40, 0.08);
  --border-default: rgba(70, 120, 30, 0.16);
  --border-strong: rgba(70, 120, 30, 0.24);
  --accent-blue: #2a6048;
  --accent-teal: #1f8a6a;
  --accent-violet: #7450c6;
  --accent-amber: #6a9820;
  --accent-rose: #b74d7e;
  --shadow-lg: 0 26px 72px rgba(30, 70, 14, 0.16);
  --shadow-md: 0 18px 42px rgba(30, 70, 14, 0.12);
  --hero-overlay-a: rgba(196, 222, 162, 0.96);
  --hero-overlay-b: rgba(180, 210, 144, 0.84);
  --group-shell-backdrop: linear-gradient(180deg, #d4eac0 0%, #c8e0b2 52%, #bcd6a4 100%);
  --page-glow-one: rgba(80, 180, 50, 0.13);
  --page-glow-two: rgba(100, 180, 80, 0.09);
  --page-glow-three: rgba(60, 160, 80, 0.08);
}

.group-hero-card {
  position: relative;
  overflow: hidden;
  margin-bottom: 1.5rem;
  border-radius: 28px;
  padding: 1.6rem;
  border: 1px solid rgba(255, 255, 255, 0.13);
  box-shadow: var(--shadow-lg), inset 0 1px 0 rgba(255, 255, 255, 0.07);
  backdrop-filter: blur(28px);
  -webkit-backdrop-filter: blur(28px);
}

.group-detail--night .group-hero-card {
  background: linear-gradient(145deg, rgba(6, 18, 12, 0.92), rgba(7, 16, 11, 0.78));
  border-color: rgba(255, 255, 255, 0.13);
}

.group-detail--day .group-hero-card {
  background: linear-gradient(145deg, rgba(210, 234, 174, 0.94), rgba(198, 222, 158, 0.82));
  border-color: rgba(90, 148, 50, 0.22);
  box-shadow: 0 24px 64px rgba(30, 70, 14, 0.18), inset 0 1px 0 rgba(240, 255, 220, 0.70);
}

.group-detail--night .group-hero-card::before,
.group-detail--night .group-hero-card::after,
.group-detail--day .group-hero-card::before,
.group-detail--day .group-hero-card::after {
  content: '';
  position: absolute;
  width: 52%;
  height: 72%;
  border-radius: 999px;
  filter: blur(22px);
  pointer-events: none;
}

.group-detail--night .group-hero-card::before,
.group-detail--day .group-hero-card::before {
  top: -35%;
  left: -6%;
}

.group-detail--night .group-hero-card::after,
.group-detail--day .group-hero-card::after {
  right: -8%;
  bottom: -32%;
  width: 46%;
}

.group-detail--night .group-hero-card::before {
  background: radial-gradient(circle, rgba(96, 165, 250, 0.22), transparent 66%);
}

.group-detail--night .group-hero-card::after {
  background: radial-gradient(circle, rgba(45, 212, 191, 0.18), transparent 68%);
}

.group-detail--day .group-hero-card::before {
  background: radial-gradient(circle, rgba(190, 154, 88, 0.18), transparent 66%);
}

.group-detail--day .group-hero-card::after {
  background: radial-gradient(circle, rgba(92, 138, 128, 0.14), transparent 68%);
}

.gd-head {
  position: relative;
  z-index: 1;
  padding: 1.35rem 1.45rem 1.4rem;
  border-radius: 28px;
  margin-bottom: 0;
  backdrop-filter: blur(24px);
  -webkit-backdrop-filter: blur(24px);
  transition:
    background 0.28s ease,
    border-color 0.28s ease,
    box-shadow 0.28s ease;
}

.group-detail--night .gd-head {
  background: linear-gradient(155deg, rgba(13, 30, 20, 0.94), rgba(9, 23, 16, 0.88));
  border: 1px solid rgba(255, 255, 255, 0.08);
  box-shadow:
    inset 0 1px 0 rgba(255, 255, 255, 0.05),
    0 18px 42px rgba(0, 8, 3, 0.18);
}

.group-detail--day .gd-head {
  background: linear-gradient(155deg, rgba(243, 250, 236, 0.94), rgba(232, 243, 223, 0.90));
  border: 1px solid rgba(90, 148, 40, 0.18);
  box-shadow:
    inset 0 1px 0 rgba(255, 255, 255, 0.62),
    0 16px 36px rgba(18, 31, 21, 0.08);
}

.gd-title {
  font-size: clamp(2rem, 3vw, 2.9rem);
  font-weight: 700;
  letter-spacing: 0;
  color: var(--text-primary);
}

.gd-subtitle {
  margin-top: 0.28rem;
  font-size: 0.98rem;
  color: var(--text-secondary);
}

.card {
  position: relative;
  border-radius: 28px;
  border: 1px solid var(--border-default);
  background: linear-gradient(
    165deg,
    color-mix(in srgb, var(--surface-elevated) 92%, transparent),
    color-mix(in srgb, var(--surface-base) 96%, transparent)
  );
  box-shadow: var(--shadow-md);
  backdrop-filter: blur(24px);
  -webkit-backdrop-filter: blur(24px);
  transition:
    border-color 0.28s ease,
    box-shadow 0.28s ease;
}

.card:hover {
  border-color: var(--border-strong);
  box-shadow: var(--shadow-lg);
}

.card::before {
  content: '';
  position: absolute;
  inset: 0;
  pointer-events: none;
  border-radius: inherit;
  background:
    radial-gradient(circle at top left, color-mix(in srgb, var(--accent-teal) 14%, transparent), transparent 32%),
    radial-gradient(circle at bottom right, color-mix(in srgb, var(--accent-blue) 10%, transparent), transparent 30%);
  opacity: 0.9;
}

.card > * {
  position: relative;
  z-index: 1;
}

.card-header {
  background: transparent;
  border-bottom: 1px solid var(--border-default);
}

.card-title {
  color: var(--text-primary);
}

.chat-status {
  color: var(--text-secondary);
}

.chat-alert {
  color: var(--text-primary);
  background: color-mix(in srgb, var(--accent-amber) 16%, transparent);
  border-bottom: 1px solid var(--border-default);
}

.pane--discussion .chat-container {
  position: relative;
  border-radius: 28px;
  border: 1px solid var(--border-default);
  background: linear-gradient(
    165deg,
    color-mix(in srgb, var(--surface-elevated) 92%, transparent),
    color-mix(in srgb, var(--surface-base) 96%, transparent)
  );
  box-shadow: var(--shadow-md);
  backdrop-filter: blur(24px);
  -webkit-backdrop-filter: blur(24px);
  overflow: hidden;
}

.pane--discussion .chat-header {
  background: transparent !important;
  background-color: transparent !important;
  color: var(--text-primary) !important;
  border-bottom: 1px solid var(--border-default);
}

.pane--discussion .chat-header h3 {
  color: var(--text-primary);
}

.pane--discussion .chat-messages {
  background: transparent;
}

.pane--discussion .chat-input {
  background: transparent;
  border-top: 1px solid var(--border-default);
}

.chat-input-field {
  background: color-mix(in srgb, var(--surface-base) 82%, transparent);
  color: var(--text-primary);
  border: 1px solid var(--border-default);
}

.chat-input-field::placeholder {
  color: var(--text-muted);
}

.chat-input-field:focus {
  border-color: var(--border-strong);
  box-shadow: 0 0 0 3px color-mix(in srgb, var(--accent-teal) 12%, transparent);
}

.chat-btn {
  border: 1px solid var(--border-default);
  background: color-mix(in srgb, var(--surface-elevated) 94%, transparent);
  color: var(--text-primary);
}

.chat-btn:hover {
  border-color: var(--border-strong);
  background: color-mix(in srgb, var(--surface-elevated) 100%, transparent);
}

.chat-btn:disabled,
.chat-btn:disabled:hover {
  cursor: not-allowed;
  opacity: 0.48;
  border-color: var(--border-default);
  background: color-mix(in srgb, var(--surface-elevated) 94%, transparent);
}

.group-detail--day .card,
.group-detail--day .pane--discussion .chat-container {
  background: linear-gradient(165deg, rgba(196, 226, 158, 0.94), rgba(182, 214, 142, 0.84));
  border-color: rgba(70, 120, 30, 0.16);
}

.group-detail--night .card,
.group-detail--night .pane--discussion .chat-container {
  background: linear-gradient(165deg, rgba(8, 22, 16, 0.92), rgba(6, 18, 12, 0.86));
  border-color: rgba(255, 255, 255, 0.09);
}

.group-detail--night .card-title,
.group-detail--night .pane--discussion .chat-header h3,
.group-detail--night .task-section-title,
.group-detail--night .task-label {
  color: #ecf7f2 !important;
}

.group-detail--night .task-section-status,
.group-detail--night .message-date,
.group-detail--night .message-time {
  color: rgba(214, 232, 223, 0.72) !important;
}

@media (max-width: 900px) {
  .gd-head {
    align-items: flex-start;
    flex-direction: column;
  }

  .gd-head-actions {
    align-items: stretch;
    width: 100%;
  }

  .group-switcher {
    justify-content: space-between;
    width: 100%;
  }

  .group-switcher select {
    flex: 1;
    max-width: none;
  }

  .split {
    grid-template-columns: 1fr;
    max-height: 80vh;
    height: 80vh;
  }

  .mobile-tabs {
    display: flex;
  }

  .split .pane {
    display: none;
  }

  .split[data-active="tasks"] .pane--tasks,
  .split[data-active="discussion"] .pane--discussion {
    display: block;
  }

  .card {
    min-height: 220px;
  }
}

/* Clean page treatment to match Events and Resources. */
.group-detail {
  isolation: auto;
  min-height: calc(100vh - 60px);
  overflow: auto;
  padding: 2rem;
  color: var(--charcoal);
  background: var(--bg-light);
  --text-primary: var(--charcoal);
  --text-secondary: #6c757d;
  --text-muted: #8a949e;
  --surface-base: var(--white);
  --surface-elevated: var(--white);
  --border-default: var(--border-light);
  --border-strong: #cfd6dd;
  --accent-blue: var(--air-force-blue);
  --accent-teal: var(--mint-green);
  --accent-amber: var(--warning);
  --shadow-sm: 0 1px 2px var(--shadow);
  --shadow-md: 0 2px 4px var(--shadow);
  --shadow-lg: 0 4px 12px var(--shadow);
}

.group-detail::before,
.group-hero-card::before,
.group-hero-card::after,
.card::before {
  display: none;
}

.group-hero-card {
  margin-bottom: 1.5rem;
  padding: 0;
  border: 0;
  border-radius: 8px;
  background: transparent;
  box-shadow: none;
  overflow: visible;
  backdrop-filter: none;
  -webkit-backdrop-filter: none;
}

.gd-head {
  padding: 1.5rem;
  margin-bottom: 0;
  border: 1px solid var(--border-light);
  border-radius: 8px;
  background: var(--white);
  box-shadow: 0 2px 4px var(--shadow);
  backdrop-filter: none;
  -webkit-backdrop-filter: none;
}

.gd-title {
  margin: 0;
  color: var(--charcoal);
  font-size: 2rem;
  font-weight: 600;
}

.gd-subtitle {
  margin-top: 0.15rem;
  color: #6c757d;
  font-size: 1rem;
}

.group-avatar {
  background: var(--air-force-blue);
  color: var(--white);
  border-color: var(--white);
}

.mobile-tabs {
  border-bottom-color: var(--border-light);
}

.tab-btn {
  color: var(--charcoal);
}

.tab-btn.active {
  color: var(--air-force-blue);
  border-bottom-color: var(--air-force-blue);
}

.card,
.pane--discussion .chat-container {
  border: 1px solid var(--border-light);
  border-radius: 8px;
  background: var(--white);
  box-shadow: 0 2px 4px var(--shadow);
  backdrop-filter: none;
  -webkit-backdrop-filter: none;
  transition: box-shadow 0.2s ease;
}

.card:hover,
.pane--discussion .chat-container:hover {
  border-color: var(--border-light);
  box-shadow: 0 4px 12px var(--shadow);
}

.card-header,
.pane--discussion .chat-header {
  background: var(--white) !important;
  color: var(--charcoal) !important;
  border-bottom: 1px solid var(--border-light);
}

.card-title,
.pane--discussion .chat-header h3,
.task-section-title,
.task-label {
  color: var(--charcoal) !important;
}

.chat-status,
.task-section-status,
.message-date,
.message-time,
.typing-indicator,
.gif-status {
  color: #6c757d !important;
}

.chat-alert {
  color: #6c4b00;
  background: #fff7d6;
  border-bottom: 1px solid #f1dd97;
}

.pane--discussion .chat-messages {
  background: #f8f9fa;
}

.pane--discussion .chat-input,
.gif-panel {
  background: var(--white);
  border-color: var(--border-light);
}

.chat-input-field,
.gif-search-input {
  background: var(--white);
  color: var(--charcoal);
  border: 1px solid var(--border-light);
  border-radius: 4px;
}

.chat-input-field::placeholder {
  color: #8a949e;
}

.chat-input-field:focus,
.gif-search-input:focus {
  outline: none;
  border-color: var(--air-force-blue);
  box-shadow: 0 0 0 3px rgba(57, 104, 123, 0.12);
}

.chat-btn {
  border: 1px solid var(--border-light);
  background: var(--white);
  color: var(--air-force-blue);
}

.chat-btn:hover {
  border-color: var(--air-force-blue);
  background: #f1f5f7;
}

.chat-btn:disabled,
.chat-btn:disabled:hover {
  color: #98a2ad;
  border-color: var(--border-light);
  background: var(--white);
}

.message-avatar {
  background: #8a949e;
}

.message-content,
.message-preview,
.attachment-chip,
.reaction-btn,
.gif-card {
  border: 1px solid var(--border-light);
  background: var(--white);
  color: var(--charcoal);
  box-shadow: 0 1px 2px rgba(0, 0, 0, 0.06);
}

.message.own .message-content {
  background: var(--air-force-blue);
  color: var(--white);
  border-color: var(--air-force-blue);
}

.message.own .message-author,
.message.own .message-time,
.message.own .message-date,
.pane--discussion .message.own .message-text {
  color: var(--white) !important;
}

.message-edited {
  background: #eef3f5;
  color: var(--air-force-blue);
}

.reaction-btn:hover {
  border-color: var(--air-force-blue);
  background: #f8f9fa;
}

.task-section {
  border-bottom-color: var(--border-light);
}

.task-item:hover {
  margin: 0;
  padding-top: 0.5rem;
  padding-right: 0;
  padding-bottom: 0.5rem;
  background-color: transparent;
}

.task-checkbox.checked {
  background-color: var(--air-force-blue);
  border-color: var(--air-force-blue);
}

.add-subtask-btn {
  color: var(--air-force-blue);
  border-color: var(--border-light);
}

.add-subtask-btn:hover {
  background: #f1f5f7;
  border-color: var(--air-force-blue);
}
</style>
