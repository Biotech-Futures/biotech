<template>
  <div class="meeting-detail-page">
    <div class="back-actions">
      <button class="back-button" @click="goBack">
        ← Back to Meetings
      </button>
    </div>

    <div v-if="loading" class="status-message">
      Loading meeting...
    </div>

    <div v-else-if="errorMessage" class="status-message error">
      {{ errorMessage }}
    </div>

    <div v-else-if="meeting" class="meeting-card">
      <div class="meeting-header">
        <div>
          <h1>{{ meeting.title }}</h1>
          <p class="meeting-date">
            {{ formatMeetingDate(meeting.start_datetime) }}
          </p>
        </div>

    <div v-if="meeting.can_manage" class="meeting-actions">
      <span class="manage-badge">
        You can manage
      </span>

      <button
        v-if="!editingMeeting"
        class="secondary-button"
        @click="startEditing"
      >
        Edit Meeting
      </button>
      <button
        v-if="!editingMeeting"
        class="danger-button"
        :disabled="cancellingMeeting"
        @click="handleCancelMeeting"
      >
        {{ cancellingMeeting ? 'Cancelling...' : 'Cancel Meeting' }}
      </button>
    </div>
      </div>

      <div class="meeting-content-grid">

        <!-- LEFT COLUMN -->
        <div class="meeting-left-column">

          <section class="detail-section meeting-info-panel">
            <h2>{{ meeting.title }}</h2>

            <p v-if="meeting.description" class="meeting-description">
              {{ meeting.description }}
            </p>

            <div class="meeting-meta">
              <p>
                <strong>Starts:</strong>
                {{ formatMeetingDate(meeting.start_datetime) }}
              </p>

              <p>
                <strong>Ends:</strong>
                {{ formatMeetingDate(meeting.ends_datetime) }}
              </p>

              <p>
                <strong>Timezone:</strong>
                {{ meeting.timezone_name || 'UTC' }}
              </p>
            </div>

            <a
              v-if="meeting.join_link"
              :href="meeting.join_link"
              target="_blank"
              rel="noopener noreferrer"
              class="join-button"
            >
              Join Meeting
            </a>
          </section>

        </div>

        <!-- RIGHT COLUMN -->
        <div class="meeting-right-column">

          <section class="detail-section shared-notes-panel">
            <div class="section-heading">
              <h2>Shared Meeting Notes</h2>
            </div>

            <div ref="editorHost" class="note-editor" />

            <p v-if="otherUserEditing" class="small-message">
              Another group member is editing...
            </p>

            <p v-if="noteMessage" class="small-message">
              {{ noteMessage }}
            </p>
          </section>

          <section class="detail-section summary-panel">
            <div class="section-heading">
              <h2>Mentor Summary</h2>

              <button
                v-if="meeting.can_manage"
                class="secondary-button"
                :disabled="savingSummary"
                @click="saveSummary"
              >
                {{ savingSummary ? 'Saving...' : 'Save Summary' }}
              </button>
            </div>

            <textarea
              v-if="meeting.can_manage"
              v-model="summaryBody"
              class="note-textarea summary-textarea"
              placeholder="Write the meeting summary..."
            />

            <p
              v-else-if="summaryBody"
              class="summary-text"
            >
              {{ summaryBody }}
            </p>

            <p
              v-else
              class="small-message"
            >
              No summary yet.
            </p>
          </section>

        </div>
      </div>    
        <section v-if="editingMeeting" class="edit-section">
        <h2>Edit Meeting</h2>

        <label>
          Title
          <input
            v-model="editTitle"
            class="edit-input"
            type="text"
          />
        </label>

        <label>
          Description
          <textarea
            v-model="editDescription"
            class="note-textarea"
            rows="4"
          />
        </label>

        <label>
          Start
          <input
            v-model="editStart"
            class="edit-input"
            type="datetime-local"
          />
        </label>

        <label>
          End
          <input
            v-model="editEnd"
            class="edit-input"
            type="datetime-local"
          />
        </label>

        <label>
          Timezone
          <input
            v-model="editTimezone"
            class="edit-input"
            type="text"
          />
        </label>

        <label>
          Join Link
          <input
            v-model="editJoinLink"
            class="edit-input"
            type="url"
          />
        </label>

        <div class="edit-actions">
          <button
            class="secondary-button"
            :disabled="savingMeeting"
            @click="cancelEditing"
          >
            Cancel
          </button>

          <button
            class="secondary-button"
            :disabled="savingMeeting"
            @click="saveMeeting"
          >
            {{ savingMeeting ? 'Saving...' : 'Save Changes' }}
          </button>
        </div>
      </section>

      <p v-if="meetingMessage" class="small-message">
        {{ meetingMessage }}
      </p>
    </div>
  </div>
</template>

<script setup lang="ts">
import { onMounted, onBeforeUnmount, ref, watch } from 'vue'
import { useRoute, useRouter } from 'vue-router'
import * as Y from 'yjs'
import * as awarenessProtocol from 'y-protocols/awareness'
import { EditorView, minimalSetup } from 'codemirror'
import { EditorState } from '@codemirror/state'
import { placeholder } from '@codemirror/view'
import { yCollab } from 'y-codemirror.next'

import { useAuthStore } from '@/stores/auth'
import {
  fetchMeetingById,
  fetchMeetingSummary,
  updateMeeting,
  cancelMeeting,
  updateMeetingSummary,
  type GroupMeeting,
} from '@/utils/meetingsAPI'

const route = useRoute()
const router = useRouter()

const meeting = ref<GroupMeeting | null>(null)

const loading = ref(true)
const errorMessage = ref('')

const noteMessage = ref('')

const summaryBody = ref('')
const savingSummary = ref(false)
const summaryMessage = ref('')
const editingMeeting = ref(false)
const savingMeeting = ref(false)
const meetingMessage = ref('')

const editTitle = ref('')
const editDescription = ref('')
const editStart = ref('')
const editEnd = ref('')
const editTimezone = ref('')
const editJoinLink = ref('')
const cancellingMeeting = ref(false)

const meetingId = Number(route.params.meetingId)

const formErrors = ref({
  title: '',
  start: '',
  end: '',
  timezone: '',
  joinLink: '',
})

const noteSocket = ref<WebSocket | null>(null)
const otherUserEditing = ref(false)

// ---------------------------------------------------------------------------
// Shared live note (Yjs + CodeMirror)
//
// The note is a Y.Text bound to a CodeMirror editor by yCollab, which also
// draws other members' cursors from the Yjs awareness state. Two kinds of
// frames go over the meeting socket:
//   - document updates: merged and persisted by the server, then relayed
//   - awareness updates (name, colour, cursor): relayed only, never stored
// ---------------------------------------------------------------------------

const REMOTE_ORIGIN = 'remote'
const UPDATE_FLUSH_MS = 200
const RECONNECT_MS = 2000
// Close codes the server uses for "bad meeting id" / "not allowed".
const FATAL_CLOSE_CODES = [4400, 4403]
const CURSOR_COLORS = ['#30bced', '#6eeb83', '#ffbc42', '#ee6352', '#9b5de5', '#00bbf9']

const auth = useAuthStore()

const ydoc = new Y.Doc()
// Must match the root name the backend uses: doc["note"].
const ytext = ydoc.getText('note')
const awareness = new awarenessProtocol.Awareness(ydoc)

// Same user, same colour, on every device.
const cursorColor = CURSOR_COLORS[(auth.user?.id ?? 0) % CURSOR_COLORS.length]
awareness.setLocalStateField('user', {
  name: auth.user?.first_name || 'Member',
  color: cursorColor,
  // Selection highlight: the same colour at ~20% opacity.
  colorLight: `${cursorColor}33`,
})

const editorHost = ref<HTMLDivElement | null>(null)
let editorView: EditorView | null = null

let pendingUpdates: Uint8Array[] = []
let flushTimer: number | undefined
let reconnectTimer: number | undefined
let pageClosed = false

const toBase64 = (bytes: Uint8Array) => {
  let binary = ''
  for (let i = 0; i < bytes.length; i++) {
    binary += String.fromCharCode(bytes[i])
  }
  return btoa(binary)
}

const fromBase64 = (text: string) =>
  Uint8Array.from(atob(text), (char) => char.charCodeAt(0))

// The editor host only exists once the meeting has loaded. yCollab keeps the
// editor in step with ytext from then on, including a sync frame that
// arrived before the editor was created.
watch(editorHost, (el) => {
  if (!el || editorView) return

  editorView = new EditorView({
    parent: el,
    state: EditorState.create({
      doc: ytext.toString(),
      extensions: [
        minimalSetup,
        EditorView.lineWrapping,
        placeholder('Write shared meeting notes here...'),
        yCollab(ytext, awareness),
        EditorView.domEventHandlers({
          focus: () => sendNotePresence(true),
          blur: () => sendNotePresence(false),
        }),
      ],
    }),
  })
})

const sendAwareness = (clientIds: number[]) => {
  if (noteSocket.value?.readyState !== WebSocket.OPEN) return

  const update = awarenessProtocol.encodeAwarenessUpdate(awareness, clientIds)
  noteSocket.value.send(
    JSON.stringify({
      type: 'awareness',
      update: toBase64(update),
    })
  )
}

// Fires on local cursor moves and on the built-in 15s keep-alive renewal.
awareness.on(
  'update',
  (
    changes: { added: number[]; updated: number[]; removed: number[] },
    origin: unknown
  ) => {
    if (origin === REMOTE_ORIGIN) return
    sendAwareness(changes.added.concat(changes.updated, changes.removed))
  }
)

const flushNoteUpdates = () => {
  flushTimer = undefined

  if (!pendingUpdates.length) return
  // Kept until the socket is back; the reconnect sends the full state.
  if (noteSocket.value?.readyState !== WebSocket.OPEN) return

  const merged = Y.mergeUpdates(pendingUpdates)
  pendingUpdates = []

  noteSocket.value.send(
    JSON.stringify({
      type: 'update',
      update: toBase64(merged),
    })
  )
}

ydoc.on('update', (update: Uint8Array, origin: unknown) => {
  if (origin === REMOTE_ORIGIN) return

  pendingUpdates.push(update)

  if (flushTimer === undefined) {
    flushTimer = window.setTimeout(flushNoteUpdates, UPDATE_FLUSH_MS)
  }
})

const connectNoteSocket = () => {
  const meetingId = Number(route.params.meetingId)
  if (!meetingId) return

  const protocol = window.location.protocol === 'https:' ? 'wss' : 'ws'
  const host = import.meta.env.VITE_API_BASE_URL
    ? new URL(import.meta.env.VITE_API_BASE_URL).host
    : 'localhost:8000'

  const socket = new WebSocket(
    `${protocol}://${host}/ws/meetings/${meetingId}/note/`
  )

  socket.onopen = () => {
    noteMessage.value = ''

    // Push anything typed while offline. Updates are idempotent, so
    // resending what the server already has is harmless. An empty doc
    // encodes to 2 bytes -- nothing worth sending.
    const state = Y.encodeStateAsUpdate(ydoc)
    pendingUpdates = []

    if (state.length > 2) {
      socket.send(
        JSON.stringify({
          type: 'update',
          update: toBase64(state),
        })
      )
    }

    // Show our cursor to everyone already in the room.
    sendAwareness([ydoc.clientID])
  }

  socket.onmessage = (event) => {
    try {
      const data = JSON.parse(event.data)

      if (
        (data.event === 'note.sync' || data.event === 'note.update') &&
        typeof data.update === 'string'
      ) {
        Y.applyUpdate(ydoc, fromBase64(data.update), REMOTE_ORIGIN)
      }

      if (data.event === 'note.awareness' && typeof data.update === 'string') {
        awarenessProtocol.applyAwarenessUpdate(
          awareness,
          fromBase64(data.update),
          REMOTE_ORIGIN
        )
      }

      if (data.event === 'note.peer_joined') {
        // A newcomer has no cursors yet; send ours instead of making them
        // wait for our next move or keep-alive.
        sendAwareness([ydoc.clientID])
      }

      if (data.event === 'note.presence') {
        otherUserEditing.value = Boolean(data.editing)
      }
    } catch (error) {
      console.error('Invalid meeting note socket message:', error)
    }
  }

  socket.onclose = (event) => {
    if (noteSocket.value === socket) {
      noteSocket.value = null
    }

    if (pageClosed) return

    if (FATAL_CLOSE_CODES.includes(event.code)) {
      noteMessage.value = 'You do not have access to this note.'
      return
    }

    noteMessage.value = 'Connection lost. Reconnecting...'
    reconnectTimer = window.setTimeout(connectNoteSocket, RECONNECT_MS)
  }

  noteSocket.value = socket
}

const sendNotePresence = (editing: boolean) => {
  if (noteSocket.value?.readyState === WebSocket.OPEN) {
    noteSocket.value.send(
      JSON.stringify({
        type: 'presence',
        editing,
      })
    )
  }
}

const loadMeeting = async () => {
  loading.value = true
  errorMessage.value = ''

  try {
    meeting.value = await fetchMeetingById(meetingId)

    // The note itself arrives over the socket (note.sync), not REST.
    try {
      const summary = await fetchMeetingSummary(meetingId)
      summaryBody.value = summary.body || ''
    } catch {
      summaryBody.value = ''
    }
  } catch (error) {
    console.error('Failed to load meeting:', error)
    errorMessage.value = 'Unable to load this meeting.'
  } finally {
    loading.value = false
  }
}

const saveSummary = async () => {
  if (!meeting.value?.can_manage) {
    return
  }

  savingSummary.value = true
  summaryMessage.value = ''

  try {
    const updated = await updateMeetingSummary(
      meetingId,
      summaryBody.value,
      false
    )

    summaryBody.value = updated.body || ''
    summaryMessage.value = 'Summary saved.'
  } catch (error) {
    console.error('Failed to save summary:', error)
    summaryMessage.value = 'Unable to save summary. Please try again.'
  } finally {
    savingSummary.value = false
  }
}

const toLocalDateTimeInput = (dateString: string) => {
  const date = new Date(dateString)
  const offset = date.getTimezoneOffset()
  const localDate = new Date(date.getTime() - offset * 60 * 1000)

  return localDate.toISOString().slice(0, 16)
}

const startEditing = () => {
  if (!meeting.value?.can_manage) {
    return
  }

  editTitle.value = meeting.value.title
  editDescription.value = meeting.value.description || ''
  editStart.value = toLocalDateTimeInput(meeting.value.start_datetime)
  editEnd.value = toLocalDateTimeInput(meeting.value.ends_datetime)
  editTimezone.value = meeting.value.timezone_name || 'UTC'
  editJoinLink.value = meeting.value.join_link || ''

  meetingMessage.value = ''
  editingMeeting.value = true
}

const cancelEditing = () => {
  editingMeeting.value = false
  meetingMessage.value = ''
}

const saveMeeting = async () => {
  if (!meeting.value?.can_manage) {
    return
  }

  savingMeeting.value = true
  meetingMessage.value = ''

  try {
    const updated = await updateMeeting(meetingId, {
      title: editTitle.value,
      description: editDescription.value,
      start_datetime: new Date(editStart.value).toISOString(),
      ends_datetime: new Date(editEnd.value).toISOString(),
      timezone_name: editTimezone.value,
      join_link: editJoinLink.value,
    })

    meeting.value = updated
    editingMeeting.value = false
    meetingMessage.value = 'Meeting updated.'
  } catch (error) {
    console.error('Failed to update meeting:', error)
    meetingMessage.value = 'Unable to update meeting. Please try again.'
  } finally {
    savingMeeting.value = false
  }
}

const handleCancelMeeting = async () => {
  if (!meeting.value?.can_manage) {
    return
  }

  const confirmed = window.confirm(
    'Are you sure you want to cancel this meeting?'
  )

  if (!confirmed) {
    return
  }

  cancellingMeeting.value = true

  try {
    await cancelMeeting(meetingId)

    await router.push({
      name: 'group-meetings',
      params: { id: route.params.id },
    })
  } catch (error) {
    console.error('Failed to cancel meeting:', error)
    meetingMessage.value = 'Unable to cancel meeting. Please try again.'
  } finally {
    cancellingMeeting.value = false
  }
}

const goBack = () => {
  router.push({
    name: 'group-meetings',
    params: {
      id: route.params.id,
    },
  })
}

const goBackToChat = () => {
  router.push({
    name: 'group-detail',
    params: {
      id: route.params.id,
    },
  })
}

const formatMeetingDate = (dateString: string) => {
  const date = new Date(dateString)

  return new Intl.DateTimeFormat('en-AU', {
    dateStyle: 'medium',
    timeStyle: 'short',
  }).format(date)
}

onMounted(loadMeeting)
onMounted(() => {
  connectNoteSocket()
})

onBeforeUnmount(() => {
  pageClosed = true

  window.clearTimeout(reconnectTimer)
  window.clearTimeout(flushTimer)
  // Send the last keystrokes that were still waiting on the flush timer.
  flushNoteUpdates()
  // Remove our cursor right away instead of letting it time out (~30s).
  // Must run while the socket is still open.
  awarenessProtocol.removeAwarenessStates(awareness, [ydoc.clientID], 'local')

  if (noteSocket.value) {
    noteSocket.value.close()
    noteSocket.value = null
  }

  editorView?.destroy()
  editorView = null
  awareness.destroy()
  ydoc.destroy()
})
</script>

<style scoped>
.meeting-detail-page {
  max-width: 1080px;
  margin: 0 auto;
  padding: 48px 32px;
}

.meeting-actions {
  display: flex;
  align-items: center;
  gap: 12px;
}

.edit-section {
  border-top: 1px solid #eeeeee;
  padding-top: 24px;
  margin-top: 24px;
  display: flex;
  flex-direction: column;
  gap: 16px;
}

.edit-section label {
  display: flex;
  flex-direction: column;
  gap: 6px;
  font-weight: 600;
}

.edit-input {
  padding: 12px;
  border: 1px solid #cccccc;
  border-radius: 8px;
  font: inherit;
}

.edit-actions {
  display: flex;
  justify-content: flex-end;
  gap: 12px;
}

.back-button {
  border: none;
  background: none;
  cursor: pointer;
  font-size: 15px;
  margin-bottom: 24px;
  padding: 0;
}

.back-actions {
  display: flex;
  align-items: center;
  gap: 10px;
  margin-bottom: 16px;
}

.meeting-card {
  border: 1px solid #dddddd;
  border-radius: 12px;
  padding: 28px;
  background: white;
}

.meeting-header {
  display: flex;
  justify-content: space-between;
  gap: 24px;
  align-items: flex-start;
  margin-bottom: 28px;
}

.meeting-header h1 {
  margin: 0 0 8px;
}

.meeting-date {
  margin: 0;
  color: #666666;
}

.manage-badge {
  background: #f1f1f1;
  border-radius: 999px;
  padding: 9px 14px;
  white-space: nowrap;
}

.detail-section {
  border-top: 1px solid #eeeeee;
  padding-top: 24px;
  margin-top: 24px;
}

.detail-section h2 {
  margin-top: 0;
  font-size: 20px;
}

.meeting-content-grid {
  display: grid;
  grid-template-columns: 34% 1fr;
  gap: 18px;
  align-items: stretch;
  margin-top: 20px;
}

.meeting-left-column,
.meeting-right-column {
  display: flex;
  flex-direction: column;
  gap: 14px;
}

.meeting-info-panel {
  padding: 18px;
}

.meeting-info-panel h2 {
  margin: 0 0 12px;
  font-size: 20px;
}

.meeting-description {
  margin-bottom: 16px;
  color: #555;
}

.meeting-meta p {
  margin: 6px 0;
}

.goals-panel {
  padding: 16px 18px;
}

.shared-notes-panel {
  padding: 18px;
}

/* CodeMirror builds its DOM at runtime, so scoped styles need :deep(). */
.note-editor :deep(.cm-editor) {
  min-height: 250px;
  padding: 6px 4px;
  border: 1px solid #cccccc;
  border-radius: 8px;
  font: inherit;
}

.note-editor :deep(.cm-editor.cm-focused) {
  outline: none;
  border-color: #888888;
}

.note-editor :deep(.cm-content) {
  font-family: inherit;
}

.summary-panel {
  padding: 16px 18px;
}

.summary-textarea {
  min-height: 90px;
}

.join-button {
  display: block;
  width: 100%;
  margin-top: 18px;
  text-align: center;
}

@media (max-width: 900px) {
  .meeting-content-grid {
    grid-template-columns: 1fr;
  }
}

.section-heading {
  display: flex;
  justify-content: space-between;
  align-items: center;
  gap: 16px;
}

.join-button {
  display: inline-block;
  margin-top: 12px;
  padding: 12px 18px;
  background: #222222;
  color: white;
  text-decoration: none;
  border-radius: 8px;
}

.secondary-button {
  border: 1px solid #cccccc;
  background: white;
  border-radius: 8px;
  padding: 9px 14px;
  cursor: pointer;
}

.secondary-button:disabled {
  cursor: not-allowed;
  opacity: 0.6;
}

.note-textarea {
  width: 100%;
  box-sizing: border-box;
  padding: 14px;
  border: 1px solid #cccccc;
  border-radius: 8px;
  font: inherit;
  resize: vertical;
}

.status-message {
  padding: 30px 0;
}

.error {
  color: #a40000;
}

.small-message {
  margin-top: 10px;
  color: #666666;
  font-size: 14px;
}

.summary-text {
  white-space: pre-wrap;
}
.danger-button {
  padding: 10px 16px;
  border: 1px solid #d32f2f;
  border-radius: 8px;
  background: transparent;
  color: #d32f2f;
  cursor: pointer;
  font: inherit;
}

.danger-button:hover {
  background: #d32f2f;
  color: white;
}

.danger-button:disabled {
  opacity: 0.6;
  cursor: not-allowed;
}
</style>
