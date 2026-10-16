<template>
  <!-- Design tokens for this section are declared on .content-area. -->
  <!-- Stray drops are swallowed so the browser never navigates away to the file. -->
  <div
    class="content-area"
    :class="{ 'is-dragging-file': isDraggingFile }"
    @dragover.prevent
    @drop.prevent
  >
    <div v-if="isLoading" class="card">
      <p>Loading submission…</p>
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
        <strong class="status-line__state">{{ state.headline
          }}{{ state.detail ? '.' : '' }}</strong>
        <span v-if="state.detail" class="status-line__detail">{{ state.detail }}</span>

        <button
          v-if="isLocked && canAct"
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

      <!-- Admins confirm anything the team will see. -->
      <div
        v-if="adminDialog"
        class="submission-dialog-backdrop"
        role="dialog"
        aria-modal="true"
        aria-labelledby="admin-dialog-title"
        tabindex="-1"
        data-testid="admin-dialog"
        @keydown.esc="answerAdminDialog(false)"
      >
        <section class="submission-dialog">
          <h2 id="admin-dialog-title" class="submission-dialog__title">{{ adminDialog.title }}</h2>
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

      <div v-if="message" ref="messageBanner" class="submission-message" :class="{ 'submission-message--error': isError }">
        <span>{{ message }}</span>
        <button type="button" class="submission-message__close" aria-label="Dismiss" @click="dismissMessage">
          &times;
        </button>
      </div>

      <SubmissionStepStrip
        :steps="tabs"
        :active="activeTab"
        :summary="stepSummary"
        @select="selectTab"
      />

      <!-- 1. Short-answer questions -->
      <section v-show="activeTab === 'questions'" class="card">
        <header v-if="sectionHeading || sectionBody" class="section-head">
          <h2 v-if="sectionHeading" class="card-title">{{ sectionHeading }}</h2>
          <p v-if="sectionBody" class="section-head__sub">{{ sectionBody }}</p>
        </header>

        <div class="submission-field">
          <label class="submission-label" for="project-title">
            Project title
            <span class="submission-required" title="Required" aria-label="required">*</span>
          </label>
          <input
            id="project-title"
            v-model="projectTitle"
            class="form-control"
            type="text"
            :maxlength="PROJECT_TITLE_MAX_LENGTH"
            v-show="!live.isLocked(TITLE_FIELD)"
            :disabled="!isEditable || live.isLocked(TITLE_FIELD)"
            @input="shareTyping(TITLE_FIELD, $event)"
          />
          <LiveTextPanel
            v-if="live.isLocked(TITLE_FIELD)"
            class="form-control"
            :text="projectTitle"
            :caret="live.caretIn(TITLE_FIELD)"
            :rows="1"
          />
          <div class="submission-field-meta">
            <TypingIndicator :names="live.typingIn(TITLE_FIELD)" />
          </div>
        </div>

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
          <div class="submission-stretch">
            <textarea
              :id="question.key"
              v-model="answers[question.key]"
              class="form-control submission-textarea"
              :rows="ANSWER_ROWS"
              v-show="!live.isLocked(question.key)"
              :style="boxHeights[question.key] ? { height: `${boxHeights[question.key]}px` } : undefined"
              :disabled="!isEditable || live.isLocked(question.key)"
              @input="shareTyping(question.key, $event)"
            ></textarea>
            <LiveTextPanel
              v-if="live.isLocked(question.key)"
              class="submission-textarea"
              :text="answers[question.key] ?? ''"
              :caret="live.caretIn(question.key)"
              :rows="ANSWER_ROWS"
              :height="boxHeights[question.key] ?? null"
            />
            <StretchHandle
              :height="boxHeights[question.key] ?? null"
              @update:height="boxHeights[question.key] = $event"
            />
          </div>
          <div class="submission-field-meta">
            <p
              v-if="question.max_words && wordCount(question.key) > 0"
              class="submission-count"
              :class="{ 'is-over-limit': wordCount(question.key) > question.max_words }"
            >
              {{ wordCount(question.key) }} / {{ question.max_words }} words
            </p>
            <TypingIndicator :names="live.typingIn(question.key)" />
          </div>
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

        <PosterChecklist
          :ticks="posterChecklist"
          :ready="Boolean(storedFile('poster'))"
          :disabled="!isEditable"
          @toggle="tickChecklist"
        />

        <!-- The slot and its preview form one drop zone. -->
        <div
          class="drop-zone"
          :class="{ 'is-drop-target': dragSlot === 'poster' }"
          data-testid="drop-poster"
          @dragover.prevent="onDragOver('poster', $event)"
          @dragleave="onDragLeave('poster', $event)"
          @drop.prevent="onDrop('poster', $event)"
        >
        <div class="submission-slot submission-slot--plain submission-slot--divided">
          <div class="submission-slot__info">
            <p class="submission-muted">
              PDF only · up to {{ maxSizeLabel('poster') }}<span v-if="isEditable"> · or drop it here</span>
            </p>

            <p v-if="storedFile('poster')" class="submission-file">
              <a :href="downloadUrl('poster')" target="_blank" rel="noopener noreferrer">
                {{ storedFile('poster')?.name }}
              </a>
              <span class="submission-muted"> ({{ formatSize(storedFile('poster')?.size) }}{{ pendingNote('poster') }})</span>
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

        <!-- Checks the slot too, since hidden steps stay in the DOM. -->
        <article class="preview-panel" :class="{ 'is-collapsed': isFolded('poster') }">
          <div class="preview-header">
            <h2 class="preview-title">
              <button
                type="button"
                class="preview-toggle"
                :aria-expanded="!isFolded('poster')"
                aria-controls="poster-preview-body"
                data-testid="toggle-poster-preview"
                :disabled="isPreviewShut('poster')"
                @click="togglePreview('poster')"
              >
                <i
                  class="fas preview-toggle__chevron"
                  :class="isFolded('poster') ? 'fa-chevron-right' : 'fa-chevron-down'"
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
          <div v-show="!isFolded('poster')" id="poster-preview-body">
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
        </div>
      </section>

      <!-- 3. Additional materials -->
      <div v-show="activeTab === 'extras'">
        <section class="card">
          <header v-if="sectionHeading || sectionBody" class="section-head">
          <h2 v-if="sectionHeading" class="card-title">{{ sectionHeading }}</h2>
          <p v-if="sectionBody" class="section-head__sub">{{ sectionBody }}</p>
        </header>

          <div
            class="drop-zone"
            :class="{ 'is-drop-target': dragSlot === 'report' }"
            data-testid="drop-report"
            @dragover.prevent="onDragOver('report', $event)"
            @dragleave="onDragLeave('report', $event)"
            @drop.prevent="onDrop('report', $event)"
          >
          <div class="submission-slot submission-slot--plain">
            <div class="submission-slot__info">
              <h2 class="panel-subheading">Scientific report</h2>
              <p class="submission-muted">
                PDF only · up to {{ maxSizeLabel('report') }}<span v-if="isEditable"> · or drop it here</span>
              </p>

              <p v-if="storedFile('report')" class="submission-file">
                <a :href="downloadUrl('report')" target="_blank" rel="noopener noreferrer">
                  {{ storedFile('report')?.name }}
                </a>
                <span class="submission-muted"> ({{ formatSize(storedFile('report')?.size) }}{{ pendingNote('report') }})</span>
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

          <article class="preview-panel" :class="{ 'is-collapsed': isFolded('report') }">
            <div class="preview-header">
              <h2 class="preview-title">
                <button
                  type="button"
                  class="preview-toggle"
                  :aria-expanded="!isFolded('report')"
                  aria-controls="report-preview-body"
                  data-testid="toggle-report-preview"
                  :disabled="isPreviewShut('report')"
                @click="togglePreview('report')"
                >
                  <i
                    class="fas preview-toggle__chevron"
                    :class="isFolded('report') ? 'fa-chevron-right' : 'fa-chevron-down'"
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

            <div v-show="!isFolded('report')" id="report-preview-body">
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
          </div>
        </section>

        <section class="card">
          <div
            class="submission-slot submission-slot--plain"
            :class="{ 'is-drop-target': dragSlot === 'prototype' }"
            data-testid="drop-prototype"
            @dragover.prevent="onDragOver('prototype', $event)"
            @dragleave="onDragLeave('prototype', $event)"
            @drop.prevent="onDrop('prototype', $event)"
          >
            <div class="submission-slot__info">
              <h2 class="panel-subheading">Prototype</h2>
              <p class="submission-muted">
                Any file type · up to {{ maxSizeLabel('prototype') }}<span v-if="isEditable"> · or drop it here</span>
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
                <span class="submission-muted"> ({{ formatSize(storedFile('prototype')?.size) }}{{ pendingNote('prototype') }})</span>
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

          <div v-if="isEditable || prototypeUrl" class="submission-field">
            <label class="field-label" for="prototype-url">Prototype link</label>
            <input
              id="prototype-url"
              v-model="prototypeUrl"
              class="form-control"
              type="url"
              placeholder="https://…"
              :disabled="!isEditable"
              :aria-invalid="linkNote ? 'true' : undefined"
              :aria-describedby="linkNote ? 'prototype-url-note' : undefined"
              @blur="tidyLink"
            />
            <p v-if="linkNote" id="prototype-url-note" class="submission-field-note">{{ linkNote }}</p>
          </div>
        </section>
      </div>


      <div class="submission-actions">

        <span
          v-if="isEditable && !adminAccess"
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
            :aria-label="isFirstStep ? 'Previous step' : `Back: ${tabs[stepIndex - 1].label}`"
            :title="isFirstStep ? undefined : `Back: ${tabs[stepIndex - 1].label}`"
            @click="goToStep(stepIndex - 1)"
          >
            <i class="fas fa-arrow-left" aria-hidden="true"></i>
          </button>
          <button
            class="btn btn-outline btn-icon"
            type="button"
            :disabled="isBusy || isLastStep"
            :aria-label="isLastStep ? 'Next step' : `Next: ${tabs[stepIndex + 1].label}`"
            :title="isLastStep ? undefined : `Next: ${tabs[stepIndex + 1].label}`"
            @click="goToStep(stepIndex + 1)"
          >
            <i class="fas fa-arrow-right" aria-hidden="true"></i>
          </button>
        </div>

        <button
          v-if="isEditable && !adminAccess"
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
import SubmissionStepStrip from '@/components/submission/SubmissionStepStrip.vue'
import { useFileDragging } from '@/components/submission/useFileDragging'
import LiveTextPanel from '@/components/live/LiveTextPanel.vue'
import PosterChecklist from '@/components/submission/PosterChecklist.vue'
import AdminSubmissionBar from '@/components/submission/AdminSubmissionBar.vue'
import StretchHandle from '@/components/submission/StretchHandle.vue'
import TypingIndicator from '@/components/live/TypingIndicator.vue'
import { useLiveRoom } from '@/composables/useLiveRoom'
import { RouterLink, useRoute, useRouter } from 'vue-router'
import { apiErrorFromUnknown } from '@/utils/apiError'
import { formatDayMonthTime } from '@/utils/date'
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
const router = useRouter()
const groupId = computed(() => String(route.params.id ?? ''))

const detail = ref<SubmissionDetail | null>(null)
const isLoading = ref(true)
const loadError = ref('')

const answers = reactive<Record<string, string>>({})
const prototypeUrl = ref('')
const projectTitle = ref('')
const PROJECT_TITLE_MAX_LENGTH = 150
const PROTOTYPE_URL_MAX_LENGTH = 500

/** Set once the link field is left, so a half-typed link is not flagged. */
const linkChecked = ref(false)

/** The link as it will be saved, with https:// added when no scheme was given. */
function normalisedLink() {
  const link = prototypeUrl.value.trim()
  if (!link || /^[a-z][a-z0-9+.-]*:\/\//i.test(link)) return link
  return `https://${link}`
}

function linkProblem(): string {
  const link = normalisedLink()
  if (!link) return ''
  if (link.length > PROTOTYPE_URL_MAX_LENGTH) {
    return `This link is longer than ${PROTOTYPE_URL_MAX_LENGTH} characters. Use a shorter share link.`
  }
  try {
    const url = new URL(link)
    if (['http:', 'https:'].includes(url.protocol) && url.hostname.includes('.') && !/\s/.test(link)) return ''
  } catch {
    // Unparseable, so reported below.
  }
  return "This doesn't look like a web link. Paste the full address, for example https://www.figma.com/…"
}

const linkNote = computed(() => (linkChecked.value ? linkProblem() : ''))

function tidyLink() {
  if (!isEditable.value) return
  linkChecked.value = true
  const link = normalisedLink()
  if (link !== prototypeUrl.value) prototypeUrl.value = link
}

/** A link with a problem is left out, so the server keeps the last good one. */
function draftFields(answers: Record<string, string>): {
  answers: Record<string, string>
  project_title?: string
  prototype_url?: string
  poster_checklist?: Record<string, boolean>
} {
  const link = linkProblem() ? savedLink : normalisedLink()
  const ticks = checklistChanges()
  return {
    answers,
    ...titleIfChanged(),
    ...(link === savedLink ? {} : { prototype_url: link }),
    ...(Object.keys(ticks).length ? { poster_checklist: ticks } : {})
  }
}

/** Answers the server holds, so only changes are sent. */
let savedAnswers: Record<string, string> = {}
/** The title the server holds; it is only sent when changed here, so a teammate's newer title is kept. */
let savedTitle = ''
/** Likewise for the prototype link. */
let savedLink = ''

function titleIfChanged(): { project_title?: string } {
  return projectTitle.value === savedTitle ? {} : { project_title: projectTitle.value }
}

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
const isRefreshing = ref(false)
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
// Admins act for a team at any time, read-only until they choose Edit.
const adminAccess = computed(() => Boolean(detail.value?.admin_access))
const adminEditing = ref(false)
const canAct = computed(() => isOpen.value || adminAccess.value)
const isEditable = computed(() => canAct.value && (adminAccess.value ? adminEditing.value : !isLocked.value))

// While the portal is on screen and the round is open, so changes made elsewhere arrive at once.
const live = useLiveRoom(
  'submission',
  groupId,
  // An admin editing leaves the room, so their unsaved work is never shown to the team.
  computed(() => canAct.value && route.name === 'group-submission' && !adminEditing.value)
)
const TITLE_FIELD = 'project-title'
/** Room for most of an answer before anyone needs to stretch the box. */
const ANSWER_ROWS = 7
/** Heights people have stretched answer boxes to, by question. */
const boxHeights = reactive<Record<string, number>>({})

function shareTyping(field: string, event: Event) {
  if (adminAccess.value) return
  const input = event.target as HTMLInputElement | HTMLTextAreaElement
  live.sendTyping(field)
  live.sendText(field, input.value, input.selectionStart ?? input.value.length)
}

// A teammate's text is theirs to save, so it is taken as already saved here.
live.onRemoteText((field, text) => {
  const wasSaved = currentSnapshot() === savedSnapshot.value
  if (field === TITLE_FIELD) {
    projectTitle.value = text
    savedTitle = text
  } else if (field in answers) {
    answers[field] = text
    savedAnswers[field] = text
  } else {
    return
  }
  if (wasSaved) savedSnapshot.value = currentSnapshot()
})

// Something changed elsewhere (a submit, reopen, file, tick or an admin's save): caught up at once.
live.onChanged(() => void catchUp())

const FILE_SLOTS: SubmissionSlot[] = ['poster', 'report', 'prototype']

function fileKeys(entry: SubmissionDetail | null): string {
  return FILE_SLOTS.map((slot) => entry?.submission?.[slot]?.storage_key ?? '').join('|')
}

/** Brings the page in line with the server: status, files and ticks always, and any box not being edited here. */
async function catchUp() {
  resyncTimer = null
  // An admin's edits are their own until Save or Submit, so nothing is brought in meanwhile.
  if (!detail.value || isSubmitting.value || isReopening.value || adminEditing.value) return
  try {
    const before = resultsApplied
    const latest = await fetchSubmission(groupId.value)
    if (!detail.value || adminEditing.value) return
    // A write answered meanwhile, so this copy may be older than the page: fetch again.
    if (resultsApplied !== before) return void catchUp()
    const wasLocked = isLocked.value
    const submittedBefore = detail.value.submission?.submitted_at ?? ''
    const filesBefore = fileKeys(detail.value)
    detail.value = latest
    // A resubmission keeps the entry locked, so a new submitted copy is checked for too.
    if (wasLocked !== isLocked.value || submittedBefore !== (latest.submission?.submitted_at ?? '')) {
      syncFromDetail()
      await syncPreviewForTab()
      return
    }
    if (filesBefore !== fileKeys(latest)) {
      syncChecklist()
      await syncPreviewForTab()
    } else {
      mergeChecklist()
    }
    syncUntouchedFields()
  } catch {
    // Best effort: the next change, release or reconnect tries again.
  }
}

/** Live text can be missed, so boxes not edited here, and not being typed in, take what was saved. */
function syncUntouchedFields() {
  const saved = detail.value?.submission
  if (!saved || showsSubmittedCopy.value) return
  const wasSaved = currentSnapshot() === savedSnapshot.value
  questions.value.forEach(({ key }) => {
    if (live.isLocked(key) || (answers[key] ?? '') !== (savedAnswers[key] ?? '')) return
    answers[key] = saved.answers?.[key] ?? ''
    savedAnswers[key] = answers[key]
  })
  if (!live.isLocked(TITLE_FIELD) && projectTitle.value === savedTitle) {
    projectTitle.value = saved.project_title ?? ''
    savedTitle = projectTitle.value
  }
  if (prototypeUrl.value === savedLink) {
    prototypeUrl.value = saved.prototype_url ?? ''
    savedLink = prototypeUrl.value
  }
  if (wasSaved) savedSnapshot.value = currentSnapshot()
}

// Allows for the typist's own autosave, which follows their last keystroke by AUTOSAVE_DELAY_MS.
const RESYNC_DELAY_MS = 2500
let resyncTimer: ReturnType<typeof setTimeout> | null = null
live.onSettled((reason) => {
  if (resyncTimer) clearTimeout(resyncTimer)
  // Back after time away: catch up at once, then again once any last autosave has landed.
  if (reason === 'rejoined') void catchUp()
  resyncTimer = setTimeout(() => void catchUp(), RESYNC_DELAY_MS)
})

const isBusy = computed(
  () => isSaving.value || isSubmitting.value || isReopening.value || isRefreshing.value || Boolean(busySlot.value)
)

const showsSubmittedCopy = computed(() => {
  const submission = detail.value?.submission
  if (!submission?.is_submitted || adminEditing.value) return false
  return submission.is_locked || !canAct.value
})

const CHECKLIST_KEYS = ['supervisor_email', 'btf_logo', 'school_logo', 'team_code', 'page_size']
const posterChecklist = reactive<Record<string, boolean>>({})
/** The ticks the server holds; only changed ticks are sent, so a teammate's ticks are kept. */
let savedChecklist: Record<string, boolean> = {}

/** Takes the checklist from the entry, e.g. after a new poster resets it. */
function syncChecklist() {
  const wasSaved = currentSnapshot() === savedSnapshot.value
  const held = detail.value?.submission?.poster_checklist ?? {}
  CHECKLIST_KEYS.forEach((key) => {
    posterChecklist[key] = Boolean(held[key])
  })
  savedChecklist = { ...posterChecklist }
  if (wasSaved) savedSnapshot.value = currentSnapshot()
}

/** Takes a teammate's ticks, keeping any changed here and not yet saved. */
function mergeChecklist() {
  const wasSaved = currentSnapshot() === savedSnapshot.value
  const held = detail.value?.submission?.poster_checklist ?? {}
  CHECKLIST_KEYS.forEach((key) => {
    if (posterChecklist[key] !== savedChecklist[key]) return
    posterChecklist[key] = Boolean(held[key])
    savedChecklist[key] = posterChecklist[key]
  })
  if (wasSaved) savedSnapshot.value = currentSnapshot()
}

function clearTicks() {
  CHECKLIST_KEYS.forEach((key) => {
    posterChecklist[key] = false
  })
}

function tickChecklist(item: string, ticked: boolean) {
  posterChecklist[item] = ticked
}

function checklistChanges(): Record<string, boolean> {
  const changed: Record<string, boolean> = {}
  CHECKLIST_KEYS.forEach((key) => {
    if (posterChecklist[key] !== savedChecklist[key]) changed[key] = Boolean(posterChecklist[key])
  })
  return changed
}

function shownFile(slot: SubmissionSlot): StoredFile | null {
  const submission = detail.value?.submission
  if (!submission) return null
  return showsSubmittedCopy.value
    ? submission[`submitted_${slot}` as const]
    : submission[slot]
}
// The finalist round has a section of its own on the group page.
const tabs = computed(() => TABS)

function selectTab(key: string) {
  goToStep(tabs.value.findIndex((tab) => tab.key === key))
}

const stepIndex = computed(() => tabs.value.findIndex((tab) => tab.key === activeTab.value))
const isFirstStep = computed(() => stepIndex.value <= 0)
const isLastStep = computed(() => stepIndex.value >= tabs.value.length - 1)

function goToStep(index: number) {
  const target = tabs.value[Math.min(Math.max(index, 0), tabs.value.length - 1)]
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

/** Nothing can be uploaded any more and nothing was, so there is nothing to preview. */
function isPreviewShut(slot: 'poster' | 'report') {
  return !isEditable.value && !storedFile(slot)
}

function isFolded(slot: 'poster' | 'report') {
  return previewCollapsed[slot] || isPreviewShut(slot)
}

function togglePreview(slot: 'poster' | 'report') {
  if (isPreviewShut(slot)) return
  previewCollapsed[slot] = !previewCollapsed[slot]
}

const saveStateLabel = computed(() => {
  if (isSaving.value) return 'Saving…'
  if (saveState.value === 'error') return 'Could not save'
  if (saveState.value === 'unsaved') return 'Unsaved changes'
  if (lastSavedAt.value) return `Saved ${formatDayMonthTime(lastSavedAt.value)}`
  return ''
})

const stage = computed<SubmissionStage>(
  () => detail.value?.submission?.stage ?? 'not_started'
)

const recordedProjectTitle = computed(() => {
  const submission = detail.value?.submission
  return (
    (showsSubmittedCopy.value ? submission?.submitted_project_title : submission?.project_title) ?? ''
  )
})

const CLOSED = 'Submissions are closed.'

/** Full sentences joined with spaces, so no combination can double a full stop. */
function sentences(...parts: string[]): string {
  return parts.filter(Boolean).join(' ')
}

const state = computed(() => {
  const closed = !isOpen.value
  const by = submittedLine.value

  switch (stage.value) {
    case 'submitted':
      return {
        tone: 'submitted',
        icon: 'fa-check',
        headline: 'Submitted',
        detail: closed ? sentences(by && `${by}.`, CLOSED) : by,
      }
    case 'revising':
      return closed
        ? {
            tone: 'submitted',
            icon: 'fa-check',
            headline: 'Submitted',
            detail: sentences(by && `${by}.`, CLOSED, 'Your unfinished revision was not submitted.'),
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
            detail: CLOSED,
          }
        : { tone: 'progress', icon: 'fa-pen', headline: 'Not Started', detail: '' }
  }
})

const submittedLine = computed(() => {
  const submission = detail.value?.submission
  if (!submission?.submitted_at) return ''
  const when = formatDayMonthTime(submission.submitted_at)
  if (submission.auto_submitted) return `Automated Submission on ${when}`
  return submission.submitted_by_name
    ? `By ${submission.submitted_by_name} on ${when}`
    : `On ${when}`
})

const deadlineDate = computed(() => {
  const closesAt = detail.value?.deadline.closes_at
  return closesAt ? formatDayMonthTime(closesAt) : 'No deadline set'
})

const timeRemaining = computed(() =>
  isOpen.value ? describeTimeRemaining(detail.value?.deadline.closes_at, now.value) : ''
)

const isDeadlineNear = computed(
  () => isOpen.value && deadlineIsNear(detail.value?.deadline.closes_at, now.value)
)

// Only explains a missing deadline: a set one shows in the set time.
const deadlineDetail = computed(() =>
  detail.value?.deadline.closes_at
    ? undefined
    : 'An administrator needs to set a deadline before entries can be saved.'
)

const TITLE_STEP_KEY = '__project_title'

function stepSummary(key: string): string {
  if (key === 'questions') {
    return describeQuestionStep(
      { ...answers, [TITLE_STEP_KEY]: projectTitle.value },
      [TITLE_STEP_KEY, ...questions.value.map((q) => q.key)]
    )
  }
  if (key === 'poster') return 'Required'
  return 'Optional'
}

const formatSize = formatFileSize

/** An admin's file changes, held until Save or Submit: a file to upload, or null to remove. */
const pendingFiles = reactive<Partial<Record<SubmissionSlot, File | null>>>({})
const pendingUrls: Partial<Record<SubmissionSlot, string>> = {}

function storedFile(slot: SubmissionSlot): StoredFile | null {
  if (!(slot in pendingFiles)) return shownFile(slot)
  const file = pendingFiles[slot]
  return file ? { storage_key: `pending:${file.name}:${file.size}`, name: file.name, mime: file.type, size: file.size } : null
}

/** A local address for a held file, so it can be opened and previewed before it is saved. */
function pendingUrl(slot: SubmissionSlot): string {
  const file = pendingFiles[slot]
  if (!file || typeof URL.createObjectURL !== 'function') return ''
  const url = pendingUrls[slot] ?? URL.createObjectURL(file)
  pendingUrls[slot] = url
  return url
}

function forgetPendingUrl(slot: SubmissionSlot) {
  const url = pendingUrls[slot]
  if (url && typeof URL.revokeObjectURL === 'function') URL.revokeObjectURL(url)
  delete pendingUrls[slot]
}

function clearPending() {
  FILE_SLOTS.forEach((slot) => {
    forgetPendingUrl(slot)
    delete pendingFiles[slot]
  })
}

function pendingNote(slot: SubmissionSlot): string {
  return pendingFiles[slot] ? ' · not saved yet' : ''
}

function downloadUrl(slot: SubmissionSlot) {
  return pendingFiles[slot] ? pendingUrl(slot) : submissionFileDownloadUrl(groupId.value, slot)
}

function previewUrlFor(slot: SubmissionSlot) {
  return pendingFiles[slot] ? pendingUrl(slot) : submissionFilePreviewUrl(groupId.value, slot)
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

const messageBanner = ref<HTMLElement | null>(null)

/** Shows an upload problem and scrolls the whole platform to the top, where the message sits. */
async function showUploadMessage(text: string) {
  setMessage(text, true)
  await nextTick()
  for (let el = messageBanner.value?.parentElement; el; el = el.parentElement) {
    if (el.scrollTop > 0) el.scrollTo({ top: 0, behavior: 'smooth' })
  }
  window.scrollTo({ top: 0, behavior: 'smooth' })
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
  const titleMissing = !projectTitle.value.trim()
  const posterMissing = !storedFile('poster')

  if (titleMissing || unanswered.length) {
    const focusKey = titleMissing ? 'project-title' : unanswered[0].key
    const problem = unanswered.length
      ? 'Some required questions have not been answered'
      : 'A project title is required'
    return {
      message: posterMissing
        ? `${problem}, and no poster has been uploaded.`
        : unanswered.length
          ? `${problem}.`
          : 'A project title is required before the entry can be submitted.',
      step: 'questions',
      focusKey
    }
  }
  if (posterMissing) {
    return {
      message: 'Please upload your poster before submitting.',
      step: 'poster'
    }
  }
  const unticked = CHECKLIST_KEYS.find((key) => !posterChecklist[key])
  if (unticked) {
    return {
      message: 'Please tick every item in the poster checklist before submitting.',
      step: 'poster',
      focusKey: `checklist-${unticked}`
    }
  }
  return null
}

async function goToBlocker(blocker: { step: TabKey; focusKey?: string }) {
  goToStep(tabs.value.findIndex((tab) => tab.key === blocker.step))
  if (!blocker.focusKey) return
  await nextTick()
  const field = document.getElementById(blocker.focusKey)
  if (!(field instanceof HTMLTextAreaElement || field instanceof HTMLInputElement)) return
  field.focus()
  // jsdom has no layout, so this rejects in tests.
  if (typeof field.scrollIntoView === 'function') {
    field.scrollIntoView({ behavior: 'smooth', block: 'center' })
  }
}

/** Server replies applied here; a background fetch overtaken by one holds an older copy. */
let resultsApplied = 0

function applyResult(result: SubmissionWriteResult) {
  if (!detail.value) return
  detail.value = { ...detail.value, deadline: result.deadline, submission: result.submission }
  resultsApplied += 1
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
  previewSource.value = pendingFiles[slot] ? pendingUrl(slot) : `${previewUrlFor(slot)}?v=${previewVersion(slot)}`
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
  projectTitle.value = recordedProjectTitle.value
  savedTitle = projectTitle.value
  savedLink = prototypeUrl.value
  syncChecklist()
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
  return JSON.stringify({
    answers,
    prototypeUrl: prototypeUrl.value,
    projectTitle: projectTitle.value,
    posterChecklist
  })
}

async function persistDraft() {
  if (isSaving.value) return
  const snapshot = currentSnapshot()

  const sent = changedAnswers()
  const overLimit = overLimitQuestions()

  isSaving.value = true
  try {
    const fields = draftFields(sent)
    applyResult(await saveDraft(groupId.value, fields))
    // Only what this save sent joins the baseline, so a teammate's newer text is kept.
    Object.assign(savedAnswers, sent)
    if (fields.project_title !== undefined) savedTitle = fields.project_title
    if (fields.prototype_url !== undefined) savedLink = fields.prototype_url
    if (fields.poster_checklist) Object.assign(savedChecklist, fields.poster_checklist)
    savedSnapshot.value = snapshot
    lastSavedAt.value = new Date()
    saveState.value = overLimit.length || linkProblem() ? 'unsaved' : 'idle'
  } catch (error) {
    saveState.value = 'error'
    setMessage(handleWriteError(error), true)
  } finally {
    isSaving.value = false
  }
}

function scheduleAutosave() {
  // Admins never autosave: their changes reach the team only on Save or Submit.
  if (adminAccess.value || !canAct.value || isSubmitting.value) return
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

    // Left out of saves too, so submitting would send the last good link.
    if (linkProblem()) {
      linkChecked.value = true
      setMessage('The prototype link needs fixing before the entry can be submitted.', true)
      void goToBlocker({ step: 'extras', focusKey: 'prototype-url' })
      return
    }

    const sent = changedAnswers()
    applyResult(await saveDraft(groupId.value, draftFields(sent)))
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
  if (file) await uploadFile(slot, file)
  // Cleared so choosing the same file again still fires a change.
  input.value = ''
}

const dragSlot = ref<SubmissionSlot | ''>('')
const isDraggingFile = useFileDragging(() => {
  dragSlot.value = ''
})

function onDragOver(slot: SubmissionSlot, event: DragEvent) {
  if (!isEditable.value || busySlot.value) return
  if (event.dataTransfer) event.dataTransfer.dropEffect = 'copy'
  dragSlot.value = slot
}

function onDragLeave(slot: SubmissionSlot, event: DragEvent) {
  // Moving onto a child element of the same slot is not leaving it.
  const next = event.relatedTarget as Node | null
  if (next && (event.currentTarget as HTMLElement).contains(next)) return
  if (dragSlot.value === slot) dragSlot.value = ''
}

function onDrop(slot: SubmissionSlot, event: DragEvent) {
  dragSlot.value = ''
  isDraggingFile.value = false
  const file = event.dataTransfer?.files?.[0]
  if (!file || !isEditable.value || busySlot.value) return
  uploadFile(slot, file)
}

async function uploadFile(slot: SubmissionSlot, file: File) {
  // Checked before uploading; the server enforces it too.
  if (file.size > maxSizeFor(slot)) {
    await showUploadMessage(
      `This file is ${formatSize(file.size)}, over the ${maxSizeLabel(slot)} limit. Please reduce its size and try again.`
    )
    return
  }

  if (adminAccess.value) {
    forgetPendingUrl(slot)
    pendingFiles[slot] = file
    // A new poster is confirmed afresh, as the team's would be.
    if (slot === 'poster') clearTicks()
    if (slot === 'poster' || slot === 'report') await loadPreview(slot)
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
    if (slot === 'poster') syncChecklist()
    // Refresh a showing preview so it never displays the replaced file.
    if (slot === 'poster' || slot === 'report') await loadPreview(slot)
  } catch (error) {
    const problems = apiErrorFromUnknown(error).body?.problems
    await showUploadMessage(Array.isArray(problems) && problems.length ? problems.join(' ') : handleWriteError(error))
  } finally {
    busySlot.value = ''
    uploadPercent.value = 0
  }
}

async function removeFile(slot: SubmissionSlot) {
  if (adminAccess.value) {
    forgetPendingUrl(slot)
    // A held file the team never had is simply dropped; a saved one is marked for removal.
    if (shownFile(slot)) pendingFiles[slot] = null
    else delete pendingFiles[slot]
    if (slot === 'poster') clearTicks()
    if (slot === previewSlot.value) clearPreview()
    return
  }
  busySlot.value = slot
  setMessage('')
  try {
    applyResult(await removeSubmissionFile(groupId.value, slot))
    if (slot === 'poster') syncChecklist()
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

watch([answers, prototypeUrl, projectTitle, posterChecklist], scheduleAutosave, { deep: true })

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
  adminEditing.value = false
  clearPending()
  clearPreview()
  load()
})

const teamName = computed(() => detail.value?.group.name ?? 'this team')

/** The entry's state in a few words, for the admin bar. */
const adminEntry = computed(() => {
  const submission = detail.value?.submission
  const when = submission?.submitted_at ? formatDayMonthTime(submission.submitted_at) : ''
  switch (stage.value) {
    case 'submitted':
      return `${submission?.auto_submitted ? 'Auto-submitted' : 'Submitted'} ${when}${
        hasUnsubmittedChanges() ? ' · changes not submitted' : ''
      }`
    case 'revising':
      return 'Reopened'
    case 'in_progress':
      return 'Draft'
    default:
      return 'Not started'
  }
})

/** A submitted entry whose working copy differs: changes an admin saved but has not submitted. */
function hasUnsubmittedChanges(): boolean {
  const entry = detail.value?.submission
  if (!entry?.is_locked) return false
  const sameAnswers = questions.value.every(
    ({ key }) => (entry.answers?.[key] ?? '') === (entry.submitted_answers?.[key] ?? '')
  )
  const sameFiles = FILE_SLOTS.every(
    (slot) => (entry[slot]?.storage_key ?? '') === (entry[`submitted_${slot}` as const]?.storage_key ?? '')
  )
  return !(
    sameAnswers &&
    sameFiles &&
    entry.project_title === entry.submitted_project_title &&
    entry.prototype_url === entry.submitted_prototype_url
  )
}

/** Whether the team can still edit; past the deadline but open means a grace period or extension. */
const studentsNote = computed(() => {
  const closesAt = detail.value?.deadline.closes_at
  if (!closesAt) return 'No deadline'
  if (!isOpen.value) return 'Closed'
  return now.value < new Date(closesAt).getTime() ? `Open until ${deadlineDate.value}` : 'Grace period'
})

const adminDirty = computed(
  () => adminEditing.value && (currentSnapshot() !== savedSnapshot.value || Object.keys(pendingFiles).length > 0)
)

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

/** The entry as the server now holds it; the copy loaded earlier misses the team's saves since. */
async function reloadDetail() {
  isRefreshing.value = true
  try {
    detail.value = await fetchSubmission(groupId.value)
    resultsApplied += 1
  } catch {
    // Kept as it was; the next save or refresh reports any problem.
  } finally {
    isRefreshing.value = false
  }
}

async function startAdminEdit() {
  await reloadDetail()
  rememberEditStart()
  adminEditing.value = true
  // A submitted entry is edited from its working copy, which the team does not see.
  syncFromDetail()
  await syncPreviewForTab()
}

async function leaveAdminEdit() {
  adminEditing.value = false
  clearPending()
  await reloadDetail()
  syncFromDetail()
  await syncPreviewForTab()
}

async function adminDiscard() {
  if (!(await askAdmin('Discard your changes?', `Nothing you changed for ${teamName.value} will be kept.`, 'Discard'))) return
  await leaveAdminEdit()
  setMessage('Changes discarded.')
}

/** What would stop a save, shown as a message; the full requirements apply only to Submit. */
function adminBlocked(forSubmit: boolean): boolean {
  const overLimit = overLimitQuestions()
  if (overLimit.length) {
    setMessage(overLimitMessage(overLimit), true)
    void goToBlocker({ step: 'questions', focusKey: overLimit[0].key })
    return true
  }
  if (linkProblem()) {
    linkChecked.value = true
    setMessage('The prototype link needs fixing first.', true)
    void goToBlocker({ step: 'extras', focusKey: 'prototype-url' })
    return true
  }
  const blocker = forSubmit ? submissionBlockers() : null
  if (blocker) {
    setMessage(blocker.message, true)
    void goToBlocker(blocker)
  }
  return Boolean(blocker)
}

/** The files as they stood when the admin chose Edit, to tell whether the team replaced one since. */
let filesAtEditStart: Partial<Record<SubmissionSlot, string>> = {}

function rememberEditStart() {
  const submission = detail.value?.submission
  filesAtEditStart = Object.fromEntries(FILE_SLOTS.map((slot) => [slot, submission?.[slot]?.storage_key ?? '']))
}

/** Parts the admin changed that the team also changed since the admin began. */
function conflictsWith(latest: SubmissionDetail['submission']): number {
  const answerClashes = Object.keys(changedAnswers()).filter(
    (key) => (latest?.answers?.[key] ?? '') !== (savedAnswers[key] ?? '')
  ).length
  const titleClash = projectTitle.value !== savedTitle && (latest?.project_title ?? '') !== savedTitle
  const linkClash = normalisedLink() !== savedLink && (latest?.prototype_url ?? '') !== savedLink
  const fileClashes = FILE_SLOTS.filter(
    (slot) => slot in pendingFiles && (latest?.[slot]?.storage_key ?? '') !== (filesAtEditStart[slot] ?? '')
  ).length
  // A replaced poster's ticks are all the admin's own, so only the file itself can clash.
  const tickClashes = 'poster' in pendingFiles ? 0 : Object.keys(checklistChanges()).filter(
    (key) => Boolean(latest?.poster_checklist?.[key]) !== Boolean(savedChecklist[key])
  ).length
  return answerClashes + fileClashes + tickClashes + (titleClash ? 1 : 0) + (linkClash ? 1 : 0)
}

/**
 * Takes the entry's current state from the server before an admin's Save or Submit, so reopening
 * and the success message follow it, and asks before overwriting the team's edits. The admin's edits stay.
 */
async function readyToWrite(): Promise<boolean> {
  const latest = await fetchSubmission(groupId.value)
  if (!detail.value) return false
  detail.value = { ...detail.value, deadline: latest.deadline, submission: latest.submission }
  resultsApplied += 1
  const conflicts = conflictsWith(latest.submission)
  return (
    !conflicts ||
    askAdmin(
      conflicts === 1 ? 'Overwrite a conflicting change?' : `Overwrite ${conflicts} conflicting changes?`,
      'The team edited some of the same parts while you were editing. Continuing replaces their version of those.',
      'Overwrite'
    )
  )
}

/** Uploads held files, then saves the changed fields, to the team's working copy. */
async function publishAdminChanges() {
  // The server starts a new poster's checklist afresh, so every tick goes with it.
  const posterChanged = 'poster' in pendingFiles
  for (const slot of FILE_SLOTS) {
    if (!(slot in pendingFiles)) continue
    const file = pendingFiles[slot]
    busySlot.value = slot
    uploadPercent.value = 0
    applyResult(
      file
        ? await uploadSubmissionFile(groupId.value, slot, file, (percent) => {
            uploadPercent.value = percent
          })
        : await removeSubmissionFile(groupId.value, slot)
    )
    forgetPendingUrl(slot)
    delete pendingFiles[slot]
  }
  busySlot.value = ''
  const fields = draftFields(changedAnswers())
  if (posterChanged) fields.poster_checklist = { ...posterChecklist }
  applyResult(await saveDraft(groupId.value, fields))
}

async function showAdminError(error: unknown) {
  const problems = apiErrorFromUnknown(error).body?.problems
  await showUploadMessage(Array.isArray(problems) && problems.length ? problems.join(' ') : handleWriteError(error))
}

async function adminSave() {
  if (adminBlocked(false)) return
  isSaving.value = true
  setMessage('')
  try {
    if (!(await readyToWrite())) return
    // Before the deadline the team sees the changes and can resubmit; after it, their submission stays as it is.
    const reopen = isLocked.value && isOpen.value
    if (
      reopen &&
      !(await askAdmin(
        'Reopen for the team?',
        `Saving reopens ${teamName.value}'s entry with your changes. Their submission stands until it's submitted again.`,
        'Reopen'
      ))
    ) {
      return
    }
    if (reopen) applyResult(await reopenEntry(groupId.value))
    const locked = isLocked.value
    await publishAdminChanges()
    await leaveAdminEdit()
    setMessage(
      locked
        ? `Saved. ${teamName.value} still sees their submission until you submit.`
        : `Saved to ${teamName.value}'s draft.`
    )
  } catch (error) {
    await showAdminError(error)
  } finally {
    isSaving.value = false
    busySlot.value = ''
  }
}

async function adminSubmit() {
  if (adminBlocked(true)) return
  isSubmitting.value = true
  setMessage('')
  try {
    if (!(await readyToWrite())) return
    if (
      !(await askAdmin(
        `Submit for ${teamName.value}?`,
        'This becomes their latest submission, and the team is emailed a confirmation.',
        'Submit'
      ))
    ) {
      return
    }
    await publishAdminChanges()
    applyResult(await submitEntry(groupId.value))
    await leaveAdminEdit()
    setMessage(`Submitted for ${teamName.value}.`)
  } catch (error) {
    await showAdminError(error)
  } finally {
    isSubmitting.value = false
    busySlot.value = ''
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

const REFRESH_MIN_GAP_MS = 5000
let lastRefreshAt = 0

/** Picks up an extension or closure made while the page sat open. */
async function refreshDeadline() {
  if (!detail.value || isLoading.value || isBusy.value) return
  if (Date.now() - lastRefreshAt < REFRESH_MIN_GAP_MS) return
  lastRefreshAt = Date.now()
  try {
    const latest = await fetchSubmission(groupId.value)
    if (!detail.value || isBusy.value) return
    const changed =
      latest.deadline.is_open !== detail.value.deadline.is_open ||
      latest.deadline.closes_at !== detail.value.deadline.closes_at
    if (!changed) return
    deadlineRecheckDone = false
    if (!isOpen.value && latest.deadline.is_open && !adminEditing.value) {
      // Nothing was editable while closed, so the whole entry can be reloaded safely.
      detail.value = latest
      syncFromDetail()
      await syncPreviewForTab()
    } else {
      detail.value = { ...detail.value, deadline: latest.deadline }
    }
  } catch {
    // Best effort: a write still reports an authoritative closure.
  }
}

watch(
  () => route.name,
  (name, previous) => {
    if (name === 'group-submission' && previous && previous !== name) refreshDeadline()
  }
)

function onPageVisible() {
  if (document.visibilityState === 'visible' && route.name === 'group-submission') {
    refreshDeadline()
  }
}
window.addEventListener('focus', onPageVisible)
document.addEventListener('visibilitychange', onPageVisible)

onBeforeUnmount(() => {
  removeLeaveGuard()
  window.removeEventListener('beforeunload', warnBeforeUnload)
  clearPending()
  window.removeEventListener('focus', onPageVisible)
  document.removeEventListener('visibilitychange', onPageVisible)
  if (autosaveTimer) clearTimeout(autosaveTimer)
  if (resyncTimer) clearTimeout(resyncTimer)
  clearInterval(clockTimer)
  clearPreview()
})
</script>

<style scoped src="../components/submission/submissionPortal.css"></style>
