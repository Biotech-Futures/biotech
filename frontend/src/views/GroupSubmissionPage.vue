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
      <!-- Mirrors the header the client's Qualtrics form injects, so students
           moving from the old form recognise where they are. -->
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

      <!-- One line rather than a panel: in progress is the ordinary state, and
           only a completed submission carries information worth pausing on. -->
      <div class="status-line" :class="`is-${state.tone}`">
        <span class="status-line__icon" aria-hidden="true">
          <i :class="`fas ${state.icon}`"></i>
        </span>
        <strong class="status-line__state">{{ state.headline }}</strong>
        <span v-if="state.detail" class="status-line__detail">{{ state.detail }}</span>

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

      <!-- Steps stay clickable as well as sequential: someone revising one
           answer should not have to walk the whole form to reach it. -->
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
          <!-- States a fact rather than judging completion: text in every box does
               not mean the answers are finished. -->
          <span class="submission-step__state">{{ stepSummary(tab.key) }}</span>
        </button>
      </nav>

      <!-- 1. Short-answer questions. Defined in the database, so this list is
           whatever the server sent rather than anything hardcoded here. -->
      <section v-show="activeTab === 'questions'" class="panel">
        <!-- Title with one supporting line, the shape the client's form uses.
             Both come from the database, so admins can reword either. -->
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
          <!-- No maxlength: a word limit cannot be enforced by truncating
               keystrokes, so the count warns and the server refuses at save. -->
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
          <!-- No heading: this step holds one item and the section header names it.
               Additional materials keeps headings because it holds two. -->
          <div class="submission-slot__info">
            <p class="submission-muted">PDF only · up to {{ maxSizeLabel('poster') }}</p>

            <p v-if="storedFile('poster')" class="submission-file">
              <a :href="downloadUrl('poster')" target="_blank" rel="noopener noreferrer">
                {{ storedFile('poster')?.name }}
              </a>
              <span class="submission-muted"> ({{ formatSize(storedFile('poster')?.size) }})</span>
            </p>
            <p v-else class="submission-muted">Nothing attached yet.</p>

            <!-- Advice, not an error: anything the poster genuinely may not do was
                 refused at upload, so everything here is a "worth checking". -->
            <div v-if="posterWarnings.length" class="poster-notice">
              <p class="poster-notice__head">Worth checking before you submit</p>
              <!-- Deliberately general: these read text, so a team code inside an image
                   looks missing to us. The findings are still recorded for reviewers. -->
              <p class="poster-notice__body">
                Please re-check your poster against the submission requirements
                — the team code, school logo, title, team members, and
                supervisor contact details — before you submit.
              </p>
              <p class="poster-notice__foot">
                You can submit without changing anything — this is a reminder,
                not a problem with your file.
              </p>
            </div>
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

        <!-- Guarded on the slot as well as the source: hidden tabs stay in the
             DOM, so this frame would otherwise load the report's preview too. -->
        <article class="preview-panel">
          <div class="preview-header">
            <h2>Preview</h2>
            <!-- Always offered: some browsers refuse to embed a PDF at all, and a
                 student must never be left unable to check their own file. -->
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

      <!-- 3. Optional extras. The report is previewed like the poster; the
           prototype is a plain upload because it can be any file type. -->
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
              <!-- The programme's wording, shown before the upload button so an
                   oversized file finds the way through before waiting on a failure. -->
              <p class="submission-muted">
                If your submission is greater than {{ maxSizeLabel('prototype') }},
                please upload to a cloud storage and submit a public link for us
                to access your submission.
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
        <!-- No Save draft button: auto-save runs on a pause and on every step
             change, and the status line above reports it. -->

        <!-- Arrows rather than labelled buttons, so Submit fits on every step.
             Each keeps its destination as its accessible name and tooltip. -->
        <div class="submission-steps-nav">
          <button
            class="btn btn-outline btn-icon"
            type="button"
            :disabled="isBusy || isFirstStep"
            :aria-label="isFirstStep ? 'Previous step' : `Back: ${TABS[stepIndex - 1].label}`"
            :title="isFirstStep ? undefined : `Back: ${TABS[stepIndex - 1].label}`"
            @click="goToStep(stepIndex - 1)"
          >
            <i class="fas fa-arrow-left" aria-hidden="true"></i>
          </button>
          <button
            class="btn btn-outline btn-icon"
            type="button"
            :disabled="isBusy || isLastStep"
            :aria-label="isLastStep ? 'Next step' : `Next: ${TABS[stepIndex + 1].label}`"
            :title="isLastStep ? undefined : `Next: ${TABS[stepIndex + 1].label}`"
            @click="goToStep(stepIndex + 1)"
          >
            <i class="fas fa-arrow-right" aria-hidden="true"></i>
          </button>
        </div>

        <!-- Reachable from any step. Pressing it early is a shortcut, not a dead
             end: the page says what is missing and moves to it. -->
        <button
          v-if="isEditable"
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
import { computed, nextTick, onBeforeUnmount, onMounted, reactive, ref, watch } from 'vue'
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
  type SubmissionStage,
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

// Fallback only for the moment between the page mounting and the first
// response arriving; the server's values replace these as soon as it loads.
const FALLBACK_MAX_FILE_SIZES: Record<SubmissionSlot, number> = {
  poster: 20 * 1024 * 1024,
  report: 20 * 1024 * 1024,
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

/**
 * The answers the server is known to hold, used to send only what changed.
 *
 * A save carrying all six asserted all six, so a teammate saving at the same
 * moment lost their work. Not reactive: it only exists to be diffed against.
 */
let savedAnswers: Record<string, string> = {}

/**
 * Changed answers that are short enough to save.
 *
 * An over-limit answer is left out rather than sent and refused: the counter
 * beside the box already turns red, so a server error would be redundant.
 */
function changedAnswers(): Record<string, string> {
  const overLimit = new Set(overLimitQuestions().map((q) => q.key))
  const changed: Record<string, string> = {}
  Object.keys(answers).forEach((key) => {
    if (overLimit.has(key)) return
    // Compared against '' rather than undefined so clearing an answer counts
    // as a change: the backend merges, so an omitted key means "leave alone"
    // and a cleared box has to be sent as an explicit empty string.
    if (answers[key] !== (savedAnswers[key] ?? '')) changed[key] = answers[key]
  })
  return changed
}

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
 * Whether the page displays the frozen copy rather than the working draft.
 *
 * Not simply "is it locked": once the deadline shuts, an unfinished revision
 * stops mattering and what was submitted is what gets marked, so that is what
 * the team must be shown. Reading `is_locked` alone showed them a draft nobody
 * would ever grade.
 */
const showsSubmittedCopy = computed(() => {
  const submission = detail.value?.submission
  if (!submission?.is_submitted) return false
  return submission.is_locked || !isOpen.value
})

/** What the format checks found about whichever poster is on show. */
const posterWarnings = computed(() => {
  const submission = detail.value?.submission
  if (!submission) return []
  const checks = showsSubmittedCopy.value
    ? submission.submitted_poster_checks
    : submission.poster_checks
  return checks?.warnings ?? []
})

function shownFile(slot: SubmissionSlot): StoredFile | null {
  const submission = detail.value?.submission
  if (!submission) return null
  return showsSubmittedCopy.value
    ? submission[`submitted_${slot}` as const]
    : submission[slot]
}
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

/**
 * Where the entry stands. A team with no entry at all has not started one.
 */
const stage = computed<SubmissionStage>(
  () => detail.value?.submission?.stage ?? 'not_started'
)

/**
 * How the entry is described, from its stage paired with the open window.
 *
 * A table rather than nested conditions because the two facts are independent:
 * every stage can be met with the window open or shut, and the combinations
 * the old conditionals did not cover are exactly where they went wrong — a
 * team who never started was told "In Progress" after the deadline had gone.
 * Listing the cases makes a missing one visible instead of silent.
 */
const state = computed(() => {
  const closed = !isOpen.value
  const by = submittedLine.value
  const on = deadlineDate.value

  switch (stage.value) {
    case 'submitted':
      return { tone: 'submitted', icon: 'fa-check', headline: 'Submitted', detail: by }
    case 'revising':
      return closed
        ? {
            tone: 'submitted',
            icon: 'fa-check',
            headline: 'Submitted',
            // The point they would otherwise have to work out for themselves.
            detail: by
              ? `${by}. Your unfinished revision was not submitted.`
              : 'Your unfinished revision was not submitted.',
          }
        : {
            tone: 'progress',
            icon: 'fa-pen',
            headline: 'In Progress',
            detail: 'Your previous submission still stands until you submit again.',
          }
    case 'in_progress':
      return closed
        ? {
            tone: 'missed',
            icon: 'fa-circle-exclamation',
            headline: 'Not Submitted',
            detail: `The deadline passed on ${on}. Your saved work is below, but it was never submitted.`,
          }
        : { tone: 'progress', icon: 'fa-pen', headline: 'In Progress', detail: '' }
    default:
      return closed
        ? {
            tone: 'missed',
            icon: 'fa-circle-exclamation',
            headline: 'Not Submitted',
            detail: `The deadline passed on ${on}. No entry was received.`,
          }
        : {
            tone: 'progress',
            icon: 'fa-pen',
            headline: 'Not Started',
            detail: `Add your answers and poster before ${on}.`,
          }
  }
})

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
 * The state half counts rather than judging: an earlier version marked a
 * section "Done" once every box held text, which claimed more than it knew.
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

/** Questions currently written past their own word limit, if any. */
function overLimitQuestions() {
  return questions.value.filter((q) => q.max_words && wordCount(q.key) > q.max_words)
}

/**
 * Wording identical to the server's own message, so a student sees the same
 * sentence whichever side catches it — only sooner, and by name not key.
 */
function overLimitMessage(list: ReturnType<typeof overLimitQuestions>): string {
  const parts = list.map(
    (q) => `"${q.prompt}" (${wordCount(q.key)} words, limit ${q.max_words})`
  )
  return `Answer too long for ${parts.join(', ')}.`
}

/** Required questions still blank, in the order they appear on the form. */
function unansweredQuestions() {
  return questions.value.filter((q) => q.is_required && !(answers[q.key] ?? '').trim())
}

/**
 * What is still missing, and where to send the student to fix it.
 *
 * The server refuses either way; this exists so the refusal arrives with
 * somewhere to go. Questions come before the poster, as the form does.
 */
function submissionBlockers(): { message: string; step: TabKey; focusKey?: string } | null {
  const unanswered = unansweredQuestions()
  const posterMissing = !shownFile('poster')

  if (unanswered.length && posterMissing) {
    return {
      message:
        'Some required questions have not been answered, and no poster has been uploaded.',
      step: 'questions',
      focusKey: unanswered[0].key
    }
  }
  if (unanswered.length) {
    return {
      message: 'Some required questions have not been answered.',
      step: 'questions',
      focusKey: unanswered[0].key
    }
  }
  if (posterMissing) {
    return {
      message: 'A poster must be uploaded before the entry can be submitted.',
      step: 'poster'
    }
  }
  return null
}

/**
 * Move to the step holding the first missing item and focus it.
 *
 * Waits a tick: the target is only in the DOM once its step is showing.
 */
async function goToBlocker(blocker: { step: TabKey; focusKey?: string }) {
  goToStep(TABS.findIndex((tab) => tab.key === blocker.step))
  if (!blocker.focusKey) return
  await nextTick()
  const field = document.getElementById(blocker.focusKey)
  if (!(field instanceof HTMLTextAreaElement)) return
  field.focus()
  // Guarded because scrolling is presentation, not behaviour: jsdom has no
  // layout and does not implement this at all, and an unhandled rejection here
  // would be a real failure reported for a cosmetic one. Focus above is what
  // actually matters, and it has already happened.
  if (typeof field.scrollIntoView === 'function') {
    field.scrollIntoView({ behavior: 'smooth', block: 'center' })
  }
}

function applyResult(result: SubmissionWriteResult) {
  if (!detail.value) return
  detail.value = { ...detail.value, deadline: result.deadline, submission: result.submission }
}

/**
 * Turn a failed write into a message, closing the page if that is why.
 *
 * The refusal is authoritative, so `isOpen` is flipped directly: that
 * disables the form and stops auto-save retrying a doomed save forever.
 */
function handleWriteError(error: unknown): string {
  const apiError = apiErrorFromUnknown(error)
  if (apiError.code === 'submissions_closed' && detail.value?.deadline.is_open) {
    detail.value = {
      ...detail.value,
      deadline: { ...detail.value.deadline, is_open: false }
    }
    return 'The submission deadline has passed while you were editing. Your most recently saved answers are shown below.'
  }
  return apiError.message
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
 * A stale panel showing a replaced or deleted file would misrepresent the
 * entry, so anything not currently valid is dropped.
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
  const source = showsSubmittedCopy.value
    ? submission?.submitted_answers
    : submission?.answers
  questions.value.forEach((question) => {
    answers[question.key] = source?.[question.key] ?? ''
  })
  prototypeUrl.value =
    (showsSubmittedCopy.value
      ? submission?.submitted_prototype_url
      : submission?.prototype_url) ?? ''
  // Baseline for change detection: what was just loaded is, by definition,
  // what the server already has.
  savedSnapshot.value = currentSnapshot()
  savedAnswers = { ...answers }
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
 * Persist the draft.
 *
 * Never announces success: it runs constantly and the status line reports
 * the outcome. Failures do surface — losing work is what this prevents.
 */
async function persistDraft() {
  if (isSaving.value) return
  const snapshot = currentSnapshot()

  const sent = changedAnswers()
  const overLimit = overLimitQuestions()

  isSaving.value = true
  try {
    applyResult(
      await saveDraft(groupId.value, {
        answers: sent,
        prototype_url: prototypeUrl.value
      })
    )
    // Only the keys actually accepted move into the baseline. Taking the whole
    // server response instead would pull a teammate's newer answer into this
    // tab's baseline for a question the student may be mid-sentence on.
    Object.assign(savedAnswers, sent)
    savedSnapshot.value = snapshot
    lastSavedAt.value = new Date()
    // changedAnswers() left an over-limit answer out of `sent` above, so this
    // save can succeed while something is still genuinely unsaved. The status
    // line should say so rather than claim everything is safely stored — the
    // red counter beside the box explains why.
    saveState.value = overLimit.length ? 'unsaved' : 'idle'
  } catch (error) {
    saveState.value = 'error'
    setMessage(handleWriteError(error), true)
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
    persistDraft()
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
    setMessage(handleWriteError(error), true)
  } finally {
    isReopening.value = false
  }
}

async function onSubmit() {
  isSubmitting.value = true
  setMessage('')
  try {
    // Checked before saving, not left for the server: changedAnswers() quietly
    // excludes an over-limit answer from every save, so without this check
    // submitting here would silently send the *last saved, still-valid* text
    // instead of what is currently in the box — correct, but exactly the kind
    // of surprise ("I edited this, why did the old version go in?") worth
    // refusing up front instead.
    // Navigation is deliberately not awaited: it only moves the view, and
    // awaiting it would hand control back to the event loop mid-refusal, which
    // is long enough for a pending auto-save to fire on the way out.
    const overLimit = overLimitQuestions()
    if (overLimit.length) {
      setMessage(overLimitMessage(overLimit), true)
      void goToBlocker({ step: 'questions', focusKey: overLimit[0].key })
      return
    }

    // Checked here as well as on the server, for the same reason: so the
    // refusal can point at the thing that needs fixing. The server stays the
    // authority — this only saves a round trip and lands the student on it.
    const blocker = submissionBlockers()
    if (blocker) {
      setMessage(blocker.message, true)
      void goToBlocker(blocker)
      return
    }

    // Save first so submitting never leaves unsaved edits behind. Sends only
    // what changed, for the same reason auto-save does.
    const sent = changedAnswers()
    applyResult(
      await saveDraft(groupId.value, {
        answers: sent,
        prototype_url: prototypeUrl.value
      })
    )
    Object.assign(savedAnswers, sent)
    applyResult(await submitEntry(groupId.value))
    syncFromDetail()
    setMessage('Submitted. Choose Resubmit if you need to change anything before the deadline.')
  } catch (error) {
    // The server's own sentence is used as-is. It already says what is wrong
    // without listing every question, and the pre-check above is what normally
    // catches this — reaching here means the entry changed underneath us, so
    // there is nothing reliable to point at.
    setMessage(handleWriteError(error), true)
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
    // A poster refused on format comes back with the specific reasons. Listing
    // them is the whole point — "not in the required format" alone would leave
    // a student re-exporting at random to find out which way it was wrong.
    const problems = apiErrorFromUnknown(error).body?.problems
    if (Array.isArray(problems) && problems.length) {
      setMessage(problems.join(' '), true)
    } else {
      setMessage(handleWriteError(error), true)
    }
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
    setMessage(handleWriteError(error), true)
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

/**
 * Notice the deadline passing while the page sits open, rather than only
 * finding out from a save that later fails.
 *
 * Re-asks the server rather than assuming closed at `closes_at`: a grace
 * period may still be running, and its length is never sent to the client.
 */
let deadlineRecheckDone = false
watch(now, async () => {
  if (deadlineRecheckDone || !isOpen.value) return
  const closesAt = detail.value?.deadline.closes_at
  if (!closesAt || now.value < new Date(closesAt).getTime()) return

  deadlineRecheckDone = true
  try {
    const latest = await fetchSubmission(groupId.value)
    if (!detail.value) return
    detail.value = { ...detail.value, deadline: latest.deadline }
    if (!latest.deadline.is_open) {
      // Kept short deliberately: the static banner beneath the status line
      // (bound to !isOpen, now true) already explains the consequence — this
      // is only the one-off notice that the moment just happened.
      setMessage('The submission deadline has just passed.', true)
    }
  } catch {
    // Best-effort: a network hiccup here just means the page keeps showing
    // the countdown a little past zero. The next write attempt still catches
    // an authoritative closure through handleWriteError.
    deadlineRecheckDone = false
  }
})

// Any edit to an answer or the prototype link queues a save.
watch([answers, prototypeUrl], scheduleAutosave, { deep: true })

watch(activeTab, () => {
  // Leaving a tab is a natural checkpoint — save now rather than waiting out
  // the timer, in case the student closes the page from the next tab.
  if (autosaveTimer) {
    clearTimeout(autosaveTimer)
    autosaveTimer = null
    persistDraft()
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
  /* Ground the panels sit on. Deliberately only ~10/255 darker than a white
     panel: enough for the shadow below to have something to fall on, faint
     enough that the page never announces itself as a different product from
     the rest of the platform. Tinted towards the brand green rather than a
     neutral grey, for the same reason. */
  --page-bg: #f3f7f4;
  --panel-edge: rgba(6, 40, 30, 0.07);
  --panel-shadow:
    0 1px 2px rgba(6, 40, 30, 0.04),
    0 8px 20px -8px rgba(6, 40, 30, 0.1);
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
  /* Matches --panel-edge in light mode so the banner and the panels below it
     are edged identically, but stays a separate token because the dark theme
     needs a green edge here and a neutral one on the panels. */
  --banner-border: rgba(6, 40, 30, 0.07);

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
  /* Overrides main.css's shared .content-area rule for this page only — the
     scoped attribute wins on specificity, so no other page is affected. */
  background-color: var(--page-bg);
}

/* Dark theme. The platform opts in with <html data-theme="dark">, so the
   overrides hang off that rather than prefers-color-scheme. */
:root[data-theme='dark'] .content-area {
  /* Let the app shell paint the dark ground rather than restating its value
     here, so the page cannot drift out of step if the shell's dark grey
     changes. A drop shadow needs a lighter surface to darken, so on a dark
     ground it does nothing but soften the edge — the border carries the
     separation instead. */
  --page-bg: transparent;
  --panel-edge: var(--panel-border);
  --panel-shadow: none;
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
  /* Same lift as the panels below it: the banner is a surface on the page,
     not a stripe painted onto it, so it should cast the same shadow. */
  box-shadow: var(--panel-shadow);
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
  gap: 0.6rem;
  flex-wrap: wrap;
  /* Matches the step buttons' left padding so the badge sits on the same
     vertical line as the numbered step markers below it. */
  padding: 0 0.9rem;
  margin-bottom: var(--gap-lg);
  font-size: var(--text-meta);
  color: var(--muted);
}

/* Deliberately the same 24px disc as .submission-step__index: the status and
   the steps then read as one column of markers rather than two unrelated
   elements that happen to be stacked. */
.status-line__icon {
  display: inline-flex;
  align-items: center;
  justify-content: center;
  width: 24px;
  height: 24px;
  border-radius: 50%;
  background: var(--accent-soft);
  color: var(--accent);
  font-size: 0.7rem;
  flex-shrink: 0;
}

.status-line__state {
  font-weight: 700;
  font-size: var(--text-body);
  color: var(--body-text);
  letter-spacing: -0.005em;
}

.status-line__detail::before {
  content: '· ';
}

.status-line__action {
  margin-left: auto;
}

/* Submitted is the state worth confirming at a glance, so it fills in — the
   same promotion the active step marker gets. */
.status-line.is-submitted .status-line__icon {
  background: var(--accent);
  color: #fff;
}

.status-line.is-submitted .status-line__state {
  color: var(--accent);
}

/* A deadline gone by with nothing submitted. Stated rather than alarmed:
   there is nothing left to do about it, so red would only be cruel. */
.status-line.is-missed .status-line__icon {
  background: var(--field-disabled-bg);
  color: var(--muted);
}

.status-line.is-missed .status-line__state {
  color: var(--body-text);
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

/* Deliberately quieter than .submission-message--error: nothing here blocks a
   submission, and styling advice like a failure would train students to
   dismiss it. Tokens only — every colour has a dark-mode value already. */
.poster-notice {
  margin-top: 0.75rem;
  padding: 0.65rem 0.85rem;
  border-left: 4px solid var(--accent);
  border-radius: 8px;
  background: var(--notice-bg);
  color: var(--body-text);
  font-size: var(--text-meta);
}

.poster-notice__head {
  font-weight: 700;
  margin: 0 0 0.3rem;
}

.poster-notice__body {
  margin: 0;
}

.poster-notice__foot {
  margin: 0.4rem 0 0;
  color: var(--muted);
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
  /* --ok-bg/--ok-border already carry a dark-mode variant (a translucent
     green wash rather than restating a colour), but sat unused: this banner
     hardcoded a light-only hex instead, and with no colour of its own it fell
     back to --body-text — which flips near-white for dark mode, so white text
     landed on a near-white background and the message read as blank. */
  border-left: 4px solid var(--ok-border);
  background: var(--ok-bg);
  color: var(--accent);
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
  border: 1px solid var(--panel-edge);
  border-radius: 12px;
  /* Lifts the white panel off the tinted ground. The hairline border is kept
     as well as the shadow: shadow alone leaves the top edge soft, and the two
     together are what read as crisp rather than floating. */
  box-shadow: var(--panel-shadow);
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

/* The two arrows read as one control, so they sit tighter to each other than
   to Submit — which is what keeps stepping and submitting from looking like
   three equal choices. */
.submission-steps-nav {
  display: flex;
  gap: 0.35rem;
}

/* Square, and large enough to hit on a phone: an icon-only button loses its
   label as a target as well as as a hint, so the 44px guidance matters more
   here than on a button with text in it. */
.btn-icon {
  min-width: 44px;
  min-height: 44px;
  display: inline-flex;
  align-items: center;
  justify-content: center;
  padding: 0;
}

.btn-icon:disabled {
  opacity: 0.45;
  cursor: default;
}

.submission-savestate.is-error {
  color: var(--error);
  font-weight: 600;
}
</style>
