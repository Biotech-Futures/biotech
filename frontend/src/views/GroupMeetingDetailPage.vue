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
          Duration
          <div class="duration-input-wrapper">
            <input
              v-model.number="editDuration"
              class="edit-input duration-input"
              type="number"
              min="5"
              max="480"
              step="5"
            />
            <span class="duration-unit">min</span>
          </div>
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

      <!-- Keep Notes mounted while editing so CodeMirror/Yjs stays connected. -->
      <div v-show="!editingMeeting">
      <div class="meeting-header">
        <div>
          <h1>{{ meeting.title }}</h1>
          <p class="meeting-date">
            {{ formatMeetingDate(meeting.start_datetime) }}
          </p>
        </div>

    <div v-if="meeting.can_manage" class="meeting-actions">

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
                {{ localTimezone }}
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
              <h2>
                Mentor Summary
                <span v-if="!meeting.can_manage" class="view-only-label">
                  (view only)
                </span>
              </h2>
            </div>

            <textarea
              v-if="meeting.can_manage"
              v-model="summaryBody"
              class="note-textarea summary-textarea"
              placeholder="Write the meeting summary..."
              @blur="saveSummary"
            />

            <p v-if="meeting.can_manage" class="small-message" role="status">
              {{ savingSummary ? 'Saving...' : (summaryMessage || 'Changes save automatically') }}
            </p>

            <textarea
              v-if="!meeting.can_manage && summaryBody"
              :value="summaryBody"
              class="note-textarea summary-textarea"
              readonly
              aria-label="Mentor Summary"
            />

            <p v-if="!meeting.can_manage && !summaryBody" class="small-message">
              No summary yet.
            </p>
          </section>

        </div>
      </div>    


      </div>

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

const localTimezone = Intl.DateTimeFormat().resolvedOptions().timeZone

const meeting = ref<GroupMeeting | null>(null)

const loading = ref(true)
const errorMessage = ref('')

const noteMessage = ref('')

const summaryBody = ref('')
const savingSummary = ref(false)
const summaryMessage = ref('')
const summaryLoaded = ref(false)
let summarySaveTimer: ReturnType<typeof setTimeout> | null = null
let lastSavedSummary = ''
let summarySaveInProgress = false
const editingMeeting = ref(false)
const savingMeeting = ref(false)
const meetingMessage = ref('')

const editTitle = ref('')
const editDescription = ref('')
const editStart = ref('')
const editDuration = ref(30)
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
    summaryLoaded.value = false
    try {
      const summary = await fetchMeetingSummary(meetingId)
      summaryBody.value = summary.body || ''
    } catch {
      summaryBody.value = ''
    }
    lastSavedSummary = summaryBody.value
    summaryLoaded.value = true
  } catch (error) {
    console.error('Failed to load meeting:', error)
    errorMessage.value = 'Unable to load this meeting.'
  } finally {
    loading.value = false
  }
}

const saveSummary = async () => {
  if (!meeting.value?.can_manage || !summaryLoaded.value || summarySaveInProgress) return
  if (summarySaveTimer !== null) {
    clearTimeout(summarySaveTimer)
    summarySaveTimer = null
  }
  if (summaryBody.value === lastSavedSummary) return

  summarySaveInProgress = true
  savingSummary.value = true
  summaryMessage.value = ''

  try {
    // Serialize requests so an older response cannot overwrite newer edits.
    while (summaryBody.value !== lastSavedSummary) {
      const bodyToSave = summaryBody.value
      await updateMeetingSummary(meetingId, bodyToSave, true)
      lastSavedSummary = bodyToSave
    }
    summaryMessage.value = 'Changes saved.'
  } catch (error) {
    console.error('Failed to save summary:', error)
    summaryMessage.value = 'Unable to save summary. Please try again.'
  } finally {
    summarySaveInProgress = false
    savingSummary.value = false
  }
}

watch(summaryBody, () => {
  if (!summaryLoaded.value || !meeting.value?.can_manage) return

  summaryMessage.value = ''

  // Schedule one save every second while typing.
  // Do not reset the timer for each keystroke.
  if (summarySaveTimer === null && !summarySaveInProgress) {
    summarySaveTimer = setTimeout(() => {
      summarySaveTimer = null
      void saveSummary()
    }, 1000)
  }
})

const toLocalDateTimeInput = (dateString: string) => {
  const date = new Date(dateString)
  const offset = date.getTimezoneOffset()
  const localDate = new Date(date.getTime() - offset * 60 * 1000)

  return localDate.toISOString().slice(0, 16)
}

const startEditing = () => {
  if (!meeting.value?.can_manage) return

  editTitle.value = meeting.value.title
  editDescription.value = meeting.value.description || ''

  editStart.value = toLocalDateTimeInput(meeting.value.start_datetime)

  const startMs = new Date(meeting.value.start_datetime).getTime()
  const endMs = new Date(meeting.value.ends_datetime).getTime()

  editDuration.value = Math.round((endMs - startMs) / 60000)
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

  // Same limit as scheduling; the max="480" on the input only bounds its arrows.
  const duration = Number(editDuration.value)
  if (!Number.isInteger(duration) || duration < 5 || duration > 480) {
    meetingMessage.value = 'Duration must be between 5 and 480 minutes.'
    return
  }

  savingMeeting.value = true
  meetingMessage.value = ''

  try {
    const updated = await updateMeeting(meetingId, {
      title: editTitle.value,
      description: editDescription.value,
      start_datetime: new Date(editStart.value).toISOString(),
      ends_datetime: new Date(
        new Date(editStart.value).getTime() + editDuration.value * 60_000
      ).toISOString(),
      timezone_name: editTimezone.value,
      join_link: editJoinLink.value,
    })

    meeting.value = updated
    editingMeeting.value = false
    meetingMessage.value = 'Meeting updated.'
  } catch (error) {
    console.error('Failed to update meeting:', error)
    meetingMessage.value =
      error instanceof Error && error.message
        ? error.message
        : 'Unable to update meeting. Please try again.'
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
    name: 'group-detail',
    params: {
      id: route.params.id,
    },
    query: {
      tab: 'meetings',
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
    timeZone: localTimezone,
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
  if (summarySaveTimer !== null) clearTimeout(summarySaveTimer)
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
/* Consistent text styling for Shared Meeting Notes and Mentor Summary */
.note-textarea,
.note-editor :deep(.cm-content),
.note-editor :deep(.cm-line) {
  font-family: Arial, sans-serif;
  font-size: 16px;
  font-weight: 400;
  line-height: 1.5;
}

.duration-input-wrapper {
  position: relative;
  width: 100%;
}

.duration-input {
  width: 100%;
  box-sizing: border-box;
  padding-right: 75px;
  appearance: auto;
}

.duration-unit {
  position: absolute;
  right: 40px;
  top: 50%;
  transform: translateY(-50%);
  color: var(--text-muted);
  font-size: 14px;
  pointer-events: none;
}

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
  align-items: flex-start;
  flex-wrap: wrap;
  gap: 16px;
  margin-bottom: 28px;
}

.meeting-header > div:first-child {
  flex: 1 1 260px;
  min-width: 0;
}

.meeting-header .meeting-actions {
  display: flex;
  flex-wrap: wrap;
  gap: 12px;
  max-width: 100%;
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
  grid-template-columns: minmax(260px, 1fr) minmax(0, 1.7fr);
  gap: 18px;
  align-items: stretch;
  margin-top: 20px;
}

.meeting-left-column,
.meeting-right-column {
  min-width: 0;
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
  white-space: pre-wrap;
  overflow-wrap: anywhere;
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
/* Shared Meeting Notes: fixed initial height, resizable */
.note-editor {
  height: 250px;
  min-height: 180px;
  max-height: 70vh;
  resize: vertical;
  overflow: hidden;
  box-sizing: border-box;
  border: 1px solid #cccccc;
  border-radius: 8px;
}

.note-editor :deep(.cm-editor) {
  height: 100%;
  min-height: 0;
  padding: 6px 4px;
  border: none;
  border-radius: 8px;
  font: inherit;
}

.note-editor :deep(.cm-scroller) {
  overflow: auto;
  height: 100%;
}

.note-editor:focus-within {
  border-color: #888888;
}

.note-editor :deep(.cm-editor.cm-focused) {
  outline: none;
}

.note-editor :deep(.cm-content) {
  font-family: inherit;
  font-size: 16px;
  font-weight: 400;
  line-height: 1.5;
}

.summary-panel {
  padding: 16px 18px;
}

.summary-textarea {
  height: 230px;
  min-height: 90px;
  max-width: 100%;
  overflow-y: auto;
  overflow-x: hidden;
  resize: vertical;
  overflow-wrap: anywhere;
  box-sizing: border-box;
}

@media (max-width: 1100px) {
  .meeting-content-grid {
    grid-template-columns: 1fr;
  }
}

@media (max-width: 600px) {
  .meeting-card {
    padding: 16px;
  }

  .meeting-header {
    flex-direction: column;
    align-items: stretch;
  }

  .meeting-header > div:first-child {
    flex: 0 1 auto;
    width: 100%;
  }

  .meeting-header .meeting-actions {
    width: 100%;
  }

  .meeting-header .meeting-actions button {
    flex: 1 1 140px;
    min-width: 0;
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
  width: 100%;
  text-align: center;
  background: var(--dark-green);
  color: #ffffff;
  text-decoration: none;
  border-radius: 8px;
  transition: background 0.2s ease;
}

.join-button:hover {
  background: #015940;
  color: #ffffff;
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
  overflow-wrap: anywhere;
  word-break: break-word;
  max-width: 100%;
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

/* Edit Meeting and Cancel Meeting - same size and text */
.meeting-actions .secondary-button,
.meeting-actions .danger-button {
  width: 160px;
  max-width: 100%;
  height: 48px;
  padding: 0 12px;
  display: inline-flex;
  align-items: center;
  justify-content: center;
  box-sizing: border-box;
  white-space: nowrap;

  font-family: inherit;
  font-size: 14px;
  font-weight: 500;
  line-height: 1;
}

/* Edit Meeting form */
.edit-section {
  background: var(--white);
  color: var(--teal);
  border: 1px solid var(--border-light);
  border-radius: 12px;
  padding: 24px;
}

.edit-section label {
  display: flex;
  flex-direction: column;
  gap: 8px;
  margin-bottom: 16px;
  font-size: 14px;
  font-weight: 600;
}

.edit-section .edit-input,
.edit-section .note-textarea {
  width: 100%;
  box-sizing: border-box;
  padding: 12px;
  background: var(--white);
  color: var(--teal);
  border: 1px solid var(--border-light);
  border-radius: 8px;
  font: inherit;
}

.edit-section .edit-input:focus,
.edit-section .note-textarea:focus {
  outline: 2px solid var(--dark-green);
  outline-offset: 1px;
}

.edit-section .edit-actions {
  display: flex;
  justify-content: flex-end;
  gap: 12px;
}

.edit-section .edit-actions button:last-child {
  background: var(--dark-green);
  border: 1px solid var(--dark-green);
  color: #ffffff;
}

.edit-section .edit-actions button:last-child:hover {
  background: #015940;
}

/* ===================================
   Meeting Detail - Dark Mode Fixes
   =================================== */

/* Meeting description */
:global(html[data-theme='dark'] .meeting-description) {
  color: #c8d5d1 !important;
}

/* Meeting date and time */
:global(html[data-theme='dark'] .meeting-date),
:global(html[data-theme='dark'] .meeting-time) {
  color: #aeb9b6 !important;
}

/* Shared Meeting Notes and Mentor Summary */
:global(html[data-theme='dark'] .note-textarea) {
  background: #1d2826 !important;
  color: #e6efed !important;
  border: 1px solid #3c4b47 !important;
}

/* Placeholder */
:global(html[data-theme='dark'] .note-textarea::placeholder) {
  color: #8a9a96 !important;
}

/* Focus */
:global(html[data-theme='dark'] .note-textarea:focus) {
  border-color: #017151 !important;
  outline: 1px solid #017151;
}

/* Back to Meetings */
:global(html[data-theme='dark']) .back-link {
  color: #c8d5d1 !important;
}

/* Edit Meeting form inputs */
:global(html[data-theme='dark']) .edit-section .edit-input,
:global(html[data-theme='dark']) .edit-section .note-textarea {
  background: #1d2826 !important;
  color: #e6efed !important;
  border-color: #3c4b47 !important;
}

/* Save Changes button */
:global(html[data-theme='dark']) .edit-section .edit-actions button:last-child {
  background: #017151 !important;
  color: #ffffff !important;
  border-color: #017151 !important;
}

/* Back to Meetings - dark mode */
:global(html[data-theme='dark'] .back-button) {
  color: #c8d5d1 !important;
}

:global(html[data-theme='dark'] .back-button:hover) {
  color: #ffffff !important;
}

/* Responsive meeting detail layout */
.meeting-detail-page,
.meeting-card {
  box-sizing: border-box;
  min-width: 0;
  max-width: 100%;
}

.meeting-header {
  display: flex;
  flex-wrap: wrap;
  align-items: flex-start;
  justify-content: space-between;
  gap: 16px;
}

.meeting-header > div:first-child {
  flex: 1 1 260px;
  min-width: 0;
}

.meeting-header h1 {
  overflow-wrap: anywhere;
}

.meeting-header .meeting-actions {
  display: flex;
  flex-wrap: wrap;
  gap: 12px;
  max-width: 100%;
}

.meeting-content-grid {
  display: grid;
  grid-template-columns: minmax(260px, 1fr) minmax(0, 1.7fr);
  gap: 18px;
  min-width: 0;
}

.meeting-left-column,
.meeting-right-column,
.detail-section {
  min-width: 0;
  max-width: 100%;
}

.meeting-description,
.note-textarea,
.summary-textarea {
  overflow-wrap: anywhere;
  max-width: 100%;
  box-sizing: border-box;
}

@media (max-width: 1100px) {
  .meeting-content-grid {
    grid-template-columns: minmax(0, 1fr);
  }
}

@media (max-width: 700px) {
  .meeting-card {
    padding: 16px;
  }

  .meeting-header {
    flex-direction: column;
    align-items: stretch;
  }

  .meeting-header > div:first-child {
    flex: 0 1 auto;
    width: 100%;
  }

  .meeting-header .meeting-actions {
    width: 100%;
  }

  .meeting-header .meeting-actions button {
    flex: 1 1 140px;
    min-width: 0;
  }
}

@media (max-width: 480px) {
  .meeting-header .meeting-actions {
    flex-direction: column;
  }

  .meeting-header .meeting-actions button {
    width: 100%;
    flex: 0 0 auto;
  }
}

@media (max-width: 700px) {
  .meeting-header .meeting-actions .secondary-button,
  .meeting-header .meeting-actions .danger-button {
    width: auto;
    max-width: 100%;
    flex: 1 1 140px;
  }
}

@media (max-width: 480px) {
  .meeting-header .meeting-actions .secondary-button,
  .meeting-header .meeting-actions .danger-button {
    width: 100%;
    flex: 0 0 auto;
  }
}

.view-only-label {
  font-size: 13px;
  font-weight: 400;
  color: #888888;
  margin-left: 6px;
}

/* Shared Meeting Notes text in dark mode */
:global(html[data-theme='dark']) .note-editor :deep(.cm-editor),
:global(html[data-theme='dark']) .note-editor :deep(.cm-scroller),
:global(html[data-theme='dark']) .note-editor :deep(.cm-content),
:global(html[data-theme='dark']) .note-editor :deep(.cm-line) {
  color: #e6efed !important;
  caret-color: #e6efed;
}

/* Dark mode: Shared Meeting Notes cursor */
:global(html[data-theme='dark']) .note-editor :deep(.cm-cursor) {
  border-left-color: #e6efed !important;
}
</style>
