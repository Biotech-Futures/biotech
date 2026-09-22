<template>
  <!-- Design tokens for this section are declared on .content-area. -->
  <div class="content-area">
    <div v-if="isLoading" class="card">
      <p>Loading submission…</p>
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

      <!-- An in-page dialog, since browsers can suppress window.confirm(). -->
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

      <div v-if="message" class="submission-message" :class="{ 'submission-message--error': isError }">
        <span>{{ message }}</span>
        <button type="button" class="submission-message__close" aria-label="Dismiss" @click="dismissMessage">
          &times;
        </button>
      </div>

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
          <span class="submission-step__state">{{ stepSummary(tab.key) }}</span>
        </button>
      </nav>

      <!-- 1. Short-answer questions -->
      <section v-show="activeTab === 'questions'" class="card">
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
          <!-- No maxlength: the count warns and the server refuses over-limit answers. -->
          <textarea
            :id="question.key"
            v-model="answers[question.key]"
            class="form-control submission-textarea"
            rows="5"
            :disabled="!isEditable"
          ></textarea>
          <p
            v-if="question.max_words && wordCount(question.key) > 0"
            class="submission-count"
            :class="{ 'is-over-limit': wordCount(question.key) > question.max_words }"
          >
            {{ wordCount(question.key) }} / {{ question.max_words }} words
          </p>
        </div>
      </section>

      <!-- 2. Poster -->
      <section v-show="activeTab === 'poster'" class="card">
        <header v-if="sectionHeading || sectionBody" class="section-head">
          <h2 v-if="sectionHeading" class="card-title">{{ sectionHeading }}</h2>
          <p v-if="sectionBody" class="section-head__sub">
            {{ sectionBody }}
            Your poster must use the programme's
            <RouterLink
              class="submission-template-link"
              :to="`/resources/${POSTER_TEMPLATE_RESOURCE_ID}`"
            >
              template
              <i class="fas fa-arrow-up-right-from-square" aria-hidden="true"></i>
            </RouterLink>.
          </p>
        </header>

        <div class="submission-slot submission-slot--plain">
          <div class="submission-slot__info">
            <p class="submission-muted">PDF only · up to {{ maxSizeLabel('poster') }}</p>

            <p v-if="storedFile('poster')" class="submission-file">
              <a :href="downloadUrl('poster')" target="_blank" rel="noopener noreferrer">
                {{ storedFile('poster')?.name }}
              </a>
              <span class="submission-muted"> ({{ formatSize(storedFile('poster')?.size) }})</span>
            </p>
            <p v-else class="submission-muted">Nothing attached yet.</p>

            <div v-if="isPosterNoticeShown" class="poster-notice">
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

        <!-- Checks the slot too, since hidden steps stay in the DOM. -->
        <article class="preview-panel" :class="{ 'is-collapsed': previewCollapsed.poster }">
          <div class="preview-header">
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
            <!-- Always offered, as some browsers will not embed a PDF. -->
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

          <!-- Hidden rather than destroyed, so reopening does not refetch the document. -->
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

      <!-- 3. Additional materials -->
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

      <div class="submission-actions">

        <span
          v-if="isEditable"
          class="submission-savestate"
          :class="{ 'is-error': saveState === 'error' }"
        >
          {{ saveStateLabel }}
        </span>

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

        <button
          v-if="isEditable"
          class="btn btn-primary"
          type="button"
          :disabled="isBusy"
          @click="onSubmit"
        >
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
  fetchSubmission,
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

const TABS: { key: TabKey; label: string }[] = [
  { key: 'questions', label: 'Questions' },
  { key: 'poster', label: 'Poster' },
  { key: 'extras', label: 'Additional materials' }
]

const AUTOSAVE_DELAY_MS = 2000

// Used only until the server's limits have loaded.
const FALLBACK_MAX_FILE_SIZES: Record<SubmissionSlot, number> = {
  poster: 20 * 1024 * 1024,
  report: 20 * 1024 * 1024,
  prototype: 50 * 1024 * 1024
}

const MESSAGE_TIMEOUT_MS = 4000

// Resource library entry for the poster template.
const POSTER_TEMPLATE_RESOURCE_ID = 9

const route = useRoute()
const groupId = computed(() => String(route.params.id ?? ''))

const detail = ref<SubmissionDetail | null>(null)
const isLoading = ref(true)
const loadError = ref('')

const answers = reactive<Record<string, string>>({})
const prototypeUrl = ref('')

/** Answers the server holds, so only changes are sent. */
let savedAnswers: Record<string, string> = {}

/** Changed answers that are within their word limit. */
function changedAnswers(): Record<string, string> {
  const overLimit = new Set(overLimitQuestions().map((q) => q.key))
  const changed: Record<string, string> = {}
  Object.keys(answers).forEach((key) => {
    if (overLimit.has(key)) return
    // Compared against '' so a cleared answer is still sent; omitted keys are left unchanged.
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
const now = ref(Date.now())
const previewSource = ref('')
const previewSlot = ref<SubmissionSlot | ''>('')
const isPreviewLoading = ref(false)
const message = ref('')
const isError = ref(false)

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
const isEditable = computed(() => isOpen.value && !isLocked.value)
const isBusy = computed(
  () => isSaving.value || isSubmitting.value || isReopening.value || Boolean(busySlot.value)
)

const showsSubmittedCopy = computed(() => {
  const submission = detail.value?.submission
  if (!submission?.is_submitted) return false
  return submission.is_locked || !isOpen.value
})

const posterWarnings = computed(() => {
  const submission = detail.value?.submission
  if (!submission) return []
  const checks = showsSubmittedCopy.value
    ? submission.submitted_poster_checks
    : submission.poster_checks
  return checks?.warnings ?? []
})

const isPosterNoticeShown = ref(false)
let posterNoticeTimer: ReturnType<typeof setTimeout> | null = null
// Keyed on the file and its findings, so an auto-save does not bring the notice back.
watch(
  () => `${shownFile('poster')?.storage_key ?? ''}|${posterWarnings.value.map((w) => w.code).join(',')}`,
  () => {
    if (posterNoticeTimer) clearTimeout(posterNoticeTimer)
    isPosterNoticeShown.value = posterWarnings.value.length > 0
    if (isPosterNoticeShown.value) {
      posterNoticeTimer = setTimeout(() => {
        isPosterNoticeShown.value = false
      }, MESSAGE_TIMEOUT_MS)
    }
  },
  { immediate: true }
)

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

const stage = computed<SubmissionStage>(
  () => detail.value?.submission?.stage ?? 'not_started'
)

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

const timeRemaining = computed(() =>
  isOpen.value ? describeTimeRemaining(detail.value?.deadline.closes_at, now.value) : ''
)

const isDeadlineNear = computed(
  () => isOpen.value && deadlineIsNear(detail.value?.deadline.closes_at, now.value)
)

const deadlineDetail = computed(() => {
  if (!detail.value?.deadline.closes_at) {
    return 'An administrator needs to set a deadline before entries can be saved.'
  }
  // Times are stored in UTC, so name the viewer's time zone.
  return `Shown in your local time (${localZone}).`
})

const localZone = Intl.DateTimeFormat().resolvedOptions().timeZone

function stepSummary(key: TabKey): string {
  if (key === 'questions') {
    return describeQuestionStep(answers, questions.value.map((q) => q.key))
  }
  if (key === 'poster') return 'Required'
  return 'Optional'
}

function formatDate(value: string) {
  return new Date(value).toLocaleString(undefined, {
    dateStyle: 'medium',
    timeStyle: 'short'
  })
}

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

function previewUrlFor(slot: SubmissionSlot) {
  return submissionFilePreviewUrl(groupId.value, slot)
}

/** Changes when the file is replaced, so the frame does not show a cached copy. */
function previewVersion(slot: SubmissionSlot) {
  return encodeURIComponent(storedFile(slot)?.storage_key ?? '')
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

  if (text) {
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

function overLimitQuestions() {
  return questions.value.filter((q) => q.max_words && wordCount(q.key) > q.max_words)
}

function overLimitMessage(list: ReturnType<typeof overLimitQuestions>): string {
  return `Answer too long for "${list[0].prompt}"`
}

function unansweredQuestions() {
  return questions.value.filter((q) => q.is_required && !(answers[q.key] ?? '').trim())
}

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

async function goToBlocker(blocker: { step: TabKey; focusKey?: string }) {
  goToStep(TABS.findIndex((tab) => tab.key === blocker.step))
  if (!blocker.focusKey) return
  await nextTick()
  const field = document.getElementById(blocker.focusKey)
  if (!(field instanceof HTMLTextAreaElement)) return
  field.focus()
  // jsdom has no layout, so this rejects in tests.
  if (typeof field.scrollIntoView === 'function') {
    field.scrollIntoView({ behavior: 'smooth', block: 'center' })
  }
}

function applyResult(result: SubmissionWriteResult) {
  if (!detail.value) return
  detail.value = { ...detail.value, deadline: result.deadline, submission: result.submission }
}

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

function clearPreview() {
  previewSource.value = ''
  previewSlot.value = ''
  isPreviewLoading.value = false
}

/** Navigated to, not fetched: Azure's redirect is unreadable by fetch(). */
async function loadPreview(slot: SubmissionSlot) {
  clearPreview()
  if (!storedFile(slot)) return

  previewSlot.value = slot
  previewSource.value = `${previewUrlFor(slot)}?v=${previewVersion(slot)}`
}

async function syncPreviewForTab() {
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

function currentSnapshot() {
  return JSON.stringify({ answers, prototypeUrl: prototypeUrl.value })
}

function formatTime(value: Date) {
  return value.toLocaleTimeString(undefined, { hour: '2-digit', minute: '2-digit' })
}

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
    // Only keys this save sent join the baseline, so a teammate's newer answer is kept.
    Object.assign(savedAnswers, sent)
    savedSnapshot.value = snapshot
    lastSavedAt.value = new Date()
    saveState.value = overLimit.length ? 'unsaved' : 'idle'
  } catch (error) {
    saveState.value = 'error'
    setMessage(handleWriteError(error), true)
  } finally {
    isSaving.value = false
  }
}

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

function cancelReopen() {
  closeReopenDialog()
}

async function confirmReopen() {
  closeReopenDialog()

  isReopening.value = true
  setMessage('')
  try {
    applyResult(await reopenEntry(groupId.value))
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
    // An over-limit answer is left out of saves, so submitting would send its last valid text.
    const overLimit = overLimitQuestions()
    if (overLimit.length) {
      setMessage(overLimitMessage(overLimit), true)
      void goToBlocker({ step: 'questions', focusKey: overLimit[0].key })
      return
    }

    const blocker = submissionBlockers()
    if (blocker) {
      setMessage(blocker.message, true)
      void goToBlocker(blocker)
      return
    }

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
    setMessage(handleWriteError(error), true)
  } finally {
    isSubmitting.value = false
  }
}

async function onFileChosen(slot: SubmissionSlot, event: Event) {
  const input = event.target as HTMLInputElement
  const file = input.files?.[0]
  if (!file) return

  // Checked before uploading; the server enforces it too.
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
    // Refresh a showing preview so it never displays the replaced file.
    if (slot === 'poster' || slot === 'report') await loadPreview(slot)
  } catch (error) {
    const problems = apiErrorFromUnknown(error).body?.problems
    if (Array.isArray(problems) && problems.length) {
      setMessage(problems.join(' '), true)
    } else {
      setMessage(handleWriteError(error), true)
    }
  } finally {
    busySlot.value = ''
    uploadPercent.value = 0
    // Cleared so choosing the same file again still fires a change.
    input.value = ''
  }
}

async function removeFile(slot: SubmissionSlot) {
  busySlot.value = slot
  setMessage('')
  try {
    applyResult(await removeSubmissionFile(groupId.value, slot))
    if (slot === previewSlot.value) clearPreview()
  } catch (error) {
    setMessage(handleWriteError(error), true)
  } finally {
    busySlot.value = ''
  }
}

onMounted(load)

const clockTimer = setInterval(() => {
  now.value = Date.now()
}, 60000)

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
      setMessage('The submission deadline has just passed.', true)
    }
  } catch {
    deadlineRecheckDone = false
  }
})

watch([answers, prototypeUrl], scheduleAutosave, { deep: true })

watch(activeTab, () => {
  // Save on leaving a step rather than waiting for the timer.
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
  if (autosaveTimer) clearTimeout(autosaveTimer)
  if (posterNoticeTimer) clearTimeout(posterNoticeTimer)
  clearInterval(clockTimer)
  clearPreview()
})
</script>

<style scoped>
.content-area {

  /* Aliases for platform tokens, so the dark theme applies automatically. */
  --panel-bg: var(--white);
  --panel-border: var(--border-light);
  --field-bg: var(--white);
  --field-border: var(--border-light);
  --field-disabled-bg: var(--bg-light);
  --notice-bg: var(--bg-light);
  --muted: var(--text-muted);
  --body-text: var(--charcoal);
  --accent: var(--dark-green);
  /* Muted so an over-limit warning is not signal red. */
  --error: color-mix(in srgb, var(--danger) 70%, var(--charcoal));
  --ok-text: color-mix(in srgb, var(--dark-green) 78%, var(--charcoal));

  /* Tints mixed from platform colours, so they follow the dark theme. */
  --accent-soft: color-mix(in srgb, var(--dark-green) 12%, transparent);
  --error-bg: color-mix(in srgb, var(--danger) 10%, transparent);
  --ok-bg: color-mix(in srgb, var(--dark-green) 10%, transparent);

  color: var(--body-text);
  /* Overrides main.css's page-level .content-area; the group page supplies padding and scrolling. */
  background-color: transparent;
  padding: 0;
  min-height: 0;
  overflow: visible;
}


.submission-due {
  display: flex;
  align-items: baseline;
  gap: 0.35rem;
  margin-left: auto;
  font-size: 0.875rem;
  font-weight: 600;
  color: var(--body-text);
  white-space: nowrap;
}

/* Plain text after a dot, so the whole deadline reads as one line. */
.submission-due .submission-remaining::before,
.submission-due .status-badge::before {
  content: '·';
  margin-right: 0.35rem;
  color: var(--muted);
}

.submission-due .status-badge {
  padding: 0;
  border-radius: 0;
  background: none;
  color: inherit;
  font-size: inherit;
  font-weight: inherit;
}

.status-line {
  display: flex;
  align-items: center;
  gap: 0.6rem;
  flex-wrap: wrap;
  padding: 0 0.9rem;
  margin-bottom: 1.5rem;
  font-size: 0.875rem;
  color: var(--muted);
}

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

.status-line__action {
  margin-left: 0.3rem;
}

.status-line.is-submitted .status-line__icon {
  background: var(--accent);
  color: #fff;
}

.status-line.is-submitted .status-line__state {
  color: var(--accent);
}

.status-line.is-missed .status-line__icon {
  background: var(--field-disabled-bg);
  color: var(--muted);
}

.status-line.is-missed .status-line__state {
  color: var(--body-text);
}

.submission-remaining {
  color: var(--accent);
}

.submission-remaining.is-near {
  color: var(--error);
}

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
  background: var(--ok-bg);
  color: var(--ok-text);
  font-size: 0.9rem;
}

.submission-message--error {
  background: var(--error-bg);
  color: var(--error);
}

/* Fixed, since the portal scrolls inside the group page. */
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



.section-head {
  margin: 0 0 1.5rem;
  padding-bottom: 1rem;
  border-bottom: 1px solid var(--panel-border);
}

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

.panel-subheading {
  margin: 0 0 0.3rem;
  font-size: 1rem;
  font-weight: 600;
  line-height: 1.3;
}

.submission-field + .submission-field {
  margin-top: 2rem;
}

.submission-label {
  display: block;
  font-weight: 600;
  font-size: 1rem;
  line-height: 1.35;
  margin-bottom: 0.55rem;
}

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

/* Set explicitly, as .form-control stays white in the dark theme. */
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

.submission-template-link {
  color: var(--accent);
  font-weight: 600;
  white-space: nowrap;
}

.submission-template-link i {
  font-size: 0.75em;
  margin-left: 0.2em;
}

.preview-panel {
  background: var(--panel-bg);
  border-radius: 8px;
  box-shadow: 0 2px 4px var(--shadow);
  min-height: 560px;
  overflow: hidden;
  margin-top: 1rem;
}

.preview-panel.is-collapsed {
  min-height: 0;
  background: none;
  box-shadow: none;
}

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

.preview-title {
  font-size: 1rem;
  font-weight: 600;
  margin: 0;
}

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

.submission-steps-nav {
  display: flex;
  gap: 0.35rem;
}

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
