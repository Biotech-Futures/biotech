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
      <div class="status-line" :class="`is-${state.tone}`">
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
          <p class="section-head__sub">
            While we hope you can join us for the whole day, we understand that not all teams are
            able to. Please select which sessions you will be able to join us for to ensure we
            schedule you into an appropriate presentation slot. You may select multiple options.
            Each student answers for themselves.
          </p>
          <p v-if="symposiumDay" class="section-head__sub">The sessions are on {{ symposiumDay }}.</p>
        </header>

        <p v-if="!detail.sessions.length" class="submission-muted">
          No sessions have been set up yet.
        </p>
        <fieldset v-else class="finalist-sessions" :disabled="!isEditable || !detail.can_choose_sessions">
          <legend class="submission-label">
            Sessions
            <span class="submission-required" title="Required" aria-label="required">*</span>
          </legend>
          <p v-if="!detail.can_choose_sessions" class="submission-muted" data-testid="students-choose">
            Each student chooses their own sessions.
          </p>
          <label v-for="session in detail.sessions" :key="session.id" class="finalist-session">
            <input
              type="checkbox"
              :value="session.id"
              :checked="selected.includes(session.id)"
              :data-testid="`session-${session.id}`"
              @change="toggleSession(session.id)"
            />
            <span>{{ session.label }}</span>
          </label>
        </fieldset>
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
                <span class="submission-muted"> ({{ formatFileSize(shownPresentation.size) }})</span>
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
                :src="`${previewUrl}?v=${encodeURIComponent(shownPresentation?.storage_key ?? '')}`"
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
        <span
          v-if="isEditable && saveStateLabel"
          class="submission-savestate"
          :class="{ 'is-error': saveFailed }"
          data-testid="finalist-savestate"
        >
          {{ saveStateLabel }}
        </span>

        <button v-if="isEditable" class="btn btn-primary" type="button" :disabled="isBusy" @click="onSubmit">
          {{ isSubmitting ? 'Submitting…' : 'Submit' }}
        </button>
      </div>
    </template>
  </div>
</template>

<script setup lang="ts">
import { computed, nextTick, onBeforeUnmount, onMounted, ref, watch } from 'vue'
import { useRoute } from 'vue-router'
import { apiErrorFromUnknown } from '@/utils/apiError'
import {
  fetchFinalist,
  presentationDownloadUrl,
  presentationPreviewUrl,
  removePresentation,
  reopenFinalist,
  saveAvailability,
  submitFinalist,
  uploadPresentation,
  type FinalistDetail,
  type FinalistWriteResult,
} from '@/utils/finalistAPI'
import { describeTimeRemaining, formatFileSize, isDeadlineNear as deadlineIsNear } from '@/utils/submissionFormat'
import { useFileDragging } from '@/components/submission/useFileDragging'

const MESSAGE_TIMEOUT_MS = 4000
const SAVE_DELAY_MS = 600
const ALLOWED_EXTENSIONS = ['pdf', 'ppt', 'pptx']

const route = useRoute()
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
const saveFailed = ref(false)
const hasPendingSave = ref(false)
const lastSavedAt = ref<Date | null>(null)
const previewCollapsed = ref(false)
const message = ref('')
const isError = ref(false)
const now = ref(Date.now())
const fileInput = ref<HTMLInputElement | null>(null)

const entry = computed(() => detail.value?.entry ?? null)
const isOpen = computed(() => Boolean(detail.value?.deadline.is_open))
const isLocked = computed(() => Boolean(entry.value?.is_locked))
const isEditable = computed(() => isOpen.value && !isLocked.value)
const isBusy = computed(
  () => isSaving.value || isSubmitting.value || isReopening.value || isUploading.value
)
const showsSubmittedCopy = computed(
  () => Boolean(entry.value?.is_submitted) && (isLocked.value || !isOpen.value)
)
const shownPresentation = computed(() =>
  showsSubmittedCopy.value ? entry.value?.submitted_presentation ?? null : entry.value?.presentation ?? null
)
const isPdf = computed(() => (shownPresentation.value?.name ?? '').toLowerCase().endsWith('.pdf'))
/** Nothing can be uploaded any more and nothing was, so there is nothing to preview. */
const isPreviewShut = computed(() => !isEditable.value && !shownPresentation.value)
const isPreviewFolded = computed(() => previewCollapsed.value || isPreviewShut.value)
const maxSizeLabel = computed(() => formatFileSize(detail.value?.max_file_size ?? 25 * 1024 * 1024))
// "Friday, 23 October 2026", as the finalist email words the Symposium day.
const symposiumDay = computed(() => {
  const iso = detail.value?.symposium_date
  if (!iso) return ''
  const [year, month, day] = iso.split('-').map(Number)
  return new Date(year!, month! - 1, day).toLocaleDateString('en-AU', {
    weekday: 'long',
    day: 'numeric',
    month: 'long',
    year: 'numeric'
  })
})
const downloadUrl = computed(() => presentationDownloadUrl(groupId.value))
const previewUrl = computed(() => presentationPreviewUrl(groupId.value))

const state = computed(() => {
  const closed = !isOpen.value
  const stage = entry.value?.stage ?? 'not_started'
  const by = entry.value?.submitted_by_name
  const submittedLine = entry.value?.submitted_at
    ? `Submitted${by ? ` by ${by}` : ''} on ${new Date(entry.value.submitted_at).toLocaleString()}`
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

const localZone = Intl.DateTimeFormat().resolvedOptions().timeZone
const deadlineDate = computed(() => {
  const closesAt = detail.value?.deadline.closes_at
  if (!closesAt) return 'No deadline set'
  const date = new Date(closesAt)
  return date.toLocaleString(undefined, {
    day: 'numeric',
    month: 'short',
    year: date.getFullYear() === new Date().getFullYear() ? undefined : 'numeric',
    hour: 'numeric',
    minute: '2-digit',
  })
})
const deadlineDetail = computed(() =>
  detail.value?.deadline.closes_at
    ? `Shown in your local time (${localZone}).`
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
  selected.value = [
    ...((showsSubmittedCopy.value ? entry.value?.submitted_session_ids : entry.value?.available_session_ids) ?? []),
  ]
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

const saveStateLabel = computed(() => {
  if (isSaving.value) return 'Saving…'
  if (saveFailed.value) return 'Could not save'
  if (hasPendingSave.value) return 'Unsaved changes'
  if (lastSavedAt.value) {
    return `Saved ${lastSavedAt.value.toLocaleTimeString(undefined, { hour: '2-digit', minute: '2-digit' })}`
  }
  return ''
})

let saveTimer: ReturnType<typeof setTimeout> | null = null
// Kept at tick time; by unmount the route already points at the next page.
let pendingGroupId = ''
function toggleSession(id: number) {
  if (!isEditable.value) return
  selected.value = selected.value.includes(id)
    ? selected.value.filter((value) => value !== id)
    : [...selected.value, id]
  hasPendingSave.value = true
  pendingGroupId = groupId.value
  if (saveTimer) clearTimeout(saveTimer)
  saveTimer = setTimeout(() => void flushAvailability(), SAVE_DELAY_MS)
}

async function flushAvailability() {
  if (saveTimer) clearTimeout(saveTimer)
  saveTimer = null
  isSaving.value = true
  try {
    applyResult(await saveAvailability(groupId.value, selected.value))
    hasPendingSave.value = false
    saveFailed.value = false
    lastSavedAt.value = new Date()
  } catch (error) {
    saveFailed.value = true
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
  if (saveTimer) await flushAvailability()
  // Whether any of the team's students has chosen sessions is the server's to
  // say (see the catch below); a student hasn't, when they haven't themselves.
  if (detail.value?.can_choose_sessions && !selected.value.length) {
    setMessage('Choose at least one session you can attend.', true)
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
    if (!isOpen.value && latest.deadline.is_open) {
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

watch(groupId, load)

onMounted(() => {
  load()
  window.addEventListener('focus', onPageVisible)
  document.addEventListener('visibilitychange', onPageVisible)
})

onBeforeUnmount(() => {
  window.removeEventListener('focus', onPageVisible)
  document.removeEventListener('visibilitychange', onPageVisible)
  if (saveTimer) {
    // A tick made just before leaving is still sent.
    clearTimeout(saveTimer)
    void saveAvailability(pendingGroupId, selected.value).catch(() => undefined)
  }
  if (messageTimer) clearTimeout(messageTimer)
  clearInterval(clockTimer)
})
</script>

<style scoped src="../components/submission/submissionPortal.css"></style>

<style scoped>
.finalist-part + .finalist-part {
  margin-top: 1.75rem;
  padding-top: 1.5rem;
  border-top: 1px solid var(--panel-border);
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
</style>
