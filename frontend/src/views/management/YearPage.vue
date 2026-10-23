<template>
  <div class="year">
    <section class="card">
      <div class="card-header">
        <h3 class="card-title">Current Year</h3>
      </div>
      <p class="year__value">{{ newYear?.year ?? '' }}</p>
      <p class="year__hint">
        The competition year currently in progress. Once this year's competition wraps
        up, use Prepare New Year below to roll the platform over.
      </p>
      <p v-if="newYear?.started" class="year__hint" data-test="year-started">
        Started {{ formatStatementTime(newYear.started.started_at) }}
        <template v-if="newYear.started.started_by">by {{ newYear.started.started_by }}</template>.
      </p>

      <ul class="year__facts">
        <li>
          <span class="year__fact-label">Registration Start</span>
          <span v-if="registration?.opens_at">{{ formatStatementTime(registration.opens_at) }}</span>
          <span v-else class="year__muted">not set</span>
        </li>
        <li>
          <span class="year__fact-label">Registration Close</span>
          <span v-if="registration?.closes_at">{{ formatStatementTime(registration.closes_at) }}</span>
          <span v-else class="year__muted">not set</span>
        </li>
        <li>
          <span class="year__fact-label">Challenge Start</span>
          <span v-if="challengeStart">{{ formatStatementTime(challengeStart) }}</span>
          <span v-else class="year__muted">not set</span>
        </li>
        <li>
          <span class="year__fact-label">Submission Deadline</span>
          <span v-if="deadline">{{ formatStatementTime(deadline.closes_at) }}</span>
          <span v-else class="year__muted">not set</span>
        </li>
        <li>
          <span class="year__fact-label">Last Extension</span>
          <span v-if="lastExtension">{{ formatStatementTime(lastExtension) }}</span>
          <span v-else class="year__muted">none granted</span>
        </li>
        <li>
          <span class="year__fact-label">Marks</span>
          <span :class="marksReleased ? 'year__ok' : 'year__muted'">
            {{ marksReleased ? 'released' : 'not released' }}
          </span>
        </li>
        <li>
          <span class="year__fact-label">Notify Finalists</span>
          <span v-if="finalists.length" :class="allNotified ? 'year__ok' : 'year__muted'">
            {{ notifiedCount }} of {{ finalists.length }} notified
          </span>
          <span v-else class="year__muted">no finalists</span>
        </li>
        <li>
          <span class="year__fact-label">Symposium Date</span>
          <span v-if="symposiumDate">{{ dayText(symposiumDate) }}</span>
          <span v-else class="year__muted">not set</span>
        </li>
        <li>
          <span class="year__fact-label">Certificates</span>
          <span :class="certsReleased ? 'year__ok' : 'year__muted'">
            {{ certsReleased ? 'released' : 'not released' }}
          </span>
        </li>
      </ul>
    </section>

    <section class="card">
      <div class="card-header">
        <h3 class="card-title">Prepare New Year</h3>
      </div>
      <div v-for="group in steps" :key="group.title" class="year__group">
        <h4 class="year__group-title">{{ group.title }}</h4>
        <ul class="year__steps">
          <li v-for="step in group.steps" :key="step">{{ step }}</li>
        </ul>
      </div>
      <p class="year__hint">
        It can be started from 1 September, once submissions have closed and no email is
        sending. If an email is sending, it waits for it to finish first. Nothing is deleted.
        What's archived stays on record.
      </p>

      <ul v-if="newYear?.blockers.length" class="year__notes year__notes--blocker" data-test="year-blockers">
        <li v-for="reason in newYear.blockers" :key="reason">
          <i class="fas fa-circle-xmark" aria-hidden="true"></i> {{ reason }}
        </li>
      </ul>
      <ul v-if="newYear?.warnings.length" class="year__notes year__notes--warning" data-test="year-warnings">
        <li v-for="note in newYear.warnings" :key="note">
          <i class="fas fa-triangle-exclamation" aria-hidden="true"></i> {{ note }}
        </li>
      </ul>
      <p v-if="error" class="year__error" role="alert">{{ error }}</p>
      <div v-if="summary.length" class="year__done" role="status" data-test="year-done">
        <p class="year__done-title">{{ newYear?.year }} has started.</p>
        <ul>
          <li v-for="line in summary" :key="line">{{ line }}</li>
        </ul>
      </div>

      <button
        type="button"
        class="btn btn-outline btn-sm"
        :disabled="!canStart"
        data-test="start-new-year"
        @click="openConfirm"
      >
        Start new year <i class="fas fa-rotate" aria-hidden="true"></i>
      </button>
    </section>

    <ConfirmDialog
      v-model="confirmOpen"
      :title="`Start ${newYear?.next_year ?? 'the new year'}?`"
      message="Every student, mentor and supervisor is signed out and deactivated, and this year's groups, events and announcements are archived. This can't be undone from here."
      confirm-label="Start new year"
      busy-label="Starting..."
      variant="danger"
      :busy="starting"
      :disabled="typed.trim() !== String(newYear?.next_year)"
      @confirm="start"
    >
      <div class="year__type">
        <label class="table-filter-label" for="new-year-confirm">
          Type <span class="year__keyword">{{ newYear?.next_year }}</span> to confirm
        </label>
        <input
          id="new-year-confirm"
          v-model="typed"
          class="form-input app-input"
          autocomplete="off"
          inputmode="numeric"
          :placeholder="String(newYear?.next_year ?? '')"
        />
      </div>
    </ConfirmDialog>
  </div>
</template>

<script setup lang="ts">
import { computed, onMounted, onUnmounted, ref } from 'vue'
import ConfirmDialog from '@/components/admin/ConfirmDialog.vue'
import { apiErrorFromUnknown } from '@/utils/apiError'
import { formatStatementTime } from '@/utils/date'
import { fetchFinalists, type FinalistRow } from '@/utils/gradingAPI'
import {
  fetchCertificatesRelease,
  fetchChallengeStart,
  fetchFinalistEmailDetails,
  fetchGroupExtensions,
  fetchNewYear,
  fetchRegistrationOpen,
  fetchRelease,
  fetchSubmissionDeadline,
  startNewYear,
  type GroupExtension,
  type NewYearState,
  type RegistrationState,
  type ReleaseStatus,
  type SubmissionDeadline
} from '@/utils/managementAPI'

const deadline = ref<SubmissionDeadline | null>(null)
const marks = ref<ReleaseStatus | null>(null)
const certs = ref<ReleaseStatus | null>(null)
const extensions = ref<GroupExtension[]>([])
const finalists = ref<FinalistRow[]>([])
const registration = ref<RegistrationState | null>(null)
// Days alone, as "2026-07-27": Challenge Start's, and Notify Finalists' Symposium.
const challengeStart = ref<string | null>(null)
const symposiumDate = ref<string | null>(null)

// What Start new year does, by area, and what it leaves as it is.
const steps: { title: string; steps: string[] }[] = [
  {
    title: 'People and Groups',
    steps: [
      'Deactivates all student, mentor and supervisor accounts and signs them out. Admins stay active. Accounts are reactivated only by registering again.',
      'Archives all groups. Groups start with the new year and new groups start again from BTF01.',
      'The 3 Guardian tables show only students registered or reactivated in the new challenge year.'
    ]
  },
  {
    title: 'Group Work and Content',
    steps: [
      'Archives all group and individual tasks, chats and submissions.',
      'Archives all events and announcements, and hides all resources.'
    ]
  },
  {
    title: 'Management',
    steps: [
      'Archives all role tasks.',
      'Resets the sent progress of every email.',
      'Clears these dates: Registration Start and End, Challenge Start, Pages Visibility, Submission Deadline, Symposium (with Confirm Attendance and Slides Due) and Results (Survey Closes).',
      "Archives late registration links, extensions, slot allocations, marks and certificates. Resets each supervisor's late registration permission and resource visibility.",
      'Clears the Symposium registration link and the feedback survey link.'
    ]
  },
  {
    title: 'Stays',
    steps: ['Presentation Times, marking rubrics, Document Setup and the Known Universities list.']
  }
]

/** "27/07/2026", as the deadlines read without their time. */
const dayText = (value: string) => value.split('-').reverse().join('/')

const marksReleased = computed(() => marks.value?.released_at != null)
const certsReleased = computed(() => certs.value?.released_at != null)

const notifiedCount = computed(() => finalists.value.filter((f) => f.notified).length)
const allNotified = computed(
  () => finalists.value.length > 0 && notifiedCount.value === finalists.value.length
)

// The furthest granted extension — the real end of this year's window.
const lastExtension = computed(() => {
  if (!extensions.value.length) return null
  const sorted = extensions.value
    .map((e) => e.extended_until)
    .sort((a, b) => new Date(a).getTime() - new Date(b).getTime())
  return sorted[sorted.length - 1]
})

// The year in progress, the next, and what stops it starting now.
const newYear = ref<NewYearState | null>(null)
const confirmOpen = ref(false)
const typed = ref('')
const starting = ref(false)
const error = ref('')
// What the press just changed, a line each.
const summary = ref<string[]>([])

const canStart = computed(() => !!newYear.value && !newYear.value.blockers.length && !starting.value)

/** "412 accounts deactivated", from what Start new year counted. */
const COUNTED: [key: string, one: string, many: string][] = [
  ['accounts', 'account deactivated and signed out', 'accounts deactivated and signed out'],
  ['groups', 'group archived', 'groups archived'],
  ['tasks', 'task archived', 'tasks archived'],
  ['role_tasks', 'role task archived', 'role tasks archived'],
  ['events', 'event archived', 'events archived'],
  ['announcements', 'announcement archived', 'announcements archived'],
  ['resources', 'resource hidden', 'resources hidden'],
  ['extensions', 'extension revoked', 'extensions revoked'],
  ['late_links', 'late registration link revoked', 'late registration links revoked']
]

const summaryOf = (counts: Record<string, number>) =>
  COUNTED.map(([key, one, many]) => {
    const n = counts[key] ?? 0
    return `${n} ${n === 1 ? one : many}`
  })

function openConfirm() {
  typed.value = ''
  error.value = ''
  confirmOpen.value = true
}

async function start() {
  starting.value = true
  error.value = ''
  try {
    newYear.value = await startNewYear(typed.value)
    summary.value = summaryOf(newYear.value.started?.counts ?? {})
    confirmOpen.value = false
    await loadFacts()
  } catch (err) {
    error.value = apiErrorFromUnknown(err, 'The new year could not be started.').message
    confirmOpen.value = false
  } finally {
    starting.value = false
  }
}

// While an email is sending, checked again every so often: the button comes
// on by itself once it has finished.
const RECHECK_MS = 15000
let recheck: ReturnType<typeof setTimeout> | undefined

async function loadYear() {
  clearTimeout(recheck)
  try {
    newYear.value = await fetchNewYear()
  } catch (err) {
    error.value = apiErrorFromUnknown(err, 'The year could not be loaded.').message
    return
  }
  if (newYear.value.sending) recheck = setTimeout(loadYear, RECHECK_MS)
}

onMounted(async () => {
  await loadYear()
  await loadFacts()
})

onUnmounted(() => clearTimeout(recheck))

async function loadFacts() {
  // Best-effort: each block independent so one failure doesn't blank the page.
  try {
    registration.value = await fetchRegistrationOpen()
  } catch {
    registration.value = null
  }
  try {
    challengeStart.value = (await fetchChallengeStart()).starts_at
  } catch {
    challengeStart.value = null
  }
  try {
    symposiumDate.value = (await fetchFinalistEmailDetails()).symposium_date
  } catch {
    symposiumDate.value = null
  }
  try {
    deadline.value = (await fetchSubmissionDeadline()).deadline
  } catch {
    deadline.value = null
  }
  try {
    marks.value = await fetchRelease()
  } catch {
    marks.value = null
  }
  try {
    certs.value = await fetchCertificatesRelease()
  } catch {
    certs.value = null
  }
  try {
    extensions.value = (await fetchGroupExtensions()).extensions
  } catch {
    extensions.value = []
  }
  try {
    finalists.value = (await fetchFinalists()).finalists
  } catch {
    finalists.value = []
  }
}
</script>

<style scoped>
.year {
  display: flex;
  flex-direction: column;
  gap: 1rem;
}

.year__value {
  font-size: 2.4rem;
  font-weight: 700;
  color: var(--dark-green);
  margin: 0 0 0.25rem;
}

.year__hint {
  color: var(--text-muted);
  font-size: 0.9rem;
  margin: 0 0 0.9rem;
}

.year__facts {
  list-style: none;
  margin: 0;
  padding: 0;
  display: flex;
  flex-direction: column;
  gap: 0.4rem;
  font-size: 0.92rem;
}

.year__fact-label {
  display: inline-block;
  min-width: 11rem;
  color: var(--teal);
  font-weight: 600;
}

.year__ok {
  color: var(--dark-green);
  font-weight: 600;
}

.year__muted {
  color: var(--text-muted);
}

.year__group-title {
  margin: 0 0 0.4rem;
  color: var(--teal);
  font-size: 0.95rem;
  font-weight: 600;
}

.year__steps {
  margin: 0 0 1rem;
  padding-left: 1.2rem;
  font-size: 0.92rem;
  color: var(--teal);
  display: flex;
  flex-direction: column;
  gap: 0.35rem;
}

.year__steps a {
  color: var(--dark-green);
}

/* What stops it starting now, and what's worth knowing first. */
.year__notes {
  list-style: none;
  margin: 0 0 0.9rem;
  padding: 0;
  display: flex;
  flex-direction: column;
  gap: 0.35rem;
  font-size: 0.9rem;
}

.year__notes li {
  border-radius: 6px;
  padding: 0.45rem 0.75rem;
}

.year__notes--blocker li {
  background: color-mix(in srgb, var(--danger) 12%, transparent);
}

.year__notes--blocker i {
  color: var(--danger);
}

.year__notes--warning li {
  background: color-mix(in srgb, var(--warning) 16%, transparent);
}

.year__error {
  border-radius: 6px;
  padding: 0.5rem 0.75rem;
  font-size: 0.9rem;
  margin: 0 0 0.9rem;
  background: color-mix(in srgb, var(--danger) 12%, transparent);
}

.year__done {
  border-radius: 6px;
  padding: 0.6rem 0.9rem;
  margin: 0 0 0.9rem;
  font-size: 0.9rem;
  background: color-mix(in srgb, var(--success) 12%, transparent);
}

.year__done-title {
  margin: 0 0 0.3rem;
  font-weight: 600;
  color: var(--dark-green);
}

.year__done ul {
  margin: 0;
  padding-left: 1.2rem;
}

/* The year typed to confirm, on the dialog's own background. */
.year__type {
  display: flex;
  flex-direction: column;
  gap: 0.3rem;
  margin-top: 0.75rem;
}

.year__type input {
  background-color: var(--white);
}

.year__keyword {
  font-family: ui-monospace, SFMono-Regular, Menlo, Consolas, monospace;
  font-weight: 700;
  color: var(--danger);
}

.btn:disabled {
  opacity: 0.55;
  cursor: not-allowed;
}
</style>
