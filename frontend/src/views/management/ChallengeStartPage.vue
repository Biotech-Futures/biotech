<template>
  <!-- Management > Challenge Start: when this year's challenge starts, then what
       students, mentors and supervisors see (Pages Visibility), set as the
       challenge begins. When each resource is released is on the Resources page. -->
  <div class="challenge-start-page">
    <section class="card challenge-start">
      <!-- Headed as a Management page's first card is. -->
      <div class="card-header">
        <h3 class="card-title">Challenge Start</h3>
      </div>
      <p class="challenge-start__hint">
        When this year's challenge starts. Times are Sydney time.
        The supervisors' weekly Registration status email asks for their students' permission forms
        to be signed by that day.
      </p>
  
      <p v-if="isLoading" class="challenge-start__hint">Loading…</p>
      <template v-else>
        <!-- As Registration Dates: the date and time, then who last set it. -->
        <div class="challenge-start__state" data-test="challenge-start-state">
          <p>
            Starts: <strong>{{ saved.starts_at ? formatSydneyStatement(saved.starts_at) : 'Not set' }}</strong>
          </p>
          <p v-if="saved.set_by" class="challenge-start__muted" data-test="challenge-start-set-by">
            Set by {{ saved.set_by }}
            <template v-if="saved.updated_at">on {{ formatSydneyStatement(saved.updated_at) }}</template>
          </p>
        </div>
  
        <form class="challenge-start__form" @submit.prevent="save(fromSydneyDateTimeInput(startsAtLocal))">
          <SydneyDateTimeFields
            v-model="startsAtLocal"
            data-test="challenge-start-date"
            date-label="Start Date"
            default-time="00:01"
            :min="minuteBeside(order.registrationOpens.value, 1)"
            :max="minuteBeside(order.deadline.value, -1)"
          />
          <div class="challenge-start__actions">
            <button type="submit" class="btn btn-primary btn-sm" :disabled="isSaving">Save Date</button>
          </div>
        </form>
  
        <p v-if="error" class="challenge-start__error" role="alert">{{ error }}</p>
      </template>
    </section>
    <SupervisorPagesPage />
  </div>
</template>

<script setup lang="ts">
import { onMounted, ref } from 'vue'
import SydneyDateTimeFields from '@/components/management/SydneyDateTimeFields.vue'
import { minuteBeside, useDateOrder } from '@/composables/useDateOrder'

import { apiErrorFromUnknown } from '@/utils/apiError'
import { formatSydneyStatement, fromSydneyDateTimeInput, toSydneyDateTimeInput } from '@/utils/date'
import { fetchChallengeStart, saveChallengeStart, type ChallengeStart } from '@/utils/managementAPI'
import SupervisorPagesPage from './SupervisorPagesPage.vue'

const isLoading = ref(true)
const isSaving = ref(false)
const error = ref('')
const saved = ref<ChallengeStart>({ year: 0, starts_at: null, set_by: '', updated_at: null })
// The form's, in Sydney's time: "2026-07-27T23:59".
const startsAtLocal = ref('')
// Registration's opening and the deadline: when it can be.
const order = useDateOrder()

const show = (state: ChallengeStart) => {
  saved.value = state
  startsAtLocal.value = toSydneyDateTimeInput(state.starts_at)
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
