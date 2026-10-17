<template>
  <!-- When registration opens and closes this year. -->
  <section class="card registration-dates">
    <h3 class="registration-dates__title">Registration Dates</h3>
    <p class="registration-dates__hint">
      When registration opens and closes this year. Times are in your local timezone
      ({{ localTimeZone }}). Leave one empty for no limit. While it's closed, the sign-in page has
      no Register now button, only a late link lets a student register, and only supervisors
      switched on under Supervisors After Close can register students.
    </p>

    <p v-if="isLoading" class="registration-dates__hint">Loading…</p>
    <template v-else>
      <p
        class="registration-dates__state"
        :class="state.open ? 'registration-dates__state--ok' : 'registration-dates__state--warn'"
        data-test="registration-dates-state"
      >
        <i :class="state.open ? 'fas fa-calendar-check' : 'fas fa-calendar-xmark'" aria-hidden="true"></i>
        {{ state.text }}
      </p>
      <!-- Each date on its own line, as Submission Deadline's Closes. -->
      <div class="registration-dates__dates" data-test="registration-dates-saved">
        <p>
          Opens:
          <strong>{{ saved.opens_at ? formatStatementTime(saved.opens_at) : 'Not set' }}</strong>
        </p>
        <p>
          Closes:
          <strong>{{ saved.closes_at ? formatStatementTime(saved.closes_at) : 'Not set' }}</strong>
        </p>
      </div>

      <form class="registration-dates__form" @submit.prevent="save">
        <label class="registration-dates__field">
          <span>Opens</span>
          <input
            :value="opensLocal"
            type="datetime-local"
            data-test="registration-opens"
            @input="opensLocal = withDefaultTime(opensLocal, ($event.target as HTMLInputElement).value)"
          />
        </label>
        <label class="registration-dates__field">
          <span>Closes</span>
          <input
            :value="closesLocal"
            type="datetime-local"
            data-test="registration-closes"
            @input="closesLocal = withDefaultTime(closesLocal, ($event.target as HTMLInputElement).value)"
          />
        </label>
        <div class="registration-dates__actions">
          <button type="submit" class="btn btn-primary btn-sm" :disabled="isSaving">Save Dates</button>
          <button
            type="button"
            class="btn btn-outline btn-sm"
            :disabled="isSaving || (!saved.opens_at && !saved.closes_at)"
            @click="clearDates"
          >
            Clear Dates
          </button>
        </div>
      </form>

      <p v-if="error" class="registration-dates__error" role="alert">{{ error }}</p>
      <p v-else-if="notice" class="registration-dates__notice" role="status">{{ notice }}</p>
    </template>
  </section>
</template>

<script setup lang="ts">
import { computed, onMounted, ref } from 'vue'

import { loadRegistrationOpen } from '@/composables/useRegistrationOpen'
import { apiErrorFromUnknown } from '@/utils/apiError'
import { describeBrowserTimeZone, formatStatementTime } from '@/utils/date'
import {
  fetchRegistrationManagement,
  saveRegistrationWindow,
  type RegistrationWindow,
} from '@/utils/managementAPI'

const localTimeZone = describeBrowserTimeZone()
const isLoading = ref(true)
const isSaving = ref(false)
const error = ref('')
const notice = ref('')
// As the server has them, and as the form has them (local, timezone-less).
const saved = ref<Pick<RegistrationWindow, 'opens_at' | 'closes_at'>>({ opens_at: null, closes_at: null })
const opensLocal = ref('')
const closesLocal = ref('')

const pad = (value: number) => String(value).padStart(2, '0')

/** "2026-11-30T23:59": an instant as a datetime-local input shows it here. */
const toLocalInput = (value: string | null) => {
  if (!value) return ''
  const date = new Date(value)
  return `${date.getFullYear()}-${pad(date.getMonth() + 1)}-${pad(date.getDate())}T${pad(date.getHours())}:${pad(date.getMinutes())}`
}

// A date picked into an empty field is at 23:59, not the time it was picked
// at (as the browser fills in); a time chosen after that stays.
const withDefaultTime = (before: string, picked: string) =>
  !before && picked ? `${picked.slice(0, 10)}T23:59` : picked

// datetime-local is timezone-less: Date() reads it as local time, and
// toISOString() gives the instant the server keeps.
const fromLocalInput = (value: string) => (value ? new Date(value).toISOString() : null)

const show = (window: Pick<RegistrationWindow, 'opens_at' | 'closes_at'>) => {
  saved.value = { opens_at: window.opens_at, closes_at: window.closes_at }
  opensLocal.value = toLocalInput(window.opens_at)
  closesLocal.value = toLocalInput(window.closes_at)
}

// Where the dates leave registration now.
const state = computed(() => {
  const now = Date.now()
  const { opens_at: opens, closes_at: closes } = saved.value
  if (opens && now < Date.parse(opens)) return { open: false, text: "Registration hasn't opened yet" }
  if (closes && now >= Date.parse(closes)) return { open: false, text: 'Registration has closed' }
  if (opens || closes) return { open: true, text: 'Registration is open' }
  return { open: true, text: 'No dates set: registration is open' }
})

const write = async (dates: Pick<RegistrationWindow, 'opens_at' | 'closes_at'>, done: string) => {
  isSaving.value = true
  error.value = ''
  notice.value = ''
  try {
    show((await saveRegistrationWindow(dates)).window)
    notice.value = done
    // The sign-in page's Register now follows.
    void loadRegistrationOpen(true)
  } catch (err) {
    error.value = apiErrorFromUnknown(err, 'The dates could not be saved.').message
  } finally {
    isSaving.value = false
  }
}

const save = () =>
  write({ opens_at: fromLocalInput(opensLocal.value), closes_at: fromLocalInput(closesLocal.value) }, 'Dates saved.')

const clearDates = () => write({ opens_at: null, closes_at: null }, 'Dates cleared.')

onMounted(async () => {
  try {
    show((await fetchRegistrationManagement()).window)
  } catch (err) {
    error.value = apiErrorFromUnknown(err, 'The dates could not be loaded.').message
  } finally {
    isLoading.value = false
  }
})
</script>

<style scoped>
/* Laid out as Registration Visibility's other cards. */
.registration-dates {
  display: flex;
  flex-direction: column;
  gap: 1rem;
}

.registration-dates__title {
  font-size: 1.05rem;
  font-weight: 600;
  margin: 0;
}

.registration-dates__hint {
  color: var(--text-muted);
  font-size: 0.9rem;
  margin: 0;
}

.registration-dates__state {
  font-weight: 600;
  font-size: 0.9rem;
  margin: 0;
}

.registration-dates__dates {
  display: flex;
  flex-direction: column;
  gap: 0.25rem;
  margin-top: -0.5rem;
  font-size: 0.9rem;
}

.registration-dates__dates p {
  margin: 0;
}

.registration-dates__state--ok {
  color: var(--dark-green);
}

.registration-dates__state--warn {
  color: #eab308;
}

.registration-dates__form {
  display: flex;
  flex-wrap: wrap;
  align-items: flex-end;
  gap: 1rem;
}

/* Each field as Extend Deadline's: its label small above it. */
.registration-dates__field {
  display: flex;
  flex-direction: column;
  gap: 0.3rem;
  font-size: 0.85rem;
  color: var(--teal);
}

.registration-dates__field input {
  border: 1px solid var(--border-light);
  border-radius: 6px;
  padding: 0.45rem 0.6rem;
  font-size: 0.9rem;
  font-family: inherit;
  background: var(--surface-elevated);
  color: var(--teal);
}

.registration-dates__field input:focus {
  outline: none;
  border-color: var(--dark-green);
}

.registration-dates__actions {
  display: flex;
  gap: 0.75rem;
}

.registration-dates__error {
  border-radius: 6px;
  padding: 0.5rem 0.75rem;
  font-size: 0.9rem;
  margin: 0;
  background: color-mix(in srgb, var(--danger) 12%, transparent);
  color: var(--danger);
}

.registration-dates__notice {
  color: var(--dark-green);
  font-size: 0.9rem;
  margin: 0;
}
</style>
