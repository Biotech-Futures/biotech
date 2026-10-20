<template>
  <!-- Management > Challenge Start: the day this year's challenge starts. -->
  <section class="card challenge-start">
    <!-- Headed as a Management page's first card is. -->
    <div class="card-header">
      <h3 class="card-title">Challenge Start</h3>
    </div>
    <p class="challenge-start__hint">
      The day this year's challenge starts. The supervisors' daily Registration status email asks
      for their students' permission forms to be signed by then.
    </p>

    <p v-if="isLoading" class="challenge-start__hint">Loading…</p>
    <template v-else>
      <!-- As Registration Dates: the date, then who last set it. -->
      <div class="challenge-start__state" data-test="challenge-start-state">
        <p>
          Starts: <strong>{{ saved.starts_on ? dayText(saved.starts_on) : 'Not set' }}</strong>
        </p>
        <p v-if="saved.set_by" class="challenge-start__muted" data-test="challenge-start-set-by">
          Set by {{ saved.set_by }}
          <template v-if="saved.updated_at">on {{ formatStatementTime(saved.updated_at) }}</template>
        </p>
      </div>

      <form class="challenge-start__form" @submit.prevent="save(startsOn || null)">
        <label class="challenge-start__field">
          <span>Starts on</span>
          <input v-model="startsOn" type="date" data-test="challenge-start-date" />
        </label>
        <div class="challenge-start__actions">
          <button type="submit" class="btn btn-primary btn-sm" :disabled="isSaving">Save Date</button>
          <button
            type="button"
            class="btn btn-outline btn-sm"
            :disabled="isSaving || !saved.starts_on"
            @click="save(null)"
          >
            Clear Date
          </button>
        </div>
      </form>

      <p v-if="error" class="challenge-start__error" role="alert">{{ error }}</p>
    </template>
  </section>
</template>

<script setup lang="ts">
import { onMounted, ref } from 'vue'

import { apiErrorFromUnknown } from '@/utils/apiError'
import { formatStatementTime } from '@/utils/date'
import { fetchChallengeStart, saveChallengeStart, type ChallengeStart } from '@/utils/managementAPI'

const isLoading = ref(true)
const isSaving = ref(false)
const error = ref('')
const saved = ref<ChallengeStart>({ year: 0, starts_on: null, set_by: '', updated_at: null })
// The form's, as a date input has it: "2026-07-27".
const startsOn = ref('')

/** "27 July 2026", as the email names it (with the year). */
const dayText = (value: string) => {
  const [year, month, day] = value.split('-').map(Number)
  return new Date(year!, month! - 1, day!).toLocaleDateString('en-AU', {
    day: 'numeric',
    month: 'long',
    year: 'numeric',
  })
}

const show = (state: ChallengeStart) => {
  saved.value = state
  startsOn.value = state.starts_on ?? ''
}

const save = async (value: string | null) => {
  isSaving.value = true
  error.value = ''
  try {
    show(await saveChallengeStart(value))
  } catch (err) {
    error.value = apiErrorFromUnknown(err, 'The date could not be saved.').message
  } finally {
    isSaving.value = false
  }
}

onMounted(async () => {
  try {
    show(await fetchChallengeStart())
  } catch (err) {
    error.value = apiErrorFromUnknown(err, 'The date could not be loaded.').message
  } finally {
    isLoading.value = false
  }
})
</script>

<style scoped>
/* Laid out as Registration Dates. */
.challenge-start {
  display: flex;
  flex-direction: column;
  gap: 1rem;
}

.challenge-start__hint {
  color: var(--text-muted);
  font-size: 0.9rem;
  margin: 0;
}

.challenge-start__state {
  display: flex;
  flex-direction: column;
  gap: 0.25rem;
  font-size: 0.9rem;
}

.challenge-start__state p {
  margin: 0;
}

.challenge-start__muted {
  color: var(--text-muted);
}

.challenge-start__form {
  display: flex;
  flex-wrap: wrap;
  align-items: flex-end;
  gap: 1rem;
}

/* As Extend Deadline's fields: the label small above it. */
.challenge-start__field {
  display: flex;
  flex-direction: column;
  gap: 0.3rem;
  font-size: 0.85rem;
  color: var(--teal);
}

.challenge-start__field input {
  border: 1px solid var(--border-light);
  border-radius: 6px;
  padding: 0.45rem 0.6rem;
  font-size: 0.9rem;
  font-family: inherit;
  background: var(--surface-elevated);
  color: var(--teal);
}

.challenge-start__field input:focus {
  outline: none;
  border-color: var(--dark-green);
}

.challenge-start__actions {
  display: flex;
  gap: 0.75rem;
}

.challenge-start__error {
  border-radius: 6px;
  padding: 0.5rem 0.75rem;
  font-size: 0.9rem;
  margin: 0;
  background: color-mix(in srgb, var(--danger) 12%, transparent);
  color: var(--danger);
}
</style>
