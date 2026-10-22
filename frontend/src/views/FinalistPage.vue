<template>
  <div
    class="content-area"
    :class="{ 'is-dragging-file': isDraggingFile }"
    @dragover.prevent
    @drop.prevent
  >
    <div v-if="isLoading" class="card">
      <p>Loading finalist details…</p>
    </div>

    <div v-else-if="loadError" class="card">
      <h2 class="card-title">{{ loadError }}</h2>
      <button class="btn btn-outline btn-sm" type="button" @click="load">Try again</button>
    </div>

    <template v-else-if="detail">
      <AdminSubmissionBar
        v-if="adminAccess"
        :team="teamName"
        :entry="adminEntry"
        :students="studentsNote"
        :editing="adminEditing"
        :dirty="adminDirty"
        :busy="isBusy"
        @edit="startAdminEdit"
        @save="adminSave"
        @submit="adminSubmit"
        @discard="adminDiscard"
        @done="leaveAdminEdit"
      />
      <div v-else class="status-line" :class="`is-${state.tone}`">
        <span class="status-line__icon" aria-hidden="true">
          <i :class="`fas ${state.icon}`"></i>
        </span>
        <strong class="status-line__state">{{ state.headline }}{{ state.detail ? '.' : '' }}</strong>
        <span v-if="state.detail" class="status-line__detail">{{ state.detail }}</span>

        <button
          v-if="isLocked && isOpen"
          ref="reopenTrigger"
          class="btn btn-outline btn-sm status-line__action"
          type="button"
          data-testid="finalist-resubmit"
          :disabled="isBusy"
          @click="askToReopen"
        >
          {{ isReopening ? 'Opening…' : 'Resubmit' }}
        </button>

        <span class="submission-due" :title="deadlineDetail">
          <span class="submission-due__label">{{ isOpen ? 'Due' : 'Closed' }}</span>
          <strong class="submission-due__date">{{ deadlineDate }}</strong>
          <span v-if="timeRemaining" class="submission-remaining" :class="{ 'is-near': isDeadlineNear }">
            {{ timeRemaining }}
          </span>
        </span>
      </div>

      <!-- An in-page dialog, since browsers can suppress window.confirm(). -->
      <div
        v-if="isConfirmingReopen"
        class="submission-dialog-backdrop"
        role="dialog"
        aria-modal="true"
        aria-labelledby="finalist-reopen-title"
        tabindex="-1"
        @keydown.esc="closeReopenDialog"
      >
        <section class="submission-dialog">
          <h2 id="finalist-reopen-title" class="submission-dialog__title">Reopen for editing?</h2>
          <p class="submission-dialog__body">
            Your current submission stays in place until you submit again.
          </p>
          <div class="submission-dialog__actions">
            <button type="button" class="btn btn-outline" @click="closeReopenDialog">Cancel</button>
            <button ref="reopenConfirm" type="button" class="btn btn-primary" @click="confirmReopen">
              Reopen
            </button>
          </div>
        </section>
      </div>

      <!-- Admins confirm anything the team will see. -->
      <div
        v-if="adminDialog"
        class="submission-dialog-backdrop"
        role="dialog"
        aria-modal="true"
        aria-labelledby="finalist-admin-dialog-title"
        tabindex="-1"
        data-testid="admin-dialog"
        @keydown.esc="answerAdminDialog(false)"
      >
        <section class="submission-dialog">
          <h2 id="finalist-admin-dialog-title" class="submission-dialog__title">{{ adminDialog.title }}</h2>
          <p class="submission-dialog__body">{{ adminDialog.body }}</p>
          <div class="submission-dialog__actions">
            <button type="button" class="btn btn-outline" data-testid="admin-dialog-cancel" @click="answerAdminDialog(false)">
              Cancel
            </button>
            <button
              ref="adminDialogConfirm"
              type="button"
              class="btn btn-primary"
              data-testid="admin-dialog-confirm"
              @click="answerAdminDialog(true)"
            >
              {{ adminDialog.confirm }}
            </button>
          </div>
        </section>
      </div>

      <div v-if="message" class="submission-message" :class="{ 'submission-message--error': isError }">
        <span>{{ message }}</span>
        <button type="button" class="submission-message__close" aria-label="Dismiss" @click="setMessage('')">
          &times;
        </button>
      </div>

      <section class="card">
        <div class="finalist-part" data-testid="finalist-availability">
        <header class="section-head">
          <h2 class="card-title">Availability</h2>
          <template v-if="detail.times_shown">
            <p class="section-head__sub">
              While we hope you can join us for the whole day, we understand that not all teams are
              able to. Please select which sessions you will be able to join us for to ensure we
              schedule you into an appropriate presentation slot. You may select multiple options.
            </p>
            <p v-if="symposiumDay" class="section-head__sub">
              The sessions are on {{ symposiumDay }}, in Sydney time ({{ sydneyClock }}).
            </p>
          </template>
        </header>

        <!-- Until Management releases the sessions: what's coming, and what to do
             then, under the heading's line like the sessions would be. -->
        <p v-if="!detail.times_shown" class="section-head__sub finalist-not-shown" data-testid="sessions-not-shown">
          The presentation sessions haven't been released yet. Stay tuned, and once they're
          released, come back here and select the sessions your team can join so we can schedule
          you into a presentation slot.
        </p>

        <p v-if="detail.times_shown && !detail.sessions.length" class="submission-muted">
          No sessions have been set up yet.
        </p>
        <fieldset v-else-if="detail.times_shown" class="finalist-sessions" :disabled="!isEditable || isSaving">
          <legend class="submission-label">
            Sessions
            <span class="submission-required" title="Required" aria-label="required">*</span>
          </legend>
          <label v-for="session in detail.sessions" :key="session.id" class="finalist-session">
            <input
              type="checkbox"
              :value="session.id"
              :checked="selected.includes(session.id)"
              :data-testid="`session-${session.id}`"
              @change="toggleSession(session.id)"
            />
            <span>{{ sessionLabel(session.label) }}</span>
          </label>
        </fieldset>

        <div v-if="detail.sessions.length" class="finalist-availability-submit">
          <button
            v-if="isEditable && !adminAccess"
            class="btn btn-primary btn-sm"
            type="button"
            data-testid="submit-availability"
            :disabled="isBusy || !canSubmitAvailability"
            @click="onSubmitAvailability"
          >
            {{ isSaving ? 'Submitting…' : 'Submit Availability' }}
          </button>
          <span v-if="availabilitySubmittedLine" class="submission-muted" data-testid="availability-submitted">
            {{ availabilitySubmittedLine }}
          </span>
        </div>
        </div>

        <div class="finalist-part" data-testid="finalist-presentation">
        <header class="section-head">
          <h2 class="card-title">Presentation</h2>
          <p class="section-head__sub">Upload the slides your team will present at the Symposium.</p>
        </header>

        <div
          class="drop-zone"
          :class="{ 'is-drop-target': isDropTarget }"
          data-testid="drop-presentation"
          @dragover.prevent="onDragOver"
          @dragleave="onDragLeave"
          @drop.prevent="onDrop"
        >
          <div class="submission-slot submission-slot--plain">
            <div class="submission-slot__info">
              <p class="submission-muted">
                PDF or PowerPoint · up to {{ maxSizeLabel }}
              </p>
              <p v-if="shownPresentation" class="submission-file">
                <a :href="downloadUrl" target="_blank" rel="noopener noreferrer">{{ shownPresentation.name }}</a>
                <span class="submission-muted"> ({{ formatFileSize(shownPresentation.size) }}{{ pendingFile ? ' · not saved yet' : '' }})</span>
              </p>
              <p v-else class="submission-muted">Nothing attached yet.</p>
            </div>

            <div v-if="isEditable" class="submission-slot__actions">
              <input
                ref="fileInput"
                type="file"
                class="submission-hidden-input"
                accept=".pdf,.ppt,.pptx,application/pdf,application/vnd.ms-powerpoint,application/vnd.openxmlformats-officedocument.presentationml.presentation"
                @change="onFileChosen"
              />
              <button class="btn btn-outline btn-sm" type="button" :disabled="isUploading" @click="fileInput?.click()">
                {{ isUploading ? `Uploading… ${uploadPercent}%` : shownPresentation ? 'Replace' : 'Upload' }}
              </button>
              <button
                v-if="shownPresentation"
                class="btn btn-outline btn-sm"
                type="button"
                :disabled="isUploading"
                @click="removeFile"
              >
                Remove
              </button>
            </div>
          </div>

          <article class="preview-panel" :class="{ 'is-collapsed': isPreviewFolded }">
            <div class="preview-header">
              <h2 class="preview-title">
                <button
                  type="button"
                  class="preview-toggle"
                  :aria-expanded="!isPreviewFolded"
                  aria-controls="finalist-preview-body"
                  data-testid="toggle-finalist-preview"
                  :disabled="isPreviewShut"
                  @click="previewCollapsed = !previewCollapsed"
                >
                  <i
                    class="fas preview-toggle__chevron"
                    :class="isPreviewFolded ? 'fa-chevron-right' : 'fa-chevron-down'"
                    aria-hidden="true"
                  ></i>
                  Preview
                </button>
              </h2>
              <a
                v-if="isPdf"
                class="btn btn-outline btn-sm"
                :href="previewUrl"
                target="_blank"
                rel="noopener noreferrer"
              >
                Open in new tab
              </a>
            </div>

            <div v-show="!isPreviewFolded" id="finalist-preview-body">
              <iframe
                v-if="isPdf"
                class="preview-frame"
                title="Presentation preview"
                :src="pendingFile ? previewUrl : `${previewUrl}?v=${encodeURIComponent(shownPresentation?.storage_key ?? '')}`"
              ></iframe>
              <div v-else-if="shownPresentation" class="preview-empty">
                <i class="fas fa-file-powerpoint" aria-hidden="true"></i>
                <p>PowerPoint files can't be previewed here. Download it to check the right file arrived.</p>
              </div>
              <div v-else class="preview-empty">
                <i class="fas fa-file-pdf" aria-hidden="true"></i>
                <p>Once you upload a PDF presentation it appears here.</p>
              </div>
            </div>
          </article>
        </div>
        </div>
      </section>

      <div class="submission-actions">
        <button v-if="isEditable && !adminAccess" class="btn btn-primary" type="button" :disabled="isBusy" @click="onSubmit">
          {{ isSubmitting ? 'Submitting…' : 'Submit' }}
        </button>
      </div>
    </template>
  </div>
</template>

<script setup lang="ts">
import { computed, nextTick, onBeforeUnmount, onMounted, ref, watch } from 'vue'
import { useRoute, useRouter } from 'vue-router'
import AdminSubmissionBar from '@/components/submission/AdminSubmissionBar.vue'
import { apiErrorFromUnknown } from '@/utils/apiError'
import { formatDayMonthTime, formatEventCalendarDay, formatSydneySlot, sydneyClockOn } from '@/utils/date'
import {
  fetchFinalist,
  presentationDownloadUrl,
  presentationPreviewUrl,
  removePresentation,
  reopenFinalist,
  submitAvailability,
  submitFinalist,
  uploadPresentation,
  type FinalistDetail,
  type FinalistWriteResult,
} from '@/utils/finalistAPI'
import { describeTimeRemaining, formatFileSize, isDeadlineNear as deadlineIsNear } from '@/utils/submissionFormat'
import { useFileDragging } from '@/components/submission/useFileDragging'

const MESSAGE_TIMEOUT_MS = 4000
const ALLOWED_EXTENSIONS = ['pdf', 'ppt', 'pptx']

const route = useRoute()
const router = useRouter()
const groupId = computed(() => String(route.params.id ?? ''))

const detail = ref<FinalistDetail | null>(null)
const isLoading = ref(true)
const loadError = ref('')
const selected = ref<number[]>([])
const isSaving = ref(false)
const isSubmitting = ref(false)
const isReopening = ref(false)
const isUploading = ref(false)
const uploadPercent = ref(0)
const isDropTarget = ref(false)
const isDraggingFile = useFileDragging(() => {
  isDropTarget.value = false
})
const previewCollapsed = ref(false)
const message = ref('')
const isError = ref(false)
const now = ref(Date.now())
const fileInput = ref<HTMLInputElement | null>(null)

const entry = computed(() => detail.value?.entry ?? null)
const isOpen = computed(() => Boolean(detail.value?.deadline.is_open))
const isLocked = computed(() => Boolean(entry.value?.is_locked))
// Admins act for a team in their own edit mode: read-only until they choose Edit.
const adminAccess = computed(() => Boolean(detail.value?.admin_access))
const adminEditing = ref(false)
const isEditable = computed(() => isOpen.value && (adminAccess.value ? adminEditing.value : !isLocked.value))
const isBusy = computed(
  () => isSaving.value || isSubmitting.value || isReopening.value || isUploading.value
)
const showsSubmittedCopy = computed(
  () => Boolean(entry.value?.is_submitted) && !adminEditing.value && (isLocked.value || !isOpen.value)
)
/** An admin's presentation change, held until Save or Submit: a file to upload, or null to remove. */
const pendingPresentation = ref<File | null | undefined>(undefined)
const pendingFile = computed(() => pendingPresentation.value ?? null)
let pendingObjectUrl = ''

function pendingUrl(): string {
  const file = pendingFile.value
  if (!file || typeof URL.createObjectURL !== 'function') return ''
  pendingObjectUrl ||= URL.createObjectURL(file)
  return pendingObjectUrl
}

function clearPending() {
  if (pendingObjectUrl && typeof URL.revokeObjectURL === 'function') URL.revokeObjectURL(pendingObjectUrl)
  pendingObjectUrl = ''
  pendingPresentation.value = undefined
}

const shownPresentation = computed(() => {
  if (pendingPresentation.value !== undefined) {
    const file = pendingPresentation.value
    return file ? { storage_key: `pending:${file.name}:${file.size}`, name: file.name, mime: file.type, size: file.size } : null
  }
  return showsSubmittedCopy.value ? entry.value?.submitted_presentation ?? null : entry.value?.presentation ?? null
})
const isPdf = computed(() => (shownPresentation.value?.name ?? '').toLowerCase().endsWith('.pdf'))
/** Nothing can be uploaded any more and nothing was, so there is nothing to preview. */
const isPreviewShut = computed(() => !isEditable.value && !shownPresentation.value)
const isPreviewFolded = computed(() => previewCollapsed.value || isPreviewShut.value)
const maxSizeLabel = computed(() => formatFileSize(detail.value?.max_file_size ?? 25 * 1024 * 1024))
// "AEDT, UTC+11" on the Symposium day: the sessions are Sydney time
// wherever the team is.
const sydneyClock = computed(() => {
  const iso = detail.value?.symposium_date
  if (!iso) return ''
  const clock = sydneyClockOn(iso)
  return `${clock.name}, ${clock.offset}`
})

// "Friday, 23rd October 2026".
const symposiumDay = computed(() => formatEventCalendarDay(detail.value?.symposium_date))

// "09:30 - 10:00 AEDT" from the session's "9:30 – 10:00": Sydney time on
// the Symposium day.
const sessionLabel = (label: string) => {
  const [start, end] = label.split('–').map((part) => part.trim())
  return start && end ? formatSydneySlot(start, end, detail.value?.symposium_date) : label
}
/** The ticks differ from the team's submitted times. */
const availabilityChanged = computed(() => {
  const saved = entry.value?.available_session_ids ?? []
  return selected.value.length !== saved.length || selected.value.some((id) => !saved.includes(id))
})
const canSubmitAvailability = computed(
  () => selected.value.length > 0 && (availabilityChanged.value || !entry.value?.availability_submitted_at)
)
const availabilitySubmittedLine = computed(() => {
  const at = entry.value?.availability_submitted_at
  if (!at) return ''
  const by = entry.value?.availability_submitted_by_name
  return `Submitted${by ? ` by ${by}` : ''} on ${formatDayMonthTime(at)}`
})
const downloadUrl = computed(() => (pendingFile.value ? pendingUrl() : presentationDownloadUrl(groupId.value)))
const previewUrl = computed(() => (pendingFile.value ? pendingUrl() : presentationPreviewUrl(groupId.value)))

const state = computed(() => {
  const closed = !isOpen.value
  const stage = entry.value?.stage ?? 'not_started'
  const by = entry.value?.submitted_by_name
  const submittedLine = entry.value?.submitted_at
    ? `Submitted${by ? ` by ${by}` : ''} on ${formatDayMonthTime(entry.value.submitted_at)}`
    : ''
  if (stage === 'submitted' || (stage === 'revising' && closed)) {
    return { tone: 'submitted', icon: 'fa-check', headline: 'Submitted', detail: submittedLine }
  }
  if (closed) {
    return { tone: 'missed', icon: 'fa-circle-exclamation', headline: 'Not Submitted', detail: 'Submissions are closed' }
  }
  if (stage === 'revising') {
    return {
      tone: 'progress',
      icon: 'fa-pen',
      headline: 'In Progress',
      detail: 'Your previous submission still stands until you submit again',
    }
  }
  return {
    tone: 'progress',
    icon: 'fa-pen',
    headline: stage === 'in_progress' ? 'In Progress' : 'Not Started',
    detail: '',
  }
})

const deadlineDate = computed(() => {
  const closesAt = detail.value?.deadline.closes_at
  return closesAt ? formatDayMonthTime(closesAt) : 'No deadline set'
})
// Only explains a missing deadline: a set one shows in the set time.
const deadlineDetail = computed(() =>
  detail.value?.deadline.closes_at
    ? undefined
    : 'An administrator needs to set a finalist deadline before entries can be saved.'
)
const timeRemaining = computed(() =>
  isOpen.value ? describeTimeRemaining(detail.value?.deadline.closes_at, now.value) : ''
)
const isDeadlineNear = computed(
  () => isOpen.value && deadlineIsNear(detail.value?.deadline.closes_at, now.value)
)

let messageTimer: ReturnType<typeof setTimeout> | null = null
function setMessage(text: string, error = false) {
  if (messageTimer) clearTimeout(messageTimer)
  message.value = text
  isError.value = error
  if (text) messageTimer = setTimeout(() => (message.value = ''), MESSAGE_TIMEOUT_MS)
}

function errorText(error: unknown): string {
  const apiError = apiErrorFromUnknown(error)
  if (apiError.code === 'submissions_closed' && detail.value) {
    detail.value = { ...detail.value, deadline: { ...detail.value.deadline, is_open: false } }
    return 'The finalist deadline has passed while you were editing.'
  }
  return apiError.message
}

function syncSelection() {
  selected.value = [...(entry.value?.available_session_ids ?? [])]
}

function applyResult(result: FinalistWriteResult) {
  if (!detail.value) return
  detail.value = { ...detail.value, deadline: result.deadline, entry: result.entry }
}

async function load() {
  isLoading.value = true
  loadError.value = ''
  try {
    detail.value = await fetchFinalist(groupId.value)
    syncSelection()
  } catch (error) {
    loadError.value = apiErrorFromUnknown(error).message
  } finally {
    isLoading.value = false
  }
}

function toggleSession(id: number) {
  if (!isEditable.value) return
  selected.value = selected.value.includes(id)
    ? selected.value.filter((value) => value !== id)
    : [...selected.value, id]
}

/** The ticks, for the whole team; the page notes who submitted them and when. */
async function onSubmitAvailability() {
  if (!canSubmitAvailability.value) return
  isSaving.value = true
  setMessage('')
  try {
    applyResult(await submitAvailability(groupId.value, selected.value))
    syncSelection()
    setMessage('Availability submitted for your team.')
  } catch (error) {
    setMessage(errorText(error), true)
  } finally {
    isSaving.value = false
  }
}

function showPart(part: 'availability' | 'presentation') {
  const element = document.querySelector(`[data-testid="finalist-${part}"]`)
  if (element && typeof element.scrollIntoView === 'function') {
    element.scrollIntoView({ behavior: 'smooth', block: 'start' })
  }
}

async function uploadFile(file: File) {
  const extension = file.name.toLowerCase().split('.').pop() ?? ''
  if (!ALLOWED_EXTENSIONS.includes(extension)) {
    setMessage('The presentation must be a PDF or PowerPoint file.', true)
    return
  }
  const limit = detail.value?.max_file_size ?? 25 * 1024 * 1024
  if (file.size > limit) {
    setMessage(`That file is ${formatFileSize(file.size)}. The limit is ${maxSizeLabel.value}.`, true)
    return
  }
  if (adminAccess.value) {
    clearPending()
    pendingPresentation.value = file
    return
  }
  isUploading.value = true
  uploadPercent.value = 0
  setMessage('')
  try {
    applyResult(await uploadPresentation(groupId.value, file, (percent) => (uploadPercent.value = percent)))
  } catch (error) {
    setMessage(errorText(error), true)
  } finally {
    isUploading.value = false
    uploadPercent.value = 0
  }
}

async function onFileChosen(event: Event) {
  const input = event.target as HTMLInputElement
  const file = input.files?.[0]
  if (file) await uploadFile(file)
  // Cleared so choosing the same file again still fires a change.
  input.value = ''
}

function onDragOver(event: DragEvent) {
  if (!isEditable.value || isUploading.value) return
  if (event.dataTransfer) event.dataTransfer.dropEffect = 'copy'
  isDropTarget.value = true
}

function onDragLeave(event: DragEvent) {
  const next = event.relatedTarget as Node | null
  if (next && (event.currentTarget as HTMLElement).contains(next)) return
  isDropTarget.value = false
}

function onDrop(event: DragEvent) {
  isDropTarget.value = false
  const file = event.dataTransfer?.files?.[0]
  if (!file || !isEditable.value || isUploading.value) return
  void uploadFile(file)
}

async function removeFile() {
  if (adminAccess.value) {
    clearPending()
    // A held file the team never had is simply dropped; a saved one is marked for removal.
    if (entry.value?.presentation) pendingPresentation.value = null
    return
  }
  isUploading.value = true
  try {
    applyResult(await removePresentation(groupId.value))
  } catch (error) {
    setMessage(errorText(error), true)
  } finally {
    isUploading.value = false
  }
}

async function onSubmit() {
  // Availability is only needed once the sessions are shown.
  if (detail.value?.times_shown && (!entry.value?.availability_submitted_at || availabilityChanged.value)) {
    setMessage("Submit your team's availability first.", true)
    showPart('availability')
    return
  }
  if (!entry.value?.presentation) {
    setMessage('A presentation must be uploaded before the entry can be submitted.', true)
    showPart('presentation')
    return
  }
  isSubmitting.value = true
  setMessage('')
  try {
    applyResult(await submitFinalist(groupId.value))
    syncSelection()
    setMessage('Submitted. Choose Resubmit if you need to change anything before the deadline.')
  } catch (error) {
    setMessage(errorText(error), true)
    if (apiErrorFromUnknown(error).code === 'availability_required') showPart('availability')
  } finally {
    isSubmitting.value = false
  }
}

const isConfirmingReopen = ref(false)
const reopenConfirm = ref<HTMLButtonElement | null>(null)
const reopenTrigger = ref<HTMLElement | null>(null)

async function askToReopen() {
  isConfirmingReopen.value = true
  await nextTick()
  reopenConfirm.value?.focus()
}

function closeReopenDialog() {
  isConfirmingReopen.value = false
  reopenTrigger.value?.focus()
}

async function confirmReopen() {
  closeReopenDialog()
  isReopening.value = true
  try {
    applyResult(await reopenFinalist(groupId.value))
    syncSelection()
    setMessage('Reopened for editing. Submit again to replace your submission.')
  } catch (error) {
    setMessage(errorText(error), true)
  } finally {
    isReopening.value = false
  }
}

const REFRESH_MIN_GAP_MS = 5000
let lastRefreshAt = 0
let deadlineRecheckDone = false

/** Picks up a deadline change made while the page sat open. */
async function refreshDeadline() {
  if (!detail.value || isLoading.value || isBusy.value) return
  if (Date.now() - lastRefreshAt < REFRESH_MIN_GAP_MS) return
  lastRefreshAt = Date.now()
  try {
    const latest = await fetchFinalist(groupId.value)
    if (!detail.value || isBusy.value) return
    if (!isOpen.value && latest.deadline.is_open && !adminEditing.value) {
      detail.value = latest
      syncSelection()
    } else {
      detail.value = { ...detail.value, deadline: latest.deadline }
    }
    deadlineRecheckDone = false
  } catch {
    // Best effort: a write still reports an authoritative closure.
  }
}

function onPageVisible() {
  if (document.visibilityState === 'visible' && route.name === 'group-finalist') refreshDeadline()
}

watch(
  () => route.name,
  (name, previous) => {
    if (name === 'group-finalist' && previous && previous !== name) refreshDeadline()
  }
)

const clockTimer = setInterval(() => (now.value = Date.now()), 60000)
watch(now, async () => {
  if (deadlineRecheckDone || !isOpen.value) return
  const closesAt = detail.value?.deadline.closes_at
  if (!closesAt || now.value < new Date(closesAt).getTime()) return
  deadlineRecheckDone = true
  lastRefreshAt = 0
  await refreshDeadline()
  if (!isOpen.value) setMessage('The finalist deadline has just passed.', true)
})

watch(groupId, () => {
  adminEditing.value = false
  clearPending()
  load()
})

// ---- Admin edit mode: nothing reaches the team until Save or Submit -----------------------

const teamName = computed(() => detail.value?.group.name ?? 'this team')

const adminEntry = computed(() => {
  const current = entry.value
  const when = current?.submitted_at ? formatDayMonthTime(current.submitted_at) : ''
  switch (current?.stage ?? 'not_started') {
    case 'submitted':
      return `Submitted ${when}`
    case 'revising':
      return `Reopened, last submitted ${when}`
    case 'in_progress':
      return 'Draft, not submitted'
    default:
      return 'Not started'
  }
})

/** The finalist deadline is shown, not enforced, so only a submitted entry stops the team. */
const studentsNote = computed(() => {
  if (isLocked.value) return "Can't edit until reopened"
  const closesAt = detail.value?.deadline.closes_at
  return closesAt ? `Can edit · due ${deadlineDate.value}` : 'Can edit'
})

const adminDirty = computed(
  () => adminEditing.value && (availabilityChanged.value || pendingPresentation.value !== undefined)
)

/** The times and slides as they stood when the admin chose Edit, to tell what the team changed since. */
let editStart: { sessions: number[]; presentationKey: string } = { sessions: [], presentationKey: '' }

const adminDialog = ref<{ title: string; body: string; confirm: string } | null>(null)
const adminDialogConfirm = ref<HTMLButtonElement | null>(null)
let answerDialog: ((ok: boolean) => void) | null = null

function askAdmin(title: string, body: string, confirm: string): Promise<boolean> {
  adminDialog.value = { title, body, confirm }
  void nextTick(() => adminDialogConfirm.value?.focus())
  return new Promise((resolve) => {
    answerDialog = resolve
  })
}

function answerAdminDialog(ok: boolean) {
  adminDialog.value = null
  answerDialog?.(ok)
  answerDialog = null
}

/** The entry as the server now holds it, since the team may have changed it meanwhile. */
async function reloadEntry() {
  try {
    detail.value = await fetchFinalist(groupId.value)
  } catch {
    // Kept as it was; the next save reports any problem.
  }
}

async function startAdminEdit() {
  await reloadEntry()
  syncSelection()
  editStart = {
    sessions: [...(entry.value?.available_session_ids ?? [])],
    presentationKey: entry.value?.presentation?.storage_key ?? ''
  }
  adminEditing.value = true
}

async function leaveAdminEdit() {
  adminEditing.value = false
  clearPending()
  await reloadEntry()
  syncSelection()
}

async function adminDiscard() {
  if (!(await askAdmin('Discard your changes?', `Nothing you changed for ${teamName.value} will be kept.`, 'Discard'))) return
  await leaveAdminEdit()
  setMessage('Changes discarded.')
}

function sameTimes(a: number[], b: number[]) {
  return a.length === b.length && a.every((id) => b.includes(id))
}

/**
 * Takes the entry's current state before an admin's Save or Submit, so reopening follows it, and
 * asks before overwriting what the team changed meanwhile. The admin's ticks and file stay.
 */
async function readyToWrite(): Promise<boolean> {
  const latest = await fetchFinalist(groupId.value)
  if (!detail.value) return false
  detail.value = { ...detail.value, deadline: latest.deadline, entry: latest.entry }
  const timesClash =
    !sameTimes(selected.value, editStart.sessions) &&
    !sameTimes(latest.entry?.available_session_ids ?? [], editStart.sessions)
  const fileClash =
    pendingPresentation.value !== undefined && (latest.entry?.presentation?.storage_key ?? '') !== editStart.presentationKey
  const conflicts = (timesClash ? 1 : 0) + (fileClash ? 1 : 0)
  return (
    !conflicts ||
    askAdmin(
      conflicts === 1 ? 'Overwrite a conflicting change?' : `Overwrite ${conflicts} conflicting changes?`,
      'The team changed some of the same parts while you were editing. Continuing replaces their version of those.',
      'Overwrite'
    )
  )
}

/** Sends the ticked times (when changed, or when a submit needs them) and the held presentation. */
async function publishAdminChanges(forSubmit: boolean) {
  const needsTimes = forSubmit && detail.value?.times_shown && !entry.value?.availability_submitted_at
  if (detail.value?.times_shown && (availabilityChanged.value || needsTimes)) {
    applyResult(await submitAvailability(groupId.value, selected.value))
  }
  if (pendingPresentation.value !== undefined) {
    const file = pendingPresentation.value
    isUploading.value = true
    try {
      if (file) {
        applyResult(await uploadPresentation(groupId.value, file, (percent) => (uploadPercent.value = percent)))
      } else if (entry.value?.presentation) {
        applyResult(await removePresentation(groupId.value))
      }
    } finally {
      isUploading.value = false
      uploadPercent.value = 0
    }
    clearPending()
  }
}

async function adminSave() {
  if (detail.value?.times_shown && availabilityChanged.value && !selected.value.length) {
    setMessage('Choose at least one session the team can attend.', true)
    showPart('availability')
    return
  }
  isSaving.value = true
  setMessage('')
  try {
    if (!(await readyToWrite())) return
    // The round has no enforced deadline, so a submitted entry is reopened to show the team the changes.
    if (isLocked.value) {
      const reopen = await askAdmin(
        'Reopen for the team?',
        `Saving reopens ${teamName.value}'s finalist entry with your changes. Their submission stands until it's submitted again.`,
        'Reopen'
      )
      if (!reopen) return
      applyResult(await reopenFinalist(groupId.value))
    }
    await publishAdminChanges(false)
    await leaveAdminEdit()
    setMessage(`Saved to ${teamName.value}'s finalist entry.`)
  } catch (error) {
    setMessage(errorText(error), true)
  } finally {
    isSaving.value = false
  }
}

async function adminSubmit() {
  if (detail.value?.times_shown && !selected.value.length) {
    setMessage('Choose at least one session the team can attend.', true)
    showPart('availability')
    return
  }
  if (!shownPresentation.value) {
    setMessage('A presentation must be uploaded before the entry can be submitted.', true)
    showPart('presentation')
    return
  }
  isSubmitting.value = true
  setMessage('')
  try {
    if (!(await readyToWrite())) return
    const confirmed = await askAdmin(
      `Submit for ${teamName.value}?`,
      'This becomes their latest finalist submission.',
      'Submit'
    )
    if (!confirmed) return
    await publishAdminChanges(true)
    applyResult(await submitFinalist(groupId.value))
    await leaveAdminEdit()
    setMessage(`Submitted for ${teamName.value}.`)
  } catch (error) {
    setMessage(errorText(error), true)
  } finally {
    isSubmitting.value = false
  }
}

const LEAVE_WARNING = 'You have unsaved changes for this team. Leave without saving?'

// Moving between this team's sections keeps the page, and the changes, in place.
const removeLeaveGuard = router.beforeEach((to) => {
  if (!adminDirty.value || String(to.params.id ?? '') === groupId.value) return true
  return window.confirm(LEAVE_WARNING)
})

function warnBeforeUnload(event: BeforeUnloadEvent) {
  if (!adminDirty.value) return
  event.preventDefault()
  event.returnValue = ''
}
window.addEventListener('beforeunload', warnBeforeUnload)

onMounted(() => {
  load()
  window.addEventListener('focus', onPageVisible)
  document.addEventListener('visibilitychange', onPageVisible)
})

onBeforeUnmount(() => {
  removeLeaveGuard()
  window.removeEventListener('beforeunload', warnBeforeUnload)
  clearPending()
  window.removeEventListener('focus', onPageVisible)
  document.removeEventListener('visibilitychange', onPageVisible)
  if (messageTimer) clearTimeout(messageTimer)
  clearInterval(clockTimer)
})
</script>

<style scoped src="../components/submission/submissionPortal.css"></style>

<style scoped>
/* The portal caps these lines at 75 characters; here they run the card's
   full width. */
.section-head__sub {
  max-width: none;
}

.finalist-part + .finalist-part {
  margin-top: 1.75rem;
  padding-top: 1.5rem;
  border-top: 1px solid var(--panel-border);
}

.finalist-not-shown {
  margin: 0;
}

.finalist-sessions {
  display: grid;
  gap: 0.6rem;
  margin: 0;
  padding: 0;
  border: none;
}

.finalist-sessions .submission-label {
  margin-bottom: 0.4rem;
}

.finalist-session {
  display: flex;
  align-items: center;
  gap: 0.6rem;
  color: var(--body-text);
  cursor: pointer;
}

.finalist-session input {
  width: 1.05rem;
  height: 1.05rem;
  accent-color: var(--accent);
}

.finalist-sessions:disabled .finalist-session {
  cursor: default;
  color: var(--muted);
}

.finalist-availability-submit {
  display: flex;
  flex-wrap: wrap;
  align-items: center;
  gap: 0.75rem;
  margin-top: 1rem;
}
</style>
