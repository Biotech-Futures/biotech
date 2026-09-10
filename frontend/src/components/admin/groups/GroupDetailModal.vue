<template>
  <FormSheet
    :model-value="modelValue"
    :title="group ? group.name : 'Group details'"
    description="Members and message history for this group."
    width="min(100vw, 640px)"
    @update:model-value="onDismiss"
    @close="onDismiss"
  >
    <div v-if="group" class="group-detail">
      <!-- Group Information view: mentor + members. Messages live behind a
           dedicated view so they don't pile up here and don't load until asked. -->
      <template v-if="view === 'info'">
        <section class="group-detail__section">
          <h3>Mentor</h3>
          <p v-if="group.mentor" class="group-detail__mentor">{{ group.mentor.name }}</p>
          <p v-else class="group-detail__muted">Unassigned</p>
        </section>

        <section class="group-detail__section">
          <h3>Members ({{ members.length }})</h3>
          <p v-if="!members.length" class="group-detail__muted">No students in this group yet.</p>
          <ul v-else class="group-detail__members">
            <li v-for="member in members" :key="member.id" class="group-detail__member">
              <div class="group-detail__member-info">
                <span class="group-detail__member-name">{{ member.name }}</span>
                <span class="group-detail__member-email">{{ member.email }}</span>
              </div>
              <button
                type="button"
                class="btn btn-sm btn-outline"
                @click="requestRemoveMember(member)"
              >
                Remove
              </button>
            </li>
          </ul>
        </section>

        <button type="button" class="btn btn-outline group-detail__view-messages" @click="showMessages">
          <i class="fas fa-comments" aria-hidden="true"></i>
          View Messages<span v-if="messagesTotal !== null"> ({{ messagesTotal }})</span>
        </button>
      </template>

      <!-- Messages view -->
      <template v-else>
        <button type="button" class="group-detail__back" @click="backToInfo">
          <i class="fas fa-arrow-left" aria-hidden="true"></i>
          Back to group information
        </button>

        <section class="group-detail__section">
          <div class="group-detail__messages-head">
            <h3>Messages{{ messagesTotal !== null ? ` (${messagesTotal})` : '' }}</h3>
          </div>

          <p v-if="messagesLoading" class="group-detail__muted">Loading messages...</p>
          <p v-else-if="messagesError" class="group-detail__error" role="alert">{{ messagesError }}</p>
          <p v-else-if="!messages.length" class="group-detail__muted">No messages in this group yet.</p>

          <ul v-else class="group-detail__messages">
            <li v-for="message in messages" :key="message.id" class="group-detail__message">
              <div class="group-detail__message-head">
                <div class="group-detail__message-sender">
                  <span class="group-detail__member-name">{{ message.sender.name || message.sender.email }}</span>
                  <span class="group-detail__member-email">{{ message.sender.email }}</span>
                </div>
                <div class="group-detail__message-meta">
                  <span v-if="message.sender.role" class="group-detail__role-badge">{{ message.sender.role }}</span>
                  <span class="group-detail__muted">{{ formatMessageTime(message.sent_at) }}</span>
                  <button
                    type="button"
                    class="group-detail__message-remove"
                    aria-label="Remove message"
                    title="Remove message"
                    @click="requestRemoveMessage(message)"
                  >
                    <i class="fas fa-trash" aria-hidden="true"></i>
                  </button>
                </div>
              </div>
              <p class="group-detail__message-text">{{ messageBody(message) }}</p>
              <p v-if="message.edited_at" class="group-detail__muted">Edited {{ formatMessageTime(message.edited_at) }}</p>
            </li>
          </ul>

          <div v-if="messagesTotal && messagesTotal > messagesLimit" class="group-detail__pager">
            <button
              type="button"
              class="btn btn-sm btn-outline"
              :disabled="messagesPage <= 1 || messagesLoading"
              @click="changeMessagesPage(messagesPage - 1)"
            >
              Previous
            </button>
            <span class="group-detail__muted">
              Page {{ messagesPage }} of {{ Math.max(1, Math.ceil(messagesTotal / messagesLimit)) }}
            </span>
            <button
              type="button"
              class="btn btn-sm btn-outline"
              :disabled="!messagesHasMore || messagesLoading"
              @click="changeMessagesPage(messagesPage + 1)"
            >
              Next
            </button>
          </div>
        </section>
      </template>
    </div>
  </FormSheet>

  <ConfirmDialog
    :model-value="memberToRemove !== null"
    title="Remove student"
    :message="removeMemberMessage"
    confirm-label="Remove"
    busy-label="Removing..."
    variant="danger"
    :busy="removingMember"
    @confirm="confirmRemoveMember"
    @update:model-value="(value) => { if (!value) closeRemoveMember() }"
  >
    <p v-if="removeMemberError" class="group-detail__error" role="alert">{{ removeMemberError }}</p>
  </ConfirmDialog>

  <ConfirmDialog
    :model-value="messageToRemove !== null"
    title="Remove message"
    message="Remove this message from the group? This will hide it from the message history."
    confirm-label="Remove"
    busy-label="Removing..."
    variant="danger"
    :busy="removingMessage"
    @confirm="confirmRemoveMessage"
    @update:model-value="(value) => { if (!value) closeRemoveMessage() }"
  >
    <p v-if="removeMessageError" class="group-detail__error" role="alert">{{ removeMessageError }}</p>
  </ConfirmDialog>
</template>

<script setup lang="ts">
import { computed, ref, watch } from 'vue'
import FormSheet from '@/components/admin/FormSheet.vue'
import ConfirmDialog from '@/components/admin/ConfirmDialog.vue'
import {
  fetchGroupMessages,
  removeGroupMember,
  removeGroupMessage,
  type AdminGroupDetail,
  type AdminGroupMember,
  type AdminGroupMessage
} from '@/utils/adminAPI'

const props = defineProps<{
  modelValue: boolean
  group: AdminGroupDetail | null
}>()

const emit = defineEmits<{
  (e: 'update:modelValue', value: boolean): void
  (e: 'changed', groupId: AdminGroupDetail['id']): void
}>()

const onDismiss = () => emit('update:modelValue', false)

// The panel opens on the group-information view (mentor + members); messages are
// a separate view reached via "View Messages" (see below) and loaded only then.
const view = ref<'info' | 'messages'>('info')

// --- Members -------------------------------------------------------------

// Local, editable copy of the members list. We never mutate `props.group`
// directly: it's the same object reference the parent holds in its table rows,
// so writing to it would silently patch the parent's data (and trips
// vue/no-mutating-props). The parent refreshes its list off the `changed` event.
const members = ref<AdminGroupMember[]>([])
watch(
  () => props.group,
  (group) => {
    members.value = group ? [...group.members] : []
  },
  { immediate: true }
)

// Removal is confirmed through the app's ConfirmDialog (consistent styling and
// accessibility with the rest of the admin area), so the click just stages the
// target and the dialog's confirm event does the work.
const memberToRemove = ref<AdminGroupMember | null>(null)
const removingMember = ref(false)
const removeMemberError = ref('')

const removeMemberMessage = computed(() => {
  const member = memberToRemove.value
  if (!member) return ''
  return `Remove ${member.name || member.email} from ${props.group?.name ?? 'this group'}?`
})

const requestRemoveMember = (member: AdminGroupMember) => {
  removeMemberError.value = ''
  memberToRemove.value = member
}

const closeRemoveMember = () => {
  if (removingMember.value) return
  memberToRemove.value = null
  removeMemberError.value = ''
}

const confirmRemoveMember = async () => {
  const member = memberToRemove.value
  if (!props.group || !member) return

  removingMember.value = true
  removeMemberError.value = ''
  try {
    await removeGroupMember(props.group.id, member.id)
    members.value = members.value.filter((m) => m.id !== member.id)
    emit('changed', props.group.id)
    memberToRemove.value = null
  } catch (err) {
    removeMemberError.value = err instanceof Error ? err.message : 'Could not remove student. Please try again.'
  } finally {
    removingMember.value = false
  }
}

// --- Messages --------------------------------------------------------------

const messages = ref<AdminGroupMessage[]>([])
const messagesTotal = ref<number | null>(null)
const messagesPage = ref(1)
const messagesLimit = ref(50)
const messagesHasMore = ref(false)
const messagesLoading = ref(false)
const messagesError = ref('')
// Whether the current group's messages have been fetched at least once, so
// re-entering the Messages view doesn't refetch needlessly.
const messagesLoaded = ref(false)

const loadMessages = async () => {
  if (!props.group) return
  messagesLoading.value = true
  messagesError.value = ''
  try {
    const data = await fetchGroupMessages(props.group.id, {
      page: messagesPage.value,
      limit: messagesLimit.value
    })
    messages.value = data.items
    messagesTotal.value = data.total
    messagesHasMore.value = data.has_more
    messagesLoaded.value = true
  } catch (err) {
    messagesError.value = err instanceof Error ? err.message : 'Failed to load messages.'
  } finally {
    messagesLoading.value = false
  }
}

const changeMessagesPage = (page: number) => {
  messagesPage.value = page
  loadMessages()
}

const showMessages = () => {
  view.value = 'messages'
  if (!messagesLoaded.value && !messagesLoading.value) loadMessages()
}

const backToInfo = () => {
  view.value = 'info'
}

// Opening the panel (or switching group) resets to the info view and clears the
// message state so the next "View Messages" fetches fresh.
watch(
  () => [props.modelValue, props.group?.id],
  ([open]) => {
    if (open && props.group) {
      view.value = 'info'
      messagesPage.value = 1
      messages.value = []
      messagesTotal.value = null
      messagesHasMore.value = false
      messagesError.value = ''
      messagesLoaded.value = false
    }
  }
)

const messageBody = (message: AdminGroupMessage): string => {
  if (message.message_type === 'gif') return '[GIF]'
  if (message.message_type === 'attachment' && message.attachments.length) {
    return `[attachment: ${message.attachments.map((a) => a.filename).join(', ')}]${message.text ? ` ${message.text}` : ''}`
  }
  return message.text
}

const messageToRemove = ref<AdminGroupMessage | null>(null)
const removingMessage = ref(false)
const removeMessageError = ref('')

const requestRemoveMessage = (message: AdminGroupMessage) => {
  removeMessageError.value = ''
  messageToRemove.value = message
}

const closeRemoveMessage = () => {
  if (removingMessage.value) return
  messageToRemove.value = null
  removeMessageError.value = ''
}

const confirmRemoveMessage = async () => {
  const message = messageToRemove.value
  if (!props.group || !message) return

  removingMessage.value = true
  removeMessageError.value = ''
  try {
    await removeGroupMessage(props.group.id, message.id)
    messageToRemove.value = null
    // Re-fetch so items / total / has_more all reconcile with the server rather
    // than trying to patch them locally (a stale has_more leaves "Next" enabled
    // and fetches an empty page). If that emptied the last page, step back one.
    await loadMessages()
    if (!messages.value.length && messagesPage.value > 1) {
      messagesPage.value -= 1
      await loadMessages()
    }
  } catch (err) {
    removeMessageError.value = err instanceof Error ? err.message : 'Could not remove message. Please try again.'
  } finally {
    removingMessage.value = false
  }
}

const formatMessageTime = (value: string): string => {
  const date = new Date(value)
  if (Number.isNaN(date.getTime())) return ''
  return new Intl.DateTimeFormat(undefined, { dateStyle: 'medium', timeStyle: 'short' }).format(date)
}
</script>

<style scoped>
.group-detail {
  display: flex;
  flex-direction: column;
  gap: 1.75rem;
}

.group-detail__section h3 {
  margin: 0 0 0.6rem;
  font-size: 0.95rem;
  color: var(--charcoal);
}

.group-detail__muted {
  color: var(--text-muted);
  font-size: 0.875rem;
}

.group-detail__error {
  color: var(--danger);
  font-size: 0.875rem;
}

.group-detail__mentor {
  font-weight: 600;
  color: var(--charcoal);
}

.group-detail__members,
.group-detail__messages {
  list-style: none;
  margin: 0;
  padding: 0;
  display: flex;
  flex-direction: column;
  gap: 0.6rem;
}

.group-detail__member {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 0.75rem;
  padding: 0.6rem 0.75rem;
  background-color: var(--bg-light);
  border-radius: 8px;
}

.group-detail__member-info {
  display: flex;
  flex-direction: column;
  min-width: 0;
}

.group-detail__member-name {
  font-weight: 600;
  color: var(--charcoal);
}

.group-detail__member-email {
  font-size: 0.8rem;
  color: var(--text-muted);
}

.group-detail__message {
  padding: 0.75rem;
  background-color: var(--bg-light);
  border-radius: 8px;
}

.group-detail__message-head {
  display: flex;
  align-items: flex-start;
  justify-content: space-between;
  gap: 0.75rem;
}

.group-detail__message-sender {
  display: flex;
  flex-direction: column;
  min-width: 0;
}

.group-detail__message-meta {
  display: flex;
  align-items: center;
  gap: 0.5rem;
  flex-shrink: 0;
}

.group-detail__role-badge {
  padding: 0.15rem 0.5rem;
  border-radius: 999px;
  background-color: var(--light-green);
  color: var(--dark-green);
  font-size: 0.7rem;
  font-weight: 600;
  text-transform: capitalize;
}

.group-detail__message-remove {
  border: none;
  background: transparent;
  color: var(--text-muted);
  cursor: pointer;
  padding: 0.25rem;
}

.group-detail__message-remove:hover {
  color: var(--danger);
}

.group-detail__message-text {
  margin: 0.5rem 0 0;
  white-space: pre-wrap;
  word-break: break-word;
  font-size: 0.9rem;
  color: var(--charcoal);
}

.group-detail__messages-head {
  display: flex;
  align-items: center;
  justify-content: space-between;
}

.group-detail__pager {
  display: flex;
  align-items: center;
  justify-content: center;
  gap: 0.75rem;
  margin-top: 0.5rem;
}

.group-detail__view-messages {
  display: inline-flex;
  align-items: center;
  justify-content: center;
  gap: 0.5rem;
  align-self: flex-start;
}

.group-detail__back {
  display: inline-flex;
  align-items: center;
  gap: 0.4rem;
  align-self: flex-start;
  padding: 0;
  border: none;
  background: transparent;
  color: var(--dark-green);
  font-size: 0.875rem;
  font-weight: 600;
  cursor: pointer;
}

.group-detail__back:hover {
  text-decoration: underline;
}
</style>
