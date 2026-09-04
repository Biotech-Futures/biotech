<template>
  <!-- Every design token on this section is declared on .content-area; without
       it ~100 declarations point at undefined properties. -->
  <div class="content-area">
    <div v-if="isLoading" class="card">
      <p>Loading submission…</p>
    </div>

    <div v-else-if="loadError" class="card">
      <h2 class="card-title">{{ loadError }}</h2>
      <button class="btn btn-outline btn-sm" type="button" @click="load">Try again</button>
    </div>

    <template v-else-if="detail">
      <!-- One line rather than a panel, with the closing date at the far end: where
           the entry stands and when it is due are one thought. -->
      <div class="status-line" :class="`is-${state.tone}`">
        <span class="status-line__icon" aria-hidden="true">
          <i :class="`fas ${state.icon}`"></i>
        </span>
        <strong class="status-line__state">{{ state.headline
          }}{{ state.detail ? '.' : '' }}</strong>
        <span v-if="state.detail" class="status-line__detail">{{ state.detail }}</span>

        <button
          v-if="isLocked && isOpen"
          ref="reopenTrigger"
          class="btn btn-outline btn-sm status-line__action"
          type="button"
          data-testid="resubmit"
          :disabled="isBusy"
          @click="askToReopen"
        >
          {{ isReopening ? 'Opening…' : 'Resubmit' }}
        </button>

        <!-- Inline rather than stacked: on its own line a label above a date read as
             a heading. -->
        <span class="submission-due" :title="deadlineDetail">
          <span class="submission-due__label">{{ isOpen ? 'Due' : 'Closed' }}</span>
          <strong class="submission-due__date">{{ deadlineDate }}</strong>
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

      <!-- In the page, not window.confirm(): a native dialog stops appearing once a
           browser suppresses dialogs, and Resubmit would then silently do nothing. -->
      <div
        v-if="isConfirmingReopen"
        class="submission-dialog-backdrop"
        role="dialog"
        aria-modal="true"
        aria-labelledby="reopen-dialog-title"
        tabindex="-1"
        data-testid="reopen-dialog"
        @keydown.esc="cancelReopen"
      >
        <section class="submission-dialog">
          <h2 id="reopen-dialog-title" class="submission-dialog__title">Reopen for editing?</h2>
          <p class="submission-dialog__body">
            Your current submission stays in place until you submit again.
          </p>
          <div class="submission-dialog__actions">
            <button
              type="button"
              class="btn btn-outline"
              data-testid="reopen-cancel"
              @click="cancelReopen"
            >
              Cancel
            </button>
            <button
              ref="reopenConfirm"
              type="button"
              class="btn btn-primary"
              data-testid="reopen-confirm"
              @click="confirmReopen"
            >
              Reopen
            </button>
          </div>
        </section>
      </div>

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
      <section v-show="activeTab === 'questions'" class="card">
        <!-- Title with one supporting line, the shape the client's form uses.
             Both come from the database, so admins can reword either. -->
        <header v-if="sectionHeading || sectionBody" class="section-head">
          <h2 v-if="sectionHeading" class="card-title">{{ sectionHeading }}</h2>
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
          <!-- Only once there is something to count: six "0 / 150 words" lines on an
               untouched form read as six things already wrong. -->
          <p
            v-if="question.max_words && wordCount(question.key) > 0"
            class="submission-count"
            :class="{ 'is-over-limit': wordCount(question.key) > question.max_words }"
          >
            {{ wordCount(question.key) }} / {{ question.max_words }} words
          </p>
        </div>
      </section>

      <!-- 2. Poster, with the preview kept open — this tab exists mainly to
           give the document room to be read. -->
      <section v-show="activeTab === 'poster'" class="card">
        <header v-if="sectionHeading || sectionBody" class="section-head">
          <h2 v-if="sectionHeading" class="card-title">{{ sectionHeading }}</h2>
          <p v-if="sectionBody" class="section-head__sub">{{ sectionBody }}</p>
        </header>

        <div class="submission-slot submission-slot--plain">
          <!-- No heading: this step holds one item and the section header names it.
               Additional materials keeps headings because it holds two. -->
          <div class="submission-slot__info">
            <p class="submission-muted">PDF only · up to {{ maxSizeLabel('poster') }}</p>

            <!-- A router link, not the absolute address the client sent: the
                 resource library is this same platform, so this keeps the
                 student in the app and works on any deployment of it. -->
            <p class="submission-template">
              Your poster must use the programme's
              <RouterLink :to="`/resources/${POSTER_TEMPLATE_RESOURCE_ID}`">template</RouterLink>.
            </p>

            <p v-if="storedFile('poster')" class="submission-file">
              <a :href="downloadUrl('poster')" target="_blank" rel="noopener noreferrer">
                {{ storedFile('poster')?.name }}
              </a>
              <span class="submission-muted"> ({{ formatSize(storedFile('poster')?.size) }})</span>
            </p>
            <p v-else class="submission-muted">Nothing attached yet.</p>

            <!-- Advice, not an error: anything the poster genuinely may not do was
                 refused at upload, so everything here is a "worth checking". -->
            <!-- Deliberately general: these checks read text, so a team code inside an
                 image looks missing to us. Full findings are still recorded for reviewers. -->
            <div v-if="posterWarnings.length" class="poster-notice">
              <p class="poster-notice__body">
                Uploaded. Please re-check your poster against the submission
                requirements before you submit.
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
        <article class="preview-panel" :class="{ 'is-collapsed': previewCollapsed.poster }">
          <div class="preview-header">
            <!-- The heading wraps the button: a button may only contain phrasing content,
                 and this keeps the preview in a screen reader's heading list. -->
            <h2 class="preview-title">
              <button
                type="button"
                class="preview-toggle"
                :aria-expanded="!previewCollapsed.poster"
                aria-controls="poster-preview-body"
                data-testid="toggle-poster-preview"
                @click="togglePreview('poster')"
              >
                <i
                  class="fas preview-toggle__chevron"
                  :class="previewCollapsed.poster ? 'fa-chevron-right' : 'fa-chevron-down'"
                  aria-hidden="true"
                ></i>
                Preview
              </button>
            </h2>
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

          <!-- Hidden rather than destroyed: tearing the iframe down would make
               every collapse and re-open refetch the document. -->
          <div v-show="!previewCollapsed.poster" id="poster-preview-body">
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
          </div>
        </article>
      </section>

      <!-- 3. Optional extras. The report is previewed like the poster; the
           prototype is a plain upload because it can be any file type. -->
      <div v-show="activeTab === 'extras'">
        <section class="card">
          <header v-if="sectionHeading || sectionBody" class="section-head">
          <h2 v-if="sectionHeading" class="card-title">{{ sectionHeading }}</h2>
          <p v-if="sectionBody" class="section-head__sub">{{ sectionBody }}</p>
        </header>

          <div class="submission-slot submission-slot--plain">
            <div class="submission-slot__info">
              <h2 class="panel-subheading">Scientific report</h2>
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

          <article class="preview-panel" :class="{ 'is-collapsed': previewCollapsed.report }">
            <div class="preview-header">
              <h2 class="preview-title">
                <button
                  type="button"
                  class="preview-toggle"
                  :aria-expanded="!previewCollapsed.report"
                  aria-controls="report-preview-body"
                  data-testid="toggle-report-preview"
                  @click="togglePreview('report')"
                >
                  <i
                    class="fas preview-toggle__chevron"
                    :class="previewCollapsed.report ? 'fa-chevron-right' : 'fa-chevron-down'"
                    aria-hidden="true"
                  ></i>
                  Preview
                </button>
              </h2>
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

            <div v-show="!previewCollapsed.report" id="report-preview-body">
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
            </div>
          </article>
        </section>

        <section class="card">
          <div class="submission-slot submission-slot--plain">
            <div class="submission-slot__info">
              <h2 class="panel-subheading">Prototype</h2>
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
          <!-- Always "Submit". Renaming it on a revision gave one control two names. -->
          {{ isSubmitting ? 'Submitting…' : 'Submit' }}
        </button>
      </div>
    </template>
  </div>
</template>

<script setup lang="ts">
import { computed, nextTick, onBeforeUnmount, onMounted, reactive, ref, watch } from 'vue'
import { RouterLink, useRoute } from 'vue-router'
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

// Section names only; the guidance text lives in the database.
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

// The resource library entry holding the programme's poster template.
const POSTER_TEMPLATE_RESOURCE_ID = 9

const route = useRoute()
const groupId = computed(() => String(route.params.id ?? ''))

const detail = ref<SubmissionDetail | null>(null)
const isLoading = ref(true)
const loadError = ref('')

const answers = reactive<Record<string, string>>({})
const prototypeUrl = ref('')

/** The answers the server is known to hold, used to send only what changed. */
let savedAnswers: Record<string, string> = {}

/** Changed answers short enough to save; an over-limit one is left out. */
function changedAnswers(): Record<string, string> {
  const overLimit = new Set(overLimitQuestions().map((q) => q.key))
  const changed: Record<string, string> = {}
  Object.keys(answers).forEach((key) => {
    if (overLimit.has(key)) return
    // Compared against '' so clearing an answer counts as a change: the backend
    // merges, so an omitted key means "leave alone".
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

/** Whether the page shows the frozen copy rather than the working draft. */
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

/** Whether the student has folded a preview away. Starts open. */
const previewCollapsed = reactive<Record<'poster' | 'report', boolean>>({
  poster: false,
  report: false,
})

function togglePreview(slot: 'poster' | 'report') {
  previewCollapsed[slot] = !previewCollapsed[slot]
}

const saveStateLabel = computed(() => {
  if (isSaving.value) return 'Saving…'
  if (saveState.value === 'error') return 'Could not save'
  if (saveState.value === 'unsaved') return 'Unsaved changes'
  if (lastSavedAt.value) return `Saved ${formatTime(lastSavedAt.value)}`
  return ''
})

/** Where the entry stands. A team with no entry at all has not started one. */
const stage = computed<SubmissionStage>(
  () => detail.value?.submission?.stage ?? 'not_started'
)

/** How the entry is described: its stage paired with the open window. */
const CLOSED = 'Submissions are closed.'

const state = computed(() => {
  const closed = !isOpen.value
  const by = submittedLine.value

  switch (stage.value) {
    case 'submitted':
      return {
        tone: 'submitted',
        icon: 'fa-check',
        headline: 'Submitted',
        detail: closed ? [by, CLOSED].filter(Boolean).join('. ') : by,
      }
    case 'revising':
      return closed
        ? {
            tone: 'submitted',
            icon: 'fa-check',
            headline: 'Submitted',
            // The point they would otherwise have to work out for themselves.
            detail: [by, CLOSED, 'Your unfinished revision was not submitted.']
              .filter(Boolean)
              .join('. '),
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
            // The saved work is plainly on the page below, so saying so only
            // restated the headline at length.
            detail: CLOSED,
          }
        : { tone: 'progress', icon: 'fa-pen', headline: 'In Progress', detail: '' }
    default:
      return closed
        ? {
            tone: 'missed',
            icon: 'fa-circle-exclamation',
            headline: 'Not Submitted',
            detail: 'Submissions are closed.',
          }
        : { tone: 'progress', icon: 'fa-pen', headline: 'Not Started', detail: '' }
  }
})

const submittedLine = computed(() => {
  const submission = detail.value?.submission
  if (!submission?.submitted_at) return ''
  const when = formatDate(submission.submitted_at)
  return submission.submitted_by_name
    ? `By ${submission.submitted_by_name} on ${when}`
    : `On ${when}`
})

const deadlineDate = computed(() => {
  const closesAt = detail.value?.deadline.closes_at
  return closesAt ? formatDeadline(closesAt) : 'No deadline set'
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

/** Whether a step is required, and what it currently holds. */
function stepSummary(key: TabKey): string {
  if (key === 'questions') {
    return describeQuestionStep(answers, questions.value.map((q) => q.key))
  }
  // Attachment state is left out: it is obvious on opening the step. The
  // question count stays because progress through six answers is not.
  if (key === 'poster') return 'Required'
  return 'Optional'
}

function formatDate(value: string) {
  return new Date(value).toLocaleString(undefined, {
    dateStyle: 'medium',
    timeStyle: 'short'
  })
}

/** Closing time for the status line; the year shows only when it is not this one. */
function formatDeadline(value: string) {
  const date = new Date(value)
  const isThisYear = date.getFullYear() === new Date().getFullYear()
  return date.toLocaleString(undefined, {
    day: 'numeric',
    month: 'short',
    year: isThisYear ? undefined : 'numeric',
    hour: 'numeric',
    minute: '2-digit'
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

/** Wording identical to the server's own message, only sooner and by name. */
/** Names one question, never a list; the count is already live under the box. */
function overLimitMessage(list: ReturnType<typeof overLimitQuestions>): string {
  return `Answer too long for "${list[0].prompt}"`
}

/** Required questions still blank, in the order they appear on the form. */
function unansweredQuestions() {
  return questions.value.filter((q) => q.is_required && !(answers[q.key] ?? '').trim())
}

/** What is still missing, and where to send the student to fix it. */
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

/** Move to the step holding the first missing item and focus it. */
async function goToBlocker(blocker: { step: TabKey; focusKey?: string }) {
  goToStep(TABS.findIndex((tab) => tab.key === blocker.step))
  if (!blocker.focusKey) return
  await nextTick()
  const field = document.getElementById(blocker.focusKey)
  if (!(field instanceof HTMLTextAreaElement)) return
  field.focus()
  // jsdom has no layout, so this rejects there; the focus above is what matters.
  if (typeof field.scrollIntoView === 'function') {
    field.scrollIntoView({ behavior: 'smooth', block: 'center' })
  }
}

function applyResult(result: SubmissionWriteResult) {
  if (!detail.value) return
  detail.value = { ...detail.value, deadline: result.deadline, submission: result.submission }
}

/** Turn a failed write into a message, closing the page if that is why. */
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

/** Keep the preview in step with the tab and with what is attached. */
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

/** Persist the draft. Never announces success; failures do surface. */
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
    // Only accepted keys move into the baseline, so a teammate's newer answer is
    // not pulled into this tab's.
    Object.assign(savedAnswers, sent)
    savedSnapshot.value = snapshot
    lastSavedAt.value = new Date()
    // An over-limit answer was left out of the save, so something can still be
    // genuinely unsaved; the status line should say so.
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

/** Reopening unlocks the draft; the dialog says the submitted entry stands. */
const isConfirmingReopen = ref(false)
const reopenConfirm = ref<HTMLButtonElement | null>(null)
const reopenTrigger = ref<HTMLElement | null>(null)

async function askToReopen() {
  isConfirmingReopen.value = true
  // Focus moves into the dialog so a keyboard user is not left tabbing through
  // the form behind it, and Escape has somewhere to land.
  await nextTick()
  reopenConfirm.value?.focus()
}

function closeReopenDialog() {
  isConfirmingReopen.value = false
  // Back to the control that opened it, rather than to the top of the document.
  reopenTrigger.value?.focus()
}

function cancelReopen() {
  closeReopenDialog()
}

async function confirmReopen() {
  closeReopenDialog()

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
    // Checked before saving: an over-limit answer is excluded from every save, so
    // submitting without this would silently send the last valid text instead.
    const overLimit = overLimitQuestions()
    if (overLimit.length) {
      setMessage(overLimitMessage(overLimit), true)
      void goToBlocker({ step: 'questions', focusKey: overLimit[0].key })
      return
    }

    // Checked here too so the refusal can point at what needs fixing; the server
    // stays the authority.
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
    // The server's sentence is used as-is: reaching here means the entry changed
    // underneath us, so there is nothing reliable to point at.
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
    setMessage(`That file is ${formatSize(file.size)}. The limit is ${maxSizeLabel(slot)}.`, true)
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
    // No confirmation: an attached file is visible in the slot. A showing preview
    // is refreshed so it never displays the file just replaced.
    if (slot === 'poster' || slot === 'report') await loadPreview(slot)
  } catch (error) {
    // A refused poster comes back with specific reasons; listing them is the point.
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

/** Notice the deadline passing while the page sits open, not only on a failed save. */
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
      // The banner below already explains the consequence; this is the one-off notice.
      setMessage('The submission deadline has just passed.', true)
    }
  } catch {
    // Best-effort: the next write still catches an authoritative closure.
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

  /* Names for the platform's colours, not colours of their own: each resolves
     to a token main.css defines, so the dark theme comes for free. */
  --panel-bg: var(--white);
  --panel-border: var(--border-light);
  --field-bg: var(--white);
  --field-border: var(--border-light);
  --field-disabled-bg: var(--bg-light);
  --notice-bg: var(--bg-light);
  --muted: var(--text-muted);
  --body-text: var(--charcoal);
  --accent: var(--dark-green);
  /* Muted towards the body text: --danger at full strength is a signal red for a
     word count creeping over a limit. Mixing with --charcoal tones both themes. */
  --error: color-mix(in srgb, var(--danger) 70%, var(--charcoal));
  /* The same treatment for the confirmation banner's text. */
  --ok-text: color-mix(in srgb, var(--dark-green) 78%, var(--charcoal));

  /* Tints the platform has no token for, mixed from platform colours so they
     follow the dark theme on their own. */
  --accent-soft: color-mix(in srgb, var(--dark-green) 12%, transparent);
  --error-bg: color-mix(in srgb, var(--danger) 10%, transparent);
  --ok-bg: color-mix(in srgb, var(--dark-green) 10%, transparent);

  color: var(--body-text);
  /* Overrides main.css's .content-area, which assumes a whole page: this is a
     section, and the group page supplies the padding, ground and scrolling. */
  /* The group page paints the ground; a tinted block of our own inside someone
     else's page is the "separate product" look the client objected to. */
  background-color: transparent;
  padding: 0;
  min-height: 0;
  overflow: visible;
}

/* No dark-mode block: every colour resolves to a token main.css redefines
   under [data-theme="dark"]. */

/* Pushed to the far end, so it stays right whether or not Resubmit is showing. */
.submission-due {
  display: flex;
  align-items: center;
  /* Wider than the 0.4rem it was: "Due", the date and the chip were running
     together as one string. */
  gap: 0.5rem;
  margin-left: auto;
  font-size: 0.875rem;
  white-space: nowrap;
}

.submission-due__date {
  font-weight: 600;
  color: var(--body-text);
}

/* Quiet, so the date is what the eye lands on: uppercase at 700 competed
   directly with the date beside it. */
.submission-due__label {
  color: var(--muted);
  font-weight: 400;
}

.status-line {
  display: flex;
  align-items: center;
  gap: 0.6rem;
  flex-wrap: wrap;
  /* Matches the step buttons' left padding so the badge sits on the same
     vertical line as the numbered step markers below it. */
  padding: 0 0.9rem;
  margin-bottom: 1.5rem;
  font-size: 0.875rem;
  color: var(--muted);
}

/* Same 24px disc as .submission-step__index, so the status and the steps read
   as one column of markers. */
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
  font-size: 1rem;
  color: var(--body-text);
  letter-spacing: -0.005em;
}

/* Follows the status text directly rather than being pushed right: the
   deadline now claims the far end of the line. */
.status-line__action {
  margin-left: 0.3rem;
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

/* The one piece of shape in the row: three runs of text at one size read flat,
   so the countdown becomes an object. A tint, not a fill. */
.submission-remaining {
  padding: 0.15rem 0.5rem;
  border-radius: 999px;
  background: var(--accent-soft);
  color: var(--accent);
  font-size: 0.8rem;
  font-weight: 600;
  line-height: 1.5;
}

/* Inside the last day the same chip changes colour rather than shape, so it
   draws the eye without the row rearranging itself underneath the student. */
.submission-remaining.is-near {
  background: var(--error-bg);
  color: var(--error);
}

/* Quieter than .submission-message--error: nothing here blocks a submission,
   and styling advice as failure trains students to ignore it. */
.poster-notice {
  margin-top: 0.75rem;
  padding: 0.65rem 0.85rem;
  border-left: 4px solid var(--accent);
  border-radius: 8px;
  background: var(--notice-bg);
  color: var(--body-text);
  font-size: 0.875rem;
}

.poster-notice__body {
  margin: 0;
}

.submission-message {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 0.75rem;
  padding: 0.65rem 0.95rem;
  margin-bottom: 1.5rem;
  border-radius: 8px;
  font-size: 0.875rem;
  font-weight: 600;
  /* No accent rule down the side: the wash and text colour already say which of
     the two this is, and an edge read as an alarm on a confirmation. */
  background: var(--ok-bg);
  color: var(--ok-text);
  font-size: 0.9rem;
}

.submission-message--error {
  background: var(--error-bg);
  color: var(--error);
}

/* Fixed, not absolute: the portal sits in the group page's scroll container,
   so an absolute overlay would scroll away with the form. */
.submission-dialog-backdrop {
  position: fixed;
  inset: 0;
  z-index: 60;
  display: flex;
  align-items: center;
  justify-content: center;
  padding: 1.5rem;
  background: rgba(6, 26, 22, 0.45);
}

.submission-dialog {
  background: var(--panel-bg);
  border-radius: 8px;
  box-shadow: 0 8px 24px var(--shadow);
  padding: 1.5rem;
  max-width: 27rem;
  width: 100%;
  display: flex;
  flex-direction: column;
  gap: 0.6rem;
}

.submission-dialog__title {
  margin: 0;
  font-size: 1.25rem;
  font-weight: 600;
  color: var(--body-text);
}

.submission-dialog__body {
  margin: 0;
  color: var(--muted);
  font-size: 0.95rem;
  line-height: 1.5;
}

.submission-dialog__actions {
  display: flex;
  justify-content: flex-end;
  gap: 0.6rem;
  margin-top: 0.6rem;
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
  font-size: 0.875rem;
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
/* An underline marks the active tab, quieter than a bordered card each, and
   makes the strip read as navigation. */
.submission-steps {
  display: flex;
  gap: 0.5rem;
  margin-bottom: 1.5rem;
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

/* Only the current step is highlighted: marking those behind made the styling
   depend on which direction you arrived from. */
.submission-step.is-active .submission-step__index {
  background: var(--accent);
  color: #fff;
}

.submission-step__label {
  font-weight: 700;
  font-size: 1rem;
  flex: 1;
}

.submission-step__state {
  font-size: 0.875rem;
  color: var(--muted);
  white-space: nowrap;
}


/* These are main.css's own .card: background, radius, shadow, padding and
   margin all come from the platform. */

/* .card-header's rhythm, but stacked: a title with a supporting line under it
   is not the row of controls .card-header assumes. */
.section-head {
  /* More room below than .card-header's 1rem: the first question sat tight under
     the rule. */
  margin: 0 0 1.5rem;
  padding-bottom: 1rem;
  border-bottom: 1px solid var(--panel-border);
}

/* .card-title from the platform; this only removes the heading margin main.css
   gives every h1-h6. */
.card-title {
  margin: 0;
}

.section-head__sub {
  margin: 0.35rem 0 0;
  color: var(--muted);
  font-size: 1rem;
  font-weight: 500;
  line-height: 1.55;
  max-width: 75ch;
}

/* A block inside a card, one level under its .card-title: body size, bolded. */
.panel-subheading {
  margin: 0 0 0.3rem;
  font-size: 1rem;
  font-weight: 600;
  line-height: 1.3;
}

/* Each question is its own block of thought; the space between them is what
   separates six answers into six tasks rather than one long page. */
.submission-field + .submission-field {
  margin-top: 2rem;
}

/* Body size, bolded: a form label, not a heading. At 1.25rem it matched
   .card-title and flattened the rank. */
.submission-label {
  display: block;
  font-weight: 600;
  font-size: 1rem;
  line-height: 1.35;
  margin-bottom: 0.55rem;
}

/* A field inside a section: reusing .submission-label here made the prototype
   link shout louder than the Prototype heading above it. */
.field-label {
  display: block;
  font-weight: 600;
  font-size: 0.875rem;
  color: var(--body-text);
  margin-bottom: 0.4rem;
}

.submission-muted {
  color: var(--muted);
  font-size: 0.875rem;
  line-height: 1.5;
  margin: 0.2rem 0;
}

/* Set explicitly, or the platform's .form-control inputs stay white in the dark
   theme, which is the one genuinely unreadable combination. */
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
  font-size: 1rem;
  font-weight: 600;
}

/* Sits above the attachment state, since it is what to do before uploading. */
.submission-template {
  margin: 0.35rem 0 0.6rem;
  font-size: 0.875rem;
  color: var(--body-text);
}

.submission-template a {
  color: var(--accent);
  font-weight: 600;
}

/* Mirrors the resource library's preview panel. The panel carries the border
   and clips the frame, which is why the frame has none. */
.preview-panel {
  background: var(--panel-bg);
  border-radius: 8px;
  box-shadow: 0 2px 4px var(--shadow);
  min-height: 560px;
  overflow: hidden;
  margin-top: 1rem;
}

/* Folded away this becomes a row in the card: a shadowed white box sitting on
   the card's white box reads as a bar floating on the page. */
.preview-panel.is-collapsed {
  min-height: 0;
  background: none;
  box-shadow: none;
}

/* Flush with the card's own padding, so the collapsed row lines up with the
   content above it rather than being indented inside an invisible box. */
.preview-panel.is-collapsed .preview-header {
  border-bottom: none;
  padding: 0.75rem 0;
}

.preview-header {
  align-items: center;
  border-bottom: 1px solid var(--panel-border);
  display: flex;
  justify-content: space-between;
  padding: 1rem 1.25rem;
}

/* Same level as .panel-subheading: a block inside a card, under its title. */
.preview-title {
  font-size: 1rem;
  font-weight: 600;
  margin: 0;
}

/* Looks like the heading it sits in; the chevron says it folds. The whole row
   is the hit target. */
.preview-toggle {
  display: inline-flex;
  align-items: center;
  gap: 0.5rem;
  padding: 0;
  border: none;
  background: none;
  font: inherit;
  color: inherit;
  cursor: pointer;
}

.preview-toggle:focus-visible {
  outline: 2px solid var(--accent);
  outline-offset: 3px;
}

.preview-toggle__chevron {
  font-size: 0.75rem;
  color: var(--muted);
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
  font-size: 0.875rem;
  color: var(--muted);
}

/* The arrows read as one control, so they sit tighter to each other than to
   Submit. */
.submission-steps-nav {
  display: flex;
  gap: 0.35rem;
}

/* Square and 44px: an icon-only button loses its label as a target as well as
   as a hint. */
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
