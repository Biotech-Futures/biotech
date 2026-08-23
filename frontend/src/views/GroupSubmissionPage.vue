<template>
  <div class="content-area">
    <div v-if="isLoading" class="panel">
      <p>Loading submission…</p>
    </div>

    <div v-else-if="loadError" class="panel">
      <h2 class="card-title">{{ loadError }}</h2>
      <button class="btn btn-outline btn-sm" type="button" @click="load">Try again</button>
    </div>

    <template v-else-if="detail">
      <!-- Mirrors the header the client's Qualtrics form injects: the logo,
           "Submission Portal", and "BIOTech Futures" beneath it. Students
           moving from the old form should recognise where they are. -->
      <div class="page-head portal-banner">
        <div class="portal-brand">
          <!-- No backdrop needed now the banner is tinted rather than solid:
               the mark reads directly against it. -->
          <img class="portal-brand__logo" :src="logo" :alt="BRAND_NAME" />
          <div>
            <h1 class="portal-brand__title">Submission Portal</h1>
            <p class="portal-brand__subtitle">{{ BRAND_NAME }}</p>
          </div>
        </div>

        <!-- Compact by design: a date and a countdown do not need a full-width
             panel, and the space is better spent on the criteria above. -->
        <!-- Stacked rather than run together: label, date and countdown on one
             line made a long string that fought the title for attention. -->
        <div class="submission-due" :title="deadlineDetail">
          <span class="submission-due__label">{{ isOpen ? 'Due' : 'Closed' }}</span>
          <strong class="submission-due__date">{{ deadlineDate }}</strong>
          <span class="submission-due__foot">
            <span
              v-if="timeRemaining"
              class="submission-remaining"
              :class="{ 'is-near': isDeadlineNear }"
            >
              {{ timeRemaining }}
            </span>
            <span v-if="detail.deadline.is_extended" class="status-badge status-info">Extended</span>
          </span>
        </div>
      </div>

      <!-- One line rather than a panel. In progress is the ordinary state and
           does not warrant a bordered box; only a completed submission carries
           information worth pausing on, so only that case is emphasised. -->
      <div class="status-line" :class="{ 'is-submitted': isLocked }">
        <i
          class="status-line__icon"
          :class="isLocked ? 'fas fa-circle-check' : 'far fa-circle'"
          aria-hidden="true"
        ></i>
        <strong class="status-line__state">{{ isLocked ? 'Submitted' : 'In Progress' }}</strong>
        <span v-if="isLocked && submittedLine" class="status-line__detail">{{ submittedLine }}</span>
        <!-- Reassurance during a revision: the entry they already handed in is
             still the one that counts until they finish this one. -->
        <span v-else-if="isRevising" class="status-line__detail">
          Your previous submission still stands until you submit again.
        </span>

        <button
          v-if="isLocked && isOpen"
          class="btn btn-outline btn-sm status-line__action"
          type="button"
          :disabled="isBusy"
          @click="onReopen"
        >
          {{ isReopening ? 'Opening…' : 'Resubmit' }}
        </button>
      </div>

      <p v-if="!isOpen" class="submission-closed">
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

      <!-- Progress strip. Steps stay clickable as well as sequential: moving
           forward suits a first submission, but someone revising one answer
           should not have to walk through the whole form to reach it. -->
      <nav class="submission-steps" aria-label="Submission sections">
        <button
          v-for="(tab, index) in TABS"
          :key="tab.key"
          type="button"
          class="submission-step"
          :class="{ 'is-active': activeTab === tab.key }"
          :aria-current="activeTab === tab.key ? 'step' : undefined"
          @click="goToStep(index)"
        >
          <span class="submission-step__index">{{ index + 1 }}</span>
          <span class="submission-step__label">{{ tab.label }}</span>
          <!-- States a fact rather than judging completion: text in every box
               does not mean the answers are finished, so calling a section
               "Done" would tell a student something we cannot know. -->
          <span class="submission-step__state">{{ stepSummary(tab.key) }}</span>
        </button>
      </nav>

      <!-- 1. Short-answer questions. Defined in the database, so this list is
           whatever the server sent rather than anything hardcoded here. -->
      <section v-show="activeTab === 'questions'" class="panel">
        <!-- Section header in the shape the client's Qualtrics form uses: a
             title with one supporting line beneath. Both come from the
             database, so admins can reword either. -->
        <header v-if="sectionHeading || sectionBody" class="section-head">
          <h2 v-if="sectionHeading" class="section-head__title">{{ sectionHeading }}</h2>
          <p v-if="sectionBody" class="section-head__sub">{{ sectionBody }}</p>
        </header>

        <p v-if="!questions.length" class="submission-muted">
          No questions have been set up yet.
        </p>

        <div v-for="question in questions" :key="question.key" class="submission-field">
          <label class="submission-label" :for="question.key">
            {{ question.prompt }}
            <span v-if="question.is_required" class="submission-required" title="Required" aria-label="required">*</span>
          </label>
          <p v-if="question.help_text" class="submission-muted">{{ question.help_text }}</p>
          <!-- No maxlength attribute: a word limit cannot be enforced by
               truncating keystrokes, so the count warns and the server
               refuses an over-long answer at save time. -->
          <textarea
            :id="question.key"
            v-model="answers[question.key]"
            class="form-control submission-textarea"
            rows="5"
            :disabled="!isEditable"
          ></textarea>
          <p
            v-if="question.max_words"
            class="submission-count"
            :class="{ 'is-over-limit': wordCount(question.key) > question.max_words }"
          >
            {{ wordCount(question.key) }} / {{ question.max_words }} words
          </p>
        </div>
      </section>

      <!-- 2. Poster, with the preview kept open — this tab exists mainly to
           give the document room to be read. -->
      <section v-show="activeTab === 'poster'" class="panel">
        <header v-if="sectionHeading || sectionBody" class="section-head">
          <h2 v-if="sectionHeading" class="section-head__title">{{ sectionHeading }}</h2>
          <p v-if="sectionBody" class="section-head__sub">{{ sectionBody }}</p>
        </header>

        <div class="submission-slot submission-slot--plain">
          <!-- No heading here: this step holds a single item and the section
               header above already names it. The Additional materials step
               keeps headings because it holds two. -->
          <div class="submission-slot__info">
            <p class="submission-muted">PDF only · up to {{ maxSizeLabel('poster') }}</p>

            <p v-if="storedFile('poster')" class="submission-file">
              <a :href="downloadUrl('poster')" target="_blank" rel="noopener noreferrer">
                {{ storedFile('poster')?.name }}
              </a>
              <span class="submission-muted"> ({{ formatSize(storedFile('poster')?.size) }})</span>
            </p>
            <p v-else class="submission-muted">Nothing attached yet.</p>
          </div>

          <div v-if="isEditable" class="submission-slot__actions">
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
        <section class="panel">
          <header v-if="sectionHeading || sectionBody" class="section-head">
          <h2 v-if="sectionHeading" class="section-head__title">{{ sectionHeading }}</h2>
          <p v-if="sectionBody" class="section-head__sub">{{ sectionBody }}</p>
        </header>

          <div class="submission-slot submission-slot--plain">
            <div class="submission-slot__info">
              <h2 class="panel__heading">Scientific report</h2>
              <p class="submission-muted">PDF only · up to {{ maxSizeLabel('report') }}</p>

              <p v-if="storedFile('report')" class="submission-file">
                <a :href="downloadUrl('report')" target="_blank" rel="noopener noreferrer">
                  {{ storedFile('report')?.name }}
                </a>
                <span class="submission-muted"> ({{ formatSize(storedFile('report')?.size) }})</span>
              </p>
              <p v-else class="submission-muted">Nothing attached yet.</p>
            </div>

            <div v-if="isEditable" class="submission-slot__actions">
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

        <section class="panel">
          <div class="submission-slot submission-slot--plain">
            <div class="submission-slot__info">
              <h2 class="panel__heading">Prototype</h2>
              <p class="submission-muted">
                Any file type · up to {{ maxSizeLabel('prototype') }}
              </p>

              <p v-if="storedFile('prototype')" class="submission-file">
                <a :href="downloadUrl('prototype')" target="_blank" rel="noopener noreferrer">
                  {{ storedFile('prototype')?.name }}
                </a>
                <span class="submission-muted"> ({{ formatSize(storedFile('prototype')?.size) }})</span>
              </p>
              <p v-else class="submission-muted">Nothing attached yet.</p>
            </div>

            <div v-if="isEditable" class="submission-slot__actions">
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
            <label class="field-label" for="prototype-url">Prototype link</label>
            <input
              id="prototype-url"
              v-model="prototypeUrl"
              class="form-control"
              type="url"
              placeholder="https://…"
              :disabled="!isEditable"
            />
          </div>
        </section>
      </div>

      <!-- Available from every tab: the server validates the whole entry, so
           there is no reason to force a student through the steps in order. -->
      <div class="submission-actions">
        <!-- An exit rather than a starting point, so it sits after the form
             instead of above the title. -->
        <RouterLink
          :to="{ name: 'group-detail', params: { id: groupId } }"
          class="submission-back"
        >
          <span aria-hidden="true">&larr;</span>
          <span>Back to group</span>
        </RouterLink>

        <!-- Auto-save is invisible by design, so it needs to say so somewhere;
             without this the student cannot tell whether their work is safe. -->
        <span
          v-if="isEditable"
          class="submission-savestate"
          :class="{ 'is-error': saveState === 'error' }"
        >
          {{ saveStateLabel }}
        </span>
        <!-- No Save draft button: auto-save runs two seconds after typing stops
             and again on every step change, and the status line above reports
             it. A button that duplicates something already happening only adds
             a control to the row. -->

        <!-- Step backwards. Hidden on the first step rather than disabled, so
             the row does not carry a permanently dead control. -->
        <button
          v-if="!isFirstStep"
          class="btn btn-outline"
          type="button"
          :disabled="isBusy"
          @click="goToStep(stepIndex - 1)"
        >
          Back
        </button>

        <!-- Next carries the flow forward; on the last step it becomes Submit,
             which is where a wizard is expected to end. -->
        <button
          v-if="!isLastStep"
          class="btn btn-primary"
          type="button"
          :disabled="isBusy"
          @click="goToStep(stepIndex + 1)"
        >
          Next: {{ TABS[stepIndex + 1].label }}
        </button>
        <button
          v-else-if="isEditable"
          class="btn btn-primary"
          type="button"
          :disabled="isBusy"
          @click="onSubmit"
        >
          <!-- "Submit" only for a team's first submission; anything after that
               is a fresh attempt replacing the one already on record. -->
          {{ isSubmitting ? 'Submitting…' : isRevising ? 'New Attempt' : 'Submit' }}
        </button>
      </div>
    </template>
  </div>
</template>

<script setup lang="ts">
import { computed, onBeforeUnmount, onMounted, reactive, ref, watch } from 'vue'
import { RouterLink, useRoute } from 'vue-router'
import logo from '@/assets/btf-logo.png'
import { BRAND_NAME } from '@/constants/brand'
import { apiErrorFromUnknown } from '@/utils/apiError'
import {
  countWords,
  describeQuestionStep,
  describeTimeRemaining,
  formatFileSize,
  isDeadlineNear as deadlineIsNear
} from '@/utils/submissionFormat'
import {
  fetchPreviewObjectUrl,
  fetchSubmission,
  releasePreview,
  removeSubmissionFile,
  reopenEntry,
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
const isReopening = ref(false)
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
const isLocked = computed(() => Boolean(detail.value?.submission?.is_locked))
/** Editing needs both an open deadline and an entry that is not locked. */
const isEditable = computed(() => isOpen.value && !isLocked.value)
const isBusy = computed(
  () => isSaving.value || isSubmitting.value || isReopening.value || Boolean(busySlot.value)
)

/**
 * A locked entry shows what was submitted, not the working draft.
 *
 * They differ while a revision is under way — that separation is what lets an
 * abandoned revision leave the submitted entry alone — so the page has to be
 * explicit about which one it is displaying.
 */
function shownFile(slot: SubmissionSlot): StoredFile | null {
  const submission = detail.value?.submission
  if (!submission) return null
  return isLocked.value ? submission[`submitted_${slot}` as const] : submission[slot]
}
const activeTabConfig = computed(() => TABS.find((tab) => tab.key === activeTab.value) ?? TABS[0])
const stepIndex = computed(() => TABS.findIndex((tab) => tab.key === activeTab.value))
const isFirstStep = computed(() => stepIndex.value <= 0)
const isLastStep = computed(() => stepIndex.value >= TABS.length - 1)

/** Move to a step, scrolling back to the top so the new section starts in view. */
function goToStep(index: number) {
  const target = TABS[Math.min(Math.max(index, 0), TABS.length - 1)]
  if (!target || target.key === activeTab.value) return
  activeTab.value = target.key
  window.scrollTo({ top: 0, behavior: 'smooth' })
}
const activeInstructions = computed(() => detail.value?.instructions?.[activeTab.value])
const sectionHeading = computed(() => activeInstructions.value?.heading ?? '')
const sectionBody = computed(() => activeInstructions.value?.body ?? '')
const isReportPreviewOpen = computed(() => previewSlot.value === 'report')
const isPosterPreviewOpen = computed(() => previewSlot.value === 'poster')

const saveStateLabel = computed(() => {
  if (isSaving.value) return 'Saving…'
  if (saveState.value === 'error') return 'Could not save'
  if (saveState.value === 'unsaved') return 'Unsaved changes'
  if (lastSavedAt.value) return `Saved ${formatTime(lastSavedAt.value)}`
  return ''
})

/** Submitted, but reopened for revision. */
const isRevising = computed(
  () => Boolean(detail.value?.submission?.is_submitted) && !isLocked.value
)

const submittedLine = computed(() => {
  const submission = detail.value?.submission
  if (!submission?.submitted_at) return ''
  const when = formatDate(submission.submitted_at)
  return submission.submitted_by_name
    ? `by ${submission.submitted_by_name} on ${when}`
    : `on ${when}`
})

const deadlineDate = computed(() => {
  const closesAt = detail.value?.deadline.closes_at
  return closesAt ? formatDate(closesAt) : 'No deadline set'
})

/** "3 days left" — urgency a fixed date does not convey on its own. */
const timeRemaining = computed(() =>
  isOpen.value ? describeTimeRemaining(detail.value?.deadline.closes_at, now.value) : ''
)

// Under a day to go is when the wording should start to feel different.
const isDeadlineNear = computed(
  () => isOpen.value && deadlineIsNear(detail.value?.deadline.closes_at, now.value)
)

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
 * Whether a step is required, and what it currently holds.
 *
 * Carries the requirement here rather than in a separate line above the page:
 * "is this optional?" is a question about a particular section, so the answer
 * belongs beside it.
 *
 * The state half deliberately counts rather than judging. An earlier version
 * marked a section "Done" once every box held any text at all, which claimed
 * far more than it could know — a single letter is not a finished answer.
 */
function stepSummary(key: TabKey): string {
  if (key === 'questions') {
    return describeQuestionStep(answers, questions.value.map((q) => q.key))
  }
  // Attachment state is left out here: whether a file is present is obvious
  // the moment you open the step, so repeating it in the strip was noise.
  // The question count stays because progress through six answers is not.
  if (key === 'poster') return 'Required'
  return 'Optional'
}

function formatDate(value: string) {
  return new Date(value).toLocaleString(undefined, {
    dateStyle: 'medium',
    timeStyle: 'short'
  })
}

const formatSize = formatFileSize

function storedFile(slot: SubmissionSlot): StoredFile | null {
  return shownFile(slot)
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

function wordCount(key: string) {
  return countWords(answers[key])
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

/** Copy server state into the fields, showing whichever copy applies. */
function syncFromDetail() {
  const submission = detail.value?.submission
  const source = isLocked.value ? submission?.submitted_answers : submission?.answers
  questions.value.forEach((question) => {
    answers[question.key] = source?.[question.key] ?? ''
  })
  prototypeUrl.value =
    (isLocked.value ? submission?.submitted_prototype_url : submission?.prototype_url) ?? ''
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

async function onReopen() {
  isReopening.value = true
  setMessage('')
  try {
    applyResult(await reopenEntry(groupId.value))
    // The draft may differ from what was submitted, so reload the fields
    // rather than leaving the submitted copy on screen as if it were editable.
    syncFromDetail()
    await syncPreviewForTab()
    setMessage('Reopened for editing. Submit again to replace your submission.')
  } catch (error) {
    setMessage(apiErrorFromUnknown(error).message, true)
  } finally {
    isReopening.value = false
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
    syncFromDetail()
    setMessage('Submitted. Choose Resubmit if you need to change anything before the deadline.')
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
    // No confirmation message: whether a file is attached is plainly visible
    // in the slot itself, so announcing it was only noise. Failures still
    // surface, since those are not self-evident.
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
/* One spacing scale for the page. The gaps between blocks were previously set
   case by case, which is most of what made the layout feel unsettled. */
.content-area {
  --gap-sm: 0.5rem;
  --gap-md: 0.85rem;
  --gap-lg: 1.5rem;
  --gap-xl: 2.25rem;
  --gap-2xl: 3rem;

  /* Local tokens. Every colour on this page routes through one of these so
     the dark theme is a matter of redefining them rather than hunting down
     hardcoded hexes — which is exactly the bug this replaces. */
  --panel-bg: var(--white, #ffffff);
  --panel-border: var(--border-light, #e0e0e0);
  --field-bg: var(--white, #ffffff);
  --field-border: #d7dbd9;
  --field-disabled-bg: #f4f5f5;
  --muted: var(--text-muted, #6c757d);
  --body-text: var(--charcoal, #174243);
  --accent: var(--dark-green, #017151);
  --accent-soft: rgba(1, 114, 81, 0.12);
  --error: #c0392b;
  --error-bg: #fdecea;
  --ok-bg: #f2f9f5;
  --ok-border: #bfe3cf;
  --notice-bg: #f4f6f5;
  --banner-bg: #e9f3ee;
  --banner-border: #cfe4d9;

  /* Type scale. Applied across the whole page rather than only the questions,
     which is what made everything else read as thin by comparison. Four sizes
     and three weights — enough to establish rank, few enough to stay coherent. */
  --text-heading: 1.15rem;
  --text-body: 1rem;
  --text-meta: 0.875rem;
  --text-micro: 0.78rem;

  /* Set here rather than globally: main.css uses Arial platform-wide, and
     changing that affects every other team's pages. A system stack renders
     noticeably sharper than Arial on Windows at no loading cost. */
  font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto,
    'Helvetica Neue', Arial, sans-serif;
  color: var(--body-text);
}

/* Dark theme. The platform opts in with <html data-theme="dark">, so the
   overrides hang off that rather than prefers-color-scheme. */
:root[data-theme='dark'] .content-area {
  --field-bg: #101817;
  --field-border: #33403c;
  --field-disabled-bg: #131b19;
  --accent-soft: rgba(1, 114, 81, 0.28);
  --error: #f87171;
  --error-bg: rgba(248, 113, 113, 0.12);
  --ok-bg: rgba(1, 114, 81, 0.14);
  --ok-border: rgba(1, 114, 81, 0.45);
  --notice-bg: rgba(255, 255, 255, 0.04);
  --banner-bg: rgba(1, 114, 81, 0.16);
  --banner-border: rgba(1, 114, 81, 0.35);
}

/* Matches the Events page header treatment: title, muted subtitle, and the
   content starting immediately underneath. */
.page-head {
  display: flex;
  justify-content: space-between;
  align-items: center;
  gap: 1rem;
  flex-wrap: wrap;
  margin-bottom: var(--gap-lg);
}

/* Brand banner, echoing the Qualtrics form's header strip — but tinted rather
   than solid: the platform already has a full-width green bar directly above,
   and two saturated greens stacked read as heavy. */
.portal-banner {
  background: var(--banner-bg);
  border: 1px solid var(--banner-border);
  padding: var(--gap-lg) var(--gap-xl);
  border-radius: 12px;
}


.page-head h1 {
  margin: 0;
  font-size: clamp(1.5rem, 2.2vw, 2rem);
}

.portal-brand {
  display: flex;
  align-items: center;
  gap: 0.85rem;
}

/* Matches the banner proportions of the Qualtrics form, whose theme sets the
   logo at 58px. The title previously sat at the same weight as section
   headings, so the page had no clear top level. */
.portal-brand__logo {
  height: 62px;
  width: auto;
  display: block;
  flex-shrink: 0;
}

.portal-brand__title {
  margin: 0;
  color: var(--body-text);
  font-size: clamp(1.9rem, 3vw, 2.6rem);
  font-weight: 800;
  line-height: 1.05;
  letter-spacing: -0.02em;
}

/* Matches the Qualtrics banner, whose .headerSubtitle is 16px italic serif
   ("Lyon, Georgia, serif"). Lyon is a licensed University of Sydney face and
   is not ours to ship, so their own Georgia fallback leads instead. */
.portal-brand__subtitle {
  margin: 0.35rem 0 0;
  color: var(--accent);
  font-family: Georgia, 'Times New Roman', serif;
  font-size: 1.05rem;
  font-style: italic;
  font-weight: 400;
  letter-spacing: 0;
}

.submission-due {
  display: flex;
  flex-direction: column;
  align-items: flex-end;
  gap: 0.1rem;
  font-size: var(--text-meta);
  text-align: right;
}

.submission-due__date {
  font-size: var(--text-body);
  line-height: 1.3;
  white-space: nowrap;
}

.submission-due__foot {
  display: flex;
  align-items: center;
  gap: 0.4rem;
}

.submission-due__label {
  color: var(--muted);
  text-transform: uppercase;
  font-weight: 700;
  font-size: var(--text-micro);
  letter-spacing: 0.04em;
}

.submission-back {
  color: var(--accent);
  text-decoration: none;
  font-size: 0.9rem;
  margin-right: auto;
}

.status-line {
  display: flex;
  align-items: center;
  gap: 0.5rem;
  flex-wrap: wrap;
  margin-bottom: var(--gap-lg);
  /* Matches the step buttons' left padding so this icon sits on the same
     vertical line as the numbered step markers below it. */
  padding-left: 0.9rem;
  font-size: var(--text-meta);
  color: var(--muted);
}

.status-line__icon {
  /* Same box as .submission-step__index, so the two centre on each other
     rather than merely starting at the same edge. */
  width: 24px;
  text-align: center;
  font-size: 1rem;
  color: var(--muted);
}

.status-line__state {
  font-weight: 700;
  color: var(--body-text);
}

.status-line__detail::before {
  content: '· ';
}

.status-line__action {
  margin-left: auto;
}

/* Only a completed submission gets the accent — it is the state a student
   actually wants confirmed at a glance. */
.status-line.is-submitted .status-line__icon,
.status-line.is-submitted .status-line__state {
  color: var(--accent);
}

.submission-remaining {
  color: var(--muted);
  font-size: var(--text-meta);
  margin-left: 0.35rem;
}

.submission-remaining.is-near {
  color: var(--error);
  font-weight: 600;
}

.submission-closed {
  padding: 0.75rem 1rem;
  margin-bottom: var(--gap-lg);
  border-radius: 8px;
  border-left: 4px solid var(--accent);
  background: var(--notice-bg);
  font-size: var(--text-meta);
  font-weight: 600;
}

.submission-message {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 0.75rem;
  padding: 0.65rem 0.95rem;
  margin-bottom: var(--gap-lg);
  border-radius: 8px;
  font-size: var(--text-meta);
  font-weight: 600;
  border-left: 4px solid var(--accent);
  background: #f2f8f5;
  font-size: 0.9rem;
}

.submission-message--error {
  border-left-color: var(--error);
  background: var(--error-bg);
  color: var(--error);
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
  font-size: var(--text-micro);
  font-weight: 600;
  color: var(--body-text);
  margin: 0.3rem 0 0;
  font-variant-numeric: tabular-nums;
}

.submission-count.is-over-limit {
  color: var(--error);
  font-weight: 600;
}

/* Step strip */
/* Tabs on a shared rule, rather than three separate boxes: an underline marks
   the active one, which is quieter than a bordered card each and makes the
   strip read as navigation instead of content. */
.submission-steps {
  display: flex;
  gap: var(--gap-sm);
  margin-bottom: var(--gap-lg);
  flex-wrap: wrap;
  border-bottom: 1px solid var(--panel-border);
}

.submission-step {
  flex: 1 1 180px;
  display: flex;
  align-items: center;
  gap: 0.6rem;
  padding: 0.7rem 0.9rem;
  border: 0;
  border-bottom: 3px solid transparent;
  background: none;
  cursor: pointer;
  text-align: left;
  font: inherit;
  color: var(--body-text);
  margin-bottom: -1px;
}

.submission-step:hover {
  color: var(--accent);
}

.submission-step.is-active {
  color: var(--accent);
  border-bottom-color: var(--accent);
}

.submission-step__index {
  display: inline-flex;
  align-items: center;
  justify-content: center;
  width: 24px;
  height: 24px;
  border-radius: 50%;
  background: var(--accent-soft);
  font-size: 0.8rem;
  font-weight: 700;
  flex-shrink: 0;
}

/* Only the step you are on is highlighted. Marking the ones behind it as well
   meant the highlighting changed depending on which direction you arrived
   from — going back un-filled steps you had already visited. */
.submission-step.is-active .submission-step__index {
  background: var(--accent);
  color: #fff;
}

.submission-step__label {
  font-weight: 700;
  font-size: var(--text-body);
  flex: 1;
}

.submission-step__state {
  font-size: var(--text-micro);
  color: var(--muted);
  white-space: nowrap;
}


/* One container rule for the whole page. Previously some blocks were `.card`,
   some carried a green left border and some neither, so nothing read as more
   important than anything else. */
.panel {
  background: var(--panel-bg);
  border: 1px solid var(--panel-border);
  border-radius: 12px;
  /* Generous inside padding does more for a long form than any amount of
     styling: it is what stops six stacked answers reading as a wall. */
  padding: var(--gap-xl);
  margin-bottom: var(--gap-lg);
}

/* Section header, in the shape the Qualtrics form uses: a substantial title
   with one supporting line under it. This is the page's second-level voice —
   clearly below the portal title, clearly above a question label. */
.section-head {
  margin: 0 0 var(--gap-xl);
  padding-bottom: var(--gap-md);
  border-bottom: 1px solid var(--panel-border);
}

.section-head__title {
  margin: 0;
  font-size: clamp(1.35rem, 1.9vw, 1.65rem);
  font-weight: 800;
  line-height: 1.2;
  letter-spacing: -0.01em;
}

.section-head__sub {
  margin: 0.35rem 0 0;
  color: var(--muted);
  font-size: var(--text-body);
  font-weight: 500;
  line-height: 1.55;
  max-width: 75ch;
}

.panel__heading {
  margin: 0 0 0.3rem;
  font-size: var(--text-heading);
  font-weight: 700;
  line-height: 1.3;
}

/* Each question is its own block of thought; the space between them is what
   separates six answers into six tasks rather than one long page. */
.submission-field + .submission-field {
  margin-top: var(--gap-2xl);
}

.submission-label {
  display: block;
  font-weight: 700;
  font-size: var(--text-heading);
  line-height: 1.35;
  margin-bottom: 0.55rem;
}

/* A field inside a section, not a section of its own. Question labels use
   .submission-label at heading size; reusing that here made the prototype link
   shout louder than the Prototype heading above it. */
.field-label {
  display: block;
  font-weight: 600;
  font-size: var(--text-meta);
  color: var(--body-text);
  margin-bottom: 0.4rem;
}

.submission-muted {
  color: var(--muted);
  font-size: var(--text-meta);
  line-height: 1.5;
  margin: 0.2rem 0;
}

/* Both the textareas and the platform's own .form-control inputs: without the
   background and colour set explicitly they stay white in the dark theme,
   which is the one combination that is genuinely unreadable. */
.submission-textarea,
.content-area .form-control {
  width: 100%;
  padding: 0.7rem 0.85rem;
  background: var(--field-bg);
  color: var(--body-text);
  border: 1px solid var(--field-border);
  border-radius: 8px;
  font: inherit;
  line-height: 1.55;
  transition: border-color 0.15s ease, box-shadow 0.15s ease;
}

.submission-textarea {
  resize: vertical;
}

.content-area .form-control::placeholder,
.submission-textarea::placeholder {
  color: var(--muted);
}

/* A visible focus state matters on a form this long — without it there is no
   indication of which of six boxes has the cursor. */
.submission-textarea:focus,
.form-control:focus {
  outline: none;
  border-color: var(--accent);
  box-shadow: 0 0 0 3px var(--accent-soft);
}

.submission-textarea:disabled {
  background: var(--field-disabled-bg);
  color: var(--body-text);
}


/* A quiet marker rather than a badge — it appears beside most labels, so
   anything louder reads as an error state on a form that is merely blank. */
.submission-required {
  color: var(--error);
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
  border-bottom: 1px solid var(--panel-border);
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
  margin: 0.35rem 0 0;
  font-size: var(--text-body);
  font-weight: 600;
}

/* Mirrors the resource library's preview panel so a file looks the same
   wherever it is viewed. The panel carries the border and clips the frame,
   which is why the frame itself has none. */
.preview-panel {
  background: var(--panel-bg);
  border-radius: 8px;
  box-shadow: 0 2px 4px var(--shadow, rgba(0, 0, 0, 0.08));
  min-height: 560px;
  overflow: hidden;
  margin-top: 1rem;
}

.preview-header {
  align-items: center;
  border-bottom: 1px solid var(--panel-border);
  display: flex;
  justify-content: space-between;
  padding: 1rem 1.25rem;
}

.preview-header h2 {
  font-size: var(--text-heading);
  font-weight: 700;
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
  color: var(--muted);
  display: flex;
  flex-direction: column;
  gap: 0.85rem;
  min-height: 480px;
  justify-content: center;
  padding: 2rem;
  text-align: center;
}

.preview-empty i {
  color: var(--accent);
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
  font-size: var(--text-meta);
  color: var(--muted);
}

.submission-savestate.is-error {
  color: var(--error);
  font-weight: 600;
}
</style>
