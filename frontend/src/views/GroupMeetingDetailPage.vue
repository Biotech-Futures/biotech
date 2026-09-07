<template>
  <div class="meeting-detail-page">
    <button class="back-button" @click="goBack">
      ← Back to Meetings
    </button>

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

      <section v-if="meeting.description" class="detail-section">
        <h2>Description</h2>
        <p>{{ meeting.description }}</p>
      </section>

      <section v-if="meeting.agenda" class="detail-section">
        <h2>Agenda</h2>
        <p>{{ meeting.agenda }}</p>
      </section>

      <section class="detail-section">
        <h2>Meeting Details</h2>

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

      <section class="detail-section">
        <div class="section-heading">
          <h2>Shared Note</h2>

          <button
            class="secondary-button"
            :disabled="savingNote"
            @click="saveNote"
          >
            {{ savingNote ? 'Saving...' : 'Save Note' }}
          </button>
        </div>

        <textarea
          v-model="noteBody"
          class="note-textarea"
          rows="8"
          placeholder="Write shared meeting notes here..."
        />

        <p v-if="noteMessage" class="small-message">
          {{ noteMessage }}
        </p>
      </section>

      <section class="detail-section">
        <div class="section-heading">
          <h2>Summary</h2>

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
          class="note-textarea"
          rows="6"
          placeholder="Write a meeting summary..."
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

        <p v-if="summaryMessage" class="small-message">
          {{ summaryMessage }}
        </p>
      </section>

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
          Agenda
          <textarea
            v-model="editAgenda"
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
import { onMounted, ref } from 'vue'
import { useRoute, useRouter } from 'vue-router'

import {
  fetchMeetingById,
  fetchMeetingNote,
  fetchMeetingSummary,
  updateMeeting,
  cancelMeeting,
  updateMeetingNote,
  updateMeetingSummary,
  type GroupMeeting,
} from '@/utils/meetingsAPI'

const route = useRoute()
const router = useRouter()

const meeting = ref<GroupMeeting | null>(null)

const loading = ref(true)
const errorMessage = ref('')

const noteBody = ref('')
const noteRevision = ref<number | undefined>(undefined)
const savingNote = ref(false)
const noteMessage = ref('')

const summaryBody = ref('')
const savingSummary = ref(false)
const summaryMessage = ref('')
const editingMeeting = ref(false)
const savingMeeting = ref(false)
const meetingMessage = ref('')

const editTitle = ref('')
const editDescription = ref('')
const editAgenda = ref('')
const editStart = ref('')
const editEnd = ref('')
const editTimezone = ref('')
const editJoinLink = ref('')
const cancellingMeeting = ref(false)

const meetingId = Number(route.params.meetingId)

const loadMeeting = async () => {
  loading.value = true
  errorMessage.value = ''

  try {
    meeting.value = await fetchMeetingById(meetingId)

    try {
      const note = await fetchMeetingNote(meetingId)
      noteBody.value = note.body || ''
      noteRevision.value = note.revision
    } catch (error) {
      console.error('Failed to load meeting note:', error)
    }

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

const saveNote = async () => {
  savingNote.value = true
  noteMessage.value = ''

  try {
    const updated = await updateMeetingNote(
      meetingId,
      noteBody.value,
      noteRevision.value
    )

    noteBody.value = updated.body || ''
    noteRevision.value = updated.revision
    noteMessage.value = 'Note saved.'
  } catch (error) {
    console.error('Failed to save note:', error)
    noteMessage.value = 'Unable to save note. Please try again.'
  } finally {
    savingNote.value = false
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
  editAgenda.value = meeting.value.agenda || ''
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
      agenda: editAgenda.value,
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

const formatMeetingDate = (dateString: string) => {
  const date = new Date(dateString)

  return new Intl.DateTimeFormat('en-AU', {
    dateStyle: 'medium',
    timeStyle: 'short',
  }).format(date)
}

onMounted(loadMeeting)
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
