<template>
  <!-- When registration opens and closes this year. -->
  <section class="card registration-dates">
    <!-- Headed as a Management page's first card is (Registration's). -->
    <div class="card-header">
      <h3 class="card-title">Registration Dates</h3>
    </div>
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
        <!-- As Submission Deadline's: who last saved them, and when. -->
        <p v-if="saved.set_by" class="registration-dates__muted" data-test="registration-dates-set-by">
          Set by {{ saved.set_by }}
          <template v-if="saved.updated_at">on {{ formatStatementTime(saved.updated_at) }}</template>
        </p>
      </div>

      <form class="registration-dates__form" @submit.prevent="save">
        <label class="registration-dates__field">
          <span>Opens</span>
          <AppDateTimePicker
            v-model="opensLocal"
            class="app-input app-input--compact"
            data-test="registration-opens"
            default-time="23:59"
            clearable
            :max="minuteBeside(order.challengeStart.value, -1)"
          />
        </label>
        <label class="registration-dates__field">
          <span>Closes</span>
          <AppDateTimePicker
            v-model="closesLocal"
            class="app-input app-input--compact"
            data-test="registration-closes"
            default-time="23:59"
            clearable
            :max="minuteBeside(order.deadlineThisYear.value, -1)"
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
    </template>
  </section>
</template>

<script setup lang="ts">
import { computed, onMounted, ref } from 'vue'
import AppDateTimePicker from '@/components/AppDateTimePicker.vue'
import { minuteBeside, useDateOrder } from '@/composables/useDateOrder'

import { loadRegistrationOpen } from '@/composables/useRegistrationOpen'
import { apiErrorFromUnknown } from '@/utils/apiError'
import {
  describeBrowserTimeZone,
  formatStatementTime,
  fromLocalDateTimeInput,
  toLocalDateTimeInput,
} from '@/utils/date'
import {
  fetchRegistrationManagement,
  saveRegistrationWindow,
  type RegistrationWindow,
} from '@/utils/managementAPI'

const localTimeZone = describeBrowserTimeZone()
const isLoading = ref(true)
const isSaving = ref(false)
const error = ref('')
// As the server has them, and as the form has them (local, timezone-less).
type SavedDates = Pick<RegistrationWindow, 'opens_at' | 'closes_at' | 'set_by' | 'updated_at'>
const saved = ref<SavedDates>({ opens_at: null, closes_at: null })
const opensLocal = ref('')
const closesLocal = ref('')

const show = (window: SavedDates) => {
  saved.value = {
    opens_at: window.opens_at,
    closes_at: window.closes_at,
    set_by: window.set_by,
    updated_at: window.updated_at,
  }
  opensLocal.value = toLocalDateTimeInput(window.opens_at)
  closesLocal.value = toLocalDateTimeInput(window.closes_at)
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

// Saved, the dates above (and Set by) show it: no message of its own.
const write = async (dates: Pick<RegistrationWindow, 'opens_at' | 'closes_at'>) => {
  isSaving.value = true
  error.value = ''
  try {
    show((await saveRegistrationWindow(dates)).window)
    // The sign-in page's Register now follows.
    void loadRegistrationOpen(true)
  } catch (err) {
    error.value = apiErrorFromUnknown(err, 'The dates could not be saved.').message
  } finally {
    isSaving.value = false
  }
}

const save = () =>
  write({ opens_at: fromLocalDateTimeInput(opensLocal.value), closes_at: fromLocalDateTimeInput(closesLocal.value) })

const clearDates = () => write({ opens_at: null, closes_at: null })

// The challenge start and the deadline: opening before the one, closing
// before the other.
const order = useDateOrder()

onMounted(async () => {
  void order.load()
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
/* Laid out as Late Registration's cards. */
.registration-dates {
  display: flex;
  flex-direction: column;
  gap: 1rem;
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

.registration-dates__muted {
  color: var(--text-muted);
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

/* The shared compact box (app-input), at its own width. */
.registration-dates__field .app-input {
  width: auto;
  max-width: none;
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
</style>
