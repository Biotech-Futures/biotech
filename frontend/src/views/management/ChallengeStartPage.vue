<template>
  <!-- Management > Challenge Start: when this year's challenge starts, then what
       students, mentors and supervisors see (Pages Visibility) and when each
       resource is released (Release Resources), set as the challenge begins. -->
  <div class="challenge-start-page">
    <section class="card challenge-start">
      <!-- Headed as a Management page's first card is. -->
      <div class="card-header">
        <h3 class="card-title">Challenge Start</h3>
      </div>
      <p class="challenge-start__hint">
        When this year's challenge starts. Times are in your local timezone ({{ localTimeZone }}).
        The supervisors' weekly Registration status email asks for their students' permission forms
        to be signed by that day.
      </p>
  
      <p v-if="isLoading" class="challenge-start__hint">Loading…</p>
      <template v-else>
        <!-- As Registration Dates: the date and time, then who last set it. -->
        <div class="challenge-start__state" data-test="challenge-start-state">
          <p>
            Starts: <strong>{{ saved.starts_at ? formatStatementTime(saved.starts_at) : 'Not set' }}</strong>
          </p>
          <p v-if="saved.set_by" class="challenge-start__muted" data-test="challenge-start-set-by">
            Set by {{ saved.set_by }}
            <template v-if="saved.updated_at">on {{ formatStatementTime(saved.updated_at) }}</template>
          </p>
        </div>
  
        <form class="challenge-start__form" @submit.prevent="save(fromLocalDateTimeInput(startsAtLocal))">
          <label class="challenge-start__field">
            <span>Starts</span>
            <AppDateTimePicker
              v-model="startsAtLocal"
              class="app-input app-input--compact"
              data-test="challenge-start-date"
              default-time="23:59"
              :min="minuteBeside(order.registrationOpens.value, 1)"
              :max="minuteBeside(order.deadline.value, -1)"
            />
          </label>
          <div class="challenge-start__actions">
            <button type="submit" class="btn btn-primary btn-sm" :disabled="isSaving">Save Date</button>
            <button
              type="button"
              class="btn btn-outline btn-sm"
              :disabled="isSaving || !saved.starts_at"
              @click="save(null)"
            >
              Clear Date
            </button>
          </div>
        </form>
  
        <p v-if="error" class="challenge-start__error" role="alert">{{ error }}</p>
      </template>
    </section>
    <SupervisorPagesPage />
    <ReleaseResourcesPage />
  </div>
</template>

<script setup lang="ts">
import { onMounted, ref } from 'vue'
import AppDateTimePicker from '@/components/AppDateTimePicker.vue'
import { minuteBeside, useDateOrder } from '@/composables/useDateOrder'

import { apiErrorFromUnknown } from '@/utils/apiError'
import {
  describeBrowserTimeZone,
  formatStatementTime,
  fromLocalDateTimeInput,
  toLocalDateTimeInput,
} from '@/utils/date'
import { fetchChallengeStart, saveChallengeStart, type ChallengeStart } from '@/utils/managementAPI'
import ReleaseResourcesPage from './ReleaseResourcesPage.vue'
import SupervisorPagesPage from './SupervisorPagesPage.vue'

const isLoading = ref(true)
const isSaving = ref(false)
const error = ref('')
const saved = ref<ChallengeStart>({ year: 0, starts_at: null, set_by: '', updated_at: null })
// The form's, in this browser's time zone: "2026-07-27T23:59".
const startsAtLocal = ref('')
const localTimeZone = describeBrowserTimeZone()
// Registration's opening and the deadline: when it can be.
const order = useDateOrder()

const show = (state: ChallengeStart) => {
  saved.value = state
  startsAtLocal.value = toLocalDateTimeInput(state.starts_at)
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
  void order.load()
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
/* Its cards one under the other, as Late Registration's are. */
.challenge-start-page {
  display: flex;
  flex-direction: column;
  gap: 1.5rem;
}

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

/* The shared compact box (app-input), at its own width. */
.challenge-start__field .app-input {
  width: auto;
  max-width: none;
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
