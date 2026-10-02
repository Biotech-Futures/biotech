<template>
  <!-- Separate cards, as on the other Management tabs: the title card with
       the results emails' details, one each for marks and certificates, then
       sending the results emails once both are released. -->
  <div class="release-results">
    <section class="card release-results__intro">
      <div class="card-header">
        <h3 class="card-title">Release Results</h3>
      </div>
      <p class="release-results__hint">
        Releasing shows results only to students whose group made a submission.
      </p>
      <h3 class="release-results__section-title">Email Details</h3>
      <p class="release-results__hint">
        The results email to groups links to the feedback survey. Set these before sending.
      </p>
      <p v-if="detailsError" class="release-results__load-error">
        Failed to load the email details. {{ detailsError }}
      </p>
      <template v-else-if="details">
        <div class="release-results__fields">
          <label class="release-results__field release-results__field--wide">
            <span>Feedback Survey Link</span>
            <input v-model="form.survey_url" type="url" placeholder="https://…" />
          </label>
          <label class="release-results__field">
            <span>Survey Closes</span>
            <input
              v-model="form.survey_closes"
              type="date"
              :min="details.today"
              :class="{ 'is-invalid': saveTried && closesPast }"
            />
          </label>
        </div>
        <p v-if="saveTried && closesPast" class="release-results__field-error" role="alert">
          Survey Closes can't be before today.
        </p>
        <!-- Save, then the group preview and the supervisor preview each on
             a line of its own, with its test send beside it. -->
        <div class="release-results__details-actions">
          <button
            type="button"
            class="btn btn-primary btn-sm"
            :disabled="savingDetails"
            @click="saveDetails"
          >
            {{ savingDetails ? 'Saving…' : 'Save' }}
          </button>
          <div class="release-results__actions">
            <button
              type="button"
              class="btn btn-outline btn-sm"
              :disabled="loadingPreview !== false"
              @click="openPreview('groups')"
            >
              {{ loadingPreview === 'groups' ? 'Loading…' : 'Preview Group Email' }}
            </button>
            <TestEmailSender v-model:recipient="testRecipients.groups" kind="results-groups" :fields="formFields" />
          </div>
          <div class="release-results__actions">
            <button
              type="button"
              class="btn btn-outline btn-sm"
              :disabled="loadingPreview !== false"
              @click="openPreview('supervisors')"
            >
              {{ loadingPreview === 'supervisors' ? 'Loading…' : 'Preview Supervisor Email' }}
            </button>
            <TestEmailSender v-model:recipient="testRecipients.supervisors" kind="results-supervisors" />
          </div>
          <!-- What the supervisor email's marks spreadsheet looks like: with
               made-up groups, or a chosen supervisor's real one. -->
          <div class="release-results__actions">
            <button
              type="button"
              class="btn btn-outline btn-sm"
              :disabled="downloadingSample"
              @click="downloadSample"
            >
              {{ downloadingSample ? 'Downloading…' : 'Download Sample Marks Spreadsheet' }}
            </button>
            <div class="release-results__supervisor-sheet">
              <button
                type="button"
                class="btn btn-outline btn-sm"
                :disabled="downloadingSheet || !sheetSupervisor"
                @click="downloadSheet"
              >
                {{ downloadingSheet ? 'Downloading…' : 'Download Supervisor Marks' }}
              </button>
              <select
                v-model="sheetSupervisor"
                class="release-results__supervisor-select"
                aria-label="Supervisor"
                :disabled="!sheetSupervisors.length"
              >
                <option v-if="!sheetSupervisors.length" value="">Nobody yet</option>
                <option v-for="option in sheetSupervisors" :key="option.value" :value="option.value">
                  {{ option.label }}
                </option>
              </select>
            </div>
          </div>
        </div>
      </template>
    </section>

    <ReleasePage @changed="loadDetails" />
    <ReleaseCertificatesPage @changed="loadDetails" />

    <section class="card release-results__send">
      <h3 class="release-results__section-title">Send Results Emails</h3>
      <p class="release-results__hint">
        Emails every group that submitted, and its students' supervisors, that their results
        are out. Each is emailed once.
      </p>
      <p class="release-results__hint">
        Group emails go to the group's students and mentors with every certificate in the group
        attached, so students get each other's and their mentor's certificates. Anyone in multiple
        groups gets multiple emails, one for each group.
      </p>
      <template v-if="details">
        <p
          v-if="totalDue"
          class="release-results__status"
          :class="allEmailed ? 'release-results__status--ok' : 'release-results__status--warn'"
        >
          <i
            :class="allEmailed ? 'fas fa-envelope-circle-check' : 'fas fa-envelope'"
            aria-hidden="true"
          ></i>
          {{
            allEmailed
              ? 'Emails are sent to every group and supervisor'
              : 'Emails are not sent to every group and supervisor'
          }}
        </p>
        <p class="release-results__counts">
          Groups: {{ details.groups.emailed }} of {{ details.groups.total }} emailed ·
          Supervisors: {{ details.supervisors.emailed }} of {{ details.supervisors.total }} emailed
        </p>
        <p v-for="reason in blockedReasons" :key="reason" class="release-results__blocked">
          {{ reason }}
        </p>
        <div class="release-results__actions">
          <button
            v-for="audience in AUDIENCES"
            :key="audience.value"
            type="button"
            class="btn btn-primary btn-sm"
            :disabled="starting !== null || !canSend[audience.value]"
            @click="confirming = audience.value"
          >
            {{ starting === audience.value ? 'Sending…' : `Email ${audience.noun}` }}
          </button>
          <template v-for="audience in AUDIENCES" :key="`progress-${audience.value}`">
            <span
              v-if="runOf(audience.value).sending && runOf(audience.value).run"
              class="release-results__progress"
              role="status"
            >
              Emailed {{ runOf(audience.value).run!.emailed }} of
              {{ audience.value === 'groups'
                ? plural(runOf(audience.value).run!.due, 'person', 'people')
                : plural(runOf(audience.value).run!.due, 'supervisor') }}
              so far…
            </span>
            <span v-if="runOf(audience.value).queued" class="release-results__queued" role="status">
              {{ audience.noun }}: {{ queuedNote(runOf(audience.value).queued, runOf(audience.value).ahead) }}
            </span>
          </template>
        </div>
        <template v-for="audience in AUDIENCES" :key="`missed-${audience.value}`">
          <div
            v-if="runOf(audience.value).run?.missed.length"
            class="release-results__missed"
            :data-testid="`missed-${audience.value}`"
          >
            <p class="release-results__missed-title">
              {{ audience.value === 'groups' ? "The group email couldn't reach:" : "The supervisor email couldn't reach:" }}
            </p>
            <ul>
              <li v-for="(m, i) in runOf(audience.value).run!.missed" :key="i">
                {{ m.who }}<span v-if="m.reason" class="release-results__missed-reason"> · {{ m.reason }}</span>
              </li>
            </ul>
          </div>
        </template>
      </template>
    </section>

    <p v-if="actionError" class="release-results__banner release-results__banner--error">
      {{ actionError }}
    </p>
    <p v-if="actionMessage" class="release-results__banner release-results__banner--ok">
      {{ actionMessage }}
    </p>
  </div>

  <Teleport to="body">
    <div v-if="confirming" class="release-results__overlay" @click.self="confirming = null">
      <div class="release-results__dialog" role="dialog" aria-modal="true" aria-label="Send results emails">
        <h3 class="release-results__dialog-title">
          <i class="fas fa-envelope" aria-hidden="true"></i> Email {{ confirming }}?
        </h3>
        <p class="release-results__dialog-text">{{ confirmText }}</p>
        <div class="release-results__dialog-actions">
          <button type="button" class="btn btn-outline btn-sm" @click="confirming = null">
            Cancel
          </button>
          <button type="button" class="btn btn-primary btn-sm" @click="sendAll(confirming)">Send</button>
        </div>
      </div>
    </div>
  </Teleport>

  <Teleport to="body">
    <div v-if="preview" class="release-results__overlay" @click.self="preview = null">
      <div
        class="release-results__dialog release-results__dialog--preview"
        role="dialog"
        aria-modal="true"
        aria-label="Email preview"
      >
        <h3 class="release-results__dialog-title">
          <i class="fas fa-envelope-open-text" aria-hidden="true"></i> {{ preview.subject }}
        </h3>
        <p class="release-results__dialog-text">
          As {{ preview.to }} would get it. Nothing has been sent.
        </p>
        <div v-if="preview.attachments.length" class="release-results__attachments">
          <span class="release-results__attachments-label">
            <i class="fas fa-paperclip" aria-hidden="true"></i> Attachments
          </span>
          <ul>
            <li v-for="name in preview.attachments" :key="name">{{ name }}</li>
          </ul>
        </div>
        <!-- As on Notify Finalists: the frame is as tall as the email and this
             box scrolls; sandbox without allow-scripts shows the email, never
             runs it; allow-same-origin only lets fitPreview measure it. -->
        <div class="release-results__preview-body">
          <iframe
            class="release-results__preview-frame"
            :srcdoc="preview.html"
            title="Email preview"
            sandbox="allow-same-origin"
            scrolling="no"
            @load="fitPreview"
          ></iframe>
        </div>
        <div class="release-results__dialog-actions">
          <button type="button" class="btn btn-outline btn-sm" @click="preview = null">Close</button>
        </div>
      </div>
    </div>
  </Teleport>
</template>

<script setup lang="ts">
import { computed, onMounted, ref } from 'vue'
import { useEmailPreview } from '@/composables/useEmailPreview'
import { describeRun, isBusy, queuedMessage, queuedNote, RUN_MESSAGE_MS, useEmailRun } from '@/composables/useEmailRun'
import { useFlashMessage } from '@/composables/useFlashMessage'
import {
  downloadResultsSampleSheet,
  downloadSupervisorMarksSheet,
  fetchResultsEmailDetails,
  fetchTestEmailRecipients,
  previewResultsEmail,
  startResultsEmail,
  updateResultsEmailDetails,
  type EmailRun,
  type ResultsAudience,
  type ResultsEmailDetails,
  type ResultsEmailFields,
  type TestEmailRecipient
} from '@/utils/managementAPI'
import { apiErrorFromUnknown } from '@/utils/apiError'
import { plural } from '@/utils/string'
import ReleaseCertificatesPage from '@/views/management/ReleaseCertificatesPage.vue'
import ReleasePage from '@/views/management/ReleasePage.vue'
import TestEmailSender from '@/views/management/TestEmailSender.vue'

// Groups (their students and mentors) and supervisors are emailed apart.
const AUDIENCES: { value: ResultsAudience; noun: string }[] = [
  { value: 'groups', noun: 'Groups' },
  { value: 'supervisors', noun: 'Supervisors' }
]

const actionError = ref('')
const { message: actionMessage, show: flashAction } = useFlashMessage()

// -- Email details ----------------------------------------------------------

const details = ref<ResultsEmailDetails | null>(null)
const detailsError = ref('')
const form = ref<ResultsEmailFields>({ survey_url: '', survey_closes: null })
const savingDetails = ref(false)
// A past close date is only pointed out once Save is pressed, as on Notify Finalists.
const saveTried = ref(false)

const fromDetails = (d: ResultsEmailDetails): ResultsEmailFields => ({
  survey_url: d.survey_url ?? '',
  survey_closes: d.survey_closes
})

const formFields = (): ResultsEmailFields => ({
  survey_url: form.value.survey_url.trim(),
  survey_closes: form.value.survey_closes || null
})

const detailsChanged = computed(() => {
  const d = details.value
  if (!d) return false
  const f = formFields()
  return f.survey_url !== (d.survey_url ?? '') || f.survey_closes !== d.survey_closes
})

const closesPast = computed(() =>
  Boolean(form.value.survey_closes && details.value && form.value.survey_closes < details.value.today)
)

// Also called when marks or certificates are (un)released below; edits in
// progress are kept.
const loadDetails = async () => {
  detailsError.value = ''
  try {
    const editing = detailsChanged.value
    const fresh = await fetchResultsEmailDetails()
    details.value = fresh
    if (!editing) form.value = fromDetails(fresh)
  } catch (err) {
    detailsError.value = apiErrorFromUnknown(err).message
  }
}

const saveDetails = async () => {
  actionError.value = ''
  saveTried.value = true
  if (closesPast.value) return
  savingDetails.value = true
  try {
    const saved = await updateResultsEmailDetails(formFields())
    details.value = saved
    form.value = fromDetails(saved)
    saveTried.value = false
    flashAction('Email details saved.')
  } catch (err) {
    actionError.value = apiErrorFromUnknown(err).message
  } finally {
    savingDetails.value = false
  }
}

// -- Preview ----------------------------------------------------------------

// The person picked in each Send Test Email: the preview is their email.
const testRecipients = ref<Record<ResultsAudience, string>>({ groups: '', supervisors: '' })
// Which audience's email is loading its preview.
const { preview, loadingPreview, openPreview, fitPreview } = useEmailPreview(
  (audience: ResultsAudience) => previewResultsEmail(audience, formFields(), testRecipients.value[audience]),
  actionError
)

// -- Sample spreadsheet -----------------------------------------------------

const downloadingSample = ref(false)

const downloadSample = async () => {
  actionError.value = ''
  downloadingSample.value = true
  try {
    await downloadResultsSampleSheet()
  } catch (err) {
    actionError.value = apiErrorFromUnknown(err).message
  } finally {
    downloadingSample.value = false
  }
}

// A supervisor's real marks spreadsheet, from the supervisors due the email.
const sheetSupervisors = ref<TestEmailRecipient[]>([])
const sheetSupervisor = ref('')
const downloadingSheet = ref(false)

const loadSheetSupervisors = async () => {
  try {
    sheetSupervisors.value = (await fetchTestEmailRecipients('results-supervisors')).recipients
    sheetSupervisor.value = sheetSupervisors.value[0]?.value ?? ''
  } catch {
    sheetSupervisors.value = []
  }
}

const downloadSheet = async () => {
  actionError.value = ''
  downloadingSheet.value = true
  try {
    await downloadSupervisorMarksSheet(sheetSupervisor.value)
  } catch (err) {
    actionError.value = apiErrorFromUnknown(err).message
  } finally {
    downloadingSheet.value = false
  }
}

// -- Sending ----------------------------------------------------------------

const pending = (audience: ResultsAudience) => {
  const count = details.value?.[audience]
  return count ? count.total - count.emailed : 0
}

const totalDue = computed(() =>
  details.value ? details.value.groups.total + details.value.supervisors.total : 0
)
const allEmailed = computed(
  () => totalDue.value > 0 && pending('groups') === 0 && pending('supervisors') === 0
)

// Why each button is off, if it is. Releasing is shared; only the group
// email carries the survey, so only it waits for those details.
const releaseReason = computed(() => {
  if (detailsError.value) return 'The email details could not be loaded.'
  const d = details.value
  if (d && (!d.marks_released || !d.certificates_released)) {
    return 'Release both marks and certificates before sending the results emails.'
  }
  // Releasing waits for this too, but an extension granted since would not.
  if (d?.submissions_open) return d.submissions_open
  return ''
})

const audienceReason = (audience: ResultsAudience) => {
  const d = details.value
  if (!d || releaseReason.value) return ''
  if (!d.emails_on[audience]) {
    return `Results: ${audience} is switched off on System Emails.`
  }
  if (!d.templates_ready[audience]) {
    return audience === 'groups'
      ? 'Upload the marks summary, student certificate and mentor certificate templates in Document Setup before emailing groups.'
      : 'Upload the student certificate and mentor certificate templates in Document Setup before emailing supervisors.'
  }
  if (audience === 'groups') {
    if (detailsChanged.value) return 'Save the email details before emailing groups.'
    if (!d.complete) return 'Set the feedback survey link and close date above before emailing groups.'
    if (d.closes_in_past) {
      return 'The survey close date is before today. Update and save it before emailing groups.'
    }
  }
  return ''
}

const blockedReasons = computed(() =>
  [releaseReason.value, audienceReason('groups'), audienceReason('supervisors')].filter(Boolean)
)

// Each email's run: whether it's sending now, and its progress.
const runOf = (audience: ResultsAudience) =>
  details.value?.runs[audience] ?? { sending: false, queued: 0, ahead: [], run: null }

const canSend = computed(() => {
  const can = (audience: ResultsAudience) =>
    details.value !== null &&
    !releaseReason.value &&
    !audienceReason(audience) &&
    pending(audience) > 0
  return { groups: can('groups'), supervisors: can('supervisors') }
})

const confirming = ref<ResultsAudience | null>(null)
const confirmText = computed(() => {
  const audience = confirming.value
  if (!audience) return ''
  const due = pending(audience)
  if (audience === 'groups') {
    return `This emails the students and mentors of the ${plural(due, 'group')} that ${due === 1 ? "hasn't" : "haven't"} had their results email yet.`
  }
  return `This emails the ${plural(due, 'supervisor')} who haven't had their results email yet.`
})

// The Send request itself; the run then sends on the server.
const starting = ref<ResultsAudience | null>(null)

const sendAll = async (audience: ResultsAudience) => {
  confirming.value = null
  actionError.value = ''
  starting.value = audience
  try {
    details.value = await startResultsEmail(audience)
    // A run with little or nothing to send can be over by the reply.
    const state = details.value.runs[audience]
    if (state.queued) flashAction(queuedMessage(state.ahead))
    else if (!isBusy(state) && state.run) reportRun(audience, state.run)
  } catch (err) {
    actionError.value = apiErrorFromUnknown(err).message
  } finally {
    starting.value = null
  }
}

// How a run went, once this page saw it finish.
const reportRun = (audience: ResultsAudience, run: EmailRun) => {
  const sentFrom = details.value?.runs[audience].sent_from
  const { text, isError } = describeRun(
    run,
    audience === 'groups'
      ? { emailed: ['person', 'people'], failed: 'group', button: 'Email Groups', sentFrom }
      : { emailed: ['supervisor'], failed: 'supervisor', failedWhole: true, button: 'Email Supervisors', sentFrom }
  )
  if (isError) actionError.value = text
  else flashAction(text, RUN_MESSAGE_MS)
}
for (const audience of ['groups', 'supervisors'] as const) {
  useEmailRun(() => details.value?.runs[audience], loadDetails, (run) => reportRun(audience, run))
}

onMounted(() => Promise.all([loadDetails(), loadSheetSupervisors()]))
</script>

<style scoped>
.release-results {
  display: flex;
  flex-direction: column;
  gap: 1rem;
}

/* The flex gap and margins below space the parts; the header's own margin
   would double it. */
.release-results__intro .card-header {
  margin-bottom: 0.75rem;
}

.release-results__hint {
  color: var(--text-muted);
  font-size: 0.9rem;
  margin: 0 0 0.75rem;
}

/* As "Email Details" on Notify Finalists. */
.release-results__section-title {
  font-size: 1.05rem;
  font-weight: 600;
  margin-bottom: 0.75rem;
}

.release-results__load-error {
  margin: 0 0 0.5rem;
}

.release-results__fields {
  display: grid;
  grid-template-columns: repeat(auto-fit, minmax(12rem, 1fr));
  gap: 0.85rem 1rem;
  margin-bottom: 1rem;
  align-items: start;
}

.release-results__field {
  display: grid;
  gap: 0.3rem;
  font-size: 0.9rem;
}

.release-results__field > span {
  color: var(--text-muted);
}

.release-results__field input {
  border: 1px solid var(--border-light);
  border-radius: 6px;
  padding: 0.45rem 0.6rem;
  font-size: 0.9rem;
  font-family: inherit;
  background: var(--surface-elevated);
  color: var(--charcoal);
}

.release-results__field input:focus {
  outline: none;
  border-color: var(--dark-green);
}

.release-results__field input.is-invalid {
  border-color: var(--danger);
}

.release-results__field--wide {
  grid-column: 1 / -1;
}

.release-results__field-error {
  color: var(--danger);
  font-size: 0.85rem;
  margin: 0 0 0.75rem;
}

.release-results__actions {
  display: flex;
  flex-wrap: wrap;
  align-items: center;
  gap: 0.75rem 1.25rem;
}

/* The button and its dropdown stay together when the line wraps. */
.release-results__supervisor-sheet {
  display: flex;
  align-items: center;
  gap: 0.5rem;
}

.release-results__supervisor-select {
  border: 1px solid var(--border-light);
  border-radius: 6px;
  padding: 0.3rem 0.5rem;
  font-size: 0.85rem;
  font-family: inherit;
  background: var(--surface-elevated);
  color: var(--charcoal);
  max-width: 14rem;
}

/* Each button as wide as its label. */
.release-results__details-actions {
  display: flex;
  flex-direction: column;
  align-items: flex-start;
  gap: 0.5rem;
}

/* As the Release Marks status line. */
.release-results__status {
  font-weight: 600;
  font-size: 0.9rem;
  margin: 0 0 0.75rem;
}

.release-results__status--ok {
  color: var(--dark-green);
}

.release-results__status--warn {
  color: #eab308;
}

/* The size of the hint lines. */
.release-results__counts {
  color: var(--text-muted);
  font-size: 0.9rem;
  margin: 0 0 0.75rem;
}

.release-results__blocked {
  color: #b8860b;
  font-size: 0.85rem;
  margin: 0 0 0.75rem;
}

.release-results__progress {
  color: var(--text-muted);
  font-size: 0.85rem;
}

/* Who the last run couldn't reach, under the buttons. */
.release-results__missed {
  margin-top: 0.75rem;
  font-size: 0.85rem;
}

/* What a queued send waits behind: the colour of Couldn't be emailed. */
.release-results__queued {
  color: var(--danger);
  font-size: 0.85rem;
}

.release-results__missed-title {
  margin: 0 0 0.25rem;
  font-weight: 600;
  color: var(--danger);
}

.release-results__missed ul {
  margin: 0;
  padding-left: 1.2rem;
}

.release-results__missed-reason {
  color: var(--text-muted);
}

.release-results__banner {
  border-radius: 6px;
  padding: 0.5rem 0.75rem;
  font-size: 0.9rem;
  margin: 0;
}

.release-results__banner--error {
  background: color-mix(in srgb, var(--danger) 12%, transparent);
  color: var(--danger);
}

.release-results__banner--ok {
  background: var(--accent-green-soft);
  color: var(--dark-green);
}

/* Dialogs as on Notify Finalists and the release confirmations. */
.release-results__overlay {
  position: fixed;
  inset: 0;
  background: rgba(0, 0, 0, 0.45);
  display: flex;
  align-items: center;
  justify-content: center;
  padding: 1rem;
  z-index: 2000;
}

.release-results__dialog {
  background: var(--surface-elevated);
  color: var(--charcoal);
  border-radius: 10px;
  box-shadow: 0 10px 40px var(--shadow);
  width: 100%;
  max-width: 26rem;
  padding: 1.25rem;
  display: flex;
  flex-direction: column;
  gap: 0.75rem;
}

.release-results__dialog.release-results__dialog--preview {
  max-width: 44rem;
  max-height: calc(100vh - 2rem);
}

.release-results__dialog-title {
  display: flex;
  align-items: center;
  gap: 0.5rem;
  font-size: 1.15rem;
  margin: 0;
}

.release-results__dialog-title i {
  color: var(--dark-green);
}

.release-results__dialog-text {
  color: var(--text-muted);
  font-size: 0.92rem;
  margin: 0;
}

.release-results__dialog-actions {
  display: flex;
  justify-content: flex-end;
  gap: 0.5rem;
}

/* The files the previewed email carries, as a mail client lists them. */
.release-results__attachments {
  display: flex;
  flex-wrap: wrap;
  align-items: baseline;
  gap: 0.4rem 0.75rem;
  font-size: 0.85rem;
}

.release-results__attachments-label {
  color: var(--text-muted);
  font-weight: 600;
}

.release-results__attachments ul {
  display: flex;
  flex-wrap: wrap;
  gap: 0.35rem;
  list-style: none;
  margin: 0;
  padding: 0;
}

.release-results__attachments li {
  border: 1px solid var(--border-light);
  border-radius: 6px;
  padding: 0.15rem 0.5rem;
  background: var(--bg-light);
}

.release-results__preview-body {
  flex: 1;
  min-height: 0;
  overflow-y: auto;
  overscroll-behavior: contain;
  border: 1px solid var(--border-light);
  border-radius: 8px;
  background: #eef0ee;
}

.release-results__preview-frame {
  display: block;
  width: 100%;
  height: 60vh;
  border: 0;
}
</style>
