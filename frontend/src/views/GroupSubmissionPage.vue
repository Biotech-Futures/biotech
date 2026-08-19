<template>
  <div class="content-area">
    <nav class="detail-breadcrumb" aria-label="Breadcrumb">
      <RouterLink :to="{ name: 'group-detail', params: { id: groupId } }" class="submission-back">
        <span aria-hidden="true">&larr;</span>
        <span>Back to group</span>
      </RouterLink>
    </nav>

    <div v-if="isLoading" class="card">
      <p>Loading submission…</p>
    </div>

    <div v-else-if="loadError" class="card">
      <h2 class="card-title">{{ loadError }}</h2>
      <button class="btn btn-outline btn-sm" type="button" @click="load">Try again</button>
    </div>

    <template v-else-if="detail">
      <header class="submission-header">
        <h1 class="submission-heading">Submission — {{ detail.group.name }}</h1>
        <span class="status-badge" :class="statusClass">{{ statusLabel }}</span>
      </header>

      <!-- Deadline. Shown prominently because it governs everything below. -->
      <div class="card submission-deadline">
        <div>
          <strong>{{ deadlineHeadline }}</strong>
          <p v-if="deadlineDetail" class="submission-muted">{{ deadlineDetail }}</p>
        </div>
        <span v-if="detail.deadline.is_extended" class="status-badge status-info">Extended</span>
      </div>

      <p v-if="!isOpen" class="card submission-closed">
        Submissions are closed, so this entry can no longer be changed. It stays visible here.
      </p>

      <!-- Slim bar rather than a full card: it appears after every action, so
           card-sized padding pushed the form down the page each time. -->
      <div v-if="message" class="submission-message" :class="{ 'submission-message--error': isError }">
        <span>{{ message }}</span>
        <button type="button" class="submission-message__close" aria-label="Dismiss" @click="dismissMessage">
          &times;
        </button>
      </div>

      <!-- Step strip. Doubles as navigation and as an at-a-glance answer to
           "what have I still not done", which a single long page made obvious
           but separate sections otherwise hide. -->
      <nav class="submission-steps" aria-label="Submission sections">
        <button
          v-for="(tab, index) in TABS"
          :key="tab.key"
          type="button"
          class="submission-step"
          :class="{ 'is-active': activeTab === tab.key }"
          :aria-current="activeTab === tab.key ? 'page' : undefined"
          @click="activeTab = tab.key"
        >
          <span class="submission-step__index">{{ index + 1 }}</span>
          <span class="submission-step__label">{{ tab.label }}</span>
          <span class="submission-step__state" :class="`is-${stepState(tab.key).tone}`">
            {{ stepState(tab.key).label }}
          </span>
        </button>
      </nav>

      <!-- Placeholder guidance until the programme team supplies real wording. -->
      <div class="card submission-instructions">
        <h2 class="card-title">{{ activeTabConfig.label }}</h2>
        <p>{{ activeTabConfig.instructions }}</p>
      </div>

      <!-- 1. Short-answer questions. Defined in the database, so this list is
           whatever the server sent rather than anything hardcoded here. -->
      <section v-show="activeTab === 'questions'" class="card">
        <p v-if="!questions.length" class="submission-muted">
          No questions have been set up yet.
        </p>

        <div v-for="question in questions" :key="question.key" class="submission-field">
          <label class="submission-label" :for="question.key">
            {{ question.prompt }}
            <span v-if="question.is_required" class="submission-required">required</span>
          </label>
          <p v-if="question.help_text" class="submission-muted">{{ question.help_text }}</p>
          <textarea
            :id="question.key"
            v-model="answers[question.key]"
            class="form-control submission-textarea"
            rows="5"
            :maxlength="question.max_length ?? undefined"
            :disabled="!isOpen"
          ></textarea>
          <p
            v-if="question.max_length"
            class="submission-count"
            :class="{ 'is-near-limit': (charactersLeft(question.key, question.max_length) ?? 99) < 100 }"
          >
            {{ (answers[question.key] || '').length }} / {{ question.max_length }}
            <span class="submission-muted">
              · {{ charactersLeft(question.key, question.max_length) }} left
            </span>
          </p>
        </div>
      </section>

      <!-- 2. Poster, with the preview kept open — this tab exists mainly to
           give the document room to be read. -->
      <section v-show="activeTab === 'poster'" class="card">
        <div class="submission-slot submission-slot--plain">
          <div class="submission-slot__info">
            <div class="submission-label">
              Poster <span class="submission-required">required</span>
            </div>
            <p class="submission-muted">PDF only · up to {{ maxSizeLabel('poster') }}</p>

            <p v-if="storedFile('poster')" class="submission-file">
              <a :href="downloadUrl('poster')" target="_blank" rel="noopener noreferrer">
                {{ storedFile('poster')?.name }}
              </a>
              <span class="submission-muted"> ({{ formatSize(storedFile('poster')?.size) }})</span>
            </p>
            <p v-else class="submission-muted">Nothing attached yet.</p>
          </div>

          <div v-if="isOpen" class="submission-slot__actions">
            <input
              :ref="(el) => registerInput('poster', el)"
              type="file"
              class="submission-hidden-input"
              accept="application/pdf"
              @change="onFileChosen('poster', $event)"
            />
            <button
              class="btn btn-outline btn-sm"
              type="button"
              :disabled="busySlot === 'poster'"
              @click="pickFile('poster')"
            >
              {{ busySlot === 'poster' ? 'Uploading…' : storedFile('poster') ? 'Replace' : 'Upload' }}
            </button>
            <button
              v-if="storedFile('poster')"
              class="btn btn-outline btn-sm"
              type="button"
              :disabled="busySlot === 'poster'"
              @click="removeFile('poster')"
            >
              Remove
            </button>
          </div>
        </div>

        <p v-if="isPreviewLoading" class="submission-muted">Loading preview…</p>
        <iframe
          v-else-if="previewSource && storedFile('poster')"
          class="submission-preview submission-preview--tall"
          :src="previewSource"
          title="Poster preview"
        ></iframe>
        <p v-else-if="!storedFile('poster')" class="submission-muted submission-preview-empty">
          Once you upload a poster it will be shown here, so you can check the right file arrived.
        </p>
      </section>

      <!-- 3. Optional extras. Intentionally plain. -->
      <section v-show="activeTab === 'extras'" class="card">
        <div v-for="slot in EXTRA_SLOTS" :key="slot.key" class="submission-slot">
          <div class="submission-slot__info">
            <div class="submission-label">{{ slot.label }}</div>
            <p class="submission-muted">{{ slot.hint }} · up to {{ maxSizeLabel(slot.key) }}</p>

            <p v-if="storedFile(slot.key)" class="submission-file">
              <a :href="downloadUrl(slot.key)" target="_blank" rel="noopener noreferrer">
                {{ storedFile(slot.key)?.name }}
              </a>
              <span class="submission-muted"> ({{ formatSize(storedFile(slot.key)?.size) }})</span>
            </p>
            <p v-else class="submission-muted">Nothing attached yet.</p>
          </div>

          <div v-if="isOpen" class="submission-slot__actions">
            <input
              :ref="(el) => registerInput(slot.key, el)"
              type="file"
              class="submission-hidden-input"
              :accept="slot.accept"
              @change="onFileChosen(slot.key, $event)"
            />
            <button
              class="btn btn-outline btn-sm"
              type="button"
              :disabled="busySlot === slot.key"
              @click="pickFile(slot.key)"
            >
              {{ busySlot === slot.key ? 'Uploading…' : storedFile(slot.key) ? 'Replace' : 'Upload' }}
            </button>
            <button
              v-if="storedFile(slot.key)"
              class="btn btn-outline btn-sm"
              type="button"
              :disabled="busySlot === slot.key"
              @click="removeFile(slot.key)"
            >
              Remove
            </button>
          </div>
        </div>

        <div class="submission-field">
          <label class="submission-label" for="prototype-url">Prototype link (optional)</label>
          <input
            id="prototype-url"
            v-model="prototypeUrl"
            class="form-control"
            type="url"
            placeholder="https://…"
            :disabled="!isOpen"
          />
        </div>
      </section>

      <!-- Available from every tab: the server validates the whole entry, so
           there is no reason to force a student through the steps in order. -->
      <div v-if="isOpen" class="submission-actions">
        <button class="btn btn-outline" type="button" :disabled="isBusy" @click="onSaveDraft">
          {{ isSaving ? 'Saving…' : 'Save draft' }}
        </button>
        <button class="btn btn-primary" type="button" :disabled="isBusy" @click="onSubmit">
          {{ isSubmitting ? 'Submitting…' : detail.submission?.is_submitted ? 'Submit again' : 'Submit' }}
        </button>
      </div>
    </template>
  </div>
</template>

<script setup lang="ts">
import { computed, onBeforeUnmount, onMounted, reactive, ref, watch } from 'vue'
import { RouterLink, useRoute } from 'vue-router'
import { apiErrorFromUnknown } from '@/utils/apiError'
import {
  fetchPreviewObjectUrl,
  fetchSubmission,
  releasePreview,
  removeSubmissionFile,
  saveDraft,
  submissionFileDownloadUrl,
  submitEntry,
  uploadSubmissionFile,
  type StoredFile,
  type SubmissionDetail,
  type SubmissionSlot,
  type SubmissionWriteResult
} from '@/utils/submissionsAPI'

type TabKey = 'questions' | 'poster' | 'extras'

// Placeholder wording. Real guidance should come from the programme team, and
// is a good candidate for moving into the database the way questions were.
const TABS: { key: TabKey; label: string; instructions: string }[] = [
  {
    key: 'questions',
    label: 'Questions',
    instructions:
      'Answer each question in your own words. Nothing is sent anywhere until you press ' +
      'Submit, and you can keep editing right up to the deadline. Remember to press Save ' +
      'draft before closing this page.'
  },
  {
    key: 'poster',
    label: 'Poster',
    instructions:
      'Upload your poster as a single PDF. It appears below once uploaded, so you can check ' +
      'the right file arrived and that it exported correctly. A poster is required before you ' +
      'can submit.'
  },
  {
    key: 'extras',
    label: 'Additional materials',
    instructions:
      'Both of these are optional. Attach a scientific report as a PDF if you have written ' +
      'one, and a prototype as a file or a link — whichever suits your project better.'
  }
]

const EXTRA_SLOTS: { key: SubmissionSlot; label: string; hint: string; accept: string }[] = [
  { key: 'report', label: 'Scientific report', hint: 'PDF only. Optional.', accept: 'application/pdf' },
  { key: 'prototype', label: 'Prototype', hint: 'Any file type. Optional.', accept: '' }
]

// Fallback only for the moment between the page mounting and the first
// response arriving; the server's values replace these as soon as it loads.
const FALLBACK_MAX_FILE_SIZES: Record<SubmissionSlot, number> = {
  poster: 5 * 1024 * 1024,
  report: 5 * 1024 * 1024,
  prototype: 50 * 1024 * 1024
}

// How long a success note stays before clearing itself. Errors are never
// auto-cleared — one a student misses is worse than a banner that lingers.
const MESSAGE_TIMEOUT_MS = 4000

const route = useRoute()
const groupId = computed(() => String(route.params.id ?? ''))

const detail = ref<SubmissionDetail | null>(null)
const isLoading = ref(true)
const loadError = ref('')

const answers = reactive<Record<string, string>>({})
const prototypeUrl = ref('')

const activeTab = ref<TabKey>('questions')
const isSaving = ref(false)
const isSubmitting = ref(false)
const busySlot = ref<SubmissionSlot | ''>('')
const previewSource = ref('')
const isPreviewLoading = ref(false)
const message = ref('')
const isError = ref(false)

const fileInputs: Partial<Record<SubmissionSlot, HTMLInputElement>> = {}

const questions = computed(() => detail.value?.questions ?? [])
const maxFileSizes = computed(() => detail.value?.max_file_sizes ?? FALLBACK_MAX_FILE_SIZES)

function maxSizeFor(slot: SubmissionSlot) {
  return maxFileSizes.value[slot] ?? FALLBACK_MAX_FILE_SIZES[slot]
}

function maxSizeLabel(slot: SubmissionSlot) {
  return formatSize(maxSizeFor(slot))
}
const isOpen = computed(() => Boolean(detail.value?.deadline.is_open))
const isBusy = computed(() => isSaving.value || isSubmitting.value || Boolean(busySlot.value))
const activeTabConfig = computed(() => TABS.find((tab) => tab.key === activeTab.value) ?? TABS[0])

const statusLabel = computed(() => {
  if (!detail.value) return ''
  if (detail.value.submission?.is_submitted) return 'Submitted'
  return isOpen.value ? 'Draft' : 'Not submitted'
})

const statusClass = computed(() => {
  if (detail.value?.submission?.is_submitted) return 'status-active'
  return isOpen.value ? 'status-pending' : 'status-danger'
})

const deadlineHeadline = computed(() => {
  const closesAt = detail.value?.deadline.closes_at
  if (!closesAt) return 'No deadline has been set yet.'
  return isOpen.value ? `Open until ${formatDate(closesAt)}` : `Closed on ${formatDate(closesAt)}`
})

const deadlineDetail = computed(() => {
  if (!detail.value?.deadline.closes_at) {
    return 'An administrator needs to set a deadline before entries can be saved.'
  }
  // Times are stored in UTC; name the viewer's zone so "when does it close?"
  // is never ambiguous.
  return `Shown in your local time (${localZone}).`
})

const localZone = Intl.DateTimeFormat().resolvedOptions().timeZone

/** Short completeness marker per step, so nothing is silently left undone. */
function stepState(key: TabKey): { label: string; tone: string } {
  if (key === 'questions') {
    const required = questions.value.filter((question) => question.is_required)
    if (!required.length) return { label: '—', tone: 'neutral' }
    const answered = required.every((question) => (answers[question.key] || '').trim())
    return answered ? { label: 'Done', tone: 'done' } : { label: 'To do', tone: 'todo' }
  }
  if (key === 'poster') {
    return storedFile('poster') ? { label: 'Done', tone: 'done' } : { label: 'To do', tone: 'todo' }
  }
  const attached = EXTRA_SLOTS.filter((slot) => storedFile(slot.key)).length
  return { label: attached ? `${attached} added` : 'Optional', tone: 'neutral' }
}

function formatDate(value: string) {
  return new Date(value).toLocaleString(undefined, {
    dateStyle: 'medium',
    timeStyle: 'short'
  })
}

function formatSize(bytes: number | null | undefined) {
  if (!bytes && bytes !== 0) return 'unknown size'
  if (bytes >= 1024 * 1024) {
    const mb = bytes / (1024 * 1024)
    // Drop the decimal on round figures so the stated limit reads "50 MB".
    return `${Number.isInteger(mb) ? mb : mb.toFixed(1)} MB`
  }
  if (bytes >= 1024) return `${Math.round(bytes / 1024)} KB`
  return `${bytes} bytes`
}

function storedFile(slot: SubmissionSlot): StoredFile | null {
  return detail.value?.submission?.[slot] ?? null
}

function downloadUrl(slot: SubmissionSlot) {
  return submissionFileDownloadUrl(groupId.value, slot)
}

function registerInput(slot: SubmissionSlot, el: unknown) {
  if (el instanceof HTMLInputElement) fileInputs[slot] = el
}

function pickFile(slot: SubmissionSlot) {
  fileInputs[slot]?.click()
}

let messageTimer: ReturnType<typeof setTimeout> | null = null

function setMessage(text: string, error = false) {
  if (messageTimer) clearTimeout(messageTimer)
  message.value = text
  isError.value = error

  // Confirmations are noise once read, so they clear themselves. Errors stay
  // until dismissed — the student needs to act on them.
  if (text && !error) {
    messageTimer = setTimeout(() => {
      message.value = ''
      messageTimer = null
    }, MESSAGE_TIMEOUT_MS)
  }
}

function dismissMessage() {
  if (messageTimer) clearTimeout(messageTimer)
  messageTimer = null
  message.value = ''
}

/** Remaining characters for one question, or null when it has no limit. */
function charactersLeft(key: string, limit: number | null) {
  if (!limit) return null
  return limit - (answers[key] || '').length
}

function applyResult(result: SubmissionWriteResult) {
  if (!detail.value) return
  detail.value = { ...detail.value, deadline: result.deadline, submission: result.submission }
}

/** Discard the in-memory copy; without this the browser holds the whole file
 *  for the life of the tab. */
function clearPreview() {
  releasePreview(previewSource.value)
  previewSource.value = ''
  isPreviewLoading.value = false
}

/**
 * Keep the poster preview in step with what is actually attached.
 *
 * Called whenever the tab changes or the poster does, rather than being
 * toggled by hand — the preview is always-on for this slot, and a stale panel
 * showing a replaced or deleted file would misrepresent the entry.
 */
async function syncPosterPreview() {
  clearPreview()
  if (activeTab.value !== 'poster' || !storedFile('poster')) return

  isPreviewLoading.value = true
  try {
    previewSource.value = await fetchPreviewObjectUrl(groupId.value, 'poster')
  } catch (error) {
    setMessage(apiErrorFromUnknown(error).message, true)
  } finally {
    isPreviewLoading.value = false
  }
}

/** Copy server state into the editable fields. */
function syncFromDetail() {
  const submission = detail.value?.submission
  questions.value.forEach((question) => {
    answers[question.key] = submission?.answers?.[question.key] ?? ''
  })
  prototypeUrl.value = submission?.prototype_url ?? ''
}

async function load() {
  isLoading.value = true
  loadError.value = ''
  try {
    detail.value = await fetchSubmission(groupId.value)
    syncFromDetail()
    await syncPosterPreview()
  } catch (error) {
    loadError.value = apiErrorFromUnknown(error).message
  } finally {
    isLoading.value = false
  }
}

async function onSaveDraft() {
  isSaving.value = true
  setMessage('')
  try {
    applyResult(
      await saveDraft(groupId.value, {
        answers: { ...answers },
        prototype_url: prototypeUrl.value
      })
    )
    setMessage('Draft saved.')
  } catch (error) {
    setMessage(apiErrorFromUnknown(error).message, true)
  } finally {
    isSaving.value = false
  }
}

async function onSubmit() {
  isSubmitting.value = true
  setMessage('')
  try {
    // Save first so submitting never leaves unsaved edits behind.
    applyResult(
      await saveDraft(groupId.value, {
        answers: { ...answers },
        prototype_url: prototypeUrl.value
      })
    )
    applyResult(await submitEntry(groupId.value))
    setMessage('Submitted. You can keep revising until the deadline.')
  } catch (error) {
    const apiError = apiErrorFromUnknown(error)
    // The backend names the unanswered questions, so repeat them here rather
    // than leaving the student to hunt for which box is blank.
    const missing = apiError.body?.missing
    if (Array.isArray(missing) && missing.length) {
      setMessage(`${apiError.message} Still needed: ${missing.join(' · ')}`, true)
    } else {
      setMessage(apiError.message, true)
    }
  } finally {
    isSubmitting.value = false
  }
}

async function onFileChosen(slot: SubmissionSlot, event: Event) {
  const input = event.target as HTMLInputElement
  const file = input.files?.[0]
  if (!file) return

  // Refuse before uploading. The server enforces this too — checking here only
  // saves the student watching a doomed upload crawl to completion.
  if (file.size > maxSizeFor(slot)) {
    setMessage(
      `That file is ${formatSize(file.size)}. The limit is ${maxSizeLabel(slot)} — ` +
        'try exporting it at a lower resolution.',
      true
    )
    input.value = ''
    return
  }

  busySlot.value = slot
  setMessage('')
  try {
    applyResult(await uploadSubmissionFile(groupId.value, slot, file))
    setMessage(`${slot} uploaded.`)
    if (slot === 'poster') await syncPosterPreview()
  } catch (error) {
    setMessage(apiErrorFromUnknown(error).message, true)
  } finally {
    busySlot.value = ''
    // Clear the input so choosing the same file again still fires a change.
    input.value = ''
  }
}

async function removeFile(slot: SubmissionSlot) {
  busySlot.value = slot
  setMessage('')
  try {
    applyResult(await removeSubmissionFile(groupId.value, slot))
    setMessage(`${slot} removed.`)
    if (slot === 'poster') await syncPosterPreview()
  } catch (error) {
    setMessage(apiErrorFromUnknown(error).message, true)
  } finally {
    busySlot.value = ''
  }
}

onMounted(load)
watch(activeTab, syncPosterPreview)
watch(groupId, () => {
  clearPreview()
  load()
})
// Releases the in-memory file if the student navigates away with a preview open.
onBeforeUnmount(clearPreview)
</script>

<style scoped>
.submission-back {
  color: var(--primary-green, #0f6b4f);
  text-decoration: none;
  font-size: 0.9rem;
}

.submission-header {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 1rem;
  flex-wrap: wrap;
  margin: 0.5rem 0 1rem;
}

.submission-heading {
  font-size: 1.5rem;
  font-weight: 700;
  margin: 0;
}

.submission-deadline {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 1rem;
  flex-wrap: wrap;
}

.submission-closed {
  border-left: 4px solid var(--primary-green, #0f6b4f);
}

.submission-message {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 0.75rem;
  padding: 0.5rem 0.85rem;
  margin-bottom: 1rem;
  border-radius: 6px;
  border-left: 4px solid var(--primary-green, #0f6b4f);
  background: #f2f8f5;
  font-size: 0.9rem;
}

.submission-message--error {
  border-left-color: #c0392b;
  background: #fdecea;
  color: #c0392b;
}

.submission-message__close {
  border: none;
  background: none;
  cursor: pointer;
  font-size: 1.1rem;
  line-height: 1;
  color: inherit;
  opacity: 0.6;
  padding: 0 0.2rem;
}

.submission-message__close:hover {
  opacity: 1;
}

.submission-count {
  font-size: 0.8rem;
  color: #4b5563;
  margin: 0.3rem 0 0;
  font-variant-numeric: tabular-nums;
}

.submission-count.is-near-limit {
  color: #b45309;
  font-weight: 600;
}

/* Step strip */
.submission-steps {
  display: flex;
  gap: 0.5rem;
  margin-bottom: 1rem;
  flex-wrap: wrap;
}

.submission-step {
  flex: 1 1 180px;
  display: flex;
  align-items: center;
  gap: 0.6rem;
  padding: 0.7rem 0.9rem;
  border: 1px solid #e5e7eb;
  border-radius: 8px;
  background: #fff;
  cursor: pointer;
  text-align: left;
  font: inherit;
}

.submission-step:hover {
  border-color: var(--primary-green, #0f6b4f);
}

.submission-step.is-active {
  border-color: var(--primary-green, #0f6b4f);
  box-shadow: inset 0 -3px 0 var(--primary-green, #0f6b4f);
}

.submission-step__index {
  display: inline-flex;
  align-items: center;
  justify-content: center;
  width: 22px;
  height: 22px;
  border-radius: 50%;
  background: #eef2f1;
  font-size: 0.8rem;
  font-weight: 600;
  flex-shrink: 0;
}

.submission-step.is-active .submission-step__index {
  background: var(--primary-green, #0f6b4f);
  color: #fff;
}

.submission-step__label {
  font-weight: 600;
  flex: 1;
}

.submission-step__state {
  font-size: 0.75rem;
  padding: 0.1rem 0.45rem;
  border-radius: 999px;
  white-space: nowrap;
}

.submission-step__state.is-done {
  background: #e6f4ec;
  color: #0f6b4f;
}

.submission-step__state.is-todo {
  background: #fdecea;
  color: #c0392b;
}

.submission-step__state.is-neutral {
  background: #f1f2f4;
  color: #6b7280;
}

.submission-instructions {
  border-left: 4px solid var(--primary-green, #0f6b4f);
}

.submission-instructions p {
  margin: 0.4rem 0 0;
  color: #4b5563;
}

.submission-field {
  margin-bottom: 1.25rem;
}

.submission-label {
  display: block;
  font-weight: 600;
  margin-bottom: 0.4rem;
}

.submission-textarea {
  width: 100%;
  resize: vertical;
}

.submission-muted {
  color: #6b7280;
  font-size: 0.85rem;
  margin: 0.2rem 0;
}

.submission-required {
  color: #c0392b;
  font-size: 0.75rem;
  font-weight: 600;
  margin-left: 0.4rem;
}

.submission-slot {
  display: flex;
  align-items: flex-start;
  justify-content: space-between;
  gap: 1rem;
  flex-wrap: wrap;
  padding: 0.9rem 0;
  border-bottom: 1px solid #e5e7eb;
}

.submission-slot--plain {
  border-bottom: none;
  padding-top: 0;
}

.submission-slot__actions {
  display: flex;
  gap: 0.5rem;
}

.submission-hidden-input {
  display: none;
}

.submission-file {
  margin: 0.3rem 0 0;
  font-size: 0.9rem;
}

.submission-preview {
  width: 100%;
  height: 60vh;
  min-height: 320px;
  margin-top: 0.75rem;
  border: 1px solid #e5e7eb;
  border-radius: 6px;
  background: #fff;
}

.submission-preview--tall {
  height: 72vh;
}

.submission-preview-empty {
  padding: 2.5rem 1rem;
  text-align: center;
  border: 1px dashed #d1d5db;
  border-radius: 6px;
  margin-top: 0.75rem;
}

.submission-actions {
  display: flex;
  gap: 0.75rem;
  justify-content: flex-end;
  margin: 1.5rem 0 3rem;
}
</style>
