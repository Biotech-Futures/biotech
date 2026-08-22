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
        <h1 class="submission-heading">Submission</h1>
      </header>

      <!-- Deadline. Shown prominently because it governs everything below. -->
      <div class="card submission-deadline">
        <div>
          <strong>{{ deadlineHeadline }}</strong>
          <!-- Quiet by default; it only earns emphasis in the last day, when
               the time left is genuinely the thing a student needs to know. -->
          <span
            v-if="timeRemaining"
            class="submission-remaining"
            :class="{ 'is-near': isDeadlineNear }"
          >
            · {{ timeRemaining }}
          </span>
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
          <!-- States a fact rather than judging completion: text in every box
               does not mean the answers are finished, so calling a section
               "Done" would tell a student something we cannot know. -->
          <span class="submission-step__state">{{ stepSummary(tab.key) }}</span>
        </button>
      </nav>

      <!-- Guidance comes from the database, so admins can reword it. -->
      <div v-if="activeInstructions" class="card submission-instructions">
        <h2 class="card-title">{{ activeTabConfig.label }}</h2>
        <p>{{ activeInstructions }}</p>
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
            <span v-if="question.is_required" class="submission-required" title="Required" aria-label="required">*</span>
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
          </p>
        </div>
      </section>

      <!-- 2. Poster, with the preview kept open — this tab exists mainly to
           give the document room to be read. -->
      <section v-show="activeTab === 'poster'" class="card">
        <div class="submission-slot submission-slot--plain">
          <div class="submission-slot__info">
            <div class="submission-label">
              Poster <span class="submission-required" title="Required" aria-label="required">*</span>
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
              {{ busySlot === 'poster' ? `Uploading… ${uploadPercent}%` : storedFile('poster') ? 'Replace' : 'Upload' }}
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

        <!-- Same shape as the resource library's preview panel, so a file looks
             the same wherever it is viewed in the platform. Guarded on the slot
             as well as the source: hidden tabs stay in the DOM, so without that
             this frame would also load whatever the report preview fetched. -->
        <article class="preview-panel">
          <div class="preview-header">
            <h2>Preview</h2>
            <!-- Always offered: some browsers refuse to display an embedded PDF
                 at all, and a student must never be left unable to check their
                 own file. Opens the same endpoint as a normal page load. -->
            <a
              v-if="storedFile('poster')"
              class="btn btn-outline btn-sm"
              :href="previewUrlFor('poster')"
              target="_blank"
              rel="noopener noreferrer"
            >
              Open in new tab
            </a>
          </div>

          <div v-if="isPosterPreviewOpen && isPreviewLoading" class="preview-empty">
            <p>Preparing preview…</p>
          </div>
          <iframe
            v-else-if="isPosterPreviewOpen && previewSource && storedFile('poster')"
            class="preview-frame"
            title="Poster preview"
            :src="previewSource"
          ></iframe>
          <div v-else class="preview-empty">
            <i class="fas fa-file-pdf" aria-hidden="true"></i>
            <p>Once you upload a poster it appears here, so you can check the right file arrived.</p>
          </div>
        </article>
      </section>

      <!-- 3. Optional extras, as two blocks: the report gets the same treatment
           as the poster since it is also a readable document; the prototype is
           a plain upload because it can be any file type. -->
      <div v-show="activeTab === 'extras'">
        <section class="card">
          <div class="submission-slot submission-slot--plain">
            <div class="submission-slot__info">
              <div class="submission-label">Scientific report</div>
              <p class="submission-muted">PDF only. Optional · up to {{ maxSizeLabel('report') }}</p>

              <p v-if="storedFile('report')" class="submission-file">
                <a :href="downloadUrl('report')" target="_blank" rel="noopener noreferrer">
                  {{ storedFile('report')?.name }}
                </a>
                <span class="submission-muted"> ({{ formatSize(storedFile('report')?.size) }})</span>
              </p>
              <p v-else class="submission-muted">Nothing attached yet.</p>
            </div>

            <div v-if="isOpen" class="submission-slot__actions">
              <input
                :ref="(el) => registerInput('report', el)"
                type="file"
                class="submission-hidden-input"
                accept="application/pdf"
                @change="onFileChosen('report', $event)"
              />
              <button
                class="btn btn-outline btn-sm"
                type="button"
                :disabled="busySlot === 'report'"
                @click="pickFile('report')"
              >
                {{ busySlot === 'report' ? `Uploading… ${uploadPercent}%` : storedFile('report') ? 'Replace' : 'Upload' }}
              </button>
              <button
                v-if="storedFile('report')"
                class="btn btn-outline btn-sm"
                type="button"
                :disabled="busySlot === 'report'"
                @click="removeFile('report')"
              >
                Remove
              </button>
            </div>
          </div>

          <article class="preview-panel">
            <div class="preview-header">
              <h2>Preview</h2>
              <a
                v-if="storedFile('report')"
                class="btn btn-outline btn-sm"
                :href="previewUrlFor('report')"
                target="_blank"
                rel="noopener noreferrer"
              >
                Open in new tab
              </a>
            </div>

            <div v-if="isReportPreviewOpen && isPreviewLoading" class="preview-empty">
              <p>Preparing preview…</p>
            </div>
            <iframe
              v-else-if="isReportPreviewOpen && previewSource && storedFile('report')"
              class="preview-frame"
              title="Scientific report preview"
              :src="previewSource"
            ></iframe>
            <div v-else class="preview-empty">
              <i class="fas fa-file-pdf" aria-hidden="true"></i>
              <p>A scientific report is optional. If you upload one it appears here.</p>
            </div>
          </article>
        </section>

        <section class="card">
          <div class="submission-slot submission-slot--plain">
            <div class="submission-slot__info">
              <div class="submission-label">Prototype</div>
              <p class="submission-muted">
                Any file type. Optional · up to {{ maxSizeLabel('prototype') }}
              </p>

              <p v-if="storedFile('prototype')" class="submission-file">
                <a :href="downloadUrl('prototype')" target="_blank" rel="noopener noreferrer">
                  {{ storedFile('prototype')?.name }}
                </a>
                <span class="submission-muted"> ({{ formatSize(storedFile('prototype')?.size) }})</span>
              </p>
              <p v-else class="submission-muted">Nothing attached yet.</p>
            </div>

            <div v-if="isOpen" class="submission-slot__actions">
              <input
                :ref="(el) => registerInput('prototype', el)"
                type="file"
                class="submission-hidden-input"
                @change="onFileChosen('prototype', $event)"
              />
              <button
                class="btn btn-outline btn-sm"
                type="button"
                :disabled="busySlot === 'prototype'"
                @click="pickFile('prototype')"
              >
                {{ busySlot === 'prototype' ? `Uploading… ${uploadPercent}%` : storedFile('prototype') ? 'Replace' : 'Upload' }}
              </button>
              <button
                v-if="storedFile('prototype')"
                class="btn btn-outline btn-sm"
                type="button"
                :disabled="busySlot === 'prototype'"
                @click="removeFile('prototype')"
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
      </div>

      <!-- Available from every tab: the server validates the whole entry, so
           there is no reason to force a student through the steps in order. -->
      <div v-if="isOpen" class="submission-actions">
        <!-- Auto-save is invisible by design, so it needs to say so somewhere;
             without this the student cannot tell whether their work is safe. -->
        <span class="submission-savestate" :class="{ 'is-error': saveState === 'error' }">
          {{ saveStateLabel }}
        </span>
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
  submissionFilePreviewUrl,
  submitEntry,
  uploadSubmissionFile,
  type StoredFile,
  type SubmissionDetail,
  type SubmissionSlot,
  type SubmissionWriteResult
} from '@/utils/submissionsAPI'

type TabKey = 'questions' | 'poster' | 'extras'

// Section names only. The guidance text itself lives in the database so the
// programme team can reword it without a code change — see the `instructions`
// field on the API response.
const TABS: { key: TabKey; label: string }[] = [
  { key: 'questions', label: 'Questions' },
  { key: 'poster', label: 'Poster' },
  { key: 'extras', label: 'Additional materials' }
]

// How long to wait after typing stops before saving. Long enough not to fire
// mid-word, short enough that a closed laptop rarely costs anything.
const AUTOSAVE_DELAY_MS = 2000

// Both optional, and both live on the Additional materials tab.
const EXTRA_SLOTS: SubmissionSlot[] = ['report', 'prototype']

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
const uploadPercent = ref(0)
// Drives the countdown; ticked by an interval so the display stays live.
const now = ref(Date.now())
const previewSource = ref('')
// Which slot the loaded preview belongs to; '' when nothing is showing.
const previewSlot = ref<SubmissionSlot | ''>('')
const isPreviewLoading = ref(false)
const message = ref('')
const isError = ref(false)

// Auto-save state. `savedSnapshot` is what the server last accepted, so a
// change can be detected without saving on every keystroke.
const saveState = ref<'idle' | 'unsaved' | 'error'>('idle')
const lastSavedAt = ref<Date | null>(null)
const savedSnapshot = ref('')
let autosaveTimer: ReturnType<typeof setTimeout> | null = null

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
const activeInstructions = computed(() => detail.value?.instructions?.[activeTab.value] ?? '')
const isReportPreviewOpen = computed(() => previewSlot.value === 'report')
const isPosterPreviewOpen = computed(() => previewSlot.value === 'poster')

const saveStateLabel = computed(() => {
  if (isSaving.value) return 'Saving…'
  if (saveState.value === 'error') return 'Could not save'
  if (saveState.value === 'unsaved') return 'Unsaved changes'
  if (lastSavedAt.value) return `Saved ${formatTime(lastSavedAt.value)}`
  return ''
})

const deadlineHeadline = computed(() => {
  const closesAt = detail.value?.deadline.closes_at
  if (!closesAt) return 'No deadline has been set yet.'
  return isOpen.value ? `Open until ${formatDate(closesAt)}` : `Closed on ${formatDate(closesAt)}`
})

/** "3 days left" — urgency a fixed date does not convey on its own. */
const timeRemaining = computed(() => {
  const closesAt = detail.value?.deadline.closes_at
  if (!closesAt || !isOpen.value) return ''

  const msLeft = new Date(closesAt).getTime() - now.value
  if (msLeft <= 0) return 'Closing now'

  const minutes = Math.floor(msLeft / 60000)
  const hours = Math.floor(minutes / 60)
  const days = Math.floor(hours / 24)

  if (days >= 1) return `${days} day${days === 1 ? '' : 's'} left`
  if (hours >= 1) return `${hours} hour${hours === 1 ? '' : 's'} left`
  return `${minutes} minute${minutes === 1 ? '' : 's'} left`
})

// Under a day to go is when the wording should start to feel different.
const isDeadlineNear = computed(() => {
  const closesAt = detail.value?.deadline.closes_at
  if (!closesAt || !isOpen.value) return false
  return new Date(closesAt).getTime() - now.value < 24 * 60 * 60 * 1000
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

/**
 * A factual note per step — what is present, not whether it is finished.
 *
 * The earlier version marked a section "Done" as soon as every box held any
 * text at all, which claimed far more than it knew. Counting what has been
 * filled in leaves the judgement to the student.
 */
function stepSummary(key: TabKey): string {
  if (key === 'questions') {
    const total = questions.value.length
    if (!total) return ''
    const answered = questions.value.filter((q) => (answers[q.key] || '').trim()).length
    return `${answered} of ${total} answered`
  }
  if (key === 'poster') {
    return storedFile('poster') ? 'Attached' : 'Not attached'
  }
  const attached = EXTRA_SLOTS.filter((slot) => storedFile(slot)).length
  return attached ? `${attached} attached` : 'Optional'
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

/** Direct link to the inline endpoint, for opening in a tab of its own. */
function previewUrlFor(slot: SubmissionSlot) {
  return submissionFilePreviewUrl(groupId.value, slot)
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
  previewSlot.value = ''
  isPreviewLoading.value = false
}

/** Load one slot's file for display. Only ever called for PDF slots. */
async function loadPreview(slot: SubmissionSlot) {
  clearPreview()
  if (!storedFile(slot)) return

  previewSlot.value = slot
  isPreviewLoading.value = true
  try {
    previewSource.value = await fetchPreviewObjectUrl(groupId.value, slot)
  } catch (error) {
    setMessage(apiErrorFromUnknown(error).message, true)
    previewSlot.value = ''
  } finally {
    isPreviewLoading.value = false
  }
}

/**
 * Keep the preview in step with the tab and with what is attached.
 *
 * The poster's preview is always-on because that tab exists to display it; the
 * report's is opened by hand, since it shares its tab with the prototype. In
 * both cases a stale panel showing a replaced or deleted file would
 * misrepresent the entry, so anything not currently valid is dropped.
 */
async function syncPreviewForTab() {
  // Each document tab shows its own file; only one is ever loaded at a time,
  // so switching tabs swaps the preview rather than stacking them.
  if (activeTab.value === 'poster') {
    await loadPreview('poster')
    return
  }
  if (activeTab.value === 'extras') {
    await loadPreview('report')
    return
  }
  clearPreview()
}

/** Copy server state into the editable fields. */
function syncFromDetail() {
  const submission = detail.value?.submission
  questions.value.forEach((question) => {
    answers[question.key] = submission?.answers?.[question.key] ?? ''
  })
  prototypeUrl.value = submission?.prototype_url ?? ''
  // Baseline for change detection: what was just loaded is, by definition,
  // what the server already has.
  savedSnapshot.value = currentSnapshot()
  saveState.value = 'idle'
}

async function load() {
  isLoading.value = true
  loadError.value = ''
  try {
    detail.value = await fetchSubmission(groupId.value)
    syncFromDetail()
    await syncPreviewForTab()
  } catch (error) {
    loadError.value = apiErrorFromUnknown(error).message
  } finally {
    isLoading.value = false
  }
}

/** Everything auto-save watches, as a comparable string. */
function currentSnapshot() {
  return JSON.stringify({ answers, prototypeUrl: prototypeUrl.value })
}

function formatTime(value: Date) {
  return value.toLocaleTimeString(undefined, { hour: '2-digit', minute: '2-digit' })
}

/**
 * Persist the draft. Shared by the button and by auto-save.
 *
 * `silent` keeps auto-save from posting a confirmation banner every couple of
 * seconds — the status line beside the buttons already reports it.
 */
async function persistDraft({ silent }: { silent: boolean }) {
  if (isSaving.value) return
  const snapshot = currentSnapshot()

  isSaving.value = true
  if (!silent) setMessage('')
  try {
    applyResult(
      await saveDraft(groupId.value, {
        answers: { ...answers },
        prototype_url: prototypeUrl.value
      })
    )
    savedSnapshot.value = snapshot
    lastSavedAt.value = new Date()
    saveState.value = 'idle'
    if (!silent) setMessage('Draft saved.')
  } catch (error) {
    saveState.value = 'error'
    // Auto-save failures still surface: silently losing work is the exact
    // problem auto-save exists to prevent.
    setMessage(apiErrorFromUnknown(error).message, true)
  } finally {
    isSaving.value = false
  }
}

function onSaveDraft() {
  if (autosaveTimer) clearTimeout(autosaveTimer)
  return persistDraft({ silent: false })
}

/** Queue a save once typing pauses, if anything actually changed. */
function scheduleAutosave() {
  if (!isOpen.value || isSubmitting.value) return
  if (currentSnapshot() === savedSnapshot.value) return

  saveState.value = 'unsaved'
  if (autosaveTimer) clearTimeout(autosaveTimer)
  autosaveTimer = setTimeout(() => {
    autosaveTimer = null
    persistDraft({ silent: true })
  }, AUTOSAVE_DELAY_MS)
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
    uploadPercent.value = 0
    applyResult(
      await uploadSubmissionFile(groupId.value, slot, file, (percent) => {
        uploadPercent.value = percent
      })
    )
    setMessage(`${slot} uploaded.`)
    // Refresh a showing preview so it never displays the file just replaced.
    if (slot === 'poster' || slot === 'report') await loadPreview(slot)
  } catch (error) {
    setMessage(apiErrorFromUnknown(error).message, true)
  } finally {
    busySlot.value = ''
    uploadPercent.value = 0
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
    // Never leave a deleted document on screen.
    if (slot === previewSlot.value) clearPreview()
  } catch (error) {
    setMessage(apiErrorFromUnknown(error).message, true)
  } finally {
    busySlot.value = ''
  }
}

onMounted(load)

// One tick a minute is enough for a countdown measured in days and hours, and
// avoids re-rendering the page every second for no visible change.
const clockTimer = setInterval(() => {
  now.value = Date.now()
}, 60000)

// Any edit to an answer or the prototype link queues a save.
watch([answers, prototypeUrl], scheduleAutosave, { deep: true })

watch(activeTab, () => {
  // Leaving a tab is a natural checkpoint — save now rather than waiting out
  // the timer, in case the student closes the page from the next tab.
  if (autosaveTimer) {
    clearTimeout(autosaveTimer)
    autosaveTimer = null
    persistDraft({ silent: true })
  }
  syncPreviewForTab()
})

watch(groupId, () => {
  clearPreview()
  load()
})

onBeforeUnmount(() => {
  // Releases the in-memory preview file and drops pending timers rather than
  // letting them fire against a page that no longer exists.
  if (autosaveTimer) clearTimeout(autosaveTimer)
  clearInterval(clockTimer)
  clearPreview()
})
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

.submission-remaining {
  color: #6b7280;
  font-size: 0.9rem;
  margin-left: 0.35rem;
}

.submission-remaining.is-near {
  color: #b45309;
  font-weight: 600;
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
  color: #6b7280;
  white-space: nowrap;
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

/* A quiet marker rather than a badge — it appears beside most labels, so
   anything louder reads as an error state on a form that is merely blank. */
.submission-required {
  color: #c0392b;
  font-weight: 600;
  margin-left: 0.2rem;
  cursor: help;
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

/* Mirrors the resource library's preview panel so a file looks the same
   wherever it is viewed. The panel carries the border and clips the frame,
   which is why the frame itself has none. */
.preview-panel {
  background: var(--white, #ffffff);
  border-radius: 8px;
  box-shadow: 0 2px 4px var(--shadow, rgba(0, 0, 0, 0.08));
  min-height: 560px;
  overflow: hidden;
  margin-top: 1rem;
}

.preview-header {
  align-items: center;
  border-bottom: 1px solid var(--border-light, #e5e7eb);
  display: flex;
  justify-content: space-between;
  padding: 1rem 1.25rem;
}

.preview-header h2 {
  font-size: 1.25rem;
  margin: 0;
}

.preview-frame {
  border: 0;
  display: block;
  height: 620px;
  width: 100%;
}

.preview-empty {
  align-items: center;
  color: var(--text-muted, #6b7280);
  display: flex;
  flex-direction: column;
  gap: 0.85rem;
  min-height: 480px;
  justify-content: center;
  padding: 2rem;
  text-align: center;
}

.preview-empty i {
  color: var(--dark-green, #0f6b4f);
  font-size: 2rem;
}

.submission-actions {
  display: flex;
  align-items: center;
  gap: 0.75rem;
  justify-content: flex-end;
  margin: 1.5rem 0 3rem;
}

.submission-savestate {
  font-size: 0.85rem;
  color: #6b7280;
  margin-right: auto;
}

.submission-savestate.is-error {
  color: #c0392b;
  font-weight: 600;
}
</style>
