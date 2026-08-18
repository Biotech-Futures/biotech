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

      <p v-if="message" class="card submission-message" :class="{ 'submission-message--error': isError }">
        {{ message }}
      </p>

      <!-- Short-answer questions -->
      <section class="card">
        <div class="card-header"><h2 class="card-title">Questions</h2></div>
        <div v-for="question in QUESTIONS" :key="question.key" class="submission-field">
          <label class="submission-label" :for="question.key">{{ question.label }}</label>
          <textarea
            :id="question.key"
            v-model="answers[question.key]"
            class="form-control submission-textarea"
            rows="4"
            :disabled="!isOpen"
          ></textarea>
        </div>
      </section>

      <!-- Attachments -->
      <section class="card">
        <div class="card-header"><h2 class="card-title">Attachments</h2></div>

        <div v-for="slot in SLOTS" :key="slot.key" class="submission-slot">
          <div class="submission-slot__info">
            <div class="submission-label">
              {{ slot.label }}
              <span v-if="slot.required" class="submission-required">required</span>
            </div>
            <p class="submission-muted">{{ slot.hint }}</p>

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
import { computed, onMounted, reactive, ref, watch } from 'vue'
import { RouterLink, useRoute } from 'vue-router'
import { apiErrorFromUnknown } from '@/utils/apiError'
import {
  fetchSubmission,
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

// Placeholder wording until the client sends their current Qualtrics form.
// Answers are stored keyed by these ids, so swapping the questions later is a
// change to this list alone — no database migration.
const QUESTIONS = [
  { key: 'q1', label: 'What problem does your project address?' },
  { key: 'q2', label: 'Describe your approach and methodology.' },
  { key: 'q3', label: 'What are your key findings or results?' },
  { key: 'q4', label: 'What impact could your project have?' }
] as const

const SLOTS: { key: SubmissionSlot; label: string; hint: string; accept: string; required: boolean }[] = [
  {
    key: 'poster',
    label: 'Poster',
    hint: 'PDF only. Must be attached before you can submit.',
    accept: 'application/pdf',
    required: true
  },
  { key: 'report', label: 'Scientific report', hint: 'PDF only. Optional.', accept: 'application/pdf', required: false },
  { key: 'prototype', label: 'Prototype', hint: 'Any file type. Optional.', accept: '', required: false }
]

const route = useRoute()
const groupId = computed(() => String(route.params.id ?? ''))

const detail = ref<SubmissionDetail | null>(null)
const isLoading = ref(true)
const loadError = ref('')

const answers = reactive<Record<string, string>>({})
const prototypeUrl = ref('')

const isSaving = ref(false)
const isSubmitting = ref(false)
const busySlot = ref<SubmissionSlot | ''>('')
const message = ref('')
const isError = ref(false)

const fileInputs: Partial<Record<SubmissionSlot, HTMLInputElement>> = {}

const isOpen = computed(() => Boolean(detail.value?.deadline.is_open))
const isBusy = computed(() => isSaving.value || isSubmitting.value || Boolean(busySlot.value))

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

function formatDate(value: string) {
  return new Date(value).toLocaleString(undefined, {
    dateStyle: 'medium',
    timeStyle: 'short'
  })
}

function formatSize(bytes: number | null | undefined) {
  if (!bytes && bytes !== 0) return 'unknown size'
  if (bytes >= 1024 * 1024) return `${(bytes / (1024 * 1024)).toFixed(1)} MB`
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

function setMessage(text: string, error = false) {
  message.value = text
  isError.value = error
}

function applyResult(result: SubmissionWriteResult) {
  if (!detail.value) return
  detail.value = { ...detail.value, deadline: result.deadline, submission: result.submission }
}

/** Copy server state into the editable fields. */
function syncFromDetail() {
  const submission = detail.value?.submission
  QUESTIONS.forEach((question) => {
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
    setMessage(apiErrorFromUnknown(error).message, true)
  } finally {
    isSubmitting.value = false
  }
}

async function onFileChosen(slot: SubmissionSlot, event: Event) {
  const input = event.target as HTMLInputElement
  const file = input.files?.[0]
  if (!file) return

  busySlot.value = slot
  setMessage('')
  try {
    applyResult(await uploadSubmissionFile(groupId.value, slot, file))
    setMessage(`${slot} uploaded.`)
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
  } catch (error) {
    setMessage(apiErrorFromUnknown(error).message, true)
  } finally {
    busySlot.value = ''
  }
}

onMounted(load)
watch(groupId, load)
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

.submission-closed,
.submission-message {
  border-left: 4px solid var(--primary-green, #0f6b4f);
}

.submission-message--error {
  border-left-color: #c0392b;
  color: #c0392b;
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

.submission-actions {
  display: flex;
  gap: 0.75rem;
  justify-content: flex-end;
  margin: 1.5rem 0 3rem;
}
</style>
