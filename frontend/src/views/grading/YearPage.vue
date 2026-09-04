<template>
  <p
    v-if="UNDER_CONSTRUCTION"
    style="background: #fff8e1; border: 1px solid #f5d97e; border-radius: 8px; color: #8a6d1a; font-size: 0.85rem; padding: 0.6rem 0.85rem; margin: 0 0 0.75rem"
  >
    <i class="fas fa-hammer" aria-hidden="true"></i>
    The backend for this page is still being built.
  </p>

  <div class="year">
    <section class="card">
      <div class="card-header">
        <h3 class="card-title">Current Year</h3>
      </div>
      <p class="year__value">{{ currentYear }}</p>
      <p class="year__hint">
        The competition year follows the active submission deadline's year — setting next
        year's deadline starts the new year.
      </p>

      <ul class="year__facts">
        <li>
          <span class="year__fact-label">Submission deadline</span>
          <span v-if="deadline">{{ new Date(deadline.closes_at).toLocaleString() }}</span>
          <span v-else class="year__muted">not set</span>
        </li>
        <li>
          <span class="year__fact-label">Marks</span>
          <span :class="marksReleased ? 'year__ok' : 'year__muted'">
            {{ marksReleased ? 'released' : 'not released' }}
          </span>
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
      <ol class="year__steps">
        <li>
          Grading shows only the new year's submissions and finalists — previous years
          stay on record.
        </li>
        <li>
          Sets the last year's deadline on the
          <RouterLink to="/grading/management/submission-deadline">Submission Deadline</RouterLink>
          tab.
        </li>
        <li>Resets marks and certificates from their tabs.</li>
      </ol>
      <p class="year__hint">
        These steps are instructions for the backend — the Start new year button will
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
import {
  fetchCertificatesRelease,
  fetchRelease,
  fetchSubmissionDeadline,
  type ReleaseStatus,
  type SubmissionDeadline
} from '@/utils/gradingAPI'

// Flip to false once the backend flow is signed off.
const UNDER_CONSTRUCTION = true

const deadline = ref<SubmissionDeadline | null>(null)
const marks = ref<ReleaseStatus | null>(null)
const certs = ref<ReleaseStatus | null>(null)

const marksReleased = computed(() => marks.value?.released_at != null)
const certsReleased = computed(() => certs.value?.released_at != null)

// Mirrors the backend's current_cohort: the deadline's year, or the calendar
// year while no deadline exists.
const currentYear = computed(() =>
  deadline.value ? new Date(deadline.value.closes_at).getFullYear() : new Date().getFullYear()
)

onMounted(async () => {
  // Best-effort: each block independent so one failure doesn't blank the page.
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
})
</script>

<style scoped>
.year {
  display: flex;
  flex-direction: column;
  gap: 1rem;
  max-width: 36rem;
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
  color: var(--charcoal);
  font-weight: 600;
}

.year__ok {
  color: var(--dark-green);
  font-weight: 600;
}

.year__muted {
  color: var(--text-muted);
}

.year__steps {
  margin: 0 0 1rem;
  padding-left: 1.2rem;
  font-size: 0.92rem;
  color: var(--charcoal);
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
