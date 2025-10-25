<template>
  <div class="content-area group-detail" :data-active="activeTab">
      <!-- 右栏：Discussion -->
      <section class="pane pane--discussion">
        <div class="chat-container">
          <div class="chat-header">
            <h3 style="margin:0;">Discussion Board</h3>
            <button
              v-if="hasMoreMessages"
              type="button"
              class="btn btn-outline btn-xs"
              :disabled="chatLoading || loadingOlder"
              @click="loadOlderMessages"
            >
              <i
                class="fas"
                :class="loadingOlder ? 'fa-spinner fa-spin' : 'fa-history'"
              ></i>
              Load earlier
            </button>
          </div>

          <div v-if="chatErrorMessage" class="alert-error">{{ chatErrorMessage }}</div>

          <div class="chat-messages" ref="msgList">
            <div v-if="chatLoading" class="chat-status">Loading messages…</div>
            <div v-else-if="!displayMessages.length" class="chat-status">No messages yet.</div>
            <template v-else>
              <div
                v-for="message in displayMessages"
                :key="message.id"
                :class="['message', { own: message.isOwn }]"
              >
                <div class="message-avatar">{{ getInitials(message.author) }}</div>
                <div class="message-content">
                  <div class="message-header">
                    <span class="message-author">{{ message.author }}</span>
                    <span class="message-meta">
                      <span class="message-date">{{ formatDate(message.timestamp) }}</span>
                      <span class="message-time">{{ formatTime(message.timestamp) }}</span>
                      <span
                        v-if="message.moderationStatus !== 'approved'"
                        :class="['message-flag', `message-flag--${message.moderationStatus}`]"
                      >
                        {{ message.moderationStatus === 'pending' ? 'Pending review' : 'Removed' }}
                      </span>
                    </span>
                  </div>
                  <div
                    class="message-text"
                    :class="{ 'message-text--muted': message.isDeleted }"
                  >
                    {{ message.displayText }}
                  </div>
                  <div v-if="message.showModerationNote" class="message-note">
                    {{ message.moderationNote }}
                  </div>
                  <div
                    v-if="message.attachments.length && (!message.isDeleted || isModerator)"
                    class="message-attachments"
                  >
                    <a
                      v-for="file in message.attachments"
                      :key="file.id"
                      :href="file.url"
                      class="message-attachment-link"
                      target="_blank"
                      rel="noopener noreferrer"
                    >
                      <i class="fas fa-paperclip"></i>
                      {{ file.filename }}
                    </a>
                  </div>
                </div>
              </div>
            </template>
          </div>

          <div
            v-if="pendingAttachments.length"
            class="chat-attachments-preview"
          >
            <div
              v-for="file in pendingAttachments"
              :key="file.id"
              :class="['attachment-chip', { uploading: file.uploading, error: !!file.error }]"
            >
              <i
                class="fas"
                :class="file.uploading ? 'fa-spinner fa-spin' : 'fa-paperclip'"
              ></i>
              <span class="attachment-name">{{ file.filename }}</span>
              <button
                type="button"
                class="attachment-remove"
                :disabled="file.uploading"
                @click="removeAttachment(file.id)"
              >
                <i class="fas fa-times"></i>
              </button>
            </div>
          </div>

          <div v-if="attachmentError" class="alert-error">{{ attachmentError }}</div>

          <div class="chat-input">
            <div class="chat-input-group">
              <textarea
                ref="composer"
                v-model="newMessage"
                class="chat-input-field"
                placeholder="Type your message..."
                rows="2"
                @keydown.enter.exact.prevent="sendMessage"
              ></textarea>
              <div class="chat-actions">
                <input
                  ref="fileInput"
                  type="file"
                  class="sr-only"
                  multiple
                  @change="handleAttachmentSelection"
                />
                <button
                  class="chat-btn chat-btn--secondary"
                  type="button"
                  title="Attach file"
                  aria-label="Attach file"
                  :disabled="isSending || isUploadingAttachment"
                  @click="triggerAttachment"
                >
                  <i
                    class="fas"
                    :class="isUploadingAttachment ? 'fa-spinner fa-spin' : 'fa-paperclip'"
                  ></i>
                </button>
                <button
                  class="chat-btn chat-btn--primary"
                  type="button"
                  @click="sendMessage"
                  title="Send"
                  aria-label="Send message"
                  :disabled="disableSendButton || isSending || isUploadingAttachment"
                >
                  <i
                    class="fas"
                    :class="isSending ? 'fa-spinner fa-spin' : 'fa-paper-plane'"
                  ></i>
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
import { ref, computed, onMounted, onBeforeUnmount, nextTick, watch } from 'vue'
import { useRoute } from 'vue-router'
import { useGroupStore } from '@/stores/groups'
import { useChatStore } from '@/stores/chat'
import { useAuthStore } from '@/stores/auth'

const route = useRoute()
const groupStore = useGroupStore()
const chatStore = useChatStore()
const authStore = useAuthStore()

const groupId = computed(() => route.params.id)
const group = computed(() => groupStore.groupsById[groupId.value])

// chat state
const newMessage = ref('')
const composer = ref(null)
const msgList = ref(null)
const fileInput = ref(null)
const pendingAttachments = ref([])
const attachmentError = ref('')
const chatMessageError = ref('')

const chatMessages = computed(() => chatStore.messagesByGroup[groupId.value] || [])
const chatLoading = computed(() => !!chatStore.loadingByGroup[groupId.value])
const hasMoreMessages = computed(() => !!chatStore.hasMoreByGroup[groupId.value])
const chatStoreError = computed(() => chatStore.errorByGroup[groupId.value])
const isSending = computed(() => !!chatStore.sendingByGroup[groupId.value])
const loadingOlder = ref(false)

const chatErrorMessage = computed(() => {
  if (chatMessageError.value) return chatMessageError.value
  const err = chatStoreError.value
  if (!err) return ''
  return err.message || `${err}`
})

const isUploadingAttachment = computed(() =>
  pendingAttachments.value.some((item) => item.uploading)
)

const readyAttachments = computed(() =>
  pendingAttachments.value.filter((item) => item.url && !item.uploading && !item.error)
)

const disableSendButton = computed(
  () => !newMessage.value.trim() && readyAttachments.value.length === 0
)

const isModerator = computed(() => {
  const currentUser = authStore.user
  if (!currentUser) return false
  const elevatedRoles = ['admin', 'supervisor']
  if (elevatedRoles.includes(currentUser.role) || currentUser.is_staff) return true
  const mentorId = group.value?.mentor?.id ?? null
  return mentorId !== null && mentorId === currentUser.id
})

const displayMessages = computed(() =>
  chatMessages.value.map((message) => {
    const timestamp = message.timestamp
    const attachments = Array.isArray(message.attachments) ? message.attachments : []
    const isDeleted = Boolean(message.isDeleted)
    const moderationStatus = message.moderation?.status || 'approved'
    const moderationNote = message.moderation?.note || ''

    return {
      id: message.id,
      author: message.author?.name || message.author || 'Unknown',
      authorId: message.author?.id ?? null,
      text: message.text || '',
      displayText: isDeleted
        ? 'This message has been removed by a moderator.'
        : message.text || '',
      timestamp,
      attachments: attachments.map((file, index) => ({
        id: `${message.id}-${index}`,
        url: file.url || file.file_url,
        filename: file.filename || 'Attachment',
        size: file.size ?? file.file_size ?? null,
        mimeType: file.mimeType || file.mime_type || 'application/octet-stream'
      })),
      isOwn: authStore.user?.id
        ? message.author?.id === authStore.user.id
        : false,
      isDeleted,
      moderationStatus,
      moderationNote,
      showModerationNote: Boolean(moderationNote) && (isModerator.value || authStore.user?.id === message.author?.id)
    }
  })
)

const getInitials = (name) =>
  String(name || '')
    .split(' ')
    .filter(Boolean)
    .map((segment) => segment[0])
    .join('')
    .toUpperCase() || '—'

const formatDate = (value) => {
  const date = new Date(value)
  if (Number.isNaN(date.getTime())) return value
  return date.toLocaleDateString('en-AU', {
    year: 'numeric',
    month: 'short',
    day: 'numeric'
  })
}

const formatTime = (value) => {
  const date = new Date(value)
  if (Number.isNaN(date.getTime())) return ''
  return date.toLocaleTimeString([], { hour: '2-digit', minute: '2-digit' })
}

const scrollToBottom = async () => {
  await nextTick()
  if (msgList.value) {
    msgList.value.scrollTop = msgList.value.scrollHeight
  }
}

const focusComposer = () => composer.value?.focus()

const loadGroup = async (id, { force = false } = {}) => {
  if (!id) return
  loading.value = true
  errorMessage.value = ''
  try {
    if (!groupStore.myGroupsLoaded) {
      await groupStore.fetchMyGroups()
    }
    await groupStore.fetchGroupDetail(id, { forceRefresh: force })
  } catch (error) {
    console.error('Failed to load group detail', error)
    errorMessage.value = error?.message || 'Failed to load group information'
  } finally {
    loading.value = false
  }
}

const loadChat = async (
  id,
  { before = null, append = false } = {}
) => {
  if (!id) return
  chatMessageError.value = ''
  try {
    await chatStore.fetchMessages(id, { before, append })
    if (!append) {
      await scrollToBottom()
    }
  } catch (error) {
    console.error('Failed to load chat messages', error)
    chatMessageError.value = error?.message || 'Failed to load chat messages'
  }
}

const loadOlderMessages = async () => {
  if (!groupId.value || !hasMoreMessages.value || loadingOlder.value) return
  const oldest = chatMessages.value[0]
  if (!oldest?.timestamp) return
  loadingOlder.value = true
  try {
    await loadChat(groupId.value, { before: oldest.timestamp, append: true })
  } finally {
    loadingOlder.value = false
  }
}

const triggerAttachment = () => {
  attachmentError.value = ''
  chatMessageError.value = ''
  fileInput.value?.click()
}

const patchAttachment = (id, patch) => {
  pendingAttachments.value = pendingAttachments.value.map((item) =>
    item.id === id ? { ...item, ...patch } : item
  )
}

const handleAttachmentSelection = async (event) => {
  const files = Array.from(event.target?.files || [])
  event.target.value = ''
  if (!files.length) return

  attachmentError.value = ''
  chatMessageError.value = ''

  for (const file of files) {
    const entry = {
      id: `${Date.now()}-${file.name}-${Math.random().toString(36).slice(2)}`,
      filename: file.name,
      size: file.size,
      mimeType: file.type || 'application/octet-stream',
      uploading: true,
      url: null,
      error: null
    }
    pendingAttachments.value = [...pendingAttachments.value, entry]

    try {
      const uploaded = await chatStore.uploadAttachment(file)
      patchAttachment(entry.id, {
        url: uploaded.url,
        filename: uploaded.filename,
        size: uploaded.size,
        mimeType: uploaded.mimeType,
        uploading: false,
        error: null
      })
    } catch (error) {
      const message = error?.message || 'File upload failed'
      patchAttachment(entry.id, {
        uploading: false,
        error: message
      })
      attachmentError.value = message
      console.error('Failed to upload attachment', error)
    }
  }
}

const removeAttachment = (id) => {
  pendingAttachments.value = pendingAttachments.value.filter((item) => item.id !== id)
}

const sendMessage = async () => {
  const text = newMessage.value.trim()
  if (disableSendButton.value) return
  if (isUploadingAttachment.value) {
    attachmentError.value = 'File upload is still in progress, please wait'
    return
  }

  chatMessageError.value = ''
  attachmentError.value = ''

  try {
    await chatStore.sendMessage(groupId.value, {
      text,
      attachments: readyAttachments.value.map((item) => ({
        url: item.url,
        filename: item.filename,
        size: item.size,
        mimeType: item.mimeType
      }))
    })
    newMessage.value = ''
    pendingAttachments.value = []
    await scrollToBottom()
    focusComposer()
  } catch (error) {
    chatMessageError.value = error?.message || 'Failed to send message'
    console.error('Failed to send message', error)
  }
}

const activeSocketGroupId = ref(null)

watch(
  groupId,
  (id, previous) => {
    if (previous && previous !== id) {
      chatStore.disconnectFromGroup(previous)
    }
    if (!id) return
    activeSocketGroupId.value = id
    chatStore.connectToGroup(id)
    showMembersList.value = false
    loadGroup(id)
    loadChat(id, { append: false })
  },
  { immediate: true }
)

watch(memberCount, (count) => {
  if (!count) showMembersList.value = false
})

watch(chatMessages, async () => {
  if (loadingOlder.value) return
  await scrollToBottom()
})

const countCompleted = (milestone) =>
  Array.isArray(milestone?.tasks)
    ? milestone.tasks.filter((task) => task.completed).length
    : 0

const toggleTask = async (milestone, task) => {
  if (!groupId.value || !task) return
  if (togglingTaskId.value === task.id) return

  errorMessage.value = ''
  const previous = task.completed
  const nextState = !previous
  task.completed = nextState
  togglingTaskId.value = task.id

  try {
    await groupStore.setTaskCompletion(groupId.value, task.id, nextState)
  } catch (error) {
    task.completed = previous
    errorMessage.value = error?.message || 'Failed to update task'
    console.error('Failed to update task', error)
  } finally {
    togglingTaskId.value = null
  }
}
</script>

<style scoped>
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

/* Discussion board layout & chat styling */
.pane--discussion .chat-container {
  display: flex;
  flex-direction: column;
  flex: 1 1 0;
  min-height: 0;
  background: var(--white);
  border-radius: var(--radius-xl);
  border: 1.5px solid var(--border-lighter);
  box-shadow: var(--shadow-md);
  overflow: hidden;
}

.chat-header {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 1rem;
  padding: 1rem 1.5rem;
  background: var(--white);
  border-bottom: 1px solid var(--border-light);
}

.chat-messages {
  flex: 1 1 0;
  min-height: 0;
  overflow-y: auto;
  padding: 1.25rem 1.5rem;
  display: flex;
  flex-direction: column;
  gap: 1rem;
  background: linear-gradient(
    180deg,
    var(--bg-lighter) 0%,
    rgba(255, 255, 255, 0.95) 30%,
    var(--white) 100%
  );
}

.message {
  display: flex;
  gap: 0.75rem;
  align-items: flex-start;
  max-width: 100%;
}

.message.own {
  flex-direction: row-reverse;
}

.message-avatar {
  width: 42px;
  height: 42px;
  border-radius: 50%;
  background: linear-gradient(135deg, var(--mint-green) 0%, var(--eucalypt) 100%);
  color: var(--white);
  display: flex;
  align-items: center;
  justify-content: center;
  font-weight: 600;
  font-size: 0.95rem;
  box-shadow: 0 6px 16px rgba(113, 163, 153, 0.35);
  flex-shrink: 0;
}

.message.own .message-avatar {
  background: linear-gradient(135deg, var(--dark-green) 0%, #018a63 100%);
  box-shadow: none;
}

.message-content {
  max-width: min(100%, 520px);
  background: var(--white);
  padding: 0.85rem 1rem;
  border-radius: 16px 16px 16px 6px;
  border: 1px solid var(--border-lighter);
  box-shadow: 0 8px 24px rgba(1, 113, 81, 0.08);
  display: flex;
  flex-direction: column;
  gap: 0.45rem;
}

.message.own .message-content {
  background: linear-gradient(135deg, var(--dark-green) 0%, #0d8a66 100%);
  color: var(--white);
  border-color: transparent;
  border-radius: 16px 6px 16px 16px;
  align-items: flex-end;
  box-shadow: 0 8px 20px rgba(1, 113, 81, 0.25);
}

.message-header {
  display: flex;
  align-items: baseline;
  justify-content: space-between;
  gap: 0.75rem;
  width: 100%;
}

.message-author {
  font-weight: 600;
  color: var(--charcoal);
  font-size: 0.95rem;
}

.message.own .message-author {
  color: var(--white);
}

.message-meta {
  display: flex;
  align-items: center;
  gap: 0.5rem;
  font-size: 0.75rem;
  color: #6c757d;
}

.message-date {
  font-weight: 500;
}

.message.own .message-meta {
  color: rgba(255, 255, 255, 0.75);
}

.message-text {
  font-size: 0.95rem;
  line-height: 1.6;
  color: inherit;
  white-space: pre-wrap;
  word-break: break-word;
}

.message-text--muted {
  color: #6c757d;
  font-style: italic;
}

.message-note {
  font-size: 0.8rem;
  background: rgba(204, 61, 85, 0.08);
  color: #c73c51;
  border-radius: 8px;
  padding: 0.35rem 0.6rem;
}

.message.own .message-note {
  background: rgba(255, 255, 255, 0.15);
  color: rgba(255, 255, 255, 0.85);
}

.message-flag {
  display: inline-flex;
  align-items: center;
  gap: 0.3rem;
  padding: 0.1rem 0.6rem;
  border-radius: 999px;
  font-size: 0.7rem;
  font-weight: 600;
  text-transform: uppercase;
  letter-spacing: 0.02em;
}

.message-flag--pending {
  background-color: rgba(255, 193, 7, 0.18);
  color: #a57200;
}

.message-flag--rejected {
  background-color: rgba(220, 53, 69, 0.18);
  color: #b91f33;
}

.message.own .message-flag--pending,
.message.own .message-flag--rejected {
  background-color: rgba(255, 255, 255, 0.25);
  color: rgba(255, 255, 255, 0.85);
}

.message-attachments {
  width: 100%;
  display: flex;
  flex-direction: column;
  gap: 0.4rem;
  align-items: flex-start;
}

.message-attachment-link {
  color: inherit;
  font-size: 0.85rem;
  display: inline-flex;
  align-items: center;
  gap: 0.4rem;
  padding: 0.35rem 0.55rem;
  border-radius: var(--radius-sm);
  background: rgba(1, 113, 81, 0.08);
}

.message-attachment-link:hover {
  text-decoration: none;
  background: rgba(1, 113, 81, 0.16);
}

.message.own .message-attachments {
  align-items: flex-end;
}

.message.own .message-attachment-link {
  background: rgba(255, 255, 255, 0.18);
}

.chat-status {
  padding: 1.5rem;
  text-align: center;
  color: #7a869a;
  font-size: 0.95rem;
  font-weight: 500;
}

.chat-attachments-preview {
  display: flex;
  flex-wrap: wrap;
  gap: 0.65rem;
  padding: 0.75rem 1.5rem;
  background: var(--bg-lighter);
  border-top: 1px solid var(--border-lighter);
}

.attachment-chip {
  display: inline-flex;
  align-items: center;
  gap: 0.5rem;
  padding: 0.4rem 0.8rem;
  border-radius: 999px;
  background: var(--white);
  border: 1.5px solid var(--border-lighter);
  box-shadow: 0 4px 12px rgba(1, 113, 81, 0.12);
  font-size: 0.85rem;
  color: var(--charcoal);
}

.attachment-chip.uploading {
  opacity: 0.7;
}

.attachment-chip.error {
  border-color: #f3c0c0;
  color: #a52727;
}

.attachment-name {
  max-width: 160px;
  white-space: nowrap;
  overflow: hidden;
  text-overflow: ellipsis;
}

.attachment-remove {
  border: none;
  background: transparent;
  color: inherit;
  cursor: pointer;
  display: inline-flex;
  align-items: center;
}

.attachment-remove:disabled {
  opacity: 0.4;
  cursor: not-allowed;
}

.chat-input {
  border-top: 1px solid var(--border-lighter);
  background: var(--white);
  padding: 1rem 1.5rem 1.5rem;
}

.chat-input-group {
  display: flex;
  align-items: flex-end;
  gap: 0.75rem;
  border: 1.5px solid var(--border-lighter);
  border-radius: var(--radius-lg);
  padding: 0.75rem 1rem;
  background: var(--bg-lighter);
}

.chat-input-field {
  flex: 1;
  border: none;
  background: transparent;
  resize: none;
  font-size: 0.95rem;
  line-height: 1.6;
  color: var(--charcoal);
  max-height: 160px;
}

.chat-input-field:focus {
  outline: none;
}

.chat-actions {
  display: flex;
  align-items: center;
  gap: 0.5rem;
}

.chat-btn {
  width: 42px;
  height: 42px;
  border-radius: 50%;
  border: none;
  display: flex;
  align-items: center;
  justify-content: center;
  font-size: 1rem;
  transition: var(--transition);
}

.chat-btn--secondary {
  background: rgba(1, 113, 81, 0.12);
  color: var(--dark-green);
}

.chat-btn--secondary:hover:not(:disabled) {
  background: rgba(1, 113, 81, 0.2);
}

.chat-btn--primary {
  background: linear-gradient(135deg, var(--dark-green) 0%, #028f68 100%);
  color: var(--white);
  box-shadow: 0 8px 18px rgba(1, 113, 81, 0.25);
}

.chat-btn--primary:hover:not(:disabled) {
  transform: translateY(-1px);
  box-shadow: 0 12px 26px rgba(1, 113, 81, 0.3);
}

.chat-btn:disabled {
  opacity: 0.55;
  cursor: not-allowed;
  transform: none;
  box-shadow: none;
}

.sr-only {
  position: absolute;
  width: 1px;
  height: 1px;
  padding: 0;
  margin: -1px;
  overflow: hidden;
  clip: rect(0, 0, 0, 0);
  border: 0;
}

.alert-error {
  margin-bottom: 1rem;
  padding: 0.75rem 1rem;
  background-color: #ffecec;
  border: 1px solid #f3c0c0;
  color: #a52727;
  border-radius: 8px;
}

.empty-state {
  padding: 1.5rem 1rem;
  text-align: center;
  color: #6c757d;
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
}

@media (max-width: 700px) {
  .chat-header {
    flex-direction: column;
    align-items: flex-start;
    gap: 0.5rem;
  }

  .chat-input {
    padding: 0.85rem 1rem 1.2rem;
  }

  .chat-input-group {
    flex-direction: column;
    align-items: stretch;
    gap: 0.65rem;
  }

  .chat-actions {
    justify-content: flex-end;
  }

  .chat-btn {
    width: 38px;
    height: 38px;
  }
}
</style>
