<template>
  <div
    class="content-area group-detail"
    :class="themeStore.isDayMode ? 'group-detail--day' : 'group-detail--night'"
    :data-active="activeTab"
  >
    <!-- Header -->
    <div class="group-hero-card">
      <div class="gd-head">
        <div class="gd-head-left">
          <div class="group-avatars">
            <div class="group-avatar" style="width:48px;height:48px;font-size:1.1rem;">YG</div>
          </div>
          <div>
            <h2 class="gd-title">{{ group.name }}</h2>
            <p class="gd-subtitle">{{ group.members }} members · Group since August 04, 2025</p>
          </div>
        </div>
      </div>
    </div>

    <!-- Mobile tabs (hidden on desktop) -->
    <nav class="mobile-tabs">
      <button
        class="tab-btn"
        :class="{ active: activeTab === 'plan' }"
        @click="activeTab = 'plan'"
      >
        Plan
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
      <!-- Left column: Plan -->
      <section class="pane pane--plan card">
        <div class="card-header">
          <h3 class="card-title">Plan</h3>
          <button type="button" class="btn btn-primary btn-sm">
            <i class="fas fa-plus"></i> Add Milestone
          </button>
        </div>
        <div class="card-content plan-content">
          <div v-for="m in tasks" :key="m.id" class="milestone">
            <div class="milestone-header">
              <div class="milestone-title">
                <i class="fas fa-flag"></i>
                {{ m.milestone }}
              </div>
              <div class="milestone-status">
                {{ countCompleted(m) }}/{{ m.tasks.length }} Completed
              </div>
            </div>

            <div class="task-list">
              <div
                v-for="t in m.tasks"
                :key="t.id"
                class="task-item"
                @click="t.completed = !t.completed"
              >
                <div :class="['task-checkbox', { checked: t.completed }]" />
                <div :class="['task-label', { completed: t.completed }]">{{ t.name }}</div>
                <i class="fas fa-calendar" style="color:#6c757d;"></i>
                <i class="fas fa-user" style="color:#6c757d;"></i>
              </div>

              <div class="add-task-row">
                <button
                  type="button"
                  class="btn btn-outline btn-sm add-task-btn"
                  @click.stop="addTask(m)"
                  title="Add a new task under this milestone"
                >
                  <i class="fas fa-plus"></i>
                  Add Task
                </button>
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
                    {{ attachment.attachment_filename || 'Attachment' }}
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
            <div v-if="showGifPanel" class="gif-panel">
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
                <button class="chat-btn" type="button" title="GIF picker" @click="toggleGifPanel">
                  <i class="fas fa-image"></i>
                </button>
                <button class="chat-btn" type="button" title="Attach file" :disabled="isUploadingFile" @click="openFilePicker">
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
import { ref, onMounted, onBeforeUnmount, nextTick, computed } from 'vue'
import { useRoute } from 'vue-router'
import { mockGroups } from '../data/mock.js'
import { useAuthStore } from '@/stores/auth'
import { useThemeStore } from '@/stores/theme'
import { buildSessionHeaders } from '@/utils/csrf'

const route = useRoute()
const auth = useAuthStore()
const themeStore = useThemeStore()
const API_BASE_URL = import.meta.env.VITE_API_BASE_URL || 'http://localhost:8000'
const CHAT_REACTION_OPTIONS = ['👍', '❤️', '🎉']
const MOCK_GIF_RESULTS = [
  { id: 'gif-1', url: 'https://media.tenor.com/2roX3uxz_68AAAAC/cat-space.gif', previewUrl: 'https://media.tenor.com/2roX3uxz_68AAAAC/cat-space.gif', title: 'Celebration cat' },
  { id: 'gif-2', url: 'https://media.tenor.com/mCYz5TvJ8FYAAAAC/excited-happy.gif', previewUrl: 'https://media.tenor.com/mCYz5TvJ8FYAAAAC/excited-happy.gif', title: 'Excited reaction' },
  { id: 'gif-3', url: 'https://media.tenor.com/v6hK8g0j8MIAAAAC/thumbs-up-yes.gif', previewUrl: 'https://media.tenor.com/v6hK8g0j8MIAAAAC/thumbs-up-yes.gif', title: 'Thumbs up' }
]
const rawGroupId = route.params.id ? String(route.params.id) : ''
const group = ref(mockGroups.find(g => String(g.id) === rawGroupId) || mockGroups[0])

// 只保留 plan / discussion
const activeTab = ref('plan')

// 示例任务数据
const tasks = ref([
  {
    id: 1,
    milestone: 'Getting Started',
    tasks: [
      { id: 11, name: 'Determine Group Topic', completed: false },
      { id: 12, name: 'Determine Meeting Time', completed: false }
    ]
  },
  {
    id: 2,
    milestone: 'Working Towards a Solution',
    tasks: [
      { id: 21, name: 'Meeting 1: Initialisation', completed: false },
      { id: 22, name: 'Meeting 2: Project Planning & Poster Outline', completed: false },
      { id: 23, name: 'Meeting 3: Draft Review & Optional Deliverables', completed: false }
    ]
  }
])

const countCompleted = (m) => m.tasks.filter(t => t.completed).length

const addTask = (m) => {
  const nextId = (m.tasks.reduce((max, t) => Math.max(max, t.id), 0) || 0) + 1
  m.tasks.push({ id: nextId, name: 'New Task', completed: false })
}

const mockMessages = [
  {
    id: 1,
    author: 'Anita Pickard',
    text: 'Hi team! How is your idea going?',
    time: '03:04 PM',
    date: '2025-09-03',
    isOwn: false
  },
  {
    id: 2,
    author: 'You',
    text: 'Sounds great!',
    time: '03:20 PM',
    date: '2025-09-03',
    isOwn: true
  }
]

const messages = ref([...mockMessages])

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
const gifResults = ref([...MOCK_GIF_RESULTS])
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
  const response = await fetch(url, {
    credentials: 'include',
    ...options,
    headers: buildSessionHeaders({
      includeCSRF: options.method && options.method !== 'GET',
      isFormData,
      headers: {
        Accept: 'application/json',
        ...(options.headers || {})
      }
    })
  })

  const text = await response.text()
  let data = null
  try {
    data = text ? JSON.parse(text) : null
  } catch {
    data = null
  }

  if (!response.ok) {
    throw new Error(data?.detail || data?.error || data?.message || `Request failed: ${response.status}`)
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
    members: Number(item?.members || item?.memberCount || group.value?.members || 0),
    createdAt: item?.created_at || item?.createdAt || ''
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

  return normalized.length ? normalized : [...MOCK_GIF_RESULTS]
}

const loadGroup = async () => {
  try {
    if (rawGroupId) {
      const data = await requestJson(`${API_BASE_URL}/groups/groups/${rawGroupId}/`)
      group.value = normalizeGroup(data)
      return
    }

    const data = await requestJson(`${API_BASE_URL}/groups/groups/?page_size=1`)
    const firstGroup = extractCollectionItems(data)[0]
    if (firstGroup) {
      group.value = normalizeGroup(firstGroup)
    }
  } catch (error) {
    group.value = mockGroups.find(g => String(g.id) === rawGroupId) || mockGroups[0]
  }
}

const normalizeMessage = (item) => {
  const raw = item?.message ? item.message : item
  const sentAt = raw?.sent_at || raw?.sent_datetime || raw?.created_at || new Date().toISOString()
  const senderId = Number(raw?.sender_user || raw?.sender_id || raw?.sender_user_id || 0)
  const currentUserId = Number(auth.user?.id || 0)
  const isOwn = currentUserId > 0 && senderId === currentUserId
  const messageText = raw?.message_text || raw?.text || ''
  const messageType = raw?.message_type || 'text'
  const attachments = Array.isArray(raw?.attachments) ? raw.attachments : []
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

const getBackendGroupId = () => {
  const id = group.value?.id
  return /^\d+$/.test(String(id || '')) ? String(id) : ''
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

const upsertMessage = (message) => {
  const normalized = normalizeMessage(message)
  const index = messages.value.findIndex(item => String(item.id) === String(normalized.id))
  if (index === -1) {
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
    chatError.value = 'Live discussion needs a backend group id. Showing local sample messages.'
    messages.value = [...mockMessages]
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
    chatError.value = 'Live discussion is unavailable, showing local sample messages.'
    messages.value = [...mockMessages]
  } finally {
    isLoadingMessages.value = false
    await scrollMessagesToBottom()
    markMessagesAsRead(messages.value.filter(message => !message.isOwn).map(message => message.id))
  }
}

const sendMessagePayload = async ({ body, requestOptions, optimisticMessage, pendingId, keepLocalOnFailure = false }) => {
  const backendGroupId = getBackendGroupId()
  if (!backendGroupId) {
    if (optimisticMessage) {
      upsertMessage({
        ...optimisticMessage,
        isLocalOnly: true
      })
      await scrollMessagesToBottom()
    }
    chatError.value = 'Live discussion needs a backend group id. This update is only shown locally.'
    return
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
      if (index !== -1) {
        messages.value.splice(index, 1, normalizeMessage(savedMessage))
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
  if (!gif?.url || isSendingMessage.value) return

  const now = new Date()
  const pendingId = `gif-${Date.now()}`
  const optimisticMessage = {
    id: pendingId,
    author: 'You',
    message_text: gif.url,
    message_type: 'gif',
    sent_at: now.toISOString(),
    isOwn: true
  }

  messages.value.push(normalizeMessage(optimisticMessage))
  showGifPanel.value = false
  gifError.value = ''
  await scrollMessagesToBottom()

  isSendingMessage.value = true
  try {
    await sendMessagePayload({
      body: 'message',
      pendingId,
      optimisticMessage,
      keepLocalOnFailure: true,
      requestOptions: {
        method: 'POST',
        body: JSON.stringify({
          message_text: gif.url,
          message_type: 'gif'
        })
      }
    })
  } catch {
    chatError.value = 'GIF endpoint is not available yet. The GIF is shown locally for now.'
  } finally {
    isSendingMessage.value = false
    composer.value?.focus()
  }
}

const openFilePicker = () => {
  fileInputRef.value?.click()
}

const uploadAttachment = async (event) => {
  const input = event?.target
  const file = input?.files?.[0]
  if (!file || isUploadingFile.value) return

  const now = new Date()
  const pendingId = `upload-${Date.now()}`
  const optimisticMessage = {
    id: pendingId,
    author: 'You',
    message_text: file.name,
    message_type: 'attachment',
    sent_at: now.toISOString(),
    attachments: [{ id: pendingId, attachment_filename: file.name }],
    isOwn: true
  }

  messages.value.push(normalizeMessage(optimisticMessage))
  await scrollMessagesToBottom()

  const formData = new FormData()
  formData.append('file', file)
  formData.append('message_text', '')

  isUploadingFile.value = true
  try {
    await sendMessagePayload({
      body: 'upload',
      pendingId,
      optimisticMessage,
      keepLocalOnFailure: true,
      requestOptions: {
        method: 'POST',
        body: formData
      }
    })
  } catch {
    chatError.value = 'Upload endpoint is not available yet. The attachment is shown locally for now.'
  } finally {
    isUploadingFile.value = false
    if (input) input.value = ''
  }
}

const fetchGifResults = async (mode = 'trending') => {
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
    gifResults.value = [...MOCK_GIF_RESULTS]
    gifError.value = 'Live GIF search is unavailable, showing fallback picks.'
  } finally {
    isLoadingGifs.value = false
  }
}

const toggleGifPanel = async () => {
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
    chatError.value = 'Reaction endpoint is not available yet. The reaction is shown locally for now.'
  }
}

const focusComposer = () => composer.value?.focus()

onMounted(async () => {
  await loadGroup()
  await loadMessages()
  connectChatSocket()
})

onBeforeUnmount(() => {
  disconnectChatSocket()
  clearTimeout(typingStopTimer)
})
</script>

<style scoped>
/* 顶部信息 */
.gd-head {
  display: flex;
  justify-content: space-between;
  align-items: center;
  margin-bottom: 1.25rem;
}
.gd-head-left {
  display: flex;
  align-items: center;
  gap: 0.9rem;
}
.gd-title { margin: 0; color: var(--charcoal); }
.gd-subtitle { color: #6c757d; margin-top: 0.15rem; }

/* 移动端 tabs（桌面隐藏） */
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

/* 双栏布局容器 */
.split {
  display: grid;
  grid-template-columns: 1.15fr 1fr;
  gap: 1.5rem;
  align-items: stretch;
  max-height: 70vh;
  height: 70vh;
}

/* 左栏：Plan */
.pane--plan {
  display: flex;
  flex-direction: column;
  height: 100%;
  min-height: 320px;
}

/* 右栏：Discussion */
.pane--discussion {
  display: flex;
  flex-direction: column;
  height: 100%;
  min-height: 320px;
}

/* 卡片样式 */
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
.plan-content {
  padding-right: 2px; /* for visible scrollbar */
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

/* Add Task 行的微调，保持与全站按钮风格一致 */
.add-task-row {
  padding-left: 0.25rem;
  margin-top: 0.4rem;
}
.add-task-btn {
  display: inline-flex;
  align-items: center;
  gap: 0.4rem;
  border-color: var(--border-light);
}

/* 讨论区头部改为白色（覆盖全局 .chat-header 绿色背景） */
.pane--discussion .chat-header {
  display: flex;
  align-items: center;
  justify-content: space-between;
  background-color: var(--white) !important;
  color: var(--charcoal) !important;
  border-bottom: 1px solid var(--border-light);
}

/* 确保 chat-container 填满可用空间 */
.pane--discussion .chat-container {
  display: flex;
  flex-direction: column;
  flex: 1 1 0;
  height: 100%;
  min-height: 0;
}

/* 使 chat-messages 占据可用空间 */
.chat-messages {
  flex: 1 1 0;
  min-height: 0;
  overflow-y: auto;
}

/* 在每条消息头部右侧同时显示日期与时间的排版 */
.message-meta {
  display: flex;
  align-items: center;
  gap: 0.5rem;
}
.message-date {
  color: #6c757d;
  font-weight: 500;
}

/* 仅“你自己的消息”把日期变为白色，与气泡一致 */
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
    transform 0.18s ease,
    background 0.18s ease;
}

.reaction-btn:hover {
  border-color: var(--border-strong);
  transform: translateY(-1px);
}

.reaction-count {
  font-size: 0.78rem;
  font-weight: 700;
}

.hidden-file-input {
  display: none;
}

/* 移动端：单列 + 由 tabs 控制显示哪一块 */
@media (max-width: 900px) {
  .split {
    grid-template-columns: 1fr;
    max-height: 80vh;
    height: 80vh;
  }
  .mobile-tabs { display: flex; }
  .split .pane { display: none; }
  .split[data-active="plan"] .pane--plan { display: block; }
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
    box-shadow 0.28s ease,
    transform 0.28s ease;
}

.card:hover {
  border-color: var(--border-strong);
  box-shadow: var(--shadow-lg);
  transform: translateY(-2px);
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
.group-detail--night .milestone-title,
.group-detail--night .task-label {
  color: #ecf7f2 !important;
}

.group-detail--night .milestone-status,
.group-detail--night .message-date,
.group-detail--night .message-time {
  color: rgba(214, 232, 223, 0.72) !important;
}

@media (max-width: 900px) {
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

  .split[data-active="plan"] .pane--plan,
  .split[data-active="discussion"] .pane--discussion {
    display: block;
  }

  .card {
    min-height: 220px;
  }
}
</style>
