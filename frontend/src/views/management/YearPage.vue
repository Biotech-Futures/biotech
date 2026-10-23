<template>
  <div class="year">
    <section class="card">
      <div class="card-header">
        <h3 class="card-title">Current Year</h3>
      </div>
      <p class="year__value">{{ currentYear }}</p>
      <p class="year__hint">
        The competition year currently in progress. Once this year's competition wraps
        up, use Prepare New Year below to roll the platform over.
      </p>

      <ul class="year__facts">
        <li>
          <span class="year__fact-label">Registration start</span>
          <span v-if="registration?.opens_at">{{ formatStatementTime(registration.opens_at) }}</span>
          <span v-else class="year__muted">not set</span>
        </li>
        <li>
          <span class="year__fact-label">Registration close</span>
          <span v-if="registration?.closes_at">{{ formatStatementTime(registration.closes_at) }}</span>
          <span v-else class="year__muted">not set</span>
        </li>
        <li>
          <span class="year__fact-label">Challenge start</span>
          <span v-if="challengeStart">{{ formatStatementTime(challengeStart) }}</span>
          <span v-else class="year__muted">not set</span>
        </li>
        <li>
          <span class="year__fact-label">Submission deadline</span>
          <span v-if="deadline">{{ formatStatementTime(deadline.closes_at) }}</span>
          <span v-else class="year__muted">not set</span>
        </li>
        <li>
          <span class="year__fact-label">Last extension</span>
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
          <span class="year__fact-label">Notify finalists</span>
          <span v-if="finalists.length" :class="allNotified ? 'year__ok' : 'year__muted'">
            {{ notifiedCount }} of {{ finalists.length }} notified
          </span>
          <span v-else class="year__muted">no finalists</span>
        </li>
        <li>
          <span class="year__fact-label">Symposium date</span>
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
        These steps are instructions for the backend - the Start new year button will
        run them automatically once it's built.
      </p>
      <button type="button" class="btn btn-outline btn-sm" disabled title="Coming soon">
        Start new year <i class="fas fa-rotate" aria-hidden="true"></i>
      </button>
    </section>
  </div>
</template>

<script setup lang="ts">
import { computed, onMounted, ref } from 'vue'
import { formatStatementTime } from '@/utils/date'
import { fetchFinalists, type FinalistRow } from '@/utils/gradingAPI'
import {
  fetchCertificatesRelease,
  fetchChallengeStart,
  fetchFinalistEmailDetails,
  fetchGroupExtensions,
  challengeYear,
  fetchRegistrationOpen,
  fetchRelease,
  fetchSubmissionDeadline,
  type GroupExtension,
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
      'Archives all group tasks, chats and submissions.',
      'Archives all events and announcements, and hides all resources.'
    ]
  },
  {
    title: 'Management',
    steps: [
      'Resets the sent progress of every email.',
      'Clears these dates: Registration Start and End, Challenge Start, Submission Deadline, Symposium (with Confirm Attendance and Slides Due) and Results (Survey Closes).',
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

// Mirrors the backend's current_cohort: the deadline's year, or the calendar
// year while no deadline exists.
const currentYear = computed(() => challengeYear(deadline.value))

onMounted(async () => {
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
})
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

.btn:disabled {
  opacity: 0.55;
  cursor: not-allowed;
}
</style>
