<template>
  <FormSheet
    :model-value="modelValue"
    :title="sheetTitle"
    :description="sheetDescription"
    width="min(100vw, 640px)"
    @update:model-value="onDismiss"
    @close="onDismiss"
  >
    <div v-if="group" class="group-detail">
      <!-- Group Information view: mentor + members. Messages live behind a
           dedicated view so they don't pile up here and don't load until asked. -->
      <template v-if="view === 'info'">
        <!-- Who formed it: its members while registering, a supervisor or an admin. -->
        <section class="group-detail__section">
          <h3>Formed by</h3>
          <p class="group-detail__muted">{{ formedByLabel }}</p>
        </section>

        <section class="group-detail__section">
          <h3>Mentor</h3>
          <div
            v-if="group.mentor"
            class="group-detail__member"
          >
            <button
              type="button"
              class="group-detail__member-btn"
              @click="openMentorDetail(group.mentor)"
            >
              <div class="group-detail__member-info">
                <span class="group-detail__member-name">{{ group.mentor.name }}</span>
                <span class="group-detail__member-email">{{ group.mentor.email }}</span>
              </div>
            </button>
            <button
              type="button"
              class="btn btn-sm btn-outline"
              @click="requestRemoveMentor(group.mentor)"
            >
              Remove
            </button>
          </div>
          <p v-else class="group-detail__muted">Unassigned</p>
        </section>

        <section class="group-detail__section">
          <h3>Mutual Areas of Interest</h3>
          <div v-if="mutualInterests.length" class="group-detail__interests">
            <span
              v-for="item in mutualInterests"
              :key="item.name"
              class="group-detail__interest-tag"
            >
              {{ item.name }}
              <span class="group-detail__interest-count">({{ item.count }})</span>
            </span>
          </div>
          <p v-else class="group-detail__muted">No mutual areas of interest identified yet.</p>
        </section>

        <section class="group-detail__section">
          <div class="group-detail__members-head">
            <h3>Members ({{ members.length }})</h3>
            <button
              type="button"
              class="btn btn-sm btn-primary"
              :disabled="remainingSeats === 0"
              :title="remainingSeats === 0 ? 'This group is full' : undefined"
              @click="showAddStudents"
            >
              Add students
            </button>
          </div>
          <p v-if="!members.length" class="group-detail__muted">No students in this group yet.</p>
          <ul v-else class="group-detail__members">
            <li v-for="member in members" :key="member.id" class="group-detail__member">
              <button
                type="button"
                class="group-detail__member-btn"
                @click="openStudentDetail(member)"
              >
              <div class="group-detail__member-info">
                <span class="group-detail__member-name">{{ member.name }}</span>
                <span class="group-detail__member-email">{{ member.email }}</span>
                <span v-if="member.supervisorName" class="group-detail__member-supervisor">
                  Supervisor: {{ member.supervisorName }}
                </span>
              </div>
            </button>
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

      <!-- Add-students view: picker for ungrouped students, capped by free seats. -->
      <template v-else-if="view === 'add'">
        <button type="button" class="group-detail__back" @click="backToInfo">
          <i class="fas fa-arrow-left" aria-hidden="true"></i>
          Back to group information
        </button>
        <GroupAddStudents
          :group="group"
          :remaining="remainingSeats"
          @added="onStudentsAdded"
          @cancel="backToInfo"
        />
      </template>

      <!-- Student details view -->
      <template v-else-if="view === 'student'">
        <button type="button" class="group-detail__back" @click="backToInfo">
          <i class="fas fa-arrow-left" aria-hidden="true"></i>
          Back to group information
        </button>

        <p v-if="loadingStudent" class="group-detail__muted">Loading student details...</p>
        <p v-else-if="studentError" class="group-detail__error" role="alert">{{ studentError }}</p>
        <AdminUserDetailContent
          v-else-if="selectedStudent"
          :user="selectedStudent"
          @updated="onStudentUpdated"
        />
      </template>

      <!-- Messages view -->
      <template v-else-if="view === 'messages'">
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
            <li
              v-for="message in messages"
              :key="message.id"
              class="group-detail__message"
              :class="{ 'group-detail__message--deleted': message.deleted_at }"
            >
              <div class="group-detail__message-head">
                <div class="group-detail__message-sender">
                  <span class="group-detail__member-name">{{ message.sender.name || message.sender.email }}</span>
                  <span class="group-detail__member-email">{{ message.sender.email }}</span>
                </div>
                <div class="group-detail__message-meta">
                  <!-- Admins still see who sent it (name and email above);
                       group members see it from "Administrator". -->
                  <span
                    v-if="message.sent_as_admin"
                    class="group-detail__role-badge group-detail__role-badge--admin"
                    title="Group members see this message from Administrator"
                  >
                    Sent as Administrator
                  </span>
                  <span v-else-if="message.sender.role" class="group-detail__role-badge">{{ message.sender.role }}</span>
                  <span class="group-detail__muted">{{ formatShortDateTime(message.sent_at) }}</span>
                  <!-- A deleted message is hidden from participants but kept in
                       full here, so moderation can review it and put it back. -->
                  <button
                    v-if="message.deleted_at"
                    type="button"
                    class="btn btn-sm btn-outline"
                    :disabled="restoringMessageId === message.id"
                    @click="restoreMessage(message)"
                  >
                    {{ restoringMessageId === message.id ? 'Restoring…' : 'Restore' }}
                  </button>
                  <button
                    v-else
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
              <p v-if="messageBody(message)" class="group-detail__message-text">{{ messageBody(message) }}</p>

              <!-- Images render inline so a moderator can see what was posted;
                   anything else stays a named chip. Both open the same
                   view / download / close popup. -->
              <div v-if="message.attachments?.length" class="group-detail__attachments">
                <div
                  v-for="attachment in message.attachments"
                  :key="attachment.id"
                  class="group-detail__attachment"
                >
                  <button
                    v-if="isImage(attachment) && imageUrls[attachment.id]"
                    type="button"
                    class="group-detail__thumb-btn"
                    :title="attachment.filename"
                    @click="toggleAttachment(message.id, attachment)"
                  >
                    <img
                      :src="imageUrls[attachment.id]"
                      :alt="attachment.filename"
                      class="group-detail__thumb"
                    />
                  </button>
                  <button
                    v-else
                    type="button"
                    class="group-detail__attachment-chip"
                    :title="attachment.filename"
                    @click="toggleAttachment(message.id, attachment)"
                  >
                    <i
                      :class="isImage(attachment) ? 'fas fa-image' : 'fas fa-paperclip'"
                      aria-hidden="true"
                    ></i>
                    {{ attachment.filename }}
                  </button>

                  <div
                    v-if="openAttachmentKey === attachmentKey(message.id, attachment)"
                    class="group-detail__attachment-menu"
                  >
                    <p class="group-detail__attachment-name">{{ attachment.filename }}</p>
                    <p v-if="attachmentError" class="group-detail__attachment-error">
                      {{ attachmentError }}
                    </p>
                    <div class="group-detail__attachment-actions">
                      <button
                        type="button"
                        class="btn btn-sm btn-outline"
                        :disabled="attachmentBusy"
                        @click="attachmentAction(attachment, 'view')"
                      >
                        View
                      </button>
                      <button
                        type="button"
                        class="btn btn-sm btn-outline"
                        :disabled="attachmentBusy"
                        @click="attachmentAction(attachment, 'download')"
                      >
                        Download
                      </button>
                      <button
                        type="button"
                        class="btn btn-sm btn-outline"
                        :disabled="attachmentBusy"
                        @click="closeAttachment"
                      >
                        Close
                      </button>
                    </div>
                  </div>
                </div>
              </div>

              <p v-if="message.deleted_at" class="group-detail__deleted-note">
                <i class="fas fa-eye-slash" aria-hidden="true"></i>
                Deleted by {{ message.deleted_by || 'unknown' }} on
                {{ formatShortDateTime(message.deleted_at) }} — hidden from the group.
              </p>
              <p v-if="restoreMessageError" class="group-detail__deleted-error">{{ restoreMessageError }}</p>
              <p v-if="message.edited_at" class="group-detail__muted">Edited {{ formatShortDateTime(message.edited_at) }}</p>
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

          <form class="group-detail__composer" novalidate @submit.prevent="sendMessage">
            <label class="form-label" for="group-detail-compose">Send a message as Administrator</label>
            <textarea
              id="group-detail-compose"
              v-model="draft"
              class="form-input"
              rows="3"
              placeholder="Write a message to this group"
              :disabled="sending"
              aria-describedby="group-detail-compose-hint"
            ></textarea>
            <p id="group-detail-compose-hint" class="group-detail__muted">
              Group members see this from "Administrator". Other admins can see it was you.
            </p>
            <p v-if="sendError" class="group-detail__error" role="alert">{{ sendError }}</p>
            <p v-if="sendNotice" class="group-detail__notice" role="status">{{ sendNotice }}</p>
            <div class="group-detail__composer-actions">
              <button type="submit" class="btn btn-sm btn-primary" :disabled="!canSend">
                <i class="fas fa-paper-plane" aria-hidden="true"></i>
                <span>{{ sending ? 'Sending...' : 'Send' }}</span>
              </button>
            </div>
          </form>
        </section>
      </template>
    </div>
  </FormSheet>

  <ConfirmDialog
    :model-value="memberToRemove !== null"
    :title="memberToRemove && String(memberToRemove.role || '').toLowerCase() === 'mentor' ? 'Remove mentor' : 'Remove student'"
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
import GroupAddStudents from '@/components/admin/groups/GroupAddStudents.vue'
import AdminUserDetailContent from '@/components/admin/users/AdminUserDetailContent.vue'
import {
  fetchAdminUser,
  fetchGroupMessages,
  removeGroupMember,
  removeGroupMessage,
  restoreGroupMessage,
  sendGroupMessage,
  downloadChatAttachment,
  resolveChatAttachmentUrl,
  type AdminGroupDetail,
  type AdminGroupMember,
  type AdminGroupMessage,
  type AdminGroupMessageAttachment,
  type AdminUser,
  type MutualInterestItem
} from '@/utils/adminAPI'
import { computeMutualInterests } from '@/utils/mutualInterests'
import { formatShortDateTime } from '@/utils/date'
import { DEFAULT_GROUP_MAX_SIZE } from '@/utils/groupCapacity'
import { userName } from '@/utils/userFormat'

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
// "Add students" swaps in the ungrouped-student picker the same way.
const view = ref<'info' | 'messages' | 'add' | 'student'>('info')

const sheetTitle = computed(() => {
  if (view.value === 'student') {
    if (selectedStudent.value) return userName(selectedStudent.value)
    if (selectedStudentMember.value) return selectedStudentMember.value.name || 'Student details'
    return 'Student details'
  }
  return props.group ? props.group.name : 'Group details'
})

const sheetDescription = computed(() => {
  if (view.value === 'student') {
    return 'Account details'
  }
  return 'Members and message history for this group.'
})

// --- Student Detail ------------------------------------------------------

const selectedStudent = ref<AdminUser | null>(null)
const selectedStudentMember = ref<AdminGroupMember | null>(null)
const loadingStudent = ref(false)
const studentError = ref('')

const openStudentDetail = async (member: AdminGroupMember) => {
  view.value = 'student'
  selectedStudentMember.value = member
  selectedStudent.value = null
  studentError.value = ''
  loadingStudent.value = true
  try {
    selectedStudent.value = await fetchAdminUser(member.id)
  } catch (err) {
    studentError.value = err instanceof Error ? err.message : 'Could not load student details.'
  } finally {
    loadingStudent.value = false
  }
}

const openMentorDetail = async (member: AdminGroupMember) => {
  view.value = 'student'
  selectedStudentMember.value = member
  selectedStudent.value = null
  studentError.value = ''
  loadingStudent.value = true
  try {
    selectedStudent.value = await fetchAdminUser(member.id)
  } catch (err) {
    studentError.value = err instanceof Error ? err.message : 'Could not load mentor details.'
  } finally {
    loadingStudent.value = false
  }
}

const onStudentUpdated = (updatedUser: AdminUser) => {
  selectedStudent.value = updatedUser
}

// Who formed the group: "Members", "Supervisor (name)" or "Admin (name)".
const formedByLabel = computed(() => {
  const formed = props.group?.formedBy
  if (formed?.kind === 'members') return 'Members'
  const role = formed?.kind === 'supervisor' ? 'Supervisor' : formed?.kind === 'admin' ? 'Admin' : ''
  if (!role) return 'Not recorded'
  return formed?.name ? `${role} (${formed.name})` : role
})

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
const removingMentor = ref(false)

const removeMemberMessage = computed(() => {
  const member = memberToRemove.value
  if (!member) return ''
  const roleLabel = String(member.role || '').toLowerCase() === 'mentor' ? 'mentor' : 'student'
  return `Remove ${member.name || member.email} from ${props.group?.name ?? 'this group'}?`
})

const requestRemoveMember = (member: AdminGroupMember) => {
  removeMemberError.value = ''
  memberToRemove.value = member
}

const requestRemoveMentor = (mentor: AdminGroupMember) => {
  removeMemberError.value = ''
  memberToRemove.value = mentor
}

const closeRemoveMember = () => {
  if (removingMember.value || removingMentor.value) return
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
    const role = String(member.role || '').toLowerCase()
    if (role === 'mentor') {
      emit('changed', props.group.id)
      memberToRemove.value = null
    } else {
      members.value = members.value.filter((m) => m.id !== member.id)
      emit('changed', props.group.id)
      memberToRemove.value = null
    }
  } catch (err) {
    removeMemberError.value = err instanceof Error ? err.message : 'Could not remove member. Please try again.'
  } finally {
    removingMember.value = false
  }
}

// --- Mutual areas of interest ----------------------------------------------

const mutualInterests = computed<MutualInterestItem[]>(() => {
  const allMembers: AdminGroupMember[] = [
    ...members.value,
    ...(props.group?.mentor ? [props.group.mentor] : [])
  ]
  return computeMutualInterests(allMembers)
})

// --- Add students ----------------------------------------------------------

// Seats are derived from the local list so they stay correct after an add or
// remove in this session, before the parent's table has refreshed.
const remainingSeats = computed(() =>
  Math.max(0, DEFAULT_GROUP_MAX_SIZE - members.value.filter((m) => m.role === 'student').length)
)

const showAddStudents = () => {
  view.value = 'add'
}

const onStudentsAdded = (added: AdminUser[]) => {
  if (!props.group) return
  members.value = [
    ...members.value,
    ...added.map((student) => ({
      id: String(student.id),
      name: [student.firstName, student.lastName].filter(Boolean).join(' '),
      email: student.email ?? '',
      role: 'student',
      membershipId: null,
      interests: student.interests ? [...student.interests] : []
    }))
  ]
  emit('changed', props.group.id)
  view.value = 'info'
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

// --- Composer (sent as Administrator) ---------------------------------------

const draft = ref('')
const sending = ref(false)
const sendError = ref('')
const sendNotice = ref('')

const canSend = computed(() => Boolean(props.group) && draft.value.trim().length > 0 && !sending.value)

const resetComposer = () => {
  draft.value = ''
  sendError.value = ''
  sendNotice.value = ''
}

// A new draft makes the last outcome stale.
watch(draft, () => {
  if (draft.value) sendNotice.value = ''
})

const sendMessage = async () => {
  if (!canSend.value || !props.group) return
  sending.value = true
  sendError.value = ''
  sendNotice.value = ''
  try {
    await sendGroupMessage(props.group.id, draft.value)
    // Cleared only once the server has it, so a failure keeps the text.
    draft.value = ''
    sendNotice.value = 'Message sent.'
    // History is oldest-first: show the last page, where the new message is.
    // Re-fetched like a removal so items / total / has_more come from the server.
    messagesPage.value = Math.max(1, Math.ceil(((messagesTotal.value ?? 0) + 1) / messagesLimit.value))
    await loadMessages()
    if (!messages.value.length && messagesPage.value > 1) {
      messagesPage.value -= 1
      await loadMessages()
    }
  } catch (err) {
    sendError.value = err instanceof Error && err.message ? err.message : 'Could not send the message. Please try again.'
  } finally {
    sending.value = false
  }
}

const showMessages = () => {
  view.value = 'messages'
  if (!messagesLoaded.value && !messagesLoading.value) loadMessages()
}

const backToInfo = () => {
  view.value = 'info'
  selectedStudent.value = null
  selectedStudentMember.value = null
  studentError.value = ''
  loadingStudent.value = false
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
      // Never carry a draft over to a different group.
      resetComposer()
      selectedStudent.value = null
      selectedStudentMember.value = null
      studentError.value = ''
      loadingStudent.value = false
    }
  }
)

const messageBody = (message: AdminGroupMessage): string => {
  if (message.message_type === 'gif') return '[GIF]'
  // Attachments used to be flattened into "[attachment: name]" here. They are
  // rendered below the text instead, so moderation can see what was actually
  // posted rather than a filename.
  return message.text
}

// --- Attachments ---------------------------------------------------------

const isImage = (attachment: AdminGroupMessageAttachment): boolean =>
  (attachment.mime_type || '').toLowerCase().startsWith('image/')

/** Signed URLs, keyed by attachment id. Resolved lazily: a group's history can
 *  hold far more images than are on screen, and each URL is short-lived. */
const imageUrls = ref<Record<number, string>>({})
const imageFailed = ref<Record<number, true>>({})

const loadImage = async (attachment: AdminGroupMessageAttachment) => {
  if (imageUrls.value[attachment.id] || imageFailed.value[attachment.id]) return
  try {
    const resolved = await resolveChatAttachmentUrl(attachment.download_url)
    imageUrls.value = { ...imageUrls.value, [attachment.id]: resolved.url }
  } catch {
    imageFailed.value = { ...imageFailed.value, [attachment.id]: true }
  }
}

watch(
  messages,
  (list) => {
    for (const message of list) {
      for (const attachment of message.attachments ?? []) {
        if (isImage(attachment)) void loadImage(attachment)
      }
    }
  },
  { deep: false }
)

// Which attachment's action popup is open, as `${messageId}:${attachmentId}`.
const openAttachmentKey = ref<string | null>(null)
const attachmentBusy = ref(false)
const attachmentError = ref('')

const attachmentKey = (messageId: string, attachment: AdminGroupMessageAttachment) =>
  `${messageId}:${attachment.id}`

const toggleAttachment = (messageId: string, attachment: AdminGroupMessageAttachment) => {
  const key = attachmentKey(messageId, attachment)
  attachmentError.value = ''
  openAttachmentKey.value = openAttachmentKey.value === key ? null : key
}

const closeAttachment = () => {
  openAttachmentKey.value = null
  attachmentError.value = ''
  attachmentBusy.value = false
}

/** View opens the file inline in a new tab; download saves it. Both go through
 *  a freshly signed URL rather than the cached one, which may have expired. */
const attachmentAction = async (
  attachment: AdminGroupMessageAttachment,
  mode: 'view' | 'download'
) => {
  attachmentBusy.value = true
  attachmentError.value = ''
  try {
    if (mode === 'view') {
      const resolved = await resolveChatAttachmentUrl(attachment.download_url)
      window.open(resolved.url, '_blank', 'noopener,noreferrer')
    } else {
      await downloadChatAttachment(attachment.download_url, attachment.filename)
    }
    closeAttachment()
  } catch (error) {
    attachmentError.value =
      error instanceof Error ? error.message : 'The attachment could not be opened.'
    attachmentBusy.value = false
  }
}

const restoringMessageId = ref<string | null>(null)
const restoreMessageError = ref('')

const restoreMessage = async (message: AdminGroupMessage) => {
  restoringMessageId.value = message.id
  restoreMessageError.value = ''
  try {
    await restoreGroupMessage(message.group_id, message.id)
    await loadMessages()
    emit('changed', props.group!.id)
  } catch (error) {
    restoreMessageError.value =
      error instanceof Error ? error.message : 'The message could not be restored.'
  } finally {
    restoringMessageId.value = null
  }
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
  color: var(--teal);
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
  color: var(--teal);
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

.group-detail__member-btn {
  display: flex;
  align-items: center;
  text-align: left;
  background: transparent;
  border: none;
  padding: 0;
  cursor: pointer;
  flex: 1;
  min-width: 0;
  font: inherit;
}

.group-detail__member-btn:hover .group-detail__member-name {
  text-decoration: underline;
}

.group-detail__member-info {
  display: flex;
  flex-direction: column;
  min-width: 0;
}

.group-detail__member-name {
  font-weight: 600;
  color: var(--teal);
}

.group-detail__member-email {
  font-size: 0.8rem;
  color: var(--text-muted);
}

.group-detail__member-supervisor {
  font-size: 0.75rem;
  color: var(--text-muted);
  margin-top: 0.25rem;
}

.group-detail__mentor-card {
  display: flex;
  align-items: center;
  text-align: left;
  background-color: var(--bg-light);
  border: none;
  border-radius: 8px;
  padding: 0.6rem 0.75rem;
  cursor: pointer;
  width: 100%;
}

.group-detail__mentor-card:hover .group-detail__member-name {
  text-decoration: underline;
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
  color: var(--teal);
}

.group-detail__members-head {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 0.75rem;
  margin-bottom: 0.6rem;
}

.group-detail__members-head h3 {
  margin: 0;
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

/* Distinct from member roles: sent from the admin panel, not by a member. */
.group-detail__role-badge--admin {
  background-color: var(--teal);
  color: var(--white);
  text-transform: none;
}

.group-detail__composer {
  display: flex;
  flex-direction: column;
  gap: 0.4rem;
  margin-top: 1rem;
  padding-top: 1rem;
  border-top: 1px solid var(--border-light);
}

.group-detail__composer textarea {
  resize: vertical;
}

.group-detail__composer-actions {
  display: flex;
  justify-content: flex-end;
}

.group-detail__notice {
  color: var(--dark-green);
  font-size: 0.875rem;
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

.group-detail__attachments {
  display: flex;
  flex-wrap: wrap;
  gap: 0.5rem;
  margin-top: 0.4rem;
}

.group-detail__attachment {
  position: relative;
}

.group-detail__thumb-btn {
  padding: 0;
  border: 1px solid var(--border-light);
  border-radius: 8px;
  background: none;
  cursor: pointer;
  overflow: hidden;
  line-height: 0;
}

.group-detail__thumb {
  display: block;
  width: 140px;
  height: 140px;
  object-fit: cover;
}

.group-detail__attachment-chip {
  display: inline-flex;
  align-items: center;
  gap: 0.4rem;
  max-width: 16rem;
  padding: 0.25rem 0.6rem;
  border: 1px solid var(--border-light);
  border-radius: 999px;
  background-color: var(--bg-light);
  color: var(--charcoal);
  font-family: inherit;
  font-size: 0.8rem;
  cursor: pointer;
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
}

.group-detail__attachment-menu {
  position: absolute;
  top: calc(100% + 0.35rem);
  left: 0;
  z-index: 20;
  min-width: 15rem;
  padding: 0.6rem;
  border: 1px solid var(--border-light);
  border-radius: 8px;
  background-color: var(--surface-elevated);
  box-shadow: 0 8px 24px var(--shadow);
}

.group-detail__attachment-name {
  margin: 0 0 0.45rem;
  color: var(--charcoal);
  font-size: 0.8rem;
  font-weight: 600;
  word-break: break-all;
}

.group-detail__attachment-error {
  margin: 0 0 0.45rem;
  color: var(--danger);
  font-size: 0.75rem;
}

.group-detail__attachment-actions {
  display: flex;
  gap: 0.35rem;
}

.group-detail__message--deleted {
  border-left: 3px solid var(--border-light);
  background-color: var(--bg-light);
  opacity: 0.85;
}

.group-detail__deleted-note {
  display: flex;
  align-items: center;
  gap: 0.35rem;
  margin: 0.35rem 0 0;
  color: var(--text-muted);
  font-size: 0.75rem;
  font-style: italic;
}

.group-detail__deleted-error {
  margin: 0.35rem 0 0;
  color: var(--danger);
  font-size: 0.75rem;
}

.group-detail__interests {
  display: flex;
  flex-wrap: wrap;
  gap: 0.5rem;
}

.group-detail__interest-tag {
  display: inline-flex;
  align-items: center;
  gap: 0.3rem;
  padding: 0.25rem 0.65rem;
  border-radius: 999px;
  background-color: var(--light-green);
  color: var(--dark-green);
  font-size: 0.8rem;
  font-weight: 500;
}

.group-detail__interest-count {
  font-weight: 500;
  opacity: 0.85;
}
</style>
